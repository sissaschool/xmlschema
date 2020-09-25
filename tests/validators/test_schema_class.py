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
import tempfile
import warnings
import pathlib
import platform
import glob
import os
import re

from xmlschema import XMLSchemaParseError, XMLSchemaIncludeWarning, XMLSchemaImportWarning
from xmlschema.etree import etree_element
from xmlschema.namespaces import SCHEMAS_DIR
from xmlschema.qnames import XSD_ELEMENT, XSI_TYPE
from xmlschema.validators import XMLSchema11
from xmlschema.testing import SKIP_REMOTE_TESTS, XsdValidatorTestCase, print_test_header


class TestXMLSchema10(XsdValidatorTestCase):
    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')
    maxDiff = None

    def test_schema_validation(self):
        schema = self.schema_class(self.vh_xsd_file)
        self.assertEqual(schema.validation, 'strict')

        schema = self.schema_class(self.vh_xsd_file, validation='lax')
        self.assertEqual(schema.validation, 'lax')

        schema = self.schema_class(self.vh_xsd_file, validation='skip')
        self.assertEqual(schema.validation, 'skip')

        with self.assertRaises(ValueError):
            self.schema_class(self.vh_xsd_file, validation='none')

    def test_schema_string_repr(self):
        schema = self.schema_class(self.vh_xsd_file)
        tmpl = "%s(name='vehicles.xsd', namespace='http://example.com/vehicles')"
        self.assertEqual(str(schema), tmpl % self.schema_class.__name__)

    def test_schema_copy(self):
        schema = self.vh_schema.copy()
        self.assertNotEqual(id(self.vh_schema), id(schema))
        self.assertNotEqual(id(self.vh_schema.namespaces), id(schema.namespaces))
        self.assertNotEqual(id(self.vh_schema.maps), id(schema.maps))

    def test_resolve_qname(self):
        schema = self.schema_class("""<xs:schema
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

            <xs:element name="root" />
        </xs:schema>""")
        self.assertEqual(schema.resolve_qname('xs:element'), XSD_ELEMENT)
        self.assertEqual(schema.resolve_qname('xsi:type'), XSI_TYPE)

        self.assertEqual(schema.resolve_qname(XSI_TYPE), XSI_TYPE)
        self.assertEqual(schema.resolve_qname('element'), 'element')
        self.assertRaises(ValueError, schema.resolve_qname, '')
        self.assertRaises(ValueError, schema.resolve_qname, 'xsi:a type ')
        self.assertRaises(ValueError, schema.resolve_qname, 'xml::lang')

    def test_global_group_definitions(self):
        schema = self.check_schema("""
            <xs:group name="wrong_child">
              <xs:element name="foo"/>
            </xs:group>""", validation='lax')
        self.assertEqual(len(schema.errors), 1)

        self.check_schema('<xs:group name="empty" />', XMLSchemaParseError)
        self.check_schema('<xs:group name="empty"><xs:annotation/></xs:group>', XMLSchemaParseError)

    def test_wrong_includes_and_imports(self):

        with warnings.catch_warnings(record=True) as context:
            warnings.simplefilter("always")
            self.check_schema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="ns">
                <xs:include schemaLocation="example.xsd" />
                <xs:import schemaLocation="example.xsd" />
                <xs:redefine schemaLocation="example.xsd"/>
                <xs:import namespace="http://missing.example.test/" />
                <xs:import/>
            </xs:schema>
            """)
            self.assertEqual(len(context), 3, "Wrong number of include/import warnings")
            self.assertEqual(context[0].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[1].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[2].category, XMLSchemaImportWarning)
            self.assertTrue(str(context[0].message).startswith("Include"))
            self.assertTrue(str(context[1].message).startswith("Redefine"))
            self.assertTrue(str(context[2].message).startswith("Import of namespace"))

    def test_wrong_references(self):
        # Wrong namespace for element type's reference
        self.check_schema("""
        <xs:element name="dimension" type="xs:dimensionType"/>
        <xs:simpleType name="dimensionType">
          <xs:restriction base="xs:short"/>
        </xs:simpleType>
        """, XMLSchemaParseError)

    def test_annotations(self):
        schema = self.check_schema("""
            <xs:element name='foo'>
                <xs:annotation />
            </xs:element>""")
        self.assertIsNotNone(schema.elements['foo'].annotation)

        schema = self.check_schema("""
        <xs:simpleType name='Magic'>
            <xs:annotation>
                <xs:documentation> stuff </xs:documentation>
            </xs:annotation>
            <xs:restriction base='xs:string'>
                <xs:enumeration value='A'/>
            </xs:restriction>
        </xs:simpleType>""")
        self.assertIsNotNone(schema.types["Magic"].annotation)

        self.check_schema("""
        <xs:simpleType name='Magic'>
            <xs:annotation />
            <xs:annotation />
            <xs:restriction base='xs:string'>
                <xs:enumeration value='A'/>
            </xs:restriction>
        </xs:simpleType>""", XMLSchemaParseError)

    def test_base_schemas(self):
        self.schema_class(os.path.join(SCHEMAS_DIR, 'xml_minimal.xsd'))

    def test_root_elements(self):
        # Test issue #107 fix
        schema = self.schema_class("""<?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root1" type="root"/>
                <xs:element name="root2" type="root"/>
                <xs:complexType name="root">
                    <xs:sequence>
                        <xs:element name="elementWithNoType"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:schema>""")

        self.assertEqual(set(schema.root_elements),
                         {schema.elements['root1'], schema.elements['root2']})

    def test_is_restriction_method(self):
        # Test issue #111 fix
        schema = self.schema_class(source=self.casepath('issues/issue_111/issue_111.xsd'))
        extended_header_def = schema.types['extendedHeaderDef']
        self.assertTrue(extended_header_def.is_derived(schema.types['blockDef']))

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_remote_schemas_loading(self):
        col_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                       "tests/test_cases/examples/collection/collection.xsd",
                                       timeout=300)
        self.assertTrue(isinstance(col_schema, self.schema_class))
        vh_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                      "tests/test_cases/examples/vehicles/vehicles.xsd",
                                      timeout=300)
        self.assertTrue(isinstance(vh_schema, self.schema_class))

    def test_schema_defuse(self):
        vh_schema = self.schema_class(self.vh_xsd_file, defuse='always')
        self.assertIsInstance(vh_schema.root, etree_element)
        for schema in vh_schema.maps.iter_schemas():
            self.assertIsInstance(schema.root, etree_element)

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
            self.assertEqual(
                exported_schema,
                original_schema.replace('../..', dirname.replace('\\', '/'))
            )

        self.assertFalse(os.path.isdir(dirname))

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
            vh_schema.export(target=dirname, only_relative=False)
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
            self.assertEqual(
                exported_schema,
                original_schema.replace('https://raw.githubusercontent.com',
                                        dirname.replace('\\', '/') + '/raw.githubusercontent.com')
            )

        self.assertFalse(os.path.isdir(dirname))


class TestXMLSchema11(TestXMLSchema10):

    schema_class = XMLSchema11


if __name__ == '__main__':
    print_test_header()
    unittest.main()
