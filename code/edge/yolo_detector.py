import numpy as np
import cv2
import time
import re
from typing import Optional, Tuple


class YOLOVehicleDetector:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.5, device="cpu"):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.device = device
        self.model = None
        self.vehicle_classes = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            if self.device == "cpu":
                self.model.to("cpu")
            print(f"[YOLO] Model loaded: {self.model_path} on {self.device}")
        except ImportError:
            print("[YOLO] ultralytics not installed. Run: pip install ultralytics")
            print("[YOLO] Falling back to OpenCV DNN mode")
            self._load_onnx_fallback()

    def _load_onnx_fallback(self):
        try:
            onnx_path = self.model_path.replace('.pt', '.onnx')
            import os
            if os.path.exists(onnx_path):
                self.model = cv2.dnn.readNetFromONNX(onnx_path)
                self.model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                print(f"[YOLO-Fallback] ONNX model loaded: {onnx_path}")
            else:
                print(f"[YOLO-Fallback] ONNX model not found: {onnx_path}")
                self.model = "onnx_missing"
        except Exception as e:
            print(f"[YOLO-Fallback] Load failed: {e}")
            self.model = None

    def detect(self, image: np.ndarray) -> Tuple[bool, Optional[np.ndarray]]:
        if self.model is None or self.model == "onnx_missing":
            return False, None

        original = image.copy()
        h, w = original.shape[:2]

        if hasattr(self.model, 'predict'):
            results = self.model.predict(image, conf=self.conf_threshold, device=self.device, verbose=False)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        if cls_id in self.vehicle_classes and conf >= self.conf_threshold:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(w, x2), min(h, y2)
                            vehicle_crop = original[y1:y2, x1:x2]
                            if vehicle_crop.size > 0:
                                return True, vehicle_crop
        elif hasattr(self.model, 'forward'):
            blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640), swapRB=True, crop=False)
            self.model.setInput(blob)
            outputs = self.model.forward()
            for detection in outputs[0, 0]:
                cls_id = int(detection[1])
                conf = float(detection[2])
                if cls_id in self.vehicle_classes and conf >= self.conf_threshold:
                    x1 = int(detection[3] * w)
                    y1 = int(detection[4] * h)
                    x2 = int(detection[5] * w)
                    y2 = int(detection[6] * h)
                    vehicle_crop = original[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
                    if vehicle_crop.size > 0:
                        return True, vehicle_crop

        return False, None

    def detect_multiple(self, image: np.ndarray) -> list:
        detections = []
        if self.model is None or self.model == "onnx_missing":
            return detections

        h, w = image.shape[:2]
        if hasattr(self.model, 'predict'):
            results = self.model.predict(image, conf=self.conf_threshold, device=self.device, verbose=False)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        if cls_id in self.vehicle_classes and conf >= self.conf_threshold:
                            detections.append({
                                "class": self.vehicle_classes.get(cls_id, "unknown"),
                                "confidence": round(conf, 3),
                                "bbox": box.xyxy[0].tolist()
                            })

        return detections
