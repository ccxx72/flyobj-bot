"""
Esegui con:  pytest test_api.py -v
"""
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Polyline encoding
# ---------------------------------------------------------------------------

from flight_manager import _encode_polyline, _field


def test_encode_polyline_single_point():
    # Un solo punto: (38.5, -120.2) → "`~oia@" secondo la documentazione Google
    result = _encode_polyline([(38.5, -120.2)])
    assert isinstance(result, str)
    assert len(result) > 0


def test_encode_polyline_two_points_deterministic():
    pts = [(48.8566, 2.3522), (51.5074, -0.1278)]
    assert _encode_polyline(pts) == _encode_polyline(pts)


def test_encode_polyline_empty():
    assert _encode_polyline([]) == ''


def test_encode_polyline_known_output():
    # Coppia di punti usata come esempio nella documentazione ufficiale Google
    # (38.5, -120.2) → (40.7, -120.95) → (43.252, -126.453)
    result = _encode_polyline([(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)])
    assert result == '`~oia@_p~iF~ps|U_ulLnnqC_mqNvxq`@'


# ---------------------------------------------------------------------------
# _field helper
# ---------------------------------------------------------------------------

def test_field_returns_value():
    state = ['icao', 'AZA123', 'Italy', None, None, 9.1, 45.0]
    assert _field(state, 1) == 'AZA123'
    assert _field(state, 6) == 45.0


def test_field_returns_default_on_none():
    state = [None]
    assert _field(state, 0, 'fallback') == 'fallback'


def test_field_returns_default_on_out_of_range():
    assert _field([], 5, 99) == 99


# ---------------------------------------------------------------------------
# Lookup: compagnie aeree e aeroporti
# ---------------------------------------------------------------------------

from lookup import get_airline_name, get_airport_city


def test_get_airline_name_known():
    # RYR = Ryanair (prefisso ICAO standard)
    name = get_airline_name('RYR1234')
    assert 'Ryan' in name or name != ''


def test_get_airline_name_unknown():
    assert get_airline_name('ZZZ9999') == ''


def test_get_airline_name_short_callsign():
    assert get_airline_name('AB') == ''


def test_get_airport_city_known():
    # LIRF = Roma Fiumicino
    city = get_airport_city('LIRF')
    assert city != '' and city != 'LIRF'


def test_get_airport_city_unknown():
    # Codice inesistente: ritorna il codice stesso
    assert get_airport_city('ZZZZ') == 'ZZZZ'


def test_get_airport_city_empty():
    assert get_airport_city('') == ''


# ---------------------------------------------------------------------------
# DbManager: quota API
# ---------------------------------------------------------------------------

from db_manager import DbManager


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """DbManager che usa un database temporaneo isolato."""
    db_file = str(tmp_path / 'test.sqlite3')
    monkeypatch.setattr('db_manager.DB_PATH', db_file)
    return DbManager()


def test_quota_available_initially(tmp_db):
    assert tmp_db.has_quota_available() is True


def test_quota_decrements(tmp_db):
    for _ in range(349):
        tmp_db.increase_counter()
    assert tmp_db.has_quota_available() is True
    tmp_db.increase_counter()
    assert tmp_db.has_quota_available() is False


# ---------------------------------------------------------------------------
# DbManager: stato conversazionale
# ---------------------------------------------------------------------------

def test_coords_none_initially(tmp_db):
    assert tmp_db.get_coords(999) is None


def test_save_and_get_coords(tmp_db):
    tmp_db.save_coords(1, 45.4654, 9.1866)
    coords = tmp_db.get_coords(1)
    assert coords is not None
    assert abs(coords[0] - 45.4654) < 1e-4
    assert abs(coords[1] - 9.1866) < 1e-4


def test_waiting_address_default_false(tmp_db):
    assert tmp_db.is_waiting_address(2) is False


def test_set_waiting_address(tmp_db):
    tmp_db.set_waiting_address(2, True)
    assert tmp_db.is_waiting_address(2) is True
    tmp_db.set_waiting_address(2, False)
    assert tmp_db.is_waiting_address(2) is False


def test_pending_track_default_none(tmp_db):
    assert tmp_db.get_pending_track(3) is None


def test_set_and_clear_pending_track(tmp_db):
    tmp_db.set_pending_track(3, 'maps/3_track.png')
    assert tmp_db.get_pending_track(3) == 'maps/3_track.png'
    tmp_db.set_pending_track(3, None)
    assert tmp_db.get_pending_track(3) is None


# ---------------------------------------------------------------------------
# Traduzione statica
# ---------------------------------------------------------------------------

from translations import translate


def test_translate_italian():
    assert translate('Aggiorna lista', 'it') == 'Aggiorna lista'


def test_translate_english():
    assert translate('Aggiorna lista', 'en') == 'Refresh list'


def test_translate_unknown_language_falls_back_to_english():
    result = translate('Aggiorna lista', 'xx')
    assert result == 'Refresh list'


def test_translate_unknown_string_returns_original():
    assert translate('Stringa non registrata', 'en') == 'Stringa non registrata'
