import time

import numpy as np

from plate_scanner.camera.capture import CameraStream


class FakeCapture:
    def __init__(self, frames):
        self._frames = frames
        self._i = 0
        self.opened = True

    def isOpened(self):
        return self.opened

    def read(self):
        frame = self._frames[self._i % len(self._frames)]
        self._i += 1
        return True, frame

    def release(self):
        self.opened = False


def test_latest_frame_updates_from_backend():
    frames = [np.full((2, 2, 3), i, dtype=np.uint8) for i in range(3)]
    stream = CameraStream(source="0", label="left", fps=50.0, capture_backend=FakeCapture(frames))

    stream.start()
    try:
        deadline = time.time() + 2.0
        frame = None
        while time.time() < deadline:
            frame = stream.latest_frame()
            if frame is not None:
                break
            time.sleep(0.01)

        assert frame is not None
        assert frame.label == "left"
        assert frame.image.shape == (2, 2, 3)
    finally:
        stream.stop()


def test_latest_frame_none_before_first_read():
    stream = CameraStream(source="0", label="right", fps=5.0, capture_backend=FakeCapture([np.zeros((2, 2, 3), dtype=np.uint8)]))
    assert stream.latest_frame() is None


def test_latest_frame_respects_max_age():
    stream = CameraStream(source="0", label="left", fps=50.0, capture_backend=FakeCapture([np.zeros((2, 2, 3), dtype=np.uint8)]))
    stream.start()
    try:
        deadline = time.time() + 2.0
        while stream.latest_frame() is None and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.2)
        assert stream.latest_frame(max_age_seconds=0.001) is None
        assert stream.latest_frame(max_age_seconds=10.0) is not None
    finally:
        stream.stop()
