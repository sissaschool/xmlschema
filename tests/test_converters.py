#!/usr/bin/env python
#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import os

from xmlschema import XMLSchema, XMLSchemaConverter, ElementData
from xmlschema.etree import etree_element, etree_register_namespace, \
    lxml_etree_element, lxml_etree_register_namespace, etree_elements_assert_equal

from xmlschema.converters import ParquetConverter


class TestConverters(unittest.TestCase):

    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), 'test_cases')

    @classmethod
    def casepath(cls, relative_path):
        return os.path.join(cls.TEST_CASES_DIR, relative_path)

    def test_element_class_argument(self):
        converter = XMLSchemaConverter()
        self.assertIs(converter.etree_element_class, etree_element)
        self.assertIs(converter.register_namespace, etree_register_namespace)

        converter = XMLSchemaConverter(etree_element_class=etree_element)
        self.assertIs(converter.etree_element_class, etree_element)
        self.assertIs(converter.register_namespace, etree_register_namespace)

        if lxml_etree_element is not None:
            converter = XMLSchemaConverter(etree_element_class=lxml_etree_element)
            self.assertIs(converter.etree_element_class, lxml_etree_element)
            self.assertIs(converter.register_namespace, lxml_etree_register_namespace)

        with self.assertRaises(TypeError):
            XMLSchemaConverter(etree_element_class=ElementData)

    def test_prefix_arguments(self):
        converter = XMLSchemaConverter(cdata_prefix='#')
        self.assertEqual(converter.cdata_prefix, '#')

        converter = XMLSchemaConverter(attr_prefix='%')
        self.assertEqual(converter.attr_prefix, '%')

        with self.assertRaises(ValueError):
            XMLSchemaConverter(attr_prefix='_')

    def test_strip_namespace_argument(self):
        # Test for issue #161
        converter = XMLSchemaConverter(strip_namespaces=True)
        col_xsd_filename = self.casepath('examples/collection/collection.xsd')
        col_xml_filename = self.casepath('examples/collection/collection.xml')

        col_schema = XMLSchema(col_xsd_filename, converter=converter)
        self.assertIn('@xmlns:', str(col_schema.decode(col_xml_filename, strip_namespaces=False)))
        self.assertNotIn('@xmlns:', str(col_schema.decode(col_xml_filename)))

    def test_lossy_property(self):
        self.assertTrue(XMLSchemaConverter().lossy)
        self.assertFalse(XMLSchemaConverter(cdata_prefix='#').lossy)

    def test_cdata_mapping(self):
        schema = XMLSchema("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="root">
                <xs:complexType mixed="true">
                    <xs:sequence>
                        <xs:element name="node" type="xs:string" maxOccurs="unbounded"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
        </xs:schema> 
        """)

        self.assertEqual(
            schema.decode('<root>1<node/>2<node/>3</root>'), {'node': [None, None]}
        )
        self.assertEqual(
            schema.decode('<root>1<node/>2<node/>3</root>', cdata_prefix='#'),
            {'#1': '1', 'node': [None, None], '#2': '2', '#3': '3'}
        )

    def test_etree_element_method(self):
        converter = XMLSchemaConverter()
        elem = converter.etree_element('A')
        self.assertIsNone(etree_elements_assert_equal(elem, etree_element('A')))

        elem = converter.etree_element('A', attrib={})
        self.assertIsNone(etree_elements_assert_equal(elem, etree_element('A')))

    def test_parquet_converter(self):
        col_xsd_filename = self.casepath('examples/collection/collection.xsd')
        col_xml_filename = self.casepath('examples/collection/collection.xml')

        col_schema = XMLSchema(col_xsd_filename, converter=ParquetConverter)

        obj = col_schema.decode(col_xml_filename)
        self.assertIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertNotIn("'author__id'", str(obj))

        obj = col_schema.decode(col_xml_filename, attr_prefix='_')
        self.assertNotIn("'authorid'", str(obj))
        self.assertIn("'author_id'", str(obj))
        self.assertNotIn("'author__id'", str(obj))

        obj = col_schema.decode(col_xml_filename, attr_prefix='__')
        self.assertNotIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertIn("'author__id'", str(obj))

        col_schema = XMLSchema(col_xsd_filename)

        obj = col_schema.decode(col_xml_filename, converter=ParquetConverter, attr_prefix='__')
        self.assertNotIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertIn("'author__id'", str(obj))


if __name__ == '__main__':
    from xmlschema.testing import print_test_header

    print_test_header()
    unittest.main()
