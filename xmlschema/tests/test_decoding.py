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
This module runs tests concerning the decoding of XML files with the 'xmlschema' package.
"""
import unittest
import os
import sys
from collections import OrderedDict
from decimal import Decimal
import base64
from xml.etree import ElementTree as _ElementTree

try:
    import lxml.etree as _lxml_etree
except ImportError:
    _lxml_etree = None


try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.tests import XMLSchemaTestCase
from xmlschema import XMLSchemaValidationError


_VEHICLES_DICT = {
    'vh:cars': {
        'vh:car': [
            {'@make': 'Porsche', '@model': '911'},
            {'@make': 'Porsche', '@model': '911'}
        ]},
    'vh:bikes': {
        'vh:bike': [
            {'@make': 'Harley-Davidson', '@model': 'WL'},
            {'@make': 'Yamaha', '@model': 'XS650'}
        ]},
    '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd'
}

_VEHICLES_DICT_ALT = [
    {'vh:cars': [
        {'vh:car': None, '@make': 'Porsche', '@model': '911'},
        {'vh:car': None, '@make': 'Porsche', '@model': '911'}
        ]},
    {'vh:bikes': [
        {'vh:bike': None, '@make': 'Harley-Davidson', '@model': 'WL'},
        {'vh:bike': None, '@make': 'Yamaha', '@model': 'XS650'}
        ]},
    {'@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd'}
]

_COLLECTION_DICT = {
    '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
    'object': [{
        '@available': True,
        '@id': 'b0836217462',
        'author': {
            '@id': 'PAR',
            'born': '1841-02-25',
            'dead': '1919-12-03',
            'name': 'Pierre-Auguste Renoir',
            'qualification': 'painter'
        },
        'estimation': Decimal('10000.00'),
        'position': 1,
        'title': 'The Umbrellas',
        'year': '1886'},
        {
            '@available': True,
            '@id': 'b0836217463',
            'author': {
                '@id': 'JM',
                'born': '1893-04-20',
                'dead': '1983-12-25',
                'name': u'Joan Miró',
                'qualification': 'painter, sculptor and ceramicist'
            },
            'position': 2,
            'title': None,
            'year': '1925'
        }]
}

_COLLECTION_PARKER = {
    'object': [{'author': {'born': '1841-02-25',
                           'dead': '1919-12-03',
                           'name': 'Pierre-Auguste Renoir',
                           'qualification': 'painter'},
                'estimation': 10000.0,
                'position': 1,
                'title': 'The Umbrellas',
                'year': '1886'},
               {'author': {'born': '1893-04-20',
                           'dead': '1983-12-25',
                           'name': u'Joan Miró',
                           'qualification': 'painter, sculptor and ceramicist'},
                'position': 2,
                'title': None,
                'year': '1925'}]}

_COLLECTION_PARKER_ROOT = {
    'col:collection': {'object': [{'author': {'born': '1841-02-25',
                                              'dead': '1919-12-03',
                                              'name': 'Pierre-Auguste Renoir',
                                              'qualification': 'painter'},
                                   'estimation': 10000.0,
                                   'position': 1,
                                   'title': 'The Umbrellas',
                                   'year': '1886'},
                                  {'author': {'born': '1893-04-20',
                                              'dead': '1983-12-25',
                                              'name': u'Joan Miró',
                                              'qualification': 'painter, sculptor and ceramicist'},
                                   'position': 2,
                                   'title': None,
                                   'year': '1925'}]}}

_COLLECTION_BADGERFISH = {
    '@xmlns': {
        'col': 'http://example.com/ns/collection',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'},
    'col:collection': {
        '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
        'object': [{
            '@available': True,
            '@id': 'b0836217462',
            'author': {
                '@id': 'PAR',
                'born': {'$': '1841-02-25'},
                'dead': {'$': '1919-12-03'},
                'name': {'$': 'Pierre-Auguste Renoir'},
                'qualification': {'$': 'painter'}},
            'estimation': {'$': 10000.0},
            'position': {'$': 1},
            'title': {'$': 'The Umbrellas'},
            'year': {'$': '1886'}},
            {
                '@available': True,
                '@id': 'b0836217463',
                'author': {
                    '@id': 'JM',
                    'born': {'$': '1893-04-20'},
                    'dead': {'$': '1983-12-25'},
                    'name': {'$': u'Joan Miró'},
                    'qualification': {
                        '$': 'painter, sculptor and ceramicist'}
                },
                'position': {'$': 2},
                'title': {},
                'year': {'$': '1925'}
            }]
    }
}

_COLLECTION_ABDERA = {
    'attributes': {
        'xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd'
    },
    'children': [
        {
            'object': [
                {
                    'attributes': {'available': True, 'id': 'b0836217462'},
                    'children': [{
                        'author': {
                            'attributes': {'id': 'PAR'},
                            'children': [{
                                'born': '1841-02-25',
                                'dead': '1919-12-03',
                                'name': 'Pierre-Auguste Renoir',
                                'qualification': 'painter'}
                            ]},
                        'estimation': 10000.0,
                        'position': 1,
                        'title': 'The Umbrellas',
                        'year': '1886'}
                    ]},
                {
                    'attributes': {'available': True, 'id': 'b0836217463'},
                    'children': [{
                        'author': {
                            'attributes': {'id': 'JM'},
                            'children': [{
                                'born': '1893-04-20',
                                'dead': '1983-12-25',
                                'name': u'Joan Miró',
                                'qualification': 'painter, sculptor and ceramicist'}
                            ]},
                        'position': 2,
                        'title': [],
                        'year': '1925'
                    }]
                }]
        }
    ]}

_COLLECTION_JSON_ML = [
    'col:collection',
    {'xmlns:col': 'http://example.com/ns/collection',
     'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     'xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd'},
    ['object',
     {'available': True, 'id': 'b0836217462'},
     ['position', 1],
     ['title', 'The Umbrellas'],
     ['year', '1886'],
     [
         'author',
         {'id': 'PAR'},
         ['name', 'Pierre-Auguste Renoir'],
         ['born', '1841-02-25'],
         ['dead', '1919-12-03'],
         ['qualification', 'painter']
     ],
     [
         'estimation',
         Decimal('10000.00')
     ]],
    ['object',
     {'available': True, 'id': 'b0836217463'},
     ['position', 2],
     ['title'],
     ['year', '1925'],
     [
         'author',
         {'id': 'JM'},
         ['name', u'Joan Miró'],
         ['born', '1893-04-20'],
         ['dead', '1983-12-25'],
         ['qualification', 'painter, sculptor and ceramicist']
     ]]
]

_DATA_DICT = {
    '@xsi:schemaLocation': 'ns ./simple-types.xsd',
    'certification': [
        {'$': 'ISO-9001', '@Year': 1999},
        {'$': 'ISO-27001', '@Year': 2009}
    ],
    'decimal_value': [Decimal('1')],
    u'menù': u'baccalà mantecato',
    u'complex_boolean': [
        {'$': True, '@Type': 2}, {'$': False, '@Type': 1}, True, False
    ],
    u'simple_boolean': [True, False]
}


def make_decoding_test_function(xml_file, schema_class, expected_errors=0, inspect=False,
                                locations=None, defuse='defuse'):
    def test_decoding(self):
        schema, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        xs = schema_class(schema, validation='lax', locations=_locations, defuse=defuse)
        errors = []
        chunks = []
        for obj in xs.iter_decode(xml_file):
            if isinstance(obj, (xmlschema.XMLSchemaDecodeError, xmlschema.XMLSchemaValidationError)):
                errors.append(obj)
            else:
                chunks.append(obj)
        if len(errors) != expected_errors:
            import pdb
            pdb.set_trace()
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (
                    expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors])
                )
            )
        if not chunks:
            raise ValueError("No decoded object returned!!")
        elif len(chunks) > 1:
            raise ValueError("Too many ({}) decoded objects returned: {}".format(len(chunks), chunks))
        elif not isinstance(chunks[0], dict):
            raise ValueError("Decoded object is not a dictionary: {}".format(chunks))
        else:
            self.assertTrue(True, "Successfully test decoding for {}".format(xml_file))

    return test_decoding


def make_lxml_decoding_test_function(xml_file, schema_class, expected_errors=0, inspect=False,
                                     locations=None, defuse='defuse'):
    def test_decoding(self):
        schema, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        xs = schema_class(schema, validation='lax', locations=_locations, defuse=defuse)
        data = _lxml_etree.parse(xml_file)
        errors = []
        chunks = []
        for obj in xs.iter_decode(data):
            if isinstance(obj, (xmlschema.XMLSchemaDecodeError, xmlschema.XMLSchemaValidationError)):
                errors.append(obj)
            else:
                chunks.append(obj)
        if len(errors) != expected_errors:
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (
                    expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors])
                )
            )
        if not chunks:
            raise ValueError("No decoded object returned!!")
        elif len(chunks) > 1:
            raise ValueError("Too many ({}) decoded objects returned: {}".format(len(chunks), chunks))
        elif not isinstance(chunks[0], dict):
            raise ValueError("Decoded object is not a dictionary: {}".format(chunks))
        else:
            self.assertTrue(True, "Successfully test decoding for {}".format(xml_file))

    return test_decoding


class TestDecoding(XMLSchemaTestCase):

    def check_decode(self, xsd_component, data, expected, **kwargs):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.decode, data, **kwargs)
        else:
            obj = xsd_component.decode(data, **kwargs)
            if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[1], list) \
                    and isinstance(obj[1][0], Exception):
                self.assertEqual(expected, obj[0])
                self.assertTrue(isinstance(obj[0], type(expected)))
            else:
                self.assertEqual(expected, obj)
                self.assertTrue(isinstance(obj, type(expected)))

    @unittest.skipIf(_lxml_etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        vh_xml_tree = _lxml_etree.parse(self.abspath('cases/examples/vehicles/vehicles.xml'))
        self.assertEqual(self.vh_schema.to_dict(vh_xml_tree), _VEHICLES_DICT)
        self.assertEqual(xmlschema.to_dict(vh_xml_tree, self.vh_schema.url), _VEHICLES_DICT)

    def test_to_dict_from_etree(self):
        vh_xml_tree = _ElementTree.parse(self.abspath('cases/examples/vehicles/vehicles.xml'))
        col_xml_tree = _ElementTree.parse(self.abspath('cases/examples/collection/collection.xml'))

        xml_dict = self.vh_schema.to_dict(vh_xml_tree)
        self.assertNotEqual(xml_dict, _VEHICLES_DICT)  # XSI namespace unmapped

        xml_dict = self.vh_schema.to_dict(vh_xml_tree, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _VEHICLES_DICT)

        xml_dict = xmlschema.to_dict(vh_xml_tree, self.vh_schema.url, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _VEHICLES_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_tree)
        self.assertNotEqual(xml_dict, _COLLECTION_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_tree, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _COLLECTION_DICT)

        xml_dict = xmlschema.to_dict(col_xml_tree, self.col_schema.url, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _COLLECTION_DICT)

    def test_to_dict_from_string(self):
        with open(self.abspath('cases/examples/vehicles/vehicles.xml')) as f:
            vh_xml_string = f.read()

        with open(self.abspath('cases/examples/collection/collection.xml')) as f:
            col_xml_string = f.read()

        xml_dict = self.vh_schema.to_dict(vh_xml_string, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _VEHICLES_DICT)

        xml_dict = xmlschema.to_dict(vh_xml_string, self.vh_schema.url, namespaces=self.namespaces)
        self.assertEqual(xml_dict, _VEHICLES_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_string, namespaces=self.namespaces)
        self.assertTrue(xml_dict, _COLLECTION_DICT)

        xml_dict = xmlschema.to_dict(col_xml_string, self.col_schema.url, namespaces=self.namespaces)
        self.assertTrue(xml_dict, _COLLECTION_DICT)

    def test_path(self):
        xt = _ElementTree.parse(self.abspath('cases/examples/vehicles/vehicles.xml'))
        xd = self.vh_schema.to_dict(xt, '/vh:vehicles/vh:bikes', namespaces=self.namespaces)
        self.assertEqual(xd, _VEHICLES_DICT['vh:bikes'])
        xd = self.vh_schema.to_dict(xt, '/vh:vehicles/vh:bikes', namespaces=self.namespaces)
        self.assertEqual(xd, _VEHICLES_DICT['vh:bikes'])

    def test_validation_strict(self):
        self.assertRaises(
            xmlschema.XMLSchemaValidationError,
            self.vh_schema.to_dict,
            _ElementTree.parse(self.abspath('cases/examples/vehicles/vehicles-2_errors.xml')),
            validation='strict',
            namespaces=self.namespaces
        )

    def test_validation_skip(self):
        xt = _ElementTree.parse(self.abspath('cases/features/decoder/data3.xml'))
        xd = self.st_schema.decode(xt, validation='skip', namespaces=self.namespaces)
        self.assertEqual(xd['decimal_value'], ['abc'])

    def test_datatypes3(self):
        xt = _ElementTree.parse(self.abspath('cases/features/decoder/data.xml'))
        xd = self.st_schema.to_dict(xt, namespaces=self.namespaces)
        self.assertEqual(xd, _DATA_DICT)

    def test_converters(self):
        filename = self.abspath('cases/examples/collection/collection.xml')

        parker_dict = self.col_schema.to_dict(filename, converter=xmlschema.ParkerConverter)
        self.assertTrue(parker_dict == _COLLECTION_PARKER)

        parker_dict_root = self.col_schema.to_dict(
            filename, converter=xmlschema.ParkerConverter(preserve_root=True), decimal_type=float)
        self.assertTrue(parker_dict_root == _COLLECTION_PARKER_ROOT)

        badgerfish_dict = self.col_schema.to_dict(
            filename, converter=xmlschema.BadgerFishConverter, decimal_type=float)
        self.assertTrue(badgerfish_dict == _COLLECTION_BADGERFISH)

        abdera_dict = self.col_schema.to_dict(
            filename, converter=xmlschema.AbderaConverter, decimal_type=float, dict_class=dict)
        self.assertTrue(abdera_dict == _COLLECTION_ABDERA)

        json_ml_dict = self.col_schema.to_dict(filename, converter=xmlschema.JsonMLConverter)
        self.assertTrue(json_ml_dict == _COLLECTION_JSON_ML)

    def test_dict_granularity(self):
        """Based on Issue #22, test to make sure an xsd indicating list with
        dictionaries, returns just that even when it has a single dict. """
        xsd_string = self.abspath('cases/issues/issue_022/xsd_string.xsd')
        xml_string_1 = self.abspath('cases/issues/issue_022/xml_string_1.xml')
        xml_string_2 = self.abspath('cases/issues/issue_022/xml_string_2.xml')
        xsd_schema = xmlschema.XMLSchema(xsd_string)
        xml_data_1 = xsd_schema.to_dict(xml_string_1)
        xml_data_2 = xsd_schema.to_dict(xml_string_2)
        self.assertTrue(isinstance(xml_data_1['bar'], type(xml_data_2['bar'])),
                        msg="XSD with an array that return a single element from xml must still yield a list.")

    def test_any_type(self):
        any_type = xmlschema.XMLSchema.meta_schema.types['anyType']
        xml_data_1 = _ElementTree.Element('dummy')
        self.assertEqual(any_type.decode(xml_data_1), (None, [], []))
        xml_data_2 = _ElementTree.fromstring('<root>\n    <child_1/>\n    <child_2/>\n</root>')
        self.assertEqual(any_type.decode(xml_data_2), (None, [], []))  # Currently no decoding yet

    def test_choice_model_decoding(self):
        schema = xmlschema.XMLSchema(self.abspath('cases/issues/issue_041/issue_041.xsd'))
        data = schema.to_dict(self.abspath('cases/issues/issue_041/issue_041.xml'))
        self.assertEqual(data, {
            u'@xsi:noNamespaceSchemaLocation': 'issue_041.xsd',
            'Name': u'SomeNameValueThingy',
            'Value': {'Integer': 0}
        })

    def test_cdata_decoding(self):
        schema = xmlschema.XMLSchema(self.abspath('cases/issues/issue_046/issue_046.xsd'))
        xml_file = self.abspath('cases/issues/issue_046/issue_046.xml')
        self.assertEqual(
            schema.decode(xml_file, dict_class=OrderedDict, cdata_prefix='#'),
            OrderedDict([('@xsi:noNamespaceSchemaLocation', 'issue_046.xsd'),
                         ('#1', 'Dear Mr.'), ('name', 'John Smith'),
                         ('#2', '.\n  Your order'), ('orderid', 1032),
                         ('#3', 'will be shipped on'), ('shipdate', '2001-07-13'), ('#4', '.')])
        )

    def test_string_facets(self):
        none_empty_string_type = self.st_schema.types['none_empty_string']
        self.check_decode(none_empty_string_type, '', XMLSchemaValidationError)

    def test_binary_data_facets(self):
        hex_code_type = self.st_schema.types['hexCode']
        self.check_decode(hex_code_type, u'00D7310A', u'00D7310A')

        base64_code_type = self.st_schema.types['base64Code']
        self.check_decode(base64_code_type, base64.b64encode(b'ok'), XMLSchemaValidationError)
        base64_value = base64.b64encode(b'hello')
        self.check_decode(base64_code_type, base64_value, base64_value.decode('utf-8'))
        self.check_decode(base64_code_type, base64.b64encode(b'abcefgh'), u'YWJjZWZnaA==')
        self.check_decode(base64_code_type, b' Y  W J j ZWZ\t\tn\na A= =', u'Y W J j ZWZ n a A= =')
        self.check_decode(base64_code_type, u' Y  W J j ZWZ\t\tn\na A= =', u'Y W J j ZWZ n a A= =')
        self.check_decode(base64_code_type, base64.b64encode(b'abcefghi'), u'YWJjZWZnaGk=')

        self.check_decode(base64_code_type, u'YWJjZWZnaA=', XMLSchemaValidationError)
        self.check_decode(base64_code_type, u'YWJjZWZna$==', XMLSchemaValidationError)

        base64_length4_type = self.st_schema.types['base64Length4']
        self.check_decode(base64_length4_type, base64.b64encode(b'abc'), XMLSchemaValidationError)
        self.check_decode(base64_length4_type, base64.b64encode(b'abce'), u'YWJjZQ==')
        self.check_decode(base64_length4_type, base64.b64encode(b'abcef'), XMLSchemaValidationError)

        base64_length5_type = self.st_schema.types['base64Length5']
        self.check_decode(base64_length5_type, base64.b64encode(b'1234'), XMLSchemaValidationError)
        self.check_decode(base64_length5_type, base64.b64encode(b'12345'), u'MTIzNDU=')
        self.check_decode(base64_length5_type, base64.b64encode(b'123456'), XMLSchemaValidationError)

    def test_decimal_type(self):
        schema = self.get_schema("""
        <element name="A" type="ns:A_type" />
        <simpleType name="A_type">
            <restriction base="decimal">
                <minInclusive value="100.50"/>
            </restriction>
        </simpleType>
        """)

        self.check_decode(schema, '<A xmlns="ns">120.48</A>', Decimal('120.48'))
        self.check_decode(schema, '<A xmlns="ns">100.50</A>', Decimal('100.50'))
        self.check_decode(schema, '<A xmlns="ns">100.49</A>', XMLSchemaValidationError)
        self.check_decode(schema, '<A xmlns="ns">120.48</A>', 120.48, decimal_type=float)
        self.check_decode(schema, '<A xmlns="ns">120.48</A>', '120.48', decimal_type=str)  # Issue #66


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, tests_factory, get_testfiles

    print_test_header()
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    decoding_tests = tests_factory(make_decoding_test_function, testfiles, 'decoding', 'xml')
    lxml_decoding_tests = tests_factory(make_lxml_decoding_test_function, testfiles, 'lxml_decoding', 'xml')
    globals().update(decoding_tests)
    globals().update(lxml_decoding_tests)
    unittest.main()
