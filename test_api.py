import requests
from googletrans import Translator

OPENSKY_URL = "https://opensky-network.org/api/states/all"
MAPS_URL    = "https://maps.googleapis.com/maps/api/staticmap"

# --- 1. OpenSky Network ---
print("=== 1. OpenSky Network API ===")
try:
    params = {'lamin': 44.0, 'lomin': 8.0, 'lamax': 46.0, 'lomax': 10.0}
    r = requests.get(OPENSKY_URL, params=params, timeout=15)
    print(f"HTTP Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        states = data.get('states') or []
        print(f"OK - Aerei ricevuti: {len(states)}")
        if states:
            s = states[0]
            print(f"  Esempio: callsign={str(s[1]).strip()}, paese={s[2]}, lat={s[6]}, lon={s[5]}, alt={s[7]}m")
    else:
        print(f"ERRORE - Risposta: {r.text[:200]}")
except Exception as e:
    print(f"ERRORE connessione: {e}")

# --- 2. Google Maps Static API ---
print("\n=== 2. Google Maps Static API ===")
try:
    r = requests.get(
        f"{MAPS_URL}?center=45,9&zoom=9&size=100x100&maptype=roadmap&key=INVALID_KEY_TEST",
        timeout=10
    )
    print(f"HTTP Status: {r.status_code}")
    if r.status_code == 200:
        print("OK - Endpoint raggiungibile e chiave valida")
    elif r.status_code in (400, 403):
        print("Endpoint raggiungibile - chiave non valida (comportamento atteso con chiave di test)")
    else:
        print(f"Risposta inattesa: {r.text[:200]}")
except Exception as e:
    print(f"ERRORE connessione: {e}")

# --- 3. Google Translate (googletrans) ---
print("\n=== 3. Google Translate (googletrans) ===")
try:
    tr = Translator()
    result = tr.translate("Hello, this is a test", dest="it")
    print(f"OK - Traduzione: {result.text}")
except Exception as e:
    print(f"ERRORE: {e}")
