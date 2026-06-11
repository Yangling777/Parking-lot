import time
import queue
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class EdgeNodeType(Enum):
    PI5 = "raspberry_pi_5"
    ESP32 = "esp32_s3"
    STM32 = "stm32"
    K210 = "k210"


class DetectionEvent(Enum):
    VEHICLE_ENTER = "vehicle_enter"
    VEHICLE_EXIT = "vehicle_exit"
    VEHICLE_PASSING = "vehicle_passing"


@dataclass
class FrameResult:
    timestamp: float = field(default_factory=time.time)
    has_vehicle: bool = False
    plate_number: str = ""
    confidence: float = 0.0
    plate_bbox: tuple = (0, 0, 0, 0)
    image_bytes: Optional[bytes] = None
    is_edge_confident: bool = False


@dataclass
class Stm32SensorData:
    device_id: str = ""
    slot_number: str = ""
    distance_cm: float = 0.0
    occupied: bool = False
    gate_angle: float = 0.0
    gate_state: str = "closed"
    timestamp: float = field(default_factory=time.time)


class EdgePipeline:
    def __init__(self, backend_url="http://127.0.0.1:5000", node_type=EdgeNodeType.PI5):
        self.backend_url = backend_url.rstrip('/')
        self.node_type = node_type
        self.node_id = f"{node_type.value}_{int(time.time())}"
        self.running = False
        self.result_queue = queue.Queue(maxsize=100)
        self.stabilization_window = []
        self.max_window_size = 5
        self.stabilization_threshold = 3
        self.send_thread = None
        self.heartbeat_thread = None
        self.last_heartbeat = 0
        self.config = {}

    def start(self):
        self.running = True
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def stop(self):
        self.running = False

    def push_result(self, result: FrameResult):
        if self.result_queue.full():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                pass
        self.result_queue.put(result)

    def stabilize_plate(self, plate: str, confidence: float) -> tuple:
        clean_plate = self._clean_plate(plate)
        self.stabilization_window.append(clean_plate)
        if len(self.stabilization_window) > self.max_window_size:
            self.stabilization_window.pop(0)
        if len(self.stabilization_window) >= self.stabilization_threshold:
            from collections import Counter
            counter = Counter(self.stabilization_window)
            most_common, count = counter.most_common(1)[0]
            if count >= self.stabilization_threshold:
                return most_common, confidence
        return None, 0.0

    def _clean_plate(self, plate: str) -> str:
        import re
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate).upper()

    def _send_loop(self):
        import requests
        while self.running:
            try:
                result = self.result_queue.get(timeout=0.5)
                self._upload_to_backend(result)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Pipeline] Upload error: {e}")
                time.sleep(1)

    def _upload_to_backend(self, result: FrameResult):
        import requests
        import base64
        payload = {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "local_plate": result.plate_number,
            "confidence": result.confidence,
            "has_vehicle": result.has_vehicle,
        }
        if result.image_bytes:
            payload["image_base64"] = base64.b64encode(result.image_bytes).decode('utf-8')
        try:
            resp = requests.post(f"{self.backend_url}/api/hardware/edge/upload",
                                 json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    print(f"[Pipeline] Upload OK: {data.get('action', 'none')} plate={result.plate_number}")
        except Exception as e:
            print(f"[Pipeline] Upload failed: {e}")

    def _heartbeat_loop(self):
        import requests
        while self.running:
            now = time.time()
            if now - self.last_heartbeat > 10:
                try:
                    resp = requests.post(f"{self.backend_url}/api/hardware/heartbeat",
                                         json={"device_id": self.node_id,
                                               "device_type": self.node_type.value},
                                         timeout=3)
                    self.last_heartbeat = now
                except Exception:
                    pass
            time.sleep(10)

    def pull_config(self):
        import requests
        try:
            resp = requests.get(f"{self.backend_url}/api/hardware/edge/config",
                               params={"node_id": self.node_id}, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    self.config = data.get('data', {})
                    return self.config
        except Exception:
            pass
        return {}
