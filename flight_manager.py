import glob
import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image

import pickle
from config import BASE_URL_OPENSKY, BASE_URL_MAPS, MAPS_KEY
from db_manager import db
from lookup import get_airline_name, get_airport_city, get_airport_coords

# Indice → nome per i campi StateVector (da documentazione ufficiale)
# [0]icao24 [1]callsign [2]country [3]time_pos [4]last_contact
# [5]lon [6]lat [7]baro_alt [8]on_ground [9]velocity
# [10]true_track [11]vertical_rate [12]sensors [13]geo_alt
# [14]squawk [15]spi [16]position_source [17]category

POSITION_SOURCES = {0: 'ADS-B', 1: 'ASTERIX', 2: 'MLAT', 3: 'FLARM'}

# Rate limiting: OpenSky free tier richiede almeno 10s tra chiamate a /states/all
_opensky_lock = threading.Lock()
_last_opensky_call: float = 0.0
_OPENSKY_COOLDOWN = 10.0


def _throttle_opensky():
    """Blocca il thread corrente fino a quando non sono trascorsi 10s dall'ultima chiamata."""
    with _opensky_lock:
        wait = _OPENSKY_COOLDOWN - (time.time() - _last_opensky_call)
        if wait > 0:
            time.sleep(wait)
        globals()['_last_opensky_call'] = time.time()


def _field(state, idx, default=None):
    try:
        v = state[idx]
        return v if v is not None else default
    except IndexError:
        return default


def _encode_polyline(points: list) -> str:
    """Codifica una lista di (lat, lon) con l'algoritmo Encoded Polyline di Google."""
    result = []
    prev_lat_e5 = prev_lon_e5 = 0
    for lat, lon in points:
        lat_e5 = round(lat * 1e5)
        lon_e5 = round(lon * 1e5)
        for delta in (lat_e5 - prev_lat_e5, lon_e5 - prev_lon_e5):
            v = delta << 1
            if delta < 0:
                v = ~v
            while v >= 0x20:
                result.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            result.append(chr(v + 63))
        prev_lat_e5, prev_lon_e5 = lat_e5, lon_e5
    return ''.join(result)


