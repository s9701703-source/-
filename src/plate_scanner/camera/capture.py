"""Threaded camera capture.

Each mirror camera runs its own grabber thread so a slow frame read on one
side never stalls the other, or the recognition pipeline. Only the most
recent frame is kept -- this is a live scanner, not a recorder, so we always
want the freshest frame rather than draining a backlog.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Frame:
    image: np.ndarray
    label: str
    timestamp: float


class CameraStream:
    """Continuously reads frames from one camera in a background thread."""

    def __init__(self, source: str, label: str, fps: float = 5.0, capture_backend=None):
        """``capture_backend`` is injectable for tests; defaults to cv2.VideoCapture."""
        self._source = source
        self._label = label
        self._min_interval = 1.0 / fps if fps > 0 else 0.0
        self._capture_backend = capture_backend
        self._cap = None
        self._frame: Optional[Frame] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"camera-{self._label}")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()

    def latest_frame(self, max_age_seconds: Optional[float] = None) -> Optional[Frame]:
        with self._lock:
            frame = self._frame
        if frame is None:
            return None
        if max_age_seconds is not None and (time.time() - frame.timestamp) > max_age_seconds:
            return None
        return frame

    def _open_capture(self):
        if self._capture_backend is not None:
            return self._capture_backend
        import cv2

        source = self._source
        # Numeric-looking sources (e.g. "0") mean a /dev/videoN index.
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        return cv2.VideoCapture(source)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._cap = self._open_capture()
                if not self._cap.isOpened():
                    raise IOError(f"cannot open camera source {self._source!r}")
                while not self._stop_event.is_set():
                    ok, image = self._cap.read()
                    if not ok:
                        raise IOError(f"lost signal from camera {self._label}")
                    with self._lock:
                        self._frame = Frame(image=image, label=self._label, timestamp=time.time())
                    time.sleep(self._min_interval)
            except (IOError, OSError) as exc:
                logger.warning("Camera %s error: %s; retrying in 3s", self._label, exc)
                if self._cap is not None:
                    self._cap.release()
                    self._cap = None
                time.sleep(3.0)


class DualCameraRig:
    """Convenience wrapper managing the left and right mirror cameras together."""

    def __init__(self, left: CameraStream, right: CameraStream):
        self.left = left
        self.right = right

    def start(self) -> None:
        self.left.start()
        self.right.start()

    def stop(self) -> None:
        self.left.stop()
        self.right.stop()

    def latest_frames(self, max_age_seconds: Optional[float] = None) -> list[Frame]:
        frames = [self.left.latest_frame(max_age_seconds), self.right.latest_frame(max_age_seconds)]
        return [f for f in frames if f is not None]
