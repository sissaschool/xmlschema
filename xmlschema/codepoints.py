# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
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
from collections import MutableSet

from .compat import PY3, unicode_chr, unicode_type
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaRegexError


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


def get_compacted_code_points(code_points, sort=False):
    """
    Get a compacted representation of a list of numerical code points.

    :param code_points: Sequence of numerical code points.
    :param sort: Sort the sequence before compacting.
    :return: A list with a compacted representation of code points.
    """
    def generate_code_points(items):
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
                yield range_code_point, range_code_point + range_len - 1
                range_code_point = code_point
                range_len = 1
        else:
            if range_len == 1:
                yield range_code_point
            elif range_len == 2:
                yield range_code_point
                yield range_code_point + 1
            else:
                yield range_code_point, range_code_point + range_len - 1

    if sort:
        code_points = sorted(code_points)
    return [cp for cp in generate_code_points(code_points)]


def unicode_category_sequencer(code_points):
    """
    Generate a sequence of unicode categories associations.

    :param code_point_range:
    :return: Yields integers value or 2-tuple with integers items.
    """
    from unicodedata import category

    code_points_iter = iter(code_points)

    try:
        prev_cp = next(code_points_iter)
    except StopIteration:
        return
    prev_cat = category(unicode_chr(prev_cp))
    next_cp = None

    while True:
        try:
            next_cp = next(code_points_iter)
        except StopIteration:
            if next_cp is None:
                yield prev_cat, prev_cp
            else:
                diff = next_cp - prev_cp
                if diff > 1:
                    yield prev_cat, (prev_cp, next_cp)
                elif diff == 1:
                    yield prev_cat, prev_cp
                    yield prev_cat, next_cp
                else:
                    yield prev_cat, prev_cp
            break
        else:
            next_cat = category(unicode_chr(next_cp))
            if next_cat != prev_cat:
                diff = next_cp - prev_cp
                if diff > 2:
                    yield prev_cat, (prev_cp, next_cp - 1)
                elif diff == 2:
                    yield prev_cat, prev_cp
                    yield prev_cat, next_cp - 1
                else:
                    yield prev_cat, prev_cp
                prev_cp = next_cp
                prev_cat = next_cat


def code_point_sorter(x):
    return x[0] if isinstance(x, tuple) else x


def save_unicode_categories(filename=None):
    """
    Save Unicode categories to a JSON file.

    :param filename: Name of the JSON file to save. If None use the predefined
    filename 'unicode_categories.json' and try to save in the directory of this
    module.
    """
    from collections import defaultdict

    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'unicode_categories.json')

    categories = defaultdict(list)
    for key, cp in unicode_category_sequencer(range(maxunicode + 1)):
        categories[key].append(cp)

    with open(filename, 'w') as fp:
        json.dump(categories, fp)


def _parse_character_group(s):
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
                        "bad character range %r-%r at position %d: %r" % (char, end_char, i - 2, s)
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


def parse_character_group(s, expand_ranges=False):
    """
    Parse a regex character group part, generating a sequence of code points
    and code points ranges. An unescaped hyphen (-) that is not at the start
    or at the and is interpreted as range specifier.

    :param s: A string representing a character group part.
    :param expand_ranges: Do not expand ranges, returns as couples of integers. \
    This is the default.
    :return: Sequence of integers or couple of integers.
    """
    escaped = False
    start_char = None
    last_index = len(s) - 1
    string_iter = iter(range(len(s)))
    for i in string_iter:
        if i == 0:
            char = s[0]
            if char == '\\':
                escaped = True
            elif char in r'[]' and len(s) > 1:
                raise XMLSchemaRegexError("bad character %r at position 0" % char)
            elif expand_ranges:
                yield ord(char)
            elif last_index == 0 or s[1] != '-':
                yield ord(char)
            else:
                start_char = char
        elif s[i] == '-':
            if escaped or (i == len(s) - 1):
                char = s[i]
                yield ord(char)
                escaped = False
            else:
                i = next(string_iter)
                end_char = s[i]
                if end_char == '\\' and (i < len(s) - 1) and s[i + 1] in r'-|.^?*+{}()[]':
                    i = next(string_iter)
                    end_char = s[i]
                if ord(char) > ord(end_char):
                    raise XMLSchemaRegexError(
                        "bad character range %r-%r at position %d: %r" % (char, end_char, i - 2, s)
                    )
                if expand_ranges:
                    for cp in range(ord(char) + 1, ord(end_char) + 1):
                        yield cp
                else:
                    yield [ord(start_char), ord(end_char)]
        elif s[i] in r'|.^?*+{}()':
            if escaped:
                escaped = False
            char = s[i]
            yield ord(char)
        elif s[i] in r'[]':
            if not escaped and len(s) > 1:
                raise XMLSchemaRegexError("bad character %r at position %d" % (s[i], i))
            escaped = False
            char = s[i]
            yield ord(char)
        elif s[i] == '\\':
            if escaped:
                escaped = False
                char = '\\'
                yield ord(char)
            else:
                escaped = True
        else:
            if escaped:
                escaped = False
                yield ord('\\')
            char = s[i]
            if expand_ranges:
                yield ord(char)
            elif last_index > i and s[i + 1] == '-':
                start_char = char
            else:
                yield ord(char)
    if escaped:
        yield ord('\\')


