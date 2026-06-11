import base64
import cv2
import numpy as np
import requests

API_URL = 'http://127.0.0.1:5000/api/hardware/upload_image'


def start_camera_bridge(ser):
    print("✅ [模块加载] 摄像头抓拍与AI识别中枢已启动...")
    print("📺 实时预览已开启 (按 Q 键退出，按空格键强制抓拍)")

    is_receiving = False
    img_acc = ""

    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
            except:
                continue

            if not line:
                continue

            # 状态A：开始接收图像
            if line == "---BEGIN_IMAGE---":
                is_receiving = True
                img_acc = ""
                print("\n📥 [硬件] 咔嚓！正在接收照片数据...")
                continue

            # 状态B：图像接收完毕，开始处理
            if line == "---END_IMAGE---":
                is_receiving = False
                print("✅ [中转] 照片接收完毕，正在请求 Flask 云端识别...")
                try:
                    # 1. 图像渲染与保存
                    img_bytes = base64.b64decode(img_acc)
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is not None:
                        cv2.imshow("ESP32-S3 Live View", frame)

                        # 👇 终极调试大招：在这里把刚才拍到的照片原封不动地存到电脑上！
                        cv2.imwrite("debug_photo.jpg", frame)
                        print("📸 [本地存储] 已将本次抓拍的画面保存为 debug_photo.jpg，请去文件夹查看！")

                    else:
                        print("⚠️ [警告] 照片解码失败，可能串口丢包了")

                    # 2. 提交给后端 AI
                    res = requests.post(API_URL, json={'image_base64': img_acc}, timeout=10)

                    if res.status_code == 200:
                        data = res.json()
                        action = data.get('action')
                        plate = data.get('plate')
                        msg = data.get('msg', '无')

                        print(f"🔍 [云端反馈] 车牌: {plate} | 动作: {action} | 备注: {msg}")

                        # 3. 拦截动作并下发给屏幕
                        if action == 'open_in':
                            ser.write((f"ENTER|{plate}\n").encode('utf-8'))
                            print(f"🚦 [指令下发] 车辆入场放行: {plate}")
                        elif action == 'open_out':
                            fee = data.get('fee', '5.0')
                            ser.write((f"PAY|{fee}\n").encode('utf-8'))
                            print(f"🚦 [指令下发] 车辆出场结算: 扫码支付 ¥{fee}")
                    else:
                        print(f"❌ [云端错误] Flask 报错，状态码: {res.status_code}")

                except requests.exceptions.ConnectionError:
                    print("❌ [严重错误] 连不上 Flask！请检查 app.py 是否在运行！")
                except Exception as e:
                    print(f"❌ [代码异常] 发生未捕获的错误: {e}")
                continue

            # 状态C：正在接收 Base64 碎片
            if is_receiving:
                img_acc += line

            # 状态D：打印硬件的普通日志
            else:
                if line not in ["capture", "stream_on", "stream_off"]:  # 屏蔽回显
                    print(f"🤖 [硬件日志] {line}")

        # 键盘监听逻辑
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            ser.write(b"stream_off\n")
            break
        elif key == 32:  # 空格键
            print("\n📸 键盘按键：手动触发抓拍...")
            ser.write(b"capture\n")