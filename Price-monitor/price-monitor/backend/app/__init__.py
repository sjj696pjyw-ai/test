import os

from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from app.logging_config import configure_logging
from app.models import db
from config.config import config

jwt = JWTManager()
bcrypt = Bcrypt()

def create_app(config_name='default'):
    configure_logging()
    frontend_dist = os.environ.get('FRONTEND_DIST')
    app = Flask(__name__, static_folder=frontend_dist, static_url_path='')
    app.config.from_object(config[config_name])

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    from app.routes import analysis_bp, auth_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(analysis_bp)

    with app.app_context():
        db.create_all()

    from app.scheduler import start_scheduler
    start_scheduler(app)

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
