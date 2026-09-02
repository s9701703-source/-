from plate_scanner.dedup import RecentPlateCache


def test_first_sighting_is_not_a_duplicate():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=1)
    assert cache.is_duplicate("ABC1234", now=0.0) is False


def test_same_plate_within_window_is_duplicate():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=1)
    cache.is_duplicate("ABC1234", now=0.0)
    assert cache.is_duplicate("ABC1234", now=5.0) is True


def test_noisy_ocr_reading_within_edit_distance_is_duplicate():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=1)
    cache.is_duplicate("ABC1234", now=0.0)
    # single-character OCR slip (4 misread as A)
    assert cache.is_duplicate("ABC123A", now=1.0) is True


def test_different_plate_is_not_duplicate():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=1)
    cache.is_duplicate("ABC1234", now=0.0)
    assert cache.is_duplicate("XYZ9999", now=1.0) is False


def test_same_plate_outside_window_is_not_duplicate():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=1)
    cache.is_duplicate("ABC1234", now=0.0)
    assert cache.is_duplicate("ABC1234", now=31.0) is False


def test_zero_edit_distance_requires_exact_match():
    cache = RecentPlateCache(window_seconds=30.0, max_edit_distance=0)
    cache.is_duplicate("ABC1234", now=0.0)
    assert cache.is_duplicate("ABC123A", now=1.0) is False
