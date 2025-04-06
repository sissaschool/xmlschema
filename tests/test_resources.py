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
"""Tests concerning XML resources"""
import io
import unittest
import os
import contextlib
import copy
import pathlib
import platform
import warnings
from io import StringIO, BytesIO
from urllib.request import urlopen, build_opener, FileHandler
from urllib.response import addinfourl
from urllib.parse import urlsplit, uses_relative
from pathlib import Path, PurePath, PureWindowsPath
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import fetch_namespaces, fetch_resource, fetch_schema, \
    fetch_schema_locations, XMLResource, XMLResourceError, XMLSchema
from xmlschema.names import XSD_NAMESPACE
from xmlschema.utils.etree import is_etree_element, is_lxml_element
from xmlschema.testing import SKIP_REMOTE_TESTS, XMLSchemaTestCase, run_xmlschema_tests
from xmlschema.utils.urls import normalize_url
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError, \
    XMLResourceForbidden, XMLResourceBlocked, XMLResourceOSError
from xmlschema.resources import XMLResourceManager
from xmlschema.resources.sax import defuse_xml

DRIVE_REGEX = '(/[a-zA-Z]:|/)' if platform.system() == 'Windows' else ''

XML_WITH_NAMESPACES = '<pfa:root xmlns:pfa="http://xmlschema.test/nsa">\n' \
                      '  <pfb:elem xmlns:pfb="http://xmlschema.test/nsb"/>\n' \
                      '</pfa:root>'


@contextlib.contextmanager
def working_dir(path):
    current = Path().absolute()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(current)


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


