from translations import translate, _T  # noqa: F401 – re-export translate for callers


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
        'volo':          translate('✈ Volo', language),
        'compagnia':     translate('della compagnia', language),
        'da':            translate('Partito da', language),
        'per':           translate('diretto a', language),
        'rotta_stimata': translate('(rotta stimata)', language),
        'quota_geo':     translate('Quota geometrica', language),
        'quota_baro':    translate('Quota barometrica', language),
        'velocita':      translate('Velocità', language),
        'rotta':         translate('Rotta', language),
        'aeromobile':    translate('Aeromobile', language),
        'registrazione': translate('Registrazione', language),
        'in_salita':     translate('In salita a', language),
        'in_discesa':    translate('In discesa a', language),
    }
