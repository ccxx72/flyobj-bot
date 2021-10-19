import logging
import time

import telepot
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

from config import TELEGRAM_TOKEN
from flight_manager import elenco_aerei, info_volo
from utils import traduci

logging.basicConfig(filename='myapp.log', format='%(asctime)s %(message)s', level=logging.INFO)
logging.info('Started')


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    
    language = msg["from"]["language_code"][0:2]
    chat_id = msg["chat"]["id"]
    name = msg["from"].get("first_name", "")
    last_name = msg["from"].get("last_name", "")

    logging.info(f"USER: {name} {last_name}")

    if content_type == 'text':
        txt = msg['text']
        if txt[2] + txt[-1:] == '><':
            info_volo(chat_id, txt, language, bot)

        elif txt == '/start':
            bot.sendMessage(
                chat_id,
                'Ciao ' + name +
                traduci(
                    ', if you give me your position I give you a list of flights in your area',
                    language
                ),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text=traduci('Share your coordinates', language), request_location=True)],
                        [KeyboardButton(text=traduci('Share your address', language), request_location=False)]
                    ]
                )
            )
        elif txt == '/help':
            bot.sendMessage(
                chat_id,
                traduci(
                    'Questo bot fornisce informazioni sugli aerei che sorvolano la tua zona in un raggio di '
                    'circa 50 Km. Digita "/start" per attivare il bot',
                    language
                )
            )
        else:
            bot.sendMessage(
                chat_id,
                traduci(
                    'Questo bot fornisce informazioni sugli aerei che sorvolano la tua zona in un raggio di '
                    'circa 50 Km. Digita "/start" per attivare il bot',
                    language
                )
            )
    elif content_type == "location":
        try:
            latitudine = msg["location"]["latitude"]
            longitudine = msg["location"]["longitude"]
            logging.info(str(latitudine) + "," + str(longitudine))
            elenco_aerei(chat_id, latitudine, longitudine, language, bot)
        except KeyError as e:
            logging.info('I got a KeyError - reason "%s"' % str(e))
            bot.sendMessage(chat_id, traduci("C'è qualche problema con le tue coordinate", language))
    elif content_type == "sticker":
        bot.sendMessage(chat_id, traduci('The answer is 42', language))


bot = telepot.Bot(TELEGRAM_TOKEN)
bot.message_loop(on_chat_message)

logging.info('Listening ...')

while 1:
    time.sleep(10)
