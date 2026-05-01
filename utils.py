from googletrans import Translator

_translator = Translator()
_cache: dict = {}


def get_user_info(msg):
    lang = getattr(msg.from_user, 'language_code', None) or 'en'
    return {
        'language': lang[:2],
        'chat_id': msg.chat.id,
        'name': msg.from_user.first_name or '',
        'last_name': msg.from_user.last_name or ''
    }


def flight_message(language):
    return {
        # Rotta
        'volo':             translate('✈ Volo', language),
        'compagnia':        translate('della compagnia', language),
        'da':               translate('Partito da', language),
        'per':              translate('diretto a', language),
        'rotta_stimata':    translate('(rotta stimata)', language),
        # Posizione
        'quota_geo':        translate('Quota geometrica', language),
        'quota_baro':       translate('Quota barometrica', language),
        'velocita':         translate('Velocità', language),
        'rotta':            translate('Rotta', language),
        # Aeromobile
        'aeromobile':       translate('Aeromobile', language),
        'registrazione':    translate('Registrazione', language),
        # Verticale
        'in_salita':        translate('In salita a', language),
        'in_discesa':       translate('In discesa a', language),
    }


def translate(sentence, language):
    key = (sentence, language)
    if key not in _cache:
        _cache[key] = _translator.translate(sentence, dest=language).text
    return _cache[key]
