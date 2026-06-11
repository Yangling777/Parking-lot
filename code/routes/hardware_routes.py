from flask import Blueprint, jsonify, request
import base64
import re
from datetime import datetime
from difflib import SequenceMatcher

from models import User, ParkingSlot, ParkingRecord, HardwareDevice
from extensions import (
    db, calculate_parking_fee_simple, add_log, audit_log,
    build_protocol_message, parse_protocol_message, calculate_crc16
)

hardware_bp = Blueprint('hardware', __name__)

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ocr.v20181119 import ocr_client, models as tc_models

TENCENT_SECRET_ID = "YOUR_TENCENT_SECRET_ID"
TENCENT_SECRET_KEY = "YOUR_TENCENT_SECRET_KEY"
TENCENT_REGION = "ap-beijing"


def is_green_plate(plate):
    if not plate:
        return False
    clean_plate = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate)
    return len(clean_plate) == 8


def recognize_license_plate_tencent(image_bytes):
    try:
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        httpProfile = HttpProfile()
        httpProfile.endpoint = "ocr.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = ocr_client.OcrClient(cred, TENCENT_REGION, clientProfile)
        req = tc_models.LicensePlateOCRRequest()
        req.ImageBase64 = base64.b64encode(image_bytes).decode('utf-8')
        resp = client.LicensePlateOCR(req)
        if resp.Number:
            return resp.Number, "识别成功"
        return None, "未能提取到车牌号文本"
    except Exception as e:
        return None, f"识别接口调用失败: {e}"


def recognize_license_plate_paddleocr(image_bytes):
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
        import numpy as np
        import cv2
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        result = ocr.ocr(img, cls=True)
        if result and result[0]:
            texts = [line[1][0] for line in result[0] if line[1][1] > 0.8]
            for text in texts:
                clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).upper()
                if 7 <= len(clean) <= 8:
                    return clean, "PaddleOCR 识别成功"
        return None, "PaddleOCR 未检测到车牌"
    except ImportError:
        return None, "PaddleOCR 未安装"
    except Exception as e:
        return None, f"PaddleOCR 异常: {e}"


def recognize_plate_with_fallback(image_bytes):
    plate, msg = recognize_license_plate_tencent(image_bytes)
    if plate:
        return plate, msg
    plate, msg = recognize_license_plate_paddleocr(image_bytes)
    if plate:
        return plate, msg
    return None, msg


def string_similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


@hardware_bp.route('/api/hardware/upload_image', methods=['POST'])
def handle_hardware_upload():
    local_plate = None
    confidence = 0.0
    image_bytes = None

    if request.is_json:
        img_base64 = request.json.get('image_base64')
        local_plate = request.json.get('local_plate')
        confidence = float(request.json.get('confidence', 0.0))
        if img_base64:
            image_bytes = base64.b64decode(img_base64)
    else:
        file = request.files.get('imageFile')
        if file:
            image_bytes = file.read()

    if not image_bytes:
        return jsonify({"code": 400, "msg": "未找到图片文件", "action": "none"})

    final_plate = None
    if local_plate and confidence >= 0.85:
        final_plate = local_plate
    else:
        final_plate, msg = recognize_plate_with_fallback(image_bytes)
        if not final_plate:
            return jsonify({"code": 400, "msg": f"云端与边缘均未检出车牌: {msg}", "action": "none"})

    standard_plate = final_plate
    best_match_user = None
    max_score = 0
    for user in User.query.all():
        if user.plate_number:
            db_plate_clean = user.plate_number.replace('·', '').strip()
            score = string_similar(db_plate_clean, final_plate.strip())
            if score > 0.70 and score > max_score:
                max_score = score
                best_match_user = user

    if best_match_user:
        standard_plate = best_match_user.plate_number

    active_record = ParkingRecord.query.filter_by(plate_number=standard_plate).filter(
        ParkingRecord.status.in_(['正在停车', '待支付'])).first()

    if active_record:
        active_record.exit_time = datetime.now()
        active_record.fee = calculate_parking_fee_simple(
            active_record.entry_time, active_record.exit_time
        )
        active_record.status = '已支付'
        slot = ParkingSlot.query.filter_by(slot_number=active_record.slot_number).first()
        if slot:
            slot.status = 0
        db.session.commit()
        add_log(f"硬件识别出场: {standard_plate} 费用 ¥{active_record.fee}", "info")
        audit_log(best_match_user.id if best_match_user else None,
                  best_match_user.username if best_match_user else '未知',
                  'HW_EXIT', standard_plate, f"费用 ¥{active_record.fee}", request.remote_addr)
        return jsonify({
            "code": 200, "plate": standard_plate, "action": "open_out",
            "msg": "允许出场", "fee": active_record.fee
        })
    else:
        free_slot = ParkingSlot.query.filter_by(status=0).first()
        if not free_slot:
            return jsonify({"code": 400, "plate": standard_plate, "action": "none", "msg": "车位已满"})
        free_slot.status = 1
        new_record = ParkingRecord(
            user_id=(best_match_user.id if best_match_user else None),
            plate_number=standard_plate, slot_number=free_slot.slot_number, status='正在停车'
        )
        db.session.add(new_record)
        db.session.commit()
        add_log(f"硬件识别入场: {standard_plate} → {free_slot.slot_number}", "info")
        audit_log(best_match_user.id if best_match_user else None,
                  best_match_user.username if best_match_user else '未知',
                  'HW_ENTRY', standard_plate, f"车位 {free_slot.slot_number}", request.remote_addr)
        return jsonify({"code": 200, "plate": standard_plate, "action": "open_in", "msg": "欢迎入场"})


