import os
import sys
from datetime import datetime
from multiprocessing.pool import ThreadPool
from operator import attrgetter
from string import Template

import bs4
import pandas as pd
import requests
import urllib3

import config
from article import Article
from ticket import Ticket

session = None


def extract_author_name_part(label):
    if label is None:
        return ''
    else:
        return label.find_next_siblings('p')[0].get_text(strip=True)


def get_ticket(ticket_id):
    try:
        response = session.get(
            f"{config.otrs_url}?Action=AgentTicketZoom;TicketID={ticket_id}",
            verify=False)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        div_sidebar = soup.find('div', {'class': 'SidebarColumn'})

        queue_name = div_sidebar.\
            find('label', text='Очередь:').\
            find_next_siblings('p')[0].get_text(strip=True)

        label_name = div_sidebar.find('label', text='Имя:')
        label_last_name = div_sidebar.find('label', text='Фамилия:')
        author = f'{extract_author_name_part(label_last_name)} \
            {extract_author_name_part(label_name)}'.strip()

        date = soup.find('div', {'class': 'AdditionalInformation'}).\
            contents[0].strip().split(": ")[2].split(' кем')[0].strip()

        tr_title_close = soup.find('div', {'title': 'Закрыть'}).\
            find_parent('tr')
        td_closed_date = tr_title_close.find('td', {'class': 'Created'})
        td_closed_from = tr_title_close.find('td', {'class': 'From'})
        end_date = datetime.strptime(
            td_closed_date.find('input').get('value'), '%Y-%m-%d %H:%M:%S')
        end_from = td_closed_from.find('a').contents[0]

        h1 = soup.find('h1')
        title = h1.contents[2].strip()
        ticket_number = h1.contents[0].strip().replace('Заявка №', '')

        articles = get_articles(ticket_id)
        print("Got ticket data", ticket_id)
        return Ticket(ticket_id, ticket_number, author, date, title,
                      queue_name, end_date, end_from, articles)

    except Exception as err:
        print('ticket {0}, error: {1}'.format(ticket_id, err))
        return None


def search_by_pages(attr_search):
    ticket_ids = []
    response = session.post(config.otrs_url, verify=False, data=attr_search)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    pages = soup.find_all(
        "a", id=lambda v: v and v.startswith("AgentTicketSearchPage"))
    if not pages:
        pages.append("page1")
    for page_num, _ in enumerate(pages):
        ticket_ids.extend(search_tickets_ids(page_num, attr_search))
    return ticket_ids


def search_tickets_ids(page_num, attr_search):
    attr_search['StartHit'] = page_num*35+1
    response = session.post(config.otrs_url, verify=False, data=attr_search)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    inputs_ticketId = soup.find_all('a', {'class': 'MasterActionLink'})
    return [i["href"][-5:] for i in inputs_ticketId]


def get_article_text(article_id):
    try:
        response = session.get(
            f"{config.otrs_url}?"
            f"Action=AgentTicketAttachment;Subaction=HTMLView;"
            f"ArticleID={article_id};FileID=1",
            verify=False)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        body = soup.find('body')
        body.find('div', {'id': 'turnkey-credit'}).decompose()
        return body.get_text().strip()
    except Exception as err:
        return 'article {0}, error: {1}'.format(article_id, err)


def get_articles(ticket_id):
    response = session.get(
        '{0}?Action=AgentTicketZoom;TicketID={1}'.
        format(config.otrs_url, ticket_id), verify=False)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')

    tr_elems = soup.find_all('tr', {'class': 'agent-note-internal'})
    articles = []
    for tr in tr_elems:
        article_subject = tr.find('td', {'class': 'Subject'}). \
            find('input'). get('value')

        article_id = tr.find('td', {'class': 'No'}). \
            find('input', {'class': 'ArticleID'}).get('value')

        article_from = tr.find('td', {'class': 'From'}).find('a').contents[0]

        article_created = datetime.strptime(
            tr.find('td', {'class': 'Created'}).find('input').get('value'),
            '%Y-%m-%d %H:%M:%S')

        if article_subject == 'Закрыть':
            article_text = get_article_text(article_id)
        else:
            article_text = article_subject

        articles.append(
            Article(article_id, article_from, article_created, article_text))

    return sorted(articles, key=attrgetter('date'), reverse=True)


def report_html(tickets):
    pd.set_option('display.max_colwidth', -1)
    df = pd.DataFrame.from_records(
        [t.to_ordered_dict() for t in tickets],
        columns=tickets[0].to_ordered_dict().keys())

    table = df.to_html(
        escape=False,
        justify='center',
        classes=["table-bordered", "table-sm", "table-hover"],
        index=False
        )

    table = table.replace(
        '<th>Заметки</th>',
        '<th style="width: 30%">Заметки</th>')
    table = table.replace('\\r\\n', '<br>').replace('\\n', '')

    with open('report.template', encoding='utf-8') as template_file:
        template = Template(template_file.read())
        html_string = template.substitute({'table': table})

    with open(config.report_path, 'w', encoding='utf-8') as f:
        f.write(html_string)


def get_tickets_by_ids(tickets_ids):
    for id in tickets_ids:
        ticket = get_ticket(id)
        if ticket:
            yield ticket


def configure_search(sys_args):
    attr_search = config.attr_search
    if len(sys.argv) > 1:
        attr_search['TicketCloseTimePoint'] = sys.argv[1]
    else:
        attr_search['TicketCloseTimePoint'] = 1
    return attr_search


if __name__ == '__main__':
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    dt_start = datetime.now()

    session = requests.session()
    session.post(config.otrs_url, data=config.data_login, verify=False)

    attr_search = configure_search(sys.argv)
    tickets_ids = search_by_pages(attr_search)

    print(f'Tickets count: {len(tickets_ids)}')

    pool = ThreadPool(3)

    tickets = get_tickets_by_ids(tickets_ids)
    tickets_sorted = sorted(tickets, key=attrgetter('end_date'), reverse=True)

    print(f'Execution time: {datetime.now() - dt_start}')

    report_html(tickets_sorted)

    os.startfile(config.report_path)
