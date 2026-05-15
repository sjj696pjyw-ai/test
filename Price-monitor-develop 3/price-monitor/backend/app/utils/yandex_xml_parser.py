import json
import os
import base64
import xml.etree.ElementTree as ET
import requests


def _get_api_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'yandex_xml.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            if cfg.get('enabled') and cfg.get('key'):
                return cfg['key'], cfg.get('folder_id', '')
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None, None


class YandexXMLParser:
    API_URL = 'https://searchapi.api.cloud.yandex.net/v2/web/search'

    def __init__(self, region='213'):
        self.region = region

    @staticmethod
    def is_configured():
        key, folder_id = _get_api_config()
        return bool(key)

    def search(self, query, positions=5):
        key, folder_id = _get_api_config()
        if not key:
            return {'organic': [], 'ads': []}

        body = {
            'query': {
                'searchType': 'SEARCH_TYPE_RU',
                'queryText': query,
            },
            'responseFormat': 'FORMAT_XML',
        }
        if folder_id:
            body['folderId'] = folder_id

        try:
            resp = requests.post(
                self.API_URL,
                headers={
                    'Authorization': f'Api-Key {key}',
                    'Content-Type': 'application/json',
                },
                json=body,
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get('rawData', '')
            if raw:
                xml_bytes = base64.b64decode(raw)
                return self._parse_response(xml_bytes.decode('utf-8'))
        except requests.RequestException:
            pass
        except (ValueError, KeyError, ET.ParseError):
            pass
        return {'organic': [], 'ads': []}

    def find_competitors(self, queries, positions=5):
        if not self.is_configured():
            return []

        competitors = {}
        for query in queries:
            results = self.search(query, positions)
            for result_type in ('organic', 'ads'):
                for item in results.get(result_type, []):
                    domain = item['domain']
                    if self._exclude_domain(domain):
                        continue
                    if domain not in competitors:
                        competitors[domain] = {
                            'domain': domain,
                            'found_in_queries': [],
                            'positions': {},
                            'types': [],
                        }
                    competitors[domain]['found_in_queries'].append(query)
                    competitors[domain]['positions'][query] = item['position']
                    t = 'ad' if result_type == 'ads' else 'organic'
                    if t not in competitors[domain]['types']:
                        competitors[domain]['types'].append(t)
        return list(competitors.values())

    def _parse_response(self, xml_text):
        result = {'organic': [], 'ads': []}
        try:
            root = ET.fromstring(xml_text)
            ns = self._get_namespace(root)

            for doc in root.findall(f'.//{ns}group/{ns}doc'):
                try:
                    url = doc.findtext(f'{ns}url', '')
                    title = doc.findtext(f'{ns}title', '')
                    result['organic'].append({
                        'position': len(result['organic']) + 1,
                        'domain': self._extract_domain(url),
                        'title': title,
                        'url': url,
                        'type': 'organic',
                    })
                except Exception:
                    continue

            for ad in root.findall(f'.//{ns}ad'):
                try:
                    url = ad.findtext(f'{ns}url', '')
                    title = ad.findtext(f'{ns}title', '')
                    result['ads'].append({
                        'position': len(result['ads']) + 1,
                        'domain': self._extract_domain(url),
                        'title': title,
                        'url': url,
                        'type': 'ad',
                    })
                except Exception:
                    continue

        except ET.ParseError:
            pass
        return result

    @staticmethod
    def _get_namespace(root):
        tag = root.tag
        ns_end = tag.find('}')
        if ns_end != -1:
            return tag[:ns_end + 1]
        return ''

    @staticmethod
    def _extract_domain(url):
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return url

    @staticmethod
    def _exclude_domain(domain):
        domain_lower = domain.lower()
        EXCLUDED = ['google.com', 'yandex.ru', 'yandex.com', 'duckduckgo.com',
                    'facebook.com', 'instagram.com', 'youtube.com',
                    'vk.com', 'ok.ru', 't.me', 'mail.ru']
        for exc in EXCLUDED:
            if exc in domain_lower:
                return True
        return False
