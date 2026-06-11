import os
import re
import hmac
import hashlib
import base64
import json
import time
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import math

db = SQLAlchemy()

JWT_SECRET = os.environ.get('JWT_SECRET', 'smart-parking-jwt-secret-2026')
JWT_EXPIRE_HOURS = 2
JWT_REFRESH_DAYS = 7

token_blacklist = set()


def _base64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _base64url_decode(data_str):
    padding = 4 - len(data_str) % 4
    if padding != 4:
        data_str += '=' * padding
    return base64.urlsafe_b64decode(data_str)


def create_jwt_token(user_id, username, role):
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _base64url_encode(
        json.dumps({"user_id": user_id, "username": username, "role": role,
                     "iat": now, "exp": now + JWT_EXPIRE_HOURS * 3600, "type": "access"}).encode())
    signing_input = f"{header}.{payload}"
    signature = _base64url_encode(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def create_refresh_token(user_id):
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _base64url_encode(
        json.dumps({"user_id": user_id, "iat": now, "exp": now + JWT_REFRESH_DAYS * 86400, "type": "refresh"}).encode())
    signing_input = f"{header}.{payload}"
    signature = _base64url_encode(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def decode_jwt_token(token):
    if token in token_blacklist:
        return None
    parts = token.split('.')
    if len(parts) != 3:
        return None
    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = _base64url_encode(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature_b64, expected_sig):
        return None
    payload = json.loads(_base64url_decode(payload_b64))
    if payload.get('exp', 0) < time.time():
        return None
    return payload


sim_config = {
    "is_running": True,
    "min_interval": 5,
    "max_interval": 15,
    "entry_probability": 0.5
}

# ================= 🌟 全局日志回传系统 =================
system_logs = []


def add_log(msg, log_type="info"):
    system_logs.insert(0, {
        "id": len(system_logs) + int(datetime.now().timestamp()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "msg": msg,
        "type": log_type
    })
    if len(system_logs) > 50:
        system_logs.pop()


# ================= 🌟 核心引擎：阶梯停车费算法 =================
def get_active_price_rule():
    try:
        from models import ParkingPriceRule
        rule = ParkingPriceRule.query.filter_by(is_active=True).first()
        if rule:
            return {
                'day_start': rule.day_start_hour, 'day_end': rule.day_end_hour,
                'day_rate': rule.day_rate_per_hour, 'night_rate': rule.night_rate_per_hour,
                'free_minutes': rule.free_minutes, 'day_cap': rule.day_cap,
                'night_cap': rule.night_cap, 'discount': rule.green_plate_discount
            }
    except:
        pass
    return {
        'day_start': 8, 'day_end': 20, 'day_rate': 5.0, 'night_rate': 3.0,
        'free_minutes': 30, 'day_cap': 50.0, 'night_cap': 20.0, 'discount': 0.8
    }


def calculate_parking_fee(entry_time, exit_time=None, is_green=False):
    if not entry_time:
        return 0.0
    if not exit_time:
        exit_time = datetime.now()

    rule = get_active_price_rule()
    duration = exit_time - entry_time
    total_seconds = duration.total_seconds()

    if total_seconds <= rule['free_minutes'] * 60:
        return 0.0

    day_seconds = 0
    night_seconds = 0
    current = entry_time
    while current < exit_time:
        h = current.hour
        is_day = rule['day_start'] <= h < rule['day_end']
        next_hour = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        seg_end = min(next_hour, exit_time)
        seg_duration = (seg_end - current).total_seconds()
        if is_day:
            day_seconds += seg_duration
        else:
            night_seconds += seg_duration
        current = next_hour

    day_hours = math.ceil(day_seconds / 3600.0)
    night_hours = math.ceil(night_seconds / 3600.0)

    days_count = math.ceil(total_seconds / 86400.0)
    day_fee = days_count * min(day_hours * rule['day_rate'] / max(days_count, 1), rule['day_cap'])
    night_fee = days_count * min(night_hours * rule['night_rate'] / max(days_count, 1), rule['night_cap'])

    fee = round(day_fee + night_fee, 2)

    if is_green:
        fee = round(fee * rule['discount'], 2)

    return fee


def calculate_parking_fee_simple(entry_time, exit_time=None):
    if not entry_time:
        return 0.0
    if not exit_time:
        exit_time = datetime.now()
    duration = exit_time - entry_time
    total_seconds = duration.total_seconds()
    if total_seconds <= 1800:
        return 0.0
    hours = math.ceil(total_seconds / 3600.0)
    days = int(hours // 24)
    remainder_hours = hours % 24
    fee = days * 50.0 + min(remainder_hours * 5.0, 50.0)
    return round(fee, 2)


def audit_log(user_id, username, action, target='', detail='', ip_address=''):
    try:
        from models import AuditLog
        log_entry = AuditLog(user_id=user_id, username=username, action=action,
                             target=target, detail=detail, ip_address=ip_address)
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        pass


def calculate_crc16(data):
    crc = 0xFFFF
    for byte in data if isinstance(data, bytes) else data.encode('utf-8'):
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return f"{crc:04X}"


def build_protocol_message(cmd, seq, payload=''):
    body = f"{cmd}|{seq}|{payload}"
    checksum = calculate_crc16(body)
    return f"{body}|{checksum}"


def parse_protocol_message(message):
    try:
        msg = message.strip()
        parts = msg.split('|')
        if len(parts) < 4:
            return None
        expected_crc = parts[-1]
        body = '|'.join(parts[:-1])
        if calculate_crc16(body) != expected_crc:
            return None
        return {'cmd': parts[0], 'seq': parts[1], 'payload': parts[2]}
    except Exception:
        return None


# ================= 🌟 全局挂载 AI 智能核心引擎 =================
from routes.ai_parking_engine import ParkingTopology, TrafficPredictor, CollaborativeSpotRecommender

topology_engine = ParkingTopology()
traffic_predictor = TrafficPredictor()
spot_recommender = CollaborativeSpotRecommender()