import gettext
from pathlib import PurePath

translator = gettext.NullTranslations()


def register_translator(folder: PurePath):
    global translator
    translator = gettext.translation(
        'xmlschema',
        folder
    )


def get_translation(message):
    return translator.gettext(message)


_ = get_translation
