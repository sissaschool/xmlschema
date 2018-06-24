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
import pickle
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
from xmlschema.etree import (
    etree_element, etree_tostring, etree_iselement, etree_fromstring, etree_parse,
    etree_get_namespaces, etree_elements_equal
)
from xmlschema.qnames import local_name
from xmlschema import XMLSchemaEncodeError, XMLSchemaValidationError


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


def iter_nested_items(items, dict_class=dict, list_class=list):
    if isinstance(items, dict_class):
        for k, v in items.items():
            for value in iter_nested_items(v, dict_class, list_class):
                yield value
    elif isinstance(items, list_class):
        for item in items:
            for value in iter_nested_items(item, dict_class, list_class):
                yield value
    elif isinstance(items, dict):
        raise TypeError("%r: is a dict() instead of %r." % (items, dict_class))
    elif isinstance(items, list):
        raise TypeError("%r: is a list() instead of %r." % (items, list_class))
    else:
        yield items


def make_decoder_test_function(xml_file, schema_class, expected_errors=0, inspect=False,
                               locations=None, defuse='defuse'):

    def test_decoder(self):
        source, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        schema = schema_class(source, validation='lax', locations=_locations, defuse=defuse)
        errors = []
        chunks = []
        for obj in schema.iter_decode(xml_file):
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

        if not inspect and sys.version_info >= (3,):
            # Repeat with serialized-deserialized schema (only for Python 3)
            deserialized_schema = pickle.loads(pickle.dumps(schema))
            errors2 = []
            chunks2 = []
            for obj in deserialized_schema.iter_decode(xml_file):
                if isinstance(obj, xmlschema.XMLSchemaValidationError):
                    errors2.append(obj)
                else:
                    chunks2.append(obj)

            self.assertEqual(len(errors), len(errors2))
            self.assertEqual(chunks, chunks2)

        if not errors:
            # Compare with the decode API
            self.assertEqual(schema.decode(xml_file), chunks[0], "decode() API has a different result!")

        if _lxml_etree is not None:
            # Compare with lxml
            root = _lxml_etree.parse(xml_file)
            namespaces = etree_get_namespaces(xml_file)
            errors2 = []
            chunks2 = []
            for obj in schema.iter_decode(root, namespaces=namespaces):
                if isinstance(obj, xmlschema.XMLSchemaValidationError):
                    errors2.append(obj)
                else:
                    chunks2.append(obj)

            self.assertEqual(chunks, chunks2)
            self.assertEqual(len(errors), len(errors2))

        if not errors:
            # Encoding tests (only if the XML is strictly conforming to the schema)
            root = etree_parse(xml_file).getroot()
            namespaces = etree_get_namespaces(xml_file)
            dict_class = dict if sys.version_info >= (3, 6) else OrderedDict
            kwargs = {'namespaces': namespaces, 'cdata_prefix': '#'}

            def check_etree_encode(converter=None):
                data = schema.decode(root, dict_class=dict_class, converter=converter, **kwargs)
                for _ in iter_nested_items(data, dict_class=dict_class):
                    pass
                encoded_tree = schema.encode(data, path=root.tag, dict_class=dict_class, converter=converter, **kwargs)

                self.assertEqual(
                    schema.decode(encoded_tree, **kwargs), schema.decode(root, converter=converter, **kwargs)
                )

            check_etree_encode()

            # TODO: Full encode tests with other converters
            # check_etree_encode(converter=xmlschema.ParkerConverter)
            # check_etree_encode(converter=xmlschema.BadgerFishConverter)
            # check_etree_encode(converter=xmlschema.AbderaConverter)
            # check_etree_encode(converter=xmlschema.JsonMLConverter)

    return test_decoder


