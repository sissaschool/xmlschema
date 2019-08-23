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
Parse and translate XML Schema regular expressions to Python regex syntax.
"""
from __future__ import unicode_literals
import re
from itertools import chain
from sys import maxunicode

from .compat import PY3, unicode_type, string_base_type, MutableSet
from .exceptions import XMLSchemaValueError, XMLSchemaRegexError
from .codepoints import UnicodeSubset, UNICODE_CATEGORIES, unicode_subset

_RE_HYPHENS = re.compile(r'(?<!\\)--')
_RE_QUANTIFIER = re.compile(r'{\d+(,(\d+)?)?}')
_RE_FORBIDDEN_ESCAPES = re.compile(
    r'(?<!\\)\\(U[0-9a-fA-F]{8}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|o{\d+}|\d+|A|Z|z|B|b|o)'
)


I_SHORTCUT_REPLACE = (
    ":A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF"
    "\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

C_SHORTCUT_REPLACE = (
    "-.0-9:A-Z_a-z\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u037D\u037F-\u1FFF\u200C-"
    "\u200D\u203F\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

S_SHORTCUT_SET = UnicodeSubset(' \n\t\r')
D_SHORTCUT_SET = UnicodeSubset()
D_SHORTCUT_SET._code_points = UNICODE_CATEGORIES['Nd'].code_points
I_SHORTCUT_SET = UnicodeSubset(I_SHORTCUT_REPLACE)
C_SHORTCUT_SET = UnicodeSubset(C_SHORTCUT_REPLACE)
W_SHORTCUT_SET = UnicodeSubset(chain(
    UNICODE_CATEGORIES['L'].code_points,
    UNICODE_CATEGORIES['M'].code_points,
    UNICODE_CATEGORIES['N'].code_points,
    UNICODE_CATEGORIES['S'].code_points
))

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
    '\\\\': '\\',

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
    _re_char_group = re.compile(r'(?<!.-)(\\[nrt|.\-^?*+{}()\]sSdDiIcCwW]|\\[pP]{[a-zA-Z\-0-9]+})')
    _re_unicode_ref = re.compile(r'\\([pP]){([\w\d-]+)}')

    def __init__(self, xsd_version='1.0', *args):
        self.xsd_version = xsd_version
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
            elif part.startswith('\\p'):
                if self._re_unicode_ref.search(part) is None:
                    raise XMLSchemaValueError("wrong Unicode subset specification %r" % part)
                self.positive |= unicode_subset(part[3:-1], self.xsd_version > '1.0')
            elif part.startswith('\\P'):
                if self._re_unicode_ref.search(part) is None:
                    raise XMLSchemaValueError("wrong Unicode subset specification %r" % part)
                self.negative |= unicode_subset(part[3:-1], self.xsd_version > '1.0')
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
            elif part.startswith('\\p'):
                if self._re_unicode_ref.search(part) is None:
                    raise XMLSchemaValueError("wrong Unicode subset specification %r" % part)
                self.positive -= unicode_subset(part[3:-1], self.xsd_version > '1.0')
            elif part.startswith('\\P'):
                if self._re_unicode_ref.search(part) is None:
                    raise XMLSchemaValueError("wrong Unicode subset specification %r" % part)
                self.negative -= unicode_subset(part[3:-1], self.xsd_version > '1.0')
            else:
                self.positive.difference_update(part)

    def clear(self):
        self.positive.clear()
        self.negative.clear()

    def complement(self):
        self.positive, self.negative = self.negative, self.positive


def parse_character_class(xml_regex, class_pos, xsd_version='1.0'):
    """
    Parses a character class of an XML Schema regular expression.

    :param xml_regex: the source XML Schema regular expression.
    :param class_pos: the position of the character class in the source string, \
    must coincide with a '[' character.
    :param xsd_version: the version of the XML Schema processor ('1.0' or '1.1') \
    that called the regular expression parsing.
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
        if xml_regex[pos] == '[':
            raise XMLSchemaRegexError("'[' is invalid in a character class: %r" % xml_regex)
        elif xml_regex[pos] == '\\':
            pos += 2
        elif xml_regex[pos] == ']' or xml_regex[pos:pos + 2] == '-[':
            if pos == group_pos:
                raise XMLSchemaRegexError(
                    "empty character class at position %d: %r" % (class_pos, xml_regex)
                )
            if _RE_HYPHENS.search(xml_regex[group_pos:pos]) and pos - group_pos > 2:
                raise XMLSchemaRegexError(
                    "invalid character range '--' at position %d: %r" % (class_pos, xml_regex)
                )

            char_group = XsdRegexCharGroup(xsd_version, xml_regex[group_pos:pos])
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
                "unterminated character group at position %d: %r" % (class_pos, xml_regex)
            )
        char_group -= subtracted_group

    return char_group, pos