@hardware_bp.route('/api/hardware/update_slot', methods=['POST'])
def update_physical_slot():
    data = request.json
    slot_number = data.get('slot_number')
    status = data.get('status')

    slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
    if not slot:
        return jsonify({"code": 404, "msg": "车位未找到"})

    if status == 'OCCUPIED' and slot.status == 0:
        slot.status = 1
        db.session.add(ParkingRecord(plate_number="未知物理车辆", slot_number=slot_number, status='正在停车'))
        db.session.commit()
        add_log(f"物理传感器占用: {slot_number}", "info")
    elif status == 'EMPTY' and slot.status == 1:
        slot.status = 0
        record = ParkingRecord.query.filter_by(slot_number=slot_number, status='正在停车').first()
        if record:
            record.exit_time = datetime.now()
            record.status = '已离场'
        db.session.commit()
        add_log(f"物理传感器释放: {slot_number}", "info")
    return jsonify({"code": 200, "msg": "真实车位状态已更新"})


@hardware_bp.route('/api/hardware/heartbeat', methods=['POST'])
def device_heartbeat():
    data = request.json or {}
    device_id = data.get('device_id', 'unknown')
    device_type = data.get('device_type', 'ESP32-S3')
    location = data.get('location', '')
    firmware = data.get('firmware_version', '')
    ip_addr = request.remote_addr

    device = HardwareDevice.query.filter_by(device_id=device_id).first()
    if not device:
        device = HardwareDevice(
            device_id=device_id, device_type=device_type,
            location=location, firmware_version=firmware,
            ip_address=ip_addr
        )
        db.session.add(device)
    device.status = 'online'
    device.last_heartbeat = datetime.now()
    device.ip_address = ip_addr
    db.session.commit()

    return jsonify({
        "code": 200,
        "msg": "心跳已接收",
        "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@hardware_bp.route('/api/hardware/devices', methods=['GET'])
def list_devices():
    devices = HardwareDevice.query.order_by(HardwareDevice.last_heartbeat.desc()).all()
    res = []
    for d in devices:
        is_online = False
        if d.last_heartbeat:
            is_online = (datetime.now() - d.last_heartbeat).total_seconds() < 30
        res.append({
            "device_id": d.device_id, "device_type": d.device_type,
            "location": d.location, "status": "online" if is_online else "offline",
            "last_heartbeat": d.last_heartbeat.strftime('%H:%M:%S') if d.last_heartbeat else '',
            "firmware_version": d.firmware_version
        })
    return jsonify({"code": 200, "data": res})


@hardware_bp.route('/api/hardware/protocol', methods=['POST'])
def handle_protocol_message():
    raw = request.data.decode('utf-8', errors='ignore') if isinstance(request.data, bytes) else request.json.get('message', '')
    if not raw:
        return jsonify({"code": 400, "msg": "空消息"})

    parsed = parse_protocol_message(raw)
    if not parsed:
        return jsonify({"code": 400, "msg": "协议校验失败"})

    cmd = parsed['cmd']
    seq = parsed['seq']
    payload = parsed['payload']

    if cmd == 'PING':
        ack = build_protocol_message('PONG', seq, 'OK')
        return jsonify({"code": 200, "msg": "PONG", "protocol_response": ack})

    elif cmd == 'ENTRY':
        add_log(f"硬件协议入场: {payload}", "info")
        ack = build_protocol_message('ACK_ENTRY', seq, 'OK')
        return jsonify({"code": 200, "msg": "ACK_ENTRY", "protocol_response": ack})

    elif cmd == 'EXIT':
        add_log(f"硬件协议出场: {payload}", "info")
        ack = build_protocol_message('ACK_EXIT', seq, payload)
        return jsonify({"code": 200, "msg": "ACK_EXIT", "protocol_response": ack})

    elif cmd == 'SLOT':
        parts = payload.split(',')
        if len(parts) >= 2:
            slot_number = parts[0]
            slot_status = parts[1]
            slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
            if slot:
                old_status = slot.status
                slot.status = 1 if slot_status == 'OCCUPIED' else 0
                db.session.commit()
                if old_status != slot.status:
                    add_log(f"协议车位更新: {slot_number} → {'占用' if slot.status == 1 else '空闲'}", "info")
        ack = build_protocol_message('ACK_SLOT', seq, 'OK')
        return jsonify({"code": 200, "msg": "ACK_SLOT", "protocol_response": ack})

    elif cmd == 'TIME':
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ack = build_protocol_message('TIME', seq, current_time)
        return jsonify({"code": 200, "msg": "TIME_SYNC", "protocol_response": ack})

    elif cmd == 'ERR':
        add_log(f"硬件错误上报: {payload}", "error")
        ack = build_protocol_message('ACK_ERR', seq, 'RECEIVED')
        return jsonify({"code": 200, "msg": "ACK_ERR", "protocol_response": ack})

    else:
        return jsonify({"code": 400, "msg": f"未知指令 {cmd}"})


@hardware_bp.route('/api/hardware/edge/upload', methods=['POST'])
def handle_edge_upload():
    data = request.json
    node_id = data.get('node_id', 'unknown')
    node_type = data.get('node_type', 'pi5')
    local_plate = data.get('local_plate', '')
    confidence = float(data.get('confidence', 0.0))
    has_vehicle = data.get('has_vehicle', False)
    img_base64 = data.get('image_base64', '')
    image_bytes = base64.b64decode(img_base64) if img_base64 else None

    if not has_vehicle:
        add_log(f"[{node_type}] {node_id} 画面无车辆", "debug")
        return jsonify({"code": 200, "msg": "no_vehicle", "action": "none"})

    final_plate = local_plate
    if not final_plate and image_bytes:
        final_plate, _ = recognize_plate_with_fallback(image_bytes)

    if not final_plate:
        return jsonify({"code": 400, "msg": "边缘与云端均未检出车牌", "action": "none"})

    if confidence < 0.85 and image_bytes:
        cloud_plate, _ = recognize_license_plate_tencent(image_bytes)
        if cloud_plate:
            final_plate = cloud_plate

    standard_plate = final_plate
    best_match_user = None
    max_score = 0
    for user in User.query.all():
        if user.plate_number:
            db_plate_clean = user.plate_number.replace('·', '').strip()
            score = string_similar(db_plate_clean, final_plate.strip())
            if score > 0.70 and score > max_score:
                max_score = score
                best_match_user = user

    if best_match_user:
        standard_plate = best_match_user.plate_number

    active_record = ParkingRecord.query.filter_by(plate_number=standard_plate).filter(
        ParkingRecord.status.in_(['正在停车', '待支付'])).first()

    if active_record:
        active_record.exit_time = datetime.now()
        active_record.fee = calculate_parking_fee_simple(
            active_record.entry_time, active_record.exit_time
        )
        active_record.status = '已支付'
        slot = ParkingSlot.query.filter_by(slot_number=active_record.slot_number).first()
        if slot:
            slot.status = 0
        db.session.commit()
        add_log(f"[{node_type}] 出场: {standard_plate} 费用 ¥{active_record.fee}", "info")
        audit_log(best_match_user.id if best_match_user else None,
                  best_match_user.username if best_match_user else '未知',
                  f'EDGE_EXIT_{node_type.upper()}', standard_plate,
                  f"费用 ¥{active_record.fee}", request.remote_addr)
        return jsonify({
            "code": 200, "plate": standard_plate, "action": "open_out",
            "msg": "允许出场", "fee": active_record.fee,
            "gate_command": "OPEN", "led_mode": "GREEN"
        })
    else:
        free_slot = ParkingSlot.query.filter_by(status=0).first()
        if not free_slot:
            return jsonify({
                "code": 400, "plate": standard_plate, "action": "none",
                "msg": "车位已满", "led_mode": "RED"
            })
        free_slot.status = 1
        new_record = ParkingRecord(
            user_id=(best_match_user.id if best_match_user else None),
            plate_number=standard_plate, slot_number=free_slot.slot_number, status='正在停车'
        )
        db.session.add(new_record)
        db.session.commit()
        add_log(f"[{node_type}] 入场: {standard_plate} → {free_slot.slot_number}", "info")
        audit_log(best_match_user.id if best_match_user else None,
                  best_match_user.username if best_match_user else '未知',
                  f'EDGE_ENTRY_{node_type.upper()}', standard_plate,
                  f"车位 {free_slot.slot_number}", request.remote_addr)
        return jsonify({
            "code": 200, "plate": standard_plate, "action": "open_in",
            "msg": "欢迎入场", "slot": free_slot.slot_number,
            "gate_command": "OPEN", "led_mode": "GREEN"
        })


@hardware_bp.route('/api/hardware/edge/config', methods=['GET'])
def edge_config():
    node_id = request.args.get('node_id', '')
    return jsonify({
        "code": 200,
        "data": {
            "confidence_threshold": 0.85,
            "stabilization_window": 5,
            "stabilization_threshold": 3,
            "upload_interval_ms": 300,
            "heartbeat_interval_s": 10,
            "max_image_quality": 80,
            "node_id": node_id,
            "backend_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    })


@hardware_bp.route('/api/hardware/stm32/sensor', methods=['POST'])
def handle_stm32_sensor():
    data = request.json
    device_id = data.get('device_id', '')
    sensor_data = data.get('sensor_data', {})

    slot_number = sensor_data.get('slot_number', '')
    occupied = sensor_data.get('occupied', False)
    distance = sensor_data.get('distance_cm', 0.0)

    if slot_number:
        slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
        if slot:
            old_status = slot.status
            if occupied and slot.status == 0:
                slot.status = 1
                db.session.add(ParkingRecord(
                    plate_number="未知物理车辆", slot_number=slot_number,
                    status='正在停车', entry_time=datetime.now()
                ))
                add_log(f"[STM32] 车位占用: {slot_number} (距离:{distance}cm)", "info")
            elif not occupied and slot.status == 1:
                slot.status = 0
                record = ParkingRecord.query.filter_by(
                    slot_number=slot_number, status='正在停车'
                ).first()
                if record:
                    record.exit_time = datetime.now()
                    record.status = '已离场'
                add_log(f"[STM32] 车位释放: {slot_number}", "info")
            if old_status != slot.status:
                db.session.commit()

    return jsonify({
        "code": 200, "msg": "传感器数据已接收",
        "gate_command": "CLOSE" if occupied else "OPEN",
        "led_mode": "RED" if occupied else "GREEN"
    })


@hardware_bp.route('/api/hardware/stm32/heartbeat', methods=['POST'])
def stm32_heartbeat():
    data = request.json or {}
    device_id = data.get('device_id', 'stm32_unknown')
    stm32_status = data.get('stm32_status', {})

    device = HardwareDevice.query.filter_by(device_id=f"STM32_{device_id}").first()
    if not device:
        device = HardwareDevice(
            device_id=f"STM32_{device_id}", device_type='stm32',
            location='ParkingArea'
        )
        db.session.add(device)
    device.status = 'online'
    device.last_heartbeat = datetime.now()
    device.ip_address = request.remote_addr
    db.session.commit()

    return jsonify({
        "code": 200, "msg": "STM32心跳已接收",
        "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@hardware_bp.route('/api/hardware/stm32/command', methods=['POST'])
def send_stm32_command():
    data = request.json
    target_device = data.get('target_device', '')
    command = data.get('command', '')
    params = data.get('params', {})

    cmd_map = {
        'gate_open': lambda: jsonify({
            "code": 200, "msg": "闸机开启指令已下发",
            "stm32_command": {"cmd": "GATE_CONTROL", "data": [1, 0x01, 90]}
        }),
        'gate_close': lambda: jsonify({
            "code": 200, "msg": "闸机关闭指令已下发",
            "stm32_command": {"cmd": "GATE_CONTROL", "data": [1, 0x00, 0]}
        }),
        'led_green': lambda: jsonify({
            "code": 200, "msg": "LED绿灯指令已下发",
            "stm32_command": {"cmd": "LED_CONTROL",
                              "data": [params.get('slot_id', 1), 0x01, 0x00, 0x00]}
        }),
        'led_red': lambda: jsonify({
            "code": 200, "msg": "LED红灯指令已下发",
            "stm32_command": {"cmd": "LED_CONTROL",
                              "data": [params.get('slot_id', 1), 0x02, 0x00, 0x00]}
        }),
        'servo_set': lambda: jsonify({
            "code": 200, "msg": "舵机角度指令已下发",
            "stm32_command": {
                "cmd": "SERVO_CONTROL",
                "data": [params.get('servo_id', 1), params.get('angle', 90)]
            }
        }),
    }

    handler = cmd_map.get(command)
    if handler:
        add_log(f"[STM32 CMD] {command} -> {target_device}", "info")
        return handler()
    return jsonify({"code": 400, "msg": f"未知指令: {command}"})


@hardware_bp.route('/api/hardware/esp32/bridge', methods=['POST'])
def esp32_bridge():
    data = request.json or {}
    bridge_type = data.get('bridge_type', '')
    payload = data.get('payload', {})

    if bridge_type == 'sensor_relay':
        return handle_stm32_sensor()

    elif bridge_type == 'command_relay':
        slot_number = payload.get('slot_number', '')
        action = payload.get('action', '')
        if action == 'entry':
            slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
            if slot and slot.status == 0:
                slot.status = 1
                db.session.add(ParkingRecord(
                    plate_number=payload.get('plate', 'ESP32_ENTRY'),
                    slot_number=slot_number, status='正在停车'
                ))
                db.session.commit()
                add_log(f"[ESP32 Relay] 入场: {slot_number}", "info")
                return jsonify({"code": 200, "msg": "入场成功"})
        elif action == 'exit':
            slot = ParkingSlot.query.filter_by(slot_number=slot_number).first()
            if slot and slot.status == 1:
                slot.status = 0
                record = ParkingRecord.query.filter_by(
                    slot_number=slot_number, status='正在停车'
                ).first()
                if record:
                    record.exit_time = datetime.now()
                    record.status = '已离场'
                db.session.commit()
                add_log(f"[ESP32 Relay] 出场: {slot_number}", "info")
                return jsonify({"code": 200, "msg": "出场成功"})
        return jsonify({"code": 400, "msg": "无效操作"})

    elif bridge_type == 'time_sync':
        return jsonify({
            "code": 200, "msg": "时间同步",
            "server_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "timestamp_ms": int(datetime.now().timestamp() * 1000)
        })

    elif bridge_type == 'status':
        return jsonify({
            "code": 200, "data": {
                "total_slots": ParkingSlot.query.count(),
                "free_slots": ParkingSlot.query.filter_by(status=0).count(),
                "occupied_slots": ParkingSlot.query.filter_by(status=1).count()
            }
        })

    return jsonify({"code": 400, "msg": f"未知桥接类型: {bridge_type}"})
