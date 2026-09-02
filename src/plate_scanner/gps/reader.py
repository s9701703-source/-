"""Background GPS reader.

Supports two backends:

* ``gpsd`` -- talks to a local gpsd daemon (the common setup on Raspberry Pi
  with a USB GPS dongle: ``sudo apt install gpsd gpsd-clients``).
* ``serial`` -- reads raw NMEA 0183 sentences directly off a serial port.

Both backends run in a daemon thread and expose the latest fix through
``GpsReader.get_fix()`` so the recognition pipeline never blocks waiting for
a GPS sample.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

import pynmea2

logger = logging.getLogger(__name__)


@dataclass
class GpsFix:
    latitude: float
    longitude: float
    altitude_m: Optional[float]
    speed_kmh: Optional[float]
    timestamp: float  # time.time() when the fix was captured
    fix_quality: Optional[int] = None


def parse_nmea_sentence(line: str, previous: Optional[GpsFix] = None) -> Optional[GpsFix]:
    """Parse a single NMEA sentence (GGA or RMC) into a GpsFix.

    Returns ``None`` if the sentence doesn't carry a usable fix. GGA gives
    position + altitude + fix quality; RMC gives position + speed. Since a
    receiver interleaves both, ``previous`` lets us carry forward fields the
    current sentence type doesn't provide.
    """
    try:
        msg = pynmea2.parse(line)
    except pynmea2.ParseError:
        return None

    now = time.time()

    if isinstance(msg, pynmea2.types.talker.GGA):
        if msg.gps_qual is None or int(msg.gps_qual) == 0:
            return None
        if msg.latitude == 0 and msg.longitude == 0:
            return None
        return GpsFix(
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude_m=float(msg.altitude) if msg.altitude not in (None, "") else None,
            speed_kmh=previous.speed_kmh if previous else None,
            timestamp=now,
            fix_quality=int(msg.gps_qual),
        )

    if isinstance(msg, pynmea2.types.talker.RMC):
        if msg.status != "A":  # 'A' = active/valid, 'V' = void
            return None
        if msg.latitude == 0 and msg.longitude == 0:
            return None
        speed_kmh = float(msg.spd_over_grnd) * 1.852 if msg.spd_over_grnd not in (None, "") else None
        return GpsFix(
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude_m=previous.altitude_m if previous else None,
            speed_kmh=speed_kmh,
            timestamp=now,
            fix_quality=previous.fix_quality if previous else None,
        )

    return None


class GpsReader:
    """Runs a background thread that keeps the most recent GpsFix available."""

    def __init__(self, backend: str = "gpsd", **backend_kwargs):
        self._backend = backend
        self._backend_kwargs = backend_kwargs
        self._fix: Optional[GpsFix] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        target = self._run_gpsd if self._backend == "gpsd" else self._run_serial
        self._thread = threading.Thread(target=target, daemon=True, name="gps-reader")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_fix(self, max_age_seconds: Optional[float] = None) -> Optional[GpsFix]:
        with self._lock:
            fix = self._fix
        if fix is None:
            return None
        if max_age_seconds is not None and (time.time() - fix.timestamp) > max_age_seconds:
            return None
        return fix

    def _set_fix(self, fix: GpsFix) -> None:
        with self._lock:
            self._fix = fix

    def _run_serial(self) -> None:
        import serial  # local import: optional dependency for this backend only

        port = self._backend_kwargs.get("serial_port", "/dev/ttyUSB0")
        baud = self._backend_kwargs.get("serial_baud", 9600)
        while not self._stop_event.is_set():
            try:
                with serial.Serial(port, baud, timeout=1.0) as ser:
                    while not self._stop_event.is_set():
                        raw = ser.readline().decode("ascii", errors="ignore").strip()
                        if not raw:
                            continue
                        fix = parse_nmea_sentence(raw, previous=self._fix)
                        if fix is not None:
                            self._set_fix(fix)
            except (OSError, IOError) as exc:
                logger.warning("GPS serial port error on %s: %s; retrying in 3s", port, exc)
                time.sleep(3.0)

    def _run_gpsd(self) -> None:
        import gpsd  # local import: optional dependency for this backend only

        host = self._backend_kwargs.get("gpsd_host", "127.0.0.1")
        port = self._backend_kwargs.get("gpsd_port", 2947)
        while not self._stop_event.is_set():
            try:
                gpsd.connect(host=host, port=port)
                while not self._stop_event.is_set():
                    packet = gpsd.get_current()
                    if packet.mode >= 2:  # 2D or 3D fix
                        self._set_fix(
                            GpsFix(
                                latitude=packet.lat,
                                longitude=packet.lon,
                                altitude_m=getattr(packet, "alt", None),
                                speed_kmh=(packet.hspeed * 3.6) if getattr(packet, "hspeed", None) else None,
                                timestamp=time.time(),
                                fix_quality=packet.mode,
                            )
                        )
                    time.sleep(0.5)
            except Exception as exc:  # gpsd client raises plain Exception on connect failure
                logger.warning("gpsd connection error: %s; retrying in 3s", exc)
                time.sleep(3.0)
