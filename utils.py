from googletrans import Translator


def traduci(sentence, langout):
    tr = Translator()
    return f"{tr.translate(sentence, dest=langout).text}"
