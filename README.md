# FlyObj Bot

A Telegram bot that provides real-time information about aircraft flying over a specified area. The bot retrieves flight data, displays aircraft positions on a map, and offers detailed information about each flight on demand.

---

## Features

### Area radar
- Detects all aircraft currently in flight within approximately **100 km** of the user's position
- Displays a **satellite map** with a numbered marker for each aircraft
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
After viewing flight details, the user is offered the option to see a **route map** showing the aircraft's recent trajectory as a blue line overlaid on a Google Maps image, with the current position marked in red. The map is generated on demand only if the user requests it.

### Refresh without resharing location
A dedicated **"Aggiorna lista"** button allows the user to refresh the aircraft list using the last known position, without having to share their location again.

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
| [Google Translate](https://cloud.google.com/translate) | Automatic message translation based on the user's Telegram language |

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

---

## Project structure

```
flyobj-bot-main/
├── flyobj-bot.py       # Bot entry point and Telegram handlers
├── flight_manager.py   # OpenSky API calls, map generation, data processing
├── db_manager.py       # Monthly API call counter (SQLite)
├── lookup.py           # Airline and airport name lookup from local databases
├── utils.py            # Translation helpers and user info extraction
├── config.py           # Configuration loaded from .env
├── data/               # Downloaded reference databases (airlines, airports)
├── pickle/             # Per-user cached flight data
├── maps/               # Generated map images
└── requirements.txt
```

---

## Rate limiting

The bot tracks OpenSky API calls in a local SQLite database (`flyobj_bot.sqlite3`) and enforces a monthly quota of **350 requests** to stay within the free tier limits. When the quota is reached, the bot notifies the user instead of making further calls.

---

## Notes

- The OpenSky Network free tier allows up to 400 anonymous requests per day and has a minimum interval of 10 seconds between state vector requests.
- Aircraft route information (departure/destination) is estimated by OpenSky based on proximity to airports and may not always be available or accurate.
- Flight track data is marked as experimental in the OpenSky API and may occasionally be unavailable.
- Google Translate results are cached in memory for the duration of the session to minimise external API calls.
