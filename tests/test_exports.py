#!/usr/bin/env python
#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import filecmp
import glob
import os
import re
import pathlib
import platform
import tempfile
import warnings

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.exports import download_schemas
from xmlschema.testing import SKIP_REMOTE_TESTS, XMLSchemaTestCase, run_xmlschema_tests


class TestExports(XMLSchemaTestCase):
    cases_dir = pathlib.Path(__file__).absolute().parent.joinpath('test_cases')

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = cls.casepath('examples/vehicles')
        cls.vh_xsd_file = vh_xsd_file = cls.casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = cls.casepath('examples/vehicles/vehicles.xml')
        cls.vh_schema = cls.schema_class(vh_xsd_file)

    def test_export_errors__issue_187(self):
        with self.assertRaises(ValueError) as ctx:
            self.vh_schema.export(target=self.vh_dir)

        self.assertIn("target directory", str(ctx.exception))
        self.assertIn("is not empty", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self.vh_schema.export(target=self.vh_xsd_file)

        self.assertIn("target", str(ctx.exception))
        self.assertIn("is not a directory", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self.vh_schema.export(target=self.vh_xsd_file + '/target')

        self.assertIn("target parent", str(ctx.exception))
        self.assertIn("is not a directory", str(ctx.exception))

        with tempfile.TemporaryDirectory() as dirname:
            with self.assertRaises(ValueError) as ctx:
                self.vh_schema.export(target=dirname + 'subdir/target')

            self.assertIn("target parent directory", str(ctx.exception))
            self.assertIn("does not exist", str(ctx.exception))

    def test_export_same_directory__issue_187(self):
        with tempfile.TemporaryDirectory() as dirname:
            self.vh_schema.export(target=dirname)

            for filename in os.listdir(dirname):
                with pathlib.Path(dirname).joinpath(filename).open() as fp:
                    exported_schema = fp.read()
                with pathlib.Path(self.vh_dir).joinpath(filename).open() as fp:
                    original_schema = fp.read()

                if platform.system() == 'Windows':
                    exported_schema = re.sub(r'\s+', '', exported_schema)
                    original_schema = re.sub(r'\s+', '', original_schema)

                self.assertEqual(exported_schema, original_schema)

        self.assertFalse(os.path.isdir(dirname))

    def test_export_another_directory__issue_187(self):
        vh_schema_file = self.casepath('issues/issue_187/issue_187_1.xsd')
        vh_schema = self.schema_class(vh_schema_file)

        with tempfile.TemporaryDirectory() as dirname:
            vh_schema.export(target=dirname)

            path = pathlib.Path(dirname).joinpath('examples/vehicles/*.xsd')
            for filename in glob.iglob(pathname=str(path)):
                with pathlib.Path(dirname).joinpath(filename).open() as fp:
                    exported_schema = fp.read()

                basename = os.path.basename(filename)
                with pathlib.Path(self.vh_dir).joinpath(basename).open() as fp:
                    original_schema = fp.read()

                if platform.system() == 'Windows':
                    exported_schema = re.sub(r'\s+', '', exported_schema)
                    original_schema = re.sub(r'\s+', '', original_schema)

                self.assertEqual(exported_schema, original_schema)

            with pathlib.Path(dirname).joinpath('issue_187_1.xsd').open() as fp:
                exported_schema = fp.read()
            with open(vh_schema_file) as fp:
                original_schema = fp.read()

            if platform.system() == 'Windows':
                exported_schema = re.sub(r'\s+', '', exported_schema)
                original_schema = re.sub(r'\s+', '', original_schema)

            self.assertNotEqual(exported_schema, original_schema)

            if platform.system() != 'Windows':
                repl = str(pathlib.Path('file').joinpath(str(self.cases_dir).lstrip('/')))
                self.assertEqual(
                    exported_schema,
                    original_schema.replace('../..', repl)
                )

            schema_file = pathlib.Path(dirname).joinpath('issue_187_1.xsd')
            schema = self.schema_class(schema_file)
            ns_schemas = schema.maps.namespaces['http://example.com/vehicles']

            self.assertEqual(len(ns_schemas), 4)
            self.assertEqual(ns_schemas[0].name, 'issue_187_1.xsd')
            self.assertEqual(ns_schemas[1].name, 'cars.xsd')
            self.assertEqual(ns_schemas[2].name, 'types.xsd')
            self.assertEqual(ns_schemas[3].name, 'bikes.xsd')

        self.assertFalse(os.path.isdir(dirname))

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_export_remote__issue_187(self):
        vh_schema_file = self.casepath('issues/issue_187/issue_187_2.xsd')
        vh_schema = self.schema_class(vh_schema_file)

        with tempfile.TemporaryDirectory() as dirname:
            vh_schema.export(target=dirname)

            with pathlib.Path(dirname).joinpath('issue_187_2.xsd').open() as fp:
                exported_schema = fp.read()
            with open(vh_schema_file) as fp:
                original_schema = fp.read()

            if platform.system() == 'Windows':
                exported_schema = re.sub(r'\s+', '', exported_schema)
                original_schema = re.sub(r'\s+', '', original_schema)

            self.assertEqual(exported_schema, original_schema)

        self.assertFalse(os.path.isdir(dirname))

        with tempfile.TemporaryDirectory() as dirname:
            vh_schema.export(target=dirname, save_remote=True)
            path = pathlib.Path(dirname).joinpath('brunato/xmlschema/master/tests/test_cases/'
                                                  'examples/vehicles/*.xsd')

            for filename in glob.iglob(pathname=str(path)):
                with pathlib.Path(dirname).joinpath(filename).open() as fp:
                    exported_schema = fp.read()

                basename = os.path.basename(filename)
                with pathlib.Path(self.vh_dir).joinpath(basename).open() as fp:
                    original_schema = fp.read()
                self.assertEqual(exported_schema, original_schema)

            with pathlib.Path(dirname).joinpath('issue_187_2.xsd').open() as fp:
                exported_schema = fp.read()
            with open(vh_schema_file) as fp:
                original_schema = fp.read()

            if platform.system() == 'Windows':
                exported_schema = re.sub(r'\s+', '', exported_schema)
                original_schema = re.sub(r'\s+', '', original_schema)

            self.assertNotEqual(exported_schema, original_schema)
            self.assertNotIn('https://', exported_schema)
            self.assertEqual(
                exported_schema,
                original_schema.replace('https://raw.githubusercontent.com',
                                        'https/raw.githubusercontent.com')
            )

            schema_file = pathlib.Path(dirname).joinpath('issue_187_2.xsd')
            schema = self.schema_class(schema_file)
            ns_schemas = schema.maps.namespaces['http://example.com/vehicles']

            self.assertEqual(len(ns_schemas), 4)
            self.assertEqual(ns_schemas[0].name, 'issue_187_2.xsd')
            self.assertEqual(ns_schemas[1].name, 'cars.xsd')
            self.assertEqual(ns_schemas[2].name, 'types.xsd')
            self.assertEqual(ns_schemas[3].name, 'bikes.xsd')

        self.assertFalse(os.path.isdir(dirname))

        # Test with DEBUG logging level
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertLogs('xmlschema', level='DEBUG') as ctx:
                vh_schema.export(target=dirname, save_remote=True, loglevel='DEBUG')
                self.assertGreater(len(ctx.output), 0)
                self.assertTrue(any('Write modified ' in line for line in ctx.output))
                self.assertTrue(any('Write unchanged ' in line for line in ctx.output))

        self.assertFalse(os.path.isdir(dirname))

    @unittest.skipIf(platform.system() == 'Windows', 'skip, Windows systems save with <CR><LF>')
    def test_export_other_encoding(self):
        schema_file = self.casepath('examples/menù/menù.xsd')
        schema_ascii_file = self.casepath('examples/menù/menù-ascii.xsd')
        schema_cp1252_file = self.casepath('examples/menù/menù-cp1252.xsd')

        schema = self.schema_class(schema_file)
        with tempfile.TemporaryDirectory() as dirname:
            schema.export(target=dirname)
            exported_schema = pathlib.Path(dirname).joinpath('menù.xsd')
            self.assertTrue(filecmp.cmp(schema_file, exported_schema))
            self.assertFalse(filecmp.cmp(schema_ascii_file, exported_schema))
            self.assertFalse(filecmp.cmp(schema_cp1252_file, exported_schema))

        schema = self.schema_class(schema_ascii_file)
        with tempfile.TemporaryDirectory() as dirname:
            schema.export(target=dirname)
            exported_schema = pathlib.Path(dirname).joinpath('menù-ascii.xsd')
            self.assertFalse(filecmp.cmp(schema_file, exported_schema))
            self.assertTrue(filecmp.cmp(schema_ascii_file, exported_schema))
            self.assertFalse(filecmp.cmp(schema_cp1252_file, exported_schema))

        schema = self.schema_class(schema_cp1252_file)
        with tempfile.TemporaryDirectory() as dirname:
            schema.export(target=dirname)
            exported_schema = pathlib.Path(dirname).joinpath('menù-cp1252.xsd')
            self.assertFalse(filecmp.cmp(schema_file, exported_schema))
            self.assertFalse(filecmp.cmp(schema_ascii_file, exported_schema))
            self.assertTrue(filecmp.cmp(schema_cp1252_file, exported_schema))

    def test_export_more_remote_imports__issue_362(self):
        schema_file = self.casepath('issues/issue_362/issue_362_1.xsd')
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            schema = self.schema_class(schema_file)

        self.assertIn('{http://xmlschema.test/tns1}root', schema.maps.elements)
        self.assertIn('{http://xmlschema.test/tns1}item1', schema.maps.elements)
        self.assertIn('{http://xmlschema.test/tns2}item2', schema.maps.elements)
        self.assertIn('{http://xmlschema.test/tns2}item3', schema.maps.elements)

        with tempfile.TemporaryDirectory() as dirname:
            schema.export(target=dirname)

            exported_files = {
                str(x.relative_to(dirname)).replace('\\', '/')
                for x in pathlib.Path(dirname).glob('**/*.xsd')
            }
            self.assertSetEqual(
                exported_files,
                {'issue_362_1.xsd', 'dir2/issue_362_2.xsd', 'dir1/issue_362_1.xsd',
                 'dir1/dir2/issue_362_2.xsd', 'issue_362_1.xsd', 'dir2/issue_362_2.xsd',
                 'dir1/issue_362_1.xsd', 'dir1/dir2/issue_362_2.xsd'}
            )

            schema_file = pathlib.Path(dirname).joinpath('issue_362_1.xsd')
            schema = self.schema_class(schema_file)
            self.assertIn('{http://xmlschema.test/tns1}root', schema.maps.elements)
            self.assertIn('{http://xmlschema.test/tns1}item1', schema.maps.elements)
            self.assertIn('{http://xmlschema.test/tns2}item2', schema.maps.elements)
            self.assertIn('{http://xmlschema.test/tns2}item3', schema.maps.elements)


class TestExports11(TestExports):

    schema_class = XMLSchema11


class TestDownloads(XMLSchemaTestCase):
    cases_dir = pathlib.Path(__file__).absolute().parent.joinpath('test_cases')

    @classmethod
    def setUpClass(cls):
        cls.vh_dir = cls.casepath('examples/vehicles')
        cls.vh_xsd_file = cls.casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = cls.casepath('examples/vehicles/vehicles.xml')

    def test_download_local_schemas(self):
        with tempfile.TemporaryDirectory() as dirname:
            location_map = download_schemas(self.vh_xsd_file, target=dirname, modify=True)

            self.assertEqual(location_map, {})

            xsd_path = pathlib.Path(dirname).joinpath('vehicles.xsd')
            schema = XMLSchema10(xsd_path)
            for xs in schema.maps.namespaces['http://example.com/vehicles']:
                self.assertTrue(xs.url.startswith('file://'))

            self.assertTrue(pathlib.Path(dirname).joinpath('__init__.py').is_file())

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_download_local_and_remote_schemas(self):
        vh_schema_file = self.casepath('issues/issue_187/issue_187_2.xsd')
        url_common = ('raw.githubusercontent.com/brunato/xmlschema/master/'
                      'tests/test_cases/examples/vehicles')
        url_map = {
            f'https://{url_common}/bikes.xsd': f'https/{url_common}/bikes.xsd',
            f'https://{url_common}/cars.xsd': f'https/{url_common}/cars.xsd'
        }

        with tempfile.TemporaryDirectory() as dirname:
            location_map = download_schemas(vh_schema_file, target=dirname, modify=True)

            self.assertEqual(location_map, url_map)

            xsd_path = pathlib.Path(dirname).joinpath('issue_187_2.xsd')
            schema = XMLSchema10(xsd_path)
            for xs in schema.maps.namespaces['http://example.com/vehicles']:
                self.assertTrue(xs.url.startswith('file://'))

            self.assertTrue(pathlib.Path(dirname).joinpath('__init__.py').is_file())

        with tempfile.TemporaryDirectory() as dirname:
            location_map = download_schemas(vh_schema_file, target=dirname)

            self.assertEqual(location_map, url_map)

            xsd_path = pathlib.Path(dirname).joinpath('issue_187_2.xsd')
            schema = XMLSchema10(xsd_path)
            for k, xs in enumerate(schema.maps.namespaces['http://example.com/vehicles']):
                if k:
                    self.assertTrue(xs.url.startswith('https://'))
                else:
                    self.assertTrue(xs.url.startswith('file://'))

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_download_remote_schemas(self):
        url = ("https://raw.githubusercontent.com/brewpoo/"
               "BeerXML-Standard/master/schema/BeerXML.xsd")

        with tempfile.TemporaryDirectory() as dirname:
            location_map = download_schemas(url, target=dirname, modify=True)
            self.assertEqual(location_map, {})

            xsd_files = {x.name for x in pathlib.Path(dirname).glob('*.xsd')}
            self.assertSetEqual(xsd_files, {
                'BeerXML.xsd', 'measureable_units.xsd', 'hops.xsd',
                'yeast.xsd', 'mash.xsd', 'style.xsd', 'water.xsd',
                'grain.xsd', 'misc.xsd', 'recipes.xsd', 'mash_step.xsd'
            })

            xsd_path = pathlib.Path(dirname).joinpath('BeerXML.xsd')
            schema = XMLSchema10(xsd_path)
            for ns in schema.maps.namespaces:
                if ns.startswith('urn:beerxml:'):
                    for k, xs in enumerate(schema.maps.namespaces[ns]):
                        self.assertEqual(k, 0)
                        self.assertTrue(xs.url.startswith('file://'))

    def test_download_with_loglevel(self):
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertLogs('xmlschema', level='DEBUG') as ctx:
                download_schemas(self.vh_xsd_file, target=dirname, loglevel='debug')
                self.assertGreater(len(ctx.output), 10)
                self.assertFalse(any('Write modified ' in line for line in ctx.output))
                self.assertTrue(any('Write unchanged ' in line for line in ctx.output))


if __name__ == '__main__':
    run_xmlschema_tests('exports.py module')
