import logging
import time

import telepot
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

from config import TELEGRAM_TOKEN
from flight_manager import elenco_aerei, get_flight_info
from utils import translate, get_user_info, flight_message

logging.basicConfig(filename='myapp.log', format='%(asctime)s %(message)s', level=logging.INFO)
logging.info('Started')


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)

    user_dict = get_user_info(msg)

    logging.info(f"USER: {user_dict['name']} {user_dict['last_name']}")

    if content_type == 'text':
        txt = msg['text']
        if txt[2] + txt[-1:] == '><':
            flight_dict = get_flight_info(user_dict['language'], txt)

            if not flight_dict:
                bot.sendMessage(
                    user_dict['chat_id'],
                    translate('Alcuni voli non hanno tutte le informazioni che vorrei mostrarti. Prova con un altro.',
                              user_dict['language'])
                )

            flight_msg = flight_message(user_dict['language'])

            # Messaggio rotta
            msg_to_send = f"{flight_msg['volo']} {flight_dict['call']} {flight_msg['compagnia']} {flight_dict['op']}"

            if flight_dict['from']:
                msg_to_send += f" {flight_msg['da']} {flight_dict['from']} {flight_msg['per']} {flight_dict['to']}"

            msg_to_send += f"{flight_msg['altezza']} {flight_dict['hight']} {flight_msg['velocita']} {flight_dict['speed']} {flight_msg['rotta']} {flight_dict['trak']}."

            bot.sendMessage(user_dict['chat_id'], msg_to_send)

            # Messaggio velocità
            if flight_dict['velocita_cambio'] > 1:
                bot.sendMessage(user_dict['chat_id'], f"{flight_msg['velocita_cambio']} {flight_dict['velocita_cambio']} Kmh.")

            # elif flight_dict['velocita_cambio'] < 0:
            #     bot.sendMessage(
            #         chat_id,
            #         'In questo momento sta effettuando una discesa ad una velocità di ' +
            #         str(velocita_cambio) + ' Kmh' + str(dict_from_file[infovolo]['Vsi'])
            #     )

        elif txt == '/start':
            bot.sendMessage(
                user_dict['chat_id'],
                'Ciao ' + user_dict['name'] +
                translate(', if you give me your position I give you a list of flights in your area', user_dict['language']),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(
                            text=translate('Share your coordinates', user_dict['language']),
                            request_location=True
                        )],
                        [KeyboardButton(
                            text=translate('Share your address', user_dict['language']),
                            request_location=False
                        )]
                    ]
                )
            )

        elif txt == '/help':
            bot.sendMessage(
                user_dict['chat_id'],
                translate('Questo bot fornisce informazioni sugli aerei che sorvolano la tua zona in un raggio di '
                          'circa 50 Km. Digita "/start" per attivare il bot', user_dict['language'])
            )

        else:
            bot.sendMessage(
                user_dict['chat_id'],
                translate('Questo bot fornisce informazioni sugli aerei che sorvolano la tua zona in un raggio di '
                          'circa 50 Km. Digita "/start" per attivare il bot', user_dict['language'])
            )

    elif content_type == "location":
        tastiera = [[
            KeyboardButton(
                text=translate('Renew coordinates', user_dict['language']),
                request_contact=None,
                request_location=True)
        ]]

        try:
            latitudine = msg["location"]["latitude"]
            longitudine = msg["location"]["longitude"]
        except KeyError as e:
            logging.info('I got a KeyError - reason "%s"' % str(e))
            bot.sendMessage(user_dict['chat_id'], translate("C'è qualche problema con le tue coordinate", user_dict['language']))

        logging.info(f"{latitudine}, {longitudine}")

        aerei = elenco_aerei(user_dict, latitudine, longitudine)

        tastiera.extend(aerei['keyboard'])

        bot.sendPhoto(user_dict['chat_id'], open(aerei['image'], "rb"))
        bot.sendMessage(
            user_dict['chat_id'],
            translate('Clicca sul nome del volo per avere altre info', user_dict['language']),
            reply_markup=ReplyKeyboardMarkup(keyboard=tastiera)
        )

    elif content_type == "sticker":
        bot.sendMessage(user_dict['chat_id'], translate('The answer is 42', user_dict['language']))


bot = telepot.Bot(TELEGRAM_TOKEN)
bot.message_loop(on_chat_message)

logging.info('Listening ...')

while 1:
    time.sleep(10)
