from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    # момент дачи согласия на обработку ПДн (152-ФЗ) — подтверждение согласия
    consent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    analyses = db.relationship('Analysis', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'email_confirmed': bool(self.email_confirmed),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=True)
    analysis_type = db.Column(db.String(20), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    queries = db.Column(db.Text)
    user_site = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    competitors = db.relationship('Competitor', backref='analysis', lazy='dynamic', cascade='all, delete-orphan')
    product_links = db.relationship('ProductLink', backref='analysis', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'analysis_type': self.analysis_type,
            'region': self.region,
            'queries': self.queries.split('\n') if self.queries else [],
            'user_site': self.user_site,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'competitors_count': self.competitors.filter_by(is_user_site=False).count()
        }

class Competitor(db.Model):
    __tablename__ = 'competitors'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    competitor_type = db.Column(db.String(20))
    position = db.Column(db.Integer)
    is_user_site = db.Column(db.Boolean, default=False)
    title_selector = db.Column(db.String(255))
    price_selector = db.Column(db.String(255))
    last_price_update = db.Column(db.DateTime)
    update_status = db.Column(db.String(50), default='pending')
    update_error_message = db.Column(db.Text)
    # Кэш YML/price-фида: NULL — не проверяли, '' — фида нет, иначе URL фида.
    feed_url = db.Column(db.String(1000))

    products = db.relationship('Product', backref='competitor', lazy='dynamic', cascade='all, delete-orphan')
    catalogs = db.relationship('Catalog', backref='competitor', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'competitor_type': self.competitor_type,
            'position': self.position,
            'is_user_site': self.is_user_site,
            'title_selector': self.title_selector,
            'price_selector': self.price_selector,
            'last_price_update': self.last_price_update.isoformat() if self.last_price_update else None,
            'update_status': self.update_status,
            'update_error_message': self.update_error_message,
            'catalogs': [c.to_dict() for c in self.catalogs.all()]
        }


class Catalog(db.Model):
    """Каталог (источник товаров) в рамках одного конкурента. У конкурента может
    быть несколько каталогов — разные разделы или отдельные карточки одного сайта.
    URL и селекторы хранятся на каталоге; товары привязаны к каталогу."""
    __tablename__ = 'catalogs'

    id = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey('competitors.id'), nullable=False)
    url = db.Column(db.String(1000))
    name = db.Column(db.String(255))  # человекочитаемая метка (путь каталога)
    title_selector = db.Column(db.String(255))
    price_selector = db.Column(db.String(255))
    # Кэш YML/price-фида: NULL — не проверяли, '' — фида нет, иначе URL фида.
    feed_url = db.Column(db.String(1000))
    last_price_update = db.Column(db.DateTime)
    update_status = db.Column(db.String(50), default='pending')
    update_error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='catalog', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'competitor_id': self.competitor_id,
            'url': self.url,
            'name': self.name,
            'title_selector': self.title_selector,
            'price_selector': self.price_selector,
            'last_price_update': self.last_price_update.isoformat() if self.last_price_update else None,
            'update_status': self.update_status,
            'update_error_message': self.update_error_message,
            'products_count': self.products.count(),
        }


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey('competitors.id'), nullable=False)
    catalog_id = db.Column(db.Integer, db.ForeignKey('catalogs.id'), nullable=True)
    name = db.Column(db.String(500), nullable=False)
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='RUB')
    external_id = db.Column(db.String(255))
    url = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'currency': self.currency,
            'external_id': self.external_id,
            'url': self.url,
            'catalog_id': self.catalog_id
        }

class EmbedSite(db.Model):
    """Сайт пользователя со встроенным скриптом PriceMonitor.

    Скрипт ставится на свой сайт и присылает «слепок» — какие повторяющиеся
    блоки товаров есть на странице. По слепку пользователь выбирает нужную
    группу блоков вместо того, чтобы вручную подбирать CSS-селекторы.
    """
    __tablename__ = 'embed_sites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    domain = db.Column(db.String(255))          # домен, с которого пришёл слепок
    last_seen = db.Column(db.DateTime)          # когда скрипт последний раз отвечал
    last_url = db.Column(db.String(1000))       # страница последнего слепка
    snapshot = db.Column(db.Text)               # JSON: найденные группы блоков
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, with_snapshot=False):
        import json as _json
        data = {
            'id': self.id,
            'key': self.key,
            'domain': self.domain,
            'connected': bool(self.last_seen),
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_url': self.last_url,
        }
        if with_snapshot and self.snapshot:
            try:
                data['blocks'] = _json.loads(self.snapshot)
            except (ValueError, TypeError):
                data['blocks'] = []
        return data


class PriceHistory(db.Model):
    __tablename__ = 'price_history'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='RUB')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('price_history', cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'price': self.price,
            'currency': self.currency,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }

class ProductLink(db.Model):
    __tablename__ = 'product_links'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    user_product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    competitor_product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_product = db.relationship('Product', foreign_keys=[user_product_id])
    competitor_product = db.relationship('Product', foreign_keys=[competitor_product_id])

    def to_dict(self):
        return {
            'id': self.id,
            'user_product': self.user_product.to_dict() if self.user_product else None,
            'competitor_product': self.competitor_product.to_dict() if self.competitor_product else None,
            'price_difference': (
                (self.user_product.price - self.competitor_product.price)
                if self.user_product and self.competitor_product and self.user_product.price
                else None
            )
        }

