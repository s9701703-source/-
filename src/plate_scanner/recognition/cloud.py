"""Optional cloud escalation for plate readings the local OCR is unsure about.

Only invoked by the hybrid pipeline when local confidence falls in the
"uncertain" band -- most frames never leave the device. Implemented against
the Plate Recognizer (platerecognizer.com) HTTP API as a concrete default;
swap ``CloudPlateRecognizer._parse_response`` and the request body if you use
a different provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)


@dataclass
class CloudOcrResult:
    text: str
    confidence: float  # 0-100


class CloudPlateRecognizer:
    def __init__(self, api_url: str, api_key: str, timeout_seconds: float = 4.0):
        self._api_url = api_url
        self._api_key = api_key
        self._timeout = timeout_seconds

    def read(self, plate_image: np.ndarray) -> Optional[CloudOcrResult]:
        ok, buf = cv2.imencode(".jpg", plate_image)
        if not ok:
            return None
        try:
            response = requests.post(
                self._api_url,
                files={"upload": ("plate.jpg", buf.tobytes(), "image/jpeg")},
                headers={"Authorization": f"Token {self._api_key}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Cloud plate recognition request failed: %s", exc)
            return None

        return self._parse_response(response.json())

    @staticmethod
    def _parse_response(payload: dict) -> Optional[CloudOcrResult]:
        results = payload.get("results") or []
        if not results:
            return None
        best = max(results, key=lambda r: r.get("score", 0.0))
        plate = best.get("plate")
        score = best.get("score")
        if not plate or score is None:
            return None
        return CloudOcrResult(text=str(plate).upper(), confidence=float(score) * 100.0)
