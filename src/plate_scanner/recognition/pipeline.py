"""Hybrid recognition pipeline: detect -> local OCR -> optional cloud escalation.

Escalation policy:

* confidence >= ``local_accept_confidence``      -> accept the local reading.
* ``local_min_confidence`` <= confidence < accept -> uncertain: ask the cloud
  recognizer (if enabled) and take whichever reading scores higher.
* confidence < ``local_min_confidence``           -> discard, too unreliable
  even to bother escalating.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from plate_scanner.recognition.cloud import CloudPlateRecognizer
from plate_scanner.recognition.detector import PlateDetector
from plate_scanner.recognition.ocr import LocalOcr


@dataclass
class PlateReading:
    text: str
    confidence: float
    source_label: str
    timestamp: float
    image_crop: np.ndarray
    used_cloud: bool = False


class RecognitionPipeline:
    def __init__(
        self,
        detector: PlateDetector,
        local_ocr: LocalOcr,
        local_accept_confidence: float,
        local_min_confidence: float,
        cloud: Optional[CloudPlateRecognizer] = None,
    ):
        self._detector = detector
        self._local_ocr = local_ocr
        self._local_accept_confidence = local_accept_confidence
        self._local_min_confidence = local_min_confidence
        self._cloud = cloud

    def process_frame(self, image: np.ndarray, source_label: str) -> list[PlateReading]:
        readings: list[PlateReading] = []
        for region in self._detector.detect(image):
            crop = region.crop(image)
            reading = self._recognize_crop(crop, source_label)
            if reading is not None:
                readings.append(reading)
        return readings

    def _recognize_crop(self, crop: np.ndarray, source_label: str) -> Optional[PlateReading]:
        local_result = self._local_ocr.read(crop)
        if not local_result.text or local_result.confidence < self._local_min_confidence:
            return None

        text = local_result.text
        confidence = local_result.confidence
        used_cloud = False

        if confidence < self._local_accept_confidence and self._cloud is not None:
            cloud_result = self._cloud.read(crop)
            if cloud_result is not None and cloud_result.confidence > confidence:
                text = cloud_result.text
                confidence = cloud_result.confidence
                used_cloud = True

        if not text:
            return None

        return PlateReading(
            text=text,
            confidence=confidence,
            source_label=source_label,
            timestamp=time.time(),
            image_crop=crop,
            used_cloud=used_cloud,
        )
