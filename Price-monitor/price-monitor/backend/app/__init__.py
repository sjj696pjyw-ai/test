import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException

from app.logging_config import configure_logging, reset_request_id, set_request_id
from app.models import db
from config.config import config

jwt = JWTManager()
bcrypt = Bcrypt()
_req_logger = logging.getLogger('request')
_app_logger = logging.getLogger('app')


def _ensure_columns():
    """Идемпотентно добавляет недостающие колонки (простая миграция для SQLite/PG).

    db.create_all() создаёт только новые таблицы, но не колонки в существующих,
    поэтому новые поля добавляем вручную через ALTER TABLE, если их ещё нет.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)

    def add_column(table, name, ddl):
        try:
            cols = {c['name'] for c in inspector.get_columns(table)}
        except Exception:
            return
        if name not in cols:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {ddl}'))
            except Exception:
                pass

    add_column('competitors', 'feed_url', 'feed_url VARCHAR(1000)')
    # существующих пользователей считаем подтверждёнными (DEFAULT 1), чтобы не
    # запереть их новым гейтом; новые регистрации ставят False явно через ORM.
    add_column('users', 'email_confirmed', 'email_confirmed BOOLEAN NOT NULL DEFAULT 1')
    add_column('users', 'consent_at', 'consent_at DATETIME')
    # Каталоги: товар теперь принадлежит каталогу. Таблицу catalogs создаёт
    # db.create_all(); здесь добавляем колонку и заполняем дефолтные каталоги.
    add_column('products', 'catalog_id', 'catalog_id INTEGER')
    _backfill_catalogs()


def _backfill_catalogs():
    """Идемпотентно: каждому конкуренту без каталогов создаём дефолтный каталог
    из его domain/селекторов и привязываем к нему все его товары (catalog_id)."""
    from .models import Catalog, Competitor, Product

    try:
        competitors = Competitor.query.all()
    except Exception:
        return

    changed = False
    for c in competitors:
        if Catalog.query.filter_by(competitor_id=c.id).first():
            continue
        catalog = Catalog(
            competitor_id=c.id,
            url=c.domain,
            name=_catalog_label(c.domain),
            title_selector=c.title_selector,
            price_selector=c.price_selector,
            feed_url=c.feed_url,
            last_price_update=c.last_price_update,
            update_status=c.update_status or 'pending',
            update_error_message=c.update_error_message,
        )
        db.session.add(catalog)
        db.session.flush()  # получить catalog.id
        Product.query.filter_by(competitor_id=c.id).update(
            {Product.catalog_id: catalog.id}, synchronize_session=False
        )
        changed = True
    if changed:
        db.session.commit()


def _catalog_label(url):
    """Короткая метка каталога из URL (последний значимый сегмент пути)."""
    from urllib.parse import urlparse
    if not url:
        return 'Каталог'
    u = url if url.startswith(('http://', 'https://')) else f'https://{url}'
    path = urlparse(u).path.strip('/')
    if not path:
        return 'Главный каталог'
    return path.split('/')[-1] or path

def create_app(config_name='default'):
    configure_logging()
    frontend_dist = os.environ.get('FRONTEND_DIST')
    app = Flask(__name__, static_folder=frontend_dist, static_url_path='')
    app.config.from_object(config[config_name])

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    from app.routes import admin_bp, analysis_bp, auth_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        _ensure_columns()

    from app.scheduler import start_scheduler
    start_scheduler(app)

    @app.before_request
    def _begin_request():
        g._req_start = time.monotonic()
        rid = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
        g._req_id = rid
        g._req_id_token = set_request_id(rid)

    @app.after_request
    def _log_request(response):
        # Логируем только API (без healthcheck), статику и health пропускаем.
        path = request.path
        if path.startswith('/api') and path != '/api/health':
            dur_ms = (time.monotonic() - getattr(g, '_req_start', time.monotonic())) * 1000
            try:
                from flask_jwt_extended import get_jwt_identity
                uid = get_jwt_identity() or '-'
            except Exception:
                uid = '-'
            _req_logger.info(
                '%s %s -> %s %.0fms user=%s ip=%s',
                request.method, path, response.status_code, dur_ms, uid,
                request.headers.get('X-Forwarded-For', request.remote_addr),
            )
        response.headers['X-Request-ID'] = getattr(g, '_req_id', '-')
        return response

    @app.teardown_request
    def _end_request(exc):
        token = getattr(g, '_req_id_token', None)
        if token is not None:
            reset_request_id(token)

    @app.errorhandler(Exception)
    def _handle_unexpected(e):
        # HTTP-ошибки (404/403/405/...) отдаём как есть; необработанные —
        # логируем с полным трейсбеком и request-id, отвечаем 500.
        if isinstance(e, HTTPException):
            return e
        _app_logger.exception('Необработанное исключение: %s', e)
        return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy', 'message': 'API is running'}), 200

    @app.route('/')
    def serve_index():
        if app.static_folder:
            return app.send_static_file('index.html')
        return jsonify({'status': 'API is running'}), 200

    @app.errorhandler(404)
    def not_found(error):
        if not request.path.startswith('/api') and app.static_folder:
            index_path = os.path.join(app.static_folder, 'index.html')
            if os.path.exists(index_path):
                return app.send_static_file('index.html')
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token is missing'}), 401

    return app
