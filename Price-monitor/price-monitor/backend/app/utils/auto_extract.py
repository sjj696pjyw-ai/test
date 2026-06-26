"""Селектор-независимое извлечение товаров со страницы.

Идея: пользователю не нужно вручную задавать CSS-селекторы — мы пытаемся достать
карточки из машиночитаемых источников, которые многие магазины уже отдают в
разметке, по убыванию надёжности:

  0) YML/price-фид (parse_yml) — отдельный XML, подключается из SiteParser;
  1) JSON-LD  — <script type="application/ld+json"> со схемой Product/Offer/ItemList;
  2) microdata — itemtype=schema.org/Product + itemprop name/price/offers;
  3) встроенный JSON состояния SPA — __NEXT_DATA__ / window.__NUXT__ /
     window.__INITIAL_STATE__ (там часто лежит весь список товаров);
  4) структурный анализ DOM (extract_dom) — повторяющиеся карточки без разметки.

Каждый извлекатель возвращает список словарей того же формата, что и
SiteParser.parse_products: {name, price, currency, url?, external_id?}. Цена всегда
число (RUB по умолчанию). Если источник не дал товаров — возвращается пустой список,
и вызывающий код может перейти к следующему тиру (вплоть до ручных селекторов).
"""
import json
import re

from bs4 import BeautifulSoup

# Порядок тиров, которые пробует auto_extract (имя метода -> функция).
# Заполняется в конце модуля, после объявления функций.
EXTRACTORS = []


def _to_price(value):
    """Приводит цену из разметки к числу. Принимает int/float/str.
    Возвращает float или None, если распарсить не удалось."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # убираем валютные символы/пробелы-разделители разрядов; запятая -> точка
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    # "1 299,90" -> "1299.90"; "1,299.90" -> "1299.90"
    if "," in s and "." in s:
        # последний разделитель считаем десятичным
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # запятая как десятичный разделитель только если 1-2 знака после неё
        if re.search(r",\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        val = float(s)
    except ValueError:
        return None
    return val if val > 0 else None


def _norm_name(value):
    if not isinstance(value, str):
        return None
    name = re.sub(r"\s+", " ", value).strip()
    return name or None


def _make_product(name, price, currency=None, url=None, external_id=None):
    """Собирает товар в едином формате, либо None, если нет имени/цены."""
    name = _norm_name(name)
    price = _to_price(price)
    if not name or price is None:
        return None
    item = {"name": name, "price": price, "currency": (currency or "RUB")}
    if url:
        item["url"] = url
    if external_id:
        item["external_id"] = str(external_id)
    return item


def _dedup(products):
    """Убирает дубли по (имя.lower, цена)."""
    seen, out = set(), []
    for p in products:
        key = (p["name"].strip().lower(), round(float(p["price"]), 2))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# Тир 1: JSON-LD
# ---------------------------------------------------------------------------

_TYPE_PRODUCT = {"product", "productmodel"}


def _types_of(node):
    """Множество @type узла в нижнем регистре (тип может быть строкой или списком)."""
    t = node.get("@type") if isinstance(node, dict) else None
    if isinstance(t, str):
        return {t.lower()}
    if isinstance(t, list):
        return {str(x).lower() for x in t}
    return set()


def _price_from_offers(offers):
    """Достаёт (price, currency) из offers (Offer | AggregateOffer | список)."""
    if offers is None:
        return None, None
    if isinstance(offers, list):
        for off in offers:
            price, cur = _price_from_offers(off)
            if price is not None:
                return price, cur
        return None, None
    if isinstance(offers, dict):
        price = offers.get("price")
        if price is None:
            price = offers.get("lowPrice") or offers.get("highPrice")
        cur = offers.get("priceCurrency")
        # иногда цена внутри priceSpecification
        if price is None and isinstance(offers.get("priceSpecification"), dict):
            spec = offers["priceSpecification"]
            price = spec.get("price")
            cur = cur or spec.get("priceCurrency")
        return price, cur
    return None, None


def _iter_jsonld_nodes(data):
    """Рекурсивно обходит JSON-LD, разворачивая @graph и списки."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_jsonld_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            yield from _iter_jsonld_nodes(data["@graph"])
        yield data
        # ItemList -> элементы
        elements = data.get("itemListElement")
        if isinstance(elements, list):
            for el in elements:
                if isinstance(el, dict):
                    # ListItem с вложенным item, либо сам Product
                    yield from _iter_jsonld_nodes(el.get("item", el))


