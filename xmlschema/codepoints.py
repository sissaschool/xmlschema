# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
from __future__ import unicode_literals

import json
import os
from sys import maxunicode

from .compat import PY3, unicode_chr, string_base_type, Iterable, MutableSet
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaRegexError

CHARACTER_GROUP_ESCAPED = {ord(c) for c in r'-|.^?*+{}()[]\\'}
"""Code Points of escaped chars in a character group."""

UCS4_MAXUNICODE = 1114111


def code_point_order(cp):
    """Ordering function for code points."""
    return cp if isinstance(cp, int) else cp[0]


def code_point_reverse_order(cp):
    """Reverse ordering function for code points."""
    return cp if isinstance(cp, int) else cp[1] - 1


def iter_code_points(code_points, reverse=False):
    """
    Iterates a code points sequence. The code points are accorpated in ranges when are contiguous.

    :param code_points: an iterable with code points and code point ranges.
    :param reverse: if `True` reverses the order of the sequence.
    :return: yields code points or code point ranges.
    """
    start_cp = end_cp = None
    if reverse:
        code_points = sorted(code_points, key=code_point_reverse_order, reverse=True)
    else:
        code_points = sorted(code_points, key=code_point_order)

    for cp in code_points:
        if isinstance(cp, int):
            cp = cp, cp + 1

        if start_cp is None:
            start_cp, end_cp = cp
            continue
        elif reverse:
            if start_cp <= cp[1]:
                start_cp = min(start_cp, cp[0])
                continue
        elif end_cp >= cp[0]:
            end_cp = max(end_cp, cp[1])
            continue

        if end_cp > start_cp + 1:
            yield start_cp, end_cp
        else:
            yield start_cp
        start_cp, end_cp = cp
    else:
        if start_cp is not None:
            if end_cp > start_cp + 1:
                yield start_cp, end_cp
            else:
                yield start_cp


def check_code_point(cp):
    """
    Checks a code point or code point range.

    :return: a valid code point range.
    """
    if isinstance(cp, int):
        if not (0 <= cp <= maxunicode):
            raise XMLSchemaValueError("not a Unicode code point: %r" % cp)
        return cp, cp + 1
    else:
        if not (0 <= cp[0] < cp[1] <= maxunicode + 1) \
                or not isinstance(cp[0], int) or not isinstance(cp[1], int):
            raise XMLSchemaValueError("not a Unicode code point range: %r" % cp)
        return cp


def code_point_repr(cp):
    """
    Returns the string representation of a code point.

    :param cp: an integer or a tuple with at least two integers. Values must be in interval [0, sys.maxunicode].
    """
    if isinstance(cp, int):
        if cp in CHARACTER_GROUP_ESCAPED:
            return r'\%s' % unicode_chr(cp)
        return unicode_chr(cp)

    if cp[0] in CHARACTER_GROUP_ESCAPED:
        start_char = r'\%s' % unicode_chr(cp[0])
    else:
        start_char = unicode_chr(cp[0])

    end_cp = cp[1] - 1  # Character ranges include the right bound
    if end_cp in CHARACTER_GROUP_ESCAPED:
        end_char = r'\%s' % unicode_chr(end_cp)
    else:
        end_char = unicode_chr(end_cp)

    if end_cp > cp[0] + 1:
        return '%s-%s' % (start_char, end_char)
    else:
        return start_char + end_char


