import serial
import base64
import cv2
import numpy as np
import requests
import re
import hyperlpr3
from collections import Counter

# ================== 边缘节点配置 ==================
COM_PORT = 'COM6'  # 请确保 COM 口正确
BAUD_RATE = 921600
API_URL = 'http://127.0.0.1:5000/api/hardware/upload_image'
SLOT_API_URL = 'http://127.0.0.1:5000/api/hardware/update_slot'  # 🌟 真实车位上报接口

print("[边缘节点] 正在加载 HyperLPR3 预识别模型...")
catcher = hyperlpr3.LicensePlateCatcher()
print("[边缘节点] 模型加载完毕，监听数据流...")

plate_queue = []

def is_valid_chinese_plate(plate):
    if not plate: return False
    pattern = r"^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼][A-Z][A-Z0-9]{5,6}$"
    return re.match(pattern, plate) is not None

def process_img(img_acc, ser):
    global plate_queue
    try:
        valid_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        clean_data = "".join(c for c in img_acc if c in valid_chars)
        if len(clean_data) < 500: return
        missing_padding = len(clean_data) % 4
        if missing_padding: clean_data += '=' * (4 - missing_padding)

        img_bytes = base64.b64decode(clean_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is not None:
            # 图像姿态校正
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame = cv2.flip(frame, 1)

            blur_value = cv2.Laplacian(frame, cv2.CV_64F).var()
            if blur_value < 50.0:
                print(f"🚫 [防抖拦截] 图像模糊 ({blur_value:.1f})，等待下一帧。")
                return

            cv2.imshow("Plate Capture", frame)
            cv2.waitKey(1)

            results = catcher(frame)
            if not results: return

            best_result = results[0]
            local_plate = best_result[0]
            confidence = best_result[1]

            if not is_valid_chinese_plate(local_plate): return
            if confidence < 0.85: return

            plate_queue.append(local_plate)
            if len(plate_queue) > 5: plate_queue.pop(0)

            most_common_plate, count = Counter(plate_queue).most_common(1)[0]
            if count < 3: return

            print(f"🔥 [稳定触发] 最终确认车牌: {most_common_plate}")
            plate_queue = []

            _, buffer = cv2.imencode('.jpg', frame)
            corrected_base64 = base64.b64encode(buffer).decode('utf-8')

            payload = {
                'image_base64': corrected_base64,
                'local_plate': most_common_plate,
                'confidence': float(confidence)
            }

            res = requests.post(API_URL, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                action = data.get('action', 'none')
                final_plate = data.get('plate', most_common_plate)
                safe_plate_for_lcd = final_plate[1:]

                if action == 'open_in':
                    ser.write(f"ENTER|{safe_plate_for_lcd}\n".encode('utf-8'))
                elif action == 'open_out':
                    fee = data.get('fee', '0')
                    ser.write(f"PAY|{safe_plate_for_lcd}|{fee}\n".encode('utf-8'))

    except Exception as e:
        print(f"❌ 处理异常: {e}")

def main():
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.5)
        ser.set_buffer_size(rx_size=1024 * 1024)
        ser.reset_input_buffer()
        print("🔗 高速链路与防抖网关已就绪")
    except Exception as e:
        print(f"❌ 串口连接失败: {e}")
        return

    img_acc = ""
    is_receiving = False

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line: continue

                # 🌟 新增：拦截物理超声波传感器上报的车位状态
                if line.startswith("SPACE|"):
                    parts = line.split('|')
                    if len(parts) == 3:
                        space_id = int(parts[1])
                        status = parts[2] # 'OCCUPIED' 或 'EMPTY'
                        slot_number = f"A-{space_id:03d}"
                        print(f"📡 [物理传感] 真实车位 {slot_number} 状态改变: {status}")
                        try:
                            # 异步发送给 Flask 后端
                            requests.post(SLOT_API_URL, json={'slot_number': slot_number, 'status': status}, timeout=2)
                        except Exception as e:
                            print(f"❌ 物理车位状态上报失败: {e}")
                    continue

                if "---BEGIN_IMAGE---" in line:
                    is_receiving = True
                    img_acc = ""
                    continue
                elif "---END_IMAGE---" in line:
                    is_receiving = False
                    process_img(img_acc, ser)
                    continue

                if is_receiving:
                    img_acc += line

        except KeyboardInterrupt:
            break

    ser.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()