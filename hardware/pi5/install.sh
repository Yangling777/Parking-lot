#!/bin/bash
# Raspberry Pi 5 边缘节点环境安装脚本

echo "===== Pi5 智能停车场边缘节点安装 ====="
echo ""

# 更新系统
echo "[1/6] 更新系统..."
sudo apt-get update -y && sudo apt-get upgrade -y

# 安装系统依赖
echo "[2/6] 安装系统依赖..."
sudo apt-get install -y \
    python3-pip python3-venv \
    libatlas-base-dev libopenblas-dev \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libgtk2.0-dev libcanberra-gtk-module \
    libv4l-dev \
    git cmake

# 创建虚拟环境
echo "[3/6] 创建 Python 虚拟环境..."
python3 -m venv ~/pi5_env
source ~/pi5_env/bin/activate

# 安装 Python 包
echo "[4/6] 安装 Python 依赖 (可能需要较长时间)..."
pip install --upgrade pip

# 核心包
pip install flask requests numpy opencv-python RPi.GPIO pyserial

# YOLOv8
pip install ultralytics

# PaddleOCR
pip install paddlepaddle  # CPU 版本
pip install paddleocr

# 可选: ONNX Runtime (用于模型加速)
pip install onnxruntime

# 验证安装
echo "[5/6] 验证安装..."
python3 -c "import torch; print(f'PyTorch: {torch.__version__}')"
python3 -c "from ultralytics import YOLO; print('YOLO: OK')"
python3 -c "from paddleocr import PaddleOCR; print('PaddleOCR: OK')"
python3 -c "import RPi.GPIO; print('GPIO: OK')"
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}')"

# 设置开机自启 (可选)
echo "[6/6] 设置开机自启 (可选)..."
SERVICE_FILE="/etc/systemd/system/pi5-parking.service"
if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=Pi5 Smart Parking Edge Node
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/home/$USER/pi5_env/bin/python3 $(pwd)/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable pi5-parking
    echo "  已创建 systemd 服务: pi5-parking"
    echo "  启动: sudo systemctl start pi5-parking"
    echo "  状态: sudo systemctl status pi5-parking"
fi

echo ""
echo "===== 安装完成 ====="
echo "启动命令: python3 main.py"
echo "后台运行: sudo systemctl start pi5-parking"
