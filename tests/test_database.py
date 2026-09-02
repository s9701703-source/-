from plate_scanner.storage.database import PlateDatabase, PlateSighting


def test_insert_and_recent(tmp_path):
    db = PlateDatabase(str(tmp_path / "sub" / "plates.sqlite3"))
    try:
        row_id = db.insert(
            PlateSighting(
                plate_text="ABC1234",
                confidence=88.5,
                source_label="left",
                captured_at=1000.0,
                latitude=25.0330,
                longitude=121.5654,
                gps_fix_quality=1,
                used_cloud=False,
                image_path="data/crops/ABC1234.jpg",
            )
        )
        assert row_id > 0

        rows = db.recent(limit=10)
        assert len(rows) == 1
        assert rows[0].plate_text == "ABC1234"
        assert rows[0].latitude == 25.0330
        assert rows[0].longitude == 121.5654
        assert rows[0].source_label == "left"
    finally:
        db.close()


def test_recent_orders_newest_first(tmp_path):
    db = PlateDatabase(str(tmp_path / "plates.sqlite3"))
    try:
        db.insert(PlateSighting(plate_text="AAA1111", confidence=90.0, source_label="left", captured_at=100.0))
        db.insert(PlateSighting(plate_text="BBB2222", confidence=90.0, source_label="right", captured_at=200.0))

        rows = db.recent(limit=10)
        assert [r.plate_text for r in rows] == ["BBB2222", "AAA1111"]
    finally:
        db.close()


def test_nullable_gps_fields_default_none(tmp_path):
    db = PlateDatabase(str(tmp_path / "plates.sqlite3"))
    try:
        db.insert(PlateSighting(plate_text="NOFIX999", confidence=50.0, source_label="right", captured_at=1.0))
        row = db.recent(limit=1)[0]
        assert row.latitude is None
        assert row.longitude is None
    finally:
        db.close()
