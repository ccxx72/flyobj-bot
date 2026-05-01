import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MAPS_KEY = os.getenv('MAPS_KEY')

BASE_URL_OPENSKY = 'https://opensky-network.org/api/states/all'
BASE_URL_MAPS = 'https://maps.googleapis.com/maps/api/staticmap'
