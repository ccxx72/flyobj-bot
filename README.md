# FlyObj Bot &nbsp;·&nbsp; v1.2.0

A Telegram bot that provides real-time information about aircraft flying over a specified area. The bot retrieves flight data, displays aircraft positions on a map, and offers detailed information about each flight on demand.

---

## Features

### Area radar
- Detects all aircraft currently in flight within approximately **100 km** of the user's position
- Displays a **map** with a numbered marker for each aircraft
- Excludes aircraft on the ground to keep the list clean
- Supports both **GPS location sharing** and **manual address entry** (geocoded via OpenStreetMap Nominatim)

### Flight details
When the user selects a flight from the list, the bot provides:
- **Flight identifier** and **airline name** (resolved from the ICAO callsign prefix using the OpenFlights database)
- **Aircraft model and manufacturer** (e.g., Airbus A320neo, Boeing 737-800) and registration number, retrieved from the OpenSky metadata database
- **Estimated route**: departure and destination airports with city names, including a note when the route is estimated rather than confirmed
- **Geometric and barometric altitude** in metres
- **Ground speed** in km/h
- **Heading** in degrees
- **Climb or descent rate** in km/h (shown only when significant)

### Flight track map
After viewing flight details, the user is offered the option to see a **route map** that reconstructs the broadest possible picture of the flight:
- **Grey line** — estimated segment from the departure airport to the first recorded ADS-B point
- **Blue line** — actual ADS-B trajectory (full track, encoded with Google's Polyline Algorithm)
- **Green marker D** — departure airport
- **Red marker A** — current aircraft position
- **Blue marker B** — estimated arrival airport

The map zoom and centre are calculated automatically from the bounding box of all points, so short hops and long-haul flights are both framed correctly. The map is generated on demand only if the user requests it.

### Refresh without resharing location
A dedicated **"Aggiorna lista"** button allows the user to refresh the aircraft list using the last known position, without having to share their location again. The last position is persisted across bot restarts.

### Multilingual interface
All bot messages are served in the user's Telegram language via a built-in static translation table (Italian, English, German, French, Spanish, Portuguese, Russian). Unknown languages fall back to English.

---

## Data sources

| Source | Purpose |
|--------|---------|
| [OpenSky Network](https://opensky-network.org) | Real-time aircraft state vectors (position, altitude, speed, heading) |
| [OpenSky Network — Flights API](https://opensky-network.org/apidoc) | Estimated departure and arrival airports |
| [OpenSky Network — Metadata API](https://opensky-network.org/apidoc) | Aircraft model, manufacturer, registration |
| [OpenSky Network — Tracks API](https://opensky-network.org/apidoc) | Flight trajectory waypoints |
| [OpenFlights](https://openflights.org/data.html) | ICAO airline prefix → airline name, ICAO airport code → city name |
| [Google Maps Static API](https://developers.google.com/maps/documentation/maps-static) | Map images with aircraft markers and flight tracks |
| [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org) | Geocoding of manually entered addresses |

---

## Setup

### Requirements

- Python 3.9+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Google Maps Static API key ([Google Cloud Console](https://console.cloud.google.com))

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
TELEGRAM_TOKEN=your_telegram_bot_token
MAPS_KEY=your_google_maps_api_key
```

On first run, the bot automatically downloads the OpenFlights airline and airport reference databases into the `data/` directory.

### Run

```bash
python flyobj-bot.py
```

### Tests

```bash
pytest test_api.py -v
```

---

## Project structure

```
flyobj-bot/
├── flyobj-bot.py       # Bot entry point and Telegram handlers
├── flight_manager.py   # OpenSky API calls, map generation, data processing
├── db_manager.py       # API quota counter and conversational state (SQLite)
├── lookup.py           # Airline and airport name lookup from local databases
├── translations.py     # Static i18n string table (7 languages)
├── utils.py            # User info extraction and flight message labels
├── config.py           # Configuration loaded from .env
├── test_api.py         # Pytest test suite
├── data/               # Downloaded reference databases (airlines, airports)
├── pickle/             # Per-user cached flight data (auto-cleaned after 2 h)
├── maps/               # Generated map images
└── requirements.txt
```

---

## Rate limiting

The bot tracks OpenSky API calls in a local SQLite database (`flyobj_bot.sqlite3`) and enforces a monthly quota of **350 requests** to stay within the free tier limits. When the quota is reached, the bot notifies the user instead of making further calls.

A per-process throttle also guarantees at least **10 seconds** between consecutive calls to the `/states/all` endpoint, as required by the OpenSky free tier.

---

## Notes

- Aircraft route information (departure/destination) is estimated by OpenSky based on proximity to airports and may not always be available or accurate.
- Flight track data is marked as experimental in the OpenSky API and may occasionally be unavailable.
- Per-user pickle files older than 2 hours are deleted automatically on each radar refresh.
- Conversational state (last coordinates, address-waiting flag, pending track path) is persisted in SQLite and survives bot restarts.

---

## Changelog

### v1.2.0 — 2026-05-01

**Extended flight track map**
- Track map now shows the full estimated route: a grey line from the departure airport to the start of the ADS-B track, followed by the recorded trajectory in blue.
- Departure airport (green D) and estimated arrival airport (blue B) are shown as markers on the map.
- Airport coordinates are resolved locally from the OpenFlights `airports.dat` file — no extra API call.
- Map centre and zoom are computed automatically from the bounding box of all points (departure airport, track, arrival airport), replacing the fixed zoom 7.

**Bug fix**
- Fixed flight selection for flights numbered 10 and above: the previous check `txt[2] == '>'` silently ignored any button beyond the 9th in the list.

---

### v1.1.0 — 2026-05-01

**Stability & correctness**
- Added a 10-second throttle between OpenSky `/states/all` calls to comply with free-tier rate limits and avoid being blocked.
- Conversational state (`last coordinates`, `waiting for address`, `pending track`) is now stored in SQLite instead of in-memory dictionaries. State survives bot restarts.
- Per-user pickle files are automatically deleted after 2 hours, preventing unbounded disk growth.

**Maps**
- Flight track maps now use **Google Encoded Polyline** encoding, transmitting the full trajectory regardless of length instead of capping at 15 sampled waypoints.
- URL construction for all Google Static Maps requests migrated to `requests` params lists, removing manual `%7C` escaping.

**Internationalisation**
- Replaced the unstable `googletrans==4.0.0rc1` dependency with a built-in static translation table (`translations.py`) covering 7 languages. No external API calls are made for UI strings.

**Code quality**
- Debug `print()` calls in `get_flight_info()` replaced with `logging.debug()`.
- Removed unused dead code: `models/api_counter.py`, `models/__init__.py`, `tortoise.json`.
- Unpinned `requests` and `Pillow` versions to allow security updates.
- Added a `pytest` test suite (`test_api.py`) covering polyline encoding, field accessor, airline/airport lookup, API quota logic, DB state methods, and static translations.

### v1.0.0 — initial release

- Real-time radar: detects aircraft within ~100 km via OpenSky Network.
- Per-flight details: airline, aircraft model, registration, route, altitude, speed, heading, climb/descent rate.
- Flight track map generated on demand using Google Maps Static API.
- Multilingual UI via Google Translate (replaced in v1.1.0).
- Monthly API quota tracking in SQLite.
- Offline airline and airport lookup via OpenFlights data files.
