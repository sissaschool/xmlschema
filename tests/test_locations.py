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
import os
import pathlib
import platform

from urllib.parse import urlsplit, uses_relative
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
from unittest.mock import patch, MagicMock

import xmlschema.locations
from xmlschema.locations import LocationPath, LocationPosixPath, LocationWindowsPath, \
    is_url, is_local_url, is_remote_url, url_path_is_file, normalize_url, \
    normalize_locations, match_location

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


class TestLocations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
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
        with self.assertRaises(ValueError) as ec:
            LocationPath.from_uri('')
        self.assertEqual(str(ec.exception), 'Empty URI provided!')

        path = LocationPath.from_uri('https://example.com/names/?name=foo')
        self.assertIsInstance(path, LocationPosixPath)
        self.assertEqual(str(path), '/names')

        path = LocationPosixPath.from_uri('file:///home/foo/names/?name=foo')
        self.assertIsInstance(path, LocationPosixPath)
        self.assertEqual(str(path), '/home/foo/names')

        path = LocationPosixPath.from_uri('file:///home/foo/names#foo')
        self.assertIsInstance(path, LocationPosixPath)
        self.assertEqual(str(path), '/home/foo/names')

        path = LocationPosixPath.from_uri('file:///home\\foo\\names#foo')
        self.assertIsInstance(path, LocationWindowsPath)
        self.assertTrue(path.as_posix().endswith('/home/foo/names'))

        path = LocationPosixPath.from_uri('file:///c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        path = LocationPosixPath.from_uri('file:c:/home/foo/names/')
        self.assertIsInstance(path, LocationWindowsPath)
        self.assertEqual(str(path), r'c:\home\foo\names')
        self.assertEqual(path.as_uri(), 'file:///c:/home/foo/names')

        with self.assertRaises(ValueError) as ec:
            LocationPath.from_uri('file://c:/home/foo/names/')
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
