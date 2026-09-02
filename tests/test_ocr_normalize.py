from plate_scanner.recognition.ocr import normalize_plate_text

ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"


def test_normalize_uppercases():
    assert normalize_plate_text("abc-1234", ALLOWED) == "ABC-1234"


def test_normalize_strips_disallowed_characters():
    assert normalize_plate_text("AB C 12#34!", ALLOWED) == "ABC1234"


def test_normalize_empty_string():
    assert normalize_plate_text("", ALLOWED) == ""


def test_normalize_respects_restricted_allowed_set():
    assert normalize_plate_text("AB-12", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") == "AB12"
