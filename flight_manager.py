import json
import logging
import pickle
from io import BytesIO

import requests
from PIL import Image
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

from config import BASE_URL_RADAR, BASE_URL_MAPS, MAPS_KEY
from utils import traduci


def info_volo(chat_id, txt, language, bot):
	volo = txt[3:-1]
	file_da_leggere = open(f'pickle/{chat_id}.pickle', 'rb')
	dict_from_file = pickle.load(file_da_leggere)
	try:
		altezza = round((dict_from_file[volo]['GAlt']) * 0.3048)
		velocita = round((dict_from_file[volo]['Spd']) * 1.852)
		prua = str(dict_from_file[volo]['Trak'])
		# flight_dict = {
		# 	'call': dict_from_file[volo]['Call'],
		# 	'op': dict_from_file[volo]['Op'],
		# 	'from': dict_from_file[volo].get('From'),
		# 	'to': dict_from_file[volo]['To'],
		# 	'hight': round((dict_from_file[volo]['GAlt']) * 0.3048),
		# 	'speed': round((dict_from_file[volo]['Spd']) * 1.852),
		# 	'trak': dict_from_file[volo]['Trak']
		# }
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


def elenco_aerei(chat_id, latitudine, longitudine, language, bot):
	dict_from_file = dict()
	file_da_leggere = open(f'pickle/{chat_id}.pickle', 'wb')

	url = f"{BASE_URL_RADAR}?lat={latitudine}&lng={longitudine}&fDstL=0&fDstU=100"
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
		a += 1
		try:
			markers = markers + "&markers=color:red%7Clabel:" + str(a) + "%7C" + str(i["Lat"]) + "," + str(i["Long"])
			dict_from_file[i['Call']] = i

			elenco_aerei.append(i['Call'])
			logging.info('elenco aerei :' + str(elenco_aerei))
		except KeyError as e:
			logging.info('I got a KeyError - reason "%s"' % str(e))
	b = 0
	for aereo in elenco_aerei:
		b += 1
		tastiera.append([KeyboardButton(text=str(b) + ' >' + aereo + '<')])

	map_url = f"{BASE_URL_MAPS}?center={latitudine},{longitudine}&zoom=9&size=800x800&maptype=roadmap&{markers}&key={MAPS_KEY}"
	r = requests.get(map_url)
	image_name = f"maps/{chat_id}.png"
	mappa = Image.open(BytesIO(r.content))
	mappa.save(image_name)
	pickle.dump(dict_from_file, file_da_leggere)
	bot.sendPhoto(chat_id, open(image_name, "rb"))
	bot.sendMessage(
		chat_id,
		traduci('Clicca sul nome del volo per avere altre info', language),
		reply_markup=ReplyKeyboardMarkup(keyboard=tastiera)
	)
