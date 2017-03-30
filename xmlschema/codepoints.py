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
This module defines Unicode character categories and blocks, defined as sets of code points.
"""
import json
import os.path
from sys import maxunicode

from .core import unicode_chr

UNICODE_BLOCKS = {
    'IsBasicLatin': frozenset(range(0x80)),  # u'\u0000-\u007F',
    'IsLatin-1Supplement': frozenset(range(0x80, 0x100)),  # u'\u0080-\u00FF',
    'IsLatinExtended-A': frozenset(range(0x100, 0x180)),  # u'\u0100-\u017F',
    'IsLatinExtended-B': frozenset(range(0x180, 0x250)),  # u'\u0180-\u024F',
    'IsIPAExtensions': frozenset(range(0x250, 0x2B0)),  # u'\u0250-\u02AF',
    'IsSpacingModifierLetters': frozenset(range(0x2B0, 0x300)),  # u'\u02B0-\u02FF',
    'IsCombiningDiacriticalMarks': frozenset(range(0x300, 0x370)),  # u'\u0300-\u036F',
    'IsGreek': frozenset(range(0x370, 0x400)),  # u'\u0370-\u03FF',
    'IsCyrillic': frozenset(range(0x400, 0x500)),  # u'\u0400-\u04FF',
    'IsArmenian': frozenset(range(0x530, 0x590)),  # u'\u0530-\u058F',
    'IsHebrew': frozenset(range(0x590, 0x600)),  # u'\u0590-\u05FF',
    'IsArabic': frozenset(range(0x600, 0x700)),  # u'\u0600-\u06FF',
    'IsSyriac': frozenset(range(0x700, 0x750)),  # u'\u0700-\u074F',
    'IsThaana': frozenset(range(0x780, 0x7C0)),  # u'\u0780-\u07BF',
    'IsDevanagari': frozenset(range(0x900, 0x980)),  # u'\u0900-\u097F',
    'IsBengali': frozenset(range(0x980, 0xA00)),  # u'\u0980-\u09FF',
    'IsGurmukhi': frozenset(range(0xA00, 0xA80)),  # u'\u0A00-\u0A7F',
    'IsGujarati': frozenset(range(0xA80, 0xB00)),  # u'\u0A80-\u0AFF',
    'IsOriya': frozenset(range(0xB00, 0xB80)),  # u'\u0B00-\u0B7F',
    'IsTamil': frozenset(range(0xB80, 0xC00)),  # u'\u0B80-\u0BFF',
    'IsTelugu': frozenset(range(0xC00, 0xC80)),  # u'\u0C00-\u0C7F',
    'IsKannada': frozenset(range(0xC80, 0xD00)),  # u'\u0C80-\u0CFF',
    'IsMalayalam': frozenset(range(0xD00, 0xD80)),  # u'\u0D00-\u0D7F',
    'IsSinhala': frozenset(range(0xD80, 0xE00)),  # u'\u0D80-\u0DFF',
    'IsThai': frozenset(range(0xE00, 0xE80)),  # u'\u0E00-\u0E7F',
    'IsLao': frozenset(range(0xE80, 0xF00)),  # u'\u0E80-\u0EFF',
    'IsTibetan': frozenset(range(0xF00, 0x10000)),  # u'\u0F00-\u0FFF',
    'IsMyanmar': frozenset(range(0x1000, 0x10A0)),  # u'\u1000-\u109F',
    'IsGeorgian': frozenset(range(0x10A0, 0x1100)),  # u'\u10A0-\u10FF',
    'IsHangulJamo': frozenset(range(0x1100, 0x1200)),  # u'\u1100-\u11FF',
    'IsEthiopic': frozenset(range(0x1200, 0x1380)),  # u'\u1200-\u137F',
    'IsCherokee': frozenset(range(0x13A0, 0x1400)),  # u'\u13A0-\u13FF',
    'IsUnifiedCanadianAboriginalSyllabics': frozenset(range(0x1400, 0x1680)),  # u'\u1400-\u167F',
    'IsOgham': frozenset(range(0x1680, 0x16A0)),  # u'\u1680-\u169F',
    'IsRunic': frozenset(range(0x16A0, 0x1700)),  # u'\u16A0-\u16FF',
    'IsKhmer': frozenset(range(0x1780, 0x1800)),  # u'\u1780-\u17FF',
    'IsMongolian': frozenset(range(0x1800, 0x18B0)),  # u'\u1800-\u18AF',
    'IsLatinExtendedAdditional': frozenset(range(0x1E00, 0x1F00)),  # u'\u1E00-\u1EFF',
    'IsGreekExtended': frozenset(range(0x1F00, 0x2000)),  # u'\u1F00-\u1FFF',
    'IsGeneralPunctuation': frozenset(range(0x2000, 0x2070)),  # u'\u2000-\u206F',
    'IsSuperscriptsandSubscripts': frozenset(range(0x2070, 0x20A0)),  # u'\u2070-\u209F',
    'IsCurrencySymbols': frozenset(range(0x20A0, 0x20D0)),  # u'\u20A0-\u20CF',
    'IsCombiningMarksforSymbols': frozenset(range(0x20D0, 0x2100)),  # u'\u20D0-\u20FF',
    'IsLetterlikeSymbols': frozenset(range(0x2100, 0x2150)),  # u'\u2100-\u214F',
    'IsNumberForms': frozenset(range(0x2150, 0x2190)),  # u'\u2150-\u218F',
    'IsArrows': frozenset(range(0x2190, 0x2200)),  # u'\u2190-\u21FF',
    'IsMathematicalOperators': frozenset(range(0x2200, 0x2300)),  # u'\u2200-\u22FF',
    'IsMiscellaneousTechnical': frozenset(range(0x2300, 0x2400)),  # u'\u2300-\u23FF',
    'IsControlPictures': frozenset(range(0x2400, 0x2440)),  # u'\u2400-\u243F',
    'IsOpticalCharacterRecognition': frozenset(range(0x2440, 0x2460)),  # u'\u2440-\u245F',
    'IsEnclosedAlphanumerics': frozenset(range(0x2460, 0x2500)),  # u'\u2460-\u24FF',
    'IsBoxDrawing': frozenset(range(0x2500, 0x2580)),  # u'\u2500-\u257F',
    'IsBlockElements': frozenset(range(0x2580, 0x25A0)),  # u'\u2580-\u259F',
    'IsGeometricShapes': frozenset(range(0x25A0, 0x2600)),  # u'\u25A0-\u25FF',
    'IsMiscellaneousSymbols': frozenset(range(0x2600, 0x2700)),  # u'\u2600-\u26FF',
    'IsDingbats': frozenset(range(0x2700, 0x27C0)),  # u'\u2700-\u27BF',
    'IsBraillePatterns': frozenset(range(0x2800, 0x2900)),  # u'\u2800-\u28FF',
    'IsCJKRadicalsSupplement': frozenset(range(0x2E80, 0x2F00)),  # u'\u2E80-\u2EFF',
    'IsKangxiRadicals': frozenset(range(0x2F00, 0x2FE0)),  # u'\u2F00-\u2FDF',
    'IsIdeographicDescriptionCharacters': frozenset(range(0x2FF0, 0x3000)),  # u'\u2FF0-\u2FFF',
    'IsCJKSymbolsandPunctuation': frozenset(range(0x3000, 0x3040)),  # u'\u3000-\u303F',
    'IsHiragana': frozenset(range(0x3040, 0x30A0)),  # u'\u3040-\u309F',
    'IsKatakana': frozenset(range(0x30A0, 0x3100)),  # u'\u30A0-\u30FF',
    'IsBopomofo': frozenset(range(0x3100, 0x3130)),  # u'\u3100-\u312F',
    'IsHangulCompatibilityJamo': frozenset(range(0x3130, 0x3190)),  # u'\u3130-\u318F',
    'IsKanbun': frozenset(range(0x3190, 0x31A0)),  # u'\u3190-\u319F',
    'IsBopomofoExtended': frozenset(range(0x31A0, 0x31C0)),  # u'\u31A0-\u31BF',
    'IsEnclosedCJKLettersandMonths': frozenset(range(0x3200, 0x3300)),  # u'\u3200-\u32FF',
    'IsCJKCompatibility': frozenset(range(0x3300, 0x3400)),  # u'\u3300-\u33FF',
    'IsCJKUnifiedIdeographsExtensionA': frozenset(range(0x3400, 0x4DB6)),  # u'\u3400-\u4DB5',
    'IsCJKUnifiedIdeographs': frozenset(range(0x4E00, 0xA000)),  # u'\u4E00-\u9FFF',
    'IsYiSyllables': frozenset(range(0xA000, 0xA490)),  # u'\uA000-\uA48F',
    'IsYiRadicals': frozenset(range(0xA490, 0xA4D0)),  # u'\uA490-\uA4CF',
    'IsHangulSyllables': frozenset(range(0xAC00, 0xD7A4)),  # u'\uAC00-\uD7A3',
    'IsHighSurrogates': frozenset(range(0xD800, 0xDB80)),  # u'\uD800-\uDB7F',
    'IsHighPrivateUseSurrogates': frozenset(range(0xDB80, 0xDC00)),  # u'\uDB80-\uDBFF',
    'IsLowSurrogates': frozenset(range(0xDC00, 0xE000)),  # u'\uDC00-\uDFFF',
    'IsPrivateUse':
        frozenset(range(0xE000, 0xF900)) |
        frozenset(range(0xF0000, 0x10FFFE)),  # u'\uE000-\uF8FF\U000F0000-\U0010FFFD',
    'IsCJKCompatibilityIdeographs': frozenset(range(0xF900, 0xFB00)),  # u'\uF900-\uFAFF',
    'IsAlphabeticPresentationForms': frozenset(range(0xFB00, 0xFB50)),  # u'\uFB00-\uFB4F',
    'IsArabicPresentationForms-A': frozenset(range(0xFB50, 0xFE00)),  # u'\uFB50-\uFDFF',
    'IsCombiningHalfMarks': frozenset(range(0xFE20, 0xFE30)),  # u'\uFE20-\uFE2F',
    'IsCJKCompatibilityForms': frozenset(range(0xFE30, 0xFE50)),  # u'\uFE30-\uFE4F',
    'IsSmallFormVariants': frozenset(range(0xFE50, 0xFE70)),  # u'\uFE50-\uFE6F',
    'IsArabicPresentationForms-B': frozenset(range(0xFE70, 0xFEFF)),  # u'\uFE70-\uFEFE',
    'IsSpecials': {0xFEFF} | frozenset(range(0xFFF0, 0xFFFE)),  # u'\uFEFF-\uFEFF\uFFF0-\uFFFD',
    'IsHalfwidthandFullwidthForms': frozenset(range(0xFF00, 0xFFF0)),  # u'\uFF00-\uFFEF',
    'IsOldItalic': frozenset(range(0x10300, 0x10330)),  # u'\U00010300-\U0001032F',
    'IsGothic': frozenset(range(0x10330, 0x1034F)),  # u'\U00010330-\U0001034F',
    'IsDeseret': frozenset(range(0x10400, 0x10450)),  # u'\U00010400-\U0001044F',
    'IsByzantineMusicalSymbols': frozenset(range(0x1D000, 0x1D100)),  # u'\U0001D000-\U0001D0FF',
    'IsMusicalSymbols': frozenset(range(0x1D100, 0x1D200)),  # u'\U0001D100-\U0001D1FF',
    'IsMathematicalAlphanumericSymbols': frozenset(range(0x1D400, 0x1D800)),  # u'\U0001D400-\U0001D7FF',
    'IsCJKUnifiedIdeographsExtensionB': frozenset(range(0x20000, 0x2A6D7)),  # u'\U00020000-\U0002A6D6',
    'IsCJKCompatibilityIdeographsSupplement': frozenset(range(0x2F800, 0x2FA20)),  # u'\U0002F800-\U0002FA1F',
    'IsTags': frozenset(range(0xE0000, 0xE0080))  # u'\U000E0000-\U000E007F'
}


def save_unicode_categories(filename=None):
    """
    Save Unicode categories to a JSON file.

    :param filename: Name of the JSON file to save. If None use the predefined
    filename 'unicode_categories.json' and try to save in the directory of this
    module.
    """
    def gen_ranges():
        """
        Generates values or ranges in order to compress the code points representation.
        """
        if not items:
            return
        range_code_point = items[0]
        range_len = 1
        for code_point in items[1:]:
            if code_point == (range_code_point + range_len):
                # Next character --> range extension
                range_len += 1
            elif range_len == 1:
                yield range_code_point
                range_code_point = code_point
            elif range_len == 2:
                # Ending of a range of two length.
                yield range_code_point
                yield range_code_point + 1
                range_code_point = code_point
                range_len = 1
            else:
                # Ending of a range of three or more length.
                yield [range_code_point, range_code_point + range_len - 1]
                range_code_point = code_point
                range_len = 1
        else:
            if range_len == 1:
                yield range_code_point
            elif range_len == 2:
                yield range_code_point
                yield range_code_point + 1
            else:
                yield [range_code_point, range_code_point + range_len - 1]

    from unicodedata import category
    from collections import defaultdict

    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'unicode_categories.json')

    categories = defaultdict(list)
    for cp in range(maxunicode + 1):
        categories[category(unicode_chr(cp))].append(cp)

    for name, items in categories.items():
        categories[name] = [cp for cp in gen_ranges()]

    with open(filename, 'w') as fp:
        json.dump(categories, fp)


def get_unicode_categories(filename=None):
    """
    Get the Unicode categories.

    :param filename: Name of the JSON file to read. If None use the predefined
    filename 'unicode_categories.json' and try to save in the directory of this
    module.
    """
    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'unicode_categories.json')

    try:
        with open(filename, 'r') as fp:
            categories = json.load(fp)
    except (IOError, SystemError):
        from unicodedata import category
        from collections import defaultdict

        categories = defaultdict(set)
        for cp in range(maxunicode + 1):
            categories[category(unicode_chr(cp))].add(cp)
        categories = dict(categories)
    else:
        for key, values in categories.items():
            categories[key] = {
                cp for cp1, cp2 in map(
                    lambda x: x if isinstance(x, list) else (x, x), values
                ) for cp in range(cp1, cp2 + 1)
            }

    categories['C'] = categories['Cc'] | categories['Cf'] | categories['Cs'] | \
        categories['Co'] | categories['Cn']
    categories['L'] = categories['Lu'] | categories['Ll'] | categories['Lt'] | \
        categories['Lm'] | categories['Lo']
    categories['M'] = categories['Mn'] | categories['Mc'] | categories['Me']
    categories['N'] = categories['Nd'] | categories['Nl'] | categories['No']
    categories['P'] = (
        categories['Pc'] | categories['Pd'] | categories['Ps'] |
        categories['Pe'] | categories['Pi'] | categories['Pf'] | categories['Po']
    )
    categories['S'] = categories['Sm'] | categories['Sc'] | categories['Sk'] | categories['So']
    categories['Z'] = categories['Zs'] | categories['Zl'] | categories['Zp']

    return categories


UNICODE_CATEGORIES = get_unicode_categories()
