"""Local OCR of a cropped plate image, plus text normalization.

Normalization is kept generic (uppercase alphanumerics and dashes) rather
than hard-coded to one country's plate format, since format varies widely.
Adjust ``allowed_characters`` in config if your plates use other symbols.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pytesseract


@dataclass
class OcrResult:
    text: str
    confidence: float  # 0-100


def normalize_plate_text(raw: str, allowed_characters: str) -> str:
    upper = raw.upper()
    allowed = set(allowed_characters)
    return "".join(ch for ch in upper if ch in allowed)


class LocalOcr:
    def __init__(self, allowed_characters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"):
        self._allowed_characters = allowed_characters
        whitelist = re.sub(r"[^A-Z0-9\-]", "", allowed_characters)
        self._tesseract_config = f"--psm 7 -c tessedit_char_whitelist={whitelist}"

    def read(self, plate_image: np.ndarray) -> OcrResult:
        data = pytesseract.image_to_data(
            plate_image,
            config=self._tesseract_config,
            output_type=pytesseract.Output.DICT,
        )
        words = []
        confidences = []
        for text, conf in zip(data["text"], data["conf"]):
            text = text.strip()
            conf = float(conf)
            if text and conf >= 0:
                words.append(text)
                confidences.append(conf)

        raw_text = "".join(words)
        normalized = normalize_plate_text(raw_text, self._allowed_characters)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text=normalized, confidence=avg_confidence)
