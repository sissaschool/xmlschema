#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
import platform
import warnings

try:
    from pathlib import PureWindowsPath, PurePath
except ImportError:
    # noinspection PyPackageRequirements
    from pathlib2 import PureWindowsPath, PurePath

from xmlschema import (
    fetch_namespaces, fetch_resource, normalize_url, fetch_schema, fetch_schema_locations,
    load_xml_resource, XMLResource, XMLSchemaURLError, XMLSchema, XMLSchema10, XMLSchema11
)
from xmlschema.tests import SKIP_REMOTE_TESTS, casepath
from xmlschema.compat import urlopen, urlsplit, uses_relative, StringIO
from xmlschema.etree import ElementTree, PyElementTree, lxml_etree, \
    etree_element, py_etree_element
from xmlschema.namespaces import XSD_NAMESPACE
from xmlschema.helpers import is_etree_element
from xmlschema.documents import get_context


def is_windows_path(path):
    """Checks if the path argument is a Windows platform path."""
    return '\\' in path or ':' in path or '|' in path


def add_leading_slash(path):
    return '/' + path if path and path[0] not in ('/', '\\') else path


def filter_windows_path(path):
    if path.startswith('/\\'):
        return path[1:]
    elif path and path[0] not in ('/', '\\'):
        return '/' + path
    else:
        return path


