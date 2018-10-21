#!/usr/bin/env python
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
This module runs tests on XML Schema regular expressions.
"""
from __future__ import unicode_literals
import unittest
import sys
import os
import re
from unicodedata import category

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.compat import unicode_chr
from xmlschema.codepoints import iter_code_points, UnicodeSubset, build_unicode_categories, UNICODE_CATEGORIES
from xmlschema.regex import get_python_regex


class TestCodePoints(unittest.TestCase):

    def test_iter_code_points(self):
        self.assertEqual(list(iter_code_points([10, 20, 11, 12, 25, (9, 21), 21])), [(9, 22), 25])
        self.assertEqual(list(iter_code_points([10, 20, 11, 12, 25, (9, 20), 21])), [(9, 22), 25])
        self.assertEqual(list(iter_code_points({2, 120, 121, (150, 260)})), [2, (120, 122), (150, 260)])
        self.assertEqual(
            list(iter_code_points([10, 20, (10, 22), 11, 12, 25, 8, (9, 20), 21, 22, 9, 0])),
            [0, (8, 23), 25]
        )
        self.assertEqual(
            list(e for e in iter_code_points([10, 20, 11, 12, 25, (9, 21)], reverse=True)), [25, (9, 21)]
        )
        self.assertEqual(
            list(iter_code_points([10, 20, (10, 22), 11, 12, 25, 8, (9, 20), 21, 22, 9, 0], reverse=True)),
            [25, (8, 23), 0]
        )


class TestUnicodeSubset(unittest.TestCase):

    def test_creation(self):
        cds = UnicodeSubset([(0, 9), 11, 12, (14, 32), (33, sys.maxunicode + 1)])
        self.assertEqual(cds, [(0, 9), (11, 13), (14, 32), (33, sys.maxunicode + 1)])
        self.assertEqual(UnicodeSubset('0-9'), [(48, 58)])
        self.assertEqual(UnicodeSubset('0-9:'), [(48, 59)])

    def test_modify(self):
        cds = UnicodeSubset([50, 90, 10, 90])
        self.assertEqual(cds, [10, 50, 90])
        self.assertRaises(XMLSchemaValueError, cds.add, -1)
        self.assertRaises(XMLSchemaValueError, cds.add, sys.maxunicode + 1)
        cds.add((100, 20001))
        cds.discard((100, 19001))
        self.assertEqual(cds, [10, 50, 90, (19001, 20001)])
        cds.add(0)
        cds.discard(1)
        self.assertEqual(cds, [0, 10, 50, 90, (19001, 20001)])
        cds.discard(0)
        self.assertEqual(cds, [10, 50, 90, (19001, 20001)])
        cds.discard((10, 100))
        self.assertEqual(cds, [(19001, 20001)])
        cds.add(20)
        cds.add(19)
        cds.add(30)
        cds.add([30, 33])
        cds.add(30000)
        cds.add(30001)
        self.assertEqual(cds, [(19, 21), (30, 33), (19001, 20001), (30000, 30002)])
        cds.add(22)
        cds.add(21)
        cds.add(22)
        self.assertEqual(cds, [(19, 22), 22, (30, 33), (19001, 20001), (30000, 30002)])
        cds.discard((90, 50000))
        self.assertEqual(cds, [(19, 22), 22, (30, 33)])
        cds.discard(21)
        cds.discard(19)
        self.assertEqual(cds, [20, 22, (30, 33)])
        cds.discard((0, 200))
        self.assertEqual(cds, [])

    def test_complement(self):
        cds = UnicodeSubset([50, 90, 10, 90])
        self.assertEqual(list(cds.complement()), [(0, 10), (11, 50), (51, 90), (91, sys.maxunicode + 1)])
        cds.add(11)
        self.assertEqual(list(cds.complement()), [(0, 10), (12, 50), (51, 90), (91, sys.maxunicode + 1)])
        cds.add((0, 10))
        self.assertEqual(list(cds.complement()), [(12, 50), (51, 90), (91, sys.maxunicode + 1)])

    def test_union_and_intersection(self):
        cds1 = UnicodeSubset([50, (90, 200), 10])
        cds2 = UnicodeSubset([10, 51, (89, 150), 90])
        self.assertEqual(cds1 | cds2, [10, (50, 52), (89, 200)])
        self.assertEqual(cds1 & cds2, [10, (90, 150)])

    def test_max_and_min(self):
        cds1 = UnicodeSubset([10, 51, (89, 151), 90])
        cds2 = UnicodeSubset([0, 2, (80, 201), 10000])
        cds3 = UnicodeSubset([1])
        self.assertEqual((min(cds1), max(cds1)), (10, 150))
        self.assertEqual((min(cds2), max(cds2)), (0, 10000))
        self.assertEqual((min(cds3), max(cds3)), (1, 1))

    def test_subtraction(self):
        cds = UnicodeSubset([0, 2, (80, 200), 10000])
        self.assertEqual(cds - {2, 120, 121, (150, 260)}, [0, (80, 120), (122, 150), 10000])


class TestUnicodeCategories(unittest.TestCase):
    """
    Test the subsets of Unicode categories, mainly to check the loaded JSON file.
    """
    def test_build_unicode_categories(self):
        categories = build_unicode_categories('not_existing_file.json')
        self.assertEqual(sum(len(v) for k, v in categories.items() if len(k) > 1), sys.maxunicode + 1)
        self.assertEqual(min([min(s) for s in categories.values()]), 0)
        self.assertEqual(max([max(s) for s in categories.values()]), sys.maxunicode)
        base_sets = [set(v) for k, v in categories.items() if len(k) > 1]
        self.assertFalse(any([s.intersection(t) for s in base_sets for t in base_sets if s != t]))

    def test_unicode_categories(self):
        self.assertEqual(sum(len(v) for k, v in UNICODE_CATEGORIES.items() if len(k) > 1), sys.maxunicode + 1)
        self.assertEqual(min([min(s) for s in UNICODE_CATEGORIES.values()]), 0)
        self.assertEqual(max([max(s) for s in UNICODE_CATEGORIES.values()]), sys.maxunicode)
        base_sets = [set(v) for k, v in UNICODE_CATEGORIES.items() if len(k) > 1]
        self.assertFalse(any([s.intersection(t) for s in base_sets for t in base_sets if s != t]))

    @unittest.skipIf(not ((3, 6) <= sys.version_info < (3, 7)), "Test only for Python 3.6")
    def test_unicodedata_category(self):
        for key in UNICODE_CATEGORIES:
            for cp in UNICODE_CATEGORIES[key]:
                uc = category(unicode_chr(cp))
                if key == uc or len(key) == 1 and key == uc[0]:
                    continue
                self.assertTrue(
                    False, "Wrong category %r for code point %d (should be %r)." % (uc, cp, key)
                )


class TestPatterns(unittest.TestCase):
    """
    Test of specific regex patterns and their application.
    """
    def test_issue_079(self):
        # Do not escape special characters in character class
        regex = get_python_regex('[^\n\t]+')
        self.assertEqual(regex, '^([^\t\n]+)$')
        pattern = re.compile(regex)
        self.assertIsNone(pattern.search('first\tsecond\tthird'))
        self.assertEqual(pattern.search('first second third').group(0), 'first second third')

    def test_dot_wildcard(self):
        regex = get_python_regex('.+')
        self.assertEqual(regex, '^([^\r\n]+)$')
        pattern = re.compile(regex)
        self.assertIsNone(pattern.search('line1\rline2\r'))
        self.assertIsNone(pattern.search('line1\nline2'))
        self.assertIsNone(pattern.search(''))
        self.assertIsNotNone(pattern.search('\\'))
        self.assertEqual(pattern.search('abc').group(0), 'abc')

        regex = get_python_regex('.+T.+(Z|[+-].+)')
        self.assertEqual(regex, '^([^\r\n]+T[^\r\n]+(Z|[\+\-][^\r\n]+))$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('12T0A3+36').group(0), '12T0A3+36')
        self.assertEqual(pattern.search('12T0A3Z').group(0), '12T0A3Z')
        self.assertIsNone(pattern.search(''))
        self.assertIsNone(pattern.search('12T0A3Z2'))

    def test_not_spaces(self):
        regex = get_python_regex("[\S' ']{1,10}")
        if sys.version_info >= (3,):
            self.assertEqual(regex, "^([\x00-\x08\x0b\x0c\x0e-\x1f!-\U0010ffff ']{1,10})$")

        pattern = re.compile(regex)
        self.assertIsNone(pattern.search('alpha\r'))
        self.assertEqual(pattern.search('beta').group(0), 'beta')
        self.assertEqual(pattern.search('beta\n').group(0), 'beta')  # $ matches also a \n at last position
        self.assertIsNone(pattern.search('beta\n '))
        self.assertIsNone(pattern.search(''))
        self.assertIsNone(pattern.search('over the maximum length!'))
        self.assertIsNotNone(pattern.search('\\'))
        self.assertEqual(pattern.search('abc').group(0), 'abc')

    def test_category_escape(self):
        regex = get_python_regex('\\p{IsBasicLatin}*')
        self.assertEqual(regex, '^([\x00-\x7f]*)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('').group(0), '')
        self.assertEqual(pattern.search('e').group(0), 'e')
        self.assertIsNone(pattern.search('è'))

        regex = get_python_regex('[\\p{IsBasicLatin}\\p{IsLatin-1Supplement}]*')
        self.assertEqual(regex, '^([\x00-\xff]*)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('e').group(0), 'e')
        self.assertEqual(pattern.search('è').group(0), 'è')
        self.assertIsNone(pattern.search('Ĭ'))

    def test_digit_shortcut(self):
        regex = get_python_regex('\d{1,3}\.\d{1,2}')
        self.assertEqual(regex, '^(\d{1,3}\.\d{1,2})$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('12.40').group(0), '12.40')
        self.assertEqual(pattern.search('867.00').group(0), '867.00')
        self.assertEqual(pattern.search('867.00\n').group(0), '867.00')
        self.assertIsNone(pattern.search('867.00 '))
        self.assertIsNone(pattern.search('867.000'))
        self.assertIsNone(pattern.search('1867.0'))
        self.assertIsNone(pattern.search('a1.13'))

        regex = get_python_regex('[-+]?(\d+|\d+(\.\d+)?%)')
        self.assertEqual(regex, '^([\+\-]?(\d+|\d+(\.\d+)?%))$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('78.8%').group(0), '78.8%')
        self.assertIsNone(pattern.search('867.00'))

    def test_character_class_reordering(self):
        regex = get_python_regex('[A-Z ]')
        self.assertEqual(regex, '^([ A-Z])$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('A').group(0), 'A')
        self.assertEqual(pattern.search('Z').group(0), 'Z')
        self.assertEqual(pattern.search('Q').group(0), 'Q')
        self.assertEqual(pattern.search(' ').group(0), ' ')
        self.assertIsNone(pattern.search('  '))
        self.assertIsNone(pattern.search('AA'))

        regex = get_python_regex('[0-9.,DHMPRSTWYZ/:+\-]+')
        self.assertEqual(regex, '^([\+-\-\.-:DHMPR-TWYZ]+)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('12,40').group(0), '12,40')
        self.assertEqual(pattern.search('YYYY:MM:DD').group(0), 'YYYY:MM:DD')
        self.assertIsNone(pattern.search(''))
        self.assertIsNone(pattern.search('C'))

        regex = get_python_regex('[^: \n\r\t]+')
        self.assertEqual(regex, '^([^\t\n\r :]+)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('56,41').group(0), '56,41')
        self.assertEqual(pattern.search('56,41\n').group(0), '56,41')
        self.assertIsNone(pattern.search('13:20'))

        regex = get_python_regex('[A-Za-z0-9_\-]+(:[A-Za-z0-9_\-]+)?')
        self.assertEqual(regex, '^([\-0-9A-Z_a-z]+(:[\-0-9A-Z_a-z]+)?)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('fa9').group(0), 'fa9')
        self.assertEqual(pattern.search('-x_1:_tZ-\n').group(0), '-x_1:_tZ-')
        self.assertIsNone(pattern.search(''))
        self.assertIsNone(pattern.search('+78'))

        regex = get_python_regex('[!%\^\*@~;#,|/]')
        self.assertEqual(regex, '^([!#%\*,/;@\^\|~])$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('#').group(0), '#')
        self.assertEqual(pattern.search('!').group(0), '!')
        self.assertEqual(pattern.search('^').group(0), '^')
        self.assertEqual(pattern.search('|').group(0), '|')
        self.assertEqual(pattern.search('*').group(0), '*')
        self.assertIsNone(pattern.search('**'))
        self.assertIsNone(pattern.search('b'))
        self.assertIsNone(pattern.search(''))

        regex = get_python_regex('[A-Za-z]+:[A-Za-z][A-Za-z0-9\\-]+')
        self.assertEqual(regex, '^([A-Za-z]+:[A-Za-z][\\-0-9A-Za-z]+)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('zk:xy-9s').group(0), 'zk:xy-9s')
        self.assertIsNone(pattern.search('xx:y'))

    def test_occurrences_qualifiers(self):
        regex = get_python_regex('#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?')
        self.assertEqual(regex, '^(#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('#F3D').group(0), '#F3D')
        self.assertEqual(pattern.search('#F3D\n').group(0), '#F3D')
        self.assertEqual(pattern.search('#F3DA30').group(0), '#F3DA30')
        self.assertIsNone(pattern.search('#F3'))
        self.assertIsNone(pattern.search('#F3D '))
        self.assertIsNone(pattern.search('F3D'))
        self.assertIsNone(pattern.search(''))

    def test_or_operator(self):
        regex = get_python_regex('0|1')
        self.assertEqual(regex, '^(0|1)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('0').group(0), '0')
        self.assertEqual(pattern.search('1').group(0), '1')
        self.assertEqual(pattern.search('1\n').group(0), '1')
        self.assertIsNone(pattern.search(''))
        self.assertIsNone(pattern.search('2'))
        self.assertIsNone(pattern.search('01'))
        self.assertIsNone(pattern.search('1\n '))

        regex = get_python_regex('\d+[%]|\d*\.\d+[%]')
        self.assertEqual(regex, '^(\d+[%]|\d*\.\d+[%])$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('99%').group(0), '99%')
        self.assertEqual(pattern.search('99.9%').group(0), '99.9%')
        self.assertEqual(pattern.search('.90%').group(0), '.90%')
        self.assertIsNone(pattern.search('%'))
        self.assertIsNone(pattern.search('90.%'))

        regex = get_python_regex('([ -~]|\n|\r|\t)*')
        self.assertEqual(regex, '^(([ -~]|\n|\r|\t)*)$')
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('ciao\t-~ ').group(0), 'ciao\t-~ ')
        self.assertEqual(pattern.search('\r\r').group(0), '\r\r')
        self.assertEqual(pattern.search('\n -.abc').group(0), '\n -.abc')
        self.assertIsNone(pattern.search('à'))
        self.assertIsNone(pattern.search('\t\n à'))

    def test_character_class_shortcuts(self):
        regex = get_python_regex("[\i-[:]][\c-[:]]*")
        pattern = re.compile(regex)
        self.assertEqual(pattern.search('x11').group(0), 'x11')
        self.assertIsNone(pattern.search('3a'))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
