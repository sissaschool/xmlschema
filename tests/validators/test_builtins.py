#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests on XSD meta schema and XSD builtins"""
import unittest
from textwrap import dedent

from xmlschema import XMLSchemaDecodeError, XMLSchemaEncodeError, \
    XMLSchemaValidationError, XMLSchema10, XMLSchema11
from xmlschema.names import XSD_STRING
from xmlschema.helpers import is_etree_element
from xmlschema.validators.builtins import XSD_10_BUILTIN_TYPES, \
    XSD_11_BUILTIN_TYPES, xsd_builtin_types_factory


class TestXsd10BuiltinTypes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema_class = XMLSchema10
        cls.types = XMLSchema10.builtin_types()

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()

    def test_facet_lists(self):
        for builtin_types in (XSD_10_BUILTIN_TYPES, XSD_11_BUILTIN_TYPES):
            for item in builtin_types:
                if 'facets' in item:
                    self.assertIsInstance(item['facets'], list)
                    self.assertLessEqual(len([e for e in item['facets'] if callable(e)]), 1)
                    for e in item['facets']:
                        self.assertTrue(callable(e) or is_etree_element(e))

    def test_factory(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>"""), use_meta=False, build=False)

        with self.assertRaises(ValueError) as ctx:
            xsd_types = {XSD_STRING: (None, schema)}
            xsd_builtin_types_factory(schema.meta_schema, xsd_types)

        self.assertEqual(str(ctx.exception), "loaded entry schema is not the meta-schema!")

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
        self.assertRaises(XMLSchemaValidationError, self.types['float'].decode, ' true ')
        self.assertRaises(XMLSchemaValidationError, self.types['double'].decode, ' alpha  \n')

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
        self.assertFalse(datetime_type.is_valid('2007-05-10'))

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
        cls.schema_class = XMLSchema11
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


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD builtins with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
