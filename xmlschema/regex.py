# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module parse and translate XML regular expressions to Python.
"""
import re
from collections import MutableSet
from itertools import chain
from sys import maxunicode

from .core import PY3, unicode_type, unicode_chr
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaRegexError


I_SHORTCUT_REPLACE = (
    r":A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF"
    r"\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

C_SHORTCUT_REPLACE = (
    r"\-.0-9:A-Z_a-z\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u037D\u037F-\u1FFF\u200C-"
    r"\u200D\u203F\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

CHARACTER_BLOCKS = {
    'BasicLatin': u'\u0000-\u007F',
    'Latin-1Supplement': u'\u0080-\u00FF',
    'LatinExtended-A': u'\u0100-\u017F',
    'LatinExtended-B': u'\u0180-\u024F',
    'IPAExtensions': u'\u0250-\u02AF',
    'SpacingModifierLetters': u'\u02B0-\u02FF',
    'CombiningDiacriticalMarks': u'\u0300-\u036F',
    'Greek': u'\u0370-\u03FF',
    'Cyrillic': u'\u0400-\u04FF',
    'Armenian': u'\u0530-\u058F',
    'Hebrew': u'\u0590-\u05FF',
    'Arabic': u'\u0600-\u06FF',
    'Syriac': u'\u0700-\u074F',
    'Thaana': u'\u0780-\u07BF',
    'Devanagari': u'\u0900-\u097F',
    'Bengali': u'\u0980-\u09FF',
    'Gurmukhi': u'\u0A00-\u0A7F',
    'Gujarati': u'\u0A80-\u0AFF',
    'Oriya': u'\u0B00-\u0B7F',
    'Tamil': u'\u0B80-\u0BFF',
    'Telugu': u'\u0C00-\u0C7F',
    'Kannada': u'\u0C80-\u0CFF',
    'Malayalam': u'\u0D00-\u0D7F',
    'Sinhala': u'\u0D80-\u0DFF',
    'Thai': u'\u0E00-\u0E7F',
    'Lao': u'\u0E80-\u0EFF',
    'Tibetan': u'\u0F00-\u0FFF',
    'Myanmar': u'\u1000-\u109F',
    'Georgian': u'\u10A0-\u10FF',
    'HangulJamo': u'\u1100-\u11FF',
    'Ethiopic': u'\u1200-\u137F',
    'Cherokee': u'\u13A0-\u13FF',
    'UnifiedCanadianAboriginalSyllabics': u'\u1400-\u167F',
    'Ogham': u'\u1680-\u169F',
    'Runic': u'\u16A0-\u16FF',
    'Khmer': u'\u1780-\u17FF',
    'Mongolian': u'\u1800-\u18AF',
    'LatinExtendedAdditional': u'\u1E00-\u1EFF',
    'GreekExtended': u'\u1F00-\u1FFF',
    'GeneralPunctuation': u'\u2000-\u206F',
    'SuperscriptsandSubscripts': u'\u2070-\u209F',
    'CurrencySymbols': u'\u20A0-\u20CF',
    'CombiningMarksforSymbols': u'\u20D0-\u20FF',
    'LetterlikeSymbols': u'\u2100-\u214F',
    'NumberForms': u'\u2150-\u218F',
    'Arrows': u'\u2190-\u21FF',
    'MathematicalOperators': u'\u2200-\u22FF',
    'MiscellaneousTechnical': u'\u2300-\u23FF',
    'ControlPictures': u'\u2400-\u243F',
    'OpticalCharacterRecognition': u'\u2440-\u245F',
    'EnclosedAlphanumerics': u'\u2460-\u24FF',
    'BoxDrawing': u'\u2500-\u257F',
    'BlockElements': u'\u2580-\u259F',
    'GeometricShapes': u'\u25A0-\u25FF',
    'MiscellaneousSymbols': u'\u2600-\u26FF',
    'Dingbats': u'\u2700-\u27BF',
    'BraillePatterns': u'\u2800-\u28FF',
    'CJKRadicalsSupplement': u'\u2E80-\u2EFF',
    'KangxiRadicals': u'\u2F00-\u2FDF',
    'IdeographicDescriptionCharacters': u'\u2FF0-\u2FFF',
    'CJKSymbolsandPunctuation': u'\u3000-\u303F',
    'Hiragana': u'\u3040-\u309F',
    'Katakana': u'\u30A0-\u30FF',
    'Bopomofo': u'\u3100-\u312F',
    'HangulCompatibilityJamo': u'\u3130-\u318F',
    'Kanbun': u'\u3190-\u319F',
    'BopomofoExtended': u'\u31A0-\u31BF',
    'EnclosedCJKLettersandMonths': u'\u3200-\u32FF',
    'CJKCompatibility': u'\u3300-\u33FF',
    'CJKUnifiedIdeographsExtensionA': u'\u3400-\u4DB5',
    'CJKUnifiedIdeographs': u'\u4E00-\u9FFF',
    'YiSyllables': u'\uA000-\uA48F',
    'YiRadicals': u'\uA490-\uA4CF',
    'HangulSyllables': u'\uAC00-\uD7A3',
    'HighSurrogates': u'\uD800-\uDB7F',
    'HighPrivateUseSurrogates': u'\uDB80-\uDBFF',
    'LowSurrogates': u'\uDC00-\uDFFF',
    'PrivateUse': u'\uE000-\uF8FF\U000F0000-\U0010FFFD',
    'CJKCompatibilityIdeographs': u'\uF900-\uFAFF',
    'AlphabeticPresentationForms': u'\uFB00-\uFB4F',
    'ArabicPresentationForms-A': u'\uFB50-\uFDFF',
    'CombiningHalfMarks': u'\uFE20-\uFE2F',
    'CJKCompatibilityForms': u'\uFE30-\uFE4F',
    'SmallFormVariants': u'\uFE50-\uFE6F',
    'ArabicPresentationForms-B': u'\uFE70-\uFEFE',
    'Specials': u'\uFEFF-\uFEFF\uFFF0-\uFFFD',
    'HalfwidthandFullwidthForms': u'\uFF00-\uFFEF',
    'OldItalic': u'\U00010300-\U0001032F',
    'Gothic': u'\U00010330-\U0001034F',
    'Deseret': u'\U00010400-\U0001044F',
    'ByzantineMusicalSymbols': u'\U0001D000-\U0001D0FF',
    'MusicalSymbols': u'\U0001D100-\U0001D1FF',
    'MathematicalAlphanumericSymbols': u'\U0001D400-\U0001D7FF',
    'CJKUnifiedIdeographsExtensionB': u'\U00020000-\U0002A6D6',
    'CJKCompatibilityIdeographsSupplement': u'\U0002F800-\U0002FA1F',
    'Tags': u'\U000E0000-\U000E007F',
}


def parse_character_group(s):
    """
    Parse a regex character group part, generating a sequence that expands
    the escape sequences and the character ranges. An unescaped hyphen (-)
    that is not at the start or at the and is interpreted as range specifier.

    :param s: A string representing a character group part.
    """
    escaped = False
    string_iter = iter(range(len(s)))
    for i in string_iter:
        if i == 0:
            char = s[0]
            if char == '\\':
                escaped = True
            elif char in r'[]' and len(s) > 1:
                raise XMLSchemaRegexError("bad character %r at position 0" % char)
            else:
                yield char
        elif s[i] == '-':
            if escaped or (i == len(s) - 1):
                char = s[i]
                yield char
                escaped = False
            else:
                i = next(string_iter)
                end_char = s[i]
                if end_char == '\\' and (i < len(s) - 1) and s[i + 1] in r'-|.^?*+{}()[]':
                    i = next(string_iter)
                    end_char = s[i]
                if ord(char) > ord(end_char):
                    raise XMLSchemaRegexError(
                        "bad character range %r-%r at position %d" % (char, end_char, i - 2)
                    )
                for cp in range(ord(char) + 1, ord(end_char) + 1):
                    yield unicode_chr(cp)
        elif s[i] in r'|.^?*+{}()':
            if escaped:
                escaped = False
            char = s[i]
            yield char
        elif s[i] in r'[]':
            if not escaped and len(s) > 1:
                raise XMLSchemaRegexError("bad character %r at position %d" % (s[i], i))
            escaped = False
            char = s[i]
            yield char
        elif s[i] == '\\':
            if escaped:
                escaped = False
                char = '\\'
                yield char
            else:
                escaped = True
        else:
            if escaped:
                escaped = False
                yield '\\'
            char = s[i]
            yield char
    if escaped:
        yield '\\'


def generate_character_group(s):
    """
    Generate a character group representation of a sequence of Unicode characters.
    A duplicated character ends the generation of the group with a character range
    that reaches the maxunicode.

    :param s: An iterable with unicode characters.
    """
    def character_group_repr(cp):
        if cp > 126:
            return r'\u{:04x}'.format(cp) if cp < 0x10000 else r'\U{:08x}'.format(cp)
        char = unicode_chr(cp)
        if char in r'-|.^?*+{}()[]':
            return u'\%s' % char
        return char

    range_code_point = -1
    range_len = 1
    for code_point in sorted(s):
        if range_code_point < 0:
            range_code_point = code_point
        elif code_point == (range_code_point + range_len):
            # Next character --> range extension
            range_len += 1
        elif code_point == (range_code_point + range_len - 1):
            # Duplicated character!
            yield character_group_repr(range_code_point)
            yield u'-'
            yield character_group_repr(maxunicode)
            return
        elif range_len <= 2:
            # Ending of a range of two length.
            for k in range(range_len):
                yield character_group_repr(range_code_point + k)
            range_code_point = code_point
            range_len = 1
        else:
            # Ending of a range of three or more length.
            yield character_group_repr(range_code_point)
            yield u'-'
            yield character_group_repr(range_code_point + range_len - 1)
            range_code_point = code_point
            range_len = 1
    else:
        if range_code_point < 0:
            return
        if range_len <= 2:
            for k in range(range_len):
                yield character_group_repr(range_code_point + k)
        else:
            yield character_group_repr(range_code_point)
            yield u'-'
            yield character_group_repr(range_code_point + range_len - 1)


class UnicodeSubset(MutableSet):
    """
    A set of Unicode code points. It manages character ranges for adding or for
    discarding elements from a string and for a compressed representation.
    """
    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            raise XMLSchemaTypeError(
                '%s expected at most 1 arguments, got %d' % (self.__class__.__name__, len(args))
            )
        if kwargs:
            raise XMLSchemaTypeError(
                '%s does not take keyword arguments' % self.__class__.__name__
            )

        if not args:
            self._store = set()
        elif isinstance(args[0], (unicode_type, str)):
            self._store = set()
            self.add_string(args[0])
        elif isinstance(args[0], (list, tuple, set)):
            self._store = set()
            for item in args[0]:
                self.add(item)

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, str(self), id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join(generate_character_group(self._store))

    if PY3:
        __str__ = __unicode__

    def __contains__(self, code_point):
        return code_point in self._store

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def complement(self):
        return (cp for cp in range(maxunicode + 1) if cp not in self._store)

    def add(self, code_point):
        if 0 <= code_point <= maxunicode:
            self._store.add(code_point)
        else:
            raise XMLSchemaValueError(
                "Unicode code point must be in range [0 .. %d]: %r" % (maxunicode, code_point)
            )

    def discard(self, code_point):
        if 0 <= code_point <= maxunicode:
            self._store.discard(code_point)
        else:
            raise XMLSchemaValueError(
                "Unicode code point must be in range [0 .. %d]: %r" % (maxunicode, code_point)
            )

    def add_string(self, s):
        for char in parse_character_group(s):
            self._store.add(ord(char))

    def discard_string(self, s):
        for char in parse_character_group(s):
            self._store.discard(ord(char))


def get_unicode_categories():
    import sys
    from unicodedata import category
    from collections import defaultdict

    unicode_categories = defaultdict(list)

    for cp in range(sys.maxunicode + 1):
        unicode_categories[category(chr(cp))].append(cp)
    return unicode_categories


def get_unicode_categories2():
    import sys
    from unicodedata import category
    from collections import defaultdict

    unicode_categories = defaultdict(set)

    for cp in range(sys.maxunicode + 1):
        unicode_categories[category(chr(cp))].add(cp)

    return unicode_categories


def get_unicode_categories3():
    import sys
    from unicodedata import category
    from collections import defaultdict

    unicode_categories = defaultdict(set)

    for cp in range(sys.maxunicode + 1):
        unicode_categories[category(chr(cp))].add(cp)
    for k, v in unicode_categories.items():
        unicode_categories[k] = UnicodeSubset(v)
    return unicode_categories


def get_unicode_categories4():
    return {
        'Cc': UnicodeSubset(u'\x00-\x1f\u007f-\u009f'),
        'Cf': UnicodeSubset(
            u'\u00ad\u0600-\u0605\u061c\u06dd\u070f\u180e\u200b-\u200f'u'\u202a-\u202e'
            u'\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb\U000110bd\U0001bca0-\U0001bca3'
            u'\U0001d173-\U0001d17a\U000e0001\U000e0020-\U000e007f'
        ),
        'Cn': UnicodeSubset(
            u'\u0378\u0379\u0380-\u0383\u038b\u038d\u03a2\u0530\u0557\u0558\u0560\u0588\u058b'
            u'\u058c\u0590\u05c8-\u05cf\u05eb-\u05ef\u05f5-\u05ff\u061d\u070e\u074b\u074c'
            u'\u07b2-\u07bf\u07fb-\u07ff\u082e\u082f\u083f\u085c\u085d\u085f-\u089f\u08b5-\u08e2'
            u'\u0984\u098d\u098e\u0991\u0992\u09a9\u09b1\u09b3-\u09b5\u09ba\u09bb\u09c5\u09c6'
            u'\u09c9\u09ca\u09cf-\u09d6\u09d8-\u09db\u09de\u09e4\u09e5\u09fc-\u0a00\u0a04'
            u'\u0a0b-\u0a0e\u0a11\u0a12\u0a29\u0a31\u0a34\u0a37\u0a3a\u0a3b\u0a3d\u0a43-\u0a46'
            u'\u0a49\u0a4a\u0a4e-\u0a50\u0a52-\u0a58\u0a5d\u0a5f-\u0a65\u0a76-\u0a80\u0a84\u0a8e'
            u'\u0a92\u0aa9\u0ab1\u0ab4\u0aba\u0abb\u0ac6\u0aca\u0ace\u0acf\u0ad1-\u0adf\u0ae4'
            u'\u0ae5\u0af2-\u0af8\u0afa-\u0b00\u0b04\u0b0d\u0b0e\u0b11\u0b12\u0b29\u0b31\u0b34'
            u'\u0b3a\u0b3b\u0b45\u0b46\u0b49\u0b4a\u0b4e-\u0b55\u0b58-\u0b5b\u0b5e\u0b64\u0b65'
            u'\u0b78-\u0b81\u0b84\u0b8b-\u0b8d\u0b91\u0b96-\u0b98\u0b9b\u0b9d\u0ba0-\u0ba2'
            u'\u0ba5-\u0ba7\u0bab-\u0bad\u0bba-\u0bbd\u0bc3-\u0bc5\u0bc9\u0bce\u0bcf\u0bd1-\u0bd6'
            u'\u0bd8-\u0be5\u0bfb-\u0bff\u0c04\u0c0d\u0c11\u0c29\u0c3a-\u0c3c\u0c45\u0c49'
            u'\u0c4e-\u0c54\u0c57\u0c5b-\u0c5f\u0c64\u0c65\u0c70-\u0c77\u0c80\u0c84\u0c8d\u0c91'
            u'\u0ca9\u0cb4\u0cba\u0cbb\u0cc5\u0cc9\u0cce-\u0cd4\u0cd7-\u0cdd\u0cdf\u0ce4\u0ce5'
            u'\u0cf0\u0cf3-\u0d00\u0d04\u0d0d\u0d11\u0d3b\u0d3c\u0d45\u0d49\u0d4f-\u0d56'
            u'\u0d58-\u0d5e\u0d64\u0d65\u0d76-\u0d78\u0d80\u0d81\u0d84\u0d97-\u0d99\u0db2\u0dbc'
            u'\u0dbe\u0dbf\u0dc7-\u0dc9\u0dcb-\u0dce\u0dd5\u0dd7\u0de0-\u0de5\u0df0\u0df1'
            u'\u0df5-\u0e00\u0e3b-\u0e3e\u0e5c-\u0e80\u0e83\u0e85\u0e86\u0e89\u0e8b\u0e8c'
            u'\u0e8e-\u0e93\u0e98\u0ea0\u0ea4\u0ea6\u0ea8\u0ea9\u0eac\u0eba\u0ebe\u0ebf\u0ec5'
            u'\u0ec7\u0ece\u0ecf\u0eda\u0edb\u0ee0-\u0eff\u0f48\u0f6d-\u0f70\u0f98\u0fbd\u0fcd'
            u'\u0fdb-\u0fff\u10c6\u10c8-\u10cc\u10ce\u10cf\u1249\u124e\u124f\u1257\u1259\u125e'
            u'\u125f\u1289\u128e\u128f\u12b1\u12b6\u12b7\u12bf\u12c1\u12c6\u12c7\u12d7\u1311'
            u'\u1316\u1317\u135b\u135c\u137d-\u137f\u139a-\u139f\u13f6\u13f7\u13fe\u13ff'
            u'\u169d-\u169f\u16f9-\u16ff\u170d\u1715-\u171f\u1737-\u173f\u1754-\u175f\u176d'
            u'\u1771\u1774-\u177f\u17de\u17df\u17ea-\u17ef\u17fa-\u17ff\u180f\u181a-\u181f'
            u'\u1878-\u187f\u18ab-\u18af\u18f6-\u18ff\u191f\u192c-\u192f\u193c-\u193f\u1941-\u1943'
            u'\u196e\u196f\u1975-\u197f\u19ac-\u19af\u19ca-\u19cf\u19db-\u19dd\u1a1c\u1a1d\u1a5f'
            u'\u1a7d\u1a7e\u1a8a-\u1a8f\u1a9a-\u1a9f\u1aae\u1aaf\u1abf-\u1aff\u1b4c-\u1b4f'
            u'\u1b7d-\u1b7f\u1bf4-\u1bfb\u1c38-\u1c3a\u1c4a-\u1c4c\u1c80-\u1cbf\u1cc8-\u1ccf'
            u'\u1cf7\u1cfa-\u1cff\u1df6-\u1dfb\u1f16\u1f17\u1f1e\u1f1f\u1f46\u1f47\u1f4e\u1f4f'
            u'\u1f58\u1f5a\u1f5c\u1f5e\u1f7e\u1f7f\u1fb5\u1fc5\u1fd4\u1fd5\u1fdc\u1ff0\u1ff1'
            u'\u1ff5\u1fff\u2065\u2072\u2073\u208f\u209d-\u209f\u20bf-\u20cf\u20f1-\u20ff'
            u'\u218c-\u218f\u23fb-\u23ff\u2427-\u243f\u244b-\u245f\u2b74\u2b75\u2b96\u2b97'
            u'\u2bba-\u2bbc\u2bc9\u2bd2-\u2beb\u2bf0-\u2bff\u2c2f\u2c5f\u2cf4-\u2cf8\u2d26'
            u'\u2d28-\u2d2c\u2d2e\u2d2f\u2d68-\u2d6e\u2d71-\u2d7e\u2d97-\u2d9f\u2da7\u2daf'
            u'\u2db7\u2dbf\u2dc7\u2dcf\u2dd7\u2ddf\u2e43-\u2e7f\u2e9a\u2ef4-\u2eff\u2fd6-\u2fef'
            u'\u2ffc-\u2fff\u3040\u3097\u3098\u3100-\u3104\u312e-\u3130\u318f\u31bb-\u31bf'
            u'\u31e4-\u31ef\u321f\u32ff\u4db6-\u4dbf\u9fd6-\u9fff\ua48d-\ua48f\ua4c7-\ua4cf'
            u'\ua62c-\ua63f\ua6f8-\ua6ff\ua7ae\ua7af\ua7b8-\ua7f6\ua82c-\ua82f\ua83a-\ua83f'
            u'\ua878-\ua87f\ua8c5-\ua8cd\ua8da-\ua8df\ua8fe\ua8ff\ua954-\ua95e\ua97d-\ua97f'
            u'\ua9ce\ua9da-\ua9dd\ua9ff\uaa37-\uaa3f\uaa4e\uaa4f\uaa5a\uaa5b\uaac3-\uaada'
            u'\uaaf7-\uab00\uab07\uab08\uab0f\uab10\uab17-\uab1f\uab27\uab2f\uab66-\uab6f'
            u'\uabee\uabef\uabfa-\uabff\ud7a4-\ud7af\ud7c7-\ud7ca\ud7fc-\ud7ff\ufa6e\ufa6f'
            u'\ufada-\ufaff\ufb07-\ufb12\ufb18-\ufb1c\ufb37\ufb3d\ufb3f\ufb42\ufb45\ufbc2-\ufbd2'
            u'\ufd40-\ufd4f\ufd90\ufd91\ufdc8-\ufdef\ufdfe\ufdff\ufe1a-\ufe1f\ufe53\ufe67'
            u'\ufe6c-\ufe6f\ufe75\ufefd\ufefe\uff00\uffbf-\uffc1\uffc8\uffc9\uffd0\uffd1\uffd8'
            u'\uffd9\uffdd-\uffdf\uffe7\uffef-\ufff8\ufffe\uffff\U0001000c\U00010027\U0001003b'
            u'\U0001003e\U0001004e\U0001004f\U0001005e-\U0001007f\U000100fb-\U000100ff'
            u'\U00010103-\U00010106\U00010134-\U00010136\U0001018d-\U0001018f\U0001019c-\U0001019f'
            u'\U000101a1-\U000101cf\U000101fe-\U0001027f\U0001029d-\U0001029f\U000102d1-\U000102df'
            u'\U000102fc-\U000102ff\U00010324-\U0001032f\U0001034b-\U0001034f\U0001037b-\U0001037f'
            u'\U0001039e\U000103c4-\U000103c7\U000103d6-\U000103ff\U0001049e\U0001049f'
            u'\U000104aa-\U000104ff\U00010528-\U0001052f\U00010564-\U0001056e\U00010570-\U000105ff'
            u'\U00010737-\U0001073f\U00010756-\U0001075f\U00010768-\U000107ff\U00010806\U00010807'
            u'\U00010809\U00010836\U00010839-\U0001083b\U0001083d\U0001083e\U00010856'
            u'\U0001089f-\U000108a6\U000108b0-\U000108df\U000108f3\U000108f6-\U000108fa'
            u'\U0001091c-\U0001091e\U0001093a-\U0001093e\U00010940-\U0001097f\U000109b8-\U000109bb'
            u'\U000109d0\U000109d1\U00010a04\U00010a07-\U00010a0b\U00010a14\U00010a18'
            u'\U00010a34-\U00010a37\U00010a3b-\U00010a3e\U00010a48-\U00010a4f\U00010a59-\U00010a5f'
            u'\U00010aa0-\U00010abf\U00010ae7-\U00010aea\U00010af7-\U00010aff\U00010b36-\U00010b38'
            u'\U00010b56\U00010b57\U00010b73-\U00010b77\U00010b92-\U00010b98\U00010b9d-\U00010ba8'
            u'\U00010bb0-\U00010bff\U00010c49-\U00010c7f\U00010cb3-\U00010cbf\U00010cf3-\U00010cf9'
            u'\U00010d00-\U00010e5f\U00010e7f-\U00010fff\U0001104e-\U00011051\U00011070-\U0001107e'
            u'\U000110c2-\U000110cf\U000110e9-\U000110ef\U000110fa-\U000110ff\U00011135'
            u'\U00011144-\U0001114f\U00011177-\U0001117f\U000111ce\U000111cf\U000111e0'
            u'\U000111f5-\U000111ff\U00011212\U0001123e-\U0001127f\U00011287\U00011289\U0001128e'
            u'\U0001129e\U000112aa-\U000112af\U000112eb-\U000112ef\U000112fa-\U000112ff\U00011304'
            u'\U0001130d\U0001130e\U00011311\U00011312\U00011329\U00011331\U00011334\U0001133a'
            u'\U0001133b\U00011345\U00011346\U00011349\U0001134a\U0001134e\U0001134f'
            u'\U00011351-\U00011356\U00011358-\U0001135c\U00011364\U00011365\U0001136d-\U0001136f'
            u'\U00011375-\U0001147f\U000114c8-\U000114cf\U000114da-\U0001157f\U000115b6\U000115b7'
            u'\U000115de-\U000115ff\U00011645-\U0001164f\U0001165a-\U0001167f\U000116b8-\U000116bf'
            u'\U000116ca-\U000116ff\U0001171a-\U0001171c\U0001172c-\U0001172f\U00011740-\U0001189f'
            u'\U000118f3-\U000118fe\U00011900-\U00011abf\U00011af9-\U00011fff\U0001239a-\U000123ff'
            u'\U0001246f\U00012475-\U0001247f\U00012544-\U00012fff\U0001342f-\U000143ff'
            u'\U00014647-\U000167ff\U00016a39-\U00016a3f\U00016a5f\U00016a6a-\U00016a6d'
            u'\U00016a70-\U00016acf\U00016aee\U00016aef\U00016af6-\U00016aff\U00016b46-\U00016b4f'
            u'\U00016b5a\U00016b62\U00016b78-\U00016b7c\U00016b90-\U00016eff\U00016f45-\U00016f4f'
            u'\U00016f7f-\U00016f8e\U00016fa0-\U0001afff\U0001b002-\U0001bbff\U0001bc6b-\U0001bc6f'
            u'\U0001bc7d-\U0001bc7f\U0001bc89-\U0001bc8f\U0001bc9a\U0001bc9b\U0001bca4-\U0001cfff'
            u'\U0001d0f6-\U0001d0ff\U0001d127\U0001d128\U0001d1e9-\U0001d1ff\U0001d246-\U0001d2ff'
            u'\U0001d357-\U0001d35f\U0001d372-\U0001d3ff\U0001d455\U0001d49d\U0001d4a0\U0001d4a1'
            u'\U0001d4a3\U0001d4a4\U0001d4a7\U0001d4a8\U0001d4ad\U0001d4ba\U0001d4bc\U0001d4c4'
            u'\U0001d506\U0001d50b\U0001d50c\U0001d515\U0001d51d\U0001d53a\U0001d53f\U0001d545'
            u'\U0001d547-\U0001d549\U0001d551\U0001d6a6\U0001d6a7\U0001d7cc\U0001d7cd'
            u'\U0001da8c-\U0001da9a\U0001daa0\U0001dab0-\U0001e7ff\U0001e8c5\U0001e8c6'
            u'\U0001e8d7-\U0001edff\U0001ee04\U0001ee20\U0001ee23\U0001ee25\U0001ee26\U0001ee28'
            u'\U0001ee33\U0001ee38\U0001ee3a\U0001ee3c-\U0001ee41\U0001ee43-\U0001ee46\U0001ee48'
            u'\U0001ee4a\U0001ee4c\U0001ee50\U0001ee53\U0001ee55\U0001ee56\U0001ee58\U0001ee5a'
            u'\U0001ee5c\U0001ee5e\U0001ee60\U0001ee63\U0001ee65\U0001ee66\U0001ee6b\U0001ee73'
            u'\U0001ee78\U0001ee7d\U0001ee7f\U0001ee8a\U0001ee9c-\U0001eea0\U0001eea4\U0001eeaa'
            u'\U0001eebc-\U0001eeef\U0001eef2-\U0001efff\U0001f02c-\U0001f02f\U0001f094-\U0001f09f'
            u'\U0001f0af\U0001f0b0\U0001f0c0\U0001f0d0\U0001f0f6-\U0001f0ff\U0001f10d-\U0001f10f'
            u'\U0001f12f\U0001f16c-\U0001f16f\U0001f19b-\U0001f1e5\U0001f203-\U0001f20f'
            u'\U0001f23b-\U0001f23f\U0001f249-\U0001f24f\U0001f252-\U0001f2ff\U0001f57a\U0001f5a4'
            u'\U0001f6d1-\U0001f6df\U0001f6ed-\U0001f6ef\U0001f6f4-\U0001f6ff\U0001f774-\U0001f77f'
            u'\U0001f7d5-\U0001f7ff\U0001f80c-\U0001f80f\U0001f848-\U0001f84f\U0001f85a-\U0001f85f'
            u'\U0001f888-\U0001f88f\U0001f8ae-\U0001f90f\U0001f919-\U0001f97f\U0001f985-\U0001f9bf'
            u'\U0001f9c1-\U0001ffff\U0002a6d7-\U0002a6ff\U0002b735-\U0002b73f\U0002b81e\U0002b81f'
            u'\U0002cea2-\U0002f7ff\U0002fa1e-\U000e0000\U000e0002-\U000e001f\U000e0080-\U000e00ff'
            u'\U000e01f0-\U000effff\U000ffffe\U000fffff\U0010fffe\U0010ffff'
        ),
        'Co': UnicodeSubset(u'\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd'),
        'Cs': UnicodeSubset(u'\ud800-\udfff'),
        'Ll': UnicodeSubset(
            u'a-z\u00b5\u00df-\u00f6\u00f8-\u00ff\u0101\u0103\u0105\u0107\u0109\u010b\u010d\u010f'
            u'\u0111\u0113\u0115\u0117\u0119\u011b\u011d\u011f\u0121\u0123\u0125\u0127\u0129\u012b'
            u'\u012d\u012f\u0131\u0133\u0135\u0137\u0138\u013a\u013c\u013e\u0140\u0142\u0144\u0146'
            u'\u0148\u0149\u014b\u014d\u014f\u0151\u0153\u0155\u0157\u0159\u015b\u015d\u015f\u0161'
            u'\u0163\u0165\u0167\u0169\u016b\u016d\u016f\u0171\u0173\u0175\u0177\u017a\u017c'
            u'\u017e-\u0180\u0183\u0185\u0188\u018c\u018d\u0192\u0195\u0199-\u019b\u019e\u01a1'
            u'\u01a3\u01a5\u01a8\u01aa\u01ab\u01ad\u01b0\u01b4\u01b6\u01b9\u01ba\u01bd-\u01bf\u01c6'
            u'\u01c9\u01cc\u01ce\u01d0\u01d2\u01d4\u01d6\u01d8\u01da\u01dc\u01dd\u01df\u01e1\u01e3'
            u'\u01e5\u01e7\u01e9\u01eb\u01ed\u01ef\u01f0\u01f3\u01f5\u01f9\u01fb\u01fd\u01ff\u0201'
            u'\u0203\u0205\u0207\u0209\u020b\u020d\u020f\u0211\u0213\u0215\u0217\u0219\u021b\u021d'
            u'\u021f\u0221\u0223\u0225\u0227\u0229\u022b\u022d\u022f\u0231\u0233-\u0239\u023c\u023f'
            u'\u0240\u0242\u0247\u0249\u024b\u024d\u024f-\u0293\u0295-\u02af\u0371\u0373\u0377'
            u'\u037b-\u037d\u0390\u03ac-\u03ce\u03d0\u03d1\u03d5-\u03d7\u03d9\u03db\u03dd\u03df'
            u'\u03e1\u03e3\u03e5\u03e7\u03e9\u03eb\u03ed\u03ef-\u03f3\u03f5\u03f8\u03fb\u03fc'
            u'\u0430-\u045f\u0461\u0463\u0465\u0467\u0469\u046b\u046d\u046f\u0471\u0473\u0475\u0477'
            u'\u0479\u047b\u047d\u047f\u0481\u048b\u048d\u048f\u0491\u0493\u0495\u0497\u0499\u049b'
            u'\u049d\u049f\u04a1\u04a3\u04a5\u04a7\u04a9\u04ab\u04ad\u04af\u04b1\u04b3\u04b5\u04b7'
            u'\u04b9\u04bb\u04bd\u04bf\u04c2\u04c4\u04c6\u04c8\u04ca\u04cc\u04ce\u04cf\u04d1\u04d3'
            u'\u04d5\u04d7\u04d9\u04db\u04dd\u04df\u04e1\u04e3\u04e5\u04e7\u04e9\u04eb\u04ed\u04ef'
            u'\u04f1\u04f3\u04f5\u04f7\u04f9\u04fb\u04fd\u04ff\u0501\u0503\u0505\u0507\u0509\u050b'
            u'\u050d\u050f\u0511\u0513\u0515\u0517\u0519\u051b\u051d\u051f\u0521\u0523\u0525\u0527'
            u'\u0529\u052b\u052d\u052f\u0561-\u0587\u13f8-\u13fd\u1d00-\u1d2b\u1d6b-\u1d77\u1d79-\u1d9a'
            u'\u1e01\u1e03\u1e05\u1e07\u1e09\u1e0b\u1e0d\u1e0f\u1e11\u1e13\u1e15\u1e17\u1e19\u1e1b'
            u'\u1e1d\u1e1f\u1e21\u1e23\u1e25\u1e27\u1e29\u1e2b\u1e2d\u1e2f\u1e31\u1e33\u1e35\u1e37'
            u'\u1e39\u1e3b\u1e3d\u1e3f\u1e41\u1e43\u1e45\u1e47\u1e49\u1e4b\u1e4d\u1e4f\u1e51\u1e53'
            u'\u1e55\u1e57\u1e59\u1e5b\u1e5d\u1e5f\u1e61\u1e63\u1e65\u1e67\u1e69\u1e6b\u1e6d\u1e6f'
            u'\u1e71\u1e73\u1e75\u1e77\u1e79\u1e7b\u1e7d\u1e7f\u1e81\u1e83\u1e85\u1e87\u1e89\u1e8b'
            u'\u1e8d\u1e8f\u1e91\u1e93\u1e95-\u1e9d\u1e9f\u1ea1\u1ea3\u1ea5\u1ea7\u1ea9\u1eab\u1ead'
            u'\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7\u1eb9\u1ebb\u1ebd\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7\u1ec9'
            u'\u1ecb\u1ecd\u1ecf\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3\u1ee5'
            u'\u1ee7\u1ee9\u1eeb\u1eed\u1eef\u1ef1\u1ef3\u1ef5\u1ef7\u1ef9\u1efb\u1efd\u1eff-\u1f07'
            u'\u1f10-\u1f15\u1f20-\u1f27\u1f30-\u1f37\u1f40-\u1f45\u1f50-\u1f57\u1f60-\u1f67'
            u'\u1f70-\u1f7d\u1f80-\u1f87\u1f90-\u1f97\u1fa0-\u1fa7\u1fb0-\u1fb4\u1fb6\u1fb7\u1fbe'
            u'\u1fc2-\u1fc4\u1fc6\u1fc7\u1fd0-\u1fd3\u1fd6\u1fd7\u1fe0-\u1fe7\u1ff2-\u1ff4\u1ff6'
            u'\u1ff7\u210a\u210e\u210f\u2113\u212f\u2134\u2139\u213c\u213d\u2146-\u2149\u214e\u2184'
            u'\u2c30-\u2c5e\u2c61\u2c65\u2c66\u2c68\u2c6a\u2c6c\u2c71\u2c73\u2c74\u2c76-\u2c7b\u2c81'
            u'\u2c83\u2c85\u2c87\u2c89\u2c8b\u2c8d\u2c8f\u2c91\u2c93\u2c95\u2c97\u2c99\u2c9b\u2c9d'
            u'\u2c9f\u2ca1\u2ca3\u2ca5\u2ca7\u2ca9\u2cab\u2cad\u2caf\u2cb1\u2cb3\u2cb5\u2cb7\u2cb9'
            u'\u2cbb\u2cbd\u2cbf\u2cc1\u2cc3\u2cc5\u2cc7\u2cc9\u2ccb\u2ccd\u2ccf\u2cd1\u2cd3\u2cd5'
            u'\u2cd7\u2cd9\u2cdb\u2cdd\u2cdf\u2ce1\u2ce3\u2ce4\u2cec\u2cee\u2cf3\u2d00-\u2d25\u2d27'
            u'\u2d2d\ua641\ua643\ua645\ua647\ua649\ua64b\ua64d\ua64f\ua651\ua653\ua655\ua657\ua659'
            u'\ua65b\ua65d\ua65f\ua661\ua663\ua665\ua667\ua669\ua66b\ua66d\ua681\ua683\ua685\ua687'
            u'\ua689\ua68b\ua68d\ua68f\ua691\ua693\ua695\ua697\ua699\ua69b\ua723\ua725\ua727\ua729'
            u'\ua72b\ua72d\ua72f-\ua731\ua733\ua735\ua737\ua739\ua73b\ua73d\ua73f\ua741\ua743\ua745'
            u'\ua747\ua749\ua74b\ua74d\ua74f\ua751\ua753\ua755\ua757\ua759\ua75b\ua75d\ua75f\ua761'
            u'\ua763\ua765\ua767\ua769\ua76b\ua76d\ua76f\ua771-\ua778\ua77a\ua77c\ua77f\ua781\ua783'
            u'\ua785\ua787\ua78c\ua78e\ua791\ua793-\ua795\ua797\ua799\ua79b\ua79d\ua79f\ua7a1\ua7a3'
            u'\ua7a5\ua7a7\ua7a9\ua7b5\ua7b7\ua7fa\uab30-\uab5a\uab60-\uab65\uab70-\uabbf\ufb00-\ufb06'
            u'\ufb13-\ufb17\uff41-\uff5a\U00010428-\U0001044f\U00010cc0-\U00010cf2\U000118c0-\U000118df'
            u'\U0001d41a-\U0001d433\U0001d44e-\U0001d454\U0001d456-\U0001d467\U0001d482-\U0001d49b'
            u'\U0001d4b6-\U0001d4b9\U0001d4bb\U0001d4bd-\U0001d4c3\U0001d4c5-\U0001d4cf\U0001d4ea-\U0001d503'
            u'\U0001d51e-\U0001d537\U0001d552-\U0001d56b\U0001d586-\U0001d59f\U0001d5ba-\U0001d5d3'
            u'\U0001d5ee-\U0001d607\U0001d622-\U0001d63b\U0001d656-\U0001d66f\U0001d68a-\U0001d6a5'
            u'\U0001d6c2-\U0001d6da\U0001d6dc-\U0001d6e1\U0001d6fc-\U0001d714\U0001d716-\U0001d71b'
            u'\U0001d736-\U0001d74e\U0001d750-\U0001d755\U0001d770-\U0001d788\U0001d78a-\U0001d78f'
            u'\U0001d7aa-\U0001d7c2\U0001d7c4-\U0001d7c9\U0001d7cb'
        ),
        'Lm': UnicodeSubset(
            u'\u02b0-\u02c1\u02c6-\u02d1\u02e0-\u02e4\u02ec\u02ee\u0374\u037a\u0559\u0640\u06e5\u06e6'
            u'\u07f4\u07f5\u07fa\u081a\u0824\u0828\u0971\u0e46\u0ec6\u10fc\u17d7\u1843\u1aa7\u1c78-\u1c7d'
            u'\u1d2c-\u1d6a\u1d78\u1d9b-\u1dbf\u2071\u207f\u2090-\u209c\u2c7c\u2c7d\u2d6f\u2e2f\u3005'
            u'\u3031-\u3035\u303b\u309d\u309e\u30fc-\u30fe\ua015\ua4f8-\ua4fd\ua60c\ua67f\ua69c\ua69d'
            u'\ua717-\ua71f\ua770\ua788\ua7f8\ua7f9\ua9cf\ua9e6\uaa70\uaadd\uaaf3\uaaf4\uab5c-\uab5f'
            u'\uff70\uff9e\uff9f\U00016b40-\U00016b43\U00016f93-\U00016f9f'
        ),
        'Lo': UnicodeSubset(
            u'\u00aa\u00ba\u01bb\u01c0-\u01c3\u0294\u05d0-\u05ea\u05f0-\u05f2\u0620-\u063f\u0641-\u064a'
            u'\u066e\u066f\u0671-\u06d3\u06d5\u06ee\u06ef\u06fa-\u06fc\u06ff\u0710\u0712-\u072f'
            u'\u074d-\u07a5\u07b1\u07ca-\u07ea\u0800-\u0815\u0840-\u0858\u08a0-\u08b4\u0904-\u0939'
            u'\u093d\u0950\u0958-\u0961\u0972-\u0980\u0985-\u098c\u098f\u0990\u0993-\u09a8\u09aa-\u09b0'
            u'\u09b2\u09b6-\u09b9\u09bd\u09ce\u09dc\u09dd\u09df-\u09e1\u09f0\u09f1\u0a05-\u0a0a\u0a0f'
            u'\u0a10\u0a13-\u0a28\u0a2a-\u0a30\u0a32\u0a33\u0a35\u0a36\u0a38\u0a39\u0a59-\u0a5c\u0a5e'
            u'\u0a72-\u0a74\u0a85-\u0a8d\u0a8f-\u0a91\u0a93-\u0aa8\u0aaa-\u0ab0\u0ab2\u0ab3\u0ab5-\u0ab9'
            u'\u0abd\u0ad0\u0ae0\u0ae1\u0af9\u0b05-\u0b0c\u0b0f\u0b10\u0b13-\u0b28\u0b2a-\u0b30\u0b32'
            u'\u0b33\u0b35-\u0b39\u0b3d\u0b5c\u0b5d\u0b5f-\u0b61\u0b71\u0b83\u0b85-\u0b8a\u0b8e-\u0b90'
            u'\u0b92-\u0b95\u0b99\u0b9a\u0b9c\u0b9e\u0b9f\u0ba3\u0ba4\u0ba8-\u0baa\u0bae-\u0bb9\u0bd0'
            u'\u0c05-\u0c0c\u0c0e-\u0c10\u0c12-\u0c28\u0c2a-\u0c39\u0c3d\u0c58-\u0c5a\u0c60\u0c61'
            u'\u0c85-\u0c8c\u0c8e-\u0c90\u0c92-\u0ca8\u0caa-\u0cb3\u0cb5-\u0cb9\u0cbd\u0cde\u0ce0\u0ce1'
            u'\u0cf1\u0cf2\u0d05-\u0d0c\u0d0e-\u0d10\u0d12-\u0d3a\u0d3d\u0d4e\u0d5f-\u0d61\u0d7a-\u0d7f'
            u'\u0d85-\u0d96\u0d9a-\u0db1\u0db3-\u0dbb\u0dbd\u0dc0-\u0dc6\u0e01-\u0e30\u0e32\u0e33'
            u'\u0e40-\u0e45\u0e81\u0e82\u0e84\u0e87\u0e88\u0e8a\u0e8d\u0e94-\u0e97\u0e99-\u0e9f'
            u'\u0ea1-\u0ea3\u0ea5\u0ea7\u0eaa\u0eab\u0ead-\u0eb0\u0eb2\u0eb3\u0ebd\u0ec0-\u0ec4'
            u'\u0edc-\u0edf\u0f00\u0f40-\u0f47\u0f49-\u0f6c\u0f88-\u0f8c\u1000-\u102a\u103f\u1050-\u1055'
            u'\u105a-\u105d\u1061\u1065\u1066\u106e-\u1070\u1075-\u1081\u108e\u10d0-\u10fa\u10fd-\u1248'
            u'\u124a-\u124d\u1250-\u1256\u1258\u125a-\u125d\u1260-\u1288\u128a-\u128d\u1290-\u12b0'
            u'\u12b2-\u12b5\u12b8-\u12be\u12c0\u12c2-\u12c5\u12c8-\u12d6\u12d8-\u1310\u1312-\u1315'
            u'\u1318-\u135a\u1380-\u138f\u1401-\u166c\u166f-\u167f\u1681-\u169a\u16a0-\u16ea\u16f1-\u16f8'
            u'\u1700-\u170c\u170e-\u1711\u1720-\u1731\u1740-\u1751\u1760-\u176c\u176e-\u1770\u1780-\u17b3'
            u'\u17dc\u1820-\u1842\u1844-\u1877\u1880-\u18a8\u18aa\u18b0-\u18f5\u1900-\u191e\u1950-\u196d'
            u'\u1970-\u1974\u1980-\u19ab\u19b0-\u19c9\u1a00-\u1a16\u1a20-\u1a54\u1b05-\u1b33\u1b45-\u1b4b'
            u'\u1b83-\u1ba0\u1bae\u1baf\u1bba-\u1be5\u1c00-\u1c23\u1c4d-\u1c4f\u1c5a-\u1c77\u1ce9-\u1cec'
            u'\u1cee-\u1cf1\u1cf5\u1cf6\u2135-\u2138\u2d30-\u2d67\u2d80-\u2d96\u2da0-\u2da6\u2da8-\u2dae'
            u'\u2db0-\u2db6\u2db8-\u2dbe\u2dc0-\u2dc6\u2dc8-\u2dce\u2dd0-\u2dd6\u2dd8-\u2dde\u3006\u303c'
            u'\u3041-\u3096\u309f\u30a1-\u30fa\u30ff\u3105-\u312d\u3131-\u318e\u31a0-\u31ba\u31f0-\u31ff'
            u'\u3400-\u4db5\u4e00-\u9fd5\ua000-\ua014\ua016-\ua48c\ua4d0-\ua4f7\ua500-\ua60b\ua610-\ua61f'
            u'\ua62a\ua62b\ua66e\ua6a0-\ua6e5\ua78f\ua7f7\ua7fb-\ua801\ua803-\ua805\ua807-\ua80a'
            u'\ua80c-\ua822\ua840-\ua873\ua882-\ua8b3\ua8f2-\ua8f7\ua8fb\ua8fd\ua90a-\ua925\ua930-\ua946'
            u'\ua960-\ua97c\ua984-\ua9b2\ua9e0-\ua9e4\ua9e7-\ua9ef\ua9fa-\ua9fe\uaa00-\uaa28\uaa40-\uaa42'
            u'\uaa44-\uaa4b\uaa60-\uaa6f\uaa71-\uaa76\uaa7a\uaa7e-\uaaaf\uaab1\uaab5\uaab6\uaab9-\uaabd'
            u'\uaac0\uaac2\uaadb\uaadc\uaae0-\uaaea\uaaf2\uab01-\uab06\uab09-\uab0e\uab11-\uab16'
            u'\uab20-\uab26\uab28-\uab2e\uabc0-\uabe2\uac00-\ud7a3\ud7b0-\ud7c6\ud7cb-\ud7fb\uf900-\ufa6d'
            u'\ufa70-\ufad9\ufb1d\ufb1f-\ufb28\ufb2a-\ufb36\ufb38-\ufb3c\ufb3e\ufb40\ufb41\ufb43\ufb44'
            u'\ufb46-\ufbb1\ufbd3-\ufd3d\ufd50-\ufd8f\ufd92-\ufdc7\ufdf0-\ufdfb\ufe70-\ufe74\ufe76-\ufefc'
            u'\uff66-\uff6f\uff71-\uff9d\uffa0-\uffbe\uffc2-\uffc7\uffca-\uffcf\uffd2-\uffd7\uffda-\uffdc'
            u'\U00010000-\U0001000b\U0001000d-\U00010026\U00010028-\U0001003a\U0001003c\U0001003d'
            u'\U0001003f-\U0001004d\U00010050-\U0001005d\U00010080-\U000100fa\U00010280-\U0001029c'
            u'\U000102a0-\U000102d0\U00010300-\U0001031f\U00010330-\U00010340\U00010342-\U00010349'
            u'\U00010350-\U00010375\U00010380-\U0001039d\U000103a0-\U000103c3\U000103c8-\U000103cf'
            u'\U00010450-\U0001049d\U00010500-\U00010527\U00010530-\U00010563\U00010600-\U00010736'
            u'\U00010740-\U00010755\U00010760-\U00010767\U00010800-\U00010805\U00010808\U0001080a-\U00010835'
            u'\U00010837\U00010838\U0001083c\U0001083f-\U00010855\U00010860-\U00010876\U00010880-\U0001089e'
            u'\U000108e0-\U000108f2\U000108f4\U000108f5\U00010900-\U00010915\U00010920-\U00010939'
            u'\U00010980-\U000109b7\U000109be\U000109bf\U00010a00\U00010a10-\U00010a13\U00010a15-\U00010a17'
            u'\U00010a19-\U00010a33\U00010a60-\U00010a7c\U00010a80-\U00010a9c\U00010ac0-\U00010ac7'
            u'\U00010ac9-\U00010ae4\U00010b00-\U00010b35\U00010b40-\U00010b55\U00010b60-\U00010b72'
            u'\U00010b80-\U00010b91\U00010c00-\U00010c48\U00011003-\U00011037\U00011083-\U000110af'
            u'\U000110d0-\U000110e8\U00011103-\U00011126\U00011150-\U00011172\U00011176\U00011183-\U000111b2'
            u'\U000111c1-\U000111c4\U000111da\U000111dc\U00011200-\U00011211\U00011213-\U0001122b'
            u'\U00011280-\U00011286\U00011288\U0001128a-\U0001128d\U0001128f-\U0001129d\U0001129f-\U000112a8'
            u'\U000112b0-\U000112de\U00011305-\U0001130c\U0001130f\U00011310\U00011313-\U00011328'
            u'\U0001132a-\U00011330\U00011332\U00011333\U00011335-\U00011339\U0001133d\U00011350'
            u'\U0001135d-\U00011361\U00011480-\U000114af\U000114c4\U000114c5\U000114c7\U00011580-\U000115ae'
            u'\U000115d8-\U000115db\U00011600-\U0001162f\U00011644\U00011680-\U000116aa\U00011700-\U00011719'
            u'\U000118ff\U00011ac0-\U00011af8\U00012000-\U00012399\U00012480-\U00012543\U00013000-\U0001342e'
            u'\U00014400-\U00014646\U00016800-\U00016a38\U00016a40-\U00016a5e\U00016ad0-\U00016aed'
            u'\U00016b00-\U00016b2f\U00016b63-\U00016b77\U00016b7d-\U00016b8f\U00016f00-\U00016f44\U00016f50'
            u'\U0001b000\U0001b001\U0001bc00-\U0001bc6a\U0001bc70-\U0001bc7c\U0001bc80-\U0001bc88'
            u'\U0001bc90-\U0001bc99\U0001e800-\U0001e8c4\U0001ee00-\U0001ee03\U0001ee05-\U0001ee1f\U0001ee21'
            u'\U0001ee22\U0001ee24\U0001ee27\U0001ee29-\U0001ee32\U0001ee34-\U0001ee37\U0001ee39\U0001ee3b'
            u'\U0001ee42\U0001ee47\U0001ee49\U0001ee4b\U0001ee4d-\U0001ee4f\U0001ee51\U0001ee52\U0001ee54'
            u'\U0001ee57\U0001ee59\U0001ee5b\U0001ee5d\U0001ee5f\U0001ee61\U0001ee62\U0001ee64'
            u'\U0001ee67-\U0001ee6a\U0001ee6c-\U0001ee72\U0001ee74-\U0001ee77\U0001ee79-\U0001ee7c\U0001ee7e'
            u'\U0001ee80-\U0001ee89\U0001ee8b-\U0001ee9b\U0001eea1-\U0001eea3\U0001eea5-\U0001eea9'
            u'\U0001eeab-\U0001eebb\U00020000-\U0002a6d6\U0002a700-\U0002b734\U0002b740-\U0002b81d'
            u'\U0002b820-\U0002cea1\U0002f800-\U0002fa1d'
        ),
        'Lt': UnicodeSubset(u'\u01c5\u01c8\u01cb\u01f2\u1f88-\u1f8f\u1f98-\u1f9f\u1fa8-\u1faf\u1fbc\u1fcc\u1ffc'),
        'Lu': UnicodeSubset(
            u'A-Z\u00c0-\u00d6\u00d8-\u00de\u0100\u0102\u0104\u0106\u0108\u010a\u010c\u010e\u0110\u0112'
            u'\u0114\u0116\u0118\u011a\u011c\u011e\u0120\u0122\u0124\u0126\u0128\u012a\u012c\u012e\u0130'
            u'\u0132\u0134\u0136\u0139\u013b\u013d\u013f\u0141\u0143\u0145\u0147\u014a\u014c\u014e\u0150'
            u'\u0152\u0154\u0156\u0158\u015a\u015c\u015e\u0160\u0162\u0164\u0166\u0168\u016a\u016c\u016e'
            u'\u0170\u0172\u0174\u0176\u0178\u0179\u017b\u017d\u0181\u0182\u0184\u0186\u0187\u0189-\u018b'
            u'\u018e-\u0191\u0193\u0194\u0196-\u0198\u019c\u019d\u019f\u01a0\u01a2\u01a4\u01a6\u01a7'
            u'\u01a9\u01ac\u01ae\u01af\u01b1-\u01b3\u01b5\u01b7\u01b8\u01bc\u01c4\u01c7\u01ca\u01cd'
            u'\u01cf\u01d1\u01d3\u01d5\u01d7\u01d9\u01db\u01de\u01e0\u01e2\u01e4\u01e6\u01e8\u01ea\u01ec'
            u'\u01ee\u01f1\u01f4\u01f6-\u01f8\u01fa\u01fc\u01fe\u0200\u0202\u0204\u0206\u0208\u020a\u020c'
            u'\u020e\u0210\u0212\u0214\u0216\u0218\u021a\u021c\u021e\u0220\u0222\u0224\u0226\u0228\u022a'
            u'\u022c\u022e\u0230\u0232\u023a\u023b\u023d\u023e\u0241\u0243-\u0246\u0248\u024a\u024c\u024e'
            u'\u0370\u0372\u0376\u037f\u0386\u0388-\u038a\u038c\u038e\u038f\u0391-\u03a1\u03a3-\u03ab'
            u'\u03cf\u03d2-\u03d4\u03d8\u03da\u03dc\u03de\u03e0\u03e2\u03e4\u03e6\u03e8\u03ea\u03ec\u03ee'
            u'\u03f4\u03f7\u03f9\u03fa\u03fd-\u042f\u0460\u0462\u0464\u0466\u0468\u046a\u046c\u046e\u0470'
            u'\u0472\u0474\u0476\u0478\u047a\u047c\u047e\u0480\u048a\u048c\u048e\u0490\u0492\u0494\u0496'
            u'\u0498\u049a\u049c\u049e\u04a0\u04a2\u04a4\u04a6\u04a8\u04aa\u04ac\u04ae\u04b0\u04b2\u04b4'
            u'\u04b6\u04b8\u04ba\u04bc\u04be\u04c0\u04c1\u04c3\u04c5\u04c7\u04c9\u04cb\u04cd\u04d0\u04d2'
            u'\u04d4\u04d6\u04d8\u04da\u04dc\u04de\u04e0\u04e2\u04e4\u04e6\u04e8\u04ea\u04ec\u04ee\u04f0'
            u'\u04f2\u04f4\u04f6\u04f8\u04fa\u04fc\u04fe\u0500\u0502\u0504\u0506\u0508\u050a\u050c\u050e'
            u'\u0510\u0512\u0514\u0516\u0518\u051a\u051c\u051e\u0520\u0522\u0524\u0526\u0528\u052a\u052c'
            u'\u052e\u0531-\u0556\u10a0-\u10c5\u10c7\u10cd\u13a0-\u13f5\u1e00\u1e02\u1e04\u1e06\u1e08'
            u'\u1e0a\u1e0c\u1e0e\u1e10\u1e12\u1e14\u1e16\u1e18\u1e1a\u1e1c\u1e1e\u1e20\u1e22\u1e24\u1e26'
            u'\u1e28\u1e2a\u1e2c\u1e2e\u1e30\u1e32\u1e34\u1e36\u1e38\u1e3a\u1e3c\u1e3e\u1e40\u1e42\u1e44'
            u'\u1e46\u1e48\u1e4a\u1e4c\u1e4e\u1e50\u1e52\u1e54\u1e56\u1e58\u1e5a\u1e5c\u1e5e\u1e60\u1e62'
            u'\u1e64\u1e66\u1e68\u1e6a\u1e6c\u1e6e\u1e70\u1e72\u1e74\u1e76\u1e78\u1e7a\u1e7c\u1e7e\u1e80'
            u'\u1e82\u1e84\u1e86\u1e88\u1e8a\u1e8c\u1e8e\u1e90\u1e92\u1e94\u1e9e\u1ea0\u1ea2\u1ea4\u1ea6'
            u'\u1ea8\u1eaa\u1eac\u1eae\u1eb0\u1eb2\u1eb4\u1eb6\u1eb8\u1eba\u1ebc\u1ebe\u1ec0\u1ec2\u1ec4'
            u'\u1ec6\u1ec8\u1eca\u1ecc\u1ece\u1ed0\u1ed2\u1ed4\u1ed6\u1ed8\u1eda\u1edc\u1ede\u1ee0\u1ee2'
            u'\u1ee4\u1ee6\u1ee8\u1eea\u1eec\u1eee\u1ef0\u1ef2\u1ef4\u1ef6\u1ef8\u1efa\u1efc\u1efe'
            u'\u1f08-\u1f0f\u1f18-\u1f1d\u1f28-\u1f2f\u1f38-\u1f3f\u1f48-\u1f4d\u1f59\u1f5b\u1f5d\u1f5f'
            u'\u1f68-\u1f6f\u1fb8-\u1fbb\u1fc8-\u1fcb\u1fd8-\u1fdb\u1fe8-\u1fec\u1ff8-\u1ffb\u2102\u2107'
            u'\u210b-\u210d\u2110-\u2112\u2115\u2119-\u211d\u2124\u2126\u2128\u212a-\u212d\u2130-\u2133'
            u'\u213e\u213f\u2145\u2183\u2c00-\u2c2e\u2c60\u2c62-\u2c64\u2c67\u2c69\u2c6b\u2c6d-\u2c70'
            u'\u2c72\u2c75\u2c7e-\u2c80\u2c82\u2c84\u2c86\u2c88\u2c8a\u2c8c\u2c8e\u2c90\u2c92\u2c94'
            u'\u2c96\u2c98\u2c9a\u2c9c\u2c9e\u2ca0\u2ca2\u2ca4\u2ca6\u2ca8\u2caa\u2cac\u2cae\u2cb0\u2cb2'
            u'\u2cb4\u2cb6\u2cb8\u2cba\u2cbc\u2cbe\u2cc0\u2cc2\u2cc4\u2cc6\u2cc8\u2cca\u2ccc\u2cce\u2cd0'
            u'\u2cd2\u2cd4\u2cd6\u2cd8\u2cda\u2cdc\u2cde\u2ce0\u2ce2\u2ceb\u2ced\u2cf2\ua640\ua642\ua644'
            u'\ua646\ua648\ua64a\ua64c\ua64e\ua650\ua652\ua654\ua656\ua658\ua65a\ua65c\ua65e\ua660\ua662'
            u'\ua664\ua666\ua668\ua66a\ua66c\ua680\ua682\ua684\ua686\ua688\ua68a\ua68c\ua68e\ua690\ua692'
            u'\ua694\ua696\ua698\ua69a\ua722\ua724\ua726\ua728\ua72a\ua72c\ua72e\ua732\ua734\ua736\ua738'
            u'\ua73a\ua73c\ua73e\ua740\ua742\ua744\ua746\ua748\ua74a\ua74c\ua74e\ua750\ua752\ua754\ua756'
            u'\ua758\ua75a\ua75c\ua75e\ua760\ua762\ua764\ua766\ua768\ua76a\ua76c\ua76e\ua779\ua77b\ua77d'
            u'\ua77e\ua780\ua782\ua784\ua786\ua78b\ua78d\ua790\ua792\ua796\ua798\ua79a\ua79c\ua79e\ua7a0'
            u'\ua7a2\ua7a4\ua7a6\ua7a8\ua7aa-\ua7ad\ua7b0-\ua7b4\ua7b6\uff21-\uff3a\U00010400-\U00010427'
            u'\U00010c80-\U00010cb2\U000118a0-\U000118bf\U0001d400-\U0001d419\U0001d434-\U0001d44d'
            u'\U0001d468-\U0001d481\U0001d49c\U0001d49e\U0001d49f\U0001d4a2\U0001d4a5\U0001d4a6'
            u'\U0001d4a9-\U0001d4ac\U0001d4ae-\U0001d4b5\U0001d4d0-\U0001d4e9\U0001d504\U0001d505'
            u'\U0001d507-\U0001d50a\U0001d50d-\U0001d514\U0001d516-\U0001d51c\U0001d538\U0001d539'
            u'\U0001d53b-\U0001d53e\U0001d540-\U0001d544\U0001d546\U0001d54a-\U0001d550\U0001d56c-\U0001d585'
            u'\U0001d5a0-\U0001d5b9\U0001d5d4-\U0001d5ed\U0001d608-\U0001d621\U0001d63c-\U0001d655'
            u'\U0001d670-\U0001d689\U0001d6a8-\U0001d6c0\U0001d6e2-\U0001d6fa\U0001d71c-\U0001d734'
            u'\U0001d756-\U0001d76e\U0001d790-\U0001d7a8\U0001d7ca'
        ),
        'Mc': UnicodeSubset(
            u'\u0903\u093b\u093e-\u0940\u0949-\u094c\u094e\u094f\u0982\u0983\u09be-\u09c0\u09c7\u09c8'
            u'\u09cb\u09cc\u09d7\u0a03\u0a3e-\u0a40\u0a83\u0abe-\u0ac0\u0ac9\u0acb\u0acc\u0b02\u0b03'
            u'\u0b3e\u0b40\u0b47\u0b48\u0b4b\u0b4c\u0b57\u0bbe\u0bbf\u0bc1\u0bc2\u0bc6-\u0bc8'
            u'\u0bca-\u0bcc\u0bd7\u0c01-\u0c03\u0c41-\u0c44\u0c82\u0c83\u0cbe\u0cc0-\u0cc4\u0cc7\u0cc8'
            u'\u0cca\u0ccb\u0cd5\u0cd6\u0d02\u0d03\u0d3e-\u0d40\u0d46-\u0d48\u0d4a-\u0d4c\u0d57\u0d82'
            u'\u0d83\u0dcf-\u0dd1\u0dd8-\u0ddf\u0df2\u0df3\u0f3e\u0f3f\u0f7f\u102b\u102c\u1031\u1038'
            u'\u103b\u103c\u1056\u1057\u1062-\u1064\u1067-\u106d\u1083\u1084\u1087-\u108c\u108f'
            u'\u109a-\u109c\u17b6\u17be-\u17c5\u17c7\u17c8\u1923-\u1926\u1929-\u192b\u1930\u1931'
            u'\u1933-\u1938\u1a19\u1a1a\u1a55\u1a57\u1a61\u1a63\u1a64\u1a6d-\u1a72\u1b04\u1b35\u1b3b'
            u'\u1b3d-\u1b41\u1b43\u1b44\u1b82\u1ba1\u1ba6\u1ba7\u1baa\u1be7\u1bea-\u1bec\u1bee\u1bf2'
            u'\u1bf3\u1c24-\u1c2b\u1c34\u1c35\u1ce1\u1cf2\u1cf3\u302e\u302f\ua823\ua824\ua827\ua880'
            u'\ua881\ua8b4-\ua8c3\ua952\ua953\ua983\ua9b4\ua9b5\ua9ba\ua9bb\ua9bd-\ua9c0\uaa2f\uaa30'
            u'\uaa33\uaa34\uaa4d\uaa7b\uaa7d\uaaeb\uaaee\uaaef\uaaf5\uabe3\uabe4\uabe6\uabe7\uabe9'
            u'\uabea\uabec\U00011000\U00011002\U00011082\U000110b0-\U000110b2\U000110b7\U000110b8'
            u'\U0001112c\U00011182\U000111b3-\U000111b5\U000111bf\U000111c0\U0001122c-\U0001122e'
            u'\U00011232\U00011233\U00011235\U000112e0-\U000112e2\U00011302\U00011303\U0001133e'
            u'\U0001133f\U00011341-\U00011344\U00011347\U00011348\U0001134b-\U0001134d\U00011357'
            u'\U00011362\U00011363\U000114b0-\U000114b2\U000114b9\U000114bb-\U000114be\U000114c1'
            u'\U000115af-\U000115b1\U000115b8-\U000115bb\U000115be\U00011630-\U00011632\U0001163b'
            u'\U0001163c\U0001163e\U000116ac\U000116ae\U000116af\U000116b6\U00011720\U00011721'
            u'\U00011726\U00016f51-\U00016f7e\U0001d165\U0001d166\U0001d16d-\U0001d172'
        ),
        'Me': UnicodeSubset(u'\u0488\u0489\u1abe\u20dd-\u20e0\u20e2-\u20e4\ua670-\ua672'),
        'Mn': UnicodeSubset(
            u'\u0300-\u036f\u0483-\u0487\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u0610-\u061a'
            u'\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e4\u06e7\u06e8\u06ea-\u06ed\u0711\u0730-\u074a'
            u'\u07a6-\u07b0\u07eb-\u07f3\u0816-\u0819\u081b-\u0823\u0825-\u0827\u0829-\u082d\u0859-\u085b'
            u'\u08e3-\u0902\u093a\u093c\u0941-\u0948\u094d\u0951-\u0957\u0962\u0963\u0981\u09bc'
            u'\u09c1-\u09c4\u09cd\u09e2\u09e3\u0a01\u0a02\u0a3c\u0a41\u0a42\u0a47\u0a48\u0a4b-\u0a4d'
            u'\u0a51\u0a70\u0a71\u0a75\u0a81\u0a82\u0abc\u0ac1-\u0ac5\u0ac7\u0ac8\u0acd\u0ae2\u0ae3'
            u'\u0b01\u0b3c\u0b3f\u0b41-\u0b44\u0b4d\u0b56\u0b62\u0b63\u0b82\u0bc0\u0bcd\u0c00\u0c3e-\u0c40'
            u'\u0c46-\u0c48\u0c4a-\u0c4d\u0c55\u0c56\u0c62\u0c63\u0c81\u0cbc\u0cbf\u0cc6\u0ccc\u0ccd\u0ce2'
            u'\u0ce3\u0d01\u0d41-\u0d44\u0d4d\u0d62\u0d63\u0dca\u0dd2-\u0dd4\u0dd6\u0e31\u0e34-\u0e3a'
            u'\u0e47-\u0e4e\u0eb1\u0eb4-\u0eb9\u0ebb\u0ebc\u0ec8-\u0ecd\u0f18\u0f19\u0f35\u0f37\u0f39'
            u'\u0f71-\u0f7e\u0f80-\u0f84\u0f86\u0f87\u0f8d-\u0f97\u0f99-\u0fbc\u0fc6\u102d-\u1030'
            u'\u1032-\u1037\u1039\u103a\u103d\u103e\u1058\u1059\u105e-\u1060\u1071-\u1074\u1082\u1085'
            u'\u1086\u108d\u109d\u135d-\u135f\u1712-\u1714\u1732-\u1734\u1752\u1753\u1772\u1773\u17b4'
            u'\u17b5\u17b7-\u17bd\u17c6\u17c9-\u17d3\u17dd\u180b-\u180d\u18a9\u1920-\u1922\u1927\u1928'
            u'\u1932\u1939-\u193b\u1a17\u1a18\u1a1b\u1a56\u1a58-\u1a5e\u1a60\u1a62\u1a65-\u1a6c'
            u'\u1a73-\u1a7c\u1a7f\u1ab0-\u1abd\u1b00-\u1b03\u1b34\u1b36-\u1b3a\u1b3c\u1b42\u1b6b-\u1b73'
            u'\u1b80\u1b81\u1ba2-\u1ba5\u1ba8\u1ba9\u1bab-\u1bad\u1be6\u1be8\u1be9\u1bed\u1bef-\u1bf1'
            u'\u1c2c-\u1c33\u1c36\u1c37\u1cd0-\u1cd2\u1cd4-\u1ce0\u1ce2-\u1ce8\u1ced\u1cf4\u1cf8\u1cf9'
            u'\u1dc0-\u1df5\u1dfc-\u1dff\u20d0-\u20dc\u20e1\u20e5-\u20f0\u2cef-\u2cf1\u2d7f\u2de0-\u2dff'
            u'\u302a-\u302d\u3099\u309a\ua66f\ua674-\ua67d\ua69e\ua69f\ua6f0\ua6f1\ua802\ua806\ua80b\ua825'
            u'\ua826\ua8c4\ua8e0-\ua8f1\ua926-\ua92d\ua947-\ua951\ua980-\ua982\ua9b3\ua9b6-\ua9b9\ua9bc'
            u'\ua9e5\uaa29-\uaa2e\uaa31\uaa32\uaa35\uaa36\uaa43\uaa4c\uaa7c\uaab0\uaab2-\uaab4\uaab7\uaab8'
            u'\uaabe\uaabf\uaac1\uaaec\uaaed\uaaf6\uabe5\uabe8\uabed\ufb1e\ufe00-\ufe0f\ufe20-\ufe2f'
            u'\U000101fd\U000102e0\U00010376-\U0001037a\U00010a01-\U00010a03\U00010a05\U00010a06'
            u'\U00010a0c-\U00010a0f\U00010a38-\U00010a3a\U00010a3f\U00010ae5\U00010ae6\U00011001'
            u'\U00011038-\U00011046\U0001107f-\U00011081\U000110b3-\U000110b6\U000110b9\U000110ba'
            u'\U00011100-\U00011102\U00011127-\U0001112b\U0001112d-\U00011134\U00011173\U00011180'
            u'\U00011181\U000111b6-\U000111be\U000111ca-\U000111cc\U0001122f-\U00011231\U00011234'
            u'\U00011236\U00011237\U000112df\U000112e3-\U000112ea\U00011300\U00011301\U0001133c\U00011340'
            u'\U00011366-\U0001136c\U00011370-\U00011374\U000114b3-\U000114b8\U000114ba\U000114bf'
            u'\U000114c0\U000114c2\U000114c3\U000115b2-\U000115b5\U000115bc\U000115bd\U000115bf\U000115c0'
            u'\U000115dc\U000115dd\U00011633-\U0001163a\U0001163d\U0001163f\U00011640\U000116ab\U000116ad'
            u'\U000116b0-\U000116b5\U000116b7\U0001171d-\U0001171f\U00011722-\U00011725\U00011727-\U0001172b'
            u'\U00016af0-\U00016af4\U00016b30-\U00016b36\U00016f8f-\U00016f92\U0001bc9d\U0001bc9e'
            u'\U0001d167-\U0001d169\U0001d17b-\U0001d182\U0001d185-\U0001d18b\U0001d1aa-\U0001d1ad'
            u'\U0001d242-\U0001d244\U0001da00-\U0001da36\U0001da3b-\U0001da6c\U0001da75\U0001da84'
            u'\U0001da9b-\U0001da9f\U0001daa1-\U0001daaf\U0001e8d0-\U0001e8d6\U000e0100-\U000e01ef'
        ),
        'Nd': UnicodeSubset(
            u'0-9\u0660-\u0669\u06f0-\u06f9\u07c0-\u07c9\u0966-\u096f\u09e6-\u09ef\u0a66-\u0a6f'
            u'\u0ae6-\u0aef\u0b66-\u0b6f\u0be6-\u0bef\u0c66-\u0c6f\u0ce6-\u0cef\u0d66-\u0d6f'
            u'\u0de6-\u0def\u0e50-\u0e59\u0ed0-\u0ed9\u0f20-\u0f29\u1040-\u1049\u1090-\u1099'
            u'\u17e0-\u17e9\u1810-\u1819\u1946-\u194f\u19d0-\u19d9\u1a80-\u1a89\u1a90-\u1a99'
            u'\u1b50-\u1b59\u1bb0-\u1bb9\u1c40-\u1c49\u1c50-\u1c59\ua620-\ua629\ua8d0-\ua8d9'
            u'\ua900-\ua909\ua9d0-\ua9d9\ua9f0-\ua9f9\uaa50-\uaa59\uabf0-\uabf9\uff10-\uff19'
            u'\U000104a0-\U000104a9\U00011066-\U0001106f\U000110f0-\U000110f9\U00011136-\U0001113f'
            u'\U000111d0-\U000111d9\U000112f0-\U000112f9\U000114d0-\U000114d9\U00011650-\U00011659'
            u'\U000116c0-\U000116c9\U00011730-\U00011739\U000118e0-\U000118e9\U00016a60-\U00016a69'
            u'\U00016b50-\U00016b59\U0001d7ce-\U0001d7ff'
        ),
        'Nl': UnicodeSubset(
            u'\u16ee-\u16f0\u2160-\u2182\u2185-\u2188\u3007\u3021-\u3029\u3038-\u303a\ua6e6-\ua6ef'
            u'\U00010140-\U00010174\U00010341\U0001034a\U000103d1-\U000103d5\U00012400-\U0001246e'
        ),
        'No': UnicodeSubset(
            u'\u00b2\u00b3\u00b9\u00bc-\u00be\u09f4-\u09f9\u0b72-\u0b77\u0bf0-\u0bf2\u0c78-\u0c7e'
            u'\u0d70-\u0d75\u0f2a-\u0f33\u1369-\u137c\u17f0-\u17f9\u19da\u2070\u2074-\u2079\u2080-\u2089'
            u'\u2150-\u215f\u2189\u2460-\u249b\u24ea-\u24ff\u2776-\u2793\u2cfd\u3192-\u3195\u3220-\u3229'
            u'\u3248-\u324f\u3251-\u325f\u3280-\u3289\u32b1-\u32bf\ua830-\ua835\U00010107-\U00010133'
            u'\U00010175-\U00010178\U0001018a\U0001018b\U000102e1-\U000102fb\U00010320-\U00010323'
            u'\U00010858-\U0001085f\U00010879-\U0001087f\U000108a7-\U000108af\U000108fb-\U000108ff'
            u'\U00010916-\U0001091b\U000109bc\U000109bd\U000109c0-\U000109cf\U000109d2-\U000109ff'
            u'\U00010a40-\U00010a47\U00010a7d\U00010a7e\U00010a9d-\U00010a9f\U00010aeb-\U00010aef'
            u'\U00010b58-\U00010b5f\U00010b78-\U00010b7f\U00010ba9-\U00010baf\U00010cfa-\U00010cff'
            u'\U00010e60-\U00010e7e\U00011052-\U00011065\U000111e1-\U000111f4\U0001173a\U0001173b'
            u'\U000118ea-\U000118f2\U00016b5b-\U00016b61\U0001d360-\U0001d371\U0001e8c7-\U0001e8cf'
            u'\U0001f100-\U0001f10c'
        ),
        'Pc': UnicodeSubset(u'_\u203f\u2040\u2054\ufe33\ufe34\ufe4d-\ufe4f\uff3f'),
        'Pd': UnicodeSubset(
            u'\\-\u058a\u05be\u1400\u1806\u2010-\u2015\u2e17\u2e1a\u2e3a\u2e3b\u2e40\u301c\u3030'
            u'\u30a0\ufe31\ufe32\ufe58\ufe63\uff0d'
        ),
        'Pe': UnicodeSubset(
            u'\\)\\]\\}\u0f3b\u0f3d\u169c\u2046\u207e\u208e\u2309\u230b\u232a\u2769\u276b\u276d\u276f'
            u'\u2771\u2773\u2775\u27c6\u27e7\u27e9\u27eb\u27ed\u27ef\u2984\u2986\u2988\u298a\u298c'
            u'\u298e\u2990\u2992\u2994\u2996\u2998\u29d9\u29db\u29fd\u2e23\u2e25\u2e27\u2e29\u3009'
            u'\u300b\u300d\u300f\u3011\u3015\u3017\u3019\u301b\u301e\u301f\ufd3e\ufe18\ufe36\ufe38'
            u'\ufe3a\ufe3c\ufe3e\ufe40\ufe42\ufe44\ufe48\ufe5a\ufe5c\ufe5e\uff09\uff3d\uff5d\uff60\uff63'
        ),
        'Pf': UnicodeSubset(u'\u00bb\u2019\u201d\u203a\u2e03\u2e05\u2e0a\u2e0d\u2e1d\u2e21'),
        'Pi': UnicodeSubset(u'\u00ab\u2018\u201b\u201c\u201f\u2039\u2e02\u2e04\u2e09\u2e0c\u2e1c\u2e20'),
        'Po': UnicodeSubset(
            u"!-#%-'\\*,\\./:;\\?@\\\u00a1\u00a7\u00b6\u00b7\u00bf\u037e\u0387\u055a-\u055f\u0589\u05c0"
            u"\u05c3\u05c6\u05f3\u05f4\u0609\u060a\u060c\u060d\u061b\u061e\u061f\u066a-\u066d\u06d4"
            u"\u0700-\u070d\u07f7-\u07f9\u0830-\u083e\u085e\u0964\u0965\u0970\u0af0\u0df4\u0e4f\u0e5a"
            u"\u0e5b\u0f04-\u0f12\u0f14\u0f85\u0fd0-\u0fd4\u0fd9\u0fda\u104a-\u104f\u10fb\u1360-\u1368"
            u"\u166d\u166e\u16eb-\u16ed\u1735\u1736\u17d4-\u17d6\u17d8-\u17da\u1800-\u1805\u1807-\u180a"
            u"\u1944\u1945\u1a1e\u1a1f\u1aa0-\u1aa6\u1aa8-\u1aad\u1b5a-\u1b60\u1bfc-\u1bff\u1c3b-\u1c3f"
            u"\u1c7e\u1c7f\u1cc0-\u1cc7\u1cd3\u2016\u2017\u2020-\u2027\u2030-\u2038\u203b-\u203e"
            u"\u2041-\u2043\u2047-\u2051\u2053\u2055-\u205e\u2cf9-\u2cfc\u2cfe\u2cff\u2d70\u2e00\u2e01"
            u"\u2e06-\u2e08\u2e0b\u2e0e-\u2e16\u2e18\u2e19\u2e1b\u2e1e\u2e1f\u2e2a-\u2e2e\u2e30-\u2e39"
            u"\u2e3c-\u2e3f\u2e41\u3001-\u3003\u303d\u30fb\ua4fe\ua4ff\ua60d-\ua60f\ua673\ua67e"
            u"\ua6f2-\ua6f7\ua874-\ua877\ua8ce\ua8cf\ua8f8-\ua8fa\ua8fc\ua92e\ua92f\ua95f\ua9c1-\ua9cd"
            u"\ua9de\ua9df\uaa5c-\uaa5f\uaade\uaadf\uaaf0\uaaf1\uabeb\ufe10-\ufe16\ufe19\ufe30\ufe45"
            u"\ufe46\ufe49-\ufe4c\ufe50-\ufe52\ufe54-\ufe57\ufe5f-\ufe61\ufe68\ufe6a\ufe6b\uff01-\uff03"
            u"\uff05-\uff07\uff0a\uff0c\uff0e\uff0f\uff1a\uff1b\uff1f\uff20\uff3c\uff61\uff64\uff65"
            u"\U00010100-\U00010102\U0001039f\U000103d0\U0001056f\U00010857\U0001091f\U0001093f"
            u"\U00010a50-\U00010a58\U00010a7f\U00010af0-\U00010af6\U00010b39-\U00010b3f"
            u"\U00010b99-\U00010b9c\U00011047-\U0001104d\U000110bb\U000110bc\U000110be-\U000110c1"
            u"\U00011140-\U00011143\U00011174\U00011175\U000111c5-\U000111c9\U000111cd\U000111db"
            u"\U000111dd-\U000111df\U00011238-\U0001123d\U000112a9\U000114c6\U000115c1-\U000115d7"
            u"\U00011641-\U00011643\U0001173c-\U0001173e\U00012470-\U00012474\U00016a6e\U00016a6f"
            u"\U00016af5\U00016b37-\U00016b3b\U00016b44\U0001bc9f\U0001da87-\U0001da8b"
        ),
        'Ps': UnicodeSubset(
            u'\\(\\[\\{\u0f3a\u0f3c\u169b\u201a\u201e\u2045\u207d\u208d\u2308\u230a\u2329\u2768\u276a'
            u'\u276c\u276e\u2770\u2772\u2774\u27c5\u27e6\u27e8\u27ea\u27ec\u27ee\u2983\u2985\u2987\u2989'
            u'\u298b\u298d\u298f\u2991\u2993\u2995\u2997\u29d8\u29da\u29fc\u2e22\u2e24\u2e26\u2e28\u2e42'
            u'\u3008\u300a\u300c\u300e\u3010\u3014\u3016\u3018\u301a\u301d\ufd3f\ufe17\ufe35\ufe37\ufe39'
            u'\ufe3b\ufe3d\ufe3f\ufe41\ufe43\ufe47\ufe59\ufe5b\ufe5d\uff08\uff3b\uff5b\uff5f\uff62'
        ),
        'Sc': UnicodeSubset(
            u'$\u00a2-\u00a5\u058f\u060b\u09f2\u09f3\u09fb\u0af1\u0bf9\u0e3f\u17db\u20a0-\u20be'
            u'\ua838\ufdfc\ufe69\uff04\uffe0\uffe1\uffe5\uffe6'
        ),
        'Sk': UnicodeSubset(
            u'\\^`\u00a8\u00af\u00b4\u00b8\u02c2-\u02c5\u02d2-\u02df\u02e5-\u02eb\u02ed\u02ef-\u02ff\u0375'
            u'\u0384\u0385\u1fbd\u1fbf-\u1fc1\u1fcd-\u1fcf\u1fdd-\u1fdf\u1fed-\u1fef\u1ffd\u1ffe\u309b\u309c'
            u'\ua700-\ua716\ua720\ua721\ua789\ua78a\uab5b\ufbb2-\ufbc1\uff3e\uff40\uffe3\U0001f3fb-\U0001f3ff'
        ),
        'Sm': UnicodeSubset(
            u'\\+<->\\|~\u00ac\u00b1\u00d7\u00f7\u03f6\u0606-\u0608\u2044\u2052\u207a-\u207c\u208a-\u208c'
            u'\u2118\u2140-\u2144\u214b\u2190-\u2194\u219a\u219b\u21a0\u21a3\u21a6\u21ae\u21ce\u21cf\u21d2'
            u'\u21d4\u21f4-\u22ff\u2320\u2321\u237c\u239b-\u23b3\u23dc-\u23e1\u25b7\u25c1\u25f8-\u25ff\u266f'
            u'\u27c0-\u27c4\u27c7-\u27e5\u27f0-\u27ff\u2900-\u2982\u2999-\u29d7\u29dc-\u29fb\u29fe-\u2aff'
            u'\u2b30-\u2b44\u2b47-\u2b4c\ufb29\ufe62\ufe64-\ufe66\uff0b\uff1c-\uff1e\uff5c\uff5e\uffe2'
            u'\uffe9-\uffec\U0001d6c1\U0001d6db\U0001d6fb\U0001d715\U0001d735\U0001d74f\U0001d76f\U0001d789'
            u'\U0001d7a9\U0001d7c3\U0001eef0\U0001eef1'
        ),
        'So': UnicodeSubset(
            u'\u00a6\u00a9\u00ae\u00b0\u0482\u058d\u058e\u060e\u060f\u06de\u06e9\u06fd\u06fe\u07f6\u09fa'
            u'\u0b70\u0bf3-\u0bf8\u0bfa\u0c7f\u0d79\u0f01-\u0f03\u0f13\u0f15-\u0f17\u0f1a-\u0f1f\u0f34'
            u'\u0f36\u0f38\u0fbe-\u0fc5\u0fc7-\u0fcc\u0fce\u0fcf\u0fd5-\u0fd8\u109e\u109f\u1390-\u1399'
            u'\u1940\u19de-\u19ff\u1b61-\u1b6a\u1b74-\u1b7c\u2100\u2101\u2103-\u2106\u2108\u2109\u2114'
            u'\u2116\u2117\u211e-\u2123\u2125\u2127\u2129\u212e\u213a\u213b\u214a\u214c\u214d\u214f\u218a'
            u'\u218b\u2195-\u2199\u219c-\u219f\u21a1\u21a2\u21a4\u21a5\u21a7-\u21ad\u21af-\u21cd\u21d0'
            u'\u21d1\u21d3\u21d5-\u21f3\u2300-\u2307\u230c-\u231f\u2322-\u2328\u232b-\u237b\u237d-\u239a'
            u'\u23b4-\u23db\u23e2-\u23fa\u2400-\u2426\u2440-\u244a\u249c-\u24e9\u2500-\u25b6\u25b8-\u25c0'
            u'\u25c2-\u25f7\u2600-\u266e\u2670-\u2767\u2794-\u27bf\u2800-\u28ff\u2b00-\u2b2f\u2b45\u2b46'
            u'\u2b4d-\u2b73\u2b76-\u2b95\u2b98-\u2bb9\u2bbd-\u2bc8\u2bca-\u2bd1\u2bec-\u2bef\u2ce5-\u2cea'
            u'\u2e80-\u2e99\u2e9b-\u2ef3\u2f00-\u2fd5\u2ff0-\u2ffb\u3004\u3012\u3013\u3020\u3036\u3037'
            u'\u303e\u303f\u3190\u3191\u3196-\u319f\u31c0-\u31e3\u3200-\u321e\u322a-\u3247\u3250\u3260-\u327f'
            u'\u328a-\u32b0\u32c0-\u32fe\u3300-\u33ff\u4dc0-\u4dff\ua490-\ua4c6\ua828-\ua82b\ua836\ua837'
            u'\ua839\uaa77-\uaa79\ufdfd\uffe4\uffe8\uffed\uffee\ufffc\ufffd\U00010137-\U0001013f'
            u'\U00010179-\U00010189\U0001018c\U00010190-\U0001019b\U000101a0\U000101d0-\U000101fc'
            u'\U00010877\U00010878\U00010ac8\U0001173f\U00016b3c-\U00016b3f\U00016b45\U0001bc9c'
            u'\U0001d000-\U0001d0f5\U0001d100-\U0001d126\U0001d129-\U0001d164\U0001d16a-\U0001d16c'
            u'\U0001d183\U0001d184\U0001d18c-\U0001d1a9\U0001d1ae-\U0001d1e8\U0001d200-\U0001d241'
            u'\U0001d245\U0001d300-\U0001d356\U0001d800-\U0001d9ff\U0001da37-\U0001da3a\U0001da6d-\U0001da74'
            u'\U0001da76-\U0001da83\U0001da85\U0001da86\U0001f000-\U0001f02b\U0001f030-\U0001f093'
            u'\U0001f0a0-\U0001f0ae\U0001f0b1-\U0001f0bf\U0001f0c1-\U0001f0cf\U0001f0d1-\U0001f0f5'
            u'\U0001f110-\U0001f12e\U0001f130-\U0001f16b\U0001f170-\U0001f19a\U0001f1e6-\U0001f202'
            u'\U0001f210-\U0001f23a\U0001f240-\U0001f248\U0001f250\U0001f251\U0001f300-\U0001f3fa'
            u'\U0001f400-\U0001f579\U0001f57b-\U0001f5a3\U0001f5a5-\U0001f6d0\U0001f6e0-\U0001f6ec'
            u'\U0001f6f0-\U0001f6f3\U0001f700-\U0001f773\U0001f780-\U0001f7d4\U0001f800-\U0001f80b'
            u'\U0001f810-\U0001f847\U0001f850-\U0001f859\U0001f860-\U0001f887\U0001f890-\U0001f8ad'
            u'\U0001f910-\U0001f918\U0001f980-\U0001f984\U0001f9c0'
        ),
        'Zl': UnicodeSubset(u'\u2028'),
        'Zp': UnicodeSubset(u'\u2029'),
        'Zs': UnicodeSubset(u'\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000')
    }


class XsdRegexCharGroup(MutableSet):
    """
    A set subclass to represent XML Schema regex character groups.
    """

    def __init__(self, *args):
        self._positive = UnicodeSubset()
        self._negative = UnicodeSubset()
        for char in args:
            self.add(char)

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, self.get_char_class(), id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self._negative:
            max_code_point = max(max(self._positive), max(self._negative))
            if max_code_point < maxunicode:
                gen_char_group = (
                    cp for cp in range(max_code_point + 1)
                    if cp in self._positive or cp not in self._negative
                )
                return u''.join(generate_character_group(
                    chain(gen_char_group, (cp for cp in [max_code_point + 1] * 2))
                ))
        return u''.join(generate_character_group(iter(self)))

    if PY3:
        __str__ = __unicode__

    def __contains__(self, char):
        if self._negative:
            return ord(char) not in self._negative or ord(char) in self._positive
        return ord(char) in self._positive

    def __iter__(self):
        if self._negative:
            return (
                cp for cp in range(maxunicode + 1)
                if cp in self._positive or cp not in self._negative
            )
        return iter(sorted(self._positive))

    def __len__(self):
        return len(self._positive) + len(self._negative)

    def add(self, s):
        for part in re.split(r'(\\[sSdDiIcCwW])', s):
            if part == '\\s':
                self._positive.add_string(' \n\t\r')
            elif part == '\\S':
                self._negative.add_string(' \n\t\r')
            elif part == '\\d':
                self._positive.add_string('0-9')
            elif part == '\\D':
                self._negative.add_string('0-9')
            elif part == '\\i':
                self._positive.add_string(I_SHORTCUT_REPLACE)
            elif part == '\\I':
                self._negative.add_string(I_SHORTCUT_REPLACE)
            elif part == '\\c':
                self._positive.add_string(C_SHORTCUT_REPLACE)
            elif part == '\\C':
                self._negative.add_string(C_SHORTCUT_REPLACE)
            elif part == '\\w':
                self._positive.add_string(u'\u0000-\uFFFF')
            elif part == '\\W':
                self._negative.add_string(u'\u0000-\uFFFF')
            elif part == '\\p':
                pass
            elif part == '\\P':
                pass
            else:
                self._positive.add_string(part)

    def discard(self, s):
        for part in re.split(r'(\\[sSdDiIcCwW])', s):
            if part == '\\s':
                self._positive.discard_string(' \n\t\r')
            elif part == '\\S':
                self._negative.discard_string(' \n\t\r')
            elif part == '\\d':
                self._positive.discard_string('0-9')
            elif part == '\\D':
                self._negative.discard_string('0-9')
            elif part == '\\i':
                self._positive.discard_string(I_SHORTCUT_REPLACE)
            elif part == '\\I':
                self._negative.discard_string(I_SHORTCUT_REPLACE)
            elif part == '\\c':
                self._positive.discard_string(C_SHORTCUT_REPLACE)
            elif part == '\\C':
                self._negative.discard_string(C_SHORTCUT_REPLACE)
            elif part == '\\w':
                self._positive.discard_string(u'\u0000-\uFFFF')
            elif part == '\\W':
                self._negative.discard_string(u'\u0000-\uFFFF')
            elif part == '\\p':
                pass
            elif part == '\\P':
                pass
            else:
                self._positive.discard_string(part)

    def clear(self):
        self._positive.clear()
        self._negative.clear()

    def complement(self):
        self._positive, self._negative = self._negative, self._positive

    def get_char_class(self):
        if self._positive:
            return u'[%s]' % str(self)
        elif self._negative:
            return u'[^%s]' % str(self._negative)
        else:
            return ''


def get_python_regex(xml_regex):
    """
    Get a Python's compatible regex from a XML regex expression.
    """
    regex = ['^']
    pos = 0
    char_group = XsdRegexCharGroup()
    while pos < len(xml_regex):
        ch = xml_regex[pos]
        if ch == '.':
            regex.append(r'[^\r\n]')
        elif ch in ('^', '$'):
            regex.append(r'\%s' % ch)
        elif ch == '[':
            pass
        elif ch == '\\':
            pos += 1
            if pos >= len(xml_regex):
                regex.append('\\')
            elif xml_regex[pos] in 'iIcC':
                char_group.clear()
                char_group.add('\%s' % xml_regex[pos])
                regex.append(char_group.get_char_class())
            elif xml_regex[pos] in 'pP':
                start_pos = pos - 1
                try:
                    while xml_regex[pos] != '}':
                        pos += 1
                except IndexError:
                    raise XMLSchemaRegexError(
                        "truncated unicode block escape ad position %d: %r" % (start_pos, xml_regex)
                    )
                char_group.clear()
                char_group.add(xml_regex[start_pos:pos + 1])
                regex.append(char_group.get_char_class())
            else:
                regex.append('\\%s' % xml_regex[pos])
        else:
            regex.append(ch)
        pos += 1

    regex.append(r'$')
    return u''.join(regex)
