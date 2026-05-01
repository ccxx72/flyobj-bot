import logging
import os
from logging.handlers import RotatingFileHandler

import requests
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_TOKEN
from db_manager import db
from flight_manager import elenco_aerei, get_flight_info
from translations import translate
from utils import get_user_info, flight_message

os.makedirs('pickle', exist_ok=True)
os.makedirs('maps', exist_ok=True)

_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'myapp.log')
handler = RotatingFileHandler(_log_path, maxBytes=1_000_000, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
_logger = logging.getLogger()
_logger.setLevel(logging.INFO)
_logger.addHandler(handler)
logging.info('Started')

bot = telebot.TeleBot(TELEGRAM_TOKEN)


def _send_flights(chat_id, user_dict, latitudine, longitudine):
    bot.send_chat_action(chat_id, 'upload_photo')
    aerei = elenco_aerei(user_dict, latitudine, longitudine)

    if aerei is None:
        bot.send_message(chat_id, translate(
            'Servizio temporaneamente non disponibile, riprova tra qualche minuto.',
            user_dict['language']
        ))
        return

    db.save_coords(chat_id, latitudine, longitudine)

    lang = user_dict['language']
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton(text=translate('Renew coordinates', lang), request_location=True))
    markup.row(KeyboardButton(text=translate('Share your address', lang)))
    markup.row(KeyboardButton(text=translate('Aggiorna lista', lang)))

    if not aerei['flights']:
        bot.send_message(chat_id, translate(
            'Nessun aereo rilevato nella tua zona al momento.', lang
        ), reply_markup=markup)
        return

    for i, volo in enumerate(aerei['flights'], 1):
        markup.row(KeyboardButton(text=f"{i} >{volo}<"))

    if aerei['image']:
        with open(aerei['image'], 'rb') as img:
            bot.send_photo(chat_id, img)
    bot.send_message(
        chat_id,
        translate('Clicca sul nome del volo per avere altre info', lang),
        reply_markup=markup
    )


