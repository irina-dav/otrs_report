from collections import OrderedDict

from article import Article
from config import datetime_fmt


class Ticket:
    def __init__(self, ticket_id, ticket_number, author, date, title, queue_name, end_date, end_owner, articles):
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.author = author
        self.date = date
        self.title = title
        self.queue_name = queue_name
        self.end_date = end_date
        self.end_owner = end_owner
        self.articles = articles


    def __str__(self):
        return 'Заявка №{0} ({1}), {2}, {3}, тема: {4}, дата: {5} [{6}]'.format(
            self.ticket_number, self.ticket_id, self.end_date, self.author, self.title, self.date, self.queue_name
            ) 


    def report(self):
        return '{0}, {1}\r\nЗаявка №{2} ({3}) от {4}, автор: {5}, тема: {6}'.format(
            self.end_date.strftime(datetime_fmt), self.end_owner,  self.ticket_number, self.ticket_id, self.date, self.author, self.title
            )    


    def to_ordered_dict(self):
        return OrderedDict([
            ('Заметки', '\r\n'.join([a.report() for a in self.articles])),
            ('Дата закрытия', self.end_date.strftime(datetime_fmt)),
            ('Завершил', self.end_owner),
            ('Заявка', self.title),
            ('Номер заявки', '%s (%s)' % (self.ticket_number, self.ticket_id)),
            ('Дата заявки', self.date),
            ('Автор', self.author),
            ('Группа', self.queue_name),
        ])
