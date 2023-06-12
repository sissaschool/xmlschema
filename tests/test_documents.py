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
"""Tests concerning XML documents"""

import unittest
import os
import io
import pathlib
import tempfile
from decimal import Decimal
from textwrap import dedent
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema10, XMLSchema11, XmlDocument, \
    XMLResourceError, XMLSchemaValidationError, XMLSchemaDecodeError, \
    to_json, from_json, validate, XMLSchemaParseError, is_valid, to_dict, \
    to_etree, JsonMLConverter

from xmlschema.names import XSD_NAMESPACE, XSI_NAMESPACE, XSD_SCHEMA
from xmlschema.helpers import is_etree_element, is_etree_document
from xmlschema.resources import XMLResource
from xmlschema.documents import get_context
from xmlschema.testing import etree_elements_assert_equal


TEST_CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases/')


def casepath(relative_path):
    return os.path.join(TEST_CASES_DIR, relative_path)


class TestXmlDocuments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = casepath('examples/vehicles')
        cls.vh_xsd_file = casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = casepath('examples/vehicles/vehicles.xml')

        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')

    def test_to_json_api(self):
        json_data = to_json(self.col_xml_file, lazy=True)
        self.assertIsInstance(json_data, str)
        self.assertIn('"@xmlns:col"', json_data)
        self.assertIn(r'"name": "Joan Mir\u00f3"', json_data)

        with self.assertRaises(TypeError) as ctx:
            to_json(self.col_xml_file, lazy=True, decimal_type=Decimal)
        self.assertIn("is not JSON serializable", str(ctx.exception))

        col_1_error_xml_file = casepath('examples/collection/collection-1_error.xml')
        json_data, errors = to_json(col_1_error_xml_file, validation='lax', lazy=True)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], XMLSchemaDecodeError)
        self.assertIn('"position": null', json_data)

        json_data, errors = to_json(col_1_error_xml_file, validation='lax', lazy=True,
                                    json_options={'default': lambda x: None})
        self.assertEqual(len(errors), 0)
        self.assertIn('"object": [null, null]', json_data)

    def test_to_etree_api(self):
        data = to_dict(self.col_xml_file)
        root_tag = '{http://example.com/ns/collection}collection'

        with self.assertRaises(TypeError) as ctx:
            to_etree(data)
        self.assertIn("a path is required for building a dummy schema", str(ctx.exception))

        collection = to_etree(data, schema=self.col_xsd_file)
        self.assertEqual(collection.tag, root_tag)

        col_schema = XMLSchema10(self.col_xsd_file)
        collection = to_etree(data, schema=col_schema)
        self.assertEqual(collection.tag, root_tag)

        collection = to_etree(data, path=root_tag)
        self.assertEqual(collection.tag, root_tag)

    def test_to_etree_api_on_schema__issue_325(self):
        col_root = ElementTree.parse(self.col_xsd_file).getroot()
        kwargs = dict(use_defaults=False, converter=JsonMLConverter)
        data = to_dict(self.col_xsd_file, **kwargs)

        with self.assertRaises(TypeError) as ctx:
            to_etree(data)
        self.assertIn("a path is required for building a dummy schema", str(ctx.exception))

        collection_xsd = to_etree(data, schema=XMLSchema10.meta_schema.url, **kwargs)
        self.assertEqual(collection_xsd.tag, XSD_SCHEMA)
        self.assertIsNone(etree_elements_assert_equal(collection_xsd, col_root, strict=False))

        collection_xsd = to_etree(data, path=XSD_SCHEMA, **kwargs)
        self.assertIsNone(etree_elements_assert_equal(collection_xsd, col_root, strict=False))

        # automatically map xs/xsd prefixes and use meta-schema
        collection_xsd = to_etree(data, path='xs:schema', **kwargs)
        self.assertIsNone(etree_elements_assert_equal(collection_xsd, col_root, strict=False))

        with self.assertRaises(TypeError) as ctx:
            to_etree(data, path='xs:schema', namespaces={}, **kwargs)
        self.assertIn("the path must be mappable to a local or extended name",
                      str(ctx.exception))

    def test_from_json_api(self):
        json_data = to_json(self.col_xml_file, lazy=True)
        root_tag = '{http://example.com/ns/collection}collection'

        with self.assertRaises(TypeError) as ctx:
            from_json(json_data)
        self.assertIn("a path is required for building a dummy schema", str(ctx.exception))

        collection = from_json(json_data, schema=self.col_xsd_file)
        self.assertEqual(collection.tag, root_tag)

        col_schema = XMLSchema10(self.col_xsd_file)
        collection = from_json(json_data, schema=col_schema)
        self.assertEqual(collection.tag, root_tag)

        col_schema = XMLSchema10(self.col_xsd_file)
        collection = from_json(json_data, col_schema, json_options={'parse_float': Decimal})
        self.assertEqual(collection.tag, root_tag)

        collection = from_json(json_data, path=root_tag)
        self.assertEqual(collection.tag, root_tag)

    def test_get_context_with_schema(self):
        source, schema = get_context(self.col_xml_file)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)

        source, schema = get_context(self.col_xml_file, self.col_xsd_file)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)

        col_schema = XMLSchema10(self.col_xsd_file)
        source, schema = get_context(self.col_xml_file, col_schema)
        self.assertIsInstance(source, XMLResource)
        self.assertIs(schema, col_schema)

        source, schema = get_context(self.vh_xml_file, cls=XMLSchema10)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)

        source, schema = get_context(self.col_xml_file, cls=XMLSchema11)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema11)

        source, schema = get_context(XMLResource(self.vh_xml_file))
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)

        xml_document = XmlDocument(self.vh_xml_file)
        source, schema = get_context(xml_document)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)
        self.assertIs(xml_document.schema, schema)

        # Issue #145
        with open(self.vh_xml_file) as f:
            source, schema = get_context(f, schema=self.vh_xsd_file)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema10)

        with open(self.vh_xml_file) as f:
            source, schema = get_context(XMLResource(f), schema=self.vh_xsd_file)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema10)

        with open(self.vh_xml_file) as f:
            source, schema = get_context(f, base_url=self.vh_dir)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema10)

    def test_get_context_without_schema(self):
        xml_data = '<text xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' \
                   '      xmlns:xs="http://www.w3.org/2001/XMLSchema"\n' \
                   '      xsi:type="xs:string">foo</text>'

        source, schema = get_context(xml_data)
        self.assertIsInstance(source, XMLResource)
        self.assertIsNot(schema, XMLSchema10.meta_schema)
        self.assertEqual(source.root.tag, 'text')
        self.assertTrue(schema.is_valid(source))

        with self.assertRaises(ValueError) as ctx:
            get_context('<empty/>')
        self.assertEqual(str(ctx.exception),
                         "cannot get a schema for XML data, provide a schema argument")

        source, schema = get_context('<empty/>', dummy_schema=True)
        self.assertEqual(source.root.tag, 'empty')
        self.assertIsInstance(schema, XMLSchema10)

        col_xml_resource = XMLResource(self.col_xml_file)
        col_xml_resource.root.attrib.clear()
        self.assertEqual(col_xml_resource.get_locations(), [])

        source, schema = get_context(col_xml_resource, self.col_xsd_file)
        self.assertIs(source, col_xml_resource)
        self.assertIsInstance(schema, XMLSchema10)
        self.assertEqual(schema.target_namespace, 'http://example.com/ns/collection')

        # Schema target namespace doesn't match source namespace
        vh_schema = XMLSchema10(self.vh_xsd_file)

        source, schema = get_context(col_xml_resource, vh_schema)
        self.assertIs(source, col_xml_resource)
        self.assertIs(schema, vh_schema)
        self.assertFalse(schema.is_valid(source))

        vh_schema.import_schema('http://example.com/ns/collection', self.col_xsd_file)
        vh_schema.build()

        source, schema = get_context(col_xml_resource, vh_schema)
        self.assertIs(source, col_xml_resource)
        self.assertIs(schema, vh_schema)
        self.assertTrue(schema.is_valid(source))

    def test_use_location_hints_argument__issue_324(self):
        xsd_file = casepath('issues/issue_324/issue_324a.xsd')
        schema = XMLSchema10(xsd_file)

        xml_file = casepath('issues/issue_324/issue_324-valid.xml')
        self.assertIsNone(validate(xml_file))

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            validate(xml_file, schema=schema)
        self.assertIn('unavailable namespace', str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            validate(xml_file, use_location_hints=False)
        self.assertIn('provide a schema argument', str(ctx.exception))

        xml_file = casepath('issues/issue_324/issue_324-invalid.xml')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            validate(xml_file)
        self.assertIn('unmatched namespace', str(ctx.exception))

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            validate(xml_file, schema=schema)
        self.assertIn('unavailable namespace', str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            validate(xml_file, use_location_hints=False)
        self.assertIn('provide a schema argument', str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            XmlDocument(self.col_xml_file, use_location_hints=False)
        self.assertIn('provide a schema argument', str(ctx.exception))

    def test_xml_document_init_with_schema(self):
        xml_document = XmlDocument(self.vh_xml_file)
        self.assertEqual(os.path.basename(xml_document.url), 'vehicles.xml')
        self.assertEqual(xml_document.errors, ())
        self.assertIsInstance(xml_document.schema, XMLSchema10)

        xml_document = XmlDocument(self.vh_xml_file, cls=XMLSchema11)
        self.assertIsInstance(xml_document.schema, XMLSchema11)

        xml_document = XmlDocument(self.vh_xml_file, self.vh_xsd_file)
        self.assertIsInstance(xml_document.schema, XMLSchema10)

        vh_schema = XMLSchema10(self.vh_xsd_file)
        xml_document = XmlDocument(self.vh_xml_file, vh_schema)
        self.assertIsInstance(xml_document.schema, XMLSchema10)

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            XmlDocument(self.vh_xml_file, self.col_xsd_file)
        self.assertIn('is not an element of the schema', str(ctx.exception))

        xml_document = XmlDocument(self.col_xml_file)
        self.assertEqual(os.path.basename(xml_document.url), 'collection.xml')
        self.assertIsInstance(xml_document.schema, XMLSchema10)

        xml_file = casepath('examples/collection/collection-1_error.xml')
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            XmlDocument(xml_file)
        self.assertIn('invalid literal for int() with base 10', str(ctx.exception))

        xml_document = XmlDocument(xml_file, validation='lax')
        self.assertEqual(os.path.basename(xml_document.url), 'collection-1_error.xml')
        self.assertIsInstance(xml_document.schema, XMLSchema10)
        self.assertTrue(len(xml_document.errors), 1)

        with self.assertRaises(ValueError) as ctx:
            XmlDocument(xml_file, validation='foo')
        self.assertEqual(str(ctx.exception), "'foo' is not a validation mode")

    def test_xml_document_init_without_schema(self):
        with self.assertRaises(ValueError) as ctx:
            XmlDocument('<empty/>')
        self.assertIn('cannot get a schema for XML data, provide a schema argument',
                      str(ctx.exception))

        xml_document = XmlDocument('<empty/>', validation='skip')
        self.assertIsNone(xml_document.schema)
        self.assertIsInstance(xml_document._fallback_schema, XMLSchema10)
        self.assertEqual(xml_document._fallback_schema.target_namespace, '')

        xml_document = XmlDocument(
            '<tns:empty xmlns:tns="http://example.com/ns" />', validation='skip'
        )
        self.assertIsNone(xml_document.schema)
        self.assertIsInstance(xml_document._fallback_schema, XMLSchema10)
        self.assertEqual(xml_document._fallback_schema.target_namespace, xml_document.namespace)

    def test_xml_document_parse(self):
        xml_document = XmlDocument(self.vh_xml_file)
        self.assertEqual(os.path.basename(xml_document.url), 'vehicles.xml')
        self.assertFalse(xml_document.is_lazy())

        xml_file = casepath('examples/vehicles/vehicles-1_error.xml')
        with self.assertRaises(XMLSchemaValidationError):
            xml_document.parse(xml_file)

        xml_document.parse(self.vh_xml_file, lazy=True)
        self.assertEqual(os.path.basename(xml_document.url), 'vehicles.xml')
        self.assertTrue(xml_document.is_lazy())

        xml_document = XmlDocument(self.vh_xml_file, validation='lax')
        xml_document.parse(xml_file)
        self.assertEqual(len(xml_document.errors), 1)

    def test_xml_document_decode_with_schema(self):
        xml_document = XmlDocument(self.vh_xml_file)
        vh_schema = XMLSchema10(self.vh_xsd_file)
        self.assertEqual(xml_document.decode(), vh_schema.decode(self.vh_xml_file))

        namespaces = {'vh': 'http://example.com/ns'}
        self.assertEqual(xml_document.decode(namespaces=namespaces),
                         vh_schema.decode(self.vh_xml_file, namespaces=namespaces))
        self.assertNotEqual(xml_document.decode(namespaces=namespaces),
                            vh_schema.decode(self.vh_xml_file))

        xml_file = casepath('examples/collection/collection-1_error.xml')
        xml_document = XmlDocument(xml_file, validation='lax')
        col_schema = XMLSchema10(self.col_xsd_file)
        self.assertEqual(xml_document.decode(), col_schema.decode(xml_file, validation='lax')[0])

        xml_document = XmlDocument(xml_file, validation='skip')
        self.assertEqual(xml_document.decode(), col_schema.decode(xml_file, validation='skip'))
        self.assertEqual(xml_document.decode(validation='lax'),
                         col_schema.decode(xml_file, validation='lax')[0])

    def test_xml_document_decode_without_schema(self):
        xml_document = XmlDocument('<x:root xmlns:x="ns" />', validation='skip')
        self.assertIsNone(xml_document.decode())

        xml_document = XmlDocument(
            '<x:root xmlns:x="ns" a="true"><b1>10</b1><b2/></x:root>', validation='skip'
        )
        self.assertEqual(xml_document.decode(), {'@a': 'true', 'b1': ['10'], 'b2': [None]})

    def test_xml_document_decode_with_xsi_type(self):
        xml_data = '<root xmlns:xsi="{}" xmlns:xs="{}" ' \
                   'xsi:type="xs:integer">10</root>'.format(XSI_NAMESPACE, XSD_NAMESPACE)
        xml_document = XmlDocument(xml_data)

        self.assertEqual(xml_document.decode(),
                         {'@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                          '@xmlns:xs': 'http://www.w3.org/2001/XMLSchema',
                          '@xsi:type': 'xs:integer', '$': 10})

    def test_xml_document_to_json(self):
        xml_document = XmlDocument(self.col_xml_file, lazy=True)
        json_data = xml_document.to_json()
        self.assertIsInstance(json_data, str)
        self.assertIn('"@xmlns:col"', json_data)
        self.assertIn(r'"name": "Joan Mir\u00f3"', json_data)

        self.assertEqual(xml_document.to_json(validation='lax')[0], json_data)
        self.assertEqual(xml_document.to_json(namespaces=None), json_data)

        with self.assertRaises(TypeError) as ctx:
            xml_document.to_json(decimal_type=Decimal)
        self.assertIn("is not JSON serializable", str(ctx.exception))

        fp = io.StringIO()
        xml_document.to_json(fp=fp)
        self.assertEqual(fp.getvalue(), json_data)
        fp.close()

        fp = io.StringIO()
        self.assertEqual(xml_document.to_json(fp=fp, validation='lax'), ())
        self.assertEqual(fp.getvalue(), json_data)
        fp.close()

        col_1_error_xml_file = casepath('examples/collection/collection-1_error.xml')
        xml_document = XmlDocument(col_1_error_xml_file, validation='lax')
        json_data, errors = xml_document.to_json()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], XMLSchemaDecodeError)
        self.assertIn('"position": null', json_data)

        xml_document = XmlDocument(col_1_error_xml_file, validation='lax', lazy=True)
        json_data, errors = xml_document.to_json(json_options={'default': lambda x: None})
        self.assertEqual(len(errors), 0)
        self.assertIn('"object": [null, null]', json_data)

    def test_xml_document_write(self):
        with tempfile.TemporaryDirectory() as dirname:
            col_file_path = pathlib.Path(dirname).joinpath('collection.xml')

            xml_document = XmlDocument(self.col_xml_file)
            with col_file_path.open(mode='wb') as fp:
                xml_document.write(fp)

            schema = XMLSchema10(self.col_xsd_file)
            xml_document = XmlDocument(str(col_file_path), schema=schema)
            self.assertEqual(xml_document.root.tag,
                             '{http://example.com/ns/collection}collection')
            self.assertIs(xml_document.schema, schema)

            col_file_path.unlink()
            xml_document.write(str(col_file_path))
            xml_document = XmlDocument(str(col_file_path), schema=schema)
            self.assertIs(xml_document.schema, schema)

            col_file_path.unlink()
            xml_document.write(str(col_file_path), encoding='unicode')
            xml_document = XmlDocument(str(col_file_path), schema=schema)
            self.assertIs(xml_document.schema, schema)

            col_file_path.unlink()
            xml_document.write(str(col_file_path),
                               default_namespace="http://example.com/ns/collection")
            xml_document = XmlDocument(str(col_file_path), schema=schema)
            self.assertIs(xml_document.schema, schema)

            if lxml_etree is not None:
                col_file_path.unlink()
                col_etree_document = lxml_etree.parse(self.col_xml_file)
                xml_document = XmlDocument(col_etree_document, base_url=self.col_dir)
                xml_document.write(str(col_file_path),
                                   default_namespace="http://example.com/ns/collection")
                xml_document = XmlDocument(str(col_file_path), schema=schema)
                self.assertIs(xml_document.schema, schema)

            col_file_path.unlink()
            xml_document = XmlDocument(self.col_xml_file, lazy=True)
            with self.assertRaises(XMLResourceError) as ctx:
                xml_document.write(str(col_file_path))
            self.assertEqual(str(ctx.exception), "cannot serialize a lazy XML resource")

    def test_xml_document_etree_interface(self):
        xml_document = XmlDocument(self.vh_xml_file)

        self.assertIs(xml_document.getroot(), xml_document._root)
        self.assertTrue(is_etree_element(xml_document.getroot()))

        self.assertTrue(is_etree_document(xml_document.get_etree_document()))

        xml_document = XmlDocument(self.vh_xml_file, lazy=1)
        with self.assertRaises(XMLResourceError) as ctx:
            xml_document.get_etree_document()
        self.assertIn('cannot create an ElementTree instance from a lazy XML resource',
                      str(ctx.exception))

        vh_tree = ElementTree.parse(self.vh_xml_file)
        xml_document = XmlDocument(vh_tree, base_url=self.vh_dir)
        self.assertIs(xml_document.source, vh_tree)
        self.assertIs(xml_document.get_etree_document(), vh_tree)

    @unittest.skipIf(lxml_etree is None, "Skip: lxml is not available.")
    def test_xml_document_with_lxml(self):
        vh_tree = lxml_etree.parse(self.vh_xml_file)
        xml_document = XmlDocument(vh_tree, base_url=self.vh_dir)
        self.assertIs(xml_document.get_etree_document(), vh_tree)

        xml_document = XmlDocument(vh_tree.getroot(), base_url=self.vh_dir)
        etree_document = xml_document.get_etree_document()
        self.assertIsNot(etree_document, vh_tree)
        self.assertTrue(is_etree_document(etree_document))
        self.assertTrue(hasattr(etree_document, 'xpath'))
        self.assertTrue(hasattr(etree_document, 'xslt'))

    def test_xml_document_tostring(self):
        xml_document = XmlDocument(self.vh_xml_file)
        self.assertTrue(xml_document.tostring().startswith('<vh:vehicles'))

        with self.assertRaises(XMLResourceError):
            XmlDocument(self.vh_xml_file, lazy=True).tostring()

    def test_get_context_on_xsd_schema__issue_325(self):
        source, schema = get_context(self.col_xsd_file)
        self.assertIsInstance(source, XMLResource)
        self.assertTrue(source.name, 'collection.xsd')
        self.assertIs(schema, XMLSchema10.meta_schema)

        source, schema = get_context(self.col_xsd_file, cls=XMLSchema11)
        self.assertIsInstance(source, XMLResource)
        self.assertTrue(source.name, 'collection.xsd')
        self.assertIs(schema, XMLSchema11.meta_schema)

    def test_document_api_on_xsd_schema__issue_325(self):
        self.assertIsNone(validate(self.col_xsd_file))
        self.assertTrue(is_valid(self.col_xsd_file))

        valid_xsd = dedent("""\
        <xs:schema targetNamespace="http://example.com/ns/collection"
            xmlns:xs="http://www.w3.org/2001/XMLSchema" >
          <xs:element name="collection"/>
        </xs:schema>""")
        self.assertTrue(is_valid(valid_xsd))

        invalid_xsd = dedent("""\
        <xs:schema targetNamespace="http://example.com/ns/collection"
            xmlns:xs="http://www.w3.org/2001/XMLSchema" >
          <xs:element ref="collection"/>
        </xs:schema>""")
        self.assertFalse(is_valid(invalid_xsd))

        obj = to_dict(valid_xsd)
        self.assertDictEqual(obj, {
            '@xmlns:xs': 'http://www.w3.org/2001/XMLSchema',
            '@targetNamespace': 'http://example.com/ns/collection',
            '@finalDefault': [],
            '@blockDefault': [],
            '@attributeFormDefault': 'unqualified',
            '@elementFormDefault': 'unqualified',
            'xs:element': {'@name': 'collection', '@abstract': False, '@nillable': False}})

        root = XMLSchema10.meta_schema.encode(obj)
        self.assertTrue(hasattr(root, 'tag'))
        self.assertEqual(root.tag, '{http://www.w3.org/2001/XMLSchema}schema')


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XML documents with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
