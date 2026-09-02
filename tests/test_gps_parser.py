from plate_scanner.gps.reader import GpsFix, parse_nmea_sentence

GGA_FIX = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
GGA_NO_FIX = "$GPGGA,123519,,,,,,0,,,,,,,,,*66"
RMC_ACTIVE = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
RMC_VOID = "$GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*77"


def test_parse_gga_valid_fix():
    fix = parse_nmea_sentence(GGA_FIX)

    assert fix is not None
    assert fix.fix_quality == 1
    assert round(fix.latitude, 3) == 48.117
    assert round(fix.longitude, 3) == 11.517
    assert fix.altitude_m == 545.4


def test_parse_gga_no_fix_returns_none():
    assert parse_nmea_sentence(GGA_NO_FIX) is None


def test_parse_rmc_active_fix():
    fix = parse_nmea_sentence(RMC_ACTIVE)

    assert fix is not None
    assert fix.speed_kmh is not None
    assert fix.speed_kmh > 0


def test_parse_rmc_void_returns_none():
    assert parse_nmea_sentence(RMC_VOID) is None


def test_rmc_carries_forward_altitude_from_previous_gga():
    previous = GpsFix(latitude=1.0, longitude=2.0, altitude_m=123.4, speed_kmh=None, timestamp=0.0)
    fix = parse_nmea_sentence(RMC_ACTIVE, previous=previous)

    assert fix is not None
    assert fix.altitude_m == 123.4


def test_garbage_line_returns_none():
    assert parse_nmea_sentence("not a valid nmea sentence") is None
