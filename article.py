from config import datetime_fmt


class Article:
    def __init__(self, article_id, agent, date, text):
        self.article_id = article_id
        self.agent = agent
        self.date = date
        self.text = text


    def __str__(self):
        return '{0}, {1}, {2}:\r\n{3}'.format(self.article_id, self.date.strftime(datetime_fmt), self.agent, self.text)


    def report(self):
        return '[{1}, {2}] {0}'.format(self.text, self.date.strftime(datetime_fmt), self.agent)