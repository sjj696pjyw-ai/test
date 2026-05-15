import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.domains import is_excluded_domain, extract_domain

print('Testing domain extraction:')
print('extract_domain("https://www.google.com/search"):', extract_domain('https://www.google.com/search'))
print('extract_domain("http://novosibirsk.rus-buket.ru/catalog"):', extract_domain('http://novosibirsk.rus-buket.ru/catalog'))
print('extract_domain("https://rus-buket.ru"):', extract_domain('https://rus-buket.ru'))
print()
print('Testing excluded domains:')
print('is_excluded_domain("market.yandex.ru"):', is_excluded_domain('market.yandex.ru'))
print('is_excluded_domain("rus-buket.ru"):', is_excluded_domain('rus-buket.ru'))
print('is_excluded_domain("novosibirsk.rus-buket.ru"):', is_excluded_domain('novosibirsk.rus-buket.ru'))
print('is_excluded_domain("google.com"):', is_excluded_domain('google.com'))
print('is_excluded_domain("avito.ru"):', is_excluded_domain('avito.ru'))
