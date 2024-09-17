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
import unittest
import sys
import os
import pathlib
import platform

from urllib.parse import urlsplit
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
from unittest.mock import patch, MagicMock

import xmlschema.locations
from xmlschema.locations import LocationPath, LocationPosixPath, LocationWindowsPath, \
    is_url, is_local_url, is_remote_url, url_path_is_file, is_unc_path, is_drive_path, \
    normalize_url, normalize_locations, match_location, is_encoded_url, is_safe_url, \
    encode_url, decode_url, get_uri_path, get_uri, DRIVE_LETTERS

TEST_CASES_DIR = str(pathlib.Path(__file__).absolute().parent.joinpath('test_cases'))

DRIVE_REGEX = '(/[a-zA-Z]:|)' if platform.system() == 'Windows' else ''

XML_WITH_NAMESPACES = '<pfa:root xmlns:pfa="http://xmlschema.test/nsa">\n' \
                      '  <pfb:elem xmlns:pfb="http://xmlschema.test/nsb"/>\n' \
                      '</pfa:root>'

URL_CASES = (
    'file:///c:/Downloads/file.xsd',
    'file:///tmp/xmlschema/schemas/VC/XMLSchema-versioning.xsd',
    'file:///tmp/xmlschema/schemas/XSD_1.1/xsd11-extra.xsd',
    'issue #000.xml', 'dev/XMLSCHEMA/test.xsd',
    'file:///tmp/xmlschema/schemas/XSI/XMLSchema-instance_minimal.xsd',
    'vehicles.xsd', 'file://filer01/MY_HOME/',
    '//anaconda/envs/testenv/lib/python3.6/site-packages/xmlschema/validators/schemas/',
    'z:\\Dir-1.0\\Dir-2_0\\', 'https://host/path?name=2&id=', 'data.xml',
    'alpha', 'other.xsd?id=2', '\\\\filer01\\MY_HOME\\', '//root/dir1',
    '/tmp/xmlschema/schemas/XSD_1.1/xsd11-extra.xsd',
    '/tmp/xmlschema/schemas/VC/XMLSchema-versioning.xsd',
    '\\\\host\\share\\file.xsd', 'https://example.com/xsd/other_schema.xsd',
    '/tmp/tests/test_cases/examples/collection/collection.xml', 'XMLSchema.xsd',
    'file:///c:/Windows/unknown', 'k:\\Dir3\\schema.xsd',
    '/tmp/tests/test_cases/examples/collection', 'file:other.xsd',
    'issue%20%23000.xml', '\\\\filer01\\MY_HOME\\dev\\XMLSCHEMA\\test.xsd',
    'http://site/base', 'dir2/schema.xsd', '//root/dir1/schema.xsd',
    'file:///tmp/xmlschema/schemas/XML/xml_minimal.xsd',
    'https://site/base', 'file:///home#attribute',
    '/dir1/dir2/issue%20%23002', '////root/dir1/schema.xsd',
    '/tmp/xmlschema/schemas/XSD_1.1/XMLSchema.xsd',
    '/tmp/xmlschema/schemas/XML/xml_minimal.xsd',
    '/tmp/xmlschema/schemas/XSD_1.0/XMLSchema.xsd',
    'file:///home/', '////root/dir1', '//root/dir1/', 'file:///home', 'other.xsd',
    'file:///tmp/tests/test_cases/examples/collection/collection.xml',
    'file://host/home/', 'dummy path.xsd', 'other.xsd#element',
    'z:\\Dir_1_0\\Dir2-0\\schemas/XSD_1.0/XMLSchema.xsd',
    'd:/a/xmlschema/xmlschema/tests/test_cases/examples/',
    'https://xmlschema.test/schema 2/test.xsd?name=2 id=3',
    'xsd1.0/schema.xsd', '/home', 'schema.xsd',
    'dev\\XMLSCHEMA\\test.xsd', '../dir1/./dir2', 'beta',
    '/tmp/xmlschema/schemas/XSI/XMLSchema-instance_minimal.xsd',
    'file:///dir1/dir2/', 'file:///dir1/dir2/issue%20001', '/root/dir1/schema.xsd',
    'file:///tmp/xmlschema/schemas/XSD_1.1', '/path/schema 2/test.xsd?name=2 id=3',
    'file:////filer01/MY_HOME/', 'file:///home?name=2&id=', 'http://example.com/beta',
    '/home/user', 'file:///\\k:\\Dir A\\schema.xsd'
)


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


