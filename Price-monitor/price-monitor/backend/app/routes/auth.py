import os
import re
from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_identity,
    jwt_required,
)

from ..models import User, db
from ..utils.mailer import confirmation_email, reset_email, send_email

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

PASSWORD_MIN = 8


def password_error(password):
    """Возвращает текст ошибки или None, если пароль соответствует политике:
    не менее PASSWORD_MIN символов, хотя бы одна буква и хотя бы одна цифра."""
    if len(password) < PASSWORD_MIN:
        return f'Пароль должен быть не менее {PASSWORD_MIN} символов'
    if not re.search(r'[A-Za-zА-Яа-яЁё]', password):
        return 'Пароль должен содержать хотя бы одну букву'
    if not re.search(r'\d', password):
        return 'Пароль должен содержать хотя бы одну цифру'
    return None


def validate_password(password):
    return password_error(password) is None


def _frontend_base():
    """База для ссылок в письмах: FRONTEND_URL из env, иначе хост запроса."""
    base = os.environ.get('FRONTEND_URL') or request.host_url
    return base.rstrip('/')


def _make_token(user, purpose, hours):
    return create_access_token(
        identity=str(user.id),
        additional_claims={'purpose': purpose},
        expires_delta=timedelta(hours=hours),
    )


def _send_confirmation(user):
    token = _make_token(user, 'email_confirm', 24)
    link = f"{_frontend_base()}/confirm-email?token={token}"
    subject, html, text = confirmation_email(link)
    send_email(user.email, subject, html, text)


def _auth_tokens(user):
    return {
        'access_token': create_access_token(identity=str(user.id)),
        'refresh_token': create_refresh_token(identity=str(user.id)),
    }

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    pwd_err = password_error(password)
    if pwd_err:
        return jsonify({'error': pwd_err}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    user = User(email=email, email_confirmed=False)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    _send_confirmation(user)

    # Не логиним сразу: вход откроется после подтверждения почты.
    return jsonify({
        'message': 'Регистрация успешна. Проверьте почту и подтвердите адрес.',
        'email': user.email,
        'email_confirmed': False
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.email_confirmed:
        return jsonify({
            'error': 'Подтвердите email, чтобы войти. Мы отправили ссылку на вашу почту.',
            'email_unconfirmed': True,
            'email': user.email,
        }), 403

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        **_auth_tokens(user),
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)

    return jsonify({
        'access_token': access_token
    }), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({'user': user.to_dict()}), 200

@auth_bp.route('/confirm-email', methods=['POST'])
def confirm_email():
    """Подтверждение почты по токену из письма. При успехе логиним (отдаём токены)."""
    data = request.get_json() or {}
    token = data.get('token', '')
    if not token:
        return jsonify({'error': 'Token is required'}), 400

    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({'error': 'Неверная или истёкшая ссылка подтверждения'}), 400

    if decoded.get('purpose') != 'email_confirm':
        return jsonify({'error': 'Неверная ссылка подтверждения'}), 400

    user = User.query.get(decoded.get('sub'))
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    if not user.email_confirmed:
        user.email_confirmed = True
        db.session.commit()

    return jsonify({
        'message': 'Email подтверждён',
        'user': user.to_dict(),
        **_auth_tokens(user),
    }), 200


@auth_bp.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    """Повторная отправка письма подтверждения (не раскрываем, есть ли email)."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    generic = {'message': 'Если адрес ещё не подтверждён, мы отправили письмо повторно.'}
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()
    if user and not user.email_confirmed:
        _send_confirmation(user)
    return jsonify(generic), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    generic = {'message': 'Если email существует в системе, инструкции будут отправлены'}
    user = User.query.filter_by(email=email).first()
    if user:
        token = _make_token(user, 'password_reset', 1)
        link = f"{_frontend_base()}/reset-password?token={token}"
        subject, html, text = reset_email(link)
        send_email(user.email, subject, html, text)

    return jsonify(generic), 200

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    token = data.get('token', '')
    new_password = data.get('new_password', '')

    if not token or not new_password:
        return jsonify({'error': 'Token and new password are required'}), 400

    pwd_err = password_error(new_password)
    if pwd_err:
        return jsonify({'error': pwd_err}), 400

    try:
        decoded = decode_token(token)
        if decoded.get('purpose') != 'password_reset':
            return jsonify({'error': 'Invalid reset token'}), 400

        user_id = decoded.get('sub')
        user = User.query.get(user_id)

        if not user:
            return jsonify({'error': 'User not found'}), 404

        user.set_password(new_password)
        db.session.commit()

        return jsonify({'message': 'Пароль успешно изменён'}), 200
    except Exception:
        return jsonify({'error': 'Неверный или истёкший токен'}), 400
