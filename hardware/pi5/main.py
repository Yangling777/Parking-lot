#!/usr/bin/env python3
"""
Raspberry Pi 5 边缘计算主程序
  - 摄像头采集图像
  - YOLOv8n 检测车辆
  - PaddleOCR 识别车牌
  - 上报结果到云端后端
  - 接收闸机/车位控制指令

硬件接线 (Pi5 GPIO):
  - LED 绿灯: GPIO17
  - LED 红灯: GPIO27
  - 闸机继电器: GPIO22
  - 串口 (与ESP32通信): /dev/ttyAMA0
"""

import os
import sys
import time
import signal
import threading
import queue
import json
import requests
import base64
import cv2
import numpy as np
import RPi.GPIO as GPIO
import serial

from config import (BACKEND_URL, CAMERA_ID, YOLO_MODEL, CONF_THRESHOLD,
                    PLATE_GPIO_CONFIG, STABILIZATION_WINDOW, SERIAL_PORT, SERIAL_BAUD)

# ---- GPIO 初始化 ----
GPIO.setmode(GPIO.BCM)
GPIO.setup(PLATE_GPIO_CONFIG["green_led"], GPIO.OUT)
GPIO.setup(PLATE_GPIO_CONFIG["red_led"], GPIO.OUT)
GPIO.setup(PLATE_GPIO_CONFIG["relay"], GPIO.OUT)
GPIO.output(PLATE_GPIO_CONFIG["green_led"], GPIO.LOW)
GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.LOW)
GPIO.output(PLATE_GPIO_CONFIG["relay"], GPIO.LOW)

running = True
result_queue = queue.Queue(maxsize=100)
plate_window = []
config = {}


def signal_handler(sig, frame):
    global running
    running = False
    GPIO.cleanup()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def gate_open():
    GPIO.output(PLATE_GPIO_CONFIG["relay"], GPIO.HIGH)
    GPIO.output(PLATE_GPIO_CONFIG["green_led"], GPIO.HIGH)
    GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.LOW)
    threading.Timer(3.0, lambda: GPIO.output(PLATE_GPIO_CONFIG["relay"], GPIO.LOW)).start()


def gate_close():
    GPIO.output(PLATE_GPIO_CONFIG["relay"], GPIO.LOW)
    GPIO.output(PLATE_GPIO_CONFIG["green_led"], GPIO.LOW)
    GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.LOW)


def led_show_red():
    GPIO.output(PLATE_GPIO_CONFIG["green_led"], GPIO.LOW)
    GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.HIGH)


def led_show_green():
    GPIO.output(PLATE_GPIO_CONFIG["green_led"], GPIO.HIGH)
    GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.LOW)


def led_blink_red(times=5, interval=0.3):
    for _ in range(times):
        GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.HIGH)
        time.sleep(interval)
        GPIO.output(PLATE_GPIO_CONFIG["red_led"], GPIO.LOW)
        time.sleep(interval)


# ---- YOLO 车辆检测 ----
def load_yolo_model():
    from ultralytics import YOLO
    model = YOLO(YOLO_MODEL)
    print(f"[YOLO] 模型加载完成: {YOLO_MODEL}")
    return model


def detect_vehicle(model, frame):
    results = model.predict(frame, conf=CONF_THRESHOLD, device="cpu", verbose=False)
    for result in results:
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                if cls_id in (2, 3, 5, 7):
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                    return True, frame[y1:y2, x1:x2], (x1, y1, x2, y2)
    return False, None, None


# ---- PaddleOCR 车牌识别 ----
def init_ocr():
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
    print("[OCR] PaddleOCR 初始化完成")
    return ocr


def recognize_plate(ocr, crop):
    import re
    CHINA_PROVINCES = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
    result = ocr.ocr(crop, cls=True)
    if result and result[0]:
        candidates = []
        for line in result[0]:
            text = line[1][0]
            conf = line[1][1]
            clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).upper()
            if 7 <= len(clean) <= 8 and clean[0] in CHINA_PROVINCES:
                candidates.append((clean, conf))
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0]
    return "", 0.0


def stabilize_plate(plate):
    plate_window.append(plate)
    if len(plate_window) > STABILIZATION_WINDOW:
        plate_window.pop(0)
    if len(plate_window) >= max(STABILIZATION_WINDOW // 2 + 1, 3):
        from collections import Counter
        counter = Counter(plate_window)
        most, count = counter.most_common(1)[0]
        threshold = max(STABILIZATION_WINDOW // 2 + 1, 3)
        if count >= threshold:
            return most
    return None


# ---- 云端上报 ----
def upload_to_backend(plate, confidence, image=None):
    payload = {
        "node_id": f"PI5_{int(time.time())}",
        "node_type": "raspberry_pi_5",
        "local_plate": plate,
        "confidence": round(confidence, 3),
        "has_vehicle": True
    }
    if image is not None:
        _, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        payload["image_base64"] = base64.b64encode(buf).decode('utf-8')

    try:
        resp = requests.post(f"{BACKEND_URL}/api/hardware/edge/upload",
                             json=payload, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return data
    except Exception as e:
        print(f"[Upload] 失败: {e}")
    return None


def pull_config():
    global config
    try:
        resp = requests.get(f"{BACKEND_URL}/api/hardware/edge/config",
                           params={"node_id": "PI5_MAIN"}, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 200:
                config.update(data.get('data', {}))
    except Exception:
        pass


def heartbeat_loop():
    while running:
        try:
            requests.post(f"{BACKEND_URL}/api/hardware/heartbeat",
                         json={"device_id": "PI5_MAIN", "device_type": "raspberry_pi_5"},
                         timeout=3)
        except Exception:
            pass
        time.sleep(10)


# ---- 主循环 ----
def main():
    print("===== Pi5 边缘节点启动 =====")
    print(f"  后端地址: {BACKEND_URL}")
    print(f"  摄像头: {CAMERA_ID}")
    print(f"  模型: {YOLO_MODEL}")

    pull_config()

    model = load_yolo_model()
    ocr = init_ocr()

    cap = cv2.VideoCapture(CAMERA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 15)

    if not cap.isOpened():
        print("[ERROR] 无法打开摄像头")
        return

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    print("[Pi5] 开始检测...")

    last_upload_time = 0
    no_vehicle_count = 0

    while running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        has_vehicle, crop, bbox = detect_vehicle(model, frame)
        if has_vehicle and crop is not None:
            no_vehicle_count = 0
            plate, conf = recognize_plate(ocr, crop)

            if plate:
                stable = stabilize_plate(plate)
                if stable and time.time() - last_upload_time > 0.5:
                    last_upload_time = time.time()
                    resp = upload_to_backend(stable, conf, frame)

                    if resp:
                        action = resp.get('action', 'none')
                        if action == 'open_in':
                            print(f"  [ENTRY] {stable} -> {resp.get('slot')}")
                            gate_open()
                        elif action == 'open_out':
                            print(f"  [EXIT]  {stable} fee={resp.get('fee')}")
                            gate_open()
        else:
            no_vehicle_count += 1
            if no_vehicle_count > 150:
                gate_close()
                no_vehicle_count = 0

        time.sleep(0.05)

    cap.release()
    GPIO.cleanup()
    print("[Pi5] 已停止")


if __name__ == '__main__':
    main()
