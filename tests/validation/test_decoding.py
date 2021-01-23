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
import unittest
import os
from decimal import Decimal
import base64

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from elementpath import datatypes
import xmlschema
from xmlschema import XMLSchemaValidationError, ParkerConverter, BadgerFishConverter, \
    AbderaConverter, JsonMLConverter, ColumnarConverter

from xmlschema.etree import ElementTree
from xmlschema.converters import UnorderedConverter
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase

VEHICLES_DICT = {
    '@xmlns:vh': 'http://example.com/vehicles',
    '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
    'vh:cars': {
        'vh:car': [
            {'@make': 'Porsche', '@model': '911'},
            {'@make': 'Porsche', '@model': '911'}
        ]},
    'vh:bikes': {
        'vh:bike': [
            {'@make': 'Harley-Davidson', '@model': 'WL'},
            {'@make': 'Yamaha', '@model': 'XS650'}
        ]}
}

VEHICLES_DICT_ALT = [
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

COLLECTION_DICT = {
    '@xmlns:col': 'http://example.com/ns/collection',
    '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
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

COLLECTION_PARKER = {
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

COLLECTION_PARKER_ROOT = {
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

COLLECTION_BADGERFISH = {
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

COLLECTION_ABDERA = {
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

COLLECTION_JSON_ML = [
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


COLLECTION_COLUMNAR = {
    'collection': {
        'collectionxsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
        'object': [{
            'objectid': 'b0836217462',
            'objectavailable': True,
            'position': 1,
            'title': 'The Umbrellas',
            'year': '1886',
            'author': {
                'authorid': 'PAR',
                'name': 'Pierre-Auguste Renoir',
                'born': '1841-02-25',
                'dead': '1919-12-03',
                'qualification': 'painter'
            },
            'estimation': Decimal('10000.00')}, {
            'objectid': 'b0836217463',
            'objectavailable': True,
            'position': 2,
            'title': None,
            'year': '1925',
            'author': {
                'authorid': 'JM',
                'name': 'Joan Miró',
                'born': '1893-04-20',
                'dead': '1983-12-25',
                'qualification': 'painter, sculptor and ceramicist'
            }
        }]
    }
}

COLLECTION_COLUMNAR_ = {
    'collection': {
        'collection_xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
        'object': [{
            'object_id': 'b0836217462',
            'object_available': True,
            'position': 1,
            'title': 'The Umbrellas',
            'year': '1886',
            'author': {
                'author_id': 'PAR',
                'name': 'Pierre-Auguste Renoir',
                'born': '1841-02-25',
                'dead': '1919-12-03',
                'qualification': 'painter'
            },
            'estimation': Decimal('10000.00')}, {
            'object_id': 'b0836217463',
            'object_available': True,
            'position': 2,
            'title': None,
            'year': '1925',
            'author': {
                'author_id': 'JM',
                'name': 'Joan Miró',
                'born': '1893-04-20',
                'dead': '1983-12-25',
                'qualification': 'painter, sculptor and ceramicist'
            }
        }]
    }
}

DATA_DICT = {
    '@xmlns:ns': 'ns',
    '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    '@xsi:schemaLocation': 'ns ./simple-types.xsd',
    'certification': [
        {'$': 'ISO-9001', '@Year': 1999},
        {'$': 'ISO-27001', '@Year': 2009}
    ],
    'decimal_value': [Decimal('1')],
    'hexbin': 'AABBCCDD',
    'menù': 'baccalà mantecato',
    'complex_boolean': [
        {'$': True, '@Type': 2}, {'$': False, '@Type': 1}, True, False
    ],
    'simple_boolean': [True, False],
    'date_and_time': '2020-03-05T23:04:10.047',  # xs:dateTime is not decoded for default
}


class TestDecoding(XsdValidatorTestCase):
    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')

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

    @unittest.skipIf(lxml_etree is None, "The lxml library is not available.")
    def test_lxml(self):
        vh_xml_tree = lxml_etree.parse(self.vh_xml_file)
        self.assertEqual(self.vh_schema.to_dict(vh_xml_tree), VEHICLES_DICT)
        self.assertEqual(xmlschema.to_dict(vh_xml_tree, self.vh_schema.url), VEHICLES_DICT)

    def test_to_dict_from_etree(self):
        vh_xml_tree = ElementTree.parse(self.vh_xml_file)
        col_xml_tree = ElementTree.parse(self.col_xml_file)

        xml_dict = self.vh_schema.to_dict(vh_xml_tree)
        self.assertNotEqual(xml_dict, VEHICLES_DICT)

        xml_dict = self.vh_schema.to_dict(vh_xml_tree, namespaces=self.vh_namespaces)
        self.assertEqual(xml_dict, VEHICLES_DICT)

        xml_dict = xmlschema.to_dict(vh_xml_tree, self.vh_schema.url, namespaces=self.vh_namespaces)
        self.assertEqual(xml_dict, VEHICLES_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_tree)
        self.assertNotEqual(xml_dict, COLLECTION_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_tree, namespaces=self.col_namespaces)
        self.assertEqual(xml_dict, COLLECTION_DICT)

        xml_dict = xmlschema.to_dict(col_xml_tree, self.col_schema.url,
                                     namespaces=self.col_namespaces)
        self.assertEqual(xml_dict, COLLECTION_DICT)

    def test_to_dict_from_string(self):
        with open(self.vh_xml_file) as f:
            vh_xml_string = f.read()

        with open(self.col_xml_file) as f:
            col_xml_string = f.read()

        xml_dict = self.vh_schema.to_dict(vh_xml_string, namespaces=self.vh_namespaces)
        self.assertEqual(xml_dict, VEHICLES_DICT)

        xml_dict = xmlschema.to_dict(vh_xml_string, self.vh_schema.url,
                                     namespaces=self.vh_namespaces)
        self.assertEqual(xml_dict, VEHICLES_DICT)

        xml_dict = self.col_schema.to_dict(col_xml_string, namespaces=self.col_namespaces)
        self.assertTrue(xml_dict, COLLECTION_DICT)

        xml_dict = xmlschema.to_dict(col_xml_string, self.col_schema.url,
                                     namespaces=self.col_namespaces)
        self.assertTrue(xml_dict, COLLECTION_DICT)

    def test_date_decoding(self):
        # Issue #136
        schema = xmlschema.XMLSchema("""<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="1.0">
                <xs:element name="Date">
                    <xs:simpleType>
                        <xs:restriction base="xs:date">
                            <xs:minInclusive value="2000-01-01"/>
                            <xs:maxInclusive value="2099-12-31"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:element>
            </xs:schema>""")

        self.assertEqual(schema.to_dict("<Date>2019-01-01</Date>"), '2019-01-01')
        self.assertEqual(schema.to_dict("<Date>2019-01-01</Date>", datetime_types=True),
                         datatypes.Date10.fromstring('2019-01-01'))

        data, errors = schema.to_dict("<Date>2019-01-01</Date>", validation='lax')
        self.assertEqual(data, '2019-01-01')
        self.assertEqual(errors, [])

        data, errors = schema.to_dict("<Date>2019-01-01</Date>", validation='lax',
                                      datetime_types=True)
        self.assertEqual(data, datatypes.Date10.fromstring('2019-01-01'))
        self.assertEqual(errors, [])

        data, errors = schema.to_dict("<Date>1999-12-31</Date>", validation='lax')
        self.assertEqual(data, '1999-12-31')
        self.assertEqual(len(errors), 1)
        self.assertIn('value has to be greater or equal than', str(errors[0]))

        data, errors = schema.to_dict("<Date>1999-12-31</Date>", validation='lax',
                                      datetime_types=True)
        self.assertEqual(data, datatypes.Date10.fromstring('1999-12-31'))
        self.assertEqual(len(errors), 1)

        data, errors = schema.to_dict("<Date>2019</Date>", validation='lax')
        self.assertIsNone(data)
        self.assertEqual(len(errors), 1)

        with self.assertRaises(XMLSchemaValidationError):
            schema.to_dict("<Date>2019</Date>")

        data, errors = schema.to_dict("<Date>2019</Date>", validation='lax')
        self.assertIsNone(data)
        self.assertEqual(len(errors), 1)

    def test_qname_decoding(self):
        schema = self.schema_class("""<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" type="rootType" />
              <xs:complexType name="rootType">
                <xs:simpleContent>
                  <xs:extension base="xs:QName">
                    <xs:attribute name="name" type="xs:QName"/>
                  </xs:extension>
                </xs:simpleContent>
              </xs:complexType>
            </xs:schema>""")

        xml_data = '<root xmlns:ns0="http://xmlschema.test/0">ns0:foo</root>'
        self.assertEqual(schema.decode(xml_data), 'ns0:foo')

        self.assertEqual(schema.decode('<root>foo</root>'), 'foo')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.decode('<root>ns0:foo</root>')
        self.assertIn("failed validating 'ns0:foo'", str(ctx.exception))
        self.assertIn("Reason: unmapped prefix 'ns0' on QName", str(ctx.exception))
        self.assertIn("Path: /root", str(ctx.exception))

        xml_data = '<root name="ns0:bar" xmlns:ns0="http://xmlschema.test/0">ns0:foo</root>'
        self.assertEqual(schema.decode(xml_data), {'@name': 'ns0:bar', '$': 'ns0:foo'})

        # Check reverse encoding
        obj = schema.decode(xml_data, converter=JsonMLConverter)
        root = schema.encode(obj, converter=JsonMLConverter)
        self.assertEqual(ElementTree.tostring(root), b'<root name="ns0:bar">ns0:foo</root>\n')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.decode('<root name="ns0:bar">foo</root>')
        self.assertIn("failed validating 'ns0:bar'", str(ctx.exception))
        self.assertIn("unmapped prefix 'ns0' on QName", str(ctx.exception))
        self.assertIn("Path: /root", str(ctx.exception))

    def test_json_dump_and_load(self):
        vh_xml_tree = ElementTree.parse(self.vh_xml_file)
        col_xml_tree = ElementTree.parse(self.col_xml_file)
        with open(self.vh_json_file, 'w') as f:
            xmlschema.to_json(self.vh_xml_file, f)

        with open(self.vh_json_file) as f:
            root = xmlschema.from_json(f, self.vh_schema)

        os.remove(self.vh_json_file)
        self.check_etree_elements(vh_xml_tree.getroot(), root)

        with open(self.col_json_file, 'w') as f:
            xmlschema.to_json(self.col_xml_file, f)

        with open(self.col_json_file) as f:
            root = xmlschema.from_json(f, self.col_schema)

        os.remove(self.col_json_file)
        self.check_etree_elements(col_xml_tree.getroot(), root)

    def test_json_path_decoding(self):
        xml_file = self.col_xml_file
        schema = self.col_schema

        json_data = xmlschema.to_json(xml_file, schema=schema, path='*')
        self.assertIsInstance(json_data, str)
        self.assertEqual(len(json_data), 493)
        self.assertEqual(json_data[:4], '[{"@')
        self.assertEqual(json_data[-1], ']')

        self.assertEqual(
            json_data, xmlschema.to_json(xml_file, schema=schema, path='object')
        )
        self.assertEqual(
            json_data, xmlschema.to_json(xml_file, schema=schema, path='//object')
        )
        self.assertEqual(
            json_data, xmlschema.to_json(xml_file, schema=schema, path='/col:collection/object')
        )

    def test_json_lazy_decoding(self):
        kwargs = {'xml_document': self.col_xml_file, 'schema': self.col_schema}

        col_json = xmlschema.to_json(**kwargs)
        self.assertIsInstance(col_json, str)
        self.assertEqual(len(col_json), 688)
        self.assertTrue(col_json.startswith('{"@xmlns:'))
        self.assertEqual(col_json[-1], '}')

        self.assertEqual(
            col_json, xmlschema.to_json(lazy=True, **kwargs)
        )

        json_data = xmlschema.to_json(path='object', **kwargs)
        self.assertIn(json_data, col_json)
        self.assertEqual(
            json_data, xmlschema.to_json(path='object', lazy=True, **kwargs)
        )
        self.assertEqual(
            json_data, xmlschema.to_json(validation='skip', path='object', lazy=True, **kwargs)
        )

        json_data = xmlschema.to_json(path='object/author', **kwargs)
        self.assertIsInstance(json_data, str)
        self.assertEqual(len(json_data), 259)
        self.assertEqual(json_data[:4], '[{"@')
        self.assertEqual(json_data[-1], ']')

        self.assertEqual(
            json_data, xmlschema.to_json(path='object/author', lazy=True, **kwargs)
        )
        self.assertEqual(json_data, xmlschema.to_json(
            validation='skip', path='object/author', lazy=True, **kwargs
        ))

        # Tests for issue #159
        self.assertEqual(json_data, xmlschema.to_json(
            path='/col:collection/object/author', lazy=True, **kwargs
        ))
        self.assertEqual(json_data, xmlschema.to_json(
            validation='skip', path='/col:collection/object/author', lazy=True, **kwargs
        ))

    def test_path(self):
        xt = ElementTree.parse(self.vh_xml_file)
        xd = self.vh_schema.to_dict(xt, '/vh:vehicles/vh:cars', namespaces=self.vh_namespaces)
        self.assertEqual(xd['vh:car'], VEHICLES_DICT['vh:cars']['vh:car'])
        xd = self.vh_schema.to_dict(xt, '/vh:vehicles/vh:bikes', namespaces=self.vh_namespaces)
        self.assertEqual(xd['vh:bike'], VEHICLES_DICT['vh:bikes']['vh:bike'])

    def test_non_global_schema_path(self):
        # Issue #157
        xs = xmlschema.XMLSchema("""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                xmlns:foo="http://example.com/foo" 
                targetNamespace="http://example.com/foo">
            <xs:complexType name="type1">
                <xs:sequence>
                    <xs:element name="sub_part1" type="xs:string" />
                </xs:sequence>
            </xs:complexType>
            <xs:complexType name="type2">
                <xs:sequence>
                    <xs:element name="sub_part2" type="xs:string" />
                </xs:sequence>
            </xs:complexType>
            <xs:element name="foo">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="part1" type="foo:type1" />
                        <xs:element name="part2" type="foo:type2" />
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
        </xs:schema>""")

        self.assertEqual(
            xs.to_dict(
                """<part1 xmlns:foo="http://example.com/foo">
                    <sub_part1>test</sub_part1>
                </part1>""",
                schema_path='.//part1',
            ),
            {"sub_part1": "test"}
        )

    def test_validation_strict(self):
        self.assertRaises(
            xmlschema.XMLSchemaValidationError,
            self.vh_schema.to_dict,
            ElementTree.parse(self.casepath('examples/vehicles/vehicles-2_errors.xml')),
            validation='strict',
            namespaces=self.vh_namespaces
        )

    def test_validation_skip(self):
        xt = ElementTree.parse(self.casepath('features/decoder/data3.xml'))
        xd = self.st_schema.decode(xt, validation='skip', namespaces={'ns': 'ns'})
        self.assertEqual(xd['decimal_value'], ['abc'])

    def test_datatypes(self):
        xt = ElementTree.parse(self.casepath('features/decoder/data.xml'))
        xd = self.st_schema.to_dict(xt, namespaces=self.default_namespaces)
        self.assertEqual(xd, DATA_DICT)

    def test_datetime_types(self):
        xs = self.get_schema('<xs:element name="dt" type="xs:dateTime"/>')
        self.assertEqual(xs.decode('<dt>2019-01-01T13:40:00</dt>'), '2019-01-01T13:40:00')
        self.assertEqual(xs.decode('<dt>2019-01-01T13:40:00</dt>', datetime_types=True),
                         datatypes.DateTime10.fromstring('2019-01-01T13:40:00'))

        xs = self.get_schema('<xs:element name="dt" type="xs:date"/>')
        self.assertEqual(xs.decode('<dt>2001-04-15</dt>'), '2001-04-15')
        self.assertEqual(xs.decode('<dt>2001-04-15</dt>', datetime_types=True),
                         datatypes.Date10.fromstring('2001-04-15'))

    def test_duration_type(self):
        xs = self.get_schema('<xs:element name="td" type="xs:duration"/>')
        self.assertEqual(xs.decode('<td>P5Y3MT60H30.001S</td>'), 'P5Y3MT60H30.001S')
        self.assertEqual(xs.decode('<td>P5Y3MT60H30.001S</td>', datetime_types=True),
                         datatypes.Duration.fromstring('P5Y3M2DT12H30.001S'))

    def test_default_converter(self):
        self.assertEqual(self.col_schema.to_dict(self.col_xml_file), COLLECTION_DICT)

        default_dict = self.col_schema.to_dict(self.col_xml_file,
                                               converter=xmlschema.XMLSchemaConverter)
        self.assertEqual(default_dict, COLLECTION_DICT)

        default_dict_root = self.col_schema.to_dict(self.col_xml_file, preserve_root=True)
        self.assertEqual(default_dict_root, {'col:collection': COLLECTION_DICT})

    def test_visitor_converter(self):
        visitor_dict = self.col_schema.to_dict(self.col_xml_file, converter=UnorderedConverter)
        self.assertEqual(visitor_dict, COLLECTION_DICT)

        visitor_dict_root = self.col_schema.to_dict(
            self.col_xml_file, converter=UnorderedConverter(preserve_root=True))
        self.assertEqual(visitor_dict_root, {'col:collection': COLLECTION_DICT})

    def test_parker_converter(self):
        parker_dict = self.col_schema.to_dict(self.col_xml_file,
                                              converter=xmlschema.ParkerConverter)
        self.assertEqual(parker_dict, COLLECTION_PARKER)

        parker_dict_root = self.col_schema.to_dict(
            self.col_xml_file, converter=ParkerConverter(preserve_root=True), decimal_type=float)
        self.assertEqual(parker_dict_root, COLLECTION_PARKER_ROOT)

    def test_badgerfish_converter(self):
        badgerfish_dict = self.col_schema.to_dict(
            self.col_xml_file, converter=BadgerFishConverter, decimal_type=float)
        self.assertEqual(badgerfish_dict, COLLECTION_BADGERFISH)

    def test_abdera_converter(self):
        abdera_dict = self.col_schema.to_dict(
            self.col_xml_file, converter=AbderaConverter, decimal_type=float, dict_class=dict)
        self.assertEqual(abdera_dict, COLLECTION_ABDERA)

    def test_json_ml_converter(self):
        json_ml_dict = self.col_schema.to_dict(self.col_xml_file, converter=JsonMLConverter)
        self.assertEqual(json_ml_dict, COLLECTION_JSON_ML)

    def test_columnar_converter(self):
        columnar_dict = self.col_schema.to_dict(self.col_xml_file, converter=ColumnarConverter)
        self.assertEqual(columnar_dict, COLLECTION_COLUMNAR)
        columnar_dict = self.col_schema.to_dict(
            self.col_xml_file, converter=ColumnarConverter, attr_prefix='_',
        )
        self.assertEqual(columnar_dict, COLLECTION_COLUMNAR_)

        with self.assertRaises(ValueError) as ctx:
            self.col_schema.to_dict(
                self.col_xml_file, converter=ColumnarConverter, attr_prefix='-',
            )
        self.assertEqual(str(ctx.exception),
                         "attr_prefix can be the empty string or a single/double underscore")

    def test_dict_granularity(self):
        """Based on Issue #22, test to make sure an xsd indicating list with
        dictionaries, returns just that even when it has a single dict. """
        xsd_string = self.casepath('issues/issue_022/xsd_string.xsd')
        xml_string_1 = self.casepath('issues/issue_022/xml_string_1.xml')
        xml_string_2 = self.casepath('issues/issue_022/xml_string_2.xml')
        xsd_schema = xmlschema.XMLSchema(xsd_string)
        xml_data_1 = xsd_schema.to_dict(xml_string_1)
        xml_data_2 = xsd_schema.to_dict(xml_string_2)
        self.assertTrue(isinstance(xml_data_1['bar'], type(xml_data_2['bar'])),
                        msg="XSD with an array that return a single element from "
                            "xml must still yield a list.")

    def test_any_type(self):
        any_type = xmlschema.XMLSchema.meta_schema.types['anyType']
        xml_data_1 = ElementTree.Element('dummy')
        self.assertIsNone(any_type.decode(xml_data_1))
        xml_data_2 = ElementTree.fromstring('<root>\n    <child_1/>\n    <child_2/>\n</root>')
        self.assertIsNone(any_type.decode(xml_data_2))  # Currently no decoding yet

    def test_choice_model_decoding__issue_041(self):
        schema = xmlschema.XMLSchema(self.casepath('issues/issue_041/issue_041.xsd'))
        data = schema.to_dict(self.casepath('issues/issue_041/issue_041.xml'))
        self.assertEqual(data, {
            '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            '@xsi:noNamespaceSchemaLocation': 'issue_041.xsd',
            'Name': 'SomeNameValueThingy',
            'Value': {'Integer': 0}
        })

    def test_cdata_decoding(self):
        schema = xmlschema.XMLSchema(self.casepath('issues/issue_046/issue_046.xsd'))
        xml_file = self.casepath('issues/issue_046/issue_046.xml')
        self.assertEqual(
            schema.decode(xml_file, cdata_prefix='#'),
            dict(
                [('@xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance'),
                 ('@xsi:noNamespaceSchemaLocation', 'issue_046.xsd'),
                 ('#1', 'Dear Mr.'), ('name', 'John Smith'),
                 ('#2', '.\n  Your order'), ('orderid', 1032),
                 ('#3', 'will be shipped on'), ('shipdate', '2001-07-13'), ('#4', '.')]
            ))

    def test_string_facets(self):
        none_empty_string_type = self.st_schema.types['none_empty_string']
        self.check_decode(none_empty_string_type, '', XMLSchemaValidationError)
        name_type = self.st_schema.types['NameType']
        self.check_decode(name_type, '', XMLSchemaValidationError)

    def test_hex_binary_type(self):
        hex_code_type = self.st_schema.types['hexCode']
        self.check_decode(hex_code_type, '00D7310A', datatypes.HexBinary(b'00D7310A'))
        self.check_decode(hex_code_type, 'D7310A', XMLSchemaValidationError)

        xs = self.get_schema('<xs:element name="hex" type="xs:hexBinary"/>')

        obj = xs.decode('<hex> 9AFD </hex>')
        self.assertEqual(obj, ' 9AFD ')
        self.assertIsInstance(obj, str)

        obj = xs.decode('<hex> 9AFD </hex>', binary_types=True)
        self.assertEqual(obj, '9AFD')
        self.assertIsInstance(obj, datatypes.HexBinary)

    def test_base64_binary_type(self):
        base64_code_type = self.st_schema.types['base64Code']
        self.check_decode(base64_code_type, base64.b64encode(b'ok'), XMLSchemaValidationError)
        base64_value = base64.b64encode(b'hello')

        expected_value = datatypes.Base64Binary(base64_value)
        self.check_decode(base64_code_type, base64_value, expected_value)

        xs = self.get_schema('<xs:element name="b64" type="xs:base64Binary"/>')

        obj = xs.decode('<b64>{}</b64>'.format(base64_value.decode()))
        self.assertEqual(obj, expected_value)
        self.assertIsInstance(obj, str)

        obj = xs.decode('<b64>{}</b64>'.format(base64_value.decode()), binary_types=True)
        self.assertEqual(obj, expected_value)
        self.assertIsInstance(obj, datatypes.Base64Binary)

        self.check_decode(base64_code_type, base64.b64encode(b'abcefgh'),
                          datatypes.Base64Binary('YWJjZWZnaA=='))
        self.check_decode(base64_code_type, b' Y  W J j ZWZ\t\tn\na A= =',
                          datatypes.Base64Binary('Y W J j ZWZ n a A= ='))
        self.check_decode(base64_code_type, u' Y  W J j ZWZ\t\tn\na A= =',
                          datatypes.Base64Binary('Y W J j ZWZ n a A= ='))
        self.check_decode(base64_code_type, base64.b64encode(b'abcefghi'),
                          datatypes.Base64Binary('YWJjZWZnaGk='))

        self.check_decode(base64_code_type, u'YWJjZWZnaA=', XMLSchemaValidationError)
        self.check_decode(base64_code_type, u'YWJjZWZna$==', XMLSchemaValidationError)

        base64_length4_type = self.st_schema.types['base64Length4']
        self.check_decode(base64_length4_type, base64.b64encode(b'abc'),
                          XMLSchemaValidationError)
        self.check_decode(base64_length4_type, base64.b64encode(b'abce'),
                          datatypes.Base64Binary('YWJjZQ=='))
        self.check_decode(base64_length4_type, base64.b64encode(b'abcef'),
                          XMLSchemaValidationError)

        base64_length5_type = self.st_schema.types['base64Length5']
        self.check_decode(base64_length5_type, base64.b64encode(b'1234'),
                          XMLSchemaValidationError)
        self.check_decode(base64_length5_type, base64.b64encode(b'12345'),
                          datatypes.Base64Binary('MTIzNDU='))
        self.check_decode(base64_length5_type, base64.b64encode(b'123456'),
                          XMLSchemaValidationError)

    def test_decimal_type(self):
        schema = self.get_schema("""
        <xs:element name="A" type="A_type" />
        <xs:simpleType name="A_type">
          <xs:restriction base="xs:decimal">
            <xs:minInclusive value="100.50"/>
          </xs:restriction>
        </xs:simpleType>
        """)

        self.check_decode(schema, '<A>120.48</A>', Decimal('120.48'))
        self.check_decode(schema, '<A>100.50</A>', Decimal('100.50'), process_namespaces=False)
        self.check_decode(schema, '<A>100.49</A>', XMLSchemaValidationError)
        self.check_decode(schema, '<A>120.48</A>', 120.48, decimal_type=float)
        # Issue #66
        self.check_decode(schema, '<A>120.48</A>', '120.48', decimal_type=str)

    def test_nillable__issue_076(self):
        xsd_string = """<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified">
            <xs:element name="foo" type="Foo" />
            <xs:complexType name="Foo">
                <xs:sequence minOccurs="1" maxOccurs="1">
                    <xs:element name="bar" type="xs:integer" nillable="true" />
                </xs:sequence>
            </xs:complexType>
        </xs:schema>
        """
        xsd_schema = xmlschema.XMLSchema(xsd_string)
        xml_string_1 = "<foo><bar>0</bar></foo>"
        xml_string_2 = """<?xml version="1.0" encoding="UTF-8"?>
        <foo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <bar xsi:nil="true"></bar>
        </foo>
        """
        self.assertTrue(xsd_schema.is_valid(source=xml_string_1, use_defaults=False))
        self.assertTrue(xsd_schema.is_valid(source=xml_string_2, use_defaults=False))
        obj = xsd_schema.decode(xml_string_2, use_defaults=False)
        self.check_etree_elements(ElementTree.fromstring(xml_string_2), xsd_schema.encode(obj))

    def test_default_namespace__issue_077(self):
        xs = xmlschema.XMLSchema("""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
            targetNamespace="http://example.com/foo">
          <xs:element name="foo" type="xs:string" />
        </xs:schema>""")
        self.assertEqual(xs.to_dict("""<foo xmlns="http://example.com/foo">bar</foo>""",
                                    path='/foo', namespaces={'': 'http://example.com/foo'}), 'bar')
        self.assertEqual(xs.to_dict("""<foo>bar</foo>""",
                                    path='/foo', namespaces={'': 'http://example.com/foo'}), None)

    def test_complex_with_simple_content_restriction(self):
        xs = self.schema_class(
            self.casepath('features/derivations/complex-with-simple-content-restriction.xsd')
        )
        self.assertTrue(xs.is_valid('<value>10</value>'))
        self.assertFalse(xs.is_valid('<value>alpha</value>'))
        self.assertEqual(xs.decode('<value>10</value>'), 10)

    def test_union_types__issue_103(self):
        decimal_or_nan = self.st_schema.types['myType']
        self.check_decode(decimal_or_nan, '95.0', Decimal('95.0'))
        self.check_decode(decimal_or_nan, 'NaN', u'NaN')

    def test_default_values__issue_108(self):
        # From issue #108
        xsd_text = """<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" type="root" default="default_value"/>
              <xs:complexType name="root">
                <xs:simpleContent>
                  <xs:extension base="xs:string">
                    <xs:attribute name="attr" type="xs:string"/>
                    <xs:attribute name="attrWithDefault" type="xs:string" default="default_value"/>
                    <xs:attribute name="attrWithFixed" type="xs:string" fixed="fixed_value"/>
                  </xs:extension>
                </xs:simpleContent>
              </xs:complexType>
              <xs:element name="simple_root" type="xs:string" default="default_value"/>
            </xs:schema>"""

        schema = self.schema_class(xsd_text)
        self.assertEqual(schema.to_dict("<root>text</root>"),
                         {'@attrWithDefault': 'default_value',
                          '@attrWithFixed': 'fixed_value',
                          '$': 'text'})
        self.assertEqual(schema.to_dict("<root/>"),
                         {'@attrWithDefault': 'default_value',
                          '@attrWithFixed': 'fixed_value',
                          '$': 'default_value'})
        self.assertEqual(schema.to_dict("""<root attr="attr_value">text</root>"""),
                         {'$': 'text',
                          '@attr': 'attr_value',
                          '@attrWithDefault': 'default_value',
                          '@attrWithFixed': 'fixed_value'})

        self.assertEqual(schema.to_dict("<root>text</root>", use_defaults=False),
                         {'@attrWithFixed': 'fixed_value', '$': 'text'})
        self.assertEqual(schema.to_dict("""<root attr="attr_value">text</root>""",
                                        use_defaults=False),
                         {'$': 'text', '@attr': 'attr_value', '@attrWithFixed': 'fixed_value'})
        self.assertEqual(schema.to_dict("<root/>", use_defaults=False),
                         {'@attrWithFixed': 'fixed_value'})

        self.assertEqual(schema.to_dict("<simple_root/>"), 'default_value')
        self.assertIsNone(schema.to_dict("<simple_root/>", use_defaults=False))

    def test_decoding_errors_with_validation_modes(self):
        schema = self.schema_class("""<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" type="rootType" />
              <xs:complexType name="rootType">
                <xs:simpleContent>
                  <xs:extension base="xs:int">
                    <xs:attribute name="int_attr" type="xs:int"/>
                    <xs:attribute name="bool_attr" type="xs:boolean"/>
                  </xs:extension>
                </xs:simpleContent>
              </xs:complexType>
              <xs:element name="simple_root" type="xs:float"/>
            </xs:schema>""")

        self.assertIsNone(schema.to_dict("<simple_root>alpha</simple_root>", validation='lax')[0])
        self.assertEqual(schema.to_dict("<root int_attr='10'>20</root>"),
                         {'@int_attr': 10, '$': 20})
        self.assertEqual(schema.to_dict("<root int_attr='wrong'>20</root>", validation='lax')[0],
                         {'@int_attr': None, '$': 20})
        self.assertEqual(schema.to_dict("<root int_attr='wrong'>20</root>", validation='skip'),
                         {'@int_attr': 'wrong', '$': 20})

    def test_keep_unknown_tags__issue_204(self):
        schema = self.schema_class(self.casepath('issues/issue_204/issue_204.xsd'))
        self.assertTrue(schema.is_valid(self.casepath('issues/issue_204/issue_204_1.xml')))
        self.assertFalse(schema.is_valid(self.casepath('issues/issue_204/issue_204_2.xml')))

        data = schema.decode(self.casepath('issues/issue_204/issue_204_2.xml'), validation='lax')
        self.assertEqual(set(x for x in data[0] if x[0] != '@'), {'child2', 'child5'})

        data = schema.decode(self.casepath('issues/issue_204/issue_204_3.xml'), validation='lax')
        self.assertEqual(set(x for x in data[0] if x[0] != '@'), {'child2', 'child5'})

        data = schema.decode(self.casepath('issues/issue_204/issue_204_3.xml'),
                             validation='lax', keep_unknown=True)
        self.assertEqual(set(x for x in data[0] if x[0] != '@'), {'child2', 'unknown', 'child5'})
        self.assertEqual(data[0]['unknown'], {'a': [{'$': '1'}], 'b': [None]})

        data = schema.decode(self.casepath('issues/issue_204/issue_204_2.xml'), validation='skip')
        self.assertEqual(set(x for x in data if x[0] != '@'), {'child2', 'child5'})

        data = schema.decode(self.casepath('issues/issue_204/issue_204_3.xml'),
                             validation='skip', keep_unknown=True)
        self.assertEqual(set(x for x in data if x[0] != '@'), {'child2', 'unknown', 'child5'})
        self.assertEqual(data['unknown'], {'a': [{'$': '1'}], 'b': [None]})

    def test_error_message__issue_115(self):
        schema = self.schema_class(self.casepath('issues/issue_115/Rotation.xsd'))
        rotation_data = '<tns:rotation xmlns:tns="http://www.example.org/Rotation/" ' \
                        'pitch="0.0" roll="0.0" yaw="-1.0" />'

        message_lines = []
        try:
            schema.decode(rotation_data)
        except Exception as err:
            message_lines = str(err).split('\n')

        self.assertTrue(message_lines, msg="Empty error message!")
        self.assertEqual(message_lines[-6], 'Instance:')
        self.assertEqual(message_lines[-4].strip(), rotation_data)
        self.assertEqual(message_lines[-2], 'Path: /tns:rotation')

    def test_empty_base_type_extension_single_value(self):
        xsd_text = """<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            >
              <xs:element name="root" type="rootType" />

              <xs:complexType name="BaseType" abstract="true">
                <xs:sequence />
              </xs:complexType>


              <xs:complexType name="ExtensionType">
                <xs:complexContent>
                  <xs:extension base="BaseType">
                    <xs:sequence>
                      <xs:element name="Content" type="xs:string" />
                    </xs:sequence>
                  </xs:extension>
                </xs:complexContent>
              </xs:complexType>

              <xs:complexType name="rootType">
                <xs:sequence>
                    <xs:element name="ExtensionSub" type="BaseType" />
                </xs:sequence>
              </xs:complexType>
            </xs:schema>"""

        schema = self.schema_class(xsd_text)
        result = schema.to_dict(
            """<root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
              <ExtensionSub xsi:type="ExtensionType">
                <Content>my content</Content>
              </ExtensionSub>
            </root>"""
        )
        expected = {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "ExtensionSub": {
                "@xsi:type": "ExtensionType",
                "Content": "my content",
            }
        }
        self.assertEqual(result, expected)

    def test_issue_190(self):
        # Changed is_single() for XsdElement to check also parent group.
        schema = self.schema_class(self.casepath('issues/issue_190/issue_190.xsd'))
        self.assertEqual(
            schema.to_dict(self.casepath('issues/issue_190/issue_190.xml')),
            {'a': {'c': [{'$': '1'}]}, 'b': {'c': [{'$': '1'}], 'e': [{'$': '1'}]}}
        )

    def test_issue_200(self):
        # Schema path is required when path doesn't resolve to an XSD element
        schema = self.schema_class(self.casepath('issues/issue_200/issue_200.xsd'))
        self.assertEqual(
            schema.to_dict(self.casepath('issues/issue_200/issue_200.xml'),
                           path='/na:main/na:item[@doc_id=1]'),
            {'@doc_id': 1, '@ref_id': 'k1', '$': 'content_k1'}
        )
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.to_dict(self.casepath('issues/issue_200/issue_200.xml'),
                           path='/na:main/na:item[@doc_id=2]'),
        self.assertIn('is not an element of the schema', str(ctx.exception))


class TestDecoding11(TestDecoding):
    schema_class = XMLSchema11

    def test_datetime_types(self):
        xs = self.get_schema('<xs:element name="dt" type="xs:dateTime"/>')
        self.assertEqual(xs.decode('<dt>2019-01-01T13:40:00</dt>'), '2019-01-01T13:40:00')
        self.assertEqual(xs.decode('<dt>2019-01-01T13:40:00</dt>', datetime_types=True),
                         datatypes.DateTime.fromstring('2019-01-01T13:40:00'))

        xs = self.get_schema('<xs:element name="dt" type="xs:date"/>')
        self.assertEqual(xs.decode('<dt>2001-04-15</dt>'), '2001-04-15')
        self.assertEqual(xs.decode('<dt>2001-04-15</dt>', datetime_types=True),
                         datatypes.Date.fromstring('2001-04-15'))

    def test_derived_duration_types(self):
        xs = self.get_schema('<xs:element name="td" type="xs:yearMonthDuration"/>')
        self.assertEqual(xs.decode('<td>P0Y4M</td>'), 'P0Y4M')
        self.assertEqual(xs.decode('<td>P2Y10M</td>', datetime_types=True),
                         datatypes.Duration.fromstring('P2Y10M'))

        xs = self.get_schema('<xs:element name="td" type="xs:dayTimeDuration"/>')
        self.assertEqual(xs.decode('<td>P2DT6H30M30.001S</td>'), 'P2DT6H30M30.001S')
        self.assertEqual(xs.decode('<td>P2DT26H</td>'), 'P2DT26H')
        self.assertEqual(xs.decode('<td>P2DT6H30M30.001S</td>', datetime_types=True),
                         datatypes.Duration.fromstring('P2DT6H30M30.001S'))

    def test_type_alternatives(self):
        xs = self.schema_class(self.casepath('features/elements/type_alternatives-no-ns.xsd'))
        self.assertTrue(xs.is_valid('<value choice="int">10</value>'))
        self.assertFalse(xs.is_valid('<value choice="int">10.1</value>'))
        self.assertTrue(xs.is_valid('<value choice="float">10.1</value>'))
        self.assertFalse(xs.is_valid('<value choice="float">alpha</value>'))
        self.assertFalse(xs.is_valid('<value choice="bool">alpha</value>'))
        self.assertTrue(xs.is_valid('<value choice="bool">0</value>'))
        self.assertTrue(xs.is_valid('<value choice="bool">true</value>'))

        xs = self.schema_class(self.casepath('features/elements/type_alternatives.xsd'))
        self.assertTrue(xs.is_valid('<ns:value xmlns:ns="ns" choice="int">10</ns:value>'))
        self.assertFalse(xs.is_valid('<ns:value xmlns:ns="ns" choice="int">10.1</ns:value>'))
        self.assertTrue(xs.is_valid('<ns:value xmlns:ns="ns" choice="float">10.1</ns:value>'))
        self.assertFalse(xs.is_valid('<ns:value xmlns:ns="ns" choice="float">alpha</ns:value>'))
        self.assertFalse(xs.is_valid('<ns:value xmlns:ns="ns" choice="bool">alpha</ns:value>'))
        self.assertTrue(xs.is_valid('<ns:value xmlns:ns="ns" choice="bool">0</ns:value>'))
        self.assertTrue(xs.is_valid('<ns:value xmlns:ns="ns" choice="bool">true</ns:value>'))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema decoding with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