class TestValidation(XMLSchemaTestCase):

    def check_validity(self, xsd_component, data, expected, use_defaults=True):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.is_valid, data, use_defaults)
        elif expected:
            self.assertTrue(xsd_component.is_valid(data, use_defaults))
        else:
            self.assertFalse(xsd_component.is_valid(data, use_defaults))

    @unittest.skipIf(_lxml_etree is None, "The lxml library is not installed.")
    def test_lxml(self):
        xs = xmlschema.XMLSchema(self.abspath('cases/examples/vehicles/vehicles.xsd'))
        xt1 = _lxml_etree.parse(self.abspath('cases/examples/vehicles/vehicles.xml'))
        xt2 = _lxml_etree.parse(self.abspath('cases/examples/vehicles/vehicles-1_error.xml'))
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)

    def test_issue_064(self):
        self.check_validity(self.st_schema, '<name xmlns="ns"></name>', False)


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


class TestEncoding(XMLSchemaTestCase):

    def check_encode(self, xsd_component, data, expected, **kwargs):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.encode, data, **kwargs)
        elif etree_iselement(expected):
            elem = xsd_component.encode(data, **kwargs)
            self.assertTrue(etree_elements_equal(expected, elem, strict=False))
        else:
            obj = xsd_component.encode(data, **kwargs)
            if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[1], list) \
                    and isinstance(obj[1][0], Exception):
                self.assertEqual(expected, obj[0])
                self.assertTrue(isinstance(obj[0], type(expected)))
            elif etree_iselement(obj):
                self.assertEqual(expected, etree_tostring(obj).strip())
            else:
                self.assertEqual(expected, obj)
                self.assertTrue(isinstance(obj, type(expected)))

    def test_decode_encode(self):
        filename = os.path.join(self.test_dir, 'cases/examples/collection/collection.xml')
        xt = _ElementTree.parse(filename)
        xd = self.col_schema.to_dict(filename, dict_class=OrderedDict)
        elem = self.col_schema.encode(xd, path='./col:collection', namespaces=self.namespaces)

        self.assertEqual(
            len([e for e in elem.iter()]), 20,
            msg="The encoded tree must have 20 elements as the origin."
        )
        self.assertTrue(all([
            local_name(e1.tag) == local_name(e2.tag)
            for e1, e2 in zip(elem.iter(), xt.getroot().iter())
        ]))

    def test_builtin_string_based_types(self):
        self.check_encode(self.xsd_types['string'], 'sample string ', u'sample string ')
        self.check_encode(self.xsd_types['normalizedString'], ' sample string ', u' sample string ')
        self.check_encode(self.xsd_types['normalizedString'], '\n\r sample\tstring\n', u'   sample string ')
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

    def test_builtin_decimal_based_types(self):
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

    def test_builtin_list_types(self):
        self.check_encode(self.xsd_types['IDREFS'], ['first_name'], u'first_name')
        self.check_encode(self.xsd_types['IDREFS'], 'first_name', u'first_name')  # Transform data to list
        self.check_encode(self.xsd_types['IDREFS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['IDREFS'], [1, 'two', 'three'], XMLSchemaValidationError)
        self.check_encode(self.xsd_types['NMTOKENS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['ENTITIES'], ('mouse', 'cat', 'dog'), u'mouse cat dog')

    def test_list_types(self):
        list_of_strings = self.st_schema.types['list_of_strings']
        self.check_encode(list_of_strings, (10, 25, 40), u'', validation='lax')
        self.check_encode(list_of_strings, (10, 25, 40), u'10 25 40', validation='skip')
        self.check_encode(list_of_strings, ['a', 'b', 'c'], u'a b c', validation='skip')

        list_of_integers = self.st_schema.types['list_of_integers']
        self.check_encode(list_of_integers, (10, 25, 40), u'10 25 40')
        self.check_encode(list_of_integers, (10, 25.0, 40), XMLSchemaValidationError)
        self.check_encode(list_of_integers, (10, 25.0, 40), u'10 25 40', validation='lax')

        list_of_floats = self.st_schema.types['list_of_floats']
        self.check_encode(list_of_floats, [10.1, 25.0, 40.0], u'10.1 25.0 40.0')
        self.check_encode(list_of_floats, [10.1, 25, 40.0], u'10.1 25.0 40.0', validation='lax')
        self.check_encode(list_of_floats, [10.1, False, 40.0], u'10.1 0.0 40.0', validation='lax')

        list_of_booleans = self.st_schema.types['list_of_booleans']
        self.check_encode(list_of_booleans, [True, False, True], u'true false true')
        self.check_encode(list_of_booleans, [10, False, True], XMLSchemaEncodeError)
        self.check_encode(list_of_booleans, [True, False, 40.0], u'true false', validation='lax')
        self.check_encode(list_of_booleans, [True, False, 40.0], u'true false 40.0', validation='skip')

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
        elem = etree_element('{ns}A')
        elem.text = '89'
        self.check_encode(self.get_element('A', type='string'), '89', elem)
        self.check_encode(self.get_element('A', type='integer'), 89, elem)
        elem.text = '-10.4'
        self.check_encode(self.get_element('A', type='float'), -10.4, elem)
        elem.text = 'false'
        self.check_encode(self.get_element('A', type='boolean'), False, elem)
        elem.text = 'true'
        self.check_encode(self.get_element('A', type='boolean'), True, elem)

        self.check_encode(self.get_element('A', type='short'), 128000, XMLSchemaValidationError)
        elem.text = '0'
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), 0, elem)
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), '0', XMLSchemaValidationError)
        self.check_encode(self.get_element('A', type='positiveInteger'), 0, XMLSchemaValidationError)
        elem.text = '-1'
        self.check_encode(self.get_element('A', type='negativeInteger'), -1, elem)
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), -1, XMLSchemaValidationError)

    def test_complex_elements(self):
        schema = self.get_schema("""
        <element name="A" type="ns:A_type" />
        <complexType name="A_type" mixed="true">
            <simpleContent>
                <extension base="string">
                    <attribute name="a1" type="short" use="required"/>                 
                    <attribute name="a2" type="negativeInteger"/>
                </extension>
            </simpleContent>
        </complexType>
        """)
        self.check_encode(
            schema.elements['A'], data={'@a1': 10, '@a2': -1, '$': 'simple '},
            expected='<ns:A xmlns:ns="ns" a1="10" a2="-1">simple </ns:A>'
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1, '$': 'simple '},
            etree_fromstring('<A xmlns="ns" a1="10" a2="-1">simple </A>'),
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1},
            etree_fromstring('<A xmlns="ns" a1="10" a2="-1"/>')
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '$': 'simple '},
            etree_fromstring('<A xmlns="ns" a1="10">simple </A>')
        )
        self.check_encode(schema.elements['A'], {'@a2': -1, '$': 'simple '}, XMLSchemaValidationError)

        schema = self.get_schema("""
        <element name="A" type="ns:A_type" />
        <complexType name="A_type">
            <sequence>
                <element name="B1" type="string"/>
                <element name="B2" type="integer"/>
                <element name="B3" type="boolean"/>                
            </sequence>
        </complexType>
        """)
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=OrderedDict([('B1', 'abc'), ('B2', 10), ('B3', False)]),
            expected=u'<ns:A xmlns:ns="ns">\n<B1>abc</B1>\n<B2>10</B2>\n<B3>false</B3>\n  </ns:A>',
            indent=0,
        )
        self.check_encode(schema.elements['A'], {'B1': 'abc', 'B2': 10, 'B4': False}, XMLSchemaValidationError)
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=OrderedDict([('B1', 'abc'), ('B2', 10), ('#1', 'hello')]),
            expected=u'<ns:A xmlns:ns="ns">\n<B1>abc</B1>\n<B2>10</B2>hello\n  </ns:A>',
            indent=0, cdata_prefix='#'
        )


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, tests_factory, get_testfiles

    print_test_header()
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    decoder_tests = tests_factory(make_decoder_test_function, testfiles, 'decoder', 'xml')
    globals().update(decoder_tests)
    unittest.main()
