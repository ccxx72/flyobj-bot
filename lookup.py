import csv
import logging
import os

import requests

DATA_DIR = "data"
AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"
AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

_airlines: dict = {}  # ICAO prefix (3 lettere) -> nome compagnia
_airports: dict = {}  # codice ICAO aeroporto -> città


def _download(url: str, path: str):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(r.text)


def _load_airlines():
    path = os.path.join(DATA_DIR, "airlines.dat")
    if not os.path.exists(path):
        logging.info("Download airlines.dat da OpenFlights...")
        _download(AIRLINES_URL, path)
    with open(path, encoding='utf-8') as f:
        for row in csv.reader(f):
            # formato: ID, Name, Alias, IATA, ICAO, Callsign, Country, Active
            if len(row) >= 5 and row[4] not in (r'\N', 'N/A', ''):
                _airlines[row[4].upper()] = row[1]


def _load_airports():
    path = os.path.join(DATA_DIR, "airports.dat")
    if not os.path.exists(path):
        logging.info("Download airports.dat da OpenFlights...")
        _download(AIRPORTS_URL, path)
    with open(path, encoding='utf-8') as f:
        for row in csv.reader(f):
            # formato: ID, Name, City, Country, IATA, ICAO, Lat, Lon, ...
            if len(row) >= 6 and row[5] not in (r'\N', ''):
                city = row[2] if row[2] else row[1]
                _airports[row[5].upper()] = city


def get_airline_name(callsign: str) -> str:
    """Restituisce il nome della compagnia dal prefisso ICAO del callsign (primi 3 caratteri)."""
    if not callsign or len(callsign) < 3:
        return ''
    return _airlines.get(callsign[:3].upper(), '')


def get_airport_city(icao_code: str) -> str:
    """Restituisce il nome della città dato il codice ICAO dell'aeroporto."""
    if not icao_code:
        return ''
    return _airports.get(icao_code.upper(), icao_code)


os.makedirs(DATA_DIR, exist_ok=True)
try:
    _load_airlines()
    _load_airports()
    logging.info(f"Lookup caricato: {len(_airlines)} compagnie, {len(_airports)} aeroporti")
except Exception as e:
    logging.error(f"Errore caricamento lookup: {e}")
