"""Встраиваемый скрипт PriceMonitor и приём «слепка» страницы.

Идея: владелец ставит на СВОЙ сайт небольшой скрипт и открывает страницу
каталога с меткой ?pm-pick=1. Включается визуальный режим: блоки подсвечиваются
по наведению, клик по названию товара и по цене определяет селекторы, и они
уходят в PriceMonitor. Это заменяет ручной подбор CSS через инспектор браузера.

Скрипт не собирает никаких данных о посетителях: без метки в адресе он ничего
не делает и никакого интерфейса не показывает (владелец может запустить режим
и вручную — window.pmPick()).
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
  // Адрес API берём из собственного src скрипта: он гарантированно совпадает
  // с тем, откуда скрипт загрузился (включая схему). Значение с сервера —
  // запасной вариант: за прокси приложение может считать себя http, и тогда
  // запрос с https-страницы браузер заблокирует как смешанное содержимое.
  var API = (function () {
    try {
      var src = (document.currentScript && document.currentScript.src) || '';
      if (src) return src.replace(/\/embed\/pm\.js.*$/, '') + '/api/embed/snapshot';
    } catch (e) { /* ниже — запасной вариант */ }
    return '__PM_API__';
  })();
  function priceFrom(text) {
    if (!text) return null;
    var m = String(text).replace(/ /g, ' ')
      .match(/(\d[\d\s]{0,12}(?:[.,]\d{1,2})?)\s*(?:₽|руб|р\.)/i);
    if (!m) return null;
    var num = m[1].replace(/\s/g, '').replace(',', '.');
    var val = parseFloat(num);
    return isFinite(val) && val > 0 ? val : null;
  }

  // Текст элемента без лишних пробелов. Нужна при сборе примеров товаров.
  function textOf(el) {
    return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
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
        }).then(function (resp) {
          // ВАЖНО: fetch не считает ошибкой ответ 403 — статус надо проверять
          // самим, иначе «ключ не подошёл» выглядело бы как успех.
          if (resp.status === 403) {
            render('ключ не подошёл — скопируйте свежий код из PriceMonitor');
            return;
          }
          if (!resp.ok) {
            render('сервер ответил ошибкой ' + resp.status + ' — попробуйте позже');
            return;
          }
          render('готово: найдено блоков — ' + payload.blocks[0].count +
                 '. Вернитесь в PriceMonitor — выбор уже там.');
          box.style.display = 'none';
          document.removeEventListener('mousemove', onMove, true);
          document.removeEventListener('click', onClick, true);
        }).catch(function (err) {
          // Сюда попадают только сетевые сбои: заблокированный запрос,
          // отсутствие CORS, недоступный сервер.
          render('запрос не прошёл (' + (err && err.message ? err.message : 'сеть') +
                 '). Проверьте, что сайт открыт по https и адрес ' + API + ' доступен.');
        });
      } catch (e) { render('не удалось отправить: ' + e.message); }
    }

    render();
    document.addEventListener('mousemove', onMove, true);
    document.addEventListener('click', onClick, true);
  }

  window.pmPick = pick;
  // Автозапуск только по явной метке в адресе — обычные посетители ничего
  // не отправляют и никакого интерфейса не видят.
  function boot() {
    if (/[?&]pm-pick=1/.test(location.search)) setTimeout(pick, 600);
  }
  if (document.readyState === 'complete') boot();
  else window.addEventListener('load', boot);
})();
"""


@embed_bp.route('/embed/pm.js', methods=['GET'])
def serve_script():
    """Отдаёт скрипт для встраивания. Ключ передаётся параметром ?key=."""
    key = (request.args.get('key') or '').strip()
    # За обратным прокси Flask видит http, поэтому берём адрес из FRONTEND_URL,
    # а если его нет — принудительно https (сайт работает по https).
    import os
    base = (os.environ.get('FRONTEND_URL') or request.host_url).rstrip('/')
    if base.startswith('http://') and 'localhost' not in base and '127.0.0.1' not in base:
        base = 'https://' + base[len('http://'):]
    api = base + '/api/embed/snapshot'
    body = PM_JS.replace('__PM_KEY__', key).replace('__PM_API__', api)
    resp = Response(body, mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


def _cors(resp):
    """Открытый CORS для приёма слепка.

    Эндпоинт вызывается со стороннего домена (сайта пользователя) и не
    использует куки, поэтому здесь безопасно разрешить любой origin. Важно НЕ
    ставить Allow-Credentials: с ним браузер запрещает звёздочку в Allow-Origin.
    """
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Max-Age'] = '86400'
    return resp


@embed_bp.route('/api/embed/snapshot', methods=['POST', 'OPTIONS'])
def receive_snapshot():
    """Принимает слепок страницы от встроенного скрипта."""
    if request.method == 'OPTIONS':
        # предварительный запрос браузера перед POST с JSON
        return _cors(Response('', 204))

    data = request.get_json(silent=True) or {}
    key = (data.get('key') or '').strip()
    site = EmbedSite.query.filter_by(key=key).first() if key else None
    if not site:
        # Логируем префикс ключа: по нему видно, дошёл ли запрос вообще и с чем
        # именно он пришёл, при этом сам ключ в логи не попадает целиком.
        logger.warning(
            '[ВСТРАИВАНИЕ] отклонён ключ %s… с %s',
            key[:6] or '(пусто)', request.headers.get('Origin') or '-',
        )
        return _cors(jsonify({'error': 'Неизвестный ключ сайта'})), 403

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
    return _cors(jsonify({'ok': True, 'blocks': len(blocks)})), 200


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