@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_dict = get_user_info(message)
    txt = message.text
    chat_id = user_dict['chat_id']

    logging.info(f"USER: {user_dict['name']} {user_dict['last_name']}")

    lang = user_dict['language']

    if txt == translate('Aggiorna lista', lang):
        coords = db.get_coords(chat_id)
        if coords:
            _send_flights(chat_id, user_dict, coords[0], coords[1])
        else:
            bot.send_message(chat_id, translate(
                'Condividi prima la tua posizione per aggiornare la lista dei voli.', lang
            ))
        return

    if '>' in txt and txt.endswith('<') and txt.split(' ')[0].isdigit():
        flight_dict = get_flight_info(user_dict, txt)

        if not flight_dict:
            bot.send_message(chat_id, translate(
                'Condividi prima la tua posizione per aggiornare la lista dei voli.', lang
            ))
            return

        fm = flight_message(lang)
        lines = []

        header = f"{fm['volo']} {flight_dict['call']}"
        if flight_dict['op']:
            header += f"  |  {flight_dict['op']}"
        lines.append(header)

        if flight_dict['model']:
            model_line = f"{fm['aeromobile']}: {flight_dict['model']}"
            if flight_dict['typecode']:
                model_line += f" ({flight_dict['typecode']})"
            if flight_dict['registration']:
                model_line += f"  |  {fm['registrazione']}: {flight_dict['registration']}"
            lines.append(model_line)

        if flight_dict['from'] or flight_dict['to']:
            dep = f"{flight_dict['from']} ({flight_dict['from_icao']})" if flight_dict['from_icao'] else flight_dict['from'] or '?'
            arr = f"{flight_dict['to']} ({flight_dict['to_icao']})" if flight_dict['to_icao'] else flight_dict['to'] or '?'
            route_line = f"{fm['da']}: {dep}  →  {fm['per']}: {arr}"
            if not flight_dict['route_certain']:
                route_line += f"  {fm['rotta_stimata']}"
            lines.append(route_line)

        alt_line = f"{fm['quota_geo']}: {flight_dict['hight_geo']} m"
        if flight_dict['hight_baro'] != flight_dict['hight_geo']:
            alt_line += f"  |  {fm['quota_baro']}: {flight_dict['hight_baro']} m"
        lines.append(alt_line)

        lines.append(f"{fm['velocita']}: {flight_dict['speed']} km/h  |  {fm['rotta']}: {flight_dict['trak']}°")

        bot.send_message(chat_id, "\n".join(lines))

        vc = flight_dict['velocita_cambio']
        if vc > 1:
            bot.send_message(chat_id, f"{fm['in_salita']} {vc} km/h.")
        elif vc < -1:
            bot.send_message(chat_id, f"{fm['in_discesa']} {abs(vc)} km/h.")

        if flight_dict.get('track_image'):
            db.set_pending_track(chat_id, flight_dict['track_image'])
            markup_inline = InlineKeyboardMarkup()
            markup_inline.row(
                InlineKeyboardButton(translate('Sì, mostrami la rotta', lang), callback_data='show_track'),
                InlineKeyboardButton(translate('No, grazie', lang), callback_data='no_track')
            )
            bot.send_message(
                chat_id,
                translate("Vuoi vedere la rotta seguita dall'aereo?", lang),
                reply_markup=markup_inline
            )
        return

    if db.is_waiting_address(chat_id):
        db.set_waiting_address(chat_id, False)
        bot.send_chat_action(chat_id, 'typing')
        try:
            r = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': txt, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'flyobj-bot/1.0'},
                timeout=10
            )
            results = r.json()
            if results:
                lat = float(results[0]['lat'])
                lon = float(results[0]['lon'])
                _send_flights(chat_id, user_dict, lat, lon)
            else:
                bot.send_message(chat_id, translate(
                    'Indirizzo non trovato, prova a essere più preciso.', lang
                ))
        except Exception as e:
            logging.error(f"Errore geocoding: {e}")
            bot.send_message(chat_id, translate(
                'Servizio temporaneamente non disponibile, riprova tra qualche minuto.', lang
            ))
        return

    if txt == '/start':
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(KeyboardButton(text=translate('Share your coordinates', lang), request_location=True))
        markup.row(KeyboardButton(text=translate('Share your address', lang)))
        bot.send_message(
            chat_id,
            'Ciao ' + user_dict['name'] +
            translate(', if you give me your position I give you a list of flights in your area', lang),
            reply_markup=markup
        )
        return

    if txt == translate('Share your address', lang) or txt == 'Share your address':
        db.set_waiting_address(chat_id, True)
        bot.send_message(chat_id, translate('Scrivi il nome di una città o un indirizzo.', lang))
        return

    bot.send_message(
        chat_id,
        translate('Questo bot fornisce informazioni sugli aerei che sorvolano la tua zona in un raggio di '
                  'circa 100 Km. Digita "/start" per attivare il bot', lang)
    )


@bot.message_handler(content_types=['location'])
def handle_location(message):
    user_dict = get_user_info(message)
    try:
        lat = message.location.latitude
        lon = message.location.longitude
    except Exception as e:
        logging.info('Location error: %s' % str(e))
        bot.send_message(user_dict['chat_id'], translate(
            "C'è qualche problema con le tue coordinate, riprova.",
            user_dict['language']
        ))
        return

    logging.info(f"{lat}, {lon}")
    _send_flights(user_dict['chat_id'], user_dict, lat, lon)


@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    user_dict = get_user_info(message)
    bot.send_message(user_dict['chat_id'], translate('The answer is 42', user_dict['language']))


@bot.callback_query_handler(func=lambda call: call.data in ('show_track', 'no_track'))
def handle_track_callback(call):
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    if call.data == 'show_track':
        path = db.get_pending_track(chat_id)
        db.set_pending_track(chat_id, None)
        if path:
            with open(path, 'rb') as img:
                bot.send_photo(chat_id, img)
    else:
        db.set_pending_track(chat_id, None)
        bot.send_message(chat_id, 'Ok')
    bot.answer_callback_query(call.id)


logging.info('Listening ...')
bot.infinity_polling()