def iterparse_character_group(s, expand_ranges=False):
    """
    Parse a regex character group part, generating a sequence of code points
    and code points ranges. An unescaped hyphen (-) that is not at the start
    or at the and is interpreted as range specifier.

    :param s: a string representing a character group part.
    :param expand_ranges: if set to `True` then expands character ranges.
    :return: yields integers or couples of integers.
    """
    escaped = False
    on_range = False
    char = None
    length = len(s)
    string_iter = iter(range(len(s)))
    for k in string_iter:
        if k == 0:
            char = s[0]
            if char == '\\':
                escaped = True
            elif char in r'[]' and length > 1:
                raise XMLSchemaRegexError("bad character %r at position 0" % char)
            elif expand_ranges:
                yield ord(char)
            elif length <= 2 or s[1] != '-':
                yield ord(char)
        elif s[k] == '-':
            if escaped or (k == length - 1):
                char = s[k]
                yield ord(char)
                escaped = False
            elif on_range:
                char = s[k]
                yield ord(char)
                on_range = False
            else:
                # Parse character range
                on_range = True
                try:
                    k = next(string_iter)
                    end_char = s[k]
                    if end_char == '\\' and (k < length - 1):
                        if s[k + 1] in r'-|.^?*+{}()[]':
                            k = next(string_iter)
                            end_char = s[k]
                        elif s[k + 1] in r'sSdDiIcCwWpP':
                            msg = "bad character range '%s-\\%s' at position %d: %r" % (char, s[k + 1], k - 2, s)
                            raise XMLSchemaRegexError(msg)
                except StopIteration:
                    msg = "bad character range '%s-%s' at position %d: %r" % (char, s[-1], k - 2, s)
                    raise XMLSchemaRegexError(msg)

                if ord(char) > ord(end_char):
                    msg = "bad character range '%s-%s' at position %d: %r" % (char, end_char, k - 2, s)
                    raise XMLSchemaRegexError(msg)
                elif expand_ranges:
                    for cp in range(ord(char) + 1, ord(end_char) + 1):
                        yield cp
                else:
                    yield ord(char), ord(end_char) + 1
        elif s[k] in r'|.^?*+{}()':
            if escaped:
                escaped = False
            on_range = False
            char = s[k]
            yield ord(char)
        elif s[k] in r'[]':
            if not escaped and length > 1:
                raise XMLSchemaRegexError("bad character %r at position %d" % (s[k], k))
            escaped = on_range = False
            char = s[k]
            if k >= length - 2 or s[k + 1] != '-':
                yield ord(char)
        elif s[k] == '\\':
            if escaped:
                escaped = on_range = False
                char = '\\'
                yield ord(char)
            else:
                escaped = True
        else:
            if escaped:
                escaped = False
                yield ord('\\')
            on_range = False
            char = s[k]
            if k >= length - 2 or s[k + 1] != '-':
                yield ord(char)
    if escaped:
        yield ord('\\')


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

    @classmethod
    def fromlist(cls, code_points):
        subset = cls()
        subset._code_points = sorted(code_points, key=code_point_order)
        return subset

    @property
    def code_points(self):
        return self._code_points

    def __repr__(self):
        return "<%s %r at %d>" % (self.__class__.__name__, str(self._code_points), id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return ''.join(code_point_repr(cp) for cp in self._code_points)

    if PY3:
        __str__ = __unicode__

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return UnicodeSubset(self._code_points)

    def __reversed__(self):
        for item in reversed(self._code_points):
            if isinstance(item, int):
                yield item
            else:
                for cp in reversed(range(item[0], item[1])):
                    yield cp

    def complement(self):
        last_cp = 0
        for cp in self._code_points:
            if last_cp > maxunicode:
                break
            elif isinstance(cp, int):
                cp = cp, cp + 1

            diff = cp[0] - last_cp
            if diff > 2:
                yield last_cp, cp[0]
            elif diff == 2:
                yield last_cp
                yield last_cp + 1
            elif diff == 1:
                yield last_cp
            elif diff != 0:
                raise XMLSchemaValueError("instance code points unordered")
            last_cp = cp[1]

        if last_cp < maxunicode:
            yield last_cp, maxunicode + 1
        elif last_cp == maxunicode:
            yield maxunicode

    def iter_characters(self):
        return map(chr, self.__iter__())

    #
    # MutableSet's abstract methods implementation
    def __contains__(self, value):
        if not isinstance(value, int):
            try:
                value = ord(value)
            except TypeError:
                raise XMLSchemaTypeError("%r: argument must be a code point or a character." % value)

        for cp in self._code_points:
            if not isinstance(cp, int):
                if cp[0] > value:
                    return False
                elif cp[1] <= value:
                    continue
                else:
                    return True
            elif cp > value:
                return False
            elif cp == value:
                return True
        return False

    def __iter__(self):
        for cp in self._code_points:
            if isinstance(cp, int):
                yield cp
            else:
                for k in range(*cp):
                    yield k

    def __len__(self):
        k = 0
        for _ in self:
            k += 1
        return k

    def update(self, *others):
        for value in others:
            if isinstance(value, string_base_type):
                for cp in iter_code_points(iterparse_character_group(value), reverse=True):
                    self.add(cp)
            else:
                for cp in iter_code_points(value, reverse=True):
                    self.add(cp)

    def add(self, value):
        start_value, end_value = check_code_point(value)
        code_points = self._code_points
        last_index = len(code_points) - 1
        for k, cp in enumerate(code_points):
            if isinstance(cp, int):
                cp = cp, cp + 1

            if end_value < cp[0]:
                code_points.insert(k, value if isinstance(value, int) else tuple(value))
            elif start_value > cp[1]:
                continue
            elif end_value > cp[1]:
                if k == last_index:
                    code_points[k] = min(cp[0], start_value), end_value
                else:
                    next_cp = code_points[k + 1]
                    higher_bound = next_cp if isinstance(next_cp, int) else next_cp[0]
                    if end_value <= higher_bound:
                        code_points[k] = min(cp[0], start_value), end_value
                    else:
                        code_points[k] = min(cp[0], start_value), higher_bound
                        start_value = higher_bound
                        continue
            elif start_value < cp[0]:
                code_points[k] = start_value, cp[1]
            break
        else:
            self._code_points.append(tuple(value) if isinstance(value, list) else value)

    def difference_update(self, *others):
        for value in others:
            if isinstance(value, string_base_type):
                for cp in iter_code_points(iterparse_character_group(value), reverse=True):
                    self.discard(cp)
            else:
                for cp in iter_code_points(value, reverse=True):
                    self.discard(cp)

    def discard(self, value):
        start_cp, end_cp = check_code_point(value)
        code_points = self._code_points
        for k in reversed(range(len(code_points))):
            cp = code_points[k]
            if isinstance(cp, int):
                cp = cp, cp + 1

            if start_cp >= cp[1]:
                break
            elif end_cp >= cp[1]:
                if start_cp <= cp[0]:
                    del code_points[k]
                elif start_cp - cp[0] > 1:
                    code_points[k] = cp[0], start_cp
                else:
                    code_points[k] = cp[0]
            elif end_cp > cp[0]:
                if start_cp <= cp[0]:
                    if cp[1] - end_cp > 1:
                        code_points[k] = end_cp, cp[1]
                    else:
                        code_points[k] = cp[1] - 1
                else:
                    if cp[1] - end_cp > 1:
                        code_points.insert(k + 1, (end_cp, cp[1]))
                    else:
                        code_points.insert(k + 1, cp[1] - 1)
                    if start_cp - cp[0] > 1:
                        code_points[k] = cp[0], start_cp
                    else:
                        code_points[k] = cp[0]

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
            other = reversed(other._code_points)
        else:
            other = iter_code_points(other, reverse=True)

        for cp in other:
            self.add(cp)
        return self

    def __isub__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        elif isinstance(other, UnicodeSubset):
            other = reversed(other._code_points)
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


def get_unicodedata_categories():
    """
    Extracts Unicode categories information from unicodedata library. Each category is
    represented with an ordered list containing code points and code point ranges.

    :return: a dictionary with category names as keys and lists as values.
    """
    from unicodedata import category

    categories = {k: [] for k in (
        'C', 'Cc', 'Cf', 'Cs', 'Co', 'Cn',
        'L', 'Lu', 'Ll', 'Lt', 'Lm', 'Lo',
        'M', 'Mn', 'Mc', 'Me',
        'N', 'Nd', 'Nl', 'No',
        'P', 'Pc', 'Pd', 'Ps', 'Pe', 'Pi', 'Pf', 'Po',
        'S', 'Sm', 'Sc', 'Sk', 'So',
        'Z', 'Zs', 'Zl', 'Zp'
    )}

    minor_category = 'Cc'
    start_cp, next_cp = 0, 1
    for cp in range(maxunicode + 1):
        if category(unicode_chr(cp)) != minor_category:
            if cp > next_cp:
                categories[minor_category].append((start_cp, cp))
                categories[minor_category[0]].append(categories[minor_category][-1])
            else:
                categories[minor_category].append(start_cp)
                categories[minor_category[0]].append(start_cp)

            minor_category = category(unicode_chr(cp))
            start_cp, next_cp = cp, cp + 1
    else:
        if next_cp == maxunicode + 1:
            categories[minor_category].append(start_cp)
            categories[minor_category[0]].append(start_cp)
        else:
            categories[minor_category].append((start_cp, maxunicode + 1))
            categories[minor_category[0]].append(categories[minor_category][-1])

    return categories


def save_unicode_categories(filename=None):
    """
    Save Unicode categories to a JSON file.

    :param filename: the JSON file to save. If it's `None` uses the predefined filename
    'unicode_categories.json' and try to save in the directory of this module.
    """
    if filename is None:
        filename = os.path.join(os.path.dirname(__file__), 'unicode_categories.json')

    print("Saving Unicode categories to %r" % filename)
    with open(filename, 'w') as fp:
        json.dump(get_unicodedata_categories(), fp)


def build_unicode_categories(filename=None):
    """
    Builds the Unicode categories as `UnicodeSubset` instances. For a fast building a pre-built
    JSON file with Unicode categories data can be used. If the JSON file is missing or is not
    accessible the categories data is rebuild using `unicodedata.category()` API.

    :param filename: the name of the JSON file to load for a fast building of the categories. \
    If not provided the predefined filename  'unicode_categories.json' is used.
    :return: a dictionary that associates Unicode category names with `UnicodeSubset` instances.
    """
    if maxunicode < UCS4_MAXUNICODE:
        categories = get_unicodedata_categories()  # for Python 2.7
    else:
        if filename is None:
            filename = os.path.join(os.path.dirname(__file__), 'unicode_categories.json')
        try:
            with open(filename, 'r') as fp:
                categories = json.load(fp)
        except (IOError, SystemError, ValueError):
            categories = get_unicodedata_categories()
        else:
            if any(not v for v in categories):
                categories = get_unicodedata_categories()

    return {k: UnicodeSubset.fromlist(v) for k, v in categories.items()}


UNICODE_CATEGORIES = build_unicode_categories()


UNICODE_BLOCKS = {
    'IsBasicLatin': UnicodeSubset('\u0000-\u007F'),
    'IsLatin-1Supplement': UnicodeSubset('\u0080-\u00FF'),
    'IsLatinExtended-A': UnicodeSubset('\u0100-\u017F'),
    'IsLatinExtended-B': UnicodeSubset('\u0180-\u024F'),
    'IsIPAExtensions': UnicodeSubset('\u0250-\u02AF'),
    'IsSpacingModifierLetters': UnicodeSubset('\u02B0-\u02FF'),
    'IsCombiningDiacriticalMarks': UnicodeSubset('\u0300-\u036F'),
    'IsGreek': UnicodeSubset('\u0370-\u03FF'),
    'IsCyrillic': UnicodeSubset('\u0400-\u04FF'),
    'IsArmenian': UnicodeSubset('\u0530-\u058F'),
    'IsHebrew': UnicodeSubset('\u0590-\u05FF'),
    'IsArabic': UnicodeSubset('\u0600-\u06FF'),
    'IsSyriac': UnicodeSubset('\u0700-\u074F'),
    'IsThaana': UnicodeSubset('\u0780-\u07BF'),
    'IsDevanagari': UnicodeSubset('\u0900-\u097F'),
    'IsBengali': UnicodeSubset('\u0980-\u09FF'),
    'IsGurmukhi': UnicodeSubset('\u0A00-\u0A7F'),
    'IsGujarati': UnicodeSubset('\u0A80-\u0AFF'),
    'IsOriya': UnicodeSubset('\u0B00-\u0B7F'),
    'IsTamil': UnicodeSubset('\u0B80-\u0BFF'),
    'IsTelugu': UnicodeSubset('\u0C00-\u0C7F'),
    'IsKannada': UnicodeSubset('\u0C80-\u0CFF'),
    'IsMalayalam': UnicodeSubset('\u0D00-\u0D7F'),
    'IsSinhala': UnicodeSubset('\u0D80-\u0DFF'),
    'IsThai': UnicodeSubset('\u0E00-\u0E7F'),
    'IsLao': UnicodeSubset('\u0E80-\u0EFF'),
    'IsTibetan': UnicodeSubset('\u0F00-\u0FFF'),
    'IsMyanmar': UnicodeSubset('\u1000-\u109F'),
    'IsGeorgian': UnicodeSubset('\u10A0-\u10FF'),
    'IsHangulJamo': UnicodeSubset('\u1100-\u11FF'),
    'IsEthiopic': UnicodeSubset('\u1200-\u137F'),
    'IsCherokee': UnicodeSubset('\u13A0-\u13FF'),
    'IsUnifiedCanadianAboriginalSyllabics': UnicodeSubset('\u1400-\u167F'),
    'IsOgham': UnicodeSubset('\u1680-\u169F'),
    'IsRunic': UnicodeSubset('\u16A0-\u16FF'),
    'IsKhmer': UnicodeSubset('\u1780-\u17FF'),
    'IsMongolian': UnicodeSubset('\u1800-\u18AF'),
    'IsLatinExtendedAdditional': UnicodeSubset('\u1E00-\u1EFF'),
    'IsGreekExtended': UnicodeSubset('\u1F00-\u1FFF'),
    'IsGeneralPunctuation': UnicodeSubset('\u2000-\u206F'),
    'IsSuperscriptsandSubscripts': UnicodeSubset('\u2070-\u209F'),
    'IsCurrencySymbols': UnicodeSubset('\u20A0-\u20CF'),
    'IsCombiningMarksforSymbols': UnicodeSubset('\u20D0-\u20FF'),
    'IsLetterlikeSymbols': UnicodeSubset('\u2100-\u214F'),
    'IsNumberForms': UnicodeSubset('\u2150-\u218F'),
    'IsArrows': UnicodeSubset('\u2190-\u21FF'),
    'IsMathematicalOperators': UnicodeSubset('\u2200-\u22FF'),
    'IsMiscellaneousTechnical': UnicodeSubset('\u2300-\u23FF'),
    'IsControlPictures': UnicodeSubset('\u2400-\u243F'),
    'IsOpticalCharacterRecognition': UnicodeSubset('\u2440-\u245F'),
    'IsEnclosedAlphanumerics': UnicodeSubset('\u2460-\u24FF'),
    'IsBoxDrawing': UnicodeSubset('\u2500-\u257F'),
    'IsBlockElements': UnicodeSubset('\u2580-\u259F'),
    'IsGeometricShapes': UnicodeSubset('\u25A0-\u25FF'),
    'IsMiscellaneousSymbols': UnicodeSubset('\u2600-\u26FF'),
    'IsDingbats': UnicodeSubset('\u2700-\u27BF'),
    'IsBraillePatterns': UnicodeSubset('\u2800-\u28FF'),
    'IsCJKRadicalsSupplement': UnicodeSubset('\u2E80-\u2EFF'),
    'IsKangxiRadicals': UnicodeSubset('\u2F00-\u2FDF'),
    'IsIdeographicDescriptionCharacters': UnicodeSubset('\u2FF0-\u2FFF'),
    'IsCJKSymbolsandPunctuation': UnicodeSubset('\u3000-\u303F'),
    'IsHiragana': UnicodeSubset('\u3040-\u309F'),
    'IsKatakana': UnicodeSubset('\u30A0-\u30FF'),
    'IsBopomofo': UnicodeSubset('\u3100-\u312F'),
    'IsHangulCompatibilityJamo': UnicodeSubset('\u3130-\u318F'),
    'IsKanbun': UnicodeSubset('\u3190-\u319F'),
    'IsBopomofoExtended': UnicodeSubset('\u31A0-\u31BF'),
    'IsEnclosedCJKLettersandMonths': UnicodeSubset('\u3200-\u32FF'),
    'IsCJKCompatibility': UnicodeSubset('\u3300-\u33FF'),
    'IsCJKUnifiedIdeographsExtensionA': UnicodeSubset('\u3400-\u4DB5'),
    'IsCJKUnifiedIdeographs': UnicodeSubset('\u4E00-\u9FFF'),
    'IsYiSyllables': UnicodeSubset('\uA000-\uA48F'),
    'IsYiRadicals': UnicodeSubset('\uA490-\uA4CF'),
    'IsHangulSyllables': UnicodeSubset('\uAC00-\uD7A3'),
    'IsHighSurrogates': UnicodeSubset('\uD800-\uDB7F'),
    'IsHighPrivateUseSurrogates': UnicodeSubset('\uDB80-\uDBFF'),
    'IsLowSurrogates': UnicodeSubset('\uDC00-\uDFFF'),
    'IsPrivateUse': UnicodeSubset('\uE000-\uF8FF'),
    'IsCJKCompatibilityIdeographs': UnicodeSubset('\uF900-\uFAFF'),
    'IsAlphabeticPresentationForms': UnicodeSubset('\uFB00-\uFB4F'),
    'IsArabicPresentationForms-A': UnicodeSubset('\uFB50-\uFDFF'),
    'IsCombiningHalfMarks': UnicodeSubset('\uFE20-\uFE2F'),
    'IsCJKCompatibilityForms': UnicodeSubset('\uFE30-\uFE4F'),
    'IsSmallFormVariants': UnicodeSubset('\uFE50-\uFE6F'),
    'IsArabicPresentationForms-B': UnicodeSubset('\uFE70-\uFEFE'),
    'IsSpecials': UnicodeSubset('\uFEFF\uFFF0-\uFFFD'),
    'IsHalfwidthandFullwidthForms': UnicodeSubset('\uFF00-\uFFEF')
}

if maxunicode == UCS4_MAXUNICODE:
    UNICODE_BLOCKS['IsPrivateUse'].update('\U000F0000-\U0010FFFD'),
    UNICODE_BLOCKS.update({
        'IsOldItalic': UnicodeSubset('\U00010300-\U0001032F'),
        'IsGothic': UnicodeSubset('\U00010330-\U0001034F'),
        'IsDeseret': UnicodeSubset('\U00010400-\U0001044F'),
        'IsByzantineMusicalSymbols': UnicodeSubset('\U0001D000-\U0001D0FF'),
        'IsMusicalSymbols': UnicodeSubset('\U0001D100-\U0001D1FF'),
        'IsMathematicalAlphanumericSymbols': UnicodeSubset('\U0001D400-\U0001D7FF'),
        'IsCJKUnifiedIdeographsExtensionB': UnicodeSubset('\U00020000-\U0002A6D6'),
        'IsCJKCompatibilityIdeographsSupplement': UnicodeSubset('\U0002F800-\U0002FA1F'),
        'IsTags': UnicodeSubset('\U000E0000-\U000E007F')
    })


def unicode_subset(name, block_safe=False):
    if name.startswith('Is'):
        try:
            return UNICODE_BLOCKS[name]
        except KeyError:
            if block_safe:
                return UnicodeSubset.fromlist([0, maxunicode])
            raise XMLSchemaRegexError("%r doesn't match to any Unicode block." % name)
    else:
        try:
            return UNICODE_CATEGORIES[name]
        except KeyError:
            raise XMLSchemaRegexError("%r doesn't match to any Unicode category." % name)