class TestLocations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')

    def check_url(self, url, expected):
        url_parts = urlsplit(url)

        if urlsplit(expected).scheme in DRIVE_LETTERS:
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

    def test_urlsplit(self):
        url = "https://xmlschema.test/schema/test.xsd"
        self.assertEqual(
            urlsplit(url), ("https", "xmlschema.test", "/schema/test.xsd", '', '')
        )

        url = "https://xmlschema.test/xs:schema/test.xsd"
        self.assertEqual(
            urlsplit(url), ("https", "xmlschema.test", "/xs:schema/test.xsd", '', '')
        )

        url = "https://xmlschema.test/schema/test.xsd#xs:element"
        self.assertEqual(
            urlsplit(url), ("https", "xmlschema.test", "/schema/test.xsd", '', 'xs:element')
        )

        url = "https://xmlschema.test@username:password/schema/test.xsd"
        self.assertEqual(
            urlsplit(url),
            ("https", "xmlschema.test@username:password", "/schema/test.xsd", '', '')
        )

        url = "https://xmlschema.test/schema/test.xsd?id=10"
        self.assertEqual(
            urlsplit(url), ("https", "xmlschema.test", "/schema/test.xsd", 'id=10', '')
        )

    def test_path_from_uri(self):
        if platform.system() == 'Windows':
            default_class = LocationWindowsPath
        else:
            default_class = LocationPosixPath

        with self.assertRaises(ValueError) as ec:
            LocationPath.from_uri('')
        self.assertEqual(str(ec.exception), 'Empty URI provided!')

        path = LocationPath.from_uri('https://example.com/names/?name=foo')
        self.assertIsInstance(path, LocationPosixPath)
        self.assertEqual(str(path), '/names')

        path = LocationPosixPath.from_uri('file:///home/foo/names/?name=foo')
        self.assertIsInstance(path, default_class)
        self.assertEqual(str(path).replace('\\', '/'), '/home/foo/names')

        path = LocationPosixPath.from_uri('file:///home/foo/names#foo')
        self.assertIsInstance(path, default_class)
        self.assertEqual(str(path).replace('\\', '/'), '/home/foo/names')

        path = LocationPath.from_uri('file:///home\\foo\\names#foo')
        self.assertTrue(path.as_posix().endswith('/home/foo/names'))
        self.assertIsInstance(path, LocationWindowsPath)

        path = LocationPosixPath.from_uri('file:///c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)

        path = LocationPath.from_uri('file:///c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        path = LocationPosixPath.from_uri('file:c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)

        path = LocationPath.from_uri('file:c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        with self.assertRaises(ValueError) as ec:
            LocationPath.from_uri('file://c:/home/foo/names/')
        self.assertEqual(str(ec.exception), "Invalid URI 'file://c:/home/foo/names/'")

    def test_get_uri(self):
        for url in URL_CASES:
            self.assertEqual(get_uri(*urlsplit(url)), url)

        url = 'D:/a/xmlschema/xmlschema/tests/test_cases/examples/'
        self.assertNotEqual(get_uri(*urlsplit(url)), url)

    def test_get_uri_path(self):
        self.assertEqual(get_uri_path('https', 'host', 'path', 'id=7', 'types'),
                         '//host/path')
        self.assertEqual(get_uri_path('k', '', 'path/file', 'id=7', 'types'),
                         'path/file')
        self.assertEqual(get_uri_path('file', '', 'path/file', 'id=7', 'types'),
                         'path/file')

    def test_urn_uri(self):
        with self.assertRaises(ValueError) as ec:
            LocationPath.from_uri("urn:ietf:rfc:2648")
        self.assertIn("Can't create", str(ec.exception))

        self.assertEqual(get_uri(scheme='urn', path='ietf:rfc:2648'), 'urn:ietf:rfc:2648')
        self.assertEqual(get_uri_path(scheme='urn', path='ietf:rfc:2648'), 'ietf:rfc:2648')

        with self.assertRaises(ValueError) as ec:
            get_uri_path(get_uri_path(scheme='urn', path='ietf:rfc:2648:'))
        self.assertIn("Invalid URN path ", str(ec.exception))

        for arg in ('authority', 'query', 'fragment'):
            with self.assertRaises(ValueError) as ec:
                get_uri_path(get_uri_path(scheme='urn', path='ietf:rfc:2648:', **{arg: 'foo'}))

            self.assertEqual(
                str(ec.exception), "An URN can have only scheme and path components"
            )

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
        cwd_url = f'file://{cwd}/' if cwd.startswith('/') else f'file:///{cwd}/'

        self.check_url(normalize_url('other.xsd', keep_relative=True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd', keep_relative=True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd'), cwd_url + 'other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'https://site/base', True), 'file:other.xsd')
        self.check_url(normalize_url('file:other.xsd', 'http://site/base'), cwd_url + 'other.xsd')

        self.check_url(normalize_url('dummy path.xsd'), cwd_url + 'dummy%20path.xsd')
        self.check_url(normalize_url('dummy path.xsd', 'http://site/base'),
                       'http://site/base/dummy%20path.xsd')

        self.assertEqual(normalize_url('dummy path.xsd', 'file://host/home/'),
                         'file:////host/home/dummy%20path.xsd')

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

        base_url = 'D:/a/xmlschema/xmlschema/tests/test_cases/examples/'
        self.assertEqual(normalize_url('vehicles.xsd', base_url),
                         f'file:///{base_url}vehicles.xsd')

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

        # Same UNC path as URI with the host inserted in path.
        url_host_in_path = url.replace('file://', 'file:////')
        self.assertEqual(url_host_in_path, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        self.assertEqual(normalize_url(unc_path), url_host_in_path)

        with patch.object(os, 'name', 'nt'):
            self.assertEqual(os.name, 'nt')
            path = PurePath(unc_path)
            self.assertIs(path.__class__, PureWindowsPath)
            self.assertEqual(path.as_uri(), url)

            self.assertEqual(xmlschema.locations.os.name, 'nt')
            path = LocationPath(unc_path)
            self.assertIs(path.__class__, LocationWindowsPath)
            self.assertEqual(path.as_uri(), url_host_in_path)
            self.assertEqual(normalize_url(unc_path), url_host_in_path)

        with patch.object(os, 'name', 'posix'):
            self.assertEqual(os.name, 'posix')
            path = PurePath(unc_path)
            self.assertIs(path.__class__, PurePosixPath)
            self.assertEqual(str(path), unc_path)
            self.assertRaises(ValueError, path.as_uri)  # Not recognized as UNC path

            self.assertEqual(xmlschema.locations.os.name, 'posix')
            path = LocationPath(unc_path)
            self.assertIs(path.__class__, LocationPosixPath)
            self.assertEqual(str(path), unc_path)
            self.assertNotEqual(path.as_uri(), url)
            self.assertEqual(normalize_url(unc_path), url_host_in_path)

    @unittest.skipIf(platform.system() != 'Windows', "Run only on Windows systems")
    def test_normalize_url_with_base_unc_path_on_windows(self,):
        base_unc_path = '\\\\filer01\\MY_HOME\\'
        base_url = PureWindowsPath(base_unc_path).as_uri()
        self.assertEqual(str(PureWindowsPath(base_unc_path)), base_unc_path)
        self.assertEqual(base_url, 'file://filer01/MY_HOME/')

        # Same UNC path as URI with the host inserted in path
        base_url_host_in_path = base_url.replace('file://', 'file:////')
        self.assertEqual(base_url_host_in_path, 'file:////filer01/MY_HOME/')

        self.assertEqual(normalize_url(base_unc_path), base_url_host_in_path)

        self.assertEqual(os.name, 'nt')
        path = PurePath('dir/file')
        self.assertIs(path.__class__, PureWindowsPath)

        url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_unc_path)
        self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url)
        self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url_host_in_path)
        if is_unc_path('////filer01/MY_HOME/'):
            self.assertEqual(url, 'file://////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')
        else:
            self.assertRegex(
                url, f'file://{DRIVE_REGEX}/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd'
            )

    @unittest.skipIf(platform.system() == 'Windows', "Skip on Windows systems")
    def test_normalize_url_with_base_unc_path_on_others(self,):
        base_unc_path = '\\\\filer01\\MY_HOME\\'
        base_url = PureWindowsPath(base_unc_path).as_uri()
        self.assertEqual(str(PureWindowsPath(base_unc_path)), base_unc_path)
        self.assertEqual(base_url, 'file://filer01/MY_HOME/')

        # Same UNC path as URI with the host inserted in path
        base_url_host_in_path = base_url.replace('file://', 'file:////')
        self.assertEqual(base_url_host_in_path, 'file:////filer01/MY_HOME/')

        self.assertEqual(normalize_url(base_unc_path), base_url_host_in_path)

        url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_unc_path)
        self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url=base_url)
        self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

        url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url=base_url_host_in_path)
        if is_unc_path('////'):
            self.assertEqual(url, 'file://////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')
        else:
            self.assertRegex(
                url, f'file://{DRIVE_REGEX}/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd'
            )

        with patch.object(os, 'name', 'nt'):
            self.assertEqual(os.name, 'nt')
            path = PurePath('dir/file')
            self.assertIs(path.__class__, PureWindowsPath)

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_unc_path)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url)
            self.assertEqual(url, 'file:////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')

            url = normalize_url(r'dev\XMLSCHEMA\test.xsd', base_url=base_url_host_in_path)
            if is_unc_path('////filer01/MY_HOME/'):
                self.assertEqual(url, 'file://////filer01/MY_HOME/dev/XMLSCHEMA/test.xsd')
            else:
                self.assertRegex(
                    url, f'file://{DRIVE_REGEX}/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd'
                )

    def test_normalize_url_slashes(self):
        # Issue #116
        url = '//anaconda/envs/testenv/lib/python3.6/site-packages/xmlschema/validators/schemas/'
        if os.name == 'posix':
            normalize_url(url)
            self.assertEqual(normalize_url(url), pathlib.PurePath(url).as_uri())
        else:
            # On Windows // is interpreted as a network share UNC path
            self.assertEqual(os.name, 'nt')
            self.assertEqual(normalize_url(url),
                             pathlib.PurePath(url).as_uri().replace('file://', 'file:////'))

        self.assertRegex(normalize_url('/root/dir1/schema.xsd'),
                         f'file://{DRIVE_REGEX}/root/dir1/schema.xsd')

        if is_unc_path('////root/dir1/schema.xsd'):
            self.assertRegex(normalize_url('////root/dir1/schema.xsd'),
                             f'file://{DRIVE_REGEX}////root/dir1/schema.xsd')
            self.assertRegex(normalize_url('dir2/schema.xsd', '////root/dir1'),
                             f'file://{DRIVE_REGEX}////root/dir1/dir2/schema.xsd')
        else:
            # If the Python release is not capable to detect the UNC path
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
        self.assertRegex(url, f'file://{DRIVE_REGEX}/dir1/dir2/issue%20')

        url = normalize_url('issue%20%23000.xml', 'file:///dir1/dir2/')
        self.assertRegex(url, f'file://{DRIVE_REGEX}/dir1/dir2/issue%20%23000.xml')

        url = normalize_url('data.xml', 'file:///dir1/dir2/issue%20001')
        self.assertRegex(url, f'file://{DRIVE_REGEX}/dir1/dir2/issue%20001/data.xml')

        url = normalize_url('data.xml', '/dir1/dir2/issue%20%23002')
        self.assertRegex(url, f'{DRIVE_REGEX}/dir1/dir2/issue%20%23002/data.xml')

    def test_normalize_url_with_query_part(self):
        url = "https://xmlschema.test/schema 2/test.xsd?name=2 id=3"
        self.assertEqual(
            normalize_url(url),
            "https://xmlschema.test/schema%202/test.xsd?name=2%20id=3"
        )

        url = "https://xmlschema.test/schema 2/test.xsd?name=2 id=3"
        self.assertEqual(
            normalize_url(url, method='html'),
            "https://xmlschema.test/schema%202/test.xsd?name=2+id=3"
        )

        url = "/path/schema 2/test.xsd?name=2 id=3"
        self.assertRegex(
            normalize_url(url),
            f'file://{DRIVE_REGEX}/path/schema%202/test.xsd'
        )

        self.assertRegex(
            normalize_url('other.xsd?id=2', 'file:///home?name=2&id='),
            f'file://{DRIVE_REGEX}/home/other.xsd'
        )
        self.assertRegex(
            normalize_url('other.xsd#element', 'file:///home#attribute'),
            f'file://{DRIVE_REGEX}/home/other.xsd'
        )

        self.check_url(normalize_url('other.xsd?id=2', 'https://host/path?name=2&id='),
                       'https://host/path/other.xsd?id=2')
        self.check_url(normalize_url('other.xsd#element', 'https://host/path?name=2&id='),
                       'https://host/path/other.xsd#element')

    def test_normalize_url_with_local_part(self):
        # https://datatracker.ietf.org/doc/html/rfc8089#appendix-E.2

        url = "file:c:/path/to/file"
        self.assertIn(urlsplit(url).geturl(), (url, 'file:///c:/path/to/file'))
        self.assertIn(normalize_url(url), (url, 'file:///c:/path/to/file'))

        url = "file:///c:/path/to/file"
        self.assertEqual(urlsplit(url).geturl(), url)
        self.assertEqual(normalize_url(url), url)

    @unittest.skip
    def test_normalize_url_with_base_url_with_local_part(self):

        base_url = "file:///D:/a/xmlschema/xmlschema/filer01/MY_HOME"
        url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url)
        self.assertEqual(
            url, "file:///D:/a/xmlschema/xmlschema/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd"
        )

        base_url = "file:D:/a/xmlschema/xmlschema/filer01/MY_HOME"
        url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url)
        self.assertEqual(
            url, "file:///D:/a/xmlschema/xmlschema/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd"
        )

        base_url = "D:\\a\\xmlschema\\xmlschema/\\/filer01/MY_HOME"
        url = normalize_url(r'dev/XMLSCHEMA/test.xsd', base_url)
        self.assertEqual(
            url, "file:///D:/a/xmlschema/xmlschema/filer01/MY_HOME/dev/XMLSCHEMA/test.xsd"
        )

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

    def test_is_unc_path_function(self):
        self.assertFalse(is_unc_path(''))
        self.assertFalse(is_unc_path('foo'))
        self.assertFalse(is_unc_path('foo\\bar'))
        self.assertFalse(is_unc_path('foo/bar'))
        self.assertFalse(is_unc_path('\\'))
        self.assertFalse(is_unc_path('/'))
        self.assertFalse(is_unc_path('\\foo\\bar'))
        self.assertFalse(is_unc_path('/foo/bar'))
        self.assertFalse(is_unc_path('c:foo/bar'))
        self.assertFalse(is_unc_path('c:\\foo\\bar'))
        self.assertFalse(is_unc_path('c:/foo/bar'))

        self.assertTrue(is_unc_path('/\\host/share/path'))
        self.assertTrue(is_unc_path('\\/host\\share/path'))
        self.assertTrue(is_unc_path('//host/share/dir/file'))
        self.assertTrue(is_unc_path('//?/UNC/server/share/dir'))

        if sys.version_info >= (3, 12, 5):
            # Generally these tests fail with older Python releases, due to
            # bug/limitation of old versions of ntpath.splitdrive()
            self.assertTrue(is_unc_path('//'))
            self.assertTrue(is_unc_path('\\\\'))
            self.assertTrue(is_unc_path('\\\\host\\share\\foo\\bar'))
            self.assertTrue(is_unc_path('\\\\?\\UNC\\server\\share\\dir'))
            self.assertTrue(is_unc_path('////'))
            self.assertTrue(is_unc_path('////host/share/schema.xsd'))

    def test_is_drive_path_function(self):
        self.assertFalse(is_drive_path(''))
        self.assertFalse(is_drive_path('foo'))
        self.assertFalse(is_drive_path('foo\\bar'))
        self.assertFalse(is_drive_path('foo/bar'))
        self.assertFalse(is_drive_path('\\'))
        self.assertFalse(is_drive_path('/'))
        self.assertFalse(is_drive_path('\\foo\\bar'))
        self.assertFalse(is_drive_path('/foo/bar'))

        self.assertTrue(is_drive_path('c:foo/bar'))
        self.assertTrue(is_drive_path('c:\\foo\\bar'))
        self.assertTrue(is_drive_path('c:/foo/bar'))
        self.assertFalse(is_drive_path('/c:foo/bar'))
        self.assertFalse(is_drive_path('\\c:\\foo\\bar'))
        self.assertFalse(is_drive_path('/c:/foo/bar'))

        self.assertFalse(is_drive_path('/\\host/share/path'))
        self.assertFalse(is_drive_path('\\/host\\share/path'))
        self.assertFalse(is_drive_path('//host/share/dir/file'))
        self.assertFalse(is_drive_path('//?/UNC/server/share/dir'))

    def test_is_encoded_url(self):
        self.assertFalse(is_encoded_url("https://xmlschema.test/schema/test.xsd"))
        self.assertTrue(is_encoded_url("https://xmlschema.test/schema/issue%20%231999.xsd"))
        self.assertFalse(is_encoded_url("a b c"))
        self.assertFalse(is_encoded_url("a+b+c"))
        self.assertFalse(is_encoded_url("a b+c"))

    def test_is_safe_url(self):
        self.assertTrue(is_safe_url("https://xmlschema.test/schema/test.xsd"))
        self.assertFalse(is_safe_url("https://xmlschema.test/schema 2/test.xsd"))
        self.assertTrue(is_safe_url("https://xmlschema.test/schema/test.xsd#elements"))
        self.assertTrue(is_safe_url("https://xmlschema.test/schema/test.xsd?id=2"))
        self.assertFalse(is_safe_url("https://xmlschema.test/schema/test.xsd?id=2 name=foo"))

    def test_encode_and_decode_url(self):
        url = "https://xmlschema.test/schema/test.xsd"
        self.assertEqual(encode_url(url), url)
        self.assertEqual(decode_url(encode_url(url)), url)

        url = "https://xmlschema.test/schema 2/test.xsd"
        self.assertEqual(encode_url(url), "https://xmlschema.test/schema%202/test.xsd")
        self.assertEqual(decode_url(encode_url(url)), url)

        url = "https://xmlschema.test@u:p/xs:schema@2/test.xsd"
        self.assertEqual(encode_url(url), "https://xmlschema.test@u:p/xs%3Aschema%402/test.xsd")
        self.assertEqual(decode_url(encode_url(url)), url)

        url = "https://xmlschema.test/schema 2/test.xsd?name=2 id=3"
        self.assertEqual(
            encode_url(url), "https://xmlschema.test/schema%202/test.xsd?name=2%20id=3")
        self.assertEqual(decode_url(encode_url(url)), url)

        self.assertEqual(encode_url(url, method='html'),
                         "https://xmlschema.test/schema%202/test.xsd?name=2+id=3")
        self.assertEqual(decode_url(encode_url(url, method='html'), method='html'), url)
        self.assertEqual(decode_url(encode_url(url), method='html'), url)
        self.assertNotEqual(decode_url(encode_url(url, method='html')), url)

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

    def test_match_location(self):
        self.assertIsNone(match_location('schema.xsd', []))

        locations = ['schema1.xsd', 'schema']
        self.assertIsNone(match_location('schema.xsd', locations))

        locations = ['schema.xsd', 'schema']
        self.assertEqual(match_location('schema.xsd', locations), 'schema.xsd')

        locations = ['schema', 'schema.xsd']
        self.assertEqual(match_location('schema.xsd', locations), 'schema.xsd')

        locations = ['../schema.xsd', 'a/schema.xsd']
        self.assertIsNone(match_location('schema.xsd', locations))

        locations = ['../schema.xsd', 'b/schema.xsd']
        self.assertEqual(match_location('a/schema.xsd', locations), '../schema.xsd')

        locations = ['../schema.xsd', 'a/schema.xsd']
        self.assertEqual(match_location('a/schema.xsd', locations), 'a/schema.xsd')

        locations = ['../schema.xsd', './a/schema.xsd']
        self.assertEqual(match_location('a/schema.xsd', locations), './a/schema.xsd')

        locations = ['/../schema.xsd', '/a/schema.xsd']
        self.assertIsNone(match_location('a/schema.xsd', locations))
        self.assertEqual(match_location('/a/schema.xsd', locations), '/a/schema.xsd')
        self.assertEqual(match_location('/schema.xsd', locations), '/../schema.xsd')


if __name__ == '__main__':
    header_template = "Test xmlschema locations.py module with Python {} on platform {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
