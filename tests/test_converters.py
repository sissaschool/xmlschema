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
from xml.etree.ElementTree import Element, parse as etree_parse
from pathlib import Path
from typing import cast, MutableMapping, Optional, Type

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from elementpath.etree import etree_tostring

from xmlschema import XMLSchema, XMLSchemaValidationError, fetch_namespaces
from xmlschema.dataobjects import DataElement
from xmlschema.testing import etree_elements_assert_equal

from xmlschema.converters import XMLSchemaConverter, UnorderedConverter, \
    ParkerConverter, BadgerFishConverter, AbderaConverter, JsonMLConverter, \
    ColumnarConverter
from xmlschema.dataobjects import DataElementConverter


class TestConverters(unittest.TestCase):
    col_xsd_filename: str
    col_xml_filename: str
    col_nsmap: MutableMapping[str, str]
    col_lxml_root: Optional['lxml_etree.ElementTree']

    col_xsd_filename: str
    col_xml_filename: str
    col_nsmap: dict

    @classmethod
    def setUpClass(cls):
        cls.col_xsd_filename = cls.casepath('examples/collection/collection.xsd')
        cls.col_xml_filename = cls.casepath('examples/collection/collection.xml')
        cls.col_xml_root = etree_parse(cls.col_xml_filename).getroot()
        cls.col_nsmap = fetch_namespaces(cls.col_xml_filename)
        cls.col_namespace = cls.col_nsmap['col']

        if lxml_etree is not None:
            cls.col_lxml_root = lxml_etree.parse(cls.col_xml_filename).getroot()
        else:
            cls.col_lxml_root = None

    @classmethod
    def casepath(cls, relative_path):
        return str(Path(__file__).parent.joinpath('test_cases', relative_path))

    def test_element_class_argument(self):
        converter = XMLSchemaConverter()
        self.assertIs(converter.etree_element_class, Element)

        converter = XMLSchemaConverter(etree_element_class=Element)
        self.assertIs(converter.etree_element_class, Element)

        if lxml_etree is not None:
            converter = XMLSchemaConverter(
                etree_element_class=cast(Type[Element], lxml_etree.Element)
            )
            self.assertIs(converter.etree_element_class, lxml_etree.Element)

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
        </xs:schema>""")

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
        self.assertIsNone(etree_elements_assert_equal(elem, Element('A')))

        elem = converter.etree_element('A', attrib={})
        self.assertIsNone(etree_elements_assert_equal(elem, Element('A')))

    def test_columnar_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=ColumnarConverter)

        obj = col_schema.decode(self.col_xml_filename)
        self.assertIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertNotIn("'author__id'", str(obj))

        obj = col_schema.decode(self.col_xml_filename, attr_prefix='_')
        self.assertNotIn("'authorid'", str(obj))
        self.assertIn("'author_id'", str(obj))
        self.assertNotIn("'author__id'", str(obj))

        obj = col_schema.decode(self.col_xml_filename, attr_prefix='__')
        self.assertNotIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertIn("'author__id'", str(obj))

        col_schema = XMLSchema(self.col_xsd_filename)

        obj = col_schema.decode(self.col_xml_filename, converter=ColumnarConverter,
                                attr_prefix='__')
        self.assertNotIn("'authorid'", str(obj))
        self.assertNotIn("'author_id'", str(obj))
        self.assertIn("'author__id'", str(obj))

    def test_data_element_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=DataElementConverter)
        obj = col_schema.decode(self.col_xml_filename)

        self.assertIsInstance(obj, DataElement)
        self.assertEqual(obj.tag, self.col_xml_root.tag)
        self.assertEqual(obj.nsmap, self.col_nsmap)

    def test_decode_encode_default_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename)

        # Decode from XML file
        obj1 = col_schema.decode(self.col_xml_filename)
        self.assertIn("'@xmlns:col'", repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Decode from lxml.etree.Element tree
        if self.col_lxml_root is not None:
            obj2 = col_schema.decode(self.col_lxml_root)
            self.assertIn("'@xmlns:col'", repr(obj2))
            self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree providing namespaces
        obj2 = col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap)
        self.assertIn("'@xmlns:col'", repr(obj2))
        self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree without namespaces
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotIn("'@xmlns:col'", repr(obj2))
        self.assertNotEqual(obj1, obj2)

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_default_converter_with_preserve_root(self):
        col_schema = XMLSchema(self.col_xsd_filename)

        # Decode from XML file
        obj1 = col_schema.decode(self.col_xml_filename, preserve_root=True)
        self.assertIn("'col:collection'", repr(obj1))
        self.assertIn("'@xmlns:col'", repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap,
                                 preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1, preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Decode from lxml.etree.Element tree
        if self.col_lxml_root is not None:
            obj2 = col_schema.decode(self.col_lxml_root, preserve_root=True)
            self.assertIn("'col:collection'", repr(obj2))
            self.assertIn("'@xmlns:col'", repr(obj2))
            self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree providing namespaces
        obj2 = col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap, preserve_root=True)
        self.assertIn("'col:collection'", repr(obj2))
        self.assertIn("'@xmlns:col'", repr(obj2))
        self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree without namespaces
        obj2 = col_schema.decode(self.col_xml_root, preserve_root=True)
        self.assertNotIn("'col:collection'", repr(obj2))
        self.assertNotIn("'@xmlns:col'", repr(obj2))
        self.assertNotEqual(obj1, obj2)

        root = col_schema.encode(obj2, path='./col:collection',
                                 namespaces=self.col_nsmap, preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2, preserve_root=True)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_unordered_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=UnorderedConverter)

        # Decode from XML file
        obj1 = col_schema.decode(self.col_xml_filename)
        self.assertIn("'@xmlns:col'", repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Decode from lxml.etree.Element tree
        if self.col_lxml_root is not None:
            obj2 = col_schema.decode(self.col_lxml_root)
            self.assertIn("'@xmlns:col'", repr(obj2))
            self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree providing namespaces
        obj2 = col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap)
        self.assertIn("'@xmlns:col'", repr(obj2))
        self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree without namespaces
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotIn("'@xmlns:col'", repr(obj2))
        self.assertNotEqual(obj1, obj2)

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_unordered_converter_with_preserve_root(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=UnorderedConverter)

        # Decode from XML file
        obj1 = col_schema.decode(self.col_xml_filename, preserve_root=True)
        self.assertIn("'col:collection'", repr(obj1))
        self.assertIn("'@xmlns:col'", repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap,
                                 preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1, preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Decode from lxml.etree.Element tree
        if self.col_lxml_root is not None:
            obj2 = col_schema.decode(self.col_lxml_root, preserve_root=True)
            self.assertIn("'col:collection'", repr(obj2))
            self.assertIn("'@xmlns:col'", repr(obj2))
            self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree providing namespaces
        obj2 = col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap, preserve_root=True)
        self.assertIn("'col:collection'", repr(obj2))
        self.assertIn("'@xmlns:col'", repr(obj2))
        self.assertEqual(obj1, obj2)

        # Decode from ElementTree.Element tree without namespaces
        obj2 = col_schema.decode(self.col_xml_root, preserve_root=True)
        self.assertNotIn("'col:collection'", repr(obj2))
        self.assertNotIn("'@xmlns:col'", repr(obj2))
        self.assertNotEqual(obj1, obj2)

        root = col_schema.encode(obj2, path='./col:collection',
                                 namespaces=self.col_nsmap, preserve_root=True)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2, preserve_root=True)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_parker_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=ParkerConverter)

        obj1 = col_schema.decode(self.col_xml_filename)

        with self.assertRaises(XMLSchemaValidationError) as ec:
            col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIn("missing required attribute 'id'", str(ec.exception))

    def test_decode_encode_badgerfish_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=BadgerFishConverter)

        obj1 = col_schema.decode(self.col_xml_filename)
        self.assertIn("'@xmlns'", repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # With ElementTree namespaces are not mapped
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotIn("'@xmlns'", repr(obj2))
        self.assertNotEqual(obj1, obj2)
        self.assertEqual(obj1, col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap))

        # With lxml.etree namespaces are mapped
        if self.col_lxml_root is not None:
            self.assertEqual(obj1, col_schema.decode(self.col_lxml_root))

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_abdera_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=AbderaConverter)

        obj1 = col_schema.decode(self.col_xml_filename)

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Namespace mapping is required
        with self.assertRaises(XMLSchemaValidationError) as ec:
            col_schema.encode(obj1, path='./{%s}collection' % self.col_namespace)
        self.assertIn("'xsi:schemaLocation' attribute not allowed", str(ec.exception))

        # With ElementTree namespaces are not mapped
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotEqual(obj1, obj2)
        self.assertEqual(obj1, col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap))

        # With lxml.etree namespaces are mapped
        if self.col_lxml_root is not None:
            self.assertEqual(obj1, col_schema.decode(self.col_lxml_root))

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_jsonml_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=JsonMLConverter)

        obj1 = col_schema.decode(self.col_xml_filename)
        self.assertIn('col:collection', repr(obj1))
        self.assertIn('xmlns:col', repr(obj1))

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1, path='./{%s}collection' % self.col_namespace)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # With ElementTree namespaces are not mapped
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotIn('col:collection', repr(obj2))
        self.assertNotEqual(obj1, obj2)
        self.assertEqual(obj1, col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap))

        # With lxml.etree namespaces are mapped
        if self.col_lxml_root is not None:
            self.assertEqual(obj1, col_schema.decode(self.col_lxml_root))

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_columnar_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=ColumnarConverter)

        obj1 = col_schema.decode(self.col_xml_filename)

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # Namespace mapping is required
        with self.assertRaises(XMLSchemaValidationError) as ec:
            col_schema.encode(obj1, path='./{%s}collection' % self.col_namespace)
        self.assertIn("'xsi:schemaLocation' attribute not allowed", str(ec.exception))

        # With ElementTree namespaces are not mapped
        obj2 = col_schema.decode(self.col_xml_root)
        self.assertNotEqual(obj1, obj2)
        self.assertEqual(obj1, col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap))

        # With lxml.etree namespaces are mapped
        if self.col_lxml_root is not None:
            self.assertEqual(obj1, col_schema.decode(self.col_lxml_root))

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_data_element_converter(self):
        col_schema = XMLSchema(self.col_xsd_filename, converter=DataElementConverter)

        obj1 = col_schema.decode(self.col_xml_filename)
        # self.assertIn('col:collection', repr(obj1))
        self.assertIn('col', obj1.nsmap)

        root = col_schema.encode(obj1, path='./col:collection', namespaces=self.col_nsmap)

        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1, path='./{%s}collection' % self.col_namespace)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj1)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        # With ElementTree namespaces are not mapped
        obj2 = col_schema.decode(self.col_xml_root)

        # Equivalent if compared as Element trees (tag, text, attrib, tail)
        self.assertIsNone(etree_elements_assert_equal(obj1, obj2))

        self.assertIsNone(etree_elements_assert_equal(
            obj1, col_schema.decode(self.col_xml_root, namespaces=self.col_nsmap)
        ))

        # With lxml.etree namespaces are mapped
        if self.col_lxml_root is not None:
            self.assertIsNone(etree_elements_assert_equal(
                obj1, col_schema.decode(self.col_lxml_root)
            ))

        root = col_schema.encode(obj2, path='./col:collection', namespaces=self.col_nsmap)
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

        root = col_schema.encode(obj2)  # No namespace unmap is required
        self.assertIsNone(etree_elements_assert_equal(self.col_xml_root, root, strict=False))

    def test_decode_encode_with_default_namespace(self):
        # Using default namespace and qualified form for elements
        qualified_col_xsd = self.casepath('examples/collection/collection5.xsd')
        col_schema = XMLSchema(qualified_col_xsd, converter=BadgerFishConverter)

        default_xml_filename = self.casepath('examples/collection/collection-default.xml')
        obj1 = col_schema.decode(default_xml_filename)
        self.assertIn('@xmlns', obj1)
        self.assertEqual(repr(obj1).count("'@xmlns'"), 1)
        self.assertEqual(obj1['@xmlns'], {'$': 'http://example.com/ns/collection',
                                          'xsi': 'http://www.w3.org/2001/XMLSchema-instance'})

        root = col_schema.encode(obj1)
        default_xml_root = etree_parse(default_xml_filename).getroot()
        self.assertIsNone(etree_elements_assert_equal(default_xml_root, root, strict=False))

    def test_simple_content__issue_315(self):
        schema = XMLSchema(self.casepath('issues/issue_315/issue_315_simple.xsd'))
        converters = (
            XMLSchemaConverter, XMLSchemaConverter(preserve_root=True),
            BadgerFishConverter, AbderaConverter, JsonMLConverter,
            UnorderedConverter, ColumnarConverter, DataElementConverter
        )

        for k in range(1, 6):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            if k < 3:
                self.assertIsNone(schema.validate(xml_filename), xml_filename)
            else:
                self.assertFalse(schema.is_valid(xml_filename), xml_filename)

        for k in (1, 2):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            xml_tree = etree_parse(xml_filename).getroot()
            for converter in converters:
                obj = schema.decode(xml_filename, converter=converter)
                root = schema.encode(obj, converter=converter)
                self.assertIsNone(etree_elements_assert_equal(xml_tree, root))

    def test_mixed_content__issue_315(self):
        schema = XMLSchema(self.casepath('issues/issue_315/issue_315_mixed.xsd'))
        losslessly_converters = (JsonMLConverter, DataElementConverter)
        default_converters = (
            XMLSchemaConverter(cdata_prefix='#'),
            UnorderedConverter(cdata_prefix='#'),  # BadgerFishConverter, ColumnarConverter,
        )

        for k in range(1, 6):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            self.assertIsNone(schema.validate(xml_filename), xml_filename)

        for k in range(1, 6):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            xml_tree = etree_parse(xml_filename).getroot()
            for converter in losslessly_converters:
                obj = schema.decode(xml_filename, converter=converter)
                root = schema.encode(obj, converter=converter)
                self.assertIsNone(etree_elements_assert_equal(xml_tree, root, strict=False))

        for k in range(1, 6):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            xml_tree = etree_parse(xml_filename).getroot()
            for converter in default_converters:
                obj = schema.decode(xml_filename, converter=converter)
                root = schema.encode(obj, converter=converter, indent=0)
                if k < 4:
                    self.assertIsNone(etree_elements_assert_equal(xml_tree, root, strict=False))
                    continue

                if k == 4:
                    self.assertEqual(obj, {'@xmlns:tst': 'http://xmlschema.test/ns',
                                           '@a1': 'foo', 'e2': [None, None], '#1': 'bar'})
                    self.assertEqual(len(root), 2)
                else:
                    self.assertEqual(obj, {'@xmlns:tst': 'http://xmlschema.test/ns',
                                           '@a1': 'foo', 'e2': [None], '#1': 'bar'})
                    self.assertEqual(len(root), 1)

                text = etree_tostring(root, namespaces={'tst': 'http://xmlschema.test/ns'})
                self.assertEqual(len(text.split('bar')), 2)

        for k in range(1, 6):
            xml_filename = self.casepath(f'issues/issue_315/issue_315-{k}.xml')
            xml_tree = etree_parse(xml_filename).getroot()
            obj = schema.decode(xml_filename, converter=BadgerFishConverter)
            root = schema.encode(obj, converter=BadgerFishConverter, indent=0)
            if k < 4:
                self.assertIsNone(etree_elements_assert_equal(xml_tree, root, strict=False))
                continue

            if k == 4:
                self.assertEqual(obj, {'@xmlns': {'tst': 'http://xmlschema.test/ns'},
                                       'tst:e1': {'@a1': 'foo', 'e2': [{}, {}], '$1': 'bar'}})
            else:
                self.assertEqual(obj, {'@xmlns': {'tst': 'http://xmlschema.test/ns'},
                                       'tst:e1': {'@a1': 'foo', 'e2': [{}], '$1': 'bar'}})

            text = etree_tostring(root, namespaces={'tst': 'http://xmlschema.test/ns'})
            self.assertEqual(len(text.split('bar')), 2)


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema converters with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
