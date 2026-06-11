import time
import base64
import requests
from typing import Optional
from edge import EdgeNodeType


class K210Adapter:
    def __init__(self, backend_url="http://127.0.0.1:5000",
                 serial_port=None, serial_baud=115200,
                 device_id=None):
        self.backend_url = backend_url.rstrip('/')
        self.serial_port = serial_port
        self.serial_baud = serial_baud
        self.device_id = device_id or f"K210_{int(time.time())}"
        self.node_type = EdgeNodeType.K210
        self.serial = None
        self.running = False
        self.last_heartbeat = 0
        self.config = {
            "confidence_threshold": 0.85,
            "image_quality": 80,
            "max_retries": 3,
            "retry_delay": 1.0
        }

    def start(self):
        self.running = True
        self._open_serial()
        print(f"[K210] Adapter started (device={self.device_id})")

    def stop(self):
        self.running = False
        if self.serial:
            self.serial.close()

    def _open_serial(self):
        if not self.serial_port:
            return
        try:
            import serial
            self.serial = serial.Serial(self.serial_port, self.serial_baud, timeout=1)
            print(f"[K210] Serial opened: {self.serial_port} @ {self.serial_baud}")
        except ImportError:
            print("[K210] pyserial not installed")
        except Exception as e:
            print(f"[K210] Serial open failed: {e}")

    def upload_plate_result(self, plate: str, confidence: float,
                            image_bytes: Optional[bytes] = None) -> dict:
        payload = {
            "node_id": self.device_id,
            "node_type": self.node_type.value,
            "local_plate": plate,
            "confidence": confidence,
        }
        if image_bytes:
            payload["image_base64"] = base64.b64encode(image_bytes).decode('utf-8')

        for attempt in range(self.config["max_retries"]):
            try:
                resp = requests.post(
                    f"{self.backend_url}/api/hardware/edge/upload",
                    json=payload, timeout=5
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                if attempt < self.config["max_retries"] - 1:
                    time.sleep(self.config["retry_delay"])
                else:
                    return {"code": 500, "msg": f"Upload failed: {e}"}

        return {"code": 500, "msg": "Max retries exceeded"}

    def send_heartbeat(self) -> bool:
        now = time.time()
        if now - self.last_heartbeat < 10:
            return True
        try:
            resp = requests.post(
                f"{self.backend_url}/api/hardware/heartbeat",
                json={"device_id": self.device_id, "device_type": self.node_type.value},
                timeout=3
            )
            self.last_heartbeat = now
            return resp.status_code == 200
        except Exception:
            return False

    def pull_config(self) -> dict:
        try:
            resp = requests.get(
                f"{self.backend_url}/api/hardware/edge/config",
                params={"node_id": self.device_id}, timeout=3
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    self.config.update(data.get('data', {}))
                    return self.config
        except Exception:
            pass
        return self.config

    def read_serial_frame(self) -> Optional[bytes]:
        if not self.serial:
            return None
        try:
            if self.serial.in_waiting:
                return self.serial.readline()
        except Exception:
            pass
        return None

    def write_serial_command(self, cmd: str):
        if self.serial:
            try:
                self.serial.write(f"{cmd}\n".encode())
            except Exception:
                pass

    def process_legacy_k210_frame(self, raw_frame: bytes) -> Optional[dict]:
        try:
            line = raw_frame.decode('utf-8', errors='ignore').strip()
            if line.startswith("PLATE|"):
                parts = line.split("|")
                if len(parts) >= 3:
                    return {
                        "plate": parts[1],
                        "confidence": float(parts[2]) if len(parts) > 2 else 0.0,
                        "raw": line
                    }
            elif line.startswith("PING|"):
                return {"type": "ping", "raw": line}
            elif line.startswith("ERR|"):
                return {"type": "error", "message": line}
        except Exception:
            pass
        return None
