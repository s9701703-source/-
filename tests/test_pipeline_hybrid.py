import numpy as np

from plate_scanner.recognition.cloud import CloudOcrResult
from plate_scanner.recognition.detector import PlateRegion
from plate_scanner.recognition.ocr import OcrResult
from plate_scanner.recognition.pipeline import RecognitionPipeline

DUMMY_IMAGE = np.zeros((100, 200, 3), dtype=np.uint8)


class FakeDetector:
    def __init__(self, regions):
        self._regions = regions

    def detect(self, image):
        return self._regions


class FakeLocalOcr:
    def __init__(self, result: OcrResult):
        self._result = result

    def read(self, crop):
        return self._result


class FakeCloud:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    def read(self, crop):
        self.calls += 1
        return self._result


def test_high_confidence_local_reading_is_accepted_without_cloud():
    detector = FakeDetector([PlateRegion(x=0, y=0, w=50, h=20)])
    local_ocr = FakeLocalOcr(OcrResult(text="ABC1234", confidence=90.0))
    cloud = FakeCloud(CloudOcrResult(text="ZZZ0000", confidence=99.0))

    pipeline = RecognitionPipeline(detector, local_ocr, local_accept_confidence=75.0, local_min_confidence=35.0, cloud=cloud)
    readings = pipeline.process_frame(DUMMY_IMAGE, "left")

    assert len(readings) == 1
    assert readings[0].text == "ABC1234"
    assert readings[0].used_cloud is False
    assert cloud.calls == 0


def test_uncertain_local_reading_escalates_to_cloud_and_wins():
    detector = FakeDetector([PlateRegion(x=0, y=0, w=50, h=20)])
    local_ocr = FakeLocalOcr(OcrResult(text="ABC1Z34", confidence=50.0))
    cloud = FakeCloud(CloudOcrResult(text="ABC1234", confidence=92.0))

    pipeline = RecognitionPipeline(detector, local_ocr, local_accept_confidence=75.0, local_min_confidence=35.0, cloud=cloud)
    readings = pipeline.process_frame(DUMMY_IMAGE, "right")

    assert len(readings) == 1
    assert readings[0].text == "ABC1234"
    assert readings[0].used_cloud is True
    assert cloud.calls == 1


def test_uncertain_local_reading_kept_when_cloud_scores_lower():
    detector = FakeDetector([PlateRegion(x=0, y=0, w=50, h=20)])
    local_ocr = FakeLocalOcr(OcrResult(text="ABC1234", confidence=50.0))
    cloud = FakeCloud(CloudOcrResult(text="NOISE99", confidence=30.0))

    pipeline = RecognitionPipeline(detector, local_ocr, local_accept_confidence=75.0, local_min_confidence=35.0, cloud=cloud)
    readings = pipeline.process_frame(DUMMY_IMAGE, "left")

    assert len(readings) == 1
    assert readings[0].text == "ABC1234"
    assert readings[0].used_cloud is False


def test_low_confidence_reading_discarded_without_reaching_cloud_when_disabled():
    detector = FakeDetector([PlateRegion(x=0, y=0, w=50, h=20)])
    local_ocr = FakeLocalOcr(OcrResult(text="XXXXXXX", confidence=10.0))

    pipeline = RecognitionPipeline(detector, local_ocr, local_accept_confidence=75.0, local_min_confidence=35.0, cloud=None)
    readings = pipeline.process_frame(DUMMY_IMAGE, "left")

    assert readings == []


def test_no_detections_returns_no_readings():
    detector = FakeDetector([])
    local_ocr = FakeLocalOcr(OcrResult(text="SHOULDNOTBEUSED", confidence=99.0))

    pipeline = RecognitionPipeline(detector, local_ocr, local_accept_confidence=75.0, local_min_confidence=35.0, cloud=None)
    readings = pipeline.process_frame(DUMMY_IMAGE, "left")

    assert readings == []
