"""Wires cameras, GPS, the recognition pipeline, dedup and storage together."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2

from plate_scanner.camera.capture import CameraStream, DualCameraRig
from plate_scanner.config import AppConfig
from plate_scanner.dedup import RecentPlateCache
from plate_scanner.gps.reader import GpsReader
from plate_scanner.recognition.cloud import CloudPlateRecognizer
from plate_scanner.recognition.detector import PlateDetector
from plate_scanner.recognition.ocr import LocalOcr
from plate_scanner.recognition.pipeline import PlateReading, RecognitionPipeline
from plate_scanner.storage.database import PlateDatabase, PlateSighting

logger = logging.getLogger(__name__)


def configure_logging(config: AppConfig) -> None:
    Path(config.logging.file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(config.logging.file)],
    )


class PlateScannerApp:
    def __init__(self, config: AppConfig):
        self._config = config

        self._rig = DualCameraRig(
            left=CameraStream(config.cameras.left.source, config.cameras.left.label, config.cameras.fps),
            right=CameraStream(config.cameras.right.source, config.cameras.right.label, config.cameras.fps),
        )

        self._gps = GpsReader(
            backend=config.gps.backend,
            gpsd_host=config.gps.gpsd_host,
            gpsd_port=config.gps.gpsd_port,
            serial_port=config.gps.serial_port,
            serial_baud=config.gps.serial_baud,
        )

        cloud = None
        if config.cloud.enabled:
            cloud = CloudPlateRecognizer(
                api_url=config.cloud.api_url,
                api_key=config.cloud.api_key,
                timeout_seconds=config.cloud.timeout_seconds,
            )

        self._pipeline = RecognitionPipeline(
            detector=PlateDetector(
                cascade_path=config.recognition.cascade_path,
                min_width_px=config.recognition.min_plate_width_px,
                min_height_px=config.recognition.min_plate_height_px,
            ),
            local_ocr=LocalOcr(allowed_characters=config.recognition.allowed_characters),
            local_accept_confidence=config.recognition.local_accept_confidence,
            local_min_confidence=config.recognition.local_min_confidence,
            cloud=cloud,
        )

        self._dedup = RecentPlateCache(
            window_seconds=config.dedup.window_seconds,
            max_edit_distance=config.dedup.max_edit_distance,
        )

        self._db = PlateDatabase(config.storage.database_path)
        if config.storage.save_plate_crops:
            Path(config.storage.crops_dir).mkdir(parents=True, exist_ok=True)

        self._stop_requested = False

    def start(self) -> None:
        self._rig.start()
        self._gps.start()

    def stop(self) -> None:
        self._stop_requested = True
        self._rig.stop()
        self._gps.stop()
        self._db.close()

    def request_stop(self) -> None:
        self._stop_requested = True

    def run_forever(self, poll_interval_seconds: float = 0.2) -> None:
        self.start()
        try:
            while not self._stop_requested:
                for frame in self._rig.latest_frames(max_age_seconds=1.0):
                    for reading in self._pipeline.process_frame(frame.image, frame.label):
                        self._handle_reading(reading)
                time.sleep(poll_interval_seconds)
        finally:
            self.stop()

    def _handle_reading(self, reading: PlateReading) -> None:
        if not reading.text:
            return
        if self._dedup.is_duplicate(reading.text):
            return

        fix = self._gps.get_fix(max_age_seconds=self._config.gps.max_fix_age_seconds)

        image_path = None
        if self._config.storage.save_plate_crops:
            image_path = self._save_crop(reading)

        sighting = PlateSighting(
            plate_text=reading.text,
            confidence=reading.confidence,
            source_label=reading.source_label,
            captured_at=reading.timestamp,
            latitude=fix.latitude if fix else None,
            longitude=fix.longitude if fix else None,
            gps_fix_quality=fix.fix_quality if fix else None,
            used_cloud=reading.used_cloud,
            image_path=image_path,
        )
        row_id = self._db.insert(sighting)
        logger.info(
            "Saved plate #%s: %s (conf=%.1f, side=%s, lat=%s, lon=%s)",
            row_id,
            reading.text,
            reading.confidence,
            reading.source_label,
            sighting.latitude,
            sighting.longitude,
        )
        if fix is None:
            logger.warning("No recent GPS fix available for plate %s", reading.text)

    def _save_crop(self, reading: PlateReading) -> Optional[str]:
        filename = f"{int(reading.timestamp * 1000)}_{reading.source_label}_{reading.text}.jpg"
        path = Path(self._config.storage.crops_dir) / filename
        if cv2.imwrite(str(path), reading.image_crop):
            return str(path)
        logger.warning("Failed to save plate crop to %s", path)
        return None
