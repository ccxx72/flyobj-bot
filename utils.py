from googletrans import Translator


def get_user_info(msg):
    return {
        'language': msg["from"]["language_code"][0:2],
        'chat_id': msg["chat"]["id"],
        'name': msg["from"].get("first_name", ""),
        'last_name': msg["from"].get("last_name", "")
    }


def flight_message(language):
    # TODO trovare una soluzione migliore
    return {
        'volo': translate('Il volo', language),
        'compagnia': translate('della compagnia', language),
        'da': translate('partito da', language),
        'per': translate('è diretto a', language),
        'altezza': translate('. Si trova ad un altezza di', language),
        'velocita': translate('metri e vola ad una velocità di', language),
        'rotta': translate('Kmh. La sua rotta è', language),
        'velocita_cambio': translate('In questo momento sta salendo di quota ad una velocità di', language)
    }


def translate(sentence, language):
    tr = Translator()
    return f' {tr.translate(sentence, dest=language).text} '