def extract_jsonld(html):
    soup = BeautifulSoup(html, "lxml")
    products = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for node in _iter_jsonld_nodes(data):
            if not isinstance(node, dict):
                continue
            if not (_types_of(node) & _TYPE_PRODUCT):
                continue
            price, cur = _price_from_offers(node.get("offers"))
            item = _make_product(
                node.get("name"),
                price,
                currency=cur,
                url=node.get("url") if isinstance(node.get("url"), str) else None,
                external_id=node.get("sku") or node.get("mpn"),
            )
            if item:
                products.append(item)
    return _dedup(products)


# ---------------------------------------------------------------------------
# Тир 2: microdata (schema.org/Product)
# ---------------------------------------------------------------------------


def _itemprop_value(scope, prop):
    """Значение itemprop в пределах scope: content-атрибут, либо текст."""
    el = scope.find(attrs={"itemprop": prop})
    if not el:
        return None
    if el.has_attr("content") and el["content"].strip():
        return el["content"].strip()
    if el.name in ("meta",) and el.has_attr("content"):
        return el["content"].strip()
    return el.get_text(strip=True) or None


def extract_microdata(html):
    soup = BeautifulSoup(html, "lxml")
    products = []
    for scope in soup.find_all(attrs={"itemtype": True}):
        itemtype = scope.get("itemtype", "")
        if "schema.org/product" not in itemtype.lower():
            continue
        name = _itemprop_value(scope, "name")
        price = _itemprop_value(scope, "price")
        if price is None:
            price = _itemprop_value(scope, "lowPrice")
        currency = _itemprop_value(scope, "priceCurrency")
        url = None
        link = scope.find(attrs={"itemprop": "url"})
        if link and link.has_attr("href"):
            url = link["href"]
        item = _make_product(
            name, price, currency=currency, url=url,
            external_id=_itemprop_value(scope, "sku"),
        )
        if item:
            products.append(item)
    return _dedup(products)


# ---------------------------------------------------------------------------
# Тир 3: встроенный JSON состояния (SPA)
# ---------------------------------------------------------------------------

_NAME_KEYS = ("name", "title", "productName", "product_name", "displayName")
_PRICE_KEYS = (
    "price", "priceValue", "price_value", "finalPrice", "final_price",
    "salePrice", "sale_price", "minPrice", "min_price", "priceMin", "actualPrice",
)
_CURRENCY_KEYS = ("currency", "priceCurrency", "currencyCode")
_SKU_KEYS = ("sku", "article", "vendorCode", "id", "offerId", "externalId")


def _looks_like_product(obj):
    """dict похож на товар, если есть строковое имя и положительная цена."""
    if not isinstance(obj, dict):
        return None
    name = next((obj[k] for k in _NAME_KEYS if isinstance(obj.get(k), str) and obj.get(k).strip()), None)
    if not name:
        return None
    price = None
    for k in _PRICE_KEYS:
        if k in obj:
            price = _to_price(obj[k])
            if price is not None:
                break
    if price is None:
        return None
    currency = next((obj[k] for k in _CURRENCY_KEYS if isinstance(obj.get(k), str)), None)
    external_id = next((obj[k] for k in _SKU_KEYS if isinstance(obj.get(k), (str, int))), None)
    return _make_product(name, price, currency=currency, external_id=external_id)


