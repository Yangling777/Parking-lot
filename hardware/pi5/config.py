"""
Raspberry Pi 5 边缘节点配置文件
根据实际部署环境修改以下参数
"""

# ---- 网络配置 ----
# 后端 Flask 服务地址
BACKEND_URL = "http://192.168.1.100:5000"

# ---- 摄像头配置 ----
# 摄像头设备ID (Pi Camera 通常为 0, USB 摄像头可能为 1)
CAMERA_ID = 0

# 帧宽度/高度
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# ---- AI 模型配置 ----
# YOLOv8 模型路径 (支持 .pt / .onnx)
YOLO_MODEL = "yolov8n.pt"

# YOLO 检测置信度阈值
CONF_THRESHOLD = 0.5
# OCR 高置信度阈值 (>=此值直接使用边缘结果)
HIGH_CONF_THRESHOLD = 0.85

# 去抖滑动窗口大小
STABILIZATION_WINDOW = 5

# ---- GPIO 引脚配置 ----
PLATE_GPIO_CONFIG = {
    "green_led": 17,    # 通行绿灯
    "red_led": 27,      # 禁行红灯
    "relay": 22,        # 闸机继电器
}

# ---- 串口配置 (连接ESP32) ----
SERIAL_PORT = "/dev/ttyAMA0"
SERIAL_BAUD = 115200

# ---- 上报配置 ----
# 最小上报间隔 (秒)，防止频繁上传同一结果
UPLOAD_INTERVAL = 0.5

# 心跳间隔 (秒)
HEARTBEAT_INTERVAL = 10
