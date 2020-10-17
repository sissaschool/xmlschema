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
import platform
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema10, XMLSchema11, XmlDocument, \
    XMLResourceError, XMLSchemaValidationError

from xmlschema.etree import is_etree_element, is_etree_document
from xmlschema.namespaces import XSD_NAMESPACE, XSI_NAMESPACE


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

    def test_xml_document_init_with_schema(self):
        xml_document = XmlDocument(self.vh_xml_file)
        self.assertTrue(xml_document.url.endswith(self.vh_xml_file))
        self.assertEqual(xml_document.errors, [])
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
        self.assertTrue(xml_document.url.endswith(self.col_xml_file))
        self.assertIsInstance(xml_document.schema, XMLSchema10)

        xml_file = casepath('examples/collection/collection-1_error.xml')
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            XmlDocument(xml_file)
        self.assertIn('invalid literal for int() with base 10', str(ctx.exception))

        xml_document = XmlDocument(xml_file, validation='lax')
        self.assertTrue(xml_document.url.endswith(xml_file))
        self.assertIsInstance(xml_document.schema, XMLSchema10)
        self.assertTrue(len(xml_document.errors), 1)

    def test_xml_document_init_without_schema(self):
        with self.assertRaises(ValueError) as ctx:
            XmlDocument('<empty/>')
        self.assertIn('no schema can be retrieved for the XML resource', str(ctx.exception))

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

    def test_xml_document_decode_with_schema(self):
        xml_document = XmlDocument(self.vh_xml_file)
        vh_schema = XMLSchema10(self.vh_xsd_file)
        self.assertEqual(xml_document.decode(), vh_schema.decode(self.vh_xml_file))

        xml_file = casepath('examples/collection/collection-1_error.xml')
        xml_document = XmlDocument(xml_file, validation='lax')
        col_schema = XMLSchema10(self.col_xsd_file)
        self.assertEqual(xml_document.decode(), col_schema.decode(xml_file, validation='lax')[0])

        xml_document = XmlDocument(xml_file, validation='skip')
        self.assertEqual(xml_document.decode(), col_schema.decode(xml_file, validation='skip'))

    def test_xml_document_decode_without_schema(self):
        xml_document = XmlDocument('<x:root xmlns:x="ns" />', validation='skip')
        self.assertIsNone(xml_document.decode())

        xml_document = XmlDocument(
            '<x:root xmlns:x="ns" a="true"><b1>10</b1><b2/></x:root>', validation='skip'
        )
        self.assertEqual(xml_document.decode(), {'@a': 'true', 'b1': ['10'], 'b2': [None]})

    def test_xml_document_with_xsi_type(self):
        xml_data = '<root xmlns:xsi="{}" xmlns:xs="{}" ' \
                   'xsi:type="xs:integer">10</root>'.format(XSI_NAMESPACE, XSD_NAMESPACE)
        xml_document = XmlDocument(xml_data)

        self.assertEqual(xml_document.decode(),
                         {'@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                          '@xmlns:xs': 'http://www.w3.org/2001/XMLSchema',
                          '@xsi:type': 'xs:integer', '$': 10})

    def test_xml_document_etree_interface(self):
        xml_document = XmlDocument(self.vh_xml_file)

        self.assertIs(xml_document.getroot(), xml_document._root)
        self.assertTrue(is_etree_element(xml_document.getroot()))

        self.assertTrue(is_etree_document(xml_document.get_etree_document()))

        xml_document = XmlDocument(self.vh_xml_file, lazy=1)
        with self.assertRaises(XMLResourceError) as ctx:
            xml_document.get_etree_document()
        self.assertIn('cannot create an ElementTree from a lazy resource', str(ctx.exception))

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

    def test_xml_document_to_string(self):
        xml_document = XmlDocument(self.vh_xml_file)
        self.assertTrue(xml_document.tostring().startswith('<vh:vehicles'))


if __name__ == '__main__':
    header = "XML documents tests with Python {} on platform {}".format(
        platform.python_version(), platform.platform()
    )
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
