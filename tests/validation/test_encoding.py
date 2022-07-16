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
import sys
import os
import unittest
from textwrap import dedent
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from elementpath import datatypes
from elementpath.etree import etree_tostring

from xmlschema import XMLSchemaEncodeError, XMLSchemaValidationError
from xmlschema.converters import UnorderedConverter, JsonMLConverter
from xmlschema.helpers import local_name, is_etree_element
from xmlschema.resources import XMLResource
from xmlschema.validators.exceptions import XMLSchemaChildrenValidationError
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase, etree_elements_assert_equal


class TestEncoding(XsdValidatorTestCase):

    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')

    def check_encode(self, xsd_component, data, expected, **kwargs):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.encode, data, **kwargs)
        elif is_etree_element(expected):
            elem = xsd_component.encode(data, **kwargs)
            self.check_etree_elements(expected, elem)
        else:
            obj = xsd_component.encode(data, **kwargs)
            if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[1], list):
                self.assertEqual(expected, obj[0])
                self.assertTrue(isinstance(obj[0], type(expected)))
            elif is_etree_element(obj):
                namespaces = kwargs.pop('namespaces', self.default_namespaces)
                self.assertEqual(expected, etree_tostring(obj, namespaces=namespaces).strip())
            else:
                self.assertEqual(expected, obj)
                self.assertTrue(isinstance(obj, type(expected)))

    def test_decode_encode(self):
        """Test encode after decode, checking the re-encoded tree."""
        filename = self.casepath('examples/collection/collection.xml')
        xt = ElementTree.parse(filename)
        xd = self.col_schema.to_dict(filename)
        elem = self.col_schema.encode(xd, path='./col:collection', namespaces=self.col_namespaces)

        self.assertEqual(
            len([e for e in elem.iter()]), 20,
            msg="The encoded tree must have 20 elements as the origin."
        )
        self.assertTrue(all(
            local_name(e1.tag) == local_name(e2.tag)
            for e1, e2 in zip(elem.iter(), xt.getroot().iter())
        ))

    def test_string_based_builtin_types(self):
        self.check_encode(self.xsd_types['string'], 'sample string ', u'sample string ')
        self.check_encode(self.xsd_types['normalizedString'], ' sample string ', u' sample string ')
        self.check_encode(self.xsd_types['normalizedString'],
                          '\n\r sample\tstring\n', u'   sample string ')
        self.check_encode(self.xsd_types['token'], '\n\r sample\t\tstring\n ', u'sample string')
        self.check_encode(self.xsd_types['language'], 'sample string', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['language'], ' en ', u'en')
        self.check_encode(self.xsd_types['Name'], 'first_name', u'first_name')
        self.check_encode(self.xsd_types['Name'], ' first_name ', u'first_name')
        self.check_encode(self.xsd_types['Name'], 'first name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['Name'], '1st_name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['Name'], 'first_name1', u'first_name1')
        self.check_encode(self.xsd_types['Name'], 'first:name', u'first:name')
        self.check_encode(self.xsd_types['NCName'], 'first_name', u'first_name')
        self.check_encode(self.xsd_types['NCName'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['ENTITY'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['ID'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['IDREF'], 'first:name', XMLSchemaValidationError)

    def test_decimal_based_builtin_types(self):
        self.check_encode(self.xsd_types['decimal'], -99.09, u'-99.09')
        self.check_encode(self.xsd_types['decimal'], '-99.09', u'-99.09')
        self.check_encode(self.xsd_types['integer'], 1000, u'1000')
        self.check_encode(self.xsd_types['integer'], 100.0, XMLSchemaEncodeError)
        self.check_encode(self.xsd_types['integer'], 100.0, u'100', validation='lax')
        self.check_encode(self.xsd_types['short'], 1999, u'1999')
        self.check_encode(self.xsd_types['short'], 10000000, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['float'], 100.0, u'100.0')
        self.check_encode(self.xsd_types['float'], 'hello', XMLSchemaEncodeError)
        self.check_encode(self.xsd_types['double'], -4531.7, u'-4531.7')
        self.check_encode(self.xsd_types['positiveInteger'], -1, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['positiveInteger'], 0, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['nonNegativeInteger'], 0, u'0')
        self.check_encode(self.xsd_types['nonNegativeInteger'], -1, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['negativeInteger'], -100, u'-100')
        self.check_encode(self.xsd_types['nonPositiveInteger'], 7, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['unsignedLong'], 101, u'101')
        self.check_encode(self.xsd_types['unsignedLong'], -101, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['nonPositiveInteger'], 7, XMLSchemaValidationError)

    def test_list_builtin_types(self):
        self.check_encode(self.xsd_types['IDREFS'], ['first_name'], u'first_name')
        self.check_encode(self.xsd_types['IDREFS'],
                          'first_name', u'first_name')  # Transform data to list
        self.check_encode(self.xsd_types['IDREFS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['IDREFS'], [1, 'two', 'three'], XMLSchemaValidationError)
        self.check_encode(self.xsd_types['NMTOKENS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['ENTITIES'], ('mouse', 'cat', 'dog'), u'mouse cat dog')

    def test_datetime_builtin_type(self):
        xs = self.get_schema('<xs:element name="dt" type="xs:dateTime"/>')

        dt = xs.decode('<dt>2019-01-01T13:40:00</dt>', datetime_types=True)
        self.assertIsInstance(dt, datatypes.DateTime10)
        self.assertEqual(etree_tostring(xs.encode(dt)), '<dt>2019-01-01T13:40:00</dt>')

        dt = xs.decode('<dt>2019-01-01T13:40:00</dt>')
        self.assertIsInstance(dt, str)
        self.assertEqual(etree_tostring(xs.encode(dt)), '<dt>2019-01-01T13:40:00</dt>')

    def test_date_builtin_type(self):
        xs = self.get_schema('<xs:element name="dt" type="xs:date"/>')
        date = xs.decode('<dt>2001-04-15</dt>', datetime_types=True)
        self.assertEqual(etree_tostring(xs.encode(date)), '<dt>2001-04-15</dt>')

        mdate_type = self.st_schema.types['mdate']

        date = mdate_type.encode('2001-01-01')
        self.assertIsInstance(date, str)
        self.assertEqual(date, '2001-01-01')

        date = mdate_type.encode(datatypes.Date.fromstring('2001-01-01'))
        self.assertIsInstance(date, str)
        self.assertEqual(date, '2001-01-01')

    def test_duration_builtin_type(self):
        xs = self.get_schema('<xs:element name="td" type="xs:duration"/>')
        duration = xs.decode('<td>P5Y3MT60H30.001S</td>', datetime_types=True)
        self.assertEqual(etree_tostring(xs.encode(duration)), '<td>P5Y3M2DT12H30.001S</td>')

    def test_gregorian_year_builtin_type(self):
        xs = self.get_schema('<xs:element name="td" type="xs:gYear"/>')
        gyear = xs.decode('<td>2000</td>', datetime_types=True)
        self.assertEqual(etree_tostring(xs.encode(gyear)), '<td>2000</td>')

    def test_gregorian_yearmonth_builtin_type(self):
        xs = self.get_schema('<xs:element name="td" type="xs:gYearMonth"/>')
        gyear_month = xs.decode('<td>2000-12</td>', datetime_types=True)
        self.assertEqual(etree_tostring(xs.encode(gyear_month)), '<td>2000-12</td>')

    def test_hex_binary_type(self):
        hex_code_type = self.st_schema.types['hexCode']

        value = hex_code_type.encode('00D7310A')
        self.assertEqual(value, '00D7310A')
        self.assertIsInstance(value, str)

        value = hex_code_type.encode(datatypes.HexBinary(b'00D7310A'))
        self.assertEqual(value, '00D7310A')
        self.assertIsInstance(value, str)

    def test_base64_binary_type(self):
        base64_code_type = self.st_schema.types['base64Code']

        value = base64_code_type.encode('YWJjZWZnaA==')
        self.assertEqual(value, 'YWJjZWZnaA==')
        self.assertIsInstance(value, str)

        value = base64_code_type.encode(datatypes.Base64Binary(b'YWJjZWZnaA=='))
        self.assertEqual(value, 'YWJjZWZnaA==')
        self.assertIsInstance(value, str)

    def test_list_types(self):
        list_of_strings = self.st_schema.types['list_of_strings']
        self.check_encode(list_of_strings, (10, 25, 40), '10 25 40', validation='lax')
        self.check_encode(list_of_strings, (10, 25, 40), '10 25 40', validation='skip')
        self.check_encode(list_of_strings, ['a', 'b', 'c'], 'a b c', validation='skip')

        list_of_integers = self.st_schema.types['list_of_integers']
        self.check_encode(list_of_integers, (10, 25, 40), '10 25 40')
        self.check_encode(list_of_integers, (10, 25.0, 40), XMLSchemaValidationError)
        self.check_encode(list_of_integers, (10, 25.0, 40), '10 25 40', validation='lax')

        list_of_floats = self.st_schema.types['list_of_floats']
        self.check_encode(list_of_floats, [10.1, 25.0, 40.0], '10.1 25.0 40.0')
        self.check_encode(list_of_floats, [10.1, 25, 40.0], '10.1 25.0 40.0', validation='lax')
        self.check_encode(list_of_floats, [10.1, False, 40.0], '10.1 0.0 40.0', validation='lax')

        list_of_booleans = self.st_schema.types['list_of_booleans']
        self.check_encode(list_of_booleans, [True, False, True], 'true false true')
        self.check_encode(list_of_booleans, [10, False, True], XMLSchemaEncodeError)
        self.check_encode(list_of_booleans, [True, False, 40.0], 'true false', validation='lax')
        self.check_encode(list_of_booleans, [True, False, 40.0],
                          'true false 40.0', validation='skip')

    def test_union_types(self):
        integer_or_float = self.st_schema.types['integer_or_float']
        self.check_encode(integer_or_float, -95, u'-95')
        self.check_encode(integer_or_float, -95.0, u'-95.0')
        self.check_encode(integer_or_float, True, XMLSchemaEncodeError)
        self.check_encode(integer_or_float, True, u'1', validation='lax')

        integer_or_string = self.st_schema.types['integer_or_string']
        self.check_encode(integer_or_string, 89, u'89')
        self.check_encode(integer_or_string, 89.0, u'89', validation='lax')
        self.check_encode(integer_or_string, 89.0, XMLSchemaEncodeError)
        self.check_encode(integer_or_string, False, XMLSchemaEncodeError)
        self.check_encode(integer_or_string, "Venice ", u'Venice ')

        boolean_or_integer_or_string = self.st_schema.types['boolean_or_integer_or_string']
        self.check_encode(boolean_or_integer_or_string, 89, u'89')
        self.check_encode(boolean_or_integer_or_string, 89.0, u'89', validation='lax')
        self.check_encode(boolean_or_integer_or_string, 89.0, XMLSchemaEncodeError)
        self.check_encode(boolean_or_integer_or_string, False, u'false')
        self.check_encode(boolean_or_integer_or_string, "Venice ", u'Venice ')

    def test_simple_elements(self):
        elem = ElementTree.Element('A')
        elem.text = '89'
        self.check_encode(self.get_element('A', type='xs:string'), '89', elem)
        self.check_encode(self.get_element('A', type='xs:integer'), 89, elem)
        elem.text = '-10.4'
        self.check_encode(self.get_element('A', type='xs:float'), -10.4, elem)
        elem.text = 'false'
        self.check_encode(self.get_element('A', type='xs:boolean'), False, elem)
        elem.text = 'true'
        self.check_encode(self.get_element('A', type='xs:boolean'), True, elem)

        self.check_encode(self.get_element('A', type='xs:short'),
                          128000, XMLSchemaValidationError)
        elem.text = '0'
        self.check_encode(self.get_element('A', type='xs:nonNegativeInteger'), 0, elem)
        self.check_encode(self.get_element('A', type='xs:nonNegativeInteger'),
                          '0', XMLSchemaValidationError)
        self.check_encode(self.get_element('A', type='xs:positiveInteger'),
                          0, XMLSchemaValidationError)
        elem.text = '-1'
        self.check_encode(self.get_element('A', type='xs:negativeInteger'), -1, elem)
        self.check_encode(self.get_element('A', type='xs:nonNegativeInteger'),
                          -1, XMLSchemaValidationError)

    def test_complex_elements(self):
        schema = self.get_schema("""
        <xs:element name="A" type="A_type" />
        <xs:complexType name="A_type" mixed="true">
            <xs:simpleContent>
                <xs:extension base="xs:string">
                    <xs:attribute name="a1" type="xs:short" use="required"/>
                    <xs:attribute name="a2" type="xs:negativeInteger"/>
                </xs:extension>
            </xs:simpleContent>
        </xs:complexType>
        """)
        self.check_encode(
            schema.elements['A'], data={'@a1': 10, '@a2': -1, '$': 'simple '},
            expected='<A a1="10" a2="-1">simple </A>',
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1, '$': 'simple '},
            ElementTree.fromstring('<A a1="10" a2="-1">simple </A>'),
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1},
            ElementTree.fromstring('<A a1="10" a2="-1"/>')
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '$': 'simple '},
            ElementTree.fromstring('<A a1="10">simple </A>')
        )
        self.check_encode(schema.elements['A'], {'@a2': -1, '$': 'simple '},
                          XMLSchemaValidationError)

        schema = self.get_schema("""
        <xs:element name="A" type="A_type" />
        <xs:complexType name="A_type">
            <xs:sequence>
                <xs:element name="B1" type="xs:string"/>
                <xs:element name="B2" type="xs:integer"/>
                <xs:element name="B3" type="xs:boolean"/>
            </xs:sequence>
        </xs:complexType>
        """)
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('B3', False)]),
            expected=u'<A>\n<B1>abc</B1>\n<B2>10</B2>\n<B3>false</B3>\n</A>',
            indent=0,
        )
        self.check_encode(schema.elements['A'], {'B1': 'abc', 'B2': 10, 'B4': False},
                          XMLSchemaValidationError)

    def test_error_message(self):
        schema = self.schema_class(self.casepath('issues/issue_115/Rotation.xsd'))
        rotation_data = {
            "@roll": 0.0,
            "@pitch": 0.0,
            "@yaw": -1.0  # <----- invalid value, must be between 0 and 360
        }

        message_lines = []
        try:
            schema.encode(rotation_data)
        except XMLSchemaValidationError as err:
            message_lines = str(err).split('\n')
            self.assertIsNone(err.source)
            self.assertIsNone(err.path)

        self.assertTrue(message_lines, msg="Empty error message!")
        self.assertEqual(message_lines[-4], 'Instance:')
        if sys.version_info < (3, 8):
            text = '<tns:rotation xmlns:tns="http://www.example.org/Rotation/" ' \
                   'pitch="0.0" roll="0.0" yaw="-1.0" />'
        else:
            text = '<tns:rotation xmlns:tns="http://www.example.org/Rotation/" ' \
                   'roll="0.0" pitch="0.0" yaw="-1.0" />'
        self.assertEqual(message_lines[-2].strip(), text)

        # With 'lax' validation a dummy resource is assigned to source attribute
        _, errors = schema.encode(rotation_data, validation='lax')
        self.assertIsInstance(errors[0].source, XMLResource)
        self.assertEqual(errors[0].path, '/{http://www.example.org/Rotation/}rotation')

    def test_max_occurs_sequence(self):
        # Issue #119
        schema = self.get_schema("""
            <xs:element name="foo">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="A" type="xs:integer" maxOccurs="2" />
                </xs:sequence>
              </xs:complexType>
            </xs:element>""")

        # Check validity
        self.assertIsNone(schema.validate("<foo><A>1</A></foo>"))
        self.assertIsNone(schema.validate("<foo><A>1</A><A>2</A></foo>"))
        with self.assertRaises(XMLSchemaChildrenValidationError):
            schema.validate("<foo><A>1</A><A>2</A><A>3</A></foo>")

        self.assertTrue(is_etree_element(schema.to_etree({'A': 1}, path='foo')))
        self.assertTrue(is_etree_element(schema.to_etree({'A': [1]}, path='foo')))
        self.assertTrue(is_etree_element(schema.to_etree({'A': [1, 2]}, path='foo')))
        with self.assertRaises(XMLSchemaChildrenValidationError):
            schema.to_etree({'A': [1, 2, 3]}, path='foo')

        schema = self.get_schema("""
            <xs:element name="foo">
              <xs:complexType>
                <xs:sequence>
                  <xs:element name="A" type="xs:integer" maxOccurs="2" />
                  <xs:element name="B" type="xs:integer" minOccurs="0" />
                </xs:sequence>
              </xs:complexType>
            </xs:element>""")

        self.assertTrue(is_etree_element(schema.to_etree({'A': [1, 2]}, path='foo')))
        with self.assertRaises(XMLSchemaChildrenValidationError):
            schema.to_etree({'A': [1, 2, 3]}, path='foo')

    def test_encode_unordered_content(self):
        schema = self.get_schema("""
        <xs:element name="A" type="A_type" />
        <xs:complexType name="A_type" mixed="true">
            <xs:sequence>
                <xs:element name="B1" type="xs:string"/>
                <xs:element name="B2" type="xs:integer"/>
                <xs:element name="B3" type="xs:boolean"/>
            </xs:sequence>
        </xs:complexType>
        """)

        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B2', 10), ('B1', 'abc'), ('B3', True)]),
            expected=XMLSchemaChildrenValidationError
        )
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B2', 10), ('B1', 'abc'), ('B3', True)]),
            expected=u'<A>\n<B1>abc</B1>\n<B2>10</B2>\n<B3>true</B3>\n</A>',
            indent=0, cdata_prefix='#', converter=UnorderedConverter
        )

        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('#1', 'hello'), ('B3', True)]),
            expected='<A>\nhello<B1>abc</B1>\n<B2>10</B2>\n<B3>true</B3>\n</A>',
            indent=0, cdata_prefix='#', converter=UnorderedConverter
        )
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('#1', 'hello'), ('B3', True)]),
            expected=u'<A>\n<B1>abc</B1>\n<B2>10</B2>\nhello\n<B3>true</B3>\n</A>',
            indent=0, cdata_prefix='#'
        )
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('#1', 'hello')]),
            expected=XMLSchemaValidationError, indent=0, cdata_prefix='#'
        )

    def test_encode_unordered_content_2(self):
        """Here we test with a default converter at the schema level"""

        schema = self.get_schema("""
        <xs:element name="A" type="A_type" />
        <xs:complexType name="A_type" mixed="true">
            <xs:sequence>
                <xs:element name="B1" type="xs:string"/>
                <xs:element name="B2" type="xs:integer"/>
                <xs:element name="B3" type="xs:boolean"/>
            </xs:sequence>
        </xs:complexType>
        """, converter=UnorderedConverter)

        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B2', 10), ('B1', 'abc'), ('B3', True)]),
            expected=u'<A>\n<B1>abc</B1>\n<B2>10</B2>\n<B3>true</B3>\n</A>',
            indent=0, cdata_prefix='#'
        )
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('#1', 'hello'), ('B3', True)]),
            expected=u'<A>\nhello<B1>abc</B1>\n<B2>10</B2>\n<B3>true</B3>\n</A>',
            indent=0, cdata_prefix='#'
        )
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=dict([('B1', 'abc'), ('B2', 10), ('#1', 'hello')]),
            expected=XMLSchemaValidationError, indent=0, cdata_prefix='#'
        )

    def test_strict_trailing_content(self):
        """Too many elements for a group raises an exception."""
        schema = self.get_schema("""
            <xs:element name="foo">
                <xs:complexType>
                    <xs:sequence minOccurs="2" maxOccurs="2">
                        <xs:element name="A" minOccurs="0" type="xs:integer" nillable="true" />
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
            """)
        self.check_encode(
            schema.elements['foo'],
            data={"A": [1, 2, 3]},
            expected=XMLSchemaChildrenValidationError,
        )

    def test_unordered_converter_repeated_sequence_of_elements(self):
        schema = self.get_schema("""
            <xs:element name="foo">
                <xs:complexType>
                    <xs:sequence minOccurs="1" maxOccurs="2">
                        <xs:element name="A" minOccurs="0" type="xs:integer" nillable="true" />
                        <xs:element name="B" minOccurs="0" type="xs:integer" nillable="true" />
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
            """)

        root = schema.to_etree(dict([('A', [1, 2]), ('B', [3, 4])]))
        self.assertListEqual([e.text for e in root], ['1', '3', '2', '4'])

        root = schema.to_etree({"A": [1, 2], "B": [3, 4]}, converter=UnorderedConverter)
        self.assertListEqual([e.text for e in root], ['1', '3', '2', '4'])

        root = schema.to_etree({"A": [1, 2], "B": [3, 4]}, unordered=True)
        self.assertListEqual([e.text for e in root], ['1', '3', '2', '4'])

    def test_xsi_type_and_attributes_unmap__issue_214(self):
        schema = self.schema_class("""<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                       xmlns="http://xmlschema.test/ns"
                       targetNamespace="http://xmlschema.test/ns">
              <xs:element name="a" type="xs:string"/>
              <xs:complexType name="altType">
                <xs:simpleContent>
                  <xs:extension base="xs:string">
                    <xs:attribute name="a1" type="xs:string" use="required"/>
                  </xs:extension>
                </xs:simpleContent>
              </xs:complexType>
            </xs:schema>""")

        xml1 = """<a xmlns="http://xmlschema.test/ns">alpha</a>"""
        self.assertEqual(schema.decode(xml1), 'alpha')

        xml2 = """<a xmlns="http://xmlschema.test/ns"
                     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                     xsi:type="altType" a1="beta">alpha</a>"""

        obj = schema.decode(xml2)
        self.assertEqual(obj, {'@xmlns': 'http://xmlschema.test/ns',
                               '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                               '@xsi:type': 'altType', '@a1': 'beta', '$': 'alpha'})
        root = schema.encode(obj, path='{http://xmlschema.test/ns}a')
        self.assertEqual(root.tag, '{http://xmlschema.test/ns}a')
        self.assertEqual(root.attrib, {
            '{http://www.w3.org/2001/XMLSchema-instance}type': 'altType',
            'a1': 'beta'
        })

    def test_element_encoding_with_defaults__issue_218(self):
        schema = self.schema_class(dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="values" type="myType"/>
                <xs:complexType name="myType">
                    <xs:sequence>
                        <xs:element name="b1" type="xs:boolean" default="1"/>
                        <xs:element name="b2" type="xs:boolean" default="true"/>
                        <xs:element name="b3" type="xs:boolean" default="false"/>
                    </xs:sequence>
               </xs:complexType>
             </xs:schema>"""))

        self.assertEqual(schema.decode('<values><b1/><b2/><b3/></values>'),
                         {'b1': True, 'b2': True, 'b3': False})

        values = schema.encode({'b1': None, 'b2': True, 'b3': False})
        self.assertEqual(len(values), 3)
        self.assertEqual(values[0].tag, 'b1')
        self.assertEqual(values[0].text, '1')
        self.assertEqual(values[1].tag, 'b2')
        self.assertEqual(values[1].text, 'true')
        self.assertEqual(values[2].tag, 'b3')
        self.assertEqual(values[2].text, 'false')

        values = schema.encode({'b1': False, 'b2': True, 'b3': None})
        self.assertEqual(len(values), 3)
        self.assertEqual(values[0].tag, 'b1')
        self.assertEqual(values[0].text, 'false')
        self.assertEqual(values[1].tag, 'b2')
        self.assertEqual(values[1].text, 'true')
        self.assertEqual(values[2].tag, 'b3')
        self.assertEqual(values[2].text, 'false')

    def test_attribute_encoding_with_defaults__issue_218(self):
        schema = self.schema_class(dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="values" type="myType"/>
                <xs:complexType name="myType">
                    <xs:simpleContent>
                        <xs:extension base="xs:string">
                            <xs:attribute name="b1" type="xs:boolean" default="1"/>
                            <xs:attribute name="b2" type="xs:boolean" default="true"/>
                            <xs:attribute name="b3" type="xs:boolean" default="false"/>
                        </xs:extension>
                    </xs:simpleContent>
               </xs:complexType>
             </xs:schema>"""))

        self.assertTrue(schema.is_valid('<values>content</values>'))
        self.assertEqual(schema.decode('<values/>'),
                         {'@b1': True, '@b2': True, '@b3': False})

        elem = schema.encode({})
        self.assertIsNone(elem.text)
        self.assertEqual(elem.attrib, {'b1': '1', 'b2': 'true', 'b3': 'false'})

        elem = schema.encode({'@b1': True, '@b3': True})
        self.assertIsNone(elem.text)
        self.assertEqual(elem.attrib, {'b1': 'true', 'b2': 'true', 'b3': 'true'})

        elem = schema.encode({'@b2': False, '@b1': False})
        self.assertIsNone(elem.text)
        self.assertEqual(elem.attrib, {'b1': 'false', 'b2': 'false', 'b3': 'false'})

    def test_encode_sub_tree(self):
        """Test encoding data of a non-root element"""
        data = {
            "@id": "PAR",
            "name": "Pierre-Auguste Renoir",
            "born": "1841-02-25",
            "dead": "1919-12-03",
            "qualification": "painter",
        }
        elem = self.col_schema.encode(
            data,
            path=".//author",
            namespaces=self.col_namespaces,
        )
        self.assertEqual(
            etree_tostring(elem),
            dedent(
                """\
                <author id="PAR">
                    <name>Pierre-Auguste Renoir</name>
                    <born>1841-02-25</born>
                    <dead>1919-12-03</dead>
                    <qualification>painter</qualification>
                </author>"""
            )
        )

    @unittest.skipIf(lxml_etree is None, "The lxml library is not available.")
    def test_lxml_encode(self):
        """Test encode with etree_element_class=lxml.etree.Element"""
        xd = {
            "@xmlns:col": "http://example.com/ns/collection",
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": "http://example.com/ns/collection collection.xsd",
            "object": [
                {
                    "@id": "b0836217463",
                    "@available": True,
                    "position": 2,
                    "title": None,
                    "year": "1925",
                    "author": {
                        "@id": "JM",
                        "name": "Joan Miró",
                        "born": "1893-04-20",
                        "dead": "1983-12-25",
                        "qualification": "painter, sculptor and ceramicist",
                    },
                },
            ],
        }

        elem = self.col_schema.encode(
            xd,
            path="./col:collection",
            namespaces=self.col_namespaces,
            etree_element_class=lxml_etree.Element,
        )

        self.assertEqual(
            etree_tostring(elem, namespaces=self.col_namespaces),
            dedent(
                """\
                <col:collection xmlns:col="http://example.com/ns/collection" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://example.com/ns/collection collection.xsd">
                    <object id="b0836217463" available="true">
                        <position>2</position>
                        <title/>
                        <year>1925</year>
                        <author id="JM">
                            <name>Joan Miró</name>
                            <born>1893-04-20</born>
                            <dead>1983-12-25</dead>
                            <qualification>painter, sculptor and ceramicist</qualification>
                        </author>
                    </object>
                </col:collection>"""
            )
        )

    def test_float_encoding(self):
        for float_type in [self.schema_class.meta_schema.types['float'],
                           self.schema_class.meta_schema.types['double']]:
            self.assertEqual(float_type.encode(-1.0), '-1.0')
            self.assertEqual(float_type.encode(19.7), '19.7')
            self.assertEqual(float_type.encode(float('inf')), 'INF')
            self.assertEqual(float_type.encode(float('-inf')), '-INF')
            self.assertEqual(float_type.encode(float('nan')), 'NaN')

    def test_wildcard_with_foreign_and_jsonml__issue_298(self):
        schema = self.schema_class(self.casepath('issues/issue_298/issue_298.xsd'))
        xml_data = self.casepath('issues/issue_298/issue_298-2.xml')

        instance = [
            'tns:Root',
            {'xmlns:tns': 'http://xmlschema.test/ns',
             'xmlns:zz': 'http://xmlschema.test/ns2'},
            ['Container', ['Freeform', ['zz:ForeignSchema']]]
        ]
        result = schema.decode(xml_data, converter=JsonMLConverter)
        self.assertListEqual(result, instance)

        root, errors = schema.encode(instance, validation='lax', converter=JsonMLConverter)
        self.assertListEqual(errors, [])
        self.assertIsNone(etree_elements_assert_equal(root, ElementTree.parse(xml_data).getroot()))

        instance = ['tns:Root', ['Container', ['Freeform', ['zz:ForeignSchema']]]]
        namespaces = {'tns': 'http://xmlschema.test/ns',
                      'zz': 'http://xmlschema.test/ns2'}
        root, errors = schema.encode(instance, validation='lax',
                                     namespaces=namespaces,
                                     use_defaults=False,
                                     converter=JsonMLConverter)
        self.assertListEqual(errors, [])
        self.assertIsNone(etree_elements_assert_equal(root, ElementTree.parse(xml_data).getroot()))


class TestEncoding11(TestEncoding):
    schema_class = XMLSchema11


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema encoding with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
