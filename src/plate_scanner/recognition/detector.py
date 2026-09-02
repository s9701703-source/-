"""Locates candidate license-plate regions in a camera frame.

Uses an OpenCV Haar cascade as a fast, CPU-only first pass suitable for a
Raspberry Pi. It trades some recall for speed; the OCR + confidence stage
downstream is what actually decides whether a detection is trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PlateRegion:
    x: int
    y: int
    w: int
    h: int

    def crop(self, image: np.ndarray) -> np.ndarray:
        return image[self.y : self.y + self.h, self.x : self.x + self.w]


class PlateDetector:
    def __init__(self, cascade_path: str, min_width_px: int = 60, min_height_px: int = 20):
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise ValueError(f"could not load Haar cascade from {cascade_path!r}")
        self._min_size = (min_width_px, min_height_px)

    def detect(self, image: np.ndarray) -> list[PlateRegion]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        boxes = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=4,
            minSize=self._min_size,
        )
        return [PlateRegion(x=int(x), y=int(y), w=int(w), h=int(h)) for (x, y, w, h) in boxes]
