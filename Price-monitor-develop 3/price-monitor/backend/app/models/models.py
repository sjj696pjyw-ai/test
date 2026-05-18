from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
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
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=True)  # Custom name for the analysis
    analysis_type = db.Column(db.String(20), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    queries = db.Column(db.Text)
    user_site = db.Column(db.String(255))  # URL of the user's site for comparison
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
            'competitors_count': self.competitors.count()
        }


class Competitor(db.Model):
    __tablename__ = 'competitors'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analyses.id'), nullable=False)
    domain = db.Column(db.String(255), nullable=False)  # URL of the catalog page for parsing
    competitor_type = db.Column(db.String(20))
    position = db.Column(db.Integer)
    is_user_site = db.Column(db.Boolean, default=False)
    title_selector = db.Column(db.String(255))
    price_selector = db.Column(db.String(255))
    sku_selector = db.Column(db.String(255))
    last_price_update = db.Column(db.DateTime)  # Last successful price update timestamp
    update_status = db.Column(db.String(50), default='pending')  # pending, success, partial, error
    update_error_message = db.Column(db.Text)  # Error message if update failed

    products = db.relationship('Product', backref='competitor', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'domain': self.domain,
            'competitor_type': self.competitor_type,
            'position': self.position,
            'is_user_site': self.is_user_site,
            'title_selector': self.title_selector,
            'price_selector': self.price_selector,
            'sku_selector': self.sku_selector,
            'last_price_update': self.last_price_update.isoformat() if self.last_price_update else None,
            'update_status': self.update_status,
            'update_error_message': self.update_error_message
        }


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey('competitors.id'), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='RUB')
    external_id = db.Column(db.String(255))
    url = db.Column(db.String(1000))  # Product URL for matching
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'currency': self.currency,
            'external_id': self.external_id,
            'url': self.url
        }


class PriceHistory(db.Model):
    """Table to store price history for tracking price dynamics"""
    __tablename__ = 'price_history'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='RUB')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref='price_history')

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