def _walk_for_products(data, out, depth=0, limit=5000):
    if len(out) >= limit or depth > 12:
        return
    if isinstance(data, dict):
        prod = _looks_like_product(data)
        if prod:
            out.append(prod)
        for v in data.values():
            _walk_for_products(v, out, depth + 1, limit)
    elif isinstance(data, list):
        for v in data:
            _walk_for_products(v, out, depth + 1, limit)


def _embedded_json_blobs(html):
    """Возвращает JSON-строки из встроенного состояния страницы (разные фреймворки)."""
    blobs = []
    soup = BeautifulSoup(html, "lxml")
    # <script id="__NEXT_DATA__"> и любые <script type="application/json">
    for tag in soup.find_all("script", attrs={"type": "application/json"}):
        body = (tag.string or tag.get_text() or "").strip()
        if body:
            blobs.append(body)
    # window.__NUXT__ / __INITIAL_STATE__ / __APOLLO_STATE__ / __PRELOADED_STATE__ = {...}
    for m in re.finditer(
        r"window\.(?:__NUXT__|__INITIAL_STATE__|__APOLLO_STATE__|__PRELOADED_STATE__)"
        r"\s*=\s*(\{.*?\})\s*[;<]",
        html, re.DOTALL,
    ):
        blobs.append(m.group(1))
    return blobs


def extract_embedded_json(html):
    products = []
    for blob in _embedded_json_blobs(html):
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            continue
        found = []
        _walk_for_products(data, found)
        products.extend(found)
    return _dedup(products)


# ---------------------------------------------------------------------------
# Тир 4: структурный анализ DOM (повторяющиеся карточки без разметки)
# ---------------------------------------------------------------------------

_PRICE_IN_TEXT = re.compile(r"(\d[\d\s  ]{0,12}\d|\d)\s*(?:₽|руб|р\.)", re.IGNORECASE)
_NON_NAME_WORDS = (
    "в корзину", "купить", "подробнее", "показать", "избранн", "сравн",
    "добавить", "заказать", "быстрый", "в наличии", "под заказ",
)
_MIN_CARDS = 3


def _is_price_text(text):
    return bool(text) and len(text) <= 40 and bool(_PRICE_IN_TEXT.search(text))


def _sig(el):
    """Сигнатура элемента: (тег, отсортированные классы). Без класса — None."""
    classes = el.get("class") if hasattr(el, "get") else None
    if not classes:
        return None
    return (el.name, tuple(sorted(classes)))


def _price_texts(scope):
    """Тексты самых внутренних «ценовых» элементов внутри scope.
    Берём именно их, а не весь текст карточки, чтобы цифры из названия
    (напр. «iPhone 17») не приклеивались к цене."""
    out = []
    for el in scope.find_all(True):
        t = el.get_text(" ", strip=True)
        if not _is_price_text(t):
            continue
        if any(_is_price_text(c.get_text(" ", strip=True)) for c in el.find_all(True, recursive=False)):
            continue
        out.append(t)
    return out


def _card_price(card):
    texts = _price_texts(card)
    if not texts:  # запасной вариант — общий текст карточки
        texts = [card.get_text(" ", strip=True)]
    nums = []
    for t in texts:
        for m in _PRICE_IN_TEXT.finditer(t):
            v = _to_price(m.group(0))
            if v is not None:
                nums.append(v)
    if not nums:
        return None
    threshold = max(nums) * 0.3  # отбрасываем зачёркнутую старую цену
    big = [n for n in nums if n >= threshold]
    return min(big) if big else min(nums)


# метка вариации товара: вес/объём/количество (420 г, 0.85 кг, 500 мл, 1 шт)
_UNIT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:кг|гр|мл|шт|г|л|kg|ml|g|l)\b", re.IGNORECASE)


def _price_elements(card):
    """Самые внутренние элементы карточки, содержащие цену."""
    out = []
    for el in card.find_all(True):
        t = el.get_text(" ", strip=True)
        if not _is_price_text(t):
            continue
        if any(_is_price_text(c.get_text(" ", strip=True)) for c in el.find_all(True, recursive=False)):
            continue
        out.append(el)
    return out


