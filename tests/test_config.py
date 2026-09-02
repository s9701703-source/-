from pathlib import Path

from plate_scanner.config import load_config

EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_load_example_config():
    config = load_config(EXAMPLE_CONFIG)

    assert config.cameras.left.source == "/dev/video0"
    assert config.cameras.right.source == "/dev/video2"
    assert config.cameras.fps == 5.0

    assert config.gps.backend == "gpsd"
    assert config.gps.max_fix_age_seconds == 5.0

    assert config.recognition.local_accept_confidence == 75.0
    assert config.cloud.enabled is False
    assert config.dedup.window_seconds == 30.0
    assert config.storage.save_plate_crops is True


def test_load_config_missing_cameras_raises(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("cameras:\n  left:\n    source: /dev/video0\n    label: left\n")

    try:
        load_config(bad_config)
        assert False, "expected ValueError for missing 'right' camera"
    except ValueError:
        pass
