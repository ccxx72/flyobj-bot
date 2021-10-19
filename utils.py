from googletrans import Translator


def traduci(sentence, langout):
    tr = Translator()
    s = ' ' + tr.translate(sentence, dest=langout).text + ' '
    return s