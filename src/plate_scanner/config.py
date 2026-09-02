"""Typed access to the YAML configuration file."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CameraConfig:
    source: str
    label: str


@dataclass
class CamerasConfig:
    left: CameraConfig
    right: CameraConfig
    fps: float = 5.0


@dataclass
class GpsConfig:
    backend: str = "gpsd"
    gpsd_host: str = "127.0.0.1"
    gpsd_port: int = 2947
    serial_port: str = "/dev/ttyUSB0"
    serial_baud: int = 9600
    max_fix_age_seconds: float = 5.0


@dataclass
class RecognitionConfig:
    cascade_path: str = "haarcascade_russian_plate_number.xml"
    min_plate_width_px: int = 60
    min_plate_height_px: int = 20
    local_accept_confidence: float = 75.0
    local_min_confidence: float = 35.0
    allowed_characters: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"


@dataclass
class CloudConfig:
    enabled: bool = False
    provider: str = "plate_recognizer"
    api_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 4.0


@dataclass
class DedupConfig:
    window_seconds: float = 30.0
    max_edit_distance: int = 1


@dataclass
class StorageConfig:
    database_path: str = "data/plate_scanner.sqlite3"
    save_plate_crops: bool = True
    crops_dir: str = "data/crops"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "data/plate_scanner.log"


@dataclass
class AppConfig:
    cameras: CamerasConfig
    gps: GpsConfig = field(default_factory=GpsConfig)
    recognition: RecognitionConfig = field(default_factory=RecognitionConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    dedup: DedupConfig = field(default_factory=DedupConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _dc(cls, data: dict[str, Any] | None):
    data = data or {}
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML config file into an AppConfig."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cameras_raw = raw.get("cameras") or {}
    if "left" not in cameras_raw or "right" not in cameras_raw:
        raise ValueError("config.cameras must define both 'left' and 'right'")

    cameras = CamerasConfig(
        left=_dc(CameraConfig, cameras_raw["left"]),
        right=_dc(CameraConfig, cameras_raw["right"]),
        fps=float(cameras_raw.get("fps", 5.0)),
    )

    return AppConfig(
        cameras=cameras,
        gps=_dc(GpsConfig, raw.get("gps")),
        recognition=_dc(RecognitionConfig, raw.get("recognition")),
        cloud=_dc(CloudConfig, raw.get("cloud")),
        dedup=_dc(DedupConfig, raw.get("dedup")),
        storage=_dc(StorageConfig, raw.get("storage")),
        logging=_dc(LoggingConfig, raw.get("logging")),
    )
