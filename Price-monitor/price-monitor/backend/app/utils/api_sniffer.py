"""Автоопределение внутреннего API каталога — без участия пользователя.

Зачем: многие каталоги (SPA на Nuxt/React) отдают в HTML только первую порцию
товаров, а остальное подгружают запросами из браузера. Ссылок на страницы нет,
поэтому обойти каталог по URL нельзя, а кликать «Показать ещё» 60+ раз слишком
долго.

Идея: один раз открыть страницу в браузере с перехватчиком сети, нажать
«Показать ещё» и посмотреть, каким запросом сайт получил следующую порцию.
Дальше этот запрос повторяется напрямую (без браузера), меняя номер страницы, —
весь каталог собирается за секунды.

Перехват ставится через CDP до выполнения скриптов страницы, поэтому ловятся
все вызовы fetch/XMLHttpRequest, включая GraphQL.
"""
import json
import logging
import re

from .auto_extract import _dedup, _walk_for_products

logger = logging.getLogger(__name__)

# Максимальный размер тела ответа, который забираем из браузера. Ответы каталогов
# бывают на несколько мегабайт: если обрезать слишком рано, JSON перестанет
# парситься и товары не найдутся.
_MAX_BODY = 4_000_000

# JS-перехватчик fetch/XHR. Пишет вызовы в window.__pmNet.
HOOK_JS = r"""
(() => {
  if (window.__pmNet) return;
  window.__pmNet = [];
  const MAX = %d;
  // Буфер намеренно большой: при загрузке страницы сайт делает десятки
  // запросов, и нужный (за следующей порцией товаров) идёт последним.
  const keep = (entry) => { if (window.__pmNet.length < 400) window.__pmNet.push(entry); };

  const origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      const url = (typeof input === 'string') ? input : (input && input.url) || '';
      const method = (init && init.method) || (input && input.method) || 'GET';
      const body = (init && init.body) || null;
      const headers = {};
      try {
        const h = (init && init.headers) || (input && input.headers);
        if (h) {
          if (typeof h.forEach === 'function') h.forEach((v, k) => { headers[k] = v; });
          else Object.assign(headers, h);
        }
      } catch (e) { /* ignore */ }
      return origFetch.apply(this, arguments).then((resp) => {
        try {
          resp.clone().text().then((text) => {
            keep({ url: String(url), method: String(method).toUpperCase(),
                   body: body ? String(body).slice(0, MAX) : null,
                   headers: headers, status: resp.status, text: text.slice(0, MAX) });
          }).catch(() => {});
        } catch (e) { /* ignore */ }
        return resp;
      });
    };
  }

  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  const origSet = XMLHttpRequest.prototype.setRequestHeader;
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__pm = { url: String(u), method: String(m || 'GET').toUpperCase(), headers: {} };
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.setRequestHeader = function (k, v) {
    if (this.__pm) this.__pm.headers[k] = v;
    return origSet.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    const info = this.__pm;
    if (info) {
      this.addEventListener('load', () => {
        try {
          keep({ url: info.url, method: info.method,
                 body: body ? String(body).slice(0, MAX) : null,
                 headers: info.headers, status: this.status,
                 text: String(this.responseText || '').slice(0, MAX) });
        } catch (e) { /* ignore */ }
      });
    }
    return origSend.apply(this, arguments);
  };
})();
""" % _MAX_BODY


def install_hook(driver):
    """Ставит перехватчик до выполнения скриптов страницы. True — получилось."""
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': HOOK_JS})
        return True
    except Exception as e:
        logger.debug(f"[API] не удалось поставить перехватчик: {e}")
        return False


def collect_calls(driver):
    """Забирает перехваченные вызовы из браузера."""
    try:
        calls = driver.execute_script('return window.__pmNet || [];') or []
    except Exception as e:
        logger.debug(f"[API] не удалось прочитать перехваченные вызовы: {e}")
        return []
    return [c for c in calls if isinstance(c, dict) and c.get('text')]


