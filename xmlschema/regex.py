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
This module parse and translate XML regular expressions to Python regex syntax.
"""
import re
from collections import MutableSet
from sys import maxunicode

from .compat import PY3, unicode_type
from .exceptions import XMLSchemaRegexError
from .codepoints import UNICODE_CATEGORIES, UNICODE_BLOCKS, UnicodeSubset

_UNICODE_SUBSETS = UNICODE_CATEGORIES.copy()
_UNICODE_SUBSETS.update(UNICODE_BLOCKS)


def get_unicode_subset(key):
    try:
        return _UNICODE_SUBSETS[key]
    except KeyError:
        raise XMLSchemaRegexError("%r don't match to any Unicode category or block.")


I_SHORTCUT_REPLACE = (
    u":A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF"
    u"\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
)

C_SHORTCUT_REPLACE = (
    u"\-.0-9:A-Z_a-z\u00B7\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u037D\u037F-\u1FFF\u200C-"
    u"\u200D\u203F\u2040\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD"
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
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if not self.negative:
            return unicode_type(self.positive)
        elif self.positive:
            return u'{0, ..., maxunicode} - %s + %s' % (self.negative, self.positive)
        else:
            return u'{0, ..., maxunicode} - %s' % self.negative

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
                self.positive.update(part)

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
                self.positive.difference_update(part)

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
                regex.append(u'\\')
            elif xml_regex[pos] == 'i':
                regex.append(u'[%s]' % I_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'I':
                regex.append(u'[^%s]' % I_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'c':
                regex.append(u'[%s]' % C_SHORTCUT_REPLACE)
            elif xml_regex[pos] == 'C':
                regex.append(u'[^%s]' % C_SHORTCUT_REPLACE)
            elif xml_regex[pos] in 'pP':
                start_pos = pos - 1
                try:
                    if xml_regex[pos + 1] != '{':
                        raise ValueError()
                    while xml_regex[pos] != '}':
                        pos += 1
                except (IndexError, ValueError):
                    raise XMLSchemaRegexError(
                        "truncated unicode block escape at position %d: %r" % (start_pos, xml_regex))

                p_shortcut_set = get_unicode_subset(xml_regex[start_pos + 3:pos])
                if xml_regex[start_pos + 1] == 'p':
                    regex.append(u'[%s]' % p_shortcut_set)
                else:
                    regex.append(u'[^%s]' % p_shortcut_set)
            else:
                regex.append(u'\\%s' % xml_regex[pos])
        else:
            regex.append(ch)
        pos += 1

    regex.append(r'$')
    return u''.join(regex)
