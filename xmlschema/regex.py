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
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaRegexError, XMLSchemaKeyError
from .codepoints import UNICODE_CATEGORIES, UNICODE_BLOCKS

I_SHORTCUT_REPLACE = (
    u":A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF"
    u"\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

C_SHORTCUT_REPLACE = (
    u"\-.0-9:A-Z_a-z\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u037D\u037F-\u1FFF\u200C-"
    u"\u200D\u203F\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)


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


S_SHORTCUT_SET = {ord(e) for e in parse_character_group(' \n\t\r')}
D_SHORTCUT_SET = {ord(e) for e in parse_character_group('0-9')}
I_SHORTCUT_SET = {ord(e) for e in parse_character_group(I_SHORTCUT_REPLACE)}
C_SHORTCUT_SET = {ord(e) for e in parse_character_group(C_SHORTCUT_REPLACE)}
W_SHORTCUT_SET = UNICODE_CATEGORIES['P'] | UNICODE_CATEGORIES['Z'] | UNICODE_CATEGORIES['C']


def get_unicode_subset(key):
    try:
        return UNICODE_CATEGORIES[key]
    except KeyError:
        try:
            return UNICODE_BLOCKS[key]
        except KeyError:
            raise XMLSchemaKeyError("%r don't match to any Unicode category or block.")


class XsdRegexCharGroup(MutableSet):
    """
    A set subclass to represent XML Schema regex character groups.
    """
    _re_char_group = re.compile(r'(\\[sSdDiIcCwW]|\\[pP]{[a-zA-Z\-0-9]+})')
    _re_unicode_ref = re.compile(r'\\([pP]){([a-zA-Z\-0-9]+)}')

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
                self.positive |= S_SHORTCUT_SET
            elif part == '\\S':
                self.negative |= S_SHORTCUT_SET
            elif part == '\\d':
                self.positive |= D_SHORTCUT_SET
            elif part == '\\D':
                self.negative |= D_SHORTCUT_SET
            elif part == '\\i':
                self.positive |= I_SHORTCUT_SET
            elif part == '\\I':
                self.negative |= I_SHORTCUT_SET
            elif part == '\\c':
                self.positive |= C_SHORTCUT_SET
            elif part == '\\C':
                self.negative |= C_SHORTCUT_SET
            elif part == '\\w':
                self.positive |= W_SHORTCUT_SET
            elif part == '\\W':
                self.negative |= W_SHORTCUT_SET
            elif self._re_unicode_ref.search(part) is not None:
                if part.startswith('\\p'):
                    self.positive |= get_unicode_subset(part[3:-1])
                else:
                    self.negative |= get_unicode_subset(part[3:-1])
            else:
                self.positive.add_string(part)

    def discard(self, s):
        for part in self._re_char_group.split(s):
            if part == '\\s':
                self.positive -= S_SHORTCUT_SET
            elif part == '\\S':
                self.negative -= S_SHORTCUT_SET
            elif part == '\\d':
                self.positive -= D_SHORTCUT_SET
            elif part == '\\D':
                self.negative -= D_SHORTCUT_SET
            elif part == '\\i':
                self.positive -= I_SHORTCUT_REPLACE
            elif part == '\\I':
                self.negative -= I_SHORTCUT_REPLACE
            elif part == '\\c':
                self.positive -= C_SHORTCUT_REPLACE
            elif part == '\\C':
                self.negative -= C_SHORTCUT_REPLACE
            elif part == '\\w':
                self.positive -= W_SHORTCUT_SET
            elif part == '\\W':
                self.negative -= W_SHORTCUT_SET
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
            return u'[%s]' % unicode_type(self)
        elif self.negative:
            return u'[^%s]' % unicode_type(self.negative)
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


def get_python_regex(xml_regex, debug=False):
    """
    Get a Python's compatible regex from a XML regex expression.
    """
    if debug:
        import pdb
        pdb.set_trace()
    regex = ['^']
    pos = 0
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
            elif xml_regex[pos] == 'i':
                regex.append('[%s]' % I_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'I':
                regex.append('[^%s]' % I_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'c':
                regex.append('[%s]' % C_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'C':
                regex.append('[^%s]' % C_SHORTCUT_REPLACE)
            elif xml_regex[pos] in 'pP':
                start_pos = pos - 1
                try:
                    if xml_regex[pos + 1] != '{':
                        raise ValueError()
                    while xml_regex[pos] != '}':
                        pos += 1
                except (IndexError, ValueError):
                    raise XMLSchemaRegexError(
                        "truncated unicode block escape at position %d: %r" % (start_pos, xml_regex)
                    )
                p_shortcut_set = get_unicode_subset(xml_regex[start_pos + 3:pos])
                p_shortcut_replace = ''.join(generate_character_group(p_shortcut_set))
                if xml_regex[start_pos + 1] == 'p':
                    regex.append('[%s]' % p_shortcut_replace)
                else:
                    regex.append('[^%s]' % p_shortcut_replace)
            else:
                regex.append('\\%s' % xml_regex[pos])
        else:
            regex.append(ch)
        pos += 1

    regex.append(r'$')
    return u''.join(regex)
