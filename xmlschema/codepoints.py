# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
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
import os
from sys import maxunicode
from collections import Iterable, MutableSet

from .compat import PY3, unicode_chr, unicode_type
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaRegexError

CHARACTER_GROUP_ESCAPED = {ord(c) for c in r'-|.^?*+{}()[]'}
"""Code Points of escaped chars in a character group."""

UCS4_MAXUNICODE = 1114111


def code_point_repr(cp):
    if not isinstance(cp, tuple):
        if cp in CHARACTER_GROUP_ESCAPED:
            return u'\%s' % unicode_chr(cp)
        return unicode_chr(cp)

    if cp[0] in CHARACTER_GROUP_ESCAPED:
        start_char = u'\%s' % unicode_chr(cp[0])
    else:
        start_char = unicode_chr(cp[0])

    if cp[1] in CHARACTER_GROUP_ESCAPED:
        end_char = u'\%s' % unicode_chr(cp[1])
    else:
        end_char = unicode_chr(cp[1])

    if cp[1] > cp[0] + 1:
        return u'%s-%s' % (start_char, end_char)
    else:
        return start_char + end_char


def parse_character_group(s, expand_ranges=False):
    """
    Parse a regex character group part, generating a sequence of code points
    and code points ranges. An unescaped hyphen (-) that is not at the start
    or at the and is interpreted as range specifier.

    :param s: A string representing a character group part.
    :param expand_ranges: Do not expand ranges, returns as couples of integers. \
    This is the default.
    :return: Yields integers or couples of integers.
    """
    escaped = False
    char = None
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
            elif last_index <= 1 or s[1] != '-':
                yield ord(char)
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
                    yield ord(char), ord(end_char)
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
            yield ord(char)
    if escaped:
        yield ord('\\')


def iter_code_points(items, reverse=False):
    if reverse:
        items = sorted(items, reverse=reverse, key=lambda x: x if isinstance(x, int) else x[1])
    else:
        items = sorted(items, key=lambda x: x if isinstance(x, int) else x[0])

    prev_start_cp = prev_end_cp = None
    for cp in items:
        if isinstance(cp, (tuple, list)):
            start_cp, end_cp = cp
        else:
            start_cp = end_cp = cp

        try:
            if reverse:
                if prev_start_cp - 1 <= end_cp:
                    prev_start_cp = min(prev_start_cp, start_cp)
                    continue
            elif prev_end_cp + 1 >= start_cp:
                prev_end_cp = max(prev_end_cp, end_cp)
                continue
        except TypeError:
            prev_start_cp, prev_end_cp = start_cp, end_cp
        else:
            if prev_end_cp > prev_start_cp:
                yield prev_start_cp, prev_end_cp
                prev_start_cp, prev_end_cp = start_cp, end_cp
            else:
                yield prev_start_cp
                prev_start_cp, prev_end_cp = start_cp, end_cp
    else:
        if prev_start_cp is not None:
            if prev_end_cp > prev_start_cp:
                yield prev_start_cp, prev_end_cp
            else:
                yield prev_start_cp