class TestResources(XMLSchemaTestCase):

    cases_dir = pathlib.Path(__file__).absolute().parent.joinpath('test_cases')

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = cls.casepath('examples/vehicles')
        cls.vh_xsd_file = cls.casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = cls.casepath('examples/vehicles/vehicles.xml')

        cls.col_dir = cls.casepath('examples/collection')
        cls.col_xsd_file = cls.casepath('examples/collection/collection.xsd')
        cls.col_xml_file = cls.casepath('examples/collection/collection.xml')

    def check_url(self, url, expected):
        url_parts = urlsplit(url)
        if urlsplit(expected).scheme not in uses_relative:
            expected = add_leading_slash(expected)

        expected_parts = urlsplit(expected, scheme='file')

        self.assertEqual(url_parts.scheme, expected_parts.scheme,
                         "%r: Schemes differ." % url)
        self.assertEqual(url_parts.netloc, expected_parts.netloc,
                         "%r: Netloc parts differ." % url)
        self.assertEqual(url_parts.query, expected_parts.query,
                         "%r: Query parts differ." % url)
        self.assertEqual(url_parts.fragment, expected_parts.fragment,
                         "%r: Fragment parts differ." % url)

        if is_windows_path(url_parts.path) or is_windows_path(expected_parts.path):
            path = PureWindowsPath(filter_windows_path(url_parts.path))
            expected_path = PureWindowsPath(filter_windows_path(expected_parts.path))
        else:
            path = PurePath(url_parts.path)
            expected_path = PurePath(expected_parts.path)
        self.assertEqual(path, expected_path, "%r: Paths differ." % url)

    def test_fetch_resource_function(self):
        with self.assertRaises(ValueError) as ctx:
            fetch_resource('')
        self.assertIn('argument must contain a not empty string', str(ctx.exception))

        wrong_path = self.casepath('resources/dummy_file.txt')
        self.assertRaises(OSError, fetch_resource, wrong_path)

        wrong_path = self.casepath('/home/dummy_file.txt')
        self.assertRaises(OSError, fetch_resource, wrong_path)

        filepath = self.casepath('resources/dummy file.txt')
        self.assertTrue(fetch_resource(filepath).endswith('dummy%20file.txt'))

        filepath = Path(self.casepath('resources/dummy file.txt')).relative_to(os.getcwd())
        self.assertTrue(fetch_resource(str(filepath), '/home').endswith('dummy%20file.txt'))

        filepath = self.casepath('resources/dummy file.xml')
        self.assertTrue(fetch_resource(filepath).endswith('dummy%20file.xml'))

        with urlopen(fetch_resource(filepath)) as res:
            self.assertEqual(res.read(), b'<root>DUMMY CONTENT</root>')

        with working_dir(pathlib.Path(__file__).parent):
            filepath = 'test_cases/resources/dummy file.xml'
            result = fetch_resource(filepath)
            self.assertTrue(result.startswith('file://'))
            self.assertTrue(result.endswith('dummy%20file.xml'))

            base_url = "file:///wrong/base/url"
            result = fetch_resource(filepath, base_url)
            self.assertTrue(result.startswith('file://'))
            self.assertTrue(result.endswith('dummy%20file.xml'))

    def test_fetch_namespaces_function(self):
        self.assertFalse(fetch_namespaces(self.casepath('resources/malformed.xml')))

    def test_fetch_schema_locations_function(self):
        schema_url, locations = fetch_schema_locations(self.col_xml_file)
        self.check_url(schema_url, self.col_xsd_file)
        self.assertEqual(locations[0][0], 'http://example.com/ns/collection')
        self.check_url(locations[0][1], self.col_xsd_file)

        with self.assertRaises(ValueError) as ctx:
            fetch_schema_locations(self.col_xml_file, allow='none')
        self.assertIn('not found a schema for', str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            fetch_schema_locations('<empty/>')
        self.assertEqual(
            "provided arguments don't contain any schema location hint",
            str(ctx.exception)
        )

        schema_url, locations_ = fetch_schema_locations('<empty/>', locations)
        self.check_url(schema_url, self.col_xsd_file)
        self.assertListEqual(locations, locations_)

        locations = [('', self.casepath('resources/dummy file.xml'))]
        with self.assertRaises(ValueError) as ctx:
            fetch_schema_locations('<empty/>', locations)
        self.assertIn('not found a schema for', str(ctx.exception))

        with working_dir(pathlib.Path(__file__).parent):
            locations = [('http://example.com/ns/collection',
                          'test_cases/examples/collection/collection.xsd')]
            schema_url, locations_ = fetch_schema_locations('<empty/>', locations)
            self.check_url(schema_url, self.col_xsd_file)
            self.assertNotEqual(locations, locations_)

            base_url = "file:///wrong/base/url"
            with self.assertRaises(ValueError) as ctx:
                fetch_schema_locations('<empty/>', locations, base_url)
            self.assertIn('not found a schema for', str(ctx.exception))

    def test_fetch_schema_function(self):
        self.check_url(fetch_schema(self.vh_xml_file), self.vh_xsd_file)

    # Tests on XMLResource instances
    def test_xml_resource_representation(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertTrue(str(resource).startswith(
            "XMLResource(root=<Element '{http://example.com/vehicles}vehicles'"
        ))

    def test_xml_resource_from_url(self):
        resource = XMLResource(self.vh_xml_file, lazy=True)
        self.assertEqual(resource.source, self.vh_xml_file)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertTrue(resource.filepath.endswith('vehicles.xml'))
        self.assertIsNone(resource.text)
        with self.assertRaises(XMLResourceError) as ctx:
            resource.load()
        self.assertIn('can\'t load a lazy XML resource', str(ctx.exception))
        self.assertIsNone(resource.text)

        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertEqual(resource.source, self.vh_xml_file)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

        resource = XMLResource(self.vh_xml_file, lazy=False)
        resource.url = resource.url[:-12] + 'unknown.xml'
        with self.assertRaises(XMLResourceOSError):
            resource.load()

    def test_xml_resource_from_url_in_bytes(self):
        resource = XMLResource(self.vh_xml_file.encode('utf-8'), lazy=False)
        self.assertEqual(resource.source, self.vh_xml_file.encode('utf-8'))
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

    def test_xml_resource_from_path(self):
        path = Path(self.vh_xml_file)

        resource = XMLResource(path, lazy=True)
        self.assertIs(resource.source, path)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, path.as_uri())
        self.assertTrue(resource.filepath.endswith('vehicles.xml'))
        self.assertIsNone(resource.text)
        with self.assertRaises(XMLResourceError) as ctx:
            resource.load()
        self.assertIn('can\'t load a lazy XML resource', str(ctx.exception))
        self.assertIsNone(resource.text)

        resource = XMLResource(path, lazy=False)
        self.assertEqual(resource.source, path)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, path.as_uri())
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

        resource = XMLResource(path, lazy=False)
        resource.url = resource.url[:-12] + 'unknown.xml'
        with self.assertRaises(XMLResourceOSError):
            resource.load()

    def test_xml_resource_from_element_tree(self):
        vh_etree = ElementTree.parse(self.vh_xml_file)
        vh_root = vh_etree.getroot()

        resource = XMLResource(vh_etree)
        self.assertEqual(resource.source, vh_etree)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.filepath)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

        resource = XMLResource(vh_root)
        self.assertEqual(resource.source, vh_root)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.filepath)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

    @unittest.skipIf(lxml_etree is None, "Skip: lxml is not available.")
    def test_xml_resource_from_lxml(self):
        vh_etree = lxml_etree.parse(self.vh_xml_file)
        vh_root = vh_etree.getroot()

        resource = XMLResource(vh_etree)
        self.assertEqual(resource.source, vh_etree)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.filepath)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

        resource = XMLResource(vh_root)
        self.assertEqual(resource.source, vh_root)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.assertIsNone(resource.url)
        self.assertIsNone(resource.filepath)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertIsNone(resource.text)

        xml_text = resource.get_text()
        self.assertIn('<vh:vehicles ', xml_text)
        self.assertIn('<!-- Comment -->', xml_text)
        self.assertIn('</vh:vehicles>', xml_text)

    def test_xml_resource_from_resource(self):
        xml_file = urlopen(f'file://{add_leading_slash(self.vh_xml_file)}')
        try:
            resource = XMLResource(xml_file, lazy=False)
            self.assertEqual(resource.source, xml_file)
            self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
            self.assertIsNone(resource.url)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<?xml'))
            self.assertFalse(xml_file.closed)
        finally:
            xml_file.close()

        with open(self.vh_xml_file) as fp:
            resource = XMLResource(fp)
        self.assertIsNone(resource.text)

        with self.assertRaises(XMLResourceOSError):
            resource.load()

    def test_xml_resource_from_file(self):
        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file, lazy=False)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.assertIsNone(resource.url)
            self.assertIsNone(resource.text)
            resource.load()
            self.assertTrue(resource.text.startswith('<xs:schema'))
            self.assertFalse(schema_file.closed)
            for _ in resource.iter():
                pass
            self.assertFalse(schema_file.closed)
            for _ in resource.iter_depth():
                pass
            self.assertFalse(schema_file.closed)

        with open(self.vh_xsd_file) as schema_file:
            resource = XMLResource(schema_file, lazy=True)
            self.assertEqual(resource.source, schema_file)
            self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
            self.assertIsNone(resource.url)
            self.assertIsNone(resource.text)

            with self.assertRaises(XMLResourceError) as ctx:
                resource.load()
            self.assertEqual("can't load a lazy XML resource", str(ctx.exception))

            self.assertFalse(schema_file.closed)
            for _ in resource.iter():
                pass
            self.assertFalse(schema_file.closed)
            for _ in resource.iter_depth():
                pass
            self.assertFalse(schema_file.closed)

    def test_xml_resource_from_string(self):
        with open(self.vh_xsd_file) as schema_file:
            schema_text = schema_file.read()

        resource = XMLResource(schema_text, lazy=False)
        self.assertEqual(resource.source, schema_text)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertTrue(resource.text.startswith('<xs:schema'))

        invalid_xml = '<tns0:root>missing namespace declaration</tns0:root>'
        with self.assertRaises(ElementTree.ParseError) as ctx:
            XMLResource(invalid_xml)

        self.assertEqual(str(ctx.exception), 'unbound prefix: line 1, column 0')

    def test_xml_resource_from_string_io(self):
        with open(self.vh_xsd_file) as schema_file:
            schema_text = schema_file.read()

        schema_file = StringIO(schema_text)
        resource = XMLResource(schema_file)
        self.assertEqual(resource.source, schema_file)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertTrue(resource.text.startswith('<xs:schema'))

        schema_file = StringIO(schema_text)
        resource = XMLResource(schema_file, lazy=False)
        self.assertEqual(resource.source, schema_file)
        self.assertEqual(resource.root.tag, '{http://www.w3.org/2001/XMLSchema}schema')
        self.assertIsNone(resource.url)
        self.assertTrue(resource.text.startswith('<xs:schema'))

    def test_xml_resource_from_bytes(self):
        source = '<?xml version="1.0" encoding="iso-8859-1"?>\n<a>ç</a>'
        resource = XMLResource(source.encode('iso-8859-1'))
        self.assertIsNone(resource.text)
        resource.load()
        self.assertEqual(resource.text, source)

    def test_xml_resource_from_bytes_io(self):
        source = '<?xml version="1.0" encoding="iso-8859-1"?>\n<a>ç</a>'
        resource = XMLResource(BytesIO(source.encode('iso-8859-1')))
        self.assertIsNone(resource.text)
        resource.load()
        self.assertEqual(resource.text, source)

    def test_xml_resource_from_malformed_source(self):
        # related to issue #224
        malformed_xml_file = self.casepath('resources/malformed.xml')
        with self.assertRaises(ElementTree.ParseError):
            XMLResource(malformed_xml_file)

        with self.assertRaises(ElementTree.ParseError):
            XMLResource(malformed_xml_file, defuse='always')

        # the incremental parser does not found the incomplete root before the end
        resource = XMLResource(malformed_xml_file, lazy=True)
        self.assertEqual(resource.root.tag, 'malformed_xml_file')

        resource = XMLResource('<malformed_xml_file>>', lazy=True)
        self.assertEqual(resource.root.tag, 'malformed_xml_file')

        with self.assertRaises(ElementTree.ParseError):
            XMLResource('<malformed_xml_file<>', lazy=True)

    def test_xml_resource_from_wrong_arguments(self):
        self.assertRaises(TypeError, XMLResource, [b'<UNSUPPORTED_DATA_TYPE/>'])

        with self.assertRaises(TypeError) as ctx:
            XMLResource('<root/>', base_url=[b'/home'])
        self.assertIn(' ', str(ctx.exception))

    def test_xml_resource_namespace(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertEqual(resource.namespace, 'http://example.com/vehicles')
        resource = XMLResource(self.vh_xsd_file)
        self.assertEqual(resource.namespace, 'http://www.w3.org/2001/XMLSchema')
        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.namespace, 'http://example.com/ns/collection')
        self.assertEqual(XMLResource('<A/>').namespace, '')

    def test_xml_resource_access(self):
        resource = XMLResource(self.vh_xml_file)
        base_url = resource.base_url

        XMLResource(self.vh_xml_file, allow='local')
        XMLResource(
            self.vh_xml_file, base_url=os.path.dirname(self.vh_xml_file), allow='sandbox'
        )

        with self.assertRaises(XMLResourceBlocked) as ctx:
            XMLResource(self.vh_xml_file, allow='remote')
        self.assertTrue(str(ctx.exception).startswith("block access to local resource"))

        with self.assertRaises(XMLResourceOSError):
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='remote')

        with self.assertRaises(XMLResourceBlocked) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='local')
        self.assertEqual(str(ctx.exception),
                         "block access to remote resource https://xmlschema.test/vehicles.xsd")

        with self.assertRaises(XMLSchemaValueError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='sandbox')
        self.assertEqual(str(ctx.exception),
                         "block access to files out of sandbox requires 'base_url' to be set")

        with self.assertRaises(XMLSchemaValueError) as ctx:
            XMLResource("/tmp/vehicles.xsd", allow='sandbox')
        self.assertEqual(
            str(ctx.exception),
            "block access to files out of sandbox requires 'base_url' to be set",
        )

        source = "/tmp/vehicles.xsd"
        with self.assertRaises(XMLResourceBlocked) as ctx:
            XMLResource(source, base_url=base_url, allow='sandbox')
        self.assertEqual(
            str(ctx.exception),
            f"block access to out of sandbox file {normalize_url(source)}",
        )

        with self.assertRaises(XMLSchemaTypeError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow=None)
        self.assertEqual(str(ctx.exception),
                         "invalid type <class 'NoneType'> for argument 'allow'")

        with self.assertRaises(XMLSchemaValueError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='any')
        self.assertIn("invalid value 'any' for argument 'allow'", str(ctx.exception))

        with self.assertRaises(XMLResourceBlocked) as ctx:
            XMLResource(self.vh_xml_file, allow='none')
        self.assertTrue(str(ctx.exception).startswith('block access to resource'))
        self.assertTrue(str(ctx.exception).endswith('vehicles.xml'))

        with open(self.vh_xml_file) as fp:
            resource = XMLResource(fp, allow='none')
            self.assertIsInstance(resource, XMLResource)
            self.assertIsNone(resource.url)

        with open(self.vh_xml_file) as fp:
            resource = XMLResource(fp.read(), allow='none')
            self.assertIsInstance(resource, XMLResource)
            self.assertIsNone(resource.url)

        with open(self.vh_xml_file) as fp:
            resource = XMLResource(StringIO(fp.read()), allow='none')
            self.assertIsInstance(resource, XMLResource)
            self.assertIsNone(resource.url)

    def test_xml_resource_defuse(self):
        resource = XMLResource(self.vh_xml_file, defuse='never', lazy=True)
        self.assertEqual(resource.defuse, 'never')
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, defuse='all')
        self.assertRaises(TypeError, XMLResource, self.vh_xml_file, defuse=None)
        self.assertIsInstance(resource.root, ElementTree.Element)
        resource = XMLResource(self.vh_xml_file, defuse='always', lazy=True)
        self.assertIsInstance(resource.root, ElementTree.Element)

        xml_file = self.casepath('resources/with_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)
        with self.assertRaises(XMLResourceForbidden):
            XMLResource(xml_file, defuse='always', lazy=True)

        xml_file = self.casepath('resources/unused_external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)
        with self.assertRaises(XMLResourceForbidden):
            XMLResource(xml_file, defuse='always', lazy=True)

    def test_xml_resource_defuse_other_source_types(self):
        xml_file = self.casepath('resources/external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)

        with self.assertRaises(XMLResourceForbidden):
            XMLResource(xml_file, defuse='always', lazy=True)

        with self.assertRaises(XMLResourceForbidden):
            XMLResource(xml_file, defuse='always', lazy=False)

        with self.assertRaises(XMLResourceForbidden):
            XMLResource(xml_file, defuse='always', lazy=True)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(fp, defuse='always', lazy=False)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(fp.read(), defuse='always', lazy=False)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(StringIO(fp.read()), defuse='always', lazy=False)

    def test_xml_resource_defuse_bypass_example(self):
        unsafe_xml_file = self.casepath('resources/external_entity.xml')
        safe_xml_file = self.casepath('resources/dummy file.xml')

        with self.assertRaises(XMLResourceForbidden):
            with open(unsafe_xml_file) as fp:
                defuse_xml(fp)

        url = normalize_url(safe_xml_file)
        with open(unsafe_xml_file) as fp:
            fp.url = url
            with self.assertRaises(XMLResourceForbidden):
                defuse_xml(fp)

            # If XMLResource use fp.url attribute for defusing not-seekable
            # resources the defuse checks would pass silently
            with urlopen(fp.url) as fp2:
                self.assertTrue(fp2.seekable())
                self.assertIs(defuse_xml(fp2), fp2)

    def test_xml_resource_defuse_nonlocal(self):
        xml_file = self.casepath('resources/external_entity.xml')
        resource = XMLResource(xml_file, defuse='nonlocal', lazy=True)
        self.assertIsInstance(resource, XMLResource)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(fp, defuse='nonlocal', lazy=True)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(fp.read(), defuse='nonlocal', lazy=True)

        with self.assertRaises(XMLResourceForbidden):
            with open(xml_file) as fp:
                XMLResource(StringIO(fp.read()), defuse='nonlocal', lazy=True)

    def test_xml_resource_timeout(self):
        resource = XMLResource(self.vh_xml_file, timeout=30)
        self.assertEqual(resource.timeout, 30)
        self.assertRaises(TypeError, XMLResource, self.vh_xml_file, timeout='100')
        self.assertRaises(ValueError, XMLResource, self.vh_xml_file, timeout=0)

    def test_xml_resource_laziness(self):
        resource = XMLResource(self.vh_xml_file, lazy=True)
        self.assertTrue(resource.is_lazy())
        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertFalse(resource.is_lazy())
        resource = XMLResource(self.vh_xml_file, lazy=1)
        self.assertTrue(resource.is_lazy())
        resource = XMLResource(self.vh_xml_file, lazy=2)
        self.assertTrue(resource.is_lazy())
        resource = XMLResource(self.vh_xml_file, lazy=0)
        self.assertFalse(resource.is_lazy())

        with self.assertRaises(ValueError):
            XMLResource(self.vh_xml_file, lazy=-1)

        with self.assertRaises(TypeError):
            XMLResource(self.vh_xml_file, lazy='1')

    def test_xml_resource_base_url(self):
        resource = XMLResource(self.vh_xml_file)
        base_url = resource.base_url
        self.assertEqual(base_url, XMLResource(self.vh_xml_file, '/other').base_url)

        with open(self.vh_xml_file) as fp:
            self.assertIsNone(XMLResource(fp.read()).base_url)

        with open(self.vh_xml_file) as fp:
            resource = XMLResource(fp.read(), base_url='/foo')
            self.assertEqual(resource.base_url, '/foo')

        base_url = Path(self.vh_xml_file).parent
        resource = XMLResource('vehicles.xml', base_url)
        self.assertEqual(resource.base_url, base_url.as_uri())

        resource = XMLResource('vehicles.xml', str(base_url))
        self.assertEqual(resource.base_url, base_url.as_uri())

        resource = XMLResource('vehicles.xml', str(base_url).encode())
        self.assertEqual(resource.base_url, base_url.as_uri())
        self.assertEqual(resource.base_url, base_url.as_uri())

        with self.assertRaises(TypeError):
            XMLResource(self.vh_xml_file, base_url=False)

        with self.assertRaises(ValueError):
            XMLResource(self.vh_xml_file, base_url='<root/>')

        with self.assertRaises(ValueError):
            XMLResource(self.vh_xml_file, base_url=b'<root/>')

    def test_xml_resource_is_local(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertTrue(resource.is_local())

    def test_xml_resource_is_remote(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertFalse(resource.is_remote())

    def test_xml_resource_is_loaded(self):
        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertFalse(resource.is_loaded())
        resource.load()
        self.assertTrue(resource.is_loaded())

    def test_xml_resource__lazy_iterparse(self):
        resource = XMLResource(self.vh_xml_file, lazy=True)

        self.assertEqual(resource.defuse, 'remote')
        for _, elem in resource._lazy_iterparse(self.col_xml_file):
            self.assertTrue(is_etree_element(elem))

        for _, elem in resource._lazy_iterparse(self.col_xml_file):
            self.assertTrue(is_etree_element(elem))
            self.assertDictEqual(
                resource.get_nsmap(elem),
                {'col': 'http://example.com/ns/collection',
                 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
            )

        resource._defuse = 'always'
        for _, elem in resource._lazy_iterparse(self.col_xml_file):
            self.assertTrue(is_etree_element(elem))

    def test_xml_resource__parse(self):
        resource = XMLResource(self.vh_xml_file, lazy=False)

        self.assertEqual(resource.defuse, 'remote')
        with open(self.col_xml_file) as fp:
            resource._parse(fp)
        self.assertTrue(is_etree_element(resource.root))

        resource._defuse = 'always'
        with open(self.col_xml_file) as fp:
            resource._parse(fp)
        self.assertTrue(is_etree_element(resource.root))

        with urlopen(resource.url) as fp:
            resource._parse(fp)
        self.assertTrue(is_etree_element(resource.root))

    def test_xml_resource_tostring(self):
        resource = XMLResource(self.vh_xml_file)
        self.assertTrue(resource.tostring().startswith('<vh:vehicles'))

        resource = XMLResource(self.vh_xml_file, lazy=True)
        with self.assertRaises(XMLResourceError) as ctx:
            resource.tostring()
        self.assertEqual("can\'t serialize a lazy XML resource", str(ctx.exception))

        resource = XMLResource(XML_WITH_NAMESPACES)
        result = resource.tostring()
        self.assertNotEqual(result, XML_WITH_NAMESPACES)

        # With xml.etree.ElementTree namespace declarations are serialized
        # with a loss of information (all collapsed into the root element).
        self.assertEqual(result, '<pfa:root xmlns:pfa="http://xmlschema.test/nsa" '
                                 'xmlns:pfb="http://xmlschema.test/nsb">\n'
                                 '  <pfb:elem />\n</pfa:root>')

        if lxml_etree is not None:
            root = lxml_etree.XML(XML_WITH_NAMESPACES)
            resource = XMLResource(root)

            # With lxml.etree there is no information loss.
            self.assertEqual(resource.tostring(), XML_WITH_NAMESPACES)

    def test_xml_resource_open(self):
        resource = XMLResource(self.vh_xml_file)
        xml_file = resource.open()
        self.assertIsNot(xml_file, resource.source)
        data = xml_file.read().decode('utf-8')
        self.assertTrue(data.startswith('<?xml '))
        xml_file.close()

        resource.url = 'file:not-a-file'
        with self.assertRaises(XMLResourceOSError):
            resource.open()

        resource = XMLResource('<A/>')
        self.assertIsInstance(resource.open(), io.StringIO)

        resource = XMLResource(b'<A/>')
        self.assertIsInstance(resource.open(), io.BytesIO)

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

    def test_xml_resource_manager(self):
        resource = XMLResource(self.vh_xml_file)

        with XMLResourceManager(resource) as ctx:
            self.assertTrue(callable(ctx.fp.read))
            self.assertFalse(ctx.fp.closed)
        self.assertTrue(ctx.fp.closed)

        resource = XMLResource(open(self.vh_xml_file))

        with XMLResourceManager(resource) as ctx:
            self.assertTrue(callable(ctx.fp.read))
            self.assertFalse(ctx.fp.closed)
        self.assertFalse(ctx.fp.closed)
        resource.close()

    def test_xml_resource_close(self):
        resource = XMLResource(self.vh_xml_file)
        resource.close()

        with resource.open() as xml_file:
            self.assertTrue(callable(xml_file.read))

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(source=xml_file)
            resource.close()
            with self.assertRaises(XMLResourceOSError):
                resource.open()

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(xml_file)

        with self.assertRaises(XMLResourceOSError):
            resource.load()  # I/O operation on closed file

    def test_xml_resource_iter(self):
        resource = XMLResource(XMLSchema.meta_schema.source.url)
        self.assertFalse(resource.is_lazy())
        lazy_resource = XMLResource(XMLSchema.meta_schema.source.url, lazy=True)
        self.assertTrue(lazy_resource.is_lazy())

        tags = [x.tag for x in resource.iter()]
        self.assertEqual(len(tags), 1390)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)

        lazy_tags = [x.tag for x in lazy_resource.iter()]
        self.assertEqual(len(lazy_tags), 1390)
        self.assertEqual(lazy_tags[0], '{%s}schema' % XSD_NAMESPACE)
        self.assertNotEqual(tags, lazy_tags)

        tags = [x.tag for x in resource.iter('{%s}complexType' % XSD_NAMESPACE)]
        self.assertEqual(len(tags), 56)
        self.assertEqual(tags[0], '{%s}complexType' % XSD_NAMESPACE)
        self.assertListEqual(
            tags, [x.tag for x in lazy_resource.iter('{%s}complexType' % XSD_NAMESPACE)]
        )

    def test_xml_resource_iter_depth(self):
        resource = XMLResource(XMLSchema.meta_schema.source.url)
        self.assertFalse(resource.is_lazy())
        lazy_resource = XMLResource(XMLSchema.meta_schema.source.url, lazy=True)
        self.assertTrue(lazy_resource.is_lazy())

        # Note: Elements change using a lazy resource so compare only tags

        tags = [x.tag for x in resource.iter_depth()]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth()]
        self.assertEqual(len(lazy_tags), 156)
        self.assertEqual(lazy_tags[0], '{%s}annotation' % XSD_NAMESPACE)
        self.assertEqual(lazy_tags[-1], '{%s}element' % XSD_NAMESPACE)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=3)]
        self.assertListEqual(tags, lazy_tags)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=1)]
        self.assertEqual(len(lazy_tags), 156)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=4)]
        self.assertEqual(len(lazy_tags), 157)
        self.assertEqual(tags[0], lazy_tags[-1])

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=5)]
        self.assertEqual(len(lazy_tags), 158)
        self.assertEqual(tags[0], lazy_tags[0])
        self.assertEqual(tags[0], lazy_tags[-1])

        with self.assertRaises(ValueError) as ctx:
            _ = [x.tag for x in lazy_resource.iter_depth(mode=6)]
        self.assertEqual("invalid argument mode=6", str(ctx.exception))

        source = StringIO('<a xmlns:tns0="http://example.com/ns0"><b1>'
                          '  <c1 xmlns:tns1="http://example.com/ns1"/>'
                          '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                          '</b1><b2><c3><d1/></c3></b2></a>')
        resource = XMLResource(source, lazy=3)

        ancestors = []
        self.assertIs(next(resource.iter_depth(ancestors=ancestors)), resource.root[1][0][0])
        nsmap = resource.get_nsmap(resource.root[1][0][0])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0'})
        self.assertListEqual(ancestors, [resource.root, resource.root[1], resource.root[1][0]])

    def test_xml_resource_iterfind(self):
        namespaces = {'xs': XSD_NAMESPACE}
        resource = XMLResource(XMLSchema.meta_schema.source.url)
        self.assertFalse(resource.is_lazy())
        lazy_resource = XMLResource(XMLSchema.meta_schema.source.url, lazy=True)
        self.assertTrue(lazy_resource.is_lazy())

        tags = [x.tag for x in resource.iterfind(path='.')]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)

        with self.assertRaises(XMLSchemaValueError) as ctx:
            _ = [x.tag for x in lazy_resource.iterfind(path='.')]
        self.assertEqual("can't use path '.' on a lazy resource", str(ctx.exception))

        tags = [x.tag for x in resource.iterfind(path='*')]
        self.assertEqual(len(tags), 156)
        self.assertEqual(tags[0], '{%s}annotation' % XSD_NAMESPACE)
        lazy_tags = [x.tag for x in lazy_resource.iterfind(path='*')]
        self.assertListEqual(tags, lazy_tags)

        tags = [x.tag for x in resource.iterfind('xs:complexType', namespaces)]
        self.assertEqual(len(tags), 35)
        self.assertTrue(all(t == '{%s}complexType' % XSD_NAMESPACE for t in tags))
        lazy_tags = [x.tag for x in lazy_resource.iterfind('xs:complexType', namespaces)]
        self.assertListEqual(tags, lazy_tags)

        tags = [x.tag for x in resource.iterfind('. /. / xs:complexType', namespaces)]
        self.assertEqual(len(tags), 35)
        self.assertTrue(all(t == '{%s}complexType' % XSD_NAMESPACE for t in tags))
        lazy_tags = [
            x.tag for x in lazy_resource.iterfind('. /. / xs:complexType', namespaces)
        ]
        self.assertListEqual(tags, lazy_tags)

    def test_xml_resource_find(self):
        root = ElementTree.XML('<a><b1><c1/><c2 x="2"/></b1><b2/></a>')
        resource = XMLResource(root)

        self.assertIs(resource.find('*/c2'), root[0][1])
        self.assertIsNone(resource.find('*/c3'))

        resource = XMLResource('<a><b1>'
                               '  <c1 xmlns:tns1="http://example.com/ns1"/>'
                               '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                               '</b1><b2/></a>')
        self.assertIs(resource.find('*/c2'), resource.root[0][1])
        nsmap = resource.get_nsmap(resource.root[0][1])
        self.assertDictEqual(nsmap, {'tns2': 'http://example.com/ns2'})

        ancestors = []
        self.assertIs(resource.find('*/c2', ancestors=ancestors),
                      resource.root[0][1])
        nsmap = resource.get_nsmap(resource.root[0][1])
        self.assertDictEqual(nsmap, {'tns2': 'http://example.com/ns2'})
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

        ancestors = []
        self.assertIs(resource.find('.', ancestors=ancestors), resource.root)
        self.assertDictEqual(resource.get_nsmap(resource.root), {})
        self.assertListEqual(ancestors, [])

        ancestors = []
        self.assertIsNone(resource.find('b3', ancestors=ancestors))
        self.assertListEqual(ancestors, [])

    def test_xml_resource_lazy_find(self):
        source = StringIO('<a><b1><c1/><c2 x="2"/></b1><b2/></a>')
        resource = XMLResource(source, lazy=True)
        self.assertIs(resource.find('*/c2'), resource.root[0][1])

        source = StringIO('<a xmlns:tns0="http://example.com/ns0"><b1>'
                          '  <c1 xmlns:tns1="http://example.com/ns1"/>'
                          '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                          '</b1><b2><c3><d1/></c3></b2></a>')
        resource = XMLResource(source, lazy=True)

        ancestors = []
        self.assertIs(resource.find('*/c2', ancestors=ancestors),
                      resource.root[0][1])
        nsmap = resource.get_nsmap(resource.root[0][1])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0',
                                     'tns2': 'http://example.com/ns2'})
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

        ancestors = []
        self.assertIs(resource.find('*/c3', ancestors=ancestors),
                      resource.root[1][0])
        nsmap = resource.get_nsmap(resource.root[1][0])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0'})
        self.assertListEqual(ancestors, [resource.root, resource.root[1]])

        ancestors = []
        self.assertIs(resource.find('*/c3/d1', ancestors=ancestors),
                      resource.root[1][0][0])

        nsmap = resource.get_nsmap(resource.root[1][0][0])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0'})
        self.assertListEqual(ancestors,
                             [resource.root, resource.root[1], resource.root[1][0]])

        ancestors = []
        self.assertIs(resource.find('*', ancestors=ancestors),
                      resource.root[0])
        nsmap = resource.get_nsmap(resource.root[0])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0'})
        self.assertListEqual(ancestors, [resource.root])

        ancestors = []
        with self.assertRaises(XMLSchemaValueError) as ctx:
            resource.find('/b1', ancestors=ancestors)
        self.assertEqual("can't use path '/b1' on a lazy resource", str(ctx.exception))

        source.seek(0)
        resource = XMLResource(source, lazy=2)
        ancestors = []
        self.assertIs(resource.find('*/c2', ancestors=ancestors),
                      resource.root[0][1])
        nsmap = resource.get_nsmap(resource.root[0][1])
        self.assertDictEqual(nsmap, {'tns0': 'http://example.com/ns0',
                                     'tns2': 'http://example.com/ns2'})
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

    def test_xml_resource_findall(self):
        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/></a>')
        resource = XMLResource(root)

        self.assertListEqual(resource.findall('*/*'), root[0][:])
        self.assertListEqual(resource.findall('*/c3'), [])

    def test_xml_resource_nsmap_tracking(self):
        xsd_file = self.casepath('examples/collection/collection4.xsd')
        resource = XMLResource(xsd_file)
        root = resource.root

        for elem in resource.iter():
            nsmap = resource.get_nsmap(elem)
            if elem is root[2][0] or elem in root[2][0]:
                self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                               '': 'http://www.w3.org/2001/XMLSchema'})
            else:
                self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                               '': 'http://example.com/ns/collection'})

        resource._nsmaps.clear()
        resource._nsmaps[resource.root] = {}

        for elem in resource.iter():
            nsmap = resource.get_nsmap(elem)
            if elem is resource.root:
                self.assertEqual(nsmap, {})
            else:
                self.assertIsNone(nsmap)

        if lxml_etree is not None:
            tree = lxml_etree.parse(xsd_file)
            resource = XMLResource(tree)
            root = resource.root

            for elem in resource.iter():
                if callable(elem.tag):
                    continue

                nsmap = resource.get_nsmap(elem)
                if elem is root[2][0] or elem in root[2][0]:
                    self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                                   '': 'http://www.w3.org/2001/XMLSchema'})
                else:
                    self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                                   '': 'http://example.com/ns/collection'})

        resource = XMLResource(xsd_file, lazy=True)
        root = resource.root
        for k, elem in enumerate(resource.iter()):
            if not k:
                self.assertIs(elem, resource.root)
                self.assertIsNot(root, resource.root)

            nsmap = resource.get_nsmap(elem)
            try:
                if elem is resource.root[2][0] or elem in resource.root[2][0]:
                    self.assertEqual(nsmap[''], 'http://www.w3.org/2001/XMLSchema')
                else:
                    self.assertEqual(nsmap[''], 'http://example.com/ns/collection')
            except IndexError:
                self.assertEqual(nsmap[''], 'http://example.com/ns/collection')

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
            </root>""", lazy=False)
        self.assertEqual(set(resource.get_namespaces(root_only=False).keys()),
                         {'', 'tns', 'default'})

        resource = XMLResource("""<?xml version="1.0" ?>
            <root xmlns:tns="tns1">
                <tns:elem1 xmlns:tns="tns1" xmlns="unknown"/>
            </root>""", lazy=False)
        self.assertEqual(set(resource.get_namespaces(root_only=False).keys()), {'default', 'tns'})
        self.assertEqual(resource.get_namespaces(root_only=True).keys(), {'tns'})

        resource = XMLResource("""<?xml version="1.0" ?>
            <root xmlns:tns="tns1">
                <tns:elem1 xmlns:tns="tns3" xmlns="unknown"/>
            </root>""", lazy=False)
        self.assertEqual(set(resource.get_namespaces(root_only=False).keys()),
                         {'default', 'tns', 'tns0'})

        resource = XMLResource('<root/>')
        with self.assertRaises(ValueError) as ctx:
            resource.get_namespaces(namespaces={'xml': "http://example.com/ne"})
        self.assertIn("reserved prefix 'xml'", str(ctx.exception))

    def test_xml_resource_get_locations(self):
        resource = XMLResource(self.col_xml_file)
        self.check_url(resource.url, normalize_url(self.col_xml_file))

        locations = resource.get_locations([('ns', 'other.xsd')], root_only=False)
        self.assertEqual(len(locations), 2)
        self.check_url(locations[0][1], os.path.join(self.col_dir, 'other.xsd'))
        self.check_url(locations[1][1], normalize_url(self.col_xsd_file))

        source = StringIO('<a xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                          '   xsi:schemaLocation="http://example.com/ns1 /loc1"><b1>'
                          '  <c1 xsi:schemaLocation="http://example.com/ns2 /loc2"/>'
                          '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                          '</b1></a>')

        resource = XMLResource(source)
        locations = resource.get_locations(root_only=False)
        self.assertEqual(len(locations), 2)
        self.assertEqual(locations[0][0], 'http://example.com/ns1')
        self.assertRegex(locations[0][1], f'file://{DRIVE_REGEX}/loc1')
        self.assertEqual(locations[1][0], 'http://example.com/ns2')
        self.assertRegex(locations[1][1], f'file://{DRIVE_REGEX}/loc2')

        locations = resource.get_locations(root_only=True)
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0][0], 'http://example.com/ns1')
        self.assertRegex(locations[0][1], f'file://{DRIVE_REGEX}/loc1')

    @unittest.skipIf(SKIP_REMOTE_TESTS or platform.system() == 'Windows',
                     "Remote networks are not accessible or avoid SSL "
                     "verification error on Windows.")
    def test_remote_resource_loading(self):
        url = "https://raw.githubusercontent.com/brunato/xmlschema/master/" \
              "tests/test_cases/examples/collection/collection.xsd"

        with urlopen(url) as rh:
            col_xsd_resource = XMLResource(rh)

        self.assertIsNone(col_xsd_resource.url, url)
        self.assertIsNone(col_xsd_resource.filepath)

        self.assertEqual(col_xsd_resource.namespace, XSD_NAMESPACE)
        self.assertIsNone(col_xsd_resource.seek(0))

        with self.assertRaises(XMLResourceOSError) as ctx:
            col_xsd_resource.load()
        self.assertIn('has been closed', str(ctx.exception))

        col_xsd_resource = XMLResource(url)
        col_xsd_resource.load()
        col_schema = XMLSchema(col_xsd_resource.get_text())
        self.assertTrue(isinstance(col_schema, XMLSchema))

        vh_schema = XMLSchema("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                              "tests/test_cases/examples/vehicles/vehicles.xsd")
        self.assertTrue(isinstance(vh_schema, XMLSchema))
        self.assertTrue(vh_schema.source.is_remote())

    def test_schema_defuse(self):
        vh_schema = XMLSchema(self.vh_xsd_file, defuse='always')
        self.assertIsInstance(vh_schema.root, ElementTree.Element)
        for schema in vh_schema.maps.iter_schemas():
            self.assertIsInstance(schema.root, ElementTree.Element)

    def test_schema_resource_access(self):
        vh_schema = XMLSchema(self.vh_xsd_file, allow='sandbox')
        self.assertTrue(isinstance(vh_schema, XMLSchema))

        xsd_source = """
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:vh="http://example.com/vehicles">
            <xs:import namespace="http://example.com/vehicles" schemaLocation="{}"/>
        </xs:schema>""".format(self.vh_xsd_file)

        schema = XMLSchema(xsd_source, allow='all')
        self.assertTrue(isinstance(schema, XMLSchema))
        self.assertIn("http://example.com/vehicles", schema.maps.namespaces)
        self.assertEqual(len(schema.maps.namespaces["http://example.com/vehicles"]), 4)

        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")
            XMLSchema(xsd_source, allow='remote')
            self.assertEqual(len(ctx), 1, "Expected one import warning")
            self.assertIn("block access to local resource", str(ctx[0].message))

        schema = XMLSchema(xsd_source, allow='local')
        self.assertTrue(isinstance(schema, XMLSchema))
        self.assertIn("http://example.com/vehicles", schema.maps.namespaces)
        self.assertEqual(len(schema.maps.namespaces["http://example.com/vehicles"]), 4)

        with self.assertRaises(XMLSchemaValueError) as ctx:
            XMLSchema(xsd_source, allow='sandbox')
        self.assertIn("block access to files out of sandbox", str(ctx.exception))

        schema = XMLSchema(
            xsd_source, base_url=os.path.dirname(self.vh_xsd_file), allow='all'
        )
        self.assertTrue(isinstance(schema, XMLSchema))
        self.assertIn("http://example.com/vehicles", schema.maps.namespaces)
        self.assertEqual(len(schema.maps.namespaces["http://example.com/vehicles"]), 4)

        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")
            XMLSchema(xsd_source, base_url='/improbable', allow='sandbox')
            self.assertEqual(len(ctx), 1, "Expected one import warning")
            self.assertIn("block access to out of sandbox", str(ctx[0].message))

    def test_fid_with_name_attr(self):
        """XMLResource gets correct data when passed a file like object
        with a name attribute that isn't on disk.

        These file descriptors appear when working with the contents from a
        zip using the zipfile module and with Django files in some
        instances.
        """
        class FileProxy:
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

    def test_parent_map(self):
        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/></a>')
        resource = XMLResource(root)
        self.assertIsNone(resource.parent_map[root])
        self.assertIs(resource.parent_map[root[0]], root)
        self.assertIs(resource.parent_map[root[1]], root)
        self.assertIs(resource.parent_map[root[0][0]], root[0])
        self.assertIs(resource.parent_map[root[0][1]], root[0])

        resource = XMLResource(StringIO('<a><b1><c1/><c2/></b1><b2/></a>'), lazy=True)
        with self.assertRaises(XMLResourceError) as ctx:
            _ = resource.parent_map
        self.assertEqual("can't create the parent map of a lazy XML resource",
                         str(ctx.exception))

    def test_get_nsmap(self):
        source = '<a xmlns="uri1"><b1 xmlns:x="uri2"><c1/><c2/></b1><b2 xmlns="uri3"/></a>'
        alien_elem = ElementTree.XML('<a/>')

        root = ElementTree.XML(source)
        resource = XMLResource(root)

        self.assertIsNone(resource.get_nsmap(root))
        self.assertIsNone(resource.get_nsmap(root[1]))
        self.assertIsNone(resource.get_nsmap(alien_elem))

        if lxml_etree is not None:
            root = lxml_etree.XML(source)
            resource = XMLResource(root)

            self.assertDictEqual(resource.get_nsmap(root), {'': 'uri1'})
            self.assertDictEqual(resource.get_nsmap(root[0]), {'x': 'uri2', '': 'uri1'})
            self.assertDictEqual(resource.get_nsmap(root[1]), {'': 'uri3'})
            self.assertIsNone(resource.get_nsmap(alien_elem))

        resource = XMLResource(source)
        root = resource.root

        self.assertDictEqual(resource.get_nsmap(root), {'': 'uri1'})
        self.assertDictEqual(resource.get_nsmap(root[0]), {'': 'uri1', 'x': 'uri2'})
        self.assertDictEqual(resource.get_nsmap(root[1]), {'': 'uri3'})
        self.assertIsNone(resource.get_nsmap(alien_elem))

        resource = XMLResource(StringIO(source), lazy=True)
        root = resource.root
        self.assertTrue(resource.is_lazy())

        self.assertDictEqual(resource.get_nsmap(root), {'': 'uri1'})
        self.assertIsNone(resource.get_nsmap(root[0]))
        self.assertIsNone(resource.get_nsmap(root[1]))
        self.assertIsNone(resource.get_nsmap(alien_elem))

    def test_get_xmlns(self):
        source = '<a xmlns="uri1"><b1 xmlns:x="uri2"><c1/><c2/></b1><b2 xmlns="uri3"/></a>'
        alien_elem = ElementTree.XML('<a/>')

        root = ElementTree.XML(source)
        resource = XMLResource(root)

        self.assertIsNone(resource.get_xmlns(root))
        self.assertIsNone(resource.get_xmlns(root[1]))
        self.assertIsNone(resource.get_xmlns(alien_elem))

        if lxml_etree is not None:
            root = lxml_etree.XML(source)
            resource = XMLResource(root)

            self.assertListEqual(resource.get_xmlns(root), [('', 'uri1')])
            self.assertListEqual(resource.get_xmlns(root[0]), [('x', 'uri2')])
            self.assertListEqual(resource.get_xmlns(root[1]), [('', 'uri3')])
            self.assertIsNone(resource.get_xmlns(alien_elem))

        resource = XMLResource(source)
        root = resource.root

        self.assertListEqual(resource.get_xmlns(root), [('', 'uri1')])
        self.assertListEqual(resource.get_xmlns(root[0]), [('x', 'uri2')])
        self.assertListEqual(resource.get_xmlns(root[1]), [('', 'uri3')])
        self.assertIsNone(resource.get_xmlns(alien_elem))

        resource = XMLResource(StringIO(source), lazy=True)
        root = resource.root
        self.assertTrue(resource.is_lazy())

        self.assertListEqual(resource.get_xmlns(root), [('', 'uri1')])
        self.assertIsNone(resource.get_xmlns(root[0]))
        self.assertIsNone(resource.get_xmlns(root[1]))
        self.assertIsNone(resource.get_xmlns(alien_elem))

    def test_xml_subresource(self):
        resource = XMLResource(self.vh_xml_file, lazy=True)
        with self.assertRaises(XMLResourceError) as ctx:
            resource.subresource(resource.root)
        self.assertEqual("can't create a subresource from a lazy XML resource",
                         str(ctx.exception))

        resource = XMLResource(self.vh_xml_file)
        root = resource.root
        subresource = resource.subresource(root[0])
        self.assertIs(subresource.root, resource.root[0])

        with self.assertRaises(XMLSchemaTypeError) as ctx:
            resource.subresource(None)
        self.assertEqual("argument must be an Element instance", str(ctx.exception))

        if lxml_etree is not None:
            resource = XMLResource(lxml_etree.parse(self.vh_xml_file).getroot())
            root = resource.root
            subresource = resource.subresource(root[0])
            self.assertIs(subresource.root, resource.root[0])

        xml_text = '<a><b1 xmlns:x="tns0"><c1 xmlns:y="tns1"/><c2/></b1><b2/></a>'
        resource = XMLResource(xml_text)
        root = resource.root
        subresource = resource.subresource(root[0])
        self.assertIs(subresource.root, resource.root[0])

    def test_loading_from_unrelated_dirs__issue_237(self):
        relative_path = str(pathlib.Path(__file__).parent.joinpath(
            'test_cases/issues/issue_237/dir1/issue_237.xsd'
        ))
        schema = XMLSchema(relative_path)
        self.assertEqual(schema.maps.namespaces[''][1].name, 'issue_237a.xsd')
        self.assertEqual(schema.maps.namespaces[''][2].name, 'issue_237b.xsd')

    def test_uri_mapper(self):
        urn = 'urn:example:xmlschema:vehicles.xsd'
        uri_mapper = {urn: self.vh_xsd_file}

        with self.assertRaises(XMLResourceOSError):
            XMLResource(urn)

        resource = XMLResource(urn, uri_mapper=uri_mapper)
        self.assertEqual(resource.url[-30:], 'examples/vehicles/vehicles.xsd')

        vh_schema = XMLSchema(self.vh_xsd_file, uri_mapper=uri_mapper)
        self.assertTrue(vh_schema.is_valid(self.vh_xml_file))

        def uri_mapper(uri):
            return self.vh_xsd_file if uri == urn else uri

        resource = XMLResource(urn, uri_mapper=uri_mapper)
        self.assertEqual(resource.url[-30:], 'examples/vehicles/vehicles.xsd')

    def test_opener_argument(self):

        class NoSeekFile(addinfourl):
            def seekable(self): return False
            def seek(self, pos, whence=0): return pos

        class MyFileHandler(FileHandler):
            def file_open(self, req):
                obj = super().file_open(req)
                if not isinstance(obj, addinfourl):
                    return obj
                obj.close()
                return NoSeekFile(open(obj.fp.name, 'rb'), obj.headers, obj.url, obj.code)

        opener = build_opener(MyFileHandler)

        resource = XMLResource(self.vh_xml_file, opener=opener)
        fp = resource.open()
        try:
            self.assertIsInstance(fp, NoSeekFile)
        finally:
            fp.close()

        resource = XMLResource(self.vh_xml_file, opener=opener, defuse='always')
        try:
            fp = resource.open()
            self.assertIsInstance(fp, NoSeekFile)
            self.assertFalse(fp.seekable())
            self.assertEqual(fp.tell(), 0)  # File not used for defusing XML data
        finally:
            fp.close()

    def test_iterparse_argument(self):
        resource = XMLResource(self.vh_xml_file, iterparse=ElementTree.iterparse)

        k = 0
        for k, elem in enumerate(resource.root.iter(), start=1):
            self.assertTrue(is_etree_element(elem))
            self.assertFalse(is_lxml_element(elem))
            self.assertIsInstance(elem, ElementTree.Element)
            if k == 0:
                self.assertIs(elem, resource.root)

        self.assertEqual(k, 7)

    def test_iterparse_argument_with_parser_instance(self):

        def iterparse(fp, events):
            builder = ElementTree.TreeBuilder(insert_comments=True)
            parser = ElementTree.XMLParser(target=builder)
            return ElementTree.iterparse(fp, events=events, parser=parser)

        resource = XMLResource(self.vh_xml_file, iterparse=iterparse)

        k = 0
        for k, elem in enumerate(resource.root.iter(), start=1):
            self.assertTrue(is_etree_element(elem))
            self.assertFalse(is_lxml_element(elem))
            self.assertIsInstance(elem, ElementTree.Element)
            if k == 0:
                self.assertIs(elem, resource.root)
            elif k == 4:
                self.assertTrue(callable(elem.tag))  # <!-- Comment -->

        self.assertEqual(k, 8)

    @unittest.skipIf(lxml_etree is None, "Skip: lxml is not available.")
    def test_iterparse_argument_with_lxml(self):
        resource = XMLResource(self.vh_xml_file, iterparse=lxml_etree.iterparse)

        k = 0
        for k, elem in enumerate(resource.root.iter(), start=1):
            self.assertTrue(is_lxml_element(elem))
            self.assertIsInstance(elem, lxml_etree._Element)
            if k == 0:
                self.assertIs(elem, resource.root)
            elif k == 4:
                self.assertTrue(callable(elem.tag))  # <!-- Comment -->

        self.assertEqual(k, 8)

    @unittest.skipIf(lxml_etree is None, "Skip: lxml is not available.")
    def test_iterparse_argument_for_html(self):

        def iterparse(fp, events):
            # Ignore deprecation warning of 'strip_cdata' option of HTMLParser(),
            # no way to provide a parser instance or other parameters.
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                return lxml_etree.iterparse(fp, events=events, html=True)

        html_source = (b"<html><head><title>page title</title></head>"
                       b"<body><p>foo<p>bar</body></html>")

        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource(html_source, iterparse=lxml_etree.iterparse)
        self.assertIn("Opening and ending tag mismatch", str(ctx.exception))

        resource = XMLResource(html_source, iterparse=iterparse)
        self.assertTrue(is_lxml_element(resource.root))
        self.assertEqual(resource.root.tag, 'html')

        k = 0
        for k, elem in enumerate(resource.root.iter(), start=1):
            self.assertTrue(is_lxml_element(elem))
            self.assertIsInstance(elem, lxml_etree._Element)
            if k == 0:
                self.assertIs(elem, resource.root)

        self.assertEqual(k, 6)

    def test_xml_resource_copy(self):
        path = Path(self.vh_xml_file)

        resource = XMLResource(path, lazy=True)

        other = copy.copy(resource)

        self.assertIsNot(other, resource)
        self.assertIs(other.root, resource.root)
        self.assertIsNot(other._nsmaps, resource._nsmaps)
        self.assertIsNot(other._xmlns, resource._xmlns)


if __name__ == '__main__':
    run_xmlschema_tests('XML resources')
