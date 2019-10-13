#!/usr/bin/env python
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
This module runs tests on XSD meta schema and builtins of the 'xmlschema' package.
"""
import unittest

from xmlschema import XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaValidationError, \
    XMLSchema10, XMLSchema11
from xmlschema.validators.builtins import HEX_BINARY_PATTERN, NOT_BASE64_BINARY_PATTERN


class TestXsd10BuiltinTypes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.types = XMLSchema10.builtin_types()

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()

    def test_hex_binary_pattern(self):
        self.assertEqual(HEX_BINARY_PATTERN.search("aff1c").group(0), 'aff1c')
        self.assertEqual(HEX_BINARY_PATTERN.search("aF3Bc").group(0), 'aF3Bc')

    def test_not_base64_pattern(self):
        self.assertIsNone(NOT_BASE64_BINARY_PATTERN.search("YWVpb3U="))
        self.assertEqual(NOT_BASE64_BINARY_PATTERN.search("YWVpb3U!=").group(0), '!')

    def test_boolean_decode(self):
        boolean_type = self.types['boolean']
        self.assertTrue(boolean_type.decode(' true  \n') is True)
        self.assertTrue(boolean_type.decode(' 0  \n') is False)
        self.assertTrue(boolean_type.decode(' 1  \n') is True)
        self.assertTrue(boolean_type.decode(' false  \n') is False)
        self.assertRaises(XMLSchemaDecodeError, boolean_type.decode, ' 1.0  ')
        self.assertRaises(XMLSchemaDecodeError, boolean_type.decode, ' alpha  \n')

    def test_boolean_encode(self):
        boolean_type = self.types['boolean']
        self.assertTrue(boolean_type.encode(True) == 'true')
        self.assertTrue(boolean_type.encode(False) == 'false')
        self.assertRaises(XMLSchemaEncodeError, boolean_type.encode, 1)
        self.assertRaises(XMLSchemaEncodeError, boolean_type.encode, 0)
        self.assertRaises(XMLSchemaEncodeError, boolean_type.encode, 10)
        self.assertRaises(XMLSchemaEncodeError, boolean_type.encode, 'alpha')

    def test_integer_decode(self):
        integer_type = self.types['integer']
        self.assertTrue(integer_type.decode(' 1000  \n') == 1000)
        self.assertTrue(integer_type.decode(' -19  \n') == -19)
        self.assertTrue(integer_type.decode(' 0\n') == 0)
        self.assertRaises(XMLSchemaDecodeError, integer_type.decode, ' 1000.0  \n')
        self.assertRaises(XMLSchemaDecodeError, integer_type.decode, ' alpha  \n')
        self.assertRaises(XMLSchemaValidationError, self.types['byte'].decode, ' 257  \n')
        self.assertRaises(XMLSchemaValidationError, self.types['unsignedInt'].decode, ' -1')

    def test_integer_encode(self):
        integer_type = self.types['integer']
        self.assertTrue(integer_type.encode(1000) == '1000')
        self.assertTrue(integer_type.encode(-19) == '-19')
        self.assertTrue(integer_type.encode(0) == '0')
        self.assertRaises(XMLSchemaEncodeError, integer_type.encode, 10.1)
        self.assertRaises(XMLSchemaEncodeError, integer_type.encode, 'alpha')
        self.assertRaises(XMLSchemaValidationError, self.types['unsignedInt'].decode, ' -1')

    def test_float_decode(self):
        self.assertTrue(self.types['float'].decode(' 1000.1  \n') == 1000.10)
        self.assertTrue(self.types['float'].decode(' -19  \n') == -19.0)
        self.assertTrue(self.types['double'].decode(' 0.0001\n') == 0.0001)
        self.assertRaises(XMLSchemaDecodeError, self.types['float'].decode, ' true ')
        self.assertRaises(XMLSchemaDecodeError, self.types['double'].decode, ' alpha  \n')

    def test_float_encode(self):
        float_type = self.types['float']
        self.assertTrue(float_type.encode(1000.0) == '1000.0')
        self.assertTrue(float_type.encode(-19.0) == '-19.0')
        self.assertTrue(float_type.encode(0.0) == '0.0')
        self.assertRaises(XMLSchemaEncodeError, float_type.encode, True)
        self.assertRaises(XMLSchemaEncodeError, float_type.encode, 'alpha')

    def test_time_type(self):
        time_type = self.types['time']
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
        datetime_type = self.types['dateTime']
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:20.6'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00-03:00'))
        self.assertTrue(datetime_type.is_valid('2007-05-10T14:35:00Z'))
        self.assertFalse(datetime_type.is_valid('2007-05-10T14:35'))
        self.assertFalse(datetime_type.is_valid('2007-05-10t14:35:00'))
        self.assertFalse(datetime_type.is_valid('2007-05-1014:35:00'))
        self.assertFalse(datetime_type.is_valid('07-05-10T14:35:00'))
        self.assertTrue(datetime_type.is_valid('2007-05-10'))

        # Issue #85
        self.assertTrue(datetime_type.is_valid('2018-10-10T13:57:53.0702116-04:00'))

    def test_date_type(self):
        date_type = self.types['date']
        self.assertTrue(date_type.is_valid('2012-05-31'))
        self.assertTrue(date_type.is_valid('-0065-10-15'))
        self.assertTrue(date_type.is_valid('12012-05-31'))
        self.assertTrue(date_type.is_valid('2012-05-31-05:00'))
        self.assertTrue(date_type.is_valid('2015-06-30Z'))
        self.assertFalse(date_type.is_valid('12-05-31'))
        self.assertFalse(date_type.is_valid('2012-5-31'))
        self.assertFalse(date_type.is_valid('31-05-2012'))
        self.assertFalse(date_type.is_valid('1999-06-31'))
        self.assertFalse(date_type.is_valid('+2012-05-31'))
        self.assertFalse(date_type.is_valid(''))

    def test_year_zero(self):
        self.assertFalse(self.types['date'].is_valid('0000-01-01'))

    def test_g_year_type(self):
        g_year_type = self.types['gYear']
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
        g_year_month_type = self.types['gYearMonth']
        self.assertTrue(g_year_month_type.is_valid('2010-07'))
        self.assertTrue(g_year_month_type.is_valid('2020-01-05:00'))
        self.assertFalse(g_year_month_type.is_valid('99-02'))
        self.assertFalse(g_year_month_type.is_valid('1999'))
        self.assertFalse(g_year_month_type.is_valid('1995-3'))
        self.assertFalse(g_year_month_type.is_valid('1860-14'))
        self.assertFalse(g_year_month_type.is_valid(''))

    def test_g_month_type(self):
        g_month_type = self.types['gMonth']
        self.assertTrue(g_month_type.is_valid('--08'))
        self.assertTrue(g_month_type.is_valid('--05-03:00'))
        self.assertFalse(g_month_type.is_valid('03'))
        self.assertFalse(g_month_type.is_valid('3'))
        self.assertFalse(g_month_type.is_valid('--13'))
        self.assertFalse(g_month_type.is_valid('--3'))
        self.assertFalse(g_month_type.is_valid(''))

    def test_g_month_day_type(self):
        g_month_day_type = self.types['gMonthDay']
        self.assertTrue(g_month_day_type.is_valid('--12-24'))
        self.assertTrue(g_month_day_type.is_valid('--04-25Z'))
        self.assertFalse(g_month_day_type.is_valid('12-24'))
        self.assertFalse(g_month_day_type.is_valid('--11-31'))
        self.assertFalse(g_month_day_type.is_valid('--2-11'))
        self.assertFalse(g_month_day_type.is_valid('--02-1'))
        self.assertFalse(g_month_day_type.is_valid(''))

    def test_g_day_type(self):
        g_day_type = self.types['gDay']
        self.assertTrue(g_day_type.is_valid('---19'))
        self.assertTrue(g_day_type.is_valid('---07'))
        self.assertFalse(g_day_type.is_valid('---32'))
        self.assertFalse(g_day_type.is_valid('07'))
        self.assertFalse(g_day_type.is_valid('--07'))
        self.assertFalse(g_day_type.is_valid('---7'))
        self.assertFalse(g_day_type.is_valid(''))

    def test_duration_type(self):
        duration_type = self.types['duration']
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


class TestXsd11BuiltinTypes(TestXsd10BuiltinTypes):

    @classmethod
    def setUpClass(cls):
        cls.types = XMLSchema11.builtin_types()

    @classmethod
    def tearDownClass(cls):
        XMLSchema11.meta_schema.clear()

    def test_year_zero(self):
        self.assertTrue(self.types['date'].is_valid('0000-01-01'))

    def test_date_time_stamp(self):
        date_time_stamp_type = self.types['dateTimeStamp']
        self.assertTrue(date_time_stamp_type.is_valid('2003-10-20T16:50:08-03:00'))
        self.assertTrue(date_time_stamp_type.is_valid('2003-10-20T16:50:08Z'))
        self.assertFalse(date_time_stamp_type.is_valid('2003-10-20T16:50:08'))
        self.assertFalse(date_time_stamp_type.is_valid('1980-02-28T17:09:20.1'))
        self.assertFalse(date_time_stamp_type.is_valid(''))

    def test_day_time_duration_type(self):
        day_time_duration_type = self.types['dayTimeDuration']
        self.assertTrue(day_time_duration_type.is_valid('P7DT15H40M0S'))
        self.assertTrue(day_time_duration_type.is_valid('-P10D'))
        self.assertTrue(day_time_duration_type.is_valid('P0D'))
        self.assertTrue(day_time_duration_type.is_valid('PT13M'))
        self.assertTrue(day_time_duration_type.is_valid('P0DT17M'))
        self.assertTrue(day_time_duration_type.is_valid('PT3H20M10.5S'))
        self.assertFalse(day_time_duration_type.is_valid('PT5D'))
        self.assertFalse(day_time_duration_type.is_valid('PT3HM10S'))
        self.assertFalse(day_time_duration_type.is_valid('P7DT'))
        self.assertFalse(day_time_duration_type.is_valid('PT3H1.4M'))
        self.assertFalse(day_time_duration_type.is_valid('P-5D'))
        self.assertFalse(day_time_duration_type.is_valid('P1D5H'))
        self.assertFalse(day_time_duration_type.is_valid('PT10M21.S'))
        self.assertFalse(day_time_duration_type.is_valid('P'))
        self.assertFalse(day_time_duration_type.is_valid(''))

    def test_year_month_duration_type(self):
        year_month_duration_type = self.types['yearMonthDuration']
        self.assertTrue(year_month_duration_type.is_valid('P3Y4M'))
        self.assertTrue(year_month_duration_type.is_valid('P15M'))
        self.assertTrue(year_month_duration_type.is_valid('P0Y'))
        self.assertTrue(year_month_duration_type.is_valid('P0Y23M'))
        self.assertTrue(year_month_duration_type.is_valid('-P8Y'))
        self.assertFalse(year_month_duration_type.is_valid('3Y4M'))
        self.assertFalse(year_month_duration_type.is_valid('P6M1Y'))
        self.assertFalse(year_month_duration_type.is_valid('P'))
        self.assertFalse(year_month_duration_type.is_valid('P1Y6M15D'))
        self.assertFalse(year_month_duration_type.is_valid('P1.2Y'))
        self.assertFalse(year_month_duration_type.is_valid('P2YM'))
        self.assertFalse(year_month_duration_type.is_valid('P-1Y'))
        self.assertFalse(year_month_duration_type.is_valid(''))


class TestGlobalMaps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema10.meta_schema.build()
        XMLSchema11.meta_schema.build()

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()
        XMLSchema11.meta_schema.clear()

    def test_xsd_10_globals(self):
        self.assertEqual(len(XMLSchema10.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.types), 92)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attributes), 8)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attribute_groups), 3)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.groups), 12)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.elements), 41)
        self.assertEqual(len([e.is_global() for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.substitution_groups), 0)

    def test_xsd_11_globals(self):
        self.assertEqual(len(XMLSchema11.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.types), 103)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attributes), 14)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attribute_groups), 4)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.groups), 13)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.elements), 47)
        self.assertEqual(len([e.is_global() for e in XMLSchema11.meta_schema.maps.iter_globals()]), 183)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.substitution_groups), 1)

    def test_xsd_10_build(self):
        self.assertEqual(len([e for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158)
        self.assertTrue(XMLSchema10.meta_schema.maps.built)
        XMLSchema10.meta_schema.maps.clear()
        XMLSchema10.meta_schema.maps.build()
        self.assertTrue(XMLSchema10.meta_schema.maps.built)

    def test_xsd_11_build(self):
        self.assertEqual(len([e for e in XMLSchema11.meta_schema.maps.iter_globals()]), 183)
        self.assertTrue(XMLSchema11.meta_schema.maps.built)
        XMLSchema11.meta_schema.maps.clear()
        XMLSchema11.meta_schema.maps.build()
        self.assertTrue(XMLSchema11.meta_schema.maps.built)

    def test_xsd_10_components(self):
        total_counter = 0
        global_counter = 0
        for g in XMLSchema10.meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global():
                    global_counter += 1
        self.assertEqual(global_counter, 158)
        self.assertEqual(total_counter, 782)

    def test_xsd_11_components(self):
        total_counter = 0
        global_counter = 0
        for g in XMLSchema11.meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global():
                    global_counter += 1
        self.assertEqual(global_counter, 183)
        self.assertEqual(total_counter, 932)

    def test_xsd_11_restrictions(self):
        all_model_type = XMLSchema11.meta_schema.types['all']
        self.assertTrue(
            all_model_type.content_type.is_restriction(all_model_type.base_type.content_type)
        )


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