class UnicodeSubset(MutableSet):
    """
    Represent a subset of Unicode code points, implemented with an ordered list of integer values
    and ranges. It manages character ranges for adding or for discarding elements from a string
    and for a compressed representation.
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
            self._code_points = args[0].code_points.copy()
        else:
            self._code_points = list()
            self.update(args[0])

    @property
    def code_points(self):
        return self._code_points

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, str(self._code_points), id(self))

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join(code_point_repr(cp) for cp in self._code_points)

    if PY3:
        __str__ = __unicode__

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return UnicodeSubset(self._code_points)

    def __reversed__(self):
        for item in reversed(self._code_points):
            if isinstance(item, tuple):
                for cp in range(item[1], item[0] - 1, -1):
                    yield cp
            else:
                yield item

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

    #
    # MutableSet's abstract methods implementation
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

    def update(self, *others):
        for values in others:
            if isinstance(values, (str, unicode_type, bytes)):
                for cp in iter_code_points(parse_character_group(values), reverse=True):
                    self.add(cp)
            else:
                for cp in iter_code_points(values, reverse=True):
                    self.add(cp)

    def add(self, value):
        if isinstance(value, (tuple, list)):
            if len(value) > 2 or value[0] > value[1] or value[0] < 0 or value[1] > maxunicode:
                raise XMLSchemaValueError("not a Unicode code point range: %r" % value)
            start_value, end_value = value
        elif isinstance(value, int):
            if not (0 <= value <= maxunicode):
                raise XMLSchemaValueError("not a Unicode code point: %r" % value)
            start_value = end_value = value
        else:
            raise XMLSchemaTypeError("%r: an int, a tuple or a list required, not %r." % (value, type(value)))

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
                    if isinstance(value, list):
                        code_points.insert(pos, tuple(value))
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
            if isinstance(value, list):
                self._code_points.append(tuple(value))
            else:
                self._code_points.append(value)

    def difference_update(self, *others):
        for values in others:
            if isinstance(values, (str, unicode_type, bytes)):
                for cp in iter_code_points(parse_character_group(values), reverse=True):
                    self.discard(cp)
            else:
                for cp in iter_code_points(values, reverse=True):
                    self.discard(cp)

    def discard(self, value):
        if isinstance(value, (tuple, list)):
            if len(value) > 2 or value[0] > value[1] or value[0] < 0 or value[1] > maxunicode:
                raise XMLSchemaValueError("not a Unicode code point range: %r" % value)
            start_value, end_value = value
        elif isinstance(value, int):
            if not (0 <= value <= maxunicode):
                raise XMLSchemaValueError("not a Unicode code point: %r" % value)
            start_value = end_value = value
        else:
            raise XMLSchemaTypeError("%r: an int, a tuple or a list required, not %r." % (value, type(value)))

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

    #
    # MutableSet's mixin methods override
    def clear(self):
        del self._code_points[:]

    def __eq__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            return self._code_points == other._code_points
        else:
            return self._code_points == other

    def __ior__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            other = reversed(other.code_points)
        else:
            other = iter_code_points(other, reverse=True)

        for cp in other:
            self.add(cp)
        return self

    def __isub__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            other = reversed(other.code_points)
        else:
            other = iter_code_points(other, reverse=True)

        for cp in other:
            self.discard(cp)
        return self

    def __sub__(self, other):
        obj = self.copy()
        return obj.__isub__(other)

    __rsub__ = __sub__

    def __iand__(self, other):
        for value in (self - other):
            self.discard(value)
        return self

    def __ixor__(self, other):
        if other is self:
            self.clear()
            return self
        elif not isinstance(other, Iterable):
            return NotImplemented
        elif not isinstance(other, UnicodeSubset):
            other = UnicodeSubset(other)

        for value in other:
            if value in self:
                self.discard(value)
            else:
                self.add(value)
        return self


def unicode_category_sequencer(code_points):
    """
    Generate a sequence of unicode categories associations.

    :param code_points: An iterable with code points.
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
        if maxunicode < UCS4_MAXUNICODE:
            raise XMLSchemaValueError()
        with open(filename, 'r') as fp:
            categories = json.load(fp)
    except (IOError, SystemError, ValueError):
        from collections import defaultdict
        categories = defaultdict(list)
        for key, cp in unicode_category_sequencer(range(maxunicode + 1)):
            categories[key].append(cp)
    else:
        for values in categories.values():
            for k in range(len(values)):
                if isinstance(values[k], list):
                    values[k] = tuple(values[k])

    # Add general categories code points
    categories['C'] = categories['Cc'] + categories['Cf'] + categories['Cs'] + categories['Co'] + categories['Cn']
    categories['L'] = categories['Lu'] + categories['Ll'] + categories['Lt'] + categories['Lm'] + categories['Lo']
    categories['M'] = categories['Mn'] + categories['Mc'] + categories['Me']
    categories['N'] = categories['Nd'] + categories['Nl'] + categories['No']
    categories['P'] = categories['Pc'] + categories['Pd'] + categories['Ps'] + \
        categories['Pe'] + categories['Pi'] + categories['Pf'] + categories['Po']
    categories['S'] = categories['Sm'] + categories['Sc'] + categories['Sk'] + categories['So']
    categories['Z'] = categories['Zs'] + categories['Zl'] + categories['Zp']

    return {k: UnicodeSubset(v) for k, v in categories.items()}


UNICODE_CATEGORIES = get_unicode_categories()