def _salvage_json(text):
    """Пытается разобрать JSON, в том числе обрезанный.

    Если ответ был усечён (слишком большой), json.loads падает — тогда режем
    хвост до последнего закрытого объекта и достраиваем недостающие скобки,
    чтобы вытащить хотя бы часть товаров."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    cut = max(text.rfind('}'), text.rfind(']'))
    if cut <= 0:
        return None
    head = text[:cut + 1]
    # достраиваем незакрытые скобки в правильном порядке
    stack = []
    in_str = False
    esc = False
    for ch in head:
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in '{[':
            stack.append('}' if ch == '{' else ']')
        elif ch in '}]' and stack:
            stack.pop()
    try:
        return json.loads(head + ''.join(reversed(stack)))
    except (ValueError, TypeError):
        return None


def products_from_payload(text):
    """Извлекает товары из тела ответа API (любая структура JSON)."""
    if not text:
        return []
    data = _salvage_json(text)
    if data is None:
        return []
    out = []
    try:
        _walk_for_products(data, out)
    except Exception:
        return []
    return _dedup(out)


def find_product_api(calls, min_products=3):
    """Выбирает среди перехваченных вызовов тот, что вернул больше всего товаров.

    Возвращает (call, products) или (None, [])."""
    best, best_products = None, []
    scored = []
    for call in calls:
        products = products_from_payload(call.get('text'))
        scored.append((len(products), len(call.get('text') or ''), call))
        if len(products) > len(best_products):
            best, best_products = call, products

    if best and len(best_products) >= min_products:
        logger.info(
            f"[API] найден источник товаров: {best.get('method')} "
            f"{str(best.get('url'))[:120]} — {len(best_products)} товаров в ответе"
        )
        return best, best_products

    # Ничего не подошло — печатаем, что вообще видели, иначе причину не понять.
    # hits — признаки товарных данных в сыром ответе: если он большой и hits>0,
    # значит запрос мы поймали, но не распознали его формат.
    scored.sort(key=lambda x: (-x[0], -x[1]))
    logger.warning(
        f"[ДИАГНОСТИКА API] источник товаров не найден: вызовов {len(calls)}, "
        f"максимум товаров в ответе {max([s[0] for s in scored], default=0)}"
    )
    for n, size, call in scored[:8]:
        text = call.get('text') or ''
        hits = len(re.findall(r'"(?:price|minPrice|salePrice|cost|name|title)"\s*:', text))
        logger.warning(
            f"[ДИАГНОСТИКА API]   {call.get('method', '?'):4} "
            f"статус={call.get('status')} размер={size} товаров={n} "
            f"признаков_товара={hits} {str(call.get('url'))[:110]}"
        )
        # у самого «товарного» ответа показываем начало — по нему видно формат
        if hits > 0 and size > 500:
            logger.warning(f"[ДИАГНОСТИКА API]   начало ответа: {text[:400]}")
    return None, []


# Ключи, по которым узнаём параметр страницы/смещения в URL или теле запроса.
_PAGE_KEYS = ('page', 'pagenumber', 'page_number', 'pagen', 'pageindex', 'p')
_OFFSET_KEYS = ('offset', 'start', 'from', 'skip')
_LIMIT_KEYS = ('limit', 'pagesize', 'page_size', 'per_page', 'count', 'size')


def _bump_in_obj(obj, step_page=1, limit_hint=None):
    """Ищет в JSON-структуре параметр страницы/смещения и увеличивает его.

    Возвращает (новый объект, описание) или (None, None), если не нашли."""
    found = {}

    def walk(node, path=()):
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower()
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if lk in _PAGE_KEYS and 'page' not in found:
                        found['page'] = (path + (k,), v)
                    elif lk in _OFFSET_KEYS and 'offset' not in found:
                        found['offset'] = (path + (k,), v)
                    elif lk in _LIMIT_KEYS and 'limit' not in found:
                        found['limit'] = (path + (k,), v)
                walk(v, path + (k,))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + (i,))

    walk(obj)

    def set_at(root, path, value):
        cur = root
        for key in path[:-1]:
            cur = cur[key]
        cur[path[-1]] = value

    import copy
    if 'page' in found:
        path, value = found['page']
        new = copy.deepcopy(obj)
        set_at(new, path, int(value) + step_page)
        return new, f"page={int(value) + step_page}"
    if 'offset' in found:
        path, value = found['offset']
        limit = limit_hint or (found.get('limit', (None, 25))[1]) or 25
        new = copy.deepcopy(obj)
        set_at(new, path, int(value) + int(limit) * step_page)
        return new, f"offset={int(value) + int(limit) * step_page}"
    return None, None


def _bump_in_url(url, step_page=1):
    """Увеличивает номер страницы/смещение в query-параметрах URL."""
    from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if not query:
        return None, None

    limit = None
    for k, v in query.items():
        if k.lower() in _LIMIT_KEYS and v and str(v[0]).isdigit():
            limit = int(v[0])
            break

    for k, v in query.items():
        if not v or not str(v[0]).lstrip('-').isdigit():
            continue
        lk = k.lower()
        if lk in _PAGE_KEYS:
            query[k] = [str(int(v[0]) + step_page)]
            return urlunsplit(parts._replace(query=urlencode(query, doseq=True))), f"{k}={query[k][0]}"
        if lk in _OFFSET_KEYS:
            query[k] = [str(int(v[0]) + (limit or 25) * step_page)]
            return urlunsplit(parts._replace(query=urlencode(query, doseq=True))), f"{k}={query[k][0]}"
    return None, None


def paginate_api(call, fetch_json, max_pages=200, page_size_hint=None, stop_when=None):
    """Повторяет найденный запрос, увеличивая страницу, и копит товары.

    fetch_json(url, method, headers, body) -> текст ответа (или None).
    stop_when(total_collected) -> True, если пора остановиться.
    Возвращает список товаров (без первой порции — её добавляет вызывающий код).
    """
    url = call.get('url')
    method = (call.get('method') or 'GET').upper()
    headers = {k: v for k, v in (call.get('headers') or {}).items()
               if k.lower() not in ('content-length', 'host')}
    raw_body = call.get('body')

    body_obj = None
    if raw_body:
        try:
            body_obj = json.loads(raw_body)
        except (ValueError, TypeError):
            body_obj = None

    acc = []
    seen = set()
    zero = 0

    for step in range(1, max_pages + 1):
        next_url, note = url, None
        next_body = raw_body

        if body_obj is not None:
            bumped, note = _bump_in_obj(body_obj, step_page=step, limit_hint=page_size_hint)
            if bumped is None:
                next_url, note = _bump_in_url(url, step_page=step)
                if next_url is None:
                    break
            else:
                next_body = json.dumps(bumped)
        else:
            next_url, note = _bump_in_url(url, step_page=step)
            if next_url is None:
                break

        text = fetch_json(next_url, method, headers, next_body)
        items = products_from_payload(text)
        added = 0
        for p in items:
            key = (p['name'].strip().lower(), p.get('price'))
            if key in seen:
                continue
            seen.add(key)
            acc.append(p)
            added += 1

        if added == 0:
            zero += 1
            if zero >= 2:
                break
        else:
            zero = 0

        if stop_when and stop_when(len(acc)):
            break

    logger.info(f"[API] дозагружено через API: {len(acc)} товаров")
    return acc


def looks_like_api_url(url):
    """Грубый фильтр: похоже ли на вызов данных, а не на статику/аналитику."""
    u = (url or '').lower()
    if not u:
        return False
    if re.search(r'\.(png|jpe?g|gif|svg|webp|css|woff2?|ttf|ico|mp4)(\?|$)', u):
        return False
    if any(s in u for s in ('google-analytics', 'googletagmanager', 'mc.yandex',
                            'metrika', 'sentry', 'criteo', 'facebook')):
        return False
    return True
