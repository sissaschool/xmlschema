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
import unittest
import sys
import os
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
from xmlschema.codepoints import iter_code_points, UnicodeSubset, UNICODE_CATEGORIES


class TestCodePoints(unittest.TestCase):

    def test_iter_code_points(self):
        self.assertEqual(list(iter_code_points([10, 20, 11, 12, 25, (9, 20), 21])), [(9, 21), 25])
        self.assertEqual(list(iter_code_points([10, 20, 11, 12, 25, (9, 20), 21])), [(9, 21), 25])
        self.assertEqual(list(iter_code_points({2, 120, 121, (150, 260)})), [2, (120, 121), (150, 260)])
        self.assertEqual(
            list(iter_code_points([10, 20, (10, 22), 11, 12, 25, 8, (9, 20), 21, 22, 9, 0])),
            [0, (8, 22), 25]
        )
        self.assertEqual(
            list(e for e in iter_code_points([10, 20, 11, 12, 25, (9, 20)], reverse=True)), [25, (9, 20)]
        )
        self.assertEqual(
            list(iter_code_points([10, 20, (10, 22), 11, 12, 25, 8, (9, 20), 21, 22, 9, 0], reverse=True)),
            [25, (8, 22), 0]
        )


class TestUnicodeSubset(unittest.TestCase):

    def test_modify(self):
        cds = UnicodeSubset([50, 90, 10, 90])
        self.assertEqual(cds, [10, 50, 90])
        self.assertRaises(XMLSchemaValueError, cds.add, -1)
        self.assertRaises(XMLSchemaValueError, cds.add, sys.maxunicode + 1)
        cds.add((100, 20000))
        cds.discard((100, 19000))
        self.assertEqual(cds, [10, 50, 90, (19001, 20000)])
        cds.add(0)
        cds.discard(1)
        self.assertEqual(cds, [0, 10, 50, 90, (19001, 20000)])
        cds.discard(0)
        self.assertEqual(cds, [10, 50, 90, (19001, 20000)])
        cds.discard((10, 100))
        self.assertEqual(cds, [(19001, 20000)])
        cds.add(20)
        cds.add(19)
        cds.add(30)
        cds.add([30, 33])
        cds.add(30000)
        cds.add(30001)
        self.assertEqual(cds, [(19, 20), (30, 33), (19001, 20000), (30000, 30001)])
        cds.add(22)
        cds.add(21)
        cds.add(22)
        self.assertEqual(cds, [(19, 21), 22, (30, 33), (19001, 20000), (30000, 30001)])
        cds.discard((90, 50000))
        self.assertEqual(cds, [(19, 21), 22, (30, 33)])
        cds.discard(21)
        cds.discard(19)
        self.assertEqual(cds, [20, 22, (30, 33)])
        cds.discard((0, 200))
        self.assertEqual(cds, [])

    def test_complement(self):
        cds = UnicodeSubset([50, 90, 10, 90])
        self.assertEqual(list(cds.complement()), [(0, 9), (11, 49), (51, 89), (91, sys.maxunicode)])
        cds.add(11)
        self.assertEqual(list(cds.complement()), [(0, 9), (12, 49), (51, 89), (91, sys.maxunicode)])
        cds.add((0, 9))
        self.assertEqual(list(cds.complement()), [(12, 49), (51, 89), (91, sys.maxunicode)])

    def test_union_and_intersection(self):
        cds1 = UnicodeSubset([50, (90, 200), 10])
        cds2 = UnicodeSubset([10, 51, (89, 150), 90])
        self.assertEqual(cds1 | cds2, [10, (50, 51), (89, 200)])
        self.assertEqual(cds1 & cds2, [10, (90, 150)])

    def test_max_and_min(self):
        cds1 = UnicodeSubset([10, 51, (89, 150), 90])
        cds2 = UnicodeSubset([0, 2, (80, 200), 10000])
        cds3 = UnicodeSubset([1])
        self.assertEqual((min(cds1), max(cds1)), (10, 150))
        self.assertEqual((min(cds2), max(cds2)), (0, 10000))
        self.assertEqual((min(cds3), max(cds3)), (1, 1))

    def test_subtraction(self):
        cds = UnicodeSubset([0, 2, (80, 200), 10000])
        self.assertEqual(cds - {2, 120, 121, (150, 260)}, [0, (80, 119), (122, 149), 10000])


class TestUnicodeCategories(unittest.TestCase):
    """
    Test the subsets of Unicode categories, mainly to check the loaded JSON file.
    """

    def test_disjunction(self):
        base_sets = [set(v) for k, v in UNICODE_CATEGORIES.items() if len(k) > 1]
        self.assertFalse(
            any([s.intersection(t) for s in base_sets for t in base_sets if s != t]),
            "The Unicode categories are not mutually disjoined."
        )

    def test_conjunctions(self):
        n_code_points = sum(len(v) for k, v in UNICODE_CATEGORIES.items() if len(k) > 1)
        self.assertTrue(
            n_code_points == sys.maxunicode + 1,
            "The Unicode categories have a wrong number of elements: %d (!= %d) " % (n_code_points, sys.maxunicode + 1)
        )

    def test_max_value(self):
        max_code_point = max([max(s) for s in UNICODE_CATEGORIES.values()])
        self.assertTrue(
            max_code_point <= sys.maxunicode,
            "The Unicode categories have a code point greater than %d: %d" % (sys.maxunicode, max_code_point)
        )

    def test_min_value(self):
        min_code_point = min([min(s) for s in UNICODE_CATEGORIES.values()])
        self.assertTrue(
            min_code_point >= 0,
            "The Unicode categories have negative code points: %d" % min_code_point
        )

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


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
