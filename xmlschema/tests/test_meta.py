#!/usr/bin/env python
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
This module runs tests on XSD meta schema and builtins of the 'xmlschema' package.
"""
from _test_common import *

from sys import maxunicode
from xmlschema.xsdbase import xsd_qname
from xmlschema.codepoints import UNICODE_CATEGORIES
from xmlschema import XMLSchema


class TestUnicodeCategories(unittest.TestCase):
    """
    Test the subsets of Unicode categories, mainly to check the loaded JSON file.
    """

    def test_disjunction(self):
        base_sets = [v for k, v in UNICODE_CATEGORIES.items() if len(k) > 1]
        self.assertFalse(
            any([s.intersection(t) for s in base_sets for t in base_sets if s != t]),
            "The Unicode categories are not mutually disjoined."
        )

    def test_conjunctions(self):
        n_code_points = len(set.union(*[v for k, v in UNICODE_CATEGORIES.items() if len(k) > 1]))
        self.assertTrue(
            n_code_points == maxunicode + 1,
            "The Unicode categories have a wrong number of elements: %d (!= %d) " % (n_code_points, maxunicode + 1)
        )

    def test_max_value(self):
        max_code_point = max([max(s) for s in UNICODE_CATEGORIES.values()])
        self.assertTrue(
            max_code_point <= maxunicode,
            "The Unicode categories have a code point greater than %d: %d" % (maxunicode, max_code_point)
        )

    def test_min_value(self):
        min_code_point = min([min(s) for s in UNICODE_CATEGORIES.values()])
        self.assertTrue(
            min_code_point >= 0,
            "The Unicode categories have negative code points: %d" % min_code_point
        )


class TestBuiltinTypes(unittest.TestCase):

    def test_boolean(self):
        xsd_boolean = XMLSchema.META_SCHEMA.maps.types[xsd_qname('boolean')]
        self.assertTrue(all([
                xsd_boolean.decode(' true  \n'), not xsd_boolean.decode(' 0  \n'),
                xsd_boolean.decode(' 1  \n'), not xsd_boolean.decode(' false  \n')
            ]),
            "Error decoding boolean values."
        )


if __name__ == '__main__':
    unittest.main()
