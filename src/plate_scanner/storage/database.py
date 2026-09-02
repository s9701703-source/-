"""SQLite storage for accepted plate sightings."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plate_sightings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    source_label TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    gps_fix_quality INTEGER,
    used_cloud INTEGER NOT NULL DEFAULT 0,
    image_path TEXT,
    captured_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plate_sightings_plate_text ON plate_sightings (plate_text);
CREATE INDEX IF NOT EXISTS idx_plate_sightings_captured_at ON plate_sightings (captured_at);
"""


@dataclass
class PlateSighting:
    plate_text: str
    confidence: float
    source_label: str
    captured_at: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_fix_quality: Optional[int] = None
    used_cloud: bool = False
    image_path: Optional[str] = None
    id: Optional[int] = None


class PlateDatabase:
    def __init__(self, database_path: str):
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(database_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def insert(self, sighting: PlateSighting) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO plate_sightings
                (plate_text, confidence, source_label, latitude, longitude,
                 gps_fix_quality, used_cloud, image_path, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sighting.plate_text,
                sighting.confidence,
                sighting.source_label,
                sighting.latitude,
                sighting.longitude,
                sighting.gps_fix_quality,
                int(sighting.used_cloud),
                sighting.image_path,
                sighting.captured_at,
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def recent(self, limit: int = 50) -> list[PlateSighting]:
        rows = self._conn.execute(
            """
            SELECT id, plate_text, confidence, source_label, latitude, longitude,
                   gps_fix_quality, used_cloud, image_path, captured_at
            FROM plate_sightings
            ORDER BY captured_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            PlateSighting(
                id=row[0],
                plate_text=row[1],
                confidence=row[2],
                source_label=row[3],
                latitude=row[4],
                longitude=row[5],
                gps_fix_quality=row[6],
                used_cloud=bool(row[7]),
                image_path=row[8],
                captured_at=row[9],
            )
            for row in rows
        ]