UNICODE_BLOCKS = {
    'IsBasicLatin': UnicodeSubset(u'\u0000-\u007F'),
    'IsLatin-1Supplement': UnicodeSubset(u'\u0080-\u00FF'),
    'IsLatinExtended-A': UnicodeSubset(u'\u0100-\u017F'),
    'IsLatinExtended-B': UnicodeSubset(u'\u0180-\u024F'),
    'IsIPAExtensions': UnicodeSubset(u'\u0250-\u02AF'),
    'IsSpacingModifierLetters': UnicodeSubset(u'\u02B0-\u02FF'),
    'IsCombiningDiacriticalMarks': UnicodeSubset(u'\u0300-\u036F'),
    'IsGreek': UnicodeSubset(u'\u0370-\u03FF'),
    'IsCyrillic': UnicodeSubset(u'\u0400-\u04FF'),
    'IsArmenian': UnicodeSubset(u'\u0530-\u058F'),
    'IsHebrew': UnicodeSubset(u'\u0590-\u05FF'),
    'IsArabic': UnicodeSubset(u'\u0600-\u06FF'),
    'IsSyriac': UnicodeSubset(u'\u0700-\u074F'),
    'IsThaana': UnicodeSubset(u'\u0780-\u07BF'),
    'IsDevanagari': UnicodeSubset(u'\u0900-\u097F'),
    'IsBengali': UnicodeSubset(u'\u0980-\u09FF'),
    'IsGurmukhi': UnicodeSubset(u'\u0A00-\u0A7F'),
    'IsGujarati': UnicodeSubset(u'\u0A80-\u0AFF'),
    'IsOriya': UnicodeSubset(u'\u0B00-\u0B7F'),
    'IsTamil': UnicodeSubset(u'\u0B80-\u0BFF'),
    'IsTelugu': UnicodeSubset(u'\u0C00-\u0C7F'),
    'IsKannada': UnicodeSubset(u'\u0C80-\u0CFF'),
    'IsMalayalam': UnicodeSubset(u'\u0D00-\u0D7F'),
    'IsSinhala': UnicodeSubset(u'\u0D80-\u0DFF'),
    'IsThai': UnicodeSubset(u'\u0E00-\u0E7F'),
    'IsLao': UnicodeSubset(u'\u0E80-\u0EFF'),
    'IsTibetan': UnicodeSubset(u'\u0F00-\u0FFF'),
    'IsMyanmar': UnicodeSubset(u'\u1000-\u109F'),
    'IsGeorgian': UnicodeSubset(u'\u10A0-\u10FF'),
    'IsHangulJamo': UnicodeSubset(u'\u1100-\u11FF'),
    'IsEthiopic': UnicodeSubset(u'\u1200-\u137F'),
    'IsCherokee': UnicodeSubset(u'\u13A0-\u13FF'),
    'IsUnifiedCanadianAboriginalSyllabics': UnicodeSubset(u'\u1400-\u167F'),
    'IsOgham': UnicodeSubset(u'\u1680-\u169F'),
    'IsRunic': UnicodeSubset(u'\u16A0-\u16FF'),
    'IsKhmer': UnicodeSubset(u'\u1780-\u17FF'),
    'IsMongolian': UnicodeSubset(u'\u1800-\u18AF'),
    'IsLatinExtendedAdditional': UnicodeSubset(u'\u1E00-\u1EFF'),
    'IsGreekExtended': UnicodeSubset(u'\u1F00-\u1FFF'),
    'IsGeneralPunctuation': UnicodeSubset(u'\u2000-\u206F'),
    'IsSuperscriptsandSubscripts': UnicodeSubset(u'\u2070-\u209F'),
    'IsCurrencySymbols': UnicodeSubset(u'\u20A0-\u20CF'),
    'IsCombiningMarksforSymbols': UnicodeSubset(u'\u20D0-\u20FF'),
    'IsLetterlikeSymbols': UnicodeSubset(u'\u2100-\u214F'),
    'IsNumberForms': UnicodeSubset(u'\u2150-\u218F'),
    'IsArrows': UnicodeSubset(u'\u2190-\u21FF'),
    'IsMathematicalOperators': UnicodeSubset(u'\u2200-\u22FF'),
    'IsMiscellaneousTechnical': UnicodeSubset(u'\u2300-\u23FF'),
    'IsControlPictures': UnicodeSubset(u'\u2400-\u243F'),
    'IsOpticalCharacterRecognition': UnicodeSubset(u'\u2440-\u245F'),
    'IsEnclosedAlphanumerics': UnicodeSubset(u'\u2460-\u24FF'),
    'IsBoxDrawing': UnicodeSubset(u'\u2500-\u257F'),
    'IsBlockElements': UnicodeSubset(u'\u2580-\u259F'),
    'IsGeometricShapes': UnicodeSubset(u'\u25A0-\u25FF'),
    'IsMiscellaneousSymbols': UnicodeSubset(u'\u2600-\u26FF'),
    'IsDingbats': UnicodeSubset(u'\u2700-\u27BF'),
    'IsBraillePatterns': UnicodeSubset(u'\u2800-\u28FF'),
    'IsCJKRadicalsSupplement': UnicodeSubset(u'\u2E80-\u2EFF'),
    'IsKangxiRadicals': UnicodeSubset(u'\u2F00-\u2FDF'),
    'IsIdeographicDescriptionCharacters': UnicodeSubset(u'\u2FF0-\u2FFF'),
    'IsCJKSymbolsandPunctuation': UnicodeSubset(u'\u3000-\u303F'),
    'IsHiragana': UnicodeSubset(u'\u3040-\u309F'),
    'IsKatakana': UnicodeSubset(u'\u30A0-\u30FF'),
    'IsBopomofo': UnicodeSubset(u'\u3100-\u312F'),
    'IsHangulCompatibilityJamo': UnicodeSubset(u'\u3130-\u318F'),
    'IsKanbun': UnicodeSubset(u'\u3190-\u319F'),
    'IsBopomofoExtended': UnicodeSubset(u'\u31A0-\u31BF'),
    'IsEnclosedCJKLettersandMonths': UnicodeSubset(u'\u3200-\u32FF'),
    'IsCJKCompatibility': UnicodeSubset(u'\u3300-\u33FF'),
    'IsCJKUnifiedIdeographsExtensionA': UnicodeSubset(u'\u3400-\u4DB5'),
    'IsCJKUnifiedIdeographs': UnicodeSubset(u'\u4E00-\u9FFF'),
    'IsYiSyllables': UnicodeSubset(u'\uA000-\uA48F'),
    'IsYiRadicals': UnicodeSubset(u'\uA490-\uA4CF'),
    'IsHangulSyllables': UnicodeSubset(u'\uAC00-\uD7A3'),
    'IsHighSurrogates': UnicodeSubset(u'\uD800-\uDB7F'),
    'IsHighPrivateUseSurrogates': UnicodeSubset(u'\uDB80-\uDBFF'),
    'IsLowSurrogates': UnicodeSubset(u'\uDC00-\uDFFF'),
    'IsPrivateUse': UnicodeSubset(u'\uE000-\uF8FF'),
    'IsCJKCompatibilityIdeographs': UnicodeSubset(u'\uF900-\uFAFF'),
    'IsAlphabeticPresentationForms': UnicodeSubset(u'\uFB00-\uFB4F'),
    'IsArabicPresentationForms-A': UnicodeSubset(u'\uFB50-\uFDFF'),
    'IsCombiningHalfMarks': UnicodeSubset(u'\uFE20-\uFE2F'),
    'IsCJKCompatibilityForms': UnicodeSubset(u'\uFE30-\uFE4F'),
    'IsSmallFormVariants': UnicodeSubset(u'\uFE50-\uFE6F'),
    'IsArabicPresentationForms-B': UnicodeSubset(u'\uFE70-\uFEFE'),
    'IsSpecials': UnicodeSubset(u'\uFEFF\uFFF0-\uFFFD'),
    'IsHalfwidthandFullwidthForms': UnicodeSubset(u'\uFF00-\uFFEF')
}

if maxunicode == UCS4_MAXUNICODE:
    UNICODE_BLOCKS['IsPrivateUse'].update(u'\U000F0000-\U0010FFFD'),
    UNICODE_BLOCKS.update({
        'IsOldItalic': UnicodeSubset(u'\U00010300-\U0001032F'),
        'IsGothic': UnicodeSubset(u'\U00010330-\U0001034F'),
        'IsDeseret': UnicodeSubset(u'\U00010400-\U0001044F'),
        'IsByzantineMusicalSymbols': UnicodeSubset(u'\U0001D000-\U0001D0FF'),
        'IsMusicalSymbols': UnicodeSubset(u'\U0001D100-\U0001D1FF'),
        'IsMathematicalAlphanumericSymbols': UnicodeSubset(u'\U0001D400-\U0001D7FF'),
        'IsCJKUnifiedIdeographsExtensionB': UnicodeSubset(u'\U00020000-\U0002A6D6'),
        'IsCJKCompatibilityIdeographsSupplement': UnicodeSubset(u'\U0002F800-\U0002FA1F'),
        'IsTags': UnicodeSubset(u'\U000E0000-\U000E007F')
    })
