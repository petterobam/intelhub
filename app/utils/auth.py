"""Auth utilities — open-source version: auto-admin mode (no login required)"""

import functools
import jwt
import os

from flask import g

SECRET_KEY = os.environ.get('SECRET_KEY', 'intelhub-jwt-secret-key-2024-min32bytes!!')


def generate_token(user_id: str, role: str, expires_in: int = 86400) -> str:
    import time
    payload = {
        'sub': user_id,
        'role': role,
        'exp': int(time.time()) + expires_in,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])


def _get_admin_user():
    from app.models.user import User
    admin = User.query.filter_by(email='admin@intelhub.local').first()
    if not admin:
        from flask import jsonify
        return None, (jsonify({'error': {'message': 'Admin user not found'}}), 500)
    return admin, None


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        admin, err = _get_admin_user()
        if err:
            return err
        g.current_user = admin
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        admin, err = _get_admin_user()
        if err:
            return err
        g.current_user = admin
        return f(*args, **kwargs)
    return wrapper
