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
This module parse and translate XML regular expressions to Python regex syntax.
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
        elif isinstance(args[0], UnicodeSubset):
            self._store = args[0].copy()
        elif isinstance(args[0], set):
            self._store = args[0]   # assignment if initialized with another set
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

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return self._store.copy()


def get_unicode_categories():
    from unicodedata import category
    from collections import defaultdict

    unicode_categories = defaultdict(set)
    for cp in range(maxunicode + 1):
        unicode_categories[category(chr(cp))].add(cp)
    return {k: UnicodeSubset(v) for k, v in unicode_categories.items()}


UNICODE_CATEGORIES = get_unicode_categories()


def get_unicode_subset(ref):
    if ref == 'C':
        subset = UNICODE_CATEGORIES['Cc'].copy()
        subset |= UNICODE_CATEGORIES['Cf']
        subset |= UNICODE_CATEGORIES['Cs']
        subset |= UNICODE_CATEGORIES['Co']
        subset |= UNICODE_CATEGORIES['Cn']
        return subset
    if ref == 'L':
        subset = UNICODE_CATEGORIES['Lu'].copy()
        subset |= UNICODE_CATEGORIES['Ll']
        subset |= UNICODE_CATEGORIES['Lt']
        subset |= UNICODE_CATEGORIES['Lm']
        subset |= UNICODE_CATEGORIES['Lo']
        return subset
    elif ref == 'M':
        subset = UNICODE_CATEGORIES['Mn'].copy()
        subset |= UNICODE_CATEGORIES['Mc']
        subset |= UNICODE_CATEGORIES['Me']
        return subset
    elif ref == 'N':
        subset = UNICODE_CATEGORIES['Nd'].copy()
        subset |= UNICODE_CATEGORIES['Nl']
        subset |= UNICODE_CATEGORIES['No']
        return subset
    elif ref == 'P':
        subset = UNICODE_CATEGORIES['Pc'].copy()
        subset |= UNICODE_CATEGORIES['Pd']
        subset |= UNICODE_CATEGORIES['Ps']
        subset |= UNICODE_CATEGORIES['Pe']
        subset |= UNICODE_CATEGORIES['Pi']
        subset |= UNICODE_CATEGORIES['Pf']
        subset |= UNICODE_CATEGORIES['Po']
        return subset
    elif ref == 'S':
        subset = UNICODE_CATEGORIES['Sm'].copy()
        subset |= UNICODE_CATEGORIES['Sc']
        subset |= UNICODE_CATEGORIES['Sk']
        subset |= UNICODE_CATEGORIES['So']
        return subset
    elif ref == 'Z':
        subset = UNICODE_CATEGORIES['Zs'].copy()
        subset |= UNICODE_CATEGORIES['Zl']
        subset |= UNICODE_CATEGORIES['Zp']
        return subset

    try:
        return UnicodeSubset(UNICODE_CATEGORIES[ref])
    except KeyError:
        if ref[:2] != 'Is' and ref[2:] not in CHARACTER_BLOCKS:
            raise XMLSchemaRegexError("invalid unicode block reference: %r" % ref)
        return UnicodeSubset(CHARACTER_BLOCKS[ref[2:]])


