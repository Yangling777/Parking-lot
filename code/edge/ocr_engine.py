import re
import base64
import numpy as np
import cv2
from typing import Optional, Tuple


CHINESE_PROVINCES = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"


class PlateOCREngine:
    def __init__(self, use_gpu=False):
        self.ocr = None
        self.use_gpu = use_gpu
        self.tencent_id = ""
        self.tencent_key = ""
        self._init_ocr()

    def _init_ocr(self):
        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(
                use_angle_cls=True, lang='ch',
                use_gpu=self.use_gpu, show_log=False,
                det_db_thresh=0.3, rec_batch_num=6
            )
            print("[OCR] PaddleOCR initialized")
        except ImportError:
            print("[OCR] PaddleOCR not installed. Run: pip install paddleocr")
            print("[OCR] Will use Tencent Cloud API as fallback")
        except Exception as e:
            print(f"[OCR] PaddleOCR init failed: {e}")

    def recognize(self, image: np.ndarray) -> Tuple[str, float]:
        if image is None or image.size == 0:
            return "", 0.0

        if self.ocr:
            plate, conf = self._recognize_paddleocr(image)
            if plate:
                return plate, conf

        plate, conf = self._recognize_tencent(image)
        if plate:
            return plate, conf

        return "", 0.0

    def _recognize_paddleocr(self, image: np.ndarray) -> Tuple[str, float]:
        try:
            result = self.ocr.ocr(image, cls=True)
            if result and result[0]:
                candidates = []
                for line in result[0]:
                    text = line[1][0]
                    conf = line[1][1]
                    clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).upper()
                    if 7 <= len(clean) <= 8:
                        if clean[0] in CHINESE_PROVINCES:
                            candidates.append((clean, conf))
                if candidates:
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    return candidates[0]
        except AttributeError:
            pass
        except Exception as e:
            print(f"[OCR-Paddle] Error: {e}")
        return "", 0.0

    def _recognize_tencent(self, image: np.ndarray) -> Tuple[str, float]:
        if not self.tencent_id or not self.tencent_key:
            return "", 0.0
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.ocr.v20181119 import ocr_client, models as tc_models

            _, buf = cv2.imencode('.jpg', image)
            img_b64 = base64.b64encode(buf).decode('utf-8')
            cred = credential.Credential(self.tencent_id, self.tencent_key)
            hp = HttpProfile(endpoint="ocr.tencentcloudapi.com")
            cp = ClientProfile(httpProfile=hp)
            client = ocr_client.OcrClient(cred, "ap-beijing", cp)
            req = tc_models.LicensePlateOCRRequest()
            req.ImageBase64 = img_b64
            resp = client.LicensePlateOCR(req)
            if resp.Number:
                clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', resp.Number).upper()
                return clean, resp.Confidence / 100.0 if resp.Confidence else 0.9
        except Exception as e:
            print(f"[OCR-Tencent] Error: {e}")
        return "", 0.0

    @staticmethod
    def validate_plate(plate: str) -> bool:
        if not plate:
            return False
        clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', plate)
        if len(clean) not in (7, 8):
            return False
        if clean[0] not in CHINESE_PROVINCES:
            return False
        if len(clean) == 8 and clean[6] not in 'DF':
            return False
        return True
