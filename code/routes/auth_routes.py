from flask import Blueprint, jsonify, request
from functools import wraps
import re

from models import User
from extensions import (
    db, create_jwt_token, create_refresh_token,
    decode_jwt_token, token_blacklist, audit_log,
    JWT_EXPIRE_HOURS, JWT_REFRESH_DAYS
)

auth_bp = Blueprint('auth', __name__)


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        else:
            token = request.args.get('token') or (request.json or {}).get('token')
        if not token:
            return jsonify({"code": 401, "msg": "缺少认证令牌"})
        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({"code": 401, "msg": "令牌无效或已过期"})
        if payload.get('type') != 'access':
            return jsonify({"code": 401, "msg": "请使用 access_token"})
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({"code": 401, "msg": "用户不存在"})
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @jwt_required
    def decorated(*args, **kwargs):
        if request.current_user.role not in ('admin', 'manager'):
            return jsonify({"code": 403, "msg": "权限不足"})
        return f(*args, **kwargs)
    return decorated


def optional_jwt(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        request.current_user = None
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        else:
            token = request.args.get('token') or (request.json or {}).get('token')
        if token:
            payload = decode_jwt_token(token)
            if payload:
                request.current_user = User.query.get(payload['user_id'])
        return f(*args, **kwargs)
    return decorated


def format_plate_str(plate_str):
    if not plate_str:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate_str).upper()
    if len(clean) >= 2:
        return clean[:2] + '·' + clean[2:]
    return clean


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone', '')
    password = data.get('password', '')
    user = User.query.filter_by(phone=phone).first()
    if not user or not user.check_password(password):
        audit_log(None, '', 'LOGIN_FAILED', phone, '密码错误', request.remote_addr)
        return jsonify({"code": 401, "msg": "账号或密码错误"})
    if user.role == 'pending_user':
        return jsonify({"code": 403, "msg": "您的注册申请正在审核中"})
    access_token = create_jwt_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id)
    audit_log(user.id, user.username, 'LOGIN', '', '登录成功', request.remote_addr)
    return jsonify({
        "code": 200,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": JWT_EXPIRE_HOURS * 3600,
            "user": {
                "id": user.id, "username": user.username,
                "phone": user.phone, "plate_number": user.plate_number,
                "role": user.role
            }
        }
    })


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    phone = data.get('phone', '')
    username = data.get('username', '')
    password = data.get('password', '')
    plate = data.get('plate', '')

    if not phone or not username or not password:
        return jsonify({"code": 400, "msg": "手机号、姓名和密码不能为空"})
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({"code": 400, "msg": "请输入有效手机号"})
    if len(password) < 6:
        return jsonify({"code": 400, "msg": "密码长度不能少于6位"})
    if User.query.filter_by(phone=phone).first():
        return jsonify({"code": 400, "msg": "手机号已被注册"})

    fmt_plate = format_plate_str(plate)
    new_user = User(username=username, phone=phone, plate_number=fmt_plate, role='pending_user')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    audit_log(new_user.id, username, 'REGISTER', phone, '新用户注册', request.remote_addr)
    return jsonify({"code": 200, "msg": "注册资料已提交，请等待管理员审批"})


@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh():
    data = request.json
    refresh_token = data.get('refresh_token', '')
    payload = decode_jwt_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({"code": 401, "msg": "refresh_token 无效或已过期"})
    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({"code": 401, "msg": "用户不存在"})
    token_blacklist.add(refresh_token)
    new_access = create_jwt_token(user.id, user.username, user.role)
    new_refresh = create_refresh_token(user.id)
    return jsonify({
        "code": 200,
        "data": {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "expires_in": JWT_EXPIRE_HOURS * 3600
        }
    })


@auth_bp.route('/api/auth/logout', methods=['POST'])
@jwt_required
def logout():
    auth_header = request.headers.get('Authorization', '')
    token = auth_header[7:] if auth_header.startswith('Bearer ') else ''
    if token:
        token_blacklist.add(token)
    user = request.current_user
    audit_log(user.id, user.username, 'LOGOUT', '', '退出登录', request.remote_addr)
    return jsonify({"code": 200, "msg": "已退出登录"})
