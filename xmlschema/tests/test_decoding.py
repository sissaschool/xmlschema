#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
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
from xml.etree import ElementTree as _ElementTree
try:
    import lxml.etree as _lxml_etree
except ImportError:
    _lxml_etree = None

import xmlschema
from xmlschema.qnames import local_name
from _test_common import XMLSchemaTestCase, tests_factory


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
    '@xsi:schemaLocation': 'http://example.com/decoder  ./decoder.xsd',
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


def make_test_decoding_function(xml_file, schema_class, expected_errors=0, inspect=False):
    def test_decoding(self):
        schema = xmlschema.fetch_schema(xml_file)
        xs = schema_class(schema)
        errors = []
        chunks = []
        for obj in xs.iter_decode(xml_file):
            if isinstance(obj, (xmlschema.XMLSchemaDecodeError, xmlschema.XMLSchemaValidationError)):
                errors.append(obj)
            else:
                chunks.append(obj)
        if len(errors) != expected_errors:
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (
                    expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors[:3]])
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
    namespaces = {
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'vh': 'http://example.com/vehicles',
        'col': 'http://example.com/ns/collection',
        'dt': 'http://example.com/decoder'
    }

    vh_schema = xmlschema.XMLSchema('examples/vehicles/vehicles.xsd')
    col_schema = xmlschema.XMLSchema('examples/collection/collection.xsd')
    decoder_schema = xmlschema.XMLSchema('examples/decoder/decoder.xsd')

    @unittest.skipIf(_lxml_etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        vh_xml_tree = _lxml_etree.parse('examples/vehicles/vehicles.xml')
        self.assertEqual(self.vh_schema.to_dict(vh_xml_tree), _VEHICLES_DICT)
        self.assertEqual(xmlschema.to_dict(vh_xml_tree, self.vh_schema.url), _VEHICLES_DICT)

    def test_to_dict_from_etree(self):
        vh_xml_tree = _ElementTree.parse('examples/vehicles/vehicles.xml')
        col_xml_tree = _ElementTree.parse('examples/collection/collection.xml')

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
        with open('examples/vehicles/vehicles.xml') as f:
            vh_xml_string = f.read()

        with open('examples/collection/collection.xml') as f:
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
        xt = _ElementTree.parse('examples/vehicles/vehicles.xml')
        xd = self.vh_schema.to_dict(xt, './vh:vehicles/vh:bikes', namespaces=self.namespaces)
        self.assertEqual(xd, _VEHICLES_DICT['vh:bikes'])

    def test_validation_strict(self):
        self.assertRaises(
            xmlschema.XMLSchemaValidationError,
            self.vh_schema.to_dict,
            _ElementTree.parse('examples/vehicles/vehicles-2_errors.xml'),
            validation='strict',
            namespaces=self.namespaces
        )

    def test_validation_skip(self):
        xt = _ElementTree.parse('examples/decoder/data3.xml')
        xd = self.decoder_schema.decode(xt, validation='skip', namespaces=self.namespaces)
        self.assertEqual(xd['decimal_value'], ['abc'])

    def test_datatypes3(self):
        xt = _ElementTree.parse('examples/decoder/data.xml')
        xd = self.decoder_schema.to_dict(xt, namespaces=self.namespaces)
        self.assertEqual(xd, _DATA_DICT)

    def test_converters(self):
        filename = 'examples/collection/collection.xml'

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

    def test_encoding(self):
        filename = 'examples/collection/collection.xml'
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

    def test_dict_granularity(self):
        """Based on Issue #22, test to make sure an xsd indicating list with
        dictionaries, returns just that even when it has a single dict. """
        xsd_string   = 'examples/issues/issue_022/xsd_string.xsd'
        xml_string_1 = 'examples/issues/issue_022/xml_string_1.xml'
        xml_string_2 = 'examples/issues/issue_022/xml_string_2.xml'
        xsd_schema = xmlschema.XMLSchema(xsd_string)
        xml_data_1 = xsd_schema.to_dict(xml_string_1)
        xml_data_2 = xsd_schema.to_dict(xml_string_2)
        self.assertTrue(type(xml_data_1['bar']) == type(xml_data_2['bar']),
                        msg="XSD with an array that return a single element from xml must still yield a list.")

if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    path = os.path.join(pkg_folder, "tests/*/testfiles")
    decoding_tests = tests_factory(make_test_decoding_function, path, 'decoding', 'xml')
    globals().update(decoding_tests)
    unittest.main()
