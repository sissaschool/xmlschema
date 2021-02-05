#!/usr/bin/env python
#
# Copyright (c), 2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import os
import xml.etree.ElementTree as ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema, fetch_namespaces, etree_tostring
from xmlschema.helpers import is_etree_element
from xmlschema.dataobjects import DataElement
from xmlschema.testing import etree_elements_assert_equal

from xmlschema.converters import DataElementConverter


class TestDataElement(unittest.TestCase):

    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), 'test_cases')

    @classmethod
    def setUpClass(cls):
        cls.col_xsd_filename = cls.casepath('examples/collection/collection.xsd')
        cls.col_xml_filename = cls.casepath('examples/collection/collection.xml')
        cls.col_xml_root = ElementTree.parse(cls.col_xml_filename).getroot()
        cls.col_lxml_root = lxml_etree.parse(cls.col_xml_filename).getroot()
        cls.col_nsmap = fetch_namespaces(cls.col_xml_filename)
        cls.col_namespace = cls.col_nsmap['col']
        cls.col_schema = XMLSchema(cls.col_xsd_filename, converter=DataElementConverter)

    @classmethod
    def casepath(cls, relative_path):
        return os.path.join(cls.TEST_CASES_DIR, relative_path)

    def test_repr(self):
        self.assertEqual(repr(DataElement('foo')), "DataElement(tag='foo')")

    def test_value(self):
        self.assertIsNone(DataElement('foo').value)
        self.assertEqual(DataElement('foo', value=10).value, 10)
        self.assertEqual(DataElement('foo', 1.8).value, 1.8)
        self.assertFalse(DataElement('foo', False).value)

    def test_attributes(self):
        self.assertEqual(DataElement('foo').attrib, {})
        attrib = {'a': 10, 'b': 'bar'}
        self.assertEqual(DataElement('foo', attrib=attrib).attrib, attrib)
        self.assertEqual(DataElement('foo', attrib=attrib).get('a'), 10)
        self.assertIsNone(DataElement('foo', attrib=attrib).get('c'))

    def test_namespaces(self):
        self.assertEqual(DataElement('foo').nsmap, {})
        nsmap = {'tns': 'http://xmlschema.test/ns'}
        self.assertEqual(DataElement('foo', nsmap=nsmap).nsmap, nsmap)

    def test_text_value(self):
        self.assertIsNone(DataElement('foo').text)
        self.assertEqual(DataElement('foo', value=True).text, 'true')
        self.assertEqual(DataElement('foo', value=False).text, 'false')
        self.assertEqual(DataElement('foo', value=10.0).text, '10.0')

    def test_namespace(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertIsInstance(col_data, DataElement)
        self.assertEqual(col_data.tag, '{http://example.com/ns/collection}collection')
        self.assertEqual(col_data.namespace, 'http://example.com/ns/collection')

        self.assertEqual(col_data[0].tag, 'object')
        self.assertEqual(col_data[0].namespace, 'http://example.com/ns/collection')

        self.assertEqual(DataElement('foo').namespace, '')

    def test_names(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertEqual(col_data.tag, '{http://example.com/ns/collection}collection')
        self.assertEqual(col_data.name, col_data.tag)
        self.assertEqual(col_data.prefixed_name, 'col:collection')
        self.assertEqual(col_data.local_name, 'collection')

        self.assertEqual(col_data[1].tag, 'object')
        self.assertEqual(col_data[1].prefixed_name, 'object')
        self.assertEqual(col_data[1].local_name, 'object')

    def test_mutable_mapping_api(self):
        data_element = DataElement('root')

        self.assertEqual(len(data_element), 0)
        with self.assertRaises(AssertionError):
            data_element.append(1)

        data_element.append(DataElement('elem1'))
        self.assertEqual(len(data_element), 1)
        self.assertEqual(data_element[0].tag, 'elem1')

        data_element.insert(0, DataElement('elem0'))
        self.assertEqual(len(data_element), 2)
        self.assertEqual(data_element[0].tag, 'elem0')
        self.assertEqual(data_element[1].tag, 'elem1')

        data_element[0] = DataElement('elem2')
        self.assertEqual(data_element[0].tag, 'elem2')

        del data_element[0]
        self.assertEqual(len(data_element), 1)
        self.assertEqual(data_element[0].tag, 'elem1')

    def test_xpath_api(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertIs(col_data.find('.'), col_data)
        self.assertIs(col_data.find('*'), col_data[0])
        self.assertIs(col_data.find('object[2]'), col_data[1])

        self.assertListEqual(col_data.findall('*'), col_data[:])
        self.assertListEqual(list(col_data.iterfind('*')), col_data[:])

    def test_iter(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertEqual(len(list(col_data.iter())), len(list(self.col_xml_root.iter())))
        for elem, data_element in zip(self.col_xml_root.iter(), col_data.iter()):
            self.assertEqual(elem.tag, data_element.tag)
            self.assertIsInstance(data_element, DataElement)

        self.assertEqual(len(list(col_data.iter('*'))), len(list(col_data.iter())))
        self.assertEqual(len(list(col_data.iter('object'))), 2)

    def test_iterchildren(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertListEqual(list(col_data.iterchildren()), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('*')), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('object')), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('position')), [])

    def test_schema_bindings(self):
        data_element = DataElement('foo')
        self.assertIsNone(data_element.xsd_type)

        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertIs(col_data.xsd_type, self.col_schema.elements['collection'].type)
        self.assertIs(col_data._xsd_type, self.col_schema.elements['collection'].type)

        col_data.xsd_type = None
        self.assertIs(col_data.xsd_type, self.col_schema.elements['collection'].type)
        self.assertIsNone(col_data._xsd_type)

        col_data.xsd_element = None
        self.assertIsNone(col_data.xsd_type)

    def test_encode_to_element_tree(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        obj = col_data.encode()
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, self.col_xml_root, strict=False))

        col_data.xsd_type = None
        obj = col_data.encode()
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, self.col_xml_root, strict=False))

        col_data.xsd_type = col_data.xsd_element.type
        col_data.xsd_element = None
        obj = col_data.encode()
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, self.col_xml_root, strict=False))

        any_data = DataElement('a')
        any_data.append(DataElement('b1', 1999))
        any_data.append(DataElement('b2', 'alpha'))
        any_data.append(DataElement('b3', True))

        with self.assertRaises(ValueError) as ec:
            any_data.encode()
        self.assertIn("no schema bindings and valition mode is not 'skip'", str(ec.exception))

        root = ElementTree.XML('<a><b1>1999</b1><b2>alpha</b2><b3>true</b3></a>')

        obj = any_data.encode(validation='skip')
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, root, strict=False))

        any_data = DataElement('root', attrib={'a1': 49})
        any_data.append(DataElement('child', 18.7, attrib={'a2': False}))

        root = ElementTree.XML('<root a1="49"><child a2="false">18.7</child></root>')

        obj = any_data.encode(validation='skip')
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, root, strict=False))

    def test_serialize_to_xml_source(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        xml_source = col_data.tostring()
        self.assertTrue(xml_source.startswith('<col:collection '))
        self.assertTrue(xml_source.endswith('</col:collection>'))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema data objects with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
