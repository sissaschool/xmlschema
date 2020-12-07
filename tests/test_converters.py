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

try:
    from lxml.etree import Element as lxml_etree_element
except ImportError:
    lxml_etree_element = None

from xmlschema import XMLSchema, XMLSchemaConverter
from xmlschema.etree import etree_element
from xmlschema.testing.helpers import etree_elements_assert_equal

from xmlschema.converters import ColumnarConverter


class TestConverters(unittest.TestCase):

    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), 'test_cases')

    @classmethod
    def casepath(cls, relative_path):
        return os.path.join(cls.TEST_CASES_DIR, relative_path)

    def test_element_class_argument(self):
        converter = XMLSchemaConverter()
        self.assertIs(converter.etree_element_class, etree_element)

        converter = XMLSchemaConverter(etree_element_class=etree_element)
        self.assertIs(converter.etree_element_class, etree_element)

        if lxml_etree_element is not None:
            converter = XMLSchemaConverter(etree_element_class=lxml_etree_element)
            self.assertIs(converter.etree_element_class, lxml_etree_element)

    def test_prefix_arguments(self):
        converter = XMLSchemaConverter(cdata_prefix='#')
        self.assertEqual(converter.cdata_prefix, '#')

        converter = XMLSchemaConverter(attr_prefix='%')
        self.assertEqual(converter.attr_prefix, '%')

        converter = XMLSchemaConverter(attr_prefix='_')
        self.assertEqual(converter.attr_prefix, '_')

        converter = XMLSchemaConverter(attr_prefix='attribute__')
        self.assertEqual(converter.attr_prefix, 'attribute__')

        converter = XMLSchemaConverter(text_key='text__')
        self.assertEqual(converter.text_key, 'text__')

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

    def test_preserve_root__issue_215(self):
        schema = XMLSchema("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                   xmlns="http://xmlschema.test/ns"
                   targetNamespace="http://xmlschema.test/ns">
            <xs:element name="a">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="b1" type="xs:string" maxOccurs="unbounded"/>
                        <xs:element name="b2" type="xs:string" maxOccurs="unbounded"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
        </xs:schema> 
        """)

        xml_data = """<tns:a xmlns:tns="http://xmlschema.test/ns"><b1/><b2/></tns:a>"""

        obj = schema.decode(xml_data)
        self.assertListEqual(list(obj), ['@xmlns:tns', 'b1', 'b2'])
        self.assertEqual(schema.encode(obj).tag, '{http://xmlschema.test/ns}a')

        obj = schema.decode(xml_data, preserve_root=True)
        self.assertListEqual(list(obj), ['tns:a'])

        root = schema.encode(obj, preserve_root=True, path='tns:a',
                             namespaces={'tns': 'http://xmlschema.test/ns'})
        self.assertEqual(root.tag, '{http://xmlschema.test/ns}a')

        root = schema.encode(obj, preserve_root=True, path='{http://xmlschema.test/ns}a')
        self.assertEqual(root.tag, '{http://xmlschema.test/ns}a')

        root = schema.encode(obj, preserve_root=True)
        self.assertEqual(root.tag, '{http://xmlschema.test/ns}a')

    def test_etree_element_method(self):
        converter = XMLSchemaConverter()
        elem = converter.etree_element('A')
        self.assertIsNone(etree_elements_assert_equal(elem, etree_element('A')))

        elem = converter.etree_element('A', attrib={})
        self.assertIsNone(etree_elements_assert_equal(elem, etree_element('A')))

    def test_parquet_converter(self):
        col_xsd_filename = self.casepath('examples/collection/collection.xsd')
        col_xml_filename = self.casepath('examples/collection/collection.xml')

        col_schema = XMLSchema(col_xsd_filename, converter=ColumnarConverter)

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

        obj = col_schema.decode(col_xml_filename, converter=ColumnarConverter, attr_prefix='__')
        self.assertNotIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertIn("'author__id'", str(obj))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema converters with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