def _variant_label(price_el):
    """Метка вариации рядом с ценой (вес/объём). Ищем у самого ценового элемента
    и поднимаясь к строке-вариации (до 3 уровней)."""
    node = price_el
    for _ in range(3):
        if node is None:
            break
        m = _UNIT_RE.search(node.get_text(" ", strip=True))
        if m:
            return _norm_name(m.group(0))
        node = node.parent
    return None


def _card_variants(card, base_name):
    """Возвращает [(name, price)] для карточки. Если у карточки несколько цен и
    у каждой есть своя метка-вариация (вес/объём) — раскрываем в несколько
    товаров с меткой в названии; иначе — один товар."""
    price_els = _price_elements(card)
    if len(price_els) <= 1:
        p = _card_price(card)
        return [(base_name, p)] if p is not None else []

    pairs = []
    for pe in price_els:
        m = _PRICE_IN_TEXT.search(pe.get_text(" ", strip=True))
        price = _to_price(m.group(0)) if m else None
        if price is None:
            continue
        pairs.append((_variant_label(pe), price))

    labels = [lbl for lbl, _ in pairs]
    # раскрываем только при чистом соответствии 1 метка ↔ 1 цена
    if len(pairs) >= 2 and all(labels) and len(set(labels)) == len(labels):
        return [(f"{base_name} {lbl}", price) for lbl, price in pairs]

    # не удалось разметить — один товар с разумной ценой
    p = _card_price(card)
    return [(base_name, p)] if p is not None else []


def _card_name_and_url(card):
    """Название карточки = заметная ссылка/заголовок (не цена, не кнопка)."""
    best = None
    for a in card.find_all("a"):
        txt = a.get_text(" ", strip=True)
        if not txt or len(txt) < 3 or len(txt) > 160 or _is_price_text(txt):
            continue
        if any(w in txt.lower() for w in _NON_NAME_WORDS):
            continue
        href = a.get("href")
        score = len(txt) + (100 if href else 0)
        if best is None or score > best[0]:
            best = (score, txt, href)
    if best:
        return best[1], best[2]
    for h in card.find_all(["h1", "h2", "h3", "h4"]):
        txt = h.get_text(" ", strip=True)
        if txt and not _is_price_text(txt):
            return txt, None
    return None, None


