import re
import time
import json
import threading
import queue
import requests
from datetime import datetime
from typing import Optional, Callable
from edge.stm32_comm import Stm32Protocol, Stm32SensorParser, GateCommand, LedMode


class Esp32Bridge:
    def __init__(self, backend_url="http://127.0.0.1:5000",
                 serial_port=None, serial_baud=115200,
                 device_id=None):
        self.backend_url = backend_url.rstrip('/')
        self.serial_port = serial_port
        self.serial_baud = serial_baud
        self.device_id = device_id or f"ESP32_{int(time.time())}"
        self.serial = None
        self.running = False
        self.stm32_tx_queue = queue.Queue()
        self.backend_tx_queue = queue.Queue()
        self.read_thread = None
        self.process_thread = None
        self.send_thread = None
        self.heartbeat_thread = None
        self.retry_queue = queue.Queue()
        self.max_retries = 3

    def start(self):
        self.running = True
        if self.serial_port:
            self._open_serial()
            self.read_thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self.read_thread.start()
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        print(f"[ESP32] Bridge started (device={self.device_id})")

    def stop(self):
        self.running = False
        if self.serial:
            self.serial.close()

    def _open_serial(self):
        try:
            import serial
            self.serial = serial.Serial(self.serial_port, self.serial_baud, timeout=0.1)
            print(f"[ESP32] Serial opened: {self.serial_port} @ {self.serial_baud}")
        except ImportError:
            print("[ESP32] pyserial not installed")
        except Exception as e:
            print(f"[ESP32] Serial open failed: {e}")

    def forward_stm32_command(self, cmd_type: str, data: bytes):
        self.stm32_tx_queue.put((cmd_type, data))

    def on_sensor_data(self, callback: Callable):
        self._sensor_callback = callback

    def _sensor_callback(self, data):
        pass

    def _serial_read_loop(self):
        buf = b""
        while self.running and self.serial:
            try:
                if self.serial.in_waiting:
                    chunk = self.serial.read(self.serial.in_waiting)
                    buf += chunk
                    while Stm32Protocol.FRAME_HEADER in buf:
                        start = buf.find(Stm32Protocol.FRAME_HEADER)
                        end = buf.find(Stm32Protocol.FRAME_FOOTER, start + 2)
                        if end == -1:
                            break
                        frame = buf[start:end + 2]
                        buf = buf[end + 2:]
                        result = Stm32Protocol.unpack_frame(frame)
                        if result:
                            self._handle_stm32_frame(result[0], result[1])
                    if len(buf) > 1024:
                        buf = buf[-512:]
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[ESP32] Serial read error: {e}")
                time.sleep(1)

    def _handle_stm32_frame(self, cmd_id: int, data: bytes):
        if cmd_id == Stm32Protocol.CMD_SENSOR_REPORT:
            sensor_data = Stm32SensorParser.parse_ultrasonic(data)
            if sensor_data:
                self.backend_tx_queue.put(("sensor", sensor_data))
                if hasattr(self, '_sensor_callback'):
                    self._sensor_callback(sensor_data)

        elif cmd_id == Stm32Protocol.CMD_HEARTBEAT:
            self.backend_tx_queue.put(("stm32_heartbeat", {"device": "STM32", "time": time.time()}))

    def _process_loop(self):
        while self.running:
            try:
                msg_type, data = self.backend_tx_queue.get(timeout=0.5)
                if msg_type == "sensor":
                    self._upload_sensor_data(data)
                elif msg_type == "stm32_heartbeat":
                    self._upload_stm32_heartbeat(data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ESP32] Process error: {e}")

    def _send_loop(self):
        while self.running:
            try:
                cmd_type, data = self.stm32_tx_queue.get(timeout=0.5)
                if self.serial:
                    frame = None
                    if cmd_type == "gate":
                        frame = Stm32Protocol.pack_frame(Stm32Protocol.CMD_GATE_CONTROL, data)
                    elif cmd_type == "led":
                        frame = Stm32Protocol.pack_frame(Stm32Protocol.CMD_LED_CONTROL, data)
                    if frame:
                        self.serial.write(frame)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[ESP32] Send error: {e}")

    def _heartbeat_loop(self):
        while self.running:
            try:
                resp = requests.post(
                    f"{self.backend_url}/api/hardware/heartbeat",
                    json={"device_id": self.device_id, "device_type": "esp32_s3",
                          "location": "MainGate", "firmware_version": "v3.0"},
                    timeout=3
                )
                if resp.status_code == 200:
                    data = resp.json()
                    server_time = data.get('server_time', '')
                    if server_time and self.serial:
                        time_msg = f"TIME|{server_time}"
                        self.serial.write(time_msg.encode() + b'\n')
            except Exception:
                pass
            time.sleep(10)

    def _upload_sensor_data(self, sensor_data: dict):
        try:
            resp = requests.post(
                f"{self.backend_url}/api/hardware/stm32/sensor",
                json={"device_id": self.device_id, "sensor_data": sensor_data},
                timeout=3
            )
        except Exception as e:
            print(f"[ESP32] Upload sensor failed: {e}")
            self.retry_queue.put(("sensor", sensor_data))

    def _upload_stm32_heartbeat(self, data: dict):
        try:
            requests.post(
                f"{self.backend_url}/api/hardware/stm32/heartbeat",
                json={"device_id": self.device_id, "stm32_status": data},
                timeout=3
            )
        except Exception:
            pass

    def send_gate_command(self, gate_id: int, cmd: GateCommand, params: dict = None):
        data = Stm32SensorParser.build_gate_command(cmd, params or {"gate_id": gate_id})
        self.forward_stm32_command("gate", data)

    def send_led_command(self, slot_id: int, mode: LedMode, params: dict = None):
        data = Stm32SensorParser.build_led_command(mode, params or {"slot_id": slot_id})
        self.forward_stm32_command("led", data)