def get_python_regex(xml_regex, xsd_version='1.0'):
    """
    Translates an XML regex expression to a Python compatible expression.

    :param xml_regex: the source XML Schema regular expression.
    :param xsd_version: the version of the XML Schema processor ('1.0' or '1.1') \
    that called the regular expression parsing.
    """
    regex = ['^(']
    pos = 0
    xml_regex_len = len(xml_regex)
    nested_groups = 0

    match = _RE_FORBIDDEN_ESCAPES.search(xml_regex)
    if match:
        raise XMLSchemaRegexError(
            "not allowed escape sequence %r at position %d: %r" % (match.group(), match.span()[0], xml_regex)
        )

    while pos < xml_regex_len:
        ch = xml_regex[pos]
        if ch == '.':
            regex.append('[^\r\n]')
        elif ch in ('^', '$'):
            regex.append(r'\%s' % ch)
        elif ch == '[':
            try:
                char_group, pos = parse_character_class(xml_regex, pos, xsd_version)
            except IndexError:
                raise XMLSchemaRegexError(
                    "unterminated character group at position %d: %r" % (pos, xml_regex)
                )
            else:
                char_group_repr = unicode_type(char_group)
                if char_group_repr == '[^]':
                    regex.append(r'[\w\W]')
                elif char_group_repr == '[]':
                    regex.append(r'[^\w\W]')
                else:
                    regex.append(char_group_repr)

        elif ch == '{':
            if pos == 0:
                raise XMLSchemaRegexError("unexpected quantifier %r at position %d: %r" % (ch, pos, xml_regex))
            match = _RE_QUANTIFIER.match(xml_regex[pos:])
            if match is None:
                raise XMLSchemaRegexError("invalid quantifier %r at position %d: %r" % (ch, pos, xml_regex))
            regex.append(match.group())
            pos += len(match.group())
            if pos < xml_regex_len and xml_regex[pos] in ('?', '+', '*'):
                raise XMLSchemaRegexError(
                    "unexpected meta character %r at position %d: %r" % (xml_regex[pos], pos, xml_regex)
                )
            continue

        elif ch == '(':
            if xml_regex[pos:pos + 2] == '(?':
                raise XMLSchemaRegexError("'(?...)' extension notation is not allowed: %r" % xml_regex)
            nested_groups += 1
            regex.append(ch)
        elif ch == ']':
            raise XMLSchemaRegexError("unexpected meta character %r at position %d: %r" % (ch, pos, xml_regex))
        elif ch == ')':
            if nested_groups == 0:
                raise XMLSchemaRegexError("unbalanced parenthesis ')' at position %d: %r" % (pos, xml_regex))
            nested_groups -= 1
            regex.append(ch)
        elif ch in ('?', '+', '*'):
            if pos == 0:
                raise XMLSchemaRegexError("unexpected quantifier %r at position %d: %r" % (ch, pos, xml_regex))
            elif pos < xml_regex_len - 1 and xml_regex[pos + 1] in ('?', '+', '*', '{'):
                raise XMLSchemaRegexError(
                    "unexpected meta character %r at position %d: %r" % (xml_regex[pos + 1], pos + 1, xml_regex)
                )
            regex.append(ch)
        elif ch == '\\':
            pos += 1
            if pos >= xml_regex_len:
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

                p_shortcut_set = unicode_subset(xml_regex[block_pos + 3:pos], xsd_version > '1.0')
                if xml_regex[block_pos + 1] == 'p':
                    regex.append('[%s]' % p_shortcut_set)
                else:
                    regex.append('[^%s]' % p_shortcut_set)
            else:
                regex.append('\\%s' % xml_regex[pos])
        else:
            regex.append(ch)
        pos += 1

    if nested_groups > 0:
        raise XMLSchemaRegexError("unterminated subpattern in expression: %r" % xml_regex)
    regex.append(r')$')
    return ''.join(regex)
