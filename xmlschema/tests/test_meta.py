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
This module runs tests on XSD meta schema and builtins of the 'xmlschema' package.
"""
import unittest

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    import os
    import sys

    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema import XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaValidationError

meta_schema = xmlschema.XMLSchema.meta_schema


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
        float_type = meta_schema.types['float']
        self.assertTrue(float_type.encode(1000.0) == '1000.0')
        self.assertTrue(float_type.encode(-19.0) == '-19.0')
        self.assertTrue(float_type.encode(0.0) == '0.0')
        self.assertRaises(XMLSchemaEncodeError, float_type.encode, True)
        self.assertRaises(XMLSchemaEncodeError, float_type.encode, 'alpha')

    def test_time_type(self):
        time_type = meta_schema.types['time']
        self.assertTrue(time_type.is_valid('14:35:00'))
        self.assertTrue(time_type.is_valid('14:35:20.5345'))
        self.assertTrue(time_type.is_valid('14:35:00-01:00'))
        self.assertTrue(time_type.is_valid('14:35:00Z'))
        self.assertTrue(time_type.is_valid('00:00:00'))
        self.assertTrue(time_type.is_valid('24:00:00'))
        self.assertFalse(time_type.is_valid('4:20:00'))
        self.assertFalse(time_type.is_valid('14:35:0'))
        self.assertFalse(time_type.is_valid('14:35'))
        self.assertFalse(time_type.is_valid('14:35.5:00'))

    def test_datetime_type(self):
        datetime_type = meta_schema.types['dateTime']
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:20.6'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00-03:00'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00Z'))
        self.assertFalse(datetime_type.is_valid('2007-05-10T14:35'))
        self.assertFalse(datetime_type.is_valid('2007-05-10t14:35:00'))
        self.assertFalse(datetime_type.is_valid('2007-05-1014:35:00'))
        self.assertFalse(datetime_type.is_valid('07-05-10T14:35:00'))
        self.assertFalse(datetime_type.is_valid('2007-05-10'))

    def test_date_type(self):
        date_type = meta_schema.types['date']
        self.assertTrue(date_type.is_valid('2012-05-31'))
        self.assertTrue(date_type.is_valid('-0065-10-15'))
        self.assertTrue(date_type.is_valid('12012-05-31'))
        self.assertTrue(date_type.is_valid('2012-05-31-05:00'))
        self.assertTrue(date_type.is_valid('2015-06-30Z'))
        if meta_schema.version > '1.0':
            self.assertTrue(date_type.is_valid('0000-01-01'))
        else:
            self.assertFalse(date_type.is_valid('0000-01-01'))
        self.assertFalse(date_type.is_valid('12-05-31'))
        self.assertFalse(date_type.is_valid('2012-5-31'))
        self.assertFalse(date_type.is_valid('31-05-2012'))
        self.assertFalse(date_type.is_valid('1999-06-31'))
        self.assertFalse(date_type.is_valid('+2012-05-31'))
        self.assertFalse(date_type.is_valid(''))

    def test_g_year_type(self):
        g_year_type = meta_schema.types['gYear']
        self.assertTrue(g_year_type.is_valid('2007'))
        self.assertTrue(g_year_type.is_valid('2013-01:00'))
        self.assertTrue(g_year_type.is_valid('102013-01:00'))
        self.assertTrue(g_year_type.is_valid('0821'))
        self.assertTrue(g_year_type.is_valid('0014'))
        self.assertTrue(g_year_type.is_valid('-0044'))
        self.assertTrue(g_year_type.is_valid('13999'))
        self.assertFalse(g_year_type.is_valid('045'))
        self.assertFalse(g_year_type.is_valid('800'))
        self.assertFalse(g_year_type.is_valid(''))

    def test_g_year_month_type(self):
        g_year_month_type = meta_schema.types['gYearMonth']
        self.assertTrue(g_year_month_type.is_valid('2010-07'))
        self.assertTrue(g_year_month_type.is_valid('2020-01-05:00'))
        self.assertFalse(g_year_month_type.is_valid('99-02'))
        self.assertFalse(g_year_month_type.is_valid('1999'))
        self.assertFalse(g_year_month_type.is_valid('1995-3'))
        self.assertFalse(g_year_month_type.is_valid('1860-14'))
        self.assertFalse(g_year_month_type.is_valid(''))

    def test_g_month_type(self):
        g_month_type = meta_schema.types['gMonth']
        self.assertTrue(g_month_type.is_valid('--08'))
        self.assertTrue(g_month_type.is_valid('--05-03:00'))
        self.assertFalse(g_month_type.is_valid('03'))
        self.assertFalse(g_month_type.is_valid('3'))
        self.assertFalse(g_month_type.is_valid('--13'))
        self.assertFalse(g_month_type.is_valid('--3'))
        self.assertFalse(g_month_type.is_valid(''))

    def test_g_month_day_type(self):
        g_month_day_type = meta_schema.types['gMonthDay']
        self.assertTrue(g_month_day_type.is_valid('--12-24'))
        self.assertTrue(g_month_day_type.is_valid('--04-25Z'))
        self.assertFalse(g_month_day_type.is_valid('12-24'))
        self.assertFalse(g_month_day_type.is_valid('--11-31'))
        self.assertFalse(g_month_day_type.is_valid('--2-11'))
        self.assertFalse(g_month_day_type.is_valid('--02-1'))
        self.assertFalse(g_month_day_type.is_valid(''))

    def test_g_day_type(self):
        g_day_type = meta_schema.types['gDay']
        self.assertTrue(g_day_type.is_valid('---19'))
        self.assertTrue(g_day_type.is_valid('---07'))
        self.assertFalse(g_day_type.is_valid('---32'))
        self.assertFalse(g_day_type.is_valid('07'))
        self.assertFalse(g_day_type.is_valid('--07'))
        self.assertFalse(g_day_type.is_valid('---7'))
        self.assertFalse(g_day_type.is_valid(''))

    def test_duration_type(self):
        duration_type = meta_schema.types['duration']
        self.assertTrue(duration_type.is_valid('-P809YT3H5M5S'))
        self.assertTrue(duration_type.is_valid('P5Y7M20DT3H5M5S'))
        self.assertTrue(duration_type.is_valid('P1DT6H'))
        self.assertTrue(duration_type.is_valid('P15M'))
        self.assertTrue(duration_type.is_valid('PT30M'))
        self.assertTrue(duration_type.is_valid('P0Y15M0D'))
        self.assertTrue(duration_type.is_valid('P0Y'))
        self.assertTrue(duration_type.is_valid('-P10D'))
        self.assertTrue(duration_type.is_valid('PT5M30.5S'))
        self.assertTrue(duration_type.is_valid('PT10.5S'))
        self.assertFalse(duration_type.is_valid('P-50M'))
        self.assertFalse(duration_type.is_valid('P50MT'))
        self.assertFalse(duration_type.is_valid('P1YM7D'))
        self.assertFalse(duration_type.is_valid('P10.8Y'))
        self.assertFalse(duration_type.is_valid('P3D5H'))
        self.assertFalse(duration_type.is_valid('1Y'))
        self.assertFalse(duration_type.is_valid('P3D4M'))
        self.assertFalse(duration_type.is_valid('P'))
        self.assertFalse(duration_type.is_valid('PT10.S'))
        self.assertFalse(duration_type.is_valid(''))


class TestGlobalMaps(unittest.TestCase):

    def test_globals(self):
        self.assertTrue(len(meta_schema.maps.notations) == 2)
        self.assertTrue(len(meta_schema.maps.types) == 105)
        self.assertTrue(len(meta_schema.maps.attributes) == 18)
        self.assertTrue(len(meta_schema.maps.attribute_groups) == 9)
        self.assertTrue(len(meta_schema.maps.groups) == 18)
        self.assertTrue(len(meta_schema.maps.elements) == 47)
        self.assertTrue(len([e.is_global for e in meta_schema.maps.iter_globals()]) == 199)

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
                    global_counter += 1
        self.assertTrue(global_counter == 199)
        self.assertTrue(total_counter == 945)


# TODO: Add tests for base schemas files.

if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
