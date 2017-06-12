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
This module runs tests concerning the decoding of XML files with the 'xmlschema' package.
"""
from _test_common import *
import glob
import fileinput
import xmlschema
from decimal import Decimal
from xml.etree import ElementTree as _ElementTree
try:
    import lxml.etree as _etree
except ImportError:
    _etree = None


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


def create_decoding_tests(pathname):

    def make_test_decoding_function(xml_file, schema, expected_errors):
        def test_decoding(self):
            xs = xmlschema.XMLSchema(schema)
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
                        expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors[:]])
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

    # Two optional int arguments: [<test_only> [<log_level>]]
    if len(sys.argv) > 2:
        log_level = int(sys.argv.pop())
        xmlschema.set_logger('xmlschema', loglevel=log_level)
    if len(sys.argv) > 1:
        test_only = int(sys.argv.pop())
    else:
        test_only = None

    tests = {}
    test_num = 0
    for line in fileinput.input(glob.iglob(pathname)):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_args = get_test_args(line)
        filename = test_args[0]
        try:
            tot_errors = int(test_args[1])
        except (IndexError, ValueError):
            tot_errors = 0

        test_file = os.path.join(os.path.dirname(fileinput.filename()), filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.xml':
            continue

        schema_file = xmlschema.fetch_schema(test_file)
        test_func = make_test_decoding_function(test_file, schema_file, tot_errors)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        if test_only is None or test_num == test_only:
            klassname = 'Test_decoding_{0}_{1}'.format(test_num, test_name)
            tests[klassname] = type(
                klassname, (XMLSchemaTestCase,),
                {'test_decoding_{0}'.format(test_num): test_func}
            )

    return tests


class TestDecoding(unittest.TestCase):
    namespaces = {
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'vh': 'http://example.com/vehicles',
        'col': 'http://example.com/ns/collection',
        'dt': 'http://example.com/decoder'
    }
    vehicles_schema = xmlschema.XMLSchema('examples/vehicles/vehicles.xsd')
    collection_schema = xmlschema.XMLSchema('examples/collection/collection.xsd')

    @unittest.skipIf(_etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        xt1 = _etree.parse('examples/vehicles/vehicles.xml')
        self.assertTrue(self.vehicles_schema.to_dict(xt1) == _VEHICLES_DICT)
        self.assertTrue(xmlschema.to_dict(xt1, self.vehicles_schema.uri) == _VEHICLES_DICT)

    def test_to_dict_python3(self):
        xt1 = _ElementTree.parse('examples/vehicles/vehicles.xml')
        xt2 = _ElementTree.parse('examples/collection/collection.xml')
        self.assertFalse(self.vehicles_schema.to_dict(xt1) == _VEHICLES_DICT)
        self.assertTrue(
            self.vehicles_schema.to_dict(xt1, namespaces=self.namespaces) == _VEHICLES_DICT)
        self.assertTrue(
            xmlschema.to_dict(xt1, self.vehicles_schema.uri,
                              namespaces=self.namespaces) == _VEHICLES_DICT)
        self.assertTrue(
            self.collection_schema.to_dict(xt2, namespaces=self.namespaces) == _COLLECTION_DICT)
        self.assertTrue(
            xmlschema.to_dict(xt2, self.collection_schema.uri,
                              namespaces=self.namespaces) == _COLLECTION_DICT)

    def test_path(self):
        xs = xmlschema.XMLSchema('examples/vehicles/vehicles.xsd')
        xt1 = _ElementTree.parse('examples/vehicles/vehicles.xml')
        path = './vh:vehicles/vh:bikes'
        self.assertTrue(
            xs.to_dict(xt1, path, namespaces=self.namespaces) == _VEHICLES_DICT['vh:bikes']
        )

    def test_datatypes3(self):
        xs = xmlschema.XMLSchema('examples/decoder/decoder.xsd')
        xt1 = _ElementTree.parse('examples/decoder/data.xml')
        self.assertTrue(xs.to_dict(xt1, namespaces=self.namespaces) == _DATA_DICT)
        self.assertTrue(
            xs.to_dict('examples/decoder/data.xml', namespaces=self.namespaces.copy()) == _DATA_DICT
        )

    def test_formats(self):
        filename = 'examples/collection/collection.xml'

        parker_dict = self.collection_schema.to_dict(filename, converter=xmlschema.ParkerConverter)
        self.assertTrue(parker_dict == _COLLECTION_PARKER)

        parker_dict_root = self.collection_schema.to_dict(
            filename, converter=xmlschema.ParkerConverter(preserve_root=True), decimal_type=float)
        self.assertTrue(parker_dict_root == _COLLECTION_PARKER_ROOT)

        badgerfish_dict = self.collection_schema.to_dict(
            filename, converter=xmlschema.BadgerFishConverter, decimal_type=float)
        self.assertTrue(badgerfish_dict == _COLLECTION_BADGERFISH)

        abdera_dict = self.collection_schema.to_dict(
            filename, converter=xmlschema.AbderaConverter, decimal_type=float, dict_class=dict)
        self.assertTrue(abdera_dict == _COLLECTION_ABDERA)

        json_ml_dict = self.collection_schema.to_dict(filename, converter=xmlschema.JsonMLConverter)
        self.assertTrue(json_ml_dict == _COLLECTION_JSON_ML)


if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    globals().update(create_decoding_tests(os.path.join(pkg_folder, "tests/*/testfiles")))
    unittest.main()