class TestResources(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema_class = XMLSchema
        cls.vh_dir = casepath('examples/vehicles')
        cls.vh_xsd_file = casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = casepath('examples/vehicles/vehicles.xml')

        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')

    def check_url(self, url, expected):
        url_parts = urlsplit(url)
        if urlsplit(expected).scheme not in uses_relative:
            expected = add_leading_slash(expected)
        expected_parts = urlsplit(expected, scheme='file')

        self.assertEqual(url_parts.scheme, expected_parts.scheme, "%r: Schemes differ." % url)
        self.assertEqual(url_parts.netloc, expected_parts.netloc, "%r: Netloc parts differ." % url)
        self.assertEqual(url_parts.query, expected_parts.query, "%r: Query parts differ." % url)
        self.assertEqual(url_parts.fragment, expected_parts.fragment, "%r: Fragment parts differ." % url)

        if is_windows_path(url_parts.path) or is_windows_path(expected_parts.path):
            path = PureWindowsPath(filter_windows_path(url_parts.path))
            expected_path = PureWindowsPath(filter_windows_path(expected_parts.path))
        else:
            path = PurePath(url_parts.path)
            expected_path = PurePath(expected_parts.path)
        self.assertEqual(path, expected_path, "%r: Paths differ." % url)

    def test_normalize_url_posix(self):
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

    def test_normalize_url_windows(self):
        win_abs_path1 = 'z:\\Dir_1_0\\Dir2-0\\schemas/XSD_1.0/XMLSchema.xsd'
        win_abs_path2 = 'z:\\Dir-1.0\\Dir-2_0\\'
        self.check_url(normalize_url(win_abs_path1), win_abs_path1)

        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path1), 'file:///k:\\Dir3\\schema.xsd')
        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path2), 'file:///k:\\Dir3\\schema.xsd')
        self.check_url(normalize_url('schema.xsd', win_abs_path2), 'file:///z:\\Dir-1.0\\Dir-2_0/schema.xsd')
        self.check_url(
            normalize_url('xsd1.0/schema.xsd', win_abs_path2), 'file:///z:\\Dir-1.0\\Dir-2_0/xsd1.0/schema.xsd'
        )
        self.check_url(normalize_url('file:///\\k:\\Dir A\\schema.xsd'), 'file:///k:\\Dir A\\schema.xsd')

    def test_normalize_url_slashes(self):
        # Issue #116
        self.assertEqual(
            normalize_url('//anaconda/envs/testenv/lib/python3.6/site-packages/xmlschema/validators/schemas/'),
            'file:///anaconda/envs/testenv/lib/python3.6/site-packages/xmlschema/validators/schemas/'
        )
        self.assertEqual(normalize_url('/root/dir1/schema.xsd'), 'file:///root/dir1/schema.xsd')
        self.assertEqual(normalize_url('//root/dir1/schema.xsd'), 'file:///root/dir1/schema.xsd')
        self.assertEqual(normalize_url('////root/dir1/schema.xsd'), 'file:///root/dir1/schema.xsd')

        self.assertEqual(normalize_url('dir2/schema.xsd', '//root/dir1/'), 'file:///root/dir1/dir2/schema.xsd')
        self.assertEqual(normalize_url('dir2/schema.xsd', '//root/dir1'), 'file:///root/dir1/dir2/schema.xsd')
        self.assertEqual(normalize_url('dir2/schema.xsd', '////root/dir1'), 'file:///root/dir1/dir2/schema.xsd')

    def test_normalize_url_hash_character(self):
        self.check_url(normalize_url('issue #000.xml', 'file:///dir1/dir2/'),
                       'file:///dir1/dir2/issue %23000.xml')
        self.check_url(normalize_url('data.xml', 'file:///dir1/dir2/issue 000'),
                       'file:///dir1/dir2/issue 000/data.xml')
        self.check_url(normalize_url('data.xml', '/dir1/dir2/issue #000'),
                       '/dir1/dir2/issue %23000/data.xml')

    def test_fetch_resource(self):
        wrong_path = casepath('resources/dummy_file.txt')
        self.assertRaises(XMLSchemaURLError, fetch_resource, wrong_path)
        right_path = casepath('resources/dummy file.txt')
        self.assertTrue(fetch_resource(right_path).endswith('dummy file.txt'))

        ambiguous_path = casepath('resources/dummy file #2.txt')
        self.assertTrue(fetch_resource(ambiguous_path).endswith('dummy file %232.txt'))

        res = urlopen(fetch_resource(ambiguous_path))
        try:
            self.assertEqual(res.read(), b'DUMMY CONTENT')
        finally:
            res.close()

    def test_fetch_namespaces(self):
        self.assertFalse(fetch_namespaces(casepath('resources/malformed.xml')))

    def test_fetch_schema_locations(self):
        locations = fetch_schema_locations(self.col_xml_file)
        self.check_url(locations[0], self.col_xsd_file)
        self.assertEqual(locations[1][0][0], 'http://example.com/ns/collection')
        self.check_url(locations[1][0][1], self.col_xsd_file)
        self.check_url(fetch_schema(self.vh_xml_file), self.vh_xsd_file)

    def test_load_xml_resource(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            self.assertTrue(is_etree_element(load_xml_resource(self.vh_xml_file, element_only=True)))
            root, text, url = load_xml_resource(self.vh_xml_file, element_only=False)

        self.assertTrue(is_etree_element(root))
        self.assertEqual(root.tag, '{http://example.com/vehicles}vehicles')
        self.assertTrue(text.startswith('<?xml version'))
        self.check_url(url, self.vh_xml_file)

    def test_get_context(self):
        source, schema = get_context(self.col_xml_file)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema)

        source, schema = get_context(self.col_xml_file, self.col_xsd_file)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema)

        source, schema = get_context(self.vh_xml_file, cls=XMLSchema10)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema10)

        source, schema = get_context(self.col_xml_file, cls=XMLSchema11)
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema11)

        source, schema = get_context(XMLResource(self.vh_xml_file))
        self.assertIsInstance(source, XMLResource)
        self.assertIsInstance(schema, XMLSchema)

        # Issue #145
        with open(self.vh_xml_file) as f:
            source, schema = get_context(f, schema=self.vh_xsd_file)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema)

        with open(self.vh_xml_file) as f:
            source, schema = get_context(XMLResource(f), schema=self.vh_xsd_file)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema)

        with open(self.vh_xml_file) as f:
            source, schema = get_context(f, base_url=self.vh_dir)
            self.assertIsInstance(source, XMLResource)
            self.assertIsInstance(schema, XMLSchema)

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
        vh_etree = ElementTree.parse(self.vh_xml_file)
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
        self.assertIsInstance(resource.document, ElementTree.ElementTree)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

    @unittest.skipIf(lxml_etree is None, "Skip: lxml is not available.")
    def test_xml_resource_from_lxml(self):
        vh_etree = lxml_etree.parse(self.vh_xml_file)
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

    @unittest.skipIf(
        platform.python_version_tuple()[0] < '3',
        "Skip: urlopen on Python 2 can't seek 'file://' paths."
    )
    def test_xml_resource_from_resource(self):
        xml_file = urlopen('file://{}'.format(add_leading_slash(self.vh_xml_file)))
        try:
            resource = XMLResource(xml_file)
            self.assertEqual(resource.source, xml_file)
            self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
            self.assertIsNone(resource.url)
            self.assertIsNone(resource.document)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<?xml'))
            self.assertFalse(xml_file.closed)
        finally:
            xml_file.close()

    def test_xml_resource_from_file(self):
        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.assertIsNone(resource.url)
            self.assertIsNone(resource.document)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<xs:schema'))
            self.assertFalse(schema_file.closed)
            for _ in resource.iter():
                pass
            self.assertFalse(schema_file.closed)
            for _ in resource.iterfind():
                pass
            self.assertFalse(schema_file.closed)

        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file, lazy=False)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.assertIsNone(resource.url)
            self.assertIsInstance(resource.document, ElementTree.ElementTree)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<xs:schema'))
            self.assertFalse(schema_file.closed)
            for _ in resource.iter():
                pass
            self.assertFalse(schema_file.closed)
            for _ in resource.iterfind():
                pass
            self.assertFalse(schema_file.closed)

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
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, defuse='all')
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, defuse=None)
        self.assertIsInstance(resource.root, etree_element)
        resource = XMLResource(self.vh_xml_file, defuse='always')
        self.assertIsInstance(resource.root, py_etree_element)

        xml_file = casepath('resources/with_entity.xml')
        self.assertIsInstance(XMLResource(xml_file), XMLResource)
        self.assertRaises(PyElementTree.ParseError, XMLResource, xml_file, defuse='always')

        xml_file = casepath('resources/unused_external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file), XMLResource)
        self.assertRaises(PyElementTree.ParseError, XMLResource, xml_file, defuse='always')

        xml_file = casepath('resources/external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file), XMLResource)
        self.assertRaises(PyElementTree.ParseError, XMLResource, xml_file, defuse='always')

    def test_xml_resource_timeout(self):
        resource = XMLResource(self.vh_xml_file, timeout=30)
        self.assertEqual(resource.timeout, 30)
        self.assertRaises(TypeError, XMLResource, self.vh_xml_file, timeout='100')
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

    def test_xml_resource_parse(self):
        resource = XMLResource(self.vh_xml_file)

        self.assertEqual(resource.defuse, 'remote')
        xml_document = resource.parse(self.col_xml_file)
        self.assertTrue(is_etree_element(xml_document.getroot()))

        resource.defuse = 'always'
        xml_document = resource.parse(self.col_xml_file)
        self.assertTrue(is_etree_element(xml_document.getroot()))

    def test_xml_resource_iterparse(self):
        resource = XMLResource(self.vh_xml_file)

        self.assertEqual(resource.defuse, 'remote')
        for _, elem in resource.iterparse(self.col_xml_file, events=('end',)):
            self.assertTrue(is_etree_element(elem))

        resource.defuse = 'always'
        for _, elem in resource.iterparse(self.col_xml_file, events=('end',)):
            self.assertTrue(is_etree_element(elem))

    def test_xml_resource_fromstring(self):
        resource = XMLResource(self.vh_xml_file)

        self.assertEqual(resource.defuse, 'remote')
        self.assertEqual(resource.fromstring('<root/>').tag, 'root')

        resource.defuse = 'always'
        self.assertEqual(resource.fromstring('<root/>').tag, 'root')

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

    def test_xml_resource_open(self):
        resource = XMLResource(self.vh_xml_file)
        xml_file = resource.open()
        self.assertIsNot(xml_file, resource.source)
        data = xml_file.read().decode('utf-8')
        self.assertTrue(data.startswith('<?xml '))
        xml_file.close()
        resource = XMLResource('<A/>')
        self.assertRaises(ValueError, resource.open)

        resource = XMLResource(source=open(self.vh_xml_file))
        xml_file = resource.open()
        self.assertIs(xml_file, resource.source)
        xml_file.close()

    def test_xml_resource_seek(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertIsNone(resource.seek(0))
        self.assertIsNone(resource.seek(1))
        xml_file = open(self.vh_xml_file)
        resource = XMLResource(source=xml_file)
        self.assertEqual(resource.seek(0), 0)
        self.assertEqual(resource.seek(1), 1)
        xml_file.close()

    def test_xml_resource_close(self):
        resource = XMLResource(self.vh_xml_file)
        resource.close()
        xml_file = resource.open()
        self.assertTrue(callable(xml_file.read))

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(source=xml_file)
            resource.close()
            with self.assertRaises(ValueError):
                resource.open()

    def test_xml_resource_iter(self):
        resource = XMLResource(self.schema_class.meta_schema.source.url, lazy=False)
        self.assertFalse(resource.is_lazy())
        lazy_resource = XMLResource(self.schema_class.meta_schema.source.url)
        self.assertTrue(lazy_resource.is_lazy())

        tags = [x.tag for x in resource.iter()]
        self.assertEqual(len(tags), 1390)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)

        lazy_tags = [x.tag for x in lazy_resource.iter()]
        self.assertEqual(len(lazy_tags), 1390)
        self.assertEqual(lazy_tags[-1], '{%s}schema' % XSD_NAMESPACE)
        self.assertNotEqual(tags, lazy_tags)

        tags = [x.tag for x in resource.iter('{%s}complexType' % XSD_NAMESPACE)]
        self.assertEqual(len(tags), 56)
        self.assertEqual(tags[0], '{%s}complexType' % XSD_NAMESPACE)
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iter('{%s}complexType' % XSD_NAMESPACE)])

    def test_xml_resource_iterfind(self):
        namespaces = {'xs': XSD_NAMESPACE}
        resource = XMLResource(self.schema_class.meta_schema.source.url, lazy=False)
        self.assertFalse(resource.is_lazy())
        lazy_resource = XMLResource(self.schema_class.meta_schema.source.url)
        self.assertTrue(lazy_resource.is_lazy())

        # Note: Element change with lazy resource so compare only tags

        tags = [x.tag for x in resource.iterfind()]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iterfind()])

        tags = [x.tag for x in resource.iterfind(path='.')]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iterfind(path='.')])

        tags = [x.tag for x in resource.iterfind(path='*')]
        self.assertEqual(len(tags), 156)
        self.assertEqual(tags[0], '{%s}annotation' % XSD_NAMESPACE)
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iterfind(path='*')])

        tags = [x.tag for x in resource.iterfind('xs:complexType', namespaces)]
        self.assertEqual(len(tags), 35)
        self.assertTrue(all(t == '{%s}complexType' % XSD_NAMESPACE for t in tags))
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iterfind('xs:complexType', namespaces)])

        tags = [x.tag for x in resource.iterfind('. /. / xs:complexType', namespaces)]
        self.assertEqual(len(tags), 35)
        self.assertTrue(all(t == '{%s}complexType' % XSD_NAMESPACE for t in tags))
        self.assertListEqual(tags, [x.tag for x in lazy_resource.iterfind('. /. / xs:complexType', namespaces)])

    def test_xml_resource_get_namespaces(self):
        with open(self.vh_xml_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertIsNone(resource.url)
            self.assertEqual(set(resource.get_namespaces().keys()), {'vh', 'xsi'})
            self.assertFalse(schema_file.closed)

        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertIsNone(resource.url)
            self.assertEqual(set(resource.get_namespaces().keys()), {'xs', 'vh'})
            self.assertFalse(schema_file.closed)

        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.url, normalize_url(self.col_xml_file))
        self.assertEqual(set(resource.get_namespaces().keys()), {'col', 'xsi'})

        resource = XMLResource(self.col_xsd_file)
        self.assertEqual(resource.url, normalize_url(self.col_xsd_file))
        self.assertEqual(set(resource.get_namespaces().keys()), {'', 'xs'})

        resource = XMLResource("""<?xml version="1.0" ?>
            <root xmlns="tns1">
                <tns:elem1 xmlns:tns="tns1" xmlns="unknown"/>
            </root>""")
        self.assertEqual(set(resource.get_namespaces().keys()), {'', 'tns', 'default'})

        resource = XMLResource("""<?xml version="1.0" ?>
            <root xmlns:tns="tns1">
                <tns:elem1 xmlns:tns="tns1" xmlns="unknown"/>
            </root>""")
        self.assertEqual(set(resource.get_namespaces().keys()), {'default', 'tns'})

        resource = XMLResource("""<?xml version="1.0" ?>
            <root xmlns:tns="tns1">
                <tns:elem1 xmlns:tns="tns3" xmlns="unknown"/>
            </root>""")
        self.assertEqual(set(resource.get_namespaces().keys()), {'default', 'tns', 'tns0'})

    def test_xml_resource_get_locations(self):
        resource = XMLResource(self.col_xml_file)
        self.check_url(resource.url, normalize_url(self.col_xml_file))
        locations = resource.get_locations([('ns', 'other.xsd')])
        self.assertEqual(len(locations), 2)
        self.check_url(locations[0][1], os.path.join(self.col_dir, 'other.xsd'))

    @unittest.skipIf(SKIP_REMOTE_TESTS or platform.system() == 'Windows',
                     "Remote networks are not accessible or avoid SSL verification error on Windows.")
    def test_remote_schemas_loading(self):
        col_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                       "xmlschema/tests/test_cases/examples/collection/collection.xsd")
        self.assertTrue(isinstance(col_schema, self.schema_class))
        vh_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                      "xmlschema/tests/test_cases/examples/vehicles/vehicles.xsd")
        self.assertTrue(isinstance(vh_schema, self.schema_class))

    def test_schema_defuse(self):
        vh_schema = self.schema_class(self.vh_xsd_file, defuse='always')
        self.assertIsInstance(vh_schema.root, etree_element)
        for schema in vh_schema.maps.iter_schemas():
            self.assertIsInstance(schema.root, etree_element)

    def test_fid_with_name_attr(self):
        """XMLResource gets correct data when passed a file like object
        with a name attribute that isn't on disk.

        These file descriptors appear when working with the contents from a
        zip using the zipfile module and with Django files in some
        instances.
        """
        class FileProxy(object):
            def __init__(self, fid, fake_name):
                self._fid = fid
                self.name = fake_name

            def __getattr__(self, attr):
                try:
                    return self.__dict__[attr]
                except (KeyError, AttributeError):
                    return getattr(self.__dict__["_fid"], attr)

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(FileProxy(xml_file, fake_name="not__on____disk.xml"))
            self.assertIsNone(resource.url)
            self.assertEqual(set(resource.get_namespaces().keys()), {'vh', 'xsi'})
            self.assertFalse(xml_file.closed)


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
