datetime_fmt = '%d.%m.%Y %H:%M'

headers = {
    'cache-control': "no-cache",
}
data_login = {
    'Action': 'Login',
    'User': 'user_name',
    'Password': 'user_password',
}
attr_search = {
    'Action': 'AgentTicketSearch',
    'Subaction': 'Search',
    'CloseTimeSearchType': 'TimePoint',
    'TicketCloseTimePointStart': 'Last',
    'TicketCloseTimePoint': '2',
    'TicketCloseTimePointFormat': 'day',
    'AttributeOrig': 'TicketNumber',
    'ResultForm': 'Normal',
    'SortBy': 'Changed',
    'StateType': 'closed',
}

otrs_url = 'https://otrs.domen.com/otrs/index.pl'
report_path = 'd://temp//report.html'
