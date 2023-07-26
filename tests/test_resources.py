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

import unittest
import os
import pathlib
import platform
import warnings
from io import StringIO, BytesIO
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlsplit, uses_relative
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from elementpath.etree import PyElementTree, is_etree_element

from xmlschema import fetch_namespaces, fetch_resource, normalize_url, \
    fetch_schema, fetch_schema_locations, XMLResource, XMLResourceError, XMLSchema
from xmlschema.names import XSD_NAMESPACE
import xmlschema.resources
from xmlschema.resources import is_url, is_local_url, is_remote_url, \
    url_path_is_file, normalize_locations
from xmlschema.testing import SKIP_REMOTE_TESTS


TEST_CASES_DIR = str(pathlib.Path(__file__).absolute().parent.joinpath('test_cases'))

DRIVE_REGEX = '(/[a-zA-Z]:|/)' if platform.system() == 'Windows' else ''

XML_WITH_NAMESPACES = '<pfa:root xmlns:pfa="http://xmlschema.test/nsa">\n' \
                      '  <pfb:elem xmlns:pfb="http://xmlschema.test/nsb"/>\n' \
                      '</pfa:root>'


def casepath(relative_path):
    return str(pathlib.Path(TEST_CASES_DIR).joinpath(relative_path))


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

    def test_path_from_uri(self):
        _PurePath = xmlschema.resources._PurePath
        _PosixPurePath = xmlschema.resources._PurePosixPath
        _WindowsPurePath = xmlschema.resources._PureWindowsPath

        with self.assertRaises(ValueError) as ec:
            _PurePath.from_uri('')
        self.assertEqual(str(ec.exception), 'Empty URI provided!')

        path = _PurePath.from_uri('https://example.com/names/?name=foo')
        self.assertIsInstance(path, _PosixPurePath)
        self.assertEqual(str(path), '/names')

        path = _PosixPurePath.from_uri('file:///home/foo/names/?name=foo')
        self.assertIsInstance(path, _PosixPurePath)
        self.assertEqual(str(path), '/home/foo/names')

        path = _PosixPurePath.from_uri('file:///home/foo/names#foo')
        self.assertIsInstance(path, _PosixPurePath)
        self.assertEqual(str(path), '/home/foo/names')

        path = _PosixPurePath.from_uri('file:///home\\foo\\names#foo')
        self.assertIsInstance(path, _WindowsPurePath)
        self.assertTrue(path.as_posix().endswith('/home/foo/names'))

        path = _PosixPurePath.from_uri('file:///c:/home/foo/names/')
        self.assertIsInstance(path, _WindowsPurePath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        path = _PosixPurePath.from_uri('file:c:/home/foo/names/')
        self.assertIsInstance(path, _WindowsPurePath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        with self.assertRaises(ValueError) as ec:
            _PurePath.from_uri('file://c:/home/foo/names/')
        self.assertEqual(str(ec.exception), "Invalid URI 'file://c:/home/foo/names/'")

    @unittest.skipIf(platform.system() == 'Windows', "Run only on posix systems")
    def test_normalize_url_posix(self):
        url1 = "https://example.com/xsd/other_schema.xsd"
        self.check_url(normalize_url(url1, base_url="/path_my_schema/schema.xsd"), url1)

        parent_dir = os.path.dirname(os.getcwd())
        self.check_url(normalize_url('../dir1/./dir2'), os.path.join(parent_dir, 'dir1/dir2'))
        self.check_url(normalize_url('../dir1/./dir2', '/home', keep_relative=True),
                       'file:///dir1/dir2')
        self.check_url(normalize_url('../dir1/./dir2', 'file:///home'), 'file:///dir1/dir2')

        self.check_url(normalize_url('other.xsd', 'file:///home'), 'file:///home/other.xsd')
        self.check_url(normalize_url('other.xsd', 'file:///home/'), 'file:///home/other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'file:///home'), 'file:///home/other.xsd')

        cwd = os.getcwd()
        cwd_url = 'file://{}/'.format(cwd) if cwd.startswith('/') else 'file:///{}/'.format(cwd)

        self.check_url(normalize_url('other.xsd', keep_relative=True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd', keep_relative=True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd'), cwd_url + 'other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'https://site/base', True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'http://site/base'), cwd_url + 'other.xsd')

        self.check_url(normalize_url('dummy path.xsd'), cwd_url + 'dummy%20path.xsd')
        self.check_url(normalize_url('dummy path.xsd', 'http://site/base'),
                       'http://site/base/dummy%20path.xsd')
        self.check_url(normalize_url('dummy path.xsd', 'file://host/home/'),
                       PurePath('//host/home/dummy path.xsd').as_uri())

        url = "file:///c:/Downloads/file.xsd"
        self.check_url(normalize_url(url, base_url="file:///d:/Temp/"), url)

    def test_normalize_url_windows(self):
        win_abs_path1 = 'z:\\Dir_1_0\\Dir2-0\\schemas/XSD_1.0/XMLSchema.xsd'
        win_abs_path2 = 'z:\\Dir-1.0\\Dir-2_0\\'
        self.check_url(normalize_url(win_abs_path1), win_abs_path1)

        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path1),
                       'file:///k:/Dir3/schema.xsd')
        self.check_url(normalize_url('k:\\Dir3\\schema.xsd', win_abs_path2),
                       'file:///k:/Dir3/schema.xsd')

        self.check_url(normalize_url('schema.xsd', win_abs_path2),
                       'file:///z:/Dir-1.0/Dir-2_0/schema.xsd')
        self.check_url(normalize_url('xsd1.0/schema.xsd', win_abs_path2),
                       'file:///z:/Dir-1.0/Dir-2_0/xsd1.0/schema.xsd')

        with self.assertRaises(ValueError) as ec:
            normalize_url('file:///\\k:\\Dir A\\schema.xsd')
        self.assertIn("Invalid URI", str(ec.exception))

    def test_normalize_url_unc_paths__issue_246(self):
        url = PureWindowsPath(r'\\host\share\file.xsd').as_uri()
        self.assertNotEqual(normalize_url(r'\\host\share\file.xsd'),
                            url)  # file://host/share/file.xsd
        self.assertEqual(normalize_url(r'\\host\share\file.xsd'),
                         url.replace('file://', 'file:////'))

    def test_normalize_url_unc_paths__issue_268(self,):
        unc_path = r'\\filer01\MY_HOME\dev\XMLSCHEMA\test.xsd'
        url = PureWindowsPath(unc_path).as_uri()
        self.assertEqual(str(PureWindowsPath(unc_path)), unc_path)
        self.assertEqual(url, 'file://filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        # Same UNC path as URI with the host inserted in path path.
        url_host_in_path = url.replace('file://', 'file:////')
        self.assertEqual(url_host_in_path, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        self.assertEqual(normalize_url(unc_path), url_host_in_path)

        with patch.object(os, 'name', 'nt'):
            self.assertEqual(os.name, 'nt')
            path = PurePath(unc_path)
            self.assertIs(path.__class__, PureWindowsPath)
            self.assertEqual(path.as_uri(), url)

            self.assertEqual(xmlschema.resources.os.name, 'nt')
            path = xmlschema.resources._PurePath(unc_path)
            self.assertIs(path.__class__, xmlschema.resources._PureWindowsPath)
            self.assertEqual(path.as_uri(), url_host_in_path)
            self.assertEqual(normalize_url(unc_path), url_host_in_path)

        with patch.object(os, 'name', 'posix'):
            self.assertEqual(os.name, 'posix')
            path = PurePath(unc_path)
            self.assertIs(path.__class__, PurePosixPath)
            self.assertEqual(str(path), unc_path)
            self.assertRaises(ValueError, path.as_uri)  # Not recognized as UNC path

            self.assertEqual(xmlschema.resources.os.name, 'posix')
            path = xmlschema.resources._PurePath(unc_path)
            self.assertIs(path.__class__, xmlschema.resources._PurePosixPath)
            self.assertEqual(str(path), unc_path)
            self.assertNotEqual(path.as_uri(), url)
            self.assertEqual(normalize_url(unc_path), url_host_in_path)

    def test_normalize_url_with_base_unc_path(self,):
        base_unc_path = '\\\\filer01\\MY_HOME\\'
        base_url = PureWindowsPath(base_unc_path).as_uri()
        self.assertEqual(str(PureWindowsPath(base_unc_path)), base_unc_path)
        self.assertEqual(base_url, 'file://filer01/MY_HOME/')

        # Same UNC path as URI with the host inserted in path path.
        base_url_host_in_path = base_url.replace('file://', 'file:////')
        self.assertEqual(base_url_host_in_path, 'file:////filer01/MY_HOME/')

        self.assertEqual(normalize_url(base_unc_path), base_url_host_in_path)

        with patch.object(os, 'name', 'nt'):
            self.assertEqual(os.name, 'nt')
            path = PurePath('dir/file')
            self.assertIs(path.__class__, PureWindowsPath)

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_unc_path)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url_host_in_path)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        with patch.object(os, 'name', 'posix'):
            self.assertEqual(os.name, 'posix')
            path = PurePath('dir/file')
            self.assertIs(path.__class__, PurePosixPath)

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_unc_path)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url=base_url)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url=base_url_host_in_path)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

    def test_normalize_url_slashes(self):
        # Issue #116
        url = '//anaconda/envs/testenv/lib/python3.6/site-packages/xmlschema/validators/schemas/'
        if os.name == 'posix':
            self.assertEqual(normalize_url(url), pathlib.PurePath(url).as_uri())
        else:
            # On Windows // is interpreted as a network share UNC path
            self.assertEqual(os.name, 'nt')
            self.assertEqual(normalize_url(url),
                             pathlib.PurePath(url).as_uri().replace('file://', 'file:////'))

        self.assertRegex(normalize_url('/root/dir1/schema.xsd'),
                         f'file://{DRIVE_REGEX}/root/dir1/schema.xsd')

        self.assertRegex(normalize_url('////root/dir1/schema.xsd'),
                         f'file://{DRIVE_REGEX}/root/dir1/schema.xsd')
        self.assertRegex(normalize_url('dir2/schema.xsd', '////root/dir1'),
                         f'file://{DRIVE_REGEX}/root/dir1/dir2/schema.xsd')

        self.assertEqual(normalize_url('//root/dir1/schema.xsd'),
                         'file:////root/dir1/schema.xsd')
        self.assertEqual(normalize_url('dir2/schema.xsd', '//root/dir1/'),
                         'file:////root/dir1/dir2/schema.xsd')
        self.assertEqual(normalize_url('dir2/schema.xsd', '//root/dir1'),
                         'file:////root/dir1/dir2/schema.xsd')

    def test_normalize_url_hash_character(self):
        url = normalize_url('issue #000.xml', 'file:///dir1/dir2/')
        self.assertRegex(url, f'file://{DRIVE_REGEX}/dir1/dir2/issue%20%23000.xml')

        url = normalize_url('data.xml', 'file:///dir1/dir2/issue%20001')
        self.assertRegex(url, f'file://{DRIVE_REGEX}/dir1/dir2/issue%20001/data.xml')

        url = normalize_url('data.xml', '/dir1/dir2/issue #002')
        self.assertRegex(url, f'{DRIVE_REGEX}/dir1/dir2/issue%20%23002/data.xml')

    def test_is_url_function(self):
        self.assertTrue(is_url(self.col_xsd_file))
        self.assertFalse(is_url('http://example.com['))
        self.assertTrue(is_url(b'http://example.com'))
        self.assertFalse(is_url(' \t<root/>'))
        self.assertFalse(is_url(b'  <root/>'))
        self.assertFalse(is_url('line1\nline2'))
        self.assertFalse(is_url(None))

    def test_is_local_url_function(self):
        self.assertTrue(is_local_url(self.col_xsd_file))
        self.assertTrue(is_local_url(Path(self.col_xsd_file)))

        self.assertTrue(is_local_url('/home/user/'))
        self.assertFalse(is_local_url('<home/>'))
        self.assertTrue(is_local_url('/home/user/schema.xsd'))
        self.assertTrue(is_local_url('  /home/user/schema.xsd  '))
        self.assertTrue(is_local_url('C:\\Users\\foo\\schema.xsd'))
        self.assertTrue(is_local_url(' file:///home/user/schema.xsd'))
        self.assertFalse(is_local_url('http://example.com/schema.xsd'))

        self.assertTrue(is_local_url(b'/home/user/'))
        self.assertFalse(is_local_url(b'<home/>'))
        self.assertTrue(is_local_url(b'/home/user/schema.xsd'))
        self.assertTrue(is_local_url(b'  /home/user/schema.xsd  '))
        self.assertTrue(is_local_url(b'C:\\Users\\foo\\schema.xsd'))
        self.assertTrue(is_local_url(b' file:///home/user/schema.xsd'))
        self.assertFalse(is_local_url(b'http://example.com/schema.xsd'))

    def test_is_remote_url_function(self):
        self.assertFalse(is_remote_url(self.col_xsd_file))

        self.assertFalse(is_remote_url('/home/user/'))
        self.assertFalse(is_remote_url('<home/>'))
        self.assertFalse(is_remote_url('/home/user/schema.xsd'))
        self.assertFalse(is_remote_url(' file:///home/user/schema.xsd'))
        self.assertTrue(is_remote_url('  http://example.com/schema.xsd'))

        self.assertFalse(is_remote_url(b'/home/user/'))
        self.assertFalse(is_remote_url(b'<home/>'))
        self.assertFalse(is_remote_url(b'/home/user/schema.xsd'))
        self.assertFalse(is_remote_url(b' file:///home/user/schema.xsd'))
        self.assertTrue(is_remote_url(b'  http://example.com/schema.xsd'))

    def test_url_path_is_file_function(self):
        self.assertTrue(url_path_is_file(self.col_xml_file))
        self.assertTrue(url_path_is_file(normalize_url(self.col_xml_file)))
        self.assertFalse(url_path_is_file(self.col_dir))
        self.assertFalse(url_path_is_file('http://example.com/'))

        with patch('platform.system', MagicMock(return_value="Windows")):
            self.assertFalse(url_path_is_file('file:///c:/Windows/unknown'))

    def test_normalize_locations_function(self):
        locations = normalize_locations(
            [('tns0', 'alpha'), ('tns1', 'http://example.com/beta')], base_url='/home/user'
        )
        self.assertEqual(locations[0][0], 'tns0')
        self.assertRegex(locations[0][1], f'file://{DRIVE_REGEX}/home/user/alpha')
        self.assertEqual(locations[1][0], 'tns1')
        self.assertEqual(locations[1][1], 'http://example.com/beta')

        locations = normalize_locations(
            {'tns0': 'alpha', 'tns1': 'http://example.com/beta'}, base_url='/home/user'
        )
        self.assertEqual(locations[0][0], 'tns0')
        self.assertRegex(locations[0][1], f'file://{DRIVE_REGEX}/home/user/alpha')
        self.assertEqual(locations[1][0], 'tns1')
        self.assertEqual(locations[1][1], 'http://example.com/beta')

        locations = normalize_locations(
            {'tns0': ['alpha', 'beta'], 'tns1': 'http://example.com/beta'}, base_url='/home/user'
        )
        self.assertEqual(locations[0][0], 'tns0')
        self.assertRegex(locations[0][1], f'file://{DRIVE_REGEX}/home/user/alpha')
        self.assertEqual(locations[1][0], 'tns0')
        self.assertRegex(locations[1][1], f'file://{DRIVE_REGEX}/home/user/beta')
        self.assertEqual(locations[2][0], 'tns1')
        self.assertEqual(locations[2][1], 'http://example.com/beta')

        locations = normalize_locations(
            {'tns0': 'alpha', 'tns1': 'http://example.com/beta'}, keep_relative=True
        )
        self.assertListEqual(locations, [('tns0', 'file:alpha'),
                                         ('tns1', 'http://example.com/beta')])

    def test_fetch_resource_function(self):
        with self.assertRaises(ValueError) as ctx:
            fetch_resource('')
        self.assertIn('argument must contain a not empty string', str(ctx.exception))

        wrong_path = casepath('resources/dummy_file.txt')
        self.assertRaises(XMLResourceError, fetch_resource, wrong_path)

        wrong_path = casepath('/home/dummy_file.txt')
        self.assertRaises(XMLResourceError, fetch_resource, wrong_path)

        right_path = casepath('resources/dummy file.txt')
        self.assertTrue(fetch_resource(right_path).endswith('dummy%20file.txt'))

        right_path = Path(casepath('resources/dummy file.txt')).relative_to(os.getcwd())
        self.assertTrue(fetch_resource(str(right_path), '/home').endswith('dummy%20file.txt'))

        with self.assertRaises(XMLResourceError):
            fetch_resource(str(right_path.parent.joinpath('dummy_file.txt')), '/home')

        ambiguous_path = casepath('resources/dummy file #2.txt')
        self.assertTrue(fetch_resource(ambiguous_path).endswith('dummy%20file%20%232.txt'))

        with urlopen(fetch_resource(ambiguous_path)) as res:
            self.assertEqual(res.read(), b'DUMMY CONTENT')

    def test_fetch_namespaces_function(self):
        self.assertFalse(fetch_namespaces(casepath('resources/malformed.xml')))

    def test_fetch_schema_locations(self):
        locations = fetch_schema_locations(self.col_xml_file)
        self.check_url(locations[0], self.col_xsd_file)
        self.assertEqual(locations[1][0][0], 'http://example.com/ns/collection')
        self.check_url(locations[1][0][1], self.col_xsd_file)
        self.check_url(fetch_schema(self.vh_xml_file), self.vh_xsd_file)

        with self.assertRaises(ValueError) as ctx:
            fetch_schema_locations('<empty/>')
        self.assertIn('does not contain any schema location hint', str(ctx.exception))

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
        self.assertIn('cannot load a lazy XML resource', str(ctx.exception))
        self.assertIsNone(resource.text)

        resource = XMLResource(self.vh_xml_file, lazy=False)
        self.assertEqual(resource.source, self.vh_xml_file)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, self.vh_xml_file)
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

        resource = XMLResource(self.vh_xml_file, lazy=False)
        resource._url = resource._url[:-12] + 'unknown.xml'
        with self.assertRaises(XMLResourceError):
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
        self.assertIn('cannot load a lazy XML resource', str(ctx.exception))
        self.assertIsNone(resource.text)

        resource = XMLResource(path, lazy=False)
        self.assertEqual(resource.source, path)
        self.assertEqual(resource.root.tag, '{http://example.com/vehicles}vehicles')
        self.check_url(resource.url, path.as_uri())
        self.assertIsNone(resource.text)
        resource.load()
        self.assertTrue(resource.text.startswith('<?xml'))

        resource = XMLResource(path, lazy=False)
        resource._url = resource._url[:-12] + 'unknown.xml'
        with self.assertRaises(XMLResourceError):
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
        xml_file = urlopen('file://{}'.format(add_leading_slash(self.vh_xml_file)))
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

        with self.assertRaises(XMLResourceError):
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
            self.assertEqual("cannot load a lazy XML resource", str(ctx.exception))

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

    def test_xml_resource_from_bytes_io(self):

        source = '<?xml version="1.0" encoding="iso-8859-1"?>\n<a>ç</a>'

        resource = XMLResource(BytesIO(source.encode('iso-8859-1')))
        self.assertIsNone(resource.text)
        resource.load()
        self.assertEqual(resource.text, source)

    def test_xml_resource_from_malformed_source(self):
        # related to issue #224
        malformed_xml_file = casepath('resources/malformed.xml')
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

    def test_xml_resource_update_nsmap_method(self):
        resource = XMLResource(self.vh_xml_file)

        nsmap = {}
        resource._update_nsmap(nsmap, 'xs', XSD_NAMESPACE)
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE})
        resource._update_nsmap(nsmap, 'xs', XSD_NAMESPACE)
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE})
        resource._update_nsmap(nsmap, 'tns0', 'http://example.com/ns')
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE, 'tns0': 'http://example.com/ns'})
        resource._update_nsmap(nsmap, 'xs', 'http://example.com/ns')
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'tns0': 'http://example.com/ns'})
        resource._update_nsmap(nsmap, 'xs', 'http://example.com/ns')
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'tns0': 'http://example.com/ns'})

        resource._update_nsmap(nsmap, 'xs', 'http://example.com/ns2')
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'xs1': 'http://example.com/ns2',
                                 'tns0': 'http://example.com/ns'})

    def test_xml_resource_access(self):
        resource = XMLResource(self.vh_xml_file)
        base_url = resource.base_url

        XMLResource(self.vh_xml_file, allow='local')
        XMLResource(
            self.vh_xml_file, base_url=os.path.dirname(self.vh_xml_file), allow='sandbox'
        )

        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource(self.vh_xml_file, allow='remote')
        self.assertTrue(str(ctx.exception).startswith("block access to local resource"))

        with self.assertRaises(URLError):
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='remote')

        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='local')
        self.assertEqual(str(ctx.exception),
                         "block access to remote resource https://xmlschema.test/vehicles.xsd")

        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='sandbox')
        self.assertEqual(str(ctx.exception),
                         "block access to files out of sandbox requires 'base_url' to be set")

        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource("/tmp/vehicles.xsd", allow='sandbox')
        self.assertEqual(
            str(ctx.exception),
            "block access to files out of sandbox requires 'base_url' to be set",
        )

        source = "/tmp/vehicles.xsd"
        with self.assertRaises(XMLResourceError) as ctx:
            XMLResource(source, base_url=base_url, allow='sandbox')
        self.assertEqual(
            str(ctx.exception),
            "block access to out of sandbox file {}".format(normalize_url(source)),
        )

        with self.assertRaises(TypeError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow=None)
        self.assertEqual(str(ctx.exception),
                         "invalid type <class 'NoneType'> for argument 'allow'")

        with self.assertRaises(ValueError) as ctx:
            XMLResource("https://xmlschema.test/vehicles.xsd", allow='any')
        self.assertEqual(str(ctx.exception),
                         "'allow' argument: 'any' is not a security mode")

        with self.assertRaises(XMLResourceError) as ctx:
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
        self.assertIsInstance(resource.root, PyElementTree.Element)

        xml_file = casepath('resources/with_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)
        with self.assertRaises(ElementTree.ParseError):
            XMLResource(xml_file, defuse='always', lazy=True)

        xml_file = casepath('resources/unused_external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)
        with self.assertRaises(ElementTree.ParseError):
            XMLResource(xml_file, defuse='always', lazy=True)

    def test_xml_resource_defuse_other_source_types(self):
        xml_file = casepath('resources/external_entity.xml')
        self.assertIsInstance(XMLResource(xml_file, lazy=True), XMLResource)

        with self.assertRaises(ElementTree.ParseError):
            XMLResource(xml_file, defuse='always', lazy=True)

        with self.assertRaises(ElementTree.ParseError):
            XMLResource(xml_file, defuse='always', lazy=False)

        with self.assertRaises(ElementTree.ParseError):
            XMLResource(xml_file, defuse='always', lazy=True)

        with self.assertRaises(ElementTree.ParseError):
            with open(xml_file) as fp:
                XMLResource(fp, defuse='always', lazy=False)

        with self.assertRaises(ElementTree.ParseError):
            with open(xml_file) as fp:
                XMLResource(fp.read(), defuse='always', lazy=False)

        with self.assertRaises(ElementTree.ParseError):
            with open(xml_file) as fp:
                XMLResource(StringIO(fp.read()), defuse='always', lazy=False)

    def test_xml_resource_defuse_nonlocal(self):
        xml_file = casepath('resources/external_entity.xml')
        resource = XMLResource(xml_file, defuse='nonlocal', lazy=True)
        self.assertIsInstance(resource, XMLResource)

        with self.assertRaises(ElementTree.ParseError):
            with open(xml_file) as fp:
                XMLResource(fp, defuse='nonlocal', lazy=True)

        with self.assertRaises(ElementTree.ParseError):
            with open(xml_file) as fp:
                XMLResource(fp.read(), defuse='nonlocal', lazy=True)

        with self.assertRaises(ElementTree.ParseError):
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

        nsmap = []
        for _, elem in resource._lazy_iterparse(self.col_xml_file, nsmap=nsmap):
            self.assertTrue(is_etree_element(elem))
            self.assertListEqual(
                nsmap, [('col', 'http://example.com/ns/collection'),
                        ('xsi', 'http://www.w3.org/2001/XMLSchema-instance')])

        resource._defuse = 'always'
        for _, elem in resource._lazy_iterparse(self.col_xml_file):
            self.assertTrue(is_etree_element(elem))

    def test_xml_resource__iterparse(self):
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
        self.assertEqual("cannot serialize a lazy XML resource", str(ctx.exception))

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

        resource._url = 'file:not-a-file'
        with self.assertRaises(XMLResourceError):
            resource.open()

        resource = XMLResource('<A/>')
        self.assertRaises(XMLResourceError, resource.open)

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
        try:
            self.assertTrue(callable(xml_file.read))
        finally:
            resource.close()

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(source=xml_file)
            resource.close()
            with self.assertRaises(XMLResourceError):
                resource.open()

        with open(self.vh_xml_file) as xml_file:
            resource = XMLResource(xml_file)

        with self.assertRaises(XMLResourceError):
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
        self.assertEqual(lazy_tags[-1], '{%s}schema' % XSD_NAMESPACE)
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

        # Note: Element change with lazy resource so compare only tags

        nsmap = []
        tags = [x.tag for x in resource.iter_depth(nsmap=nsmap)]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], '{%s}schema' % XSD_NAMESPACE)
        self.assertListEqual(
            nsmap, [('xs', 'http://www.w3.org/2001/XMLSchema'),
                    ('hfp', 'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty')])

        lazy_tags = [x.tag for x in lazy_resource.iter_depth()]
        self.assertEqual(len(lazy_tags), 156)
        self.assertEqual(lazy_tags[0], '{%s}annotation' % XSD_NAMESPACE)
        self.assertEqual(lazy_tags[-1], '{%s}element' % XSD_NAMESPACE)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=2)]
        self.assertListEqual(tags, lazy_tags)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=1)]
        self.assertEqual(len(lazy_tags), 156)

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=3)]
        self.assertEqual(len(lazy_tags), 157)
        self.assertEqual(tags[0], lazy_tags[-1])

        lazy_tags = [x.tag for x in lazy_resource.iter_depth(mode=4)]
        self.assertEqual(len(lazy_tags), 158)
        self.assertEqual(tags[0], lazy_tags[0])
        self.assertEqual(tags[0], lazy_tags[-1])

        with self.assertRaises(ValueError) as ctx:
            _ = [x.tag for x in lazy_resource.iter_depth(mode=5)]
        self.assertEqual("invalid argument mode=5", str(ctx.exception))

        source = StringIO('<a xmlns:tns0="http://example.com/ns0"><b1>'
                          '  <c1 xmlns:tns1="http://example.com/ns1"/>'
                          '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                          '</b1><b2><c3><d1/></c3></b2></a>')
        resource = XMLResource(source, lazy=3)

        nsmap = []
        ancestors = []
        self.assertIs(next(resource.iter_depth(nsmap=nsmap, ancestors=ancestors)),
                      resource.root[1][0][0])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0')])
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
        lazy_tags = [x.tag for x in lazy_resource.iterfind(path='.')]
        self.assertListEqual(tags, lazy_tags)

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
        nsmap = []
        self.assertIs(resource.find('*/c2', nsmap=nsmap), resource.root[0][1])
        self.assertListEqual(nsmap, [('tns2', 'http://example.com/ns2')])

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*/c2', nsmap=nsmap, ancestors=ancestors),
                      resource.root[0][1])
        self.assertListEqual(nsmap, [('tns2', 'http://example.com/ns2')])
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('.', nsmap=nsmap, ancestors=ancestors),
                      resource.root)
        self.assertListEqual(nsmap, [])
        self.assertListEqual(ancestors, [])

        nsmap = []
        ancestors = []
        self.assertIsNone(resource.find('b3', nsmap=nsmap, ancestors=ancestors))
        self.assertListEqual(nsmap, [])
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

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*/c2', nsmap=nsmap, ancestors=ancestors),
                      resource.root[0][1])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0'),
                                     ('tns2', 'http://example.com/ns2')])
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*/c3', nsmap=nsmap, ancestors=ancestors),
                      resource.root[1][0])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0')])
        self.assertListEqual(ancestors, [resource.root, resource.root[1]])

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*/c3/d1', nsmap=nsmap, ancestors=ancestors),
                      resource.root[1][0][0])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0')])
        self.assertListEqual(ancestors,
                             [resource.root, resource.root[1], resource.root[1][0]])

        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*', nsmap=nsmap, ancestors=ancestors),
                      resource.root[0])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0')])
        self.assertListEqual(ancestors, [resource.root])

        nsmap = []
        ancestors = []
        self.assertIsNone(resource.find('/b1', nsmap=nsmap, ancestors=ancestors))
        self.assertListEqual(nsmap, [])
        self.assertListEqual(ancestors, [])

        source.seek(0)
        resource = XMLResource(source, lazy=2)
        nsmap = []
        ancestors = []
        self.assertIs(resource.find('*/c2', nsmap=nsmap, ancestors=ancestors),
                      resource.root[0][1])
        self.assertListEqual(nsmap, [('tns0', 'http://example.com/ns0'),
                                     ('tns2', 'http://example.com/ns2')])
        self.assertListEqual(ancestors, [resource.root, resource.root[0]])

    def test_xml_resource_findall(self):
        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/></a>')
        resource = XMLResource(root)

        self.assertListEqual(resource.findall('*/*'), root[0][:])
        self.assertListEqual(resource.findall('*/c3'), [])

    def test_xml_resource_nsmap_tracking(self):
        xsd_file = casepath('examples/collection/collection4.xsd')
        resource = XMLResource(xsd_file)
        root = resource.root
        nsmap = []

        for elem in resource.iter(nsmap=nsmap):
            if elem is root[2][0] or elem in root[2][0]:
                self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                               '': 'http://www.w3.org/2001/XMLSchema'})
            else:
                self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                               '': 'http://example.com/ns/collection'})

        nsmap.clear()
        resource._nsmap.clear()
        resource._nsmap[resource._root] = []

        for _ in resource.iter(nsmap=nsmap):
            self.assertEqual(nsmap, [])

        nsmap.clear()
        if lxml_etree is not None:
            tree = lxml_etree.parse(xsd_file)
            resource = XMLResource(tree)
            root = resource.root

            for elem in resource.iter(nsmap=nsmap):
                if callable(elem.tag):
                    continue
                if elem is root[2][0] or elem in root[2][0]:
                    self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                                   '': 'http://www.w3.org/2001/XMLSchema'})
                else:
                    self.assertEqual(dict(nsmap), {'xs': 'http://www.w3.org/2001/XMLSchema',
                                                   '': 'http://example.com/ns/collection'})

        nsmap = {}
        resource = XMLResource(xsd_file, lazy=True)
        root = elem = resource.root
        for elem in resource.iter(nsmap=nsmap):
            try:
                if elem is resource.root[2][0] or elem in resource.root[2][0]:
                    self.assertEqual(nsmap['default'], 'http://www.w3.org/2001/XMLSchema')
                self.assertEqual(nsmap[''], 'http://example.com/ns/collection')
            except IndexError:
                self.assertEqual(nsmap[''], 'http://example.com/ns/collection')

        self.assertIs(elem, resource.root)
        self.assertIsNot(root, resource.root)

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

        locations = resource.get_locations([('ns', 'other.xsd')])
        self.assertEqual(len(locations), 2)
        self.check_url(locations[0][1], os.path.join(self.col_dir, 'other.xsd'))
        self.check_url(locations[1][1], normalize_url(self.col_xsd_file))

        source = StringIO('<a xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                          '   xsi:schemaLocation="http://example.com/ns1 /loc1"><b1>'
                          '  <c1 xsi:schemaLocation="http://example.com/ns2 /loc2"/>'
                          '  <c2 xmlns:tns2="http://example.com/ns2" x="2"/>'
                          '</b1></a>')

        resource = XMLResource(source)
        locations = resource.get_locations()
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

        self.assertEqual(col_xsd_resource.url, url)
        self.assertIsNone(col_xsd_resource.filepath)

        self.assertEqual(col_xsd_resource.namespace, XSD_NAMESPACE)
        self.assertIsNone(col_xsd_resource.seek(0))
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

        with self.assertRaises(XMLResourceError) as ctx:
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
        self.assertEqual("cannot create the parent map of a lazy XML resource",
                         str(ctx.exception))

    def test_get_nsmap(self):
        source = '<a xmlns="uri1"><b1 xmlns:x="uri2"><c1/><c2/></b1><b2 xmlns="uri3"/></a>'
        alien_elem = ElementTree.XML('<a/>')

        root = ElementTree.XML(source)
        resource = XMLResource(root)

        self.assertListEqual(resource.get_nsmap(root), [])
        self.assertListEqual(resource.get_nsmap(root[1]), [])
        self.assertListEqual(resource.get_nsmap(alien_elem), [])

        if lxml_etree is not None:
            root = lxml_etree.XML(source)
            resource = XMLResource(root)

            self.assertListEqual(resource.get_nsmap(root), [('', 'uri1')])
            self.assertListEqual(resource.get_nsmap(root[0]), [('x', 'uri2'), ('', 'uri1')])
            self.assertListEqual(resource.get_nsmap(root[1]), [('', 'uri3')])
            self.assertListEqual(resource.get_nsmap(alien_elem), [])

        resource = XMLResource(source)
        root = resource.root

        self.assertListEqual(resource.get_nsmap(root), [('', 'uri1')])
        self.assertListEqual(resource.get_nsmap(root[0]), [('', 'uri1'), ('x', 'uri2')])
        self.assertListEqual(resource.get_nsmap(root[1]), [('', 'uri1'), ('', 'uri3')])
        self.assertListEqual(resource.get_nsmap(alien_elem), [])

        resource = XMLResource(StringIO(source), lazy=True)
        root = resource.root
        self.assertTrue(resource.is_lazy())

        self.assertListEqual(resource.get_nsmap(root), [('', 'uri1')])
        self.assertListEqual(resource.get_nsmap(root[0]), [])
        self.assertListEqual(resource.get_nsmap(root[1]), [])
        self.assertListEqual(resource.get_nsmap(alien_elem), [])

    def test_xml_subresource(self):
        resource = XMLResource(self.vh_xml_file, lazy=True)
        with self.assertRaises(XMLResourceError) as ctx:
            resource.subresource(resource.root)
        self.assertEqual("cannot create a subresource from a lazy XML resource",
                         str(ctx.exception))

        resource = XMLResource(self.vh_xml_file)
        root = resource.root
        subresource = resource.subresource(root[0])
        self.assertIs(subresource.root, resource.root[0])

        with self.assertRaises(XMLResourceError) as ctx:
            resource.subresource(None)
        self.assertEqual("None is not an element or the XML resource tree", str(ctx.exception))

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


if __name__ == '__main__':
    header_template = "Test xmlschema's XML resources with Python {} on platform {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
