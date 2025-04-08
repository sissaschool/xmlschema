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
import pathlib
import warnings

from xmlschema import XMLSchema11
from xmlschema import SchemaLoader, LocationSchemaLoader, SafeSchemaLoader
from xmlschema.testing import XMLSchemaTestCase, run_xmlschema_tests
from xmlschema import XMLSchemaParseError
import xmlschema.names as nm


class TestLoadersAPI(XMLSchemaTestCase):
    cases_dir = pathlib.Path(__file__).absolute().parent.joinpath('test_cases')

    @classmethod
    def setUpClass(cls):
        cls.col_xsd_file = cls.casepath('examples/collection/collection.xsd')
        cls.schema = cls.schema_class(cls.col_xsd_file)
        cls.loader = cls.schema.maps.loader

    def test_get_namespaces(self):
        self.assertListEqual(self.loader.get_locations('tns'), [])
        self.assertEqual(len(self.loader.get_locations(nm.XSD_NAMESPACE)), 3)

    def test_load_declared_schemas(self):
        with self.assertRaises(ValueError):
            self.loader.load_declared_schemas(self.schema.meta_schema)

        xsd_file = self.casepath('loaders/schema4.xsd')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(xsd_file)
        self.assertIn("the attribute 'namespace' must be different", str(ctx.exception))

        xsd_file = self.casepath('loaders/schema5.xsd')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(xsd_file)
        self.assertIn("differs from what expected", str(ctx.exception))

    def test_load_namespace(self):
        locations = [('http://xmlschema.test/ns', 'unresolved'),]

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("ignore")
            schema = self.schema_class(self.col_xsd_file, locations=locations)

        num = len(schema.maps.namespaces)
        schema.load_namespace('http://xmlschema.test/ns')
        self.assertEqual(num, len(schema.maps.namespaces))
        self.assertNotIn('http://xmlschema.test/ns', schema.maps.namespaces)


class TestSchemaLoader(XMLSchemaTestCase):
    cases_dir = pathlib.Path(__file__).absolute().parent.joinpath('test_cases')
    loader_class = SchemaLoader

    def test_load_single(self):
        col_xsd_file = self.casepath('examples/collection/collection.xsd')
        schema = self.schema_class(col_xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 1)
        self.assertTrue(schema.maps.built)

        total_globals = schema.maps.global_maps.total
        self.assertGreater(total_globals, 0)

        schema.maps.loader.clear()
        self.assertEqual(len(schema.maps.owned_schemas), 1)
        schema.build()
        self.assertEqual(schema.maps.global_maps.total, total_globals)

    def test_load_composite(self):
        vh_xsd_file = self.casepath('examples/vehicles/vehicles.xsd')
        schema = self.schema_class(vh_xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 4)
        self.assertTrue(schema.maps.built)

        total_globals = schema.maps.global_maps.total
        self.assertGreater(total_globals, 0)

        schema.maps.loader.clear()
        self.assertEqual(len(schema.maps.owned_schemas), 4)
        schema.build()
        self.assertEqual(schema.maps.global_maps.total, total_globals)

    def test_load_case1(self):
        xsd_file = self.casepath('loaders/schema1.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 2)
        self.assertTrue(schema.maps.built)

    def test_load_case2(self):
        xsd_file = self.casepath('loaders/schema2.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 2)
        self.assertTrue(schema.maps.built)

    def test_load_case3(self):
        xsd_file = self.casepath('loaders/schema3.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 2)
        self.assertTrue(schema.maps.built)


class TestSchemaLoader11(TestSchemaLoader):
    schema_class = XMLSchema11


class TestLocationSchemaLoader(TestSchemaLoader):
    loader_class = LocationSchemaLoader

    def test_load_case1(self):
        xsd_file = self.casepath('loaders/schema1.xsd')
        with warnings.catch_warnings(record=True):
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(xsd_file, loader_class=self.loader_class)

    def test_load_case2(self):
        xsd_file = self.casepath('loaders/schema2.xsd')
        with warnings.catch_warnings(record=True):
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(xsd_file, loader_class=self.loader_class)

    def test_load_case3(self):
        xsd_file = self.casepath('loaders/schema3.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 3)
        self.assertTrue(schema.maps.built)


class TestLocationSchemaLoader11(TestLocationSchemaLoader):
    schema_class = XMLSchema11


class TestSafeSchemaLoader(TestSchemaLoader):
    loader_class = SafeSchemaLoader

    def test_load_case2(self):
        xsd_file = self.casepath('loaders/schema2.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 3)
        self.assertTrue(schema.maps.built)

    def test_load_case3(self):
        xsd_file = self.casepath('loaders/schema3.xsd')
        schema = self.schema_class(xsd_file, loader_class=self.loader_class)
        self.assertIsInstance(schema, self.schema_class)
        self.assertEqual(len(schema.maps.owned_schemas), 3)
        self.assertTrue(schema.maps.built)


class TestSafeSchemaLoader11(TestSafeSchemaLoader):
    schema_class = XMLSchema11


if __name__ == '__main__':
    run_xmlschema_tests("loaders.py module")
