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

import time
from sys import maxunicode
from xmlschema.exceptions import XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaValidationError
from xmlschema.codepoints import UNICODE_CATEGORIES
from xmlschema.components import XsdAnnotated
from xmlschema import XMLSchema

meta_schema = XMLSchema.META_SCHEMA


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

    def test_boolean_decode(self):
        xsd_type = meta_schema.types['boolean']
        self.assertTrue(xsd_type.decode(' true  \n') is True)
        self.assertTrue(xsd_type.decode(' 0  \n') is False)
        self.assertTrue(xsd_type.decode(' 1  \n') is True)
        self.assertTrue(xsd_type.decode(' false  \n') is False)
        self.assertRaises(XMLSchemaDecodeError, xsd_type.decode, ' 1.0  ')
        self.assertRaises(XMLSchemaDecodeError, xsd_type.decode, ' alpha  \n')

    def test_boolean_encode(self):
        xsd_type = meta_schema.types['boolean']
        self.assertTrue(xsd_type.encode(True) == 'true')
        self.assertTrue(xsd_type.encode(False) == 'false')
        self.assertRaises(XMLSchemaEncodeError, xsd_type.encode, 1)
        self.assertRaises(XMLSchemaEncodeError, xsd_type.encode, 0)
        self.assertRaises(XMLSchemaEncodeError, xsd_type.encode, 10)
        self.assertRaises(XMLSchemaEncodeError, xsd_type.encode, 'alpha')

    def test_integer_decode(self):
        xsd_types = meta_schema.types
        self.assertTrue(xsd_types['integer'].decode(' 1000  \n') == 1000)
        self.assertTrue(xsd_types['integer'].decode(' -19  \n') == -19)
        self.assertTrue(xsd_types['integer'].decode(' 0\n') == 0)
        self.assertRaises(XMLSchemaDecodeError, xsd_types['integer'].decode, ' 1000.0  \n')
        self.assertRaises(XMLSchemaDecodeError, xsd_types['integer'].decode, ' alpha  \n')
        self.assertRaises(XMLSchemaValidationError, xsd_types['byte'].decode, ' 257  \n')
        self.assertRaises(XMLSchemaValidationError, xsd_types['unsignedInt'].decode, ' -1')

    def test_integer_encode(self):
        xsd_types = meta_schema.types
        self.assertTrue(xsd_types['integer'].encode(1000) == '1000')
        self.assertTrue(xsd_types['integer'].encode(-19) == '-19')
        self.assertTrue(xsd_types['integer'].encode(0) == '0')
        self.assertRaises(XMLSchemaEncodeError, xsd_types['integer'].encode, 10.1)
        self.assertRaises(XMLSchemaEncodeError, xsd_types['integer'].encode, 'alpha')
        self.assertRaises(XMLSchemaValidationError, xsd_types['unsignedInt'].decode, ' -1')

    def test_float_decode(self):
        xsd_types = meta_schema.types
        self.assertTrue(xsd_types['float'].decode(' 1000.1  \n') == 1000.10)
        self.assertTrue(xsd_types['float'].decode(' -19  \n') == -19.0)
        self.assertTrue(xsd_types['double'].decode(' 0.0001\n') == 0.0001)
        self.assertRaises(XMLSchemaDecodeError, xsd_types['float'].decode, ' true ')
        self.assertRaises(XMLSchemaDecodeError, xsd_types['double'].decode, ' alpha  \n')

    def test_float_encode(self):
        xsd_types = meta_schema.types
        self.assertTrue(xsd_types['float'].encode(1000.0) == '1000.0')
        self.assertTrue(xsd_types['float'].encode(-19.0) == '-19.0')
        self.assertTrue(xsd_types['float'].encode(0.0) == '0.0')
        self.assertRaises(XMLSchemaEncodeError, xsd_types['float'].encode, True)
        self.assertRaises(XMLSchemaEncodeError, xsd_types['float'].encode, 'alpha')


class TestGlobalMaps(unittest.TestCase):

    def test_globals(self):
        self.assertTrue(len(meta_schema.maps.notations) == 2)
        self.assertTrue(len(meta_schema.maps.types) == 105)
        self.assertTrue(len(meta_schema.maps.attributes) == 18)
        self.assertTrue(len(meta_schema.maps.attribute_groups) == 9)
        self.assertTrue(len(meta_schema.maps.groups) == 18)
        self.assertTrue(len(meta_schema.maps.elements) == 47)
        self.assertTrue(len([e.is_global for e in meta_schema.maps.iter_globals()]) == 199)

        self.assertTrue(len(meta_schema.maps.base_elements) == 48)
        self.assertTrue(len(meta_schema.maps.substitution_groups) == 0)

    def test_build(self):
        meta_schema.maps.build()
        self.assertTrue(len([e for e in meta_schema.maps.iter_globals()]) == 199)
        self.assertTrue(meta_schema.maps.built)
        meta_schema.maps.clear()
        meta_schema.maps.build()
        self.assertTrue(meta_schema.maps.built)

    def test_components(self):
        total_counter = 0
        global_counter = 0
        for g in meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global:
                    global_counter +=1
        self.assertTrue(global_counter == 199)
        self.assertTrue(total_counter == 1199)


# TODO: Add test for base schemas files.

if __name__ == '__main__':
    unittest.main()