def _fit_bounds(points: List[Tuple[float, float]]) -> Tuple[float, float, int]:
    """Restituisce (center_lat, center_lon, zoom) che contiene tutti i punti in 800×800 px."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    span = max(max(lats) - min(lats), max(lons) - min(lons))
    # 800 px a zoom Z copre ~1125/2^Z gradi; vogliamo span * 1.4 < copertura
    zoom = max(2, min(10, int(math.log2(750 / max(span, 0.1)))))
    return center_lat, center_lon, zoom


def _cleanup_old_pickles(max_age_hours: float = 2.0):
    """Elimina i file pickle più vecchi di max_age_hours."""
    cutoff = time.time() - max_age_hours * 3600
    for path in glob.glob('pickle/*.pickle'):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def _get_route_info(icao24: str) -> dict:
    end = int(time.time())
    begin = end - 86400
    result = {
        'from': None, 'to': '', 'from_icao': '', 'to_icao': '',
        'dep_dist_km': None, 'arr_dist_km': None, 'route_certain': False
    }
    if not icao24:
        return result
    try:
        r = requests.get(
            'https://opensky-network.org/api/flights/aircraft',
            params={'icao24': icao24, 'begin': begin, 'end': end},
            timeout=10
        )
        if r.status_code == 200:
            flights = r.json()
            if flights:
                f = sorted(flights, key=lambda x: x.get('lastSeen', 0), reverse=True)[0]
                dep_icao = f.get('estDepartureAirport') or ''
                arr_icao = f.get('estArrivalAirport') or ''
                dep_h = f.get('estDepartureAirportHorizDistance')
                arr_h = f.get('estArrivalAirportHorizDistance')
                dep_cand = f.get('departureAirportCandidatesCount', 1)
                arr_cand = f.get('arrivalAirportCandidatesCount', 1)
                result.update({
                    'from': get_airport_city(dep_icao) if dep_icao else None,
                    'to': get_airport_city(arr_icao) if arr_icao else '',
                    'from_icao': dep_icao,
                    'to_icao': arr_icao,
                    'dep_dist_km': round(dep_h / 1000) if dep_h else None,
                    'arr_dist_km': round(arr_h / 1000) if arr_h else None,
                    'route_certain': (dep_cand == 0 and arr_cand == 0)
                })
    except Exception as e:
        logging.warning(f"Errore route info per {icao24}: {e}")
    return result


def _get_aircraft_info(icao24: str) -> dict:
    if not icao24:
        return {}
    try:
        r = requests.get(
            f'https://opensky-network.org/api/metadata/aircraft/icao/{icao24}',
            timeout=10
        )
        if r.status_code == 200:
            d = r.json()
            return {
                'model':        d.get('model', '').strip(),
                'manufacturer': d.get('manufacturername', '').strip(),
                'registration': d.get('registration', '').strip(),
                'typecode':     d.get('typecode', '').strip(),
            }
    except Exception as e:
        logging.warning(f"Errore metadata aeromobile {icao24}: {e}")
    return {}


def _generate_track_map(
    icao24: str, lat: float, lon: float, chat_id,
    dep_icao: str = '', arr_icao: str = ''
) -> Optional[str]:
    """Genera una mappa che mostra:
    - linea grigia: aeroporto di partenza → inizio traccia ADS-B (stima)
    - linea blu:    traccia ADS-B reale
    - marker verde D: aeroporto di partenza
    - marker rosso A: posizione attuale
    - marker blu  B: aeroporto di arrivo stimato
    """
    if not icao24:
        return None
    try:
        r = requests.get(
            'https://opensky-network.org/api/tracks/all',
            params={'icao24': icao24, 'time': 0},
            timeout=10
        )
        if r.status_code != 200:
            return None
        track_data = r.json()
        raw_path = [wp for wp in (track_data.get('path') or [])
                    if wp[1] is not None and wp[2] is not None]
        if len(raw_path) < 2:
            return None

        actual_wps: List[Tuple[float, float]] = [(wp[1], wp[2]) for wp in raw_path]
        dep_coords = get_airport_coords(dep_icao)
        arr_coords = get_airport_coords(arr_icao)

        # Punti usati per calcolare centro e zoom della mappa
        bound_points = list(actual_wps)
        if dep_coords:
            bound_points.append(dep_coords)
        if arr_coords:
            bound_points.append(arr_coords)
        center_lat, center_lon, zoom = _fit_bounds(bound_points)

        path_params = []
        if dep_coords:
            # Segmento stimato: aeroporto di partenza → primo punto traccia
            encoded_est = _encode_polyline([dep_coords, actual_wps[0]])
            path_params.append(('path', f"color:0x888888CC|weight:2|enc:{encoded_est}"))

        # Traccia ADS-B reale
        path_params.append(('path', f"color:0x0055FFFF|weight:3|enc:{_encode_polyline(actual_wps)}"))

        marker_params = [('markers', f"color:red|label:A|{lat},{lon}")]
        if dep_coords:
            marker_params.append(('markers', f"color:green|label:D|{dep_coords[0]},{dep_coords[1]}"))
        if arr_coords:
            marker_params.append(('markers', f"color:blue|label:B|{arr_coords[0]},{arr_coords[1]}"))

        params = [
            ('center', f"{center_lat},{center_lon}"),
            ('zoom', str(zoom)),
            ('size', '800x800'),
            ('maptype', 'roadmap'),
        ] + path_params + marker_params + [('key', MAPS_KEY)]

        r2 = requests.get(BASE_URL_MAPS, params=params, timeout=15)
        r2.raise_for_status()
        image_path = f"maps/{chat_id}_track.png"
        Image.open(BytesIO(r2.content)).save(image_path)
        return image_path
    except Exception as e:
        logging.error(f"Errore mappa traccia: {e}")
        return None


def get_flight_info(user_dict: Dict, txt: str) -> Optional[Dict]:
    volo = txt[txt.index('>') + 1:-1]
    try:
        with open(f"pickle/{user_dict['chat_id']}.pickle", "rb") as f:
            dict_from_file = pickle.load(f)
    except FileNotFoundError:
        logging.info(f"Pickle non trovato per chat_id {user_dict['chat_id']}")
        return None

    try:
        raw = dict_from_file[volo]
        icao24 = raw.get('Icao24', '')
        airline = get_airline_name(raw['Call']) or raw.get('Op', '')

        # Route info prima: i codici ICAO di partenza/arrivo servono alla mappa della traccia
        route = _get_route_info(icao24)

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_aircraft = executor.submit(_get_aircraft_info, icao24)
            f_track    = executor.submit(
                _generate_track_map, icao24, raw['Lat'], raw['Long'], user_dict['chat_id'],
                route['from_icao'], route['to_icao']
            )
            aircraft_info = f_aircraft.result()
            track_image   = f_track.result()

        logging.debug(
            "Dati volo '%s': compagnia=%s aeromobile=%s %s reg=%s da=%s a=%s rotta_certa=%s track=%s",
            volo, airline,
            aircraft_info.get('manufacturer'), aircraft_info.get('model'),
            aircraft_info.get('registration'),
            route['from'], route['to'], route['route_certain'], track_image
        )

        return {
            'call': raw['Call'],
            'op': airline,
            'from': route['from'],
            'to': route['to'],
            'from_icao': route['from_icao'],
            'to_icao': route['to_icao'],
            'route_certain': route['route_certain'],
            'model': f"{aircraft_info.get('manufacturer', '')} {aircraft_info.get('model', '')}".strip(),
            'registration': aircraft_info.get('registration', ''),
            'typecode': aircraft_info.get('typecode', ''),
            'track_image': track_image,
            'hight_geo': round(raw.get('GeoAlt', 0)),
            'hight_baro': round(raw['GAlt'] * 0.3048),
            'speed': round(raw['Spd'] * 1.852),
            'trak': raw['Trak'],
            'velocita_cambio': round(raw['Vsi'] * 1.852),
        }

    except KeyError as e:
        logging.info('KeyError - reason "%s"' % str(e))
        return None


def elenco_aerei(user_dict: Dict, latitudine, longitudine) -> Optional[Dict]:
    if not db.has_quota_available():
        logging.warning("Quota API mensile OpenSky esaurita")
        return None

    _throttle_opensky()

    delta = 1.0
    params = {
        'lamin': latitudine - delta,
        'lomin': longitudine - delta,
        'lamax': latitudine + delta,
        'lomax': longitudine + delta,
    }

    try:
        response = requests.get(BASE_URL_OPENSKY, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error(f"Errore chiamata OpenSky: {e}")
        return None

    db.increase_counter()
    _cleanup_old_pickles()

    flights = []
    marker_params = []
    dict_from_file = {}
    a = 0

    for state in (data.get('states') or []):
        callsign = _field(state, 1, '').strip()
        lat = _field(state, 6)
        lon = _field(state, 5)
        if not callsign or lat is None or lon is None:
            continue
        on_ground = _field(state, 8, False)
        if on_ground:
            continue

        a += 1
        try:
            baro_alt_m   = _field(state, 7, 0)
            geo_alt_m    = _field(state, 13, baro_alt_m)
            velocity_ms  = _field(state, 9, 0)
            vert_rate_ms = _field(state, 11, 0)
            src_int      = _field(state, 16, 0)

            aircraft = {
                'Icao24': _field(state, 0, ''),
                'Call': callsign,
                'Op': _field(state, 2, ''),
                'Lat': lat,
                'Long': lon,
                'GAlt': baro_alt_m / 0.3048,
                'GeoAlt': round(geo_alt_m),
                'Spd': velocity_ms / 0.514444,
                'Trak': _field(state, 10, 0),
                'Vsi': vert_rate_ms / 0.514444,
                'OnGround': on_ground,
                'Squawk': _field(state, 14, ''),
                'PositionSource': POSITION_SOURCES.get(src_int, 'N/D'),
            }

            marker_params.append(('markers', f"color:red|label:{a}|{lat},{lon}"))
            dict_from_file[callsign] = aircraft
            flights.append(callsign)
        except (KeyError, TypeError) as e:
            logging.info('Errore parsing state: "%s"' % str(e))

    with open(f"pickle/{user_dict['chat_id']}.pickle", "wb") as f:
        pickle.dump(dict_from_file, f)

    image_name = None
    if flights:
        map_params = [
            ('center', f"{latitudine},{longitudine}"),
            ('zoom', '9'),
            ('size', '800x800'),
            ('maptype', 'roadmap'),
            ('key', MAPS_KEY),
        ] + marker_params
        try:
            r = requests.get(BASE_URL_MAPS, params=map_params, timeout=15)
            r.raise_for_status()
            image_name = f"maps/{user_dict['chat_id']}.png"
            Image.open(BytesIO(r.content)).save(image_name)
        except Exception as e:
            logging.error(f"Errore Maps API: {e}")

    return {'flights': flights, 'image': image_name}