def extract_dom(html):
    """Находит повторяющиеся карточки товаров по структуре, без разметки/селекторов.

    Идея: берём «ценоподобные» узлы, поднимаемся к самому внешнему предку с
    классом, чья сигнатура повторяется по странице (это и есть карточка), и из
    каждой карточки достаём цену и заметную ссылку-название. Промо и одиночные
    блоки отсекаются по частоте сигнатуры.
    """
    soup = BeautifulSoup(html, "lxml")

    # частота сигнатур по всему документу
    freq = {}
    for el in soup.find_all(True):
        s = _sig(el)
        if s:
            freq[s] = freq.get(s, 0) + 1

    # «ценовые» узлы — самые внутренние элементы с ценой
    price_nodes = []
    for el in soup.find_all(True):
        t = el.get_text(" ", strip=True)
        if not _is_price_text(t):
            continue
        if any(_is_price_text(c.get_text(" ", strip=True)) for c in el.find_all(True, recursive=False)):
            continue  # есть потомок с ценой — берём его, не этот
        price_nodes.append(el)

    if len(price_nodes) < _MIN_CARDS:
        return []

    # «Карточный» диапазон частоты сигнатуры привязываем к числу ценовых узлов:
    # карточек примерно столько же, сколько цен. Это отсекает как «утилитарные»
    # классы (частота сильно больше), так и общие контейнеры-гриды (частота
    # сильно меньше — иначе climb перелетел бы к обёртке всех карточек сразу).
    n = len(price_nodes)
    lo = max(_MIN_CARDS, n // 2)
    hi = int(n * 1.5) + 5

    # для каждого ценового узла — самый внешний предок-«карточка» В ДИАПАЗОНЕ
    cards, seen = [], set()
    for pn in price_nodes:
        card = None
        node = pn
        for _ in range(10):
            node = node.parent
            if node is None or node.name in ("body", "html", "[document]"):
                break
            s = _sig(node)
            if s and lo <= freq.get(s, 0) <= hi:
                card = node  # самый внешний предок «карточной» частоты
        if card is not None and id(card) not in seen:
            seen.add(id(card))
            cards.append(card)

    products = []
    for card in cards:
        name, url = _card_name_and_url(card)
        if not name:
            continue
        for vname, price in _card_variants(card, name):
            item = _make_product(vname, price, url=url)
            if item:
                products.append(item)

    products = _dedup(products)
    return products if len(products) >= _MIN_CARDS else []


def count_price_nodes(html):
    """Сколько на странице самых внутренних «ценовых» узлов (цифры + ₽/руб).
    Диагностический сигнал: если их много, а товаров не извлекли — проблема в
    структуре/валюте, а не в отсутствии цен на странице."""
    if not html:
        return 0
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return 0
    n = 0
    for el in soup.find_all(True):
        t = el.get_text(" ", strip=True)
        if not _is_price_text(t):
            continue
        if any(_is_price_text(c.get_text(" ", strip=True)) for c in el.find_all(True, recursive=False)):
            continue
        n += 1
    return n


def tier_counts(html):
    """Диагностика: сколько товаров дал бы КАЖДЫЙ HTML-тир (без короткого
    замыкания). Используется в логах при неудаче, чтобы понять, на каком шаге
    «отвалились». Возвращает {method: count, 'price_nodes': N}."""
    counts = {}
    if not html:
        return counts
    for method, fn in EXTRACTORS:
        try:
            counts[method] = len(fn(html))
        except Exception:
            counts[method] = -1  # тир упал с ошибкой
    counts["price_nodes"] = count_price_nodes(html)
    return counts


# ---------------------------------------------------------------------------
# Тир 0: YML / price-фид (Яндекс.Маркет)
# ---------------------------------------------------------------------------

_CUR_MAP = {"RUR": "RUB", "RUB": "RUB", "USD": "USD", "EUR": "EUR", "UAH": "UAH", "KZT": "KZT", "BYN": "BYN"}


def looks_like_yml(text):
    """Похоже ли содержимое на YML-фид (а не на HTML-страницу/404)."""
    if not text:
        return False
    head = text[:4000].lower()
    return ("<yml_catalog" in head) or ("<offers" in head and "<offer" in head)


def parse_yml(text):
    """Разбирает YML-фид (Яндекс.Маркет) в список товаров.

    Имя берём из <name>, иначе из typePrefix+vendor+model; цена — <price>,
    валюта — <currencyId> (RUR→RUB), ссылка — <url>, артикул — id/<vendorCode>.
    """
    if not text:
        return []
    from lxml import etree

    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    try:
        root = etree.fromstring(text.encode("utf-8", "ignore"), parser=parser)
    except (etree.XMLSyntaxError, ValueError):
        return []
    if root is None:
        return []

    def local(tag):
        return etree.QName(tag).localname if isinstance(tag, str) else tag

    products = []
    for off in root.iter():
        if local(off.tag) != "offer":
            continue

        fields = {}
        for child in off:
            name = local(child.tag)
            if name not in fields and child.text and child.text.strip():
                fields[name] = child.text.strip()

        name = fields.get("name") or " ".join(
            x for x in (fields.get("typePrefix"), fields.get("vendor"), fields.get("model")) if x
        )
        currency = _CUR_MAP.get((fields.get("currencyId") or "").upper(), fields.get("currencyId"))
        ext = fields.get("vendorCode") or fields.get("barcode") or off.get("id")
        item = _make_product(
            name or None,
            fields.get("price"),
            currency=currency,
            url=fields.get("url"),
            external_id=ext,
        )
        if item:
            products.append(item)

    return _dedup(products)


# ---------------------------------------------------------------------------
# Тир 5: OpenGraph / meta-теги (одиночная карточка товара)
# ---------------------------------------------------------------------------


def extract_opengraph(html):
    """Название+цена из og:/product: meta-тегов (обычно на карточке товара).
    Требуется и название, и цена — иначе на странице-листинге будет ложное
    срабатывание (там есть og:title, но нет цены)."""
    soup = BeautifulSoup(html, "lxml")

    def meta(*names):
        for n in names:
            el = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if el and el.get("content") and el["content"].strip():
                return el["content"].strip()
        return None

    name = meta("og:title", "twitter:title")
    price = meta("product:price:amount", "og:price:amount", "product:amount")
    currency = meta("product:price:currency", "og:price:currency")
    url = meta("og:url")
    item = _make_product(name, price, currency=currency, url=url)
    return [item] if item else []


# ---------------------------------------------------------------------------
# Shopify /products.json (парсер; запрос делает SiteParser)
# ---------------------------------------------------------------------------


def parse_shopify_products(text):
    """Разбирает ответ Shopify /products.json в список товаров."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    items = data.get("products") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out = []
    for pr in items:
        if not isinstance(pr, dict):
            continue
        prices = [
            _to_price(v.get("price"))
            for v in (pr.get("variants") or [])
            if isinstance(v, dict)
        ]
        prices = [p for p in prices if p is not None]
        handle = pr.get("handle")
        item = _make_product(
            pr.get("title"),
            min(prices) if prices else None,
            url=(f"/products/{handle}" if handle else None),
            external_id=pr.get("id"),
        )
        if item:
            out.append(item)
    return _dedup(out)


# ---------------------------------------------------------------------------
# Общий вход
# ---------------------------------------------------------------------------

EXTRACTORS = [
    ("json-ld", extract_jsonld),
    ("microdata", extract_microdata),
    ("embedded-json", extract_embedded_json),
    ("dom", extract_dom),
    ("opengraph", extract_opengraph),
]

_EXTRACTOR_MAP = dict(EXTRACTORS)


def run_extractor(method, html):
    """Прогоняет конкретный тир по HTML (для сбора последующих страниц тем же
    способом, что сработал на первой — без перебора всех тиров)."""
    fn = _EXTRACTOR_MAP.get(method)
    if not fn or not html:
        return []
    try:
        return fn(html)
    except Exception:
        return []


# Если тир дал >= стольки товаров — считаем его уверенным листингом и дальше
# не ищем (экономим работу). Меньше — продолжаем и сравниваем охват с другими
# тирами: это спасает от «битого» JSON-LD с одним товаром на странице-листинге,
# где DOM находит десятки.
_CONFIDENT = 10


def auto_extract(html, min_products=1):
    """Пробует тиры и возвращает (products, method) с НАИБОЛЬШИМ охватом.

    Тиры идут по убыванию надёжности. Если тир дал уверенно много товаров
    (>= _CONFIDENT) — берём его сразу. Иначе прогоняем остальные и выбираем
    результат с наибольшим числом товаров; при равенстве предпочитаем более
    ранний (надёжный) тир. Если ничего не нашли — ([], None), и вызывающий код
    может перейти к ручным селекторам.
    """
    if not html:
        return [], None
    results = []  # (индекс_тира, method, products)
    for i, (method, fn) in enumerate(EXTRACTORS):
        try:
            products = fn(html)
        except Exception:
            products = []
        if len(products) >= min_products:
            results.append((i, method, products))
            if len(products) >= _CONFIDENT:
                break
    if not results:
        return [], None
    _, method, products = max(results, key=lambda r: (len(r[2]), -r[0]))
    return products, method