def generate_character_group(s):
    """
    Generate a character group representation of a sequence of Unicode code points.
    A duplicated code point ends the generation of the group with a character range
    that reaches the maxunicode.

    :param s: An iterable with unicode code points.
    """
    def character_group_repr(cp):
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
        elif isinstance(args[0], (set, UnicodeSubset)):
            self._store = args[0].copy()
        else:
            self._store = set()
            if isinstance(args[0], (unicode_type, str)):
                self.add_string(args[0])
            else:
                for item in args[0]:
                    self.add(item)

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, str(self), id(self))

    def __str__(self):
        # noinspection PyCompatibility
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
        for char in _parse_character_group(s):
            self._store.add(ord(char))

    def discard_string(self, s):
        for char in _parse_character_group(s):
            self._store.discard(ord(char))

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return self._store.copy()


class CodePointSet(MutableSet):
    """
    A set of Unicode code points, implemented with a list of values and ranges.
    It manages character ranges for adding or for discarding elements from a
    string and for a compressed representation.
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
            self._code_points = list()
        elif isinstance(args[0], UnicodeSubset):
            self._code_points = args[0]._code_points.copy()
        else:
            self._code_points = list()
            if isinstance(args[0], (unicode_type, str)):
                for item in parse_character_group(args[0]):
                    self.add(item)
            else:
                for item in reversed(sorted(args[0], key=code_point_sorter)):
                    self.add(item)

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, str(self), id(self))

    def __str__(self):
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return str(self._code_points)

    if PY3:
        __str__ = __unicode__

    def __contains__(self, code_point):
        for cp in self._code_points:
            if isinstance(cp, tuple):
                if cp[0] > code_point:
                    return False
                elif cp[1] < code_point:
                    continue
                else:
                    return True
            elif cp > code_point:
                return False
            elif cp == code_point:
                return True
        return False

    def __iter__(self):
        for item in self._code_points:
            if isinstance(item, tuple):
                for cp in range(item[0], item[1] + 1):
                    yield cp
            else:
                yield item

    def __len__(self):
        i = 0
        for _ in self:
            i += 1
        return i

    def complement(self):
        last = 0
        for cp in self._code_points:
            if last > maxunicode:
                break
            if isinstance(cp, int):
                diff = cp - last
                start_cp = end_cp = cp
            else:
                start_cp, end_cp = cp
                diff = start_cp - last

            if diff > 2:
                yield last, start_cp - 1
            elif diff == 2:
                yield last
                yield last + 1
            elif diff == 1:
                yield last
            elif diff != 0:
                raise XMLSchemaValueError("code points unordered")
            last = end_cp + 1

        if last == maxunicode:
            yield maxunicode
        elif last < maxunicode:
            yield last, maxunicode

    def add(self, value):
        if isinstance(value, (list, tuple)):
            if len(value) > 2 or value[0] > value[1] or value[0] < 0 or value[1] > maxunicode:
                raise XMLSchemaValueError("not a code point range: %r" % value)
            start_value, end_value = value
            if start_value == end_value:
                value = start_value
            elif isinstance(value, list):
                value = tuple(value)
        else:
            start_value = end_value = value
            if not (0 <= value <= maxunicode):
                raise XMLSchemaValueError(
                    "Unicode code point must be in range [0 .. %d]: %r" % (maxunicode, value)
                )

        code_points = self._code_points
        for pos in range(len(code_points)):
            if isinstance(code_points[pos], tuple):
                start_cp, end_cp = code_points[pos]
            else:
                start_cp = end_cp = code_points[pos]

            try:
                higher_limit = code_points[pos + 1]
            except IndexError:
                higher_limit = maxunicode + 1
            else:
                if isinstance(higher_limit, tuple):
                    higher_limit = higher_limit[0]

            if start_value < start_cp:
                if start_value == start_cp - 1 or end_value >= start_cp - 1:
                    if end_cp > start_cp:
                        code_points[pos] = start_value, max(min(end_value, higher_limit - 1), end_cp)
                    else:
                        code_points[pos] = start_value, max(min(end_value, higher_limit - 1), end_cp)
                    break
                else:
                    code_points.insert(pos, value)
                    break
            elif start_value > end_cp + 1:
                continue
            elif end_cp > start_cp:
                code_points[pos] = start_cp, max(min(end_value, higher_limit - 1), end_cp)
            elif end_value > start_cp:
                code_points[pos] = start_cp, min(end_value, higher_limit - 1)
            break
        else:
            self._code_points.append(value)

    def discard(self, value):
        if isinstance(value, (list, tuple)):
            if len(value) > 2 or value[0] > value[1] or value[0] < 0 or value[1] > maxunicode:
                raise XMLSchemaValueError("not a code point range: %r" % value)
            start_value, end_value = value
        else:
            start_value = end_value = value
            if not (0 <= value <= maxunicode):
                raise XMLSchemaValueError(
                    "Unicode code point must be in range [0 .. %d]: %r" % (maxunicode, value)
                )

        code_points = self._code_points
        for pos in reversed(range(len(code_points))):
            if isinstance(code_points[pos], tuple):
                start_cp, end_cp = code_points[pos]
            else:
                start_cp = end_cp = code_points[pos]

            if start_value > end_cp:
                break
            elif end_value >= end_cp:
                if start_value <= start_cp:
                    del code_points[pos]
                elif start_value - start_cp > 1:
                    code_points[pos] = start_cp, start_value - 1
                else:
                    code_points[pos] = start_cp
                continue
            elif end_value >= start_cp:
                if start_value <= start_cp:
                    if end_cp - end_value > 1:
                        code_points[pos] = end_value + 1, end_cp
                    else:
                        code_points[pos] = end_cp
                else:
                    if end_cp - end_value > 1:
                        code_points.insert(pos + 1, (end_value + 1, end_cp))
                    else:
                        code_points.insert(pos + 1, end_cp)
                    if start_value - start_cp > 1:
                        code_points[pos] = start_cp, start_value - 1
                    else:
                        code_points[pos] = start_cp

    def add_string(self, s):
        for cp in parse_character_group(s):
            self.add(cp)

    def discard_string(self, s):
        for cp in parse_character_group(s):
            self.discard(cp)

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return CodePointSet(self._code_points)

    def __eq__(self, other):
        if isinstance(other, CodePointSet):
            return self._code_points == other._code_points
        else:
            return self._code_points == other

    def __or__(self, other):
        if isinstance(other, CodePointSet):
            obj = self.copy()
            for cp in other._code_points:
                obj.add(cp)
            return obj
        else:
            return self._code_points == other


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
        from collections import defaultdict
        categories = defaultdict(list)
        for key, cp in unicode_category_sequencer(range(maxunicode + 1)):
            categories[key].append(cp)
    else:
        for values in categories.values():
            for k in range(len(values)):
                if isinstance(values[k], list):
                    values[k] = tuple(values[k])

    # Build general categories code points
    categories['C'] = sorted(categories['Cc'] + categories['Cf'] + categories['Cs'] +
                             categories['Co'] + categories['Cn'], key=code_point_sorter)
    categories['L'] = sorted(categories['Lu'] + categories['Ll'] + categories['Lt'] +
                             categories['Lm'] + categories['Lo'], key=code_point_sorter)
    categories['M'] = sorted(categories['Mn'] + categories['Mc'] + categories['Me'], key=code_point_sorter)
    categories['N'] = sorted(categories['Nd'] + categories['Nl'] + categories['No'], key=code_point_sorter)
    categories['P'] = sorted(
        categories['Pc'] + categories['Pd'] + categories['Ps'] + categories['Pe'] + categories['Pi'] +
        categories['Pf'] + categories['Po'], key=code_point_sorter
    )
    categories['S'] = sorted(
        categories['Sm'] + categories['Sc'] + categories['Sk'] + categories['So'], key=code_point_sorter
    )
    categories['Z'] = sorted(categories['Zs'] + categories['Zl'] + categories['Zp'], key=code_point_sorter)

    for k, v in categories.items():
        cds = CodePointSet()
        cds._code_points = v
        categories[k] = cds

    return dict(categories)


UNICODE_CATEGORIES = get_unicode_categories()
