"""Встраиваемый скрипт PriceMonitor и приём «слепка» страницы.

Идея: пользователь ставит на свой сайт небольшой скрипт. Скрипт сам находит на
странице повторяющиеся блоки товаров и присылает нам их описание — селектор,
сколько таких блоков, и пара примеров с названием и ценой. В интерфейсе
PriceMonitor пользователь просто выбирает нужную группу блоков, вместо того
чтобы вручную подбирать CSS-селекторы через инспектор браузера.

Скрипт не собирает никаких данных о посетителях: он срабатывает только когда
владелец сайта открывает страницу с меткой ?pm-scan=1 (или сам вызывает
window.pmScan()).
"""
import json
import logging
import secrets
from datetime import datetime

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import EmbedSite, db

logger = logging.getLogger(__name__)

embed_bp = Blueprint('embed', __name__)

# --- сам встраиваемый скрипт ------------------------------------------------
# Ищем повторяющиеся карточки: группируем элементы по «подписи» (тег + классы),
# оставляем группы, где внутри есть похожее на цену. Логика намеренно та же,
# что и у серверного авто-извлечения, — чтобы результат совпадал.
PM_JS = r"""
(function () {
  var KEY = '__PM_KEY__';
  var API = '__PM_API__';

  function priceFrom(text) {
    if (!text) return null;
    var m = String(text).replace(/ /g, ' ')
      .match(/(\d[\d\s]{0,12}(?:[.,]\d{1,2})?)\s*(?:₽|руб|р\.)/i);
    if (!m) return null;
    var num = m[1].replace(/\s/g, '').replace(',', '.');
    var val = parseFloat(num);
    return isFinite(val) && val > 0 ? val : null;
  }

  function signature(el) {
    var cls = (el.className && typeof el.className === 'string')
      ? el.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '');
  }

  function selectorFor(el) {
    var cls = (el.className && typeof el.className === 'string')
      ? el.className.trim().split(/\s+/).filter(function (c) { return c && !/\d{3,}/.test(c); })
      : [];
    if (cls.length) return '.' + cls.slice(0, 2).join('.');
    return el.tagName.toLowerCase();
  }

  function textOf(el) {
    return (el.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function scan() {
    var groups = {};
    var all = document.querySelectorAll('div,li,article,section,tr');
    for (var i = 0; i < all.length && i < 8000; i++) {
      var el = all[i];
      var txt = textOf(el);
      if (!txt || txt.length > 400) continue;
      if (priceFrom(txt) === null) continue;
      // берём самый внутренний блок, где ещё есть и цена, и ссылка/заголовок
      var link = el.querySelector('a[href]');
      var sig = signature(el.parentElement || el) + ' > ' + signature(el);
      if (!groups[sig]) groups[sig] = { items: [], el: el };
      groups[sig].items.push({ el: el, text: txt, link: link });
    }

    var out = [];
    Object.keys(groups).forEach(function (sig) {
      var g = groups[sig];
      if (g.items.length < 3) return;               // не повторяющийся блок
      var samples = [];
      for (var i = 0; i < g.items.length && samples.length < 3; i++) {
        var it = g.items[i];
        var price = priceFrom(it.text);
        var nameEl = it.el.querySelector('a[href], h1, h2, h3, h4, [class*="name"], [class*="title"]');
        var name = nameEl ? textOf(nameEl) : it.text.slice(0, 80);
        if (!name || price === null) continue;
        samples.push({
          name: name.slice(0, 120),
          price: price,
          url: it.link ? it.link.href : null
        });
      }
      if (!samples.length) return;
      var first = g.items[0].el;
      var nameEl = first.querySelector('a[href], h1, h2, h3, h4, [class*="name"], [class*="title"]');
      var priceEl = null;
      var cand = first.querySelectorAll('*');
      for (var k = 0; k < cand.length; k++) {
        if (priceFrom(textOf(cand[k])) !== null && cand[k].children.length === 0) {
          priceEl = cand[k];
          break;
        }
      }
      out.push({
        count: g.items.length,
        card_selector: selectorFor(first),
        title_selector: nameEl ? selectorFor(nameEl) : null,
        price_selector: priceEl ? selectorFor(priceEl) : null,
        samples: samples
      });
    });

    out.sort(function (a, b) { return b.count - a.count; });
    return out.slice(0, 8);
  }

  function send() {
    var payload = {
      key: KEY,
      url: location.href,
      title: document.title,
      blocks: scan()
    };
    try {
      fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(function () {
        if (window.console) console.log('[PriceMonitor] страница передана, блоков: ' + payload.blocks.length);
      });
    } catch (e) { /* тихо: скрипт не должен ломать сайт */ }
  }

  // ---------------------------------------------------------------------
  // Визуальный режим: подсветка блоков по наведению и выбор кликом.
  // Владелец сайта открывает страницу с ?pm-pick=1, наводит мышь на название
  // товара и на цену — селекторы определяются сами и уходят в PriceMonitor.
  // ---------------------------------------------------------------------
  function matchCount(sel) {
    try { return document.querySelectorAll(sel).length; } catch (e) { return 0; }
  }

  // Селектор должен ловить ВСЕ такие элементы на странице, а не один
  // конкретный: нам нужен шаблон карточки, а не путь до узла.
  function groupSelector(el) {
    var cls = (el.className && typeof el.className === 'string')
      ? el.className.trim().split(/\s+/).filter(function (c) {
          return c && !/\d{3,}/.test(c) && !/^(is-|has-|active|hover|selected|current)/.test(c);
        })
      : [];
    for (var take = Math.min(cls.length, 2); take >= 1; take--) {
      var sel = '.' + cls.slice(0, take).join('.');
      if (matchCount(sel) >= 3) return sel;
    }
    if (cls.length) return '.' + cls.slice(0, 2).join('.');
    var tag = el.tagName.toLowerCase();
    var p = el.parentElement;
    if (p && p.className && typeof p.className === 'string') {
      var pc = p.className.trim().split(/\s+/)[0];
      if (pc) return '.' + pc + ' ' + tag;
    }
    return tag;
  }

  function pick() {
    var UI_ID = 'pm-picker-ui';
    if (document.getElementById(UI_ID)) return;

    var box = document.createElement('div');
    box.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483646;' +
      'border:2px solid #2563eb;background:rgba(37,99,235,.12);border-radius:4px;display:none';
    document.body.appendChild(box);

    var panel = document.createElement('div');
    panel.id = UI_ID;
    panel.style.cssText = 'position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483647;' +
      'background:#111827;color:#fff;padding:14px 16px;border-radius:12px;' +
      'font:14px -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;' +
      'box-shadow:0 8px 30px rgba(0,0,0,.35);display:flex;gap:12px;align-items:center';
    document.body.appendChild(panel);

    var step = 0;               // 0 — название, 1 — цена
    var picked = { title_selector: null, price_selector: null };

    function render(msg) {
      var titles = ['Наведите и кликните на <b>название товара</b>',
                    'Теперь кликните на <b>цену</b>'];
      panel.innerHTML =
        '<span style="flex:1">PriceMonitor · ' + (msg || titles[step] || '') + '</span>' +
        '<button id="pm-cancel" style="pointer-events:auto;background:#374151;color:#fff;' +
        'border:0;border-radius:8px;padding:8px 12px;cursor:pointer">Отмена</button>';
      var c = document.getElementById('pm-cancel');
      if (c) c.onclick = cleanup;
    }

    function cleanup() {
      document.removeEventListener('mousemove', onMove, true);
      document.removeEventListener('click', onClick, true);
      box.remove(); panel.remove();
    }

    function onMove(e) {
      var el = e.target;
      if (!el || el === panel || panel.contains(el)) { box.style.display = 'none'; return; }
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height) { box.style.display = 'none'; return; }
      box.style.display = 'block';
      box.style.left = r.left + 'px'; box.style.top = r.top + 'px';
      box.style.width = r.width + 'px'; box.style.height = r.height + 'px';
    }

    function onClick(e) {
      var el = e.target;
      if (!el || el === panel || panel.contains(el)) return;
      e.preventDefault(); e.stopPropagation();     // не уходим по ссылке
      var sel = groupSelector(el);
      if (step === 0) {
        picked.title_selector = sel;
        step = 1; render();
      } else {
        picked.price_selector = sel;
        finish();
      }
    }

    function finish() {
      var names = document.querySelectorAll(picked.title_selector);
      var prices = document.querySelectorAll(picked.price_selector);
      var samples = [];
      for (var i = 0; i < names.length && samples.length < 3; i++) {
        var price = prices[i] ? priceFrom(textOf(prices[i])) : null;
        var link = names[i].closest ? names[i].closest('a[href]') : null;
        samples.push({
          name: textOf(names[i]).slice(0, 120),
          price: price,
          url: link ? link.href : null
        });
      }
      var payload = {
        key: KEY, url: location.href, title: document.title,
        blocks: [{
          picked: true,
          count: Math.min(names.length, prices.length),
          card_selector: picked.title_selector,
          title_selector: picked.title_selector,
          price_selector: picked.price_selector,
          samples: samples
        }]
      };
      render('отправляю…');
      try {
        fetch(API, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(function () {
          render('готово: найдено блоков — ' + payload.blocks[0].count +
                 '. Вернитесь в PriceMonitor и нажмите «Проверить».');
          box.style.display = 'none';
          document.removeEventListener('mousemove', onMove, true);
          document.removeEventListener('click', onClick, true);
        }).catch(function () { render('не удалось отправить — проверьте ключ'); });
      } catch (e) { render('не удалось отправить'); }
    }

    render();
    document.addEventListener('mousemove', onMove, true);
    document.addEventListener('click', onClick, true);
  }

  window.pmScan = send;
  window.pmPick = pick;
  // Автозапуск только по явной метке в адресе — обычные посетители ничего
  // не отправляют и никакого интерфейса не видят.
  function boot() {
    if (/[?&]pm-pick=1/.test(location.search)) setTimeout(pick, 600);
    else if (/[?&]pm-scan=1/.test(location.search)) setTimeout(send, 800);
  }
  if (document.readyState === 'complete') boot();
  else window.addEventListener('load', boot);
})();
"""


