from datetime import datetime
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from operator import attrgetter
from pprint import pprint
from collections import OrderedDict

import bs4
import requests
import urllib3
import pandas as pd
import os
import sys
from requests.utils import requote_uri

import config
from ticket import Ticket
from article import Article

session = None

def get_ticket(ticket_id):
    try:
        response = session.get('{0}?Action=AgentTicketZoom;TicketID={1}'.format(config.otrs_url, ticket_id), verify=False)        
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        div_sidebar = soup.find('div', {'class': 'SidebarColumn'})

        label_queue = div_sidebar.find('label', text = 'Очередь:')
        queue_name = label_queue.find_next_siblings('p')[0].get_text(strip=True)
              
        label_name = div_sidebar.find('label', text = 'Имя:')        
        label_last_name = div_sidebar.find('label', text = 'Фамилия:')
        author = '{0} {1}'.format(
            '' if label_last_name is None else label_last_name.find_next_siblings('p')[0].get_text(strip=True),
            '' if label_name is None else label_name.find_next_siblings('p')[0].get_text(strip=True)
        ).strip()

        div_date_info = soup.find('div', {'class': 'AdditionalInformation'})
        date = div_date_info.contents[0].strip().split(": ")[2].split(' кем')[0].strip()

        div_title_close = soup.find('div', {'title': 'Закрыть'})
        td_closed_date = div_title_close.find_parent('tr').find('td', {'class': 'Created'})
        td_closed_from = div_title_close.find_parent('tr').find('td', {'class': 'From'})
        end_date = datetime.strptime(td_closed_date.find('input').get('value'), '%Y-%m-%d %H:%M:%S')
        end_from = td_closed_from.find('a').contents[0]

        h1 = soup.find('h1')        
        title = h1.contents[2].strip()
        ticket_number = h1.contents[0].strip().replace('Заявка №', '')

        articles = get_articles(ticket_id)
        print("Got ticket data", ticket_id)
        return Ticket(ticket_id, ticket_number, author, date, title, queue_name, end_date, end_from, articles)

    except Exception as err:
        print('ticket {0}, error: {1}'.format(ticket_id, err))
        return None


def search_by_pages(attr_search):
    ticket_ids = []
    response = session.post(config.otrs_url, verify=False, data=attr_search)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    pages = soup.find_all("a", id=lambda v: v and v.startswith("AgentTicketSearchPage"))
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
        response = session.get('{0}?Action=AgentTicketAttachment;Subaction=HTMLView;ArticleID={1};FileID=1'.format(config.otrs_url, article_id), verify=False)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        body = soup.find('body')
        body.find('div', {'id': 'turnkey-credit'}).decompose()
        return body.get_text().strip()
    except Exception as err:
        return 'article {0}, error: {1}'.format(article_id, err)

def get_articles(ticket_id):
    response = session.get('{0}?Action=AgentTicketZoom;TicketID={1}'.format(config.otrs_url, ticket_id), verify=False)    
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    tr_elems = soup.find_all('tr', {'class': 'agent-note-internal'})
    articles = []
    for tr in tr_elems:        
        td_class_subject =  tr.find('td', {'class': 'Subject'})
        input_article_subject = td_class_subject.find('input')
        article_subject = input_article_subject.get('value') 
       
        td_class_no = tr.find('td', {'class': 'No'})
        input_article_id = td_class_no.find('input', {'class': 'ArticleID'})
        article_id = input_article_id.get('value') 

        td_class_from = tr.find('td', {'class': 'From'})
        article_from = td_class_from.find('a').contents[0]

        td_class_created = tr.find('td', {'class': 'Created'})
        input_created = td_class_created.find('input')
        article_created = datetime.strptime(input_created.get('value'), '%Y-%m-%d %H:%M:%S')

        if article_subject == 'Закрыть':
            article_text = get_article_text(article_id)
        else:
            article_text = article_subject

        articles.append(Article(article_id, article_from, article_created, article_text))

    return sorted(articles, key=attrgetter('date'), reverse=True)

def report(tickets):   
    for ticket in tickets:
        print('='*80)
        print(ticket.report())        
        for article in ticket.articles:
            print(article.report())
    print('='*80)

def report_html(tickets):
    pd.set_option('display.max_colwidth', -1)
    df = pd.DataFrame.from_records([t.to_ordered_dict() for t in tickets], columns = tickets[0].to_ordered_dict().keys())

    table = df.to_html(escape=False, index=False)
    table = table.replace('<table border="1" class="dataframe">','<table class="table table-sm table-hover">')
    table = table.replace('<th>Заметки</th>', '<th style="width: 30%">Заметки</th>')
    table = table.replace('\\r\\n','<br>').replace('\\n','')
    
    html_string = '''
    <html>
        <head>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.1/css/bootstrap.min.css">
            <style>body{ margin:0 10; background:whitesmoke; } table {font-size: 11px;}</style>
        </head>
        <body>
            <h1>Статистика</h1>        
            ''' + table + '''
        </body>
    </html>'''

    f = open(config.report_path, 'w', encoding='utf-8')
    f.write(html_string)
    f.close()


def get_tickets_by_ids(tickets_ids):
    for id in tickets_ids:
        ticket = get_ticket(id)
        if ticket:
            yield ticket


def configure_search(sys_args):
    attr_search = config.attr_search
    if len(sys.argv) > 1:
        attr_search['TicketCloseTimePoint'] = sys.argv[1]
    return attr_search


if __name__ == '__main__':
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.session()
    session.post(config.otrs_url, data=config.data_login, verify=False)

    attr_search = configure_search(sys.argv)
    tickets_ids = search_by_pages(attr_search)
    n = datetime.now()

    pool = ThreadPool(3)
    #pool = Pool(4)
    tickets = get_tickets_by_ids(tickets_ids)    
    tickets_sorted = sorted(tickets, key=attrgetter('end_date'), reverse=True)    

    report_html(tickets_sorted)

    print(datetime.now(),  datetime.now() - n, len(tickets_sorted))

    os.startfile(config.report_path)