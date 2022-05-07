#
# Copyright (c), 2016-2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
#
from typing import Any, Iterable, Optional, Type, Union
import gettext as _gettext
from pathlib import Path

_translation: Any = None


def use_translation(localedir: Union[None, str, Path] = None,
                    languages: Optional[Iterable[str]] = None,
                    class_: Type[Any] = None,
                    fallback: bool = False,
                    install: bool = False) -> None:
    """
    Use a translation for xmlschema error messages.

    :param localedir: a string or Path-like object to locale directory
    :param languages: list of language codes
    :param class_: translation class to use
    :param fallback: if `True` activate fallback mode
    :param install: if `True` install function _() in Python’s builtins namespace
    """
    global _translation

    if localedir is None:
        localedir = Path(__file__).parent.joinpath('locale').resolve()
    if languages is None:
        languages = ['en', 'it']

    _translation = _gettext.translation(
        domain='xmlschema',
        localedir=localedir,
        languages=languages,
        class_=class_,
        fallback=fallback,
    )
    if install:
        _translation.install()


def gettext(message: str) -> str:
    if _translation is None:
        return message
    return _translation.gettext(message)
