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
Parse and translate XML regular expressions to Python regex syntax.
"""
from __future__ import unicode_literals
import re
from collections import MutableSet
from sys import maxunicode

from .compat import PY3, unicode_type, string_base_type
from .exceptions import XMLSchemaValueError, XMLSchemaRegexError
from .codepoints import UNICODE_CATEGORIES, UNICODE_BLOCKS, UnicodeSubset

_UNICODE_SUBSETS = UNICODE_CATEGORIES.copy()
_UNICODE_SUBSETS.update(UNICODE_BLOCKS)


def get_unicode_subset(key):
    try:
        return _UNICODE_SUBSETS[key]
    except KeyError:
        raise XMLSchemaRegexError("%r don't match to any Unicode category or block.")


I_SHORTCUT_REPLACE = (
    ":A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF"
    "\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

C_SHORTCUT_REPLACE = (
    "\-.0-9:A-Z_a-z\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u037D\u037F-\u1FFF\u200C-"
    "\u200D\u203F\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

S_SHORTCUT_SET = UnicodeSubset(' \n\t\r')
D_SHORTCUT_SET = UnicodeSubset('0-9')
I_SHORTCUT_SET = UnicodeSubset(I_SHORTCUT_REPLACE)
C_SHORTCUT_SET = UnicodeSubset(C_SHORTCUT_REPLACE)
W_SHORTCUT_SET = UnicodeSubset()
W_SHORTCUT_SET._code_points = sorted(
    UNICODE_CATEGORIES['P'].code_points + UNICODE_CATEGORIES['Z'].code_points +
    UNICODE_CATEGORIES['C'].code_points, key=lambda x: x[0] if isinstance(x, tuple) else x
)

# Single and Multi character escapes
CHARACTER_ESCAPES = {
    # Single-character escapes
    '\\n': '\n',
    '\\r': '\r',
    '\\t': '\t',
    '\\|': '|',
    '\\.': '.',
    '\\-': '-',
    '\\^': '^',
    '\\?': '?',
    '\\*': '*',
    '\\+': '+',
    '\\{': '{',
    '\\}': '}',
    '\\(': '(',
    '\\)': ')',
    '\\[': '[',
    '\\]': ']',

    # Multi-character escapes
    '\\s': S_SHORTCUT_SET,
    '\\S': S_SHORTCUT_SET,
    '\\d': D_SHORTCUT_SET,
    '\\D': D_SHORTCUT_SET,
    '\\i': I_SHORTCUT_SET,
    '\\I': I_SHORTCUT_SET,
    '\\c': C_SHORTCUT_SET,
    '\\C': C_SHORTCUT_SET,
    '\\w': W_SHORTCUT_SET,
    '\\W': W_SHORTCUT_SET,
}


class XsdRegexCharGroup(MutableSet):
    """
    A set subclass to represent XML Schema regex character groups.
    """
    _re_char_group = re.compile(r'(\\[nrt\\|.\-^?*+{}()\[\]sSdDiIcCwW]|\\[pP]{[a-zA-Z\-0-9]+})')
    _re_unicode_ref = re.compile(r'\\([pP]){([a-zA-Z\-0-9]+)}')

    def __init__(self, *args):
        self.positive = UnicodeSubset()
        self.negative = UnicodeSubset()
        for char in args:
            self.add(char)

    def __repr__(self):
        return '<%s at %d>' % (self.__class__.__name__, id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if not self.negative:
            return '[%s]' % unicode_type(self.positive)
        elif not self.positive:
            return '[^%s]' % unicode_type(self.negative)
        else:
            return '[%s%s]' % (
                unicode_type(UnicodeSubset(self.negative.complement())), unicode_type(self.positive)
            )

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
            if part in CHARACTER_ESCAPES:
                value = CHARACTER_ESCAPES[part]
                if isinstance(value, string_base_type):
                    self.positive.update(value)
                elif part[-1].islower():
                    self.positive |= value
                else:
                    self.negative |= value
            elif self._re_unicode_ref.search(part) is not None:
                if part.startswith('\\p'):
                    self.positive |= get_unicode_subset(part[3:-1])
                else:
                    self.negative |= get_unicode_subset(part[3:-1])
            else:
                self.positive.update(part)

    def discard(self, s):
        for part in self._re_char_group.split(s):
            if part in CHARACTER_ESCAPES:
                value = CHARACTER_ESCAPES[part]
                if isinstance(value, string_base_type):
                    self.positive.difference_update(value)
                elif part[-1].islower():
                    self.positive -= value
                else:
                    self.negative -= value
            elif self._re_unicode_ref.search(part) is not None:
                if part.startswith('\\p'):
                    self.positive -= get_unicode_subset(part[3:-1])
                else:
                    self.negative -= get_unicode_subset(part[3:-1])
            else:
                self.positive.difference_update(part)

    def clear(self):
        self.positive.clear()
        self.negative.clear()

    def complement(self):
        self.positive, self.negative = self.negative, self.positive


def parse_character_class(xml_regex, class_pos):
    """
    Parses a character class of an XML Schema regular expression.

    :param xml_regex: the source XML Schema regular expression.
    :param class_pos: the position of the character class in the source string, \
    must coincide with a '[' character.
    :return: an `XsdRegexCharGroup` instance and the first position after the character class.
    """
    if xml_regex[class_pos] != '[':
        raise XMLSchemaRegexError('not a character class at position %d: %r' % (class_pos, xml_regex))

    pos = class_pos + 1
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
                raise XMLSchemaRegexError("empty character class at position %d: %r" % (class_pos, xml_regex))
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
            raise XMLSchemaRegexError("unterminated character group at position %d: %r" % (class_pos, xml_regex))
        char_group -= subtracted_group

    return char_group, pos


def get_python_regex(xml_regex):
    """
    Translates an XML regex expression to a Python compatible expression.
    """
    regex = ['^(']
    pos = 0
    while pos < len(xml_regex):
        ch = xml_regex[pos]
        if ch == '.':
            regex.append('[^\r\n]')
        elif ch in ('^', '$'):
            regex.append(r'\%s' % ch)
        elif ch == '[':
            try:
                char_group, pos = parse_character_class(xml_regex, pos)
                regex.append(unicode_type(char_group))
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
                block_pos = pos - 1
                try:
                    if xml_regex[pos + 1] != '{':
                        raise XMLSchemaValueError("a '{' expected, found %r." % xml_regex[pos + 1])
                    while xml_regex[pos] != '}':
                        pos += 1
                except (IndexError, ValueError):
                    raise XMLSchemaRegexError(
                        "truncated unicode block escape at position %d: %r" % (block_pos, xml_regex))

                p_shortcut_set = get_unicode_subset(xml_regex[block_pos + 3:pos])
                if xml_regex[block_pos + 1] == 'p':
                    regex.append('[%s]' % p_shortcut_set)
                else:
                    regex.append('[^%s]' % p_shortcut_set)
            else:
                regex.append('\\%s' % xml_regex[pos])
        else:
            regex.append(ch)
        pos += 1

    regex.append(r')$')
    return ''.join(regex)
