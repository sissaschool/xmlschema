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
This module runs tests concerning resources.
"""
import unittest
import os
import sys

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

try:
    from pathlib import PureWindowsPath, PurePath
except ImportError:
    from pathlib2 import PureWindowsPath, PurePath

from xmlschema import (
    fetch_namespaces, fetch_resource, normalize_url, fetch_schema, fetch_schema_locations,
    load_xml_resource, XMLResource, XMLSchemaURLError
)
from xmlschema.tests import XMLSchemaTestCase
from xmlschema.compat import urlopen, urlsplit, uses_relative, StringIO
from xmlschema.etree import (
    ElementTree, defused_etree, etree_parse, etree_iterparse, etree_fromstring, lxml_etree_parse, is_etree_element
)


def is_windows_path(path):
    """Checks if the path argument is a Windows platform path."""
    return '\\' in path or ':' in path or '|' in path


def add_leading_slash(path):
    return '/' + path if path and path[0] not in ('/', '\\') else path


class TestResources(XMLSchemaTestCase):

    def check_url(self, url, expected):
        url_parts = urlsplit(url)
        if urlsplit(expected).scheme not in uses_relative:
            expected = add_leading_slash(expected)
        expected_parts = urlsplit(expected, scheme='file')

        self.assertEqual(url_parts.scheme, expected_parts.scheme, "Schemes differ.")
        self.assertEqual(url_parts.netloc, expected_parts.netloc, "Netloc parts differ.")
        self.assertEqual(url_parts.query, expected_parts.query, "Query parts differ.")
        self.assertEqual(url_parts.fragment, expected_parts.fragment, "Fragment parts differ.")

        if is_windows_path(url_parts.path) or is_windows_path(expected_parts.path):
            path = PureWindowsPath(url_parts.path)
            expected_path = PureWindowsPath(add_leading_slash(expected_parts.path))
        else:
            path = PurePath(url_parts.path)
            expected_path = PurePath(expected_parts.path)
        self.assertEqual(path, expected_path, "Paths differ.")

    def test_normalize_url(self):
        url1 = "https://example.com/xsd/other_schema.xsd"
        self.check_url(normalize_url(url1, base_url="/path_my_schema/schema.xsd"), url1)

        parent_dir = os.path.dirname(os.getcwd())
        self.check_url(normalize_url('../dir1/./dir2'), os.path.join(parent_dir, 'dir1/dir2'))
        self.check_url(normalize_url('../dir1/./dir2', '/home', keep_relative=True), 'file:///dir1/dir2')
        self.check_url(normalize_url('../dir1/./dir2', 'file:///home'), 'file:///dir1/dir2')

        self.check_url(normalize_url('other.xsd', 'file:///home'), 'file:///home/other.xsd')
        self.check_url(normalize_url('other.xsd', 'file:///home/'), 'file:///home/other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'file:///home'), 'file:///home/other.xsd')

        cwd_url = 'file://{}/'.format(add_leading_slash(os.getcwd()))
        self.check_url(normalize_url('file:other.xsd', keep_relative=True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd'), cwd_url + 'other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'http://site/base', True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'http://site/base'), cwd_url + 'other.xsd')

        self.check_url(normalize_url('dummy path.xsd'), cwd_url + 'dummy path.xsd')
        self.check_url(normalize_url('dummy path.xsd', 'http://site/base'), 'http://site/base/dummy%20path.xsd')
        self.check_url(normalize_url('dummy path.xsd', 'file://host/home/'), 'file://host/home/dummy path.xsd')

        win_abs_path1 = 'z:\\Dir_1_0\\Dir2-0\\schemas/XSD_1.0/XMLSchema.xsd'
        win_abs_path2 = 'z:\\Dir-1.0\\Dir-2_0\\'
        self.check_url(normalize_url(win_abs_path1), win_abs_path1)

        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path1), 'file:///k:\\Dir3\\schema.xsd')
        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path2), 'file:///k:\\Dir3\\schema.xsd')
        self.check_url(normalize_url('schema.xsd', win_abs_path2), 'file:///z:\\Dir-1.0\\Dir-2_0/schema.xsd')
        self.check_url(
            normalize_url('xsd1.0/schema.xsd', win_abs_path2), 'file:///z:\\Dir-1.0\\Dir-2_0/xsd1.0/schema.xsd'
        )

    def test_fetch_resource(self):
        wrong_path = os.path.join(self.test_dir, 'resources/dummy_file.txt')
        self.assertRaises(XMLSchemaURLError, fetch_resource, wrong_path)
        right_path = os.path.join(self.test_dir, 'resources/dummy file.txt')
        self.assertTrue(fetch_resource(right_path).endswith('dummy file.txt'))

    def test_fetch_namespaces(self):
        self.assertFalse(fetch_namespaces(os.path.join(self.test_dir, 'resources/malformed.xml')))

    def test_fetch_schema_locations(self):
        locations = fetch_schema_locations(self.col_xml_file)
        self.check_url(locations[0], self.col_xsd_file)
        self.assertEqual(locations[1][0][0], 'http://example.com/ns/collection')
        self.check_url(locations[1][0][1], self.col_xsd_file)
        self.check_url(fetch_schema(self.vh_xml_file), self.vh_xsd_file)

    def test_load_xml_resource(self):
        self.assertTrue(is_etree_element(load_xml_resource(self.vh_xml_file, element_only=True)))
        root, text, url = load_xml_resource(self.vh_xml_file, element_only=False)
        self.assertTrue(is_etree_element(root))
        self.assertEqual(root.tag, '{http://example.com/vehicles}vehicles')
        self.assertTrue(text.startswith('<?xml version'))
        self.check_url(url, self.vh_xml_file)

    # Tests on XMLResource instances
    def test_xml_resource_from_url(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertEqual(resource.source, self.vh_xml_file)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertIsNone(resource.document)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertEqual(resource.source, self.vh_xml_file)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertIsInstance(resource.document, ElementTree.ElementTree)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

    def test_xml_resource_from_element_tree(self):
        vh_etree = etree_parse(self.vh_xml_file)
        vh_root = vh_etree.getroot()

        resource = XMLResource(vh_etree)
        self.assertEqual(resource.source, vh_etree)
        self.assertEqual(resource.document, vh_etree)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

        resource = XMLResource(vh_root)
        self.assertEqual(resource.source, vh_root)
        self.assertIsNone(resource.document)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

    @unittest.skipIf(lxml_etree_parse is None, "Skip: lxml is not installed.")
    def test_xml_resource_from_lxml(self):
        vh_etree = lxml_etree_parse(self.vh_xml_file)
        vh_root = vh_etree.getroot()

        resource = XMLResource(vh_etree)
        self.assertEqual(resource.source, vh_etree)
        self.assertEqual(resource.document, vh_etree)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

        resource = XMLResource(vh_root)
        self.assertEqual(resource.source, vh_root)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

    def test_xml_resource_from_resource(self):
        xml_file = urlopen('file://{}'.format(add_leading_slash(self.vh_xml_file)))
        try:
            resource = XMLResource(xml_file)
            self.assertEqual(resource.source, xml_file)
            self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
            self.check_url(resource.url, self.vh_xml_file)
            self.assertIsNone(resource.document)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<?xml'))
        finally:
            xml_file.close()

    def test_xml_resource_from_file(self):
        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.check_url(resource.url, self.vh_xsd_file)
            self.assertIsNone(resource.document)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<xs:schema'))

        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file, lazy=False)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.check_url(resource.url, self.vh_xsd_file)
            self.assertIsInstance(resource.document, ElementTree.ElementTree)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<xs:schema'))

    def test_xml_resource_from_string(self):
        with open(self.vh_xsd_file) as schema_file:
            schema_text = schema_file.read()

        resource = XMLResource(schema_text)
        self.assertEqual(resource.source, schema_text)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.document)
        self.assertTrue(resource.text.startswith('<xs:schema'))

    def test_xml_resource_from_string_io(self):
        with open(self.vh_xsd_file) as schema_file:
            schema_text = schema_file.read()

        schema_file = StringIO(schema_text)
        resource = XMLResource(schema_file)
        self.assertEqual(resource.source, schema_file)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.document)
        self.assertTrue(resource.text.startswith('<xs:schema'))

        schema_file = StringIO(schema_text)
        resource = XMLResource(schema_file, lazy=False)
        self.assertEqual(resource.source, schema_file)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertIsInstance(resource.document, ElementTree.ElementTree)
        self.assertTrue(resource.text.startswith('<xs:schema'))

    def test_xml_resource_from_wrong_type(self):
        self.assertRaises(TypeError, XMLResource, [b'<UNSUPPORTED_DATA_TYPE/>'])

    def test_xml_resource_namespace(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertEqual(resource.namespace, 'http://example.com/vehicles')
        resource = XMLResource(self.vh_xsd_file)
        self.assertEqual(resource.namespace, 'http://www.w3.org/2001/XMLSchema')
        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.namespace, 'http://example.com/ns/collection')
        self.assertEqual(XMLResource('<A/>').namespace, '')

    def test_xml_resource_defuse(self):
        resource = XMLResource(self.vh_xml_file, defuse='never')
        self.assertEqual(resource.defuse, 'never')
        self.assertEqual(resource.parse, etree_parse)
        self.assertEqual(resource.iterparse, etree_iterparse)
        self.assertEqual(resource.fromstring, etree_fromstring)

        resource.defuse = 'always'
        self.assertEqual(resource.parse, defused_etree.parse)
        self.assertEqual(resource.iterparse, defused_etree.iterparse)
        self.assertEqual(resource.fromstring, defused_etree.fromstring)

        resource.defuse = 'remote'
        self.assertEqual(resource.parse, etree_parse)
        self.assertEqual(resource.iterparse, etree_iterparse)
        self.assertEqual(resource.fromstring, etree_fromstring)

        resource._url = 'http://localhost'
        self.assertEqual(resource.parse, defused_etree.parse)
        self.assertEqual(resource.iterparse, defused_etree.iterparse)
        self.assertEqual(resource.fromstring, defused_etree.fromstring)

        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, defuse='all')
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, defuse=None)

    def test_xml_resource_timeout(self):
        resource = XMLResource(self.vh_xml_file, timeout=30)
        self.assertEqual(resource.timeout, 30)
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, timeout='100')
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, timeout=0)

    def test_xml_resource_is_lazy(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertTrue(resource.is_lazy())
        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertFalse(resource.is_lazy())

    def test_xml_resource_is_loaded(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertFalse(resource.is_loaded())
        resource.load()
        self.assertTrue(resource.is_loaded())

    def test_xml_resource_open(self):
        resource = XMLResource(self.vh_xml_file)
        xml_file = resource.open()
        data = xml_file.read().decode('utf-8')
        self.assertTrue(data.startswith('<?xml '))
        xml_file.close()
        resource = XMLResource('<A/>')
        self.assertRaises(ValueError, resource.open)

    def test_xml_resource_tostring(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertTrue(resource.tostring().startswith('<vh:vehicles'))

    def test_xml_resource_copy(self):
        resource = XMLResource(self.vh_xml_file)
        resource2 = resource.copy(defuse='never')
        self.assertEqual(resource2.defuse, 'never')
        resource2 = resource.copy(timeout=30)
        self.assertEqual(resource2.timeout, 30)
        resource2 = resource.copy(lazy=False)
        self.assertFalse(resource2.is_lazy())

        self.assertIsNone(resource2.text)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNotNone(resource.text)
        resource2 = resource.copy()
        self.assertEqual(resource.text, resource2.text)

    def test_xml_resource_get_namespaces(self):
        with open(self.vh_xml_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.url, normalize_url(self.vh_xml_file))
            self.assertEqual(set(resource.get_namespaces().keys()), {'vh', 'xsi'})

        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.url, normalize_url(self.vh_xsd_file))
            self.assertEqual(set(resource.get_namespaces().keys()), {'xs', 'vh'})

        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.url, normalize_url(self.col_xml_file))
        self.assertEqual(set(resource.get_namespaces().keys()), {'col', 'xsi'})

        resource = XMLResource(self.col_xsd_file)
        self.assertEqual(resource.url, normalize_url(self.col_xsd_file))
        self.assertEqual(set(resource.get_namespaces().keys()), {'', 'xs'})

    def test_xml_resource_get_locations(self):
        resource = XMLResource(self.col_xml_file)
        self.check_url(resource.url, normalize_url(self.col_xml_file))
        locations = resource.get_locations([('ns', 'other.xsd')])
        self.assertEqual(len(locations), 2)
        self.check_url(locations[0][1], os.path.join(self.col_dir, 'other.xsd'))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