@embed_bp.route('/embed/pm.js', methods=['GET'])
def serve_script():
    """Отдаёт скрипт для встраивания. Ключ передаётся параметром ?key=."""
    key = (request.args.get('key') or '').strip()
    api = request.host_url.rstrip('/') + '/api/embed/snapshot'
    body = PM_JS.replace('__PM_KEY__', key).replace('__PM_API__', api)
    resp = Response(body, mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


@embed_bp.route('/api/embed/snapshot', methods=['POST', 'OPTIONS'])
def receive_snapshot():
    """Принимает слепок страницы от встроенного скрипта."""
    if request.method == 'OPTIONS':
        return ('', 204)

    data = request.get_json(silent=True) or {}
    key = (data.get('key') or '').strip()
    site = EmbedSite.query.filter_by(key=key).first() if key else None
    if not site:
        return jsonify({'error': 'Неизвестный ключ сайта'}), 403

    blocks = data.get('blocks') or []
    if not isinstance(blocks, list):
        blocks = []

    from urllib.parse import urlparse
    page_url = (data.get('url') or '')[:1000]
    site.domain = urlparse(page_url).netloc or site.domain
    site.last_url = page_url
    site.last_seen = datetime.utcnow()
    site.snapshot = json.dumps(blocks[:8], ensure_ascii=False)
    db.session.commit()

    logger.info(f'[ВСТРАИВАНИЕ] слепок от {site.domain}: групп блоков {len(blocks)}')
    return jsonify({'ok': True, 'blocks': len(blocks)}), 200


@embed_bp.route('/api/embed/site', methods=['GET'])
@jwt_required()
def get_site():
    """Ключ и статус подключения для текущего пользователя (создаёт при первом
    обращении). Вместе со слепком, если он уже пришёл."""
    user_id = get_jwt_identity()
    site = EmbedSite.query.filter_by(user_id=user_id).first()
    if not site:
        site = EmbedSite(user_id=user_id, key=secrets.token_urlsafe(24))
        db.session.add(site)
        db.session.commit()
    return jsonify({'site': site.to_dict(with_snapshot=True)}), 200


@embed_bp.route('/api/embed/site', methods=['DELETE'])
@jwt_required()
def reset_site():
    """Сбрасывает слепок (например, чтобы снять его заново с другой страницы)."""
    user_id = get_jwt_identity()
    site = EmbedSite.query.filter_by(user_id=user_id).first()
    if site:
        site.snapshot = None
        site.last_url = None
        db.session.commit()
    return jsonify({'ok': True}), 200
