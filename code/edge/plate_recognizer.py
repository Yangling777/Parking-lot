import cv2
import numpy as np
import threading
import time
from typing import Optional

from edge.yolo_detector import YOLOVehicleDetector
from edge.ocr_engine import PlateOCREngine
from edge import EdgePipeline, FrameResult, EdgeNodeType


class PlateRecognizer:
    def __init__(self, pipeline: EdgePipeline,
                 yolo_model="yolov8n.pt",
                 conf_threshold=0.5,
                 use_gpu=False,
                 camera_id=0):
        self.pipeline = pipeline
        self.detector = YOLOVehicleDetector(
            model_path=yolo_model,
            conf_threshold=conf_threshold,
            device="cuda" if use_gpu else "cpu"
        )
        self.ocr = PlateOCREngine(use_gpu=use_gpu)
        self.camera_id = camera_id
        self.capture = None
        self.running = False
        self.capture_thread = None
        self.process_interval = 0.3
        self.last_process_time = 0
        self.consecutive_no_vehicle = 0
        self.vehicle_timeout = 30
        self.plate_cache = {}

    def start(self, camera_id=None):
        if camera_id is not None:
            self.camera_id = camera_id
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        self.pipeline.start()
        print(f"[Recognizer] Started on camera {self.camera_id}")

    def stop(self):
        self.running = False
        self.pipeline.stop()
        if self.capture:
            self.capture.release()
            self.capture = None

    def process_frame(self, frame: np.ndarray) -> Optional[FrameResult]:
        now = time.time()
        if now - self.last_process_time < self.process_interval:
            return None
        self.last_process_time = now

        has_vehicle, vehicle_crop = self.detector.detect(frame)
        result = FrameResult(timestamp=now)

        if has_vehicle and vehicle_crop is not None:
            result.has_vehicle = True
            self.consecutive_no_vehicle = 0
            plate, conf = self.ocr.recognize(vehicle_crop)
            if plate and self.ocr.validate_plate(plate):
                result.plate_number = plate
                result.confidence = conf
                result.is_edge_confident = conf >= 0.85
                self.plate_cache[plate] = time.time()
            _, buf = cv2.imencode('.jpg', vehicle_crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
            result.image_bytes = buf.tobytes()
        else:
            self.consecutive_no_vehicle += 1

        stabilized_plate, stabilized_conf = self.pipeline.stabilize_plate(
            result.plate_number, result.confidence
        )
        if stabilized_plate:
            result.plate_number = stabilized_plate
            result.confidence = stabilized_conf

        return result

    def _capture_loop(self):
        self.capture = cv2.VideoCapture(self.camera_id)
        if not self.capture.isOpened():
            print(f"[Recognizer] Cannot open camera {self.camera_id}")
            self.running = False
            return

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.capture.set(cv2.CAP_PROP_FPS, 15)
        print(f"[Recognizer] Camera {self.camera_id} opened at 1280x720")

        while self.running:
            ret, frame = self.capture.read()
            if not ret:
                time.sleep(0.1)
                continue

            result = self.process_frame(frame)
            if result and (result.plate_number or result.has_vehicle):
                self.pipeline.push_result(result)

            if self.consecutive_no_vehicle >= self.vehicle_timeout * 10:
                self.consecutive_no_vehicle = 0

            time.sleep(0.01)

        if self.capture:
            self.capture.release()


def create_pi5_recognizer(backend_url="http://127.0.0.1:5000",
                          yolo_model="yolov8n.pt",
                          camera_id=0,
                          use_gpu=False):
    pipeline = EdgePipeline(backend_url=backend_url, node_type=EdgeNodeType.PI5)
    recognizer = PlateRecognizer(
        pipeline=pipeline,
        yolo_model=yolo_model,
        camera_id=camera_id,
        use_gpu=use_gpu
    )
    return recognizer, pipeline
