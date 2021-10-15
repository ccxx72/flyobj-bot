import logging
import time
from io import BytesIO

import json
import pickle
import requests
import telepot
from PIL import Image
from googletrans import Translator
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(filename='/progetti/flyobj_bot/myapp.log', format='%(asctime)s %(message)s', level=logging.INFO)
logging.info('Started')


TELEGRAM_TOKEN = '*******************************'
MAPS_KEY = '**********************************'


def traduci(sentence, langout):
    tr = Translator()
    s = ' ' + tr.translate(sentence, dest=langout).text + ' '
    return s


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    
    language = msg["from"]["language_code"][0:2]
    if content_type == 'text':
        name = msg["from"]["first_name"]
        print(language)
        try:
            logging.info("USER: " + name + " " + msg["from"]["last_name"])
        except KeyError:
            logging.info("Errore per : " + name)

        txt = msg['text']
        if txt[2] + txt[-1:] == '><':
            info_volo(msg, language)
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
            name = msg["from"]["first_name"]
            logging.info("USER: " + name + " " + msg["from"]["last_name"])
            latitudine = msg["location"]["latitude"]
            longitudine = msg["location"]["longitude"]
            logging.info(str(latitudine) + "," + str(longitudine))
            elenco_aerei(msg, latitudine, longitudine, language)
        except KeyError as e:
            logging.info('I got a KeyError - reason "%s"' % str(e))
            bot.sendMessage(chat_id, traduci("C'è qualche problema con le tue coordinate", language))
    elif content_type == "sticker":
        bot.sendMessage(chat_id, traduci('The answer is 42', language))


def elenco_aerei(msg, latitudine, longitudine, language):
    name = msg["from"]["first_name"]
    chat_id = msg["chat"]["id"]
    dict_from_file = dict()
    file_da_leggere = open(str(chat_id), 'wb')
    url = "https://radar.freedar.uk/VirtualRadar/AircraftList.json?lat=" + \
          str(latitudine) + "&lng=" + str(longitudine) + "&fDstL=0&fDstU=100"
    
    with requests.get(url) as url:
        data = json.loads(url.text)  # read json in dict

    elenco_aerei = []
    tastiera = [
        [
            KeyboardButton(
                text=traduci('Renew coordinates', language),
                request_contact=None,
                request_location=True)
        ]
    ]
    
    markers = ""
    a = 0
    for i in data[u'acList']:
        # acList = i
        a = a + 1
        
        try:
            markers = markers + "&markers=color:red%7Clabel:" + str(a) + "%7C" + str(i["Lat"]) + "," + str(i["Long"])
            dict_from_file[i['Call']] = i
            
            elenco_aerei.append(i['Call'])
            logging.info('elenco aerei :' + str(elenco_aerei))
        except KeyError as e:
            logging.info('I got a KeyError - reason "%s"' % str(e))
    b = 0
    for aereo in elenco_aerei:
        b = b + 1
        
        tastiera.append([KeyboardButton(text=str(b) + ' >' + aereo + '<')])
        
    map_url = "https://maps.googleapis.com/maps/api/staticmap?center=" + str(latitudine) + "," + str(longitudine) + \
              "&zoom=9&size=800x800&maptype=roadmap&" + markers + "&key=" + MAPS_KEY
    # logger.debug("Mappa : " + mapurl)
    r = requests.get(map_url)
    mappa = Image.open(BytesIO(r.content))
    mappa.save(str(chat_id) + ".png")
    # for k in dict_from_file:
    # logging.info('test dizionario : ' + k)
    pickle.dump(dict_from_file, file_da_leggere)
    # file_da_leggere.close
    # logger.debug("Tastiera " + str(tastiera))
    bot.sendPhoto(chat_id, open(str(chat_id) + ".png", "rb"))
    bot.sendMessage(
        chat_id,
        traduci('Clicca sul nome del volo per avere altre info', language),
        reply_markup=ReplyKeyboardMarkup(keyboard=tastiera)
    )


def info_volo(msg, language):
    chat_id = msg["chat"]["id"]
    txt = msg['text']
    volo = txt[3:-1]
    file_da_leggere = open(str(chat_id), 'rb')
    dict_from_file = pickle.load(file_da_leggere)
    try:
        altezza = round((dict_from_file[volo]['GAlt']) * 0.3048)
        velocita = round((dict_from_file[volo]['Spd']) * 1.852)
        prua = str(dict_from_file[volo]['Trak'])
        if 'From' in dict_from_file[volo]:
            bot.sendMessage(
                chat_id,
                traduci('Il volo ', language) + dict_from_file[volo]['Call'] +
                traduci(' della compagnia ', language) + ' ' +
                dict_from_file[volo]['Op'] + traduci(' partito da ', language) +
                dict_from_file[volo]['From'] + traduci(' è diretto a ', language) + dict_from_file[volo]['To'] +
                traduci('. Si trova ad un altezza di ', language) + str(altezza) +
                traduci(' metri e vola ad una velocità di ', language) +
                str(velocita) + traduci(' Kmh. La sua rotta è ', language) + prua
            )
        else:
            bot.sendMessage(
                chat_id,
                traduci('Il volo ', language) + dict_from_file[volo]['Call'] +
                traduci(' della compagnia ', language) + dict_from_file[volo]['Op'] +
                traduci(' si trova ad un altezza di ', language) + str(altezza) +
                traduci(' metri e vola ad una velocità di ', language) + str(velocita) +
                traduci(' Kmh. La sua rotta è ', language) + prua
            )
        velocita_cambio = round((dict_from_file[volo]['Vsi']) * 1.852)
        if velocita_cambio > 1:
            bot.sendMessage(
                chat_id,
                traduci('In questo momento sta salendo di quota ad una velocità di ', language) +
                str(velocita_cambio) + ' Kmh'
            )
            # elif velocita_cambio < 0:
            #     bot.sendMessage(
            #         chat_id,
            #         'In questo momento sta effettuando una discesa ad una velocità di ' +
            #         str(velocita_cambio) + ' Kmh' + str(dict_from_file[infovolo]['Vsi'])
            #     )
    except KeyError as e:
        logging.info('I got a KeyError - reason "%s"' % str(e))
        bot.sendMessage(
            chat_id,
            traduci('Alcuni Voli non hanno tutte le informazioni che vorrei mostrarti. Prova con un altro', language)
        )


bot = telepot.Bot(TELEGRAM_TOKEN)
bot.message_loop(on_chat_message)

logging.info('Listening ...')

while 1:
    time.sleep(10)
