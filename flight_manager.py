import logging
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Dict, Optional

import requests
from PIL import Image

import pickle
from config import BASE_URL_OPENSKY, BASE_URL_MAPS, MAPS_KEY
from db_manager import DbManager
from lookup import get_airline_name, get_airport_city

db = DbManager()

# Indice → nome per i campi StateVector (da documentazione ufficiale)
# [0]icao24 [1]callsign [2]country [3]time_pos [4]last_contact
# [5]lon [6]lat [7]baro_alt [8]on_ground [9]velocity
# [10]true_track [11]vertical_rate [12]sensors [13]geo_alt
# [14]squawk [15]spi [16]position_source [17]category

POSITION_SOURCES = {0: 'ADS-B', 1: 'ASTERIX', 2: 'MLAT', 3: 'FLARM'}


def _field(state, idx, default=None):
    try:
        v = state[idx]
        return v if v is not None else default
    except IndexError:
        return default


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
    """Recupera modello e costruttore dalla banca dati OpenSky."""
    if not icao24:
        return {}
    try:
        r = requests.get(
            f'https://opensky-network.org/api/metadata/aircraft/icao/{icao24}',
            timeout=10
        )
        if r.status_code == 200:
            d = r.json()
            model = d.get('model', '').strip()
            manufacturer = d.get('manufacturername', '').strip()
            registration = d.get('registration', '').strip()
            typecode = d.get('typecode', '').strip()
            return {
                'model': model,
                'manufacturer': manufacturer,
                'registration': registration,
                'typecode': typecode,
            }
    except Exception as e:
        logging.warning(f"Errore metadata aeromobile {icao24}: {e}")
    return {}


def _generate_track_map(icao24: str, lat: float, lon: float, chat_id) -> Optional[str]:
    """Genera una mappa con la traccia del volo sovrapposta."""
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
        path = [wp for wp in (track_data.get('path') or [])
                if wp[1] is not None and wp[2] is not None]
        if len(path) < 2:
            return None

        # Campiona max 15 punti per rispettare il limite di lunghezza URL
        step = max(1, len(path) // 15)
        waypoints = path[::step]
        if path[-1] not in waypoints:
            waypoints.append(path[-1])

        # Costruisce il parametro path per Google Static Maps
        path_param = 'color:0x0055FFFF%7Cweight:3'
        for wp in waypoints:
            path_param += f'%7C{wp[1]},{wp[2]}'

        map_url = (
            f"{BASE_URL_MAPS}?center={lat},{lon}&zoom=7&size=800x800"
            f"&maptype=roadmap&path={path_param}"
            f"&markers=color:red%7Clabel:A%7C{lat},{lon}&key={MAPS_KEY}"
        )
        r2 = requests.get(map_url, timeout=15)
        r2.raise_for_status()
        image_path = f"maps/{chat_id}_track.png"
        Image.open(BytesIO(r2.content)).save(image_path)
        return image_path
    except Exception as e:
        logging.error(f"Errore mappa traccia: {e}")
        return None


def get_flight_info(user_dict: Dict, txt: str) -> Optional[Dict]:
    volo = txt[3:-1]
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

        # Chiamate API in parallelo per ridurre i tempi di attesa
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_route    = executor.submit(_get_route_info, icao24)
            f_aircraft = executor.submit(_get_aircraft_info, icao24)
            f_track    = executor.submit(
                _generate_track_map, icao24, raw['Lat'], raw['Long'], user_dict['chat_id']
            )
            route         = f_route.result()
            aircraft_info = f_aircraft.result()
            track_image   = f_track.result()

        print(f"\n--- DATI per '{volo}' ---")
        print(f"  Compagnia   : {airline}")
        print(f"  Aeromobile  : {aircraft_info.get('manufacturer')} {aircraft_info.get('model')} ({aircraft_info.get('typecode')})")
        print(f"  Reg.        : {aircraft_info.get('registration')}")
        print(f"  Da          : {route['from']} ({route['from_icao']})")
        print(f"  A           : {route['to']} ({route['to_icao']})")
        print(f"  Rotta certa : {route['route_certain']}")
        print(f"  Track image : {track_image}")
        print("------------------------\n")

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

    flights = []
    markers = ""
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

            markers += f"&markers=color:red%7Clabel:{a}%7C{lat},{lon}"
            dict_from_file[callsign] = aircraft
            flights.append(callsign)
        except (KeyError, TypeError) as e:
            logging.info('Errore parsing state: "%s"' % str(e))

    with open(f"pickle/{user_dict['chat_id']}.pickle", "wb") as f:
        pickle.dump(dict_from_file, f)

    image_name = None
    if flights:
        map_url = (
            f"{BASE_URL_MAPS}?center={latitudine},{longitudine}"
            f"&zoom=9&size=800x800&maptype=roadmap&{markers}&key={MAPS_KEY}"
        )
        try:
            r = requests.get(map_url, timeout=15)
            r.raise_for_status()
            image_name = f"maps/{user_dict['chat_id']}.png"
            Image.open(BytesIO(r.content)).save(image_name)
        except Exception as e:
            logging.error(f"Errore Maps API: {e}")

    return {'flights': flights, 'image': image_name}