class XsdRegexCharGroup(MutableSet):
    """
    A set subclass to represent XML Schema regex character groups.
    """
    _re_char_group = re.compile(r'(\\[sSdDiIcCwW]|\\[pP]{[a-zA-Z\-0-9]+})')
    _re_unicode_ref = re.compile(r'\\([pP])\{(\w+)\}')

    def __init__(self, *args):
        self.positive = UnicodeSubset()
        self.negative = UnicodeSubset()
        for char in args:
            self.add(char)

    def __repr__(self):
        return u"<%s %r at %d>" % (self.__class__.__name__, self.get_char_class(), id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.negative:
            if self.positive:
                max_code_point = max(max(self.positive), max(self.negative))
            else:
                max_code_point = max(self.negative)
            if max_code_point < maxunicode:
                gen_char_group = (
                    cp for cp in range(max_code_point + 1)
                    if cp in self.positive or cp not in self.negative
                )
                return u''.join(generate_character_group(
                    chain(gen_char_group, (cp for cp in [max_code_point + 1] * 2))
                ))
        return u''.join(generate_character_group(iter(self)))

    if PY3:
        __str__ = __unicode__

    def __contains__(self, char):
        if self.negative:
            return ord(char) not in self.negative or ord(char) in self.positive
        return ord(char) in self.positive

    def __iter__(self):
        if self.negative:
            return (
                cp for cp in range(maxunicode + 1)
                if cp in self.positive or cp not in self.negative
            )
        return iter(sorted(self.positive))

    def __len__(self):
        return len(self.positive) + len(self.negative)

    # Operators override
    def __isub__(self, other):
        if self.negative:
            self.positive |= (other.negative - self.negative)
            if other.negative:
                self.negative.clear()
        elif other.negative:
            self.positive &= other.negative
        self.positive -= other.positive
        return self

    def add(self, s):
        for part in self._re_char_group.split(s):
            if part == '\\s':
                self.positive.add_string(' \n\t\r')
            elif part == '\\S':
                self.negative.add_string(' \n\t\r')
            elif part == '\\d':
                self.positive.add_string('0-9')
            elif part == '\\D':
                self.negative.add_string('0-9')
            elif part == '\\i':
                self.positive.add_string(I_SHORTCUT_REPLACE)
            elif part == '\\I':
                self.negative.add_string(I_SHORTCUT_REPLACE)
            elif part == '\\c':
                self.positive.add_string(C_SHORTCUT_REPLACE)
            elif part == '\\C':
                self.negative.add_string(C_SHORTCUT_REPLACE)
            elif part == '\\w':
                self.negative |= get_unicode_subset('P')
                self.negative |= get_unicode_subset('Z')
                self.negative |= get_unicode_subset('C')
            elif part == '\\W':
                self.positive |= get_unicode_subset('P')
                self.positive |= get_unicode_subset('Z')
                self.positive |= get_unicode_subset('C')
            elif self._re_unicode_ref.search(part) is not None:
                if part.startswith('\\p'):
                    print(part)
                    self.positive |= get_unicode_subset(part[3:-1])
                else:
                    self.negative |= get_unicode_subset(part[3:-1])
            else:
                self.positive.add_string(part)

    def discard(self, s):
        for part in self._re_char_group.split(s):
            if part == '\\s':
                self.positive.discard_string(' \n\t\r')
            elif part == '\\S':
                self.negative.discard_string(' \n\t\r')
            elif part == '\\d':
                self.positive.discard_string('0-9')
            elif part == '\\D':
                self.negative.discard_string('0-9')
            elif part == '\\i':
                self.positive.discard_string(I_SHORTCUT_REPLACE)
            elif part == '\\I':
                self.negative.discard_string(I_SHORTCUT_REPLACE)
            elif part == '\\c':
                self.positive.discard_string(C_SHORTCUT_REPLACE)
            elif part == '\\C':
                self.negative.discard_string(C_SHORTCUT_REPLACE)
            elif part == '\\w':
                self.negative -= get_unicode_subset('P')
                self.negative -= get_unicode_subset('Z')
                self.negative -= get_unicode_subset('C')
            elif part == '\\W':
                self.positive -= get_unicode_subset('P')
                self.positive -= get_unicode_subset('Z')
                self.positive -= get_unicode_subset('C')
            elif self._re_unicode_ref.search(part) is not None:
                if part.startswith('\\p'):
                    self.positive -= get_unicode_subset(part[3:-1])
                else:
                    self.negative -= get_unicode_subset(part[3:-1])
            else:
                self.positive.discard_string(part)

    def clear(self):
        self.positive.clear()
        self.negative.clear()

    def complement(self):
        self.positive, self.negative = self.negative, self.positive

    def get_char_class(self):
        if self.positive:
            return u'[%s]' % str(self)
        elif self.negative:
            return u'[^%s]' % str(self.negative)
        else:
            return u'[]'


def parse_character_class(xml_regex, start_pos):
    if xml_regex[start_pos] != '[':
        raise XMLSchemaRegexError(
            'not a character class at position %d: %r' % (start_pos, xml_regex)
        )
    pos = start_pos + 1

    if xml_regex[pos] == '^':
        pos += 1
        negative = True
    else:
        negative = False

    group_pos = pos
    while True:
        if xml_regex[pos] == '\\':
            pos += 2
        elif xml_regex[pos] == ']' or xml_regex[pos:pos + 2] == '-[':
            if pos == group_pos:
                raise XMLSchemaRegexError(
                    "empty character class at position %d: %r" % (start_pos, xml_regex)
                )
            char_group = XsdRegexCharGroup(xml_regex[group_pos:pos])
            if negative:
                char_group.complement()
            break
        else:
            pos += 1

    if xml_regex[pos] != ']':
        # Parse a group subtraction
        pos += 1
        subtracted_group, pos = parse_character_class(xml_regex, pos)
        pos += 1
        if xml_regex[pos] != ']':
            raise XMLSchemaRegexError(
                "unterminated character group at position %d: %r" % (start_pos, xml_regex)
            )
        char_group -= subtracted_group

    return char_group, pos


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
            try:
                char_group, pos = parse_character_class(xml_regex, pos)
                regex.append(char_group.get_char_class())
            except IndexError:
                raise XMLSchemaRegexError(
                    "unterminated character group at position %d: %r" % (pos, xml_regex)
                )
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
                        "truncated unicode block escape at position %d: %r" % (start_pos, xml_regex)
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
