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
import logging
import tempfile
import warnings
import pathlib
import platform
import glob
import os
import re
from textwrap import dedent

from xmlschema import XMLSchemaParseError, XMLSchemaIncludeWarning, XMLSchemaImportWarning
from xmlschema.names import XML_NAMESPACE, LOCATION_HINTS, SCHEMAS_DIR, XSD_ELEMENT, XSI_TYPE
from xmlschema.etree import etree_element
from xmlschema.validators import XMLSchemaBase, XMLSchema11, XsdGlobals
from xmlschema.testing import SKIP_REMOTE_TESTS, XsdValidatorTestCase
from xmlschema.validators.schema import logger, XMLSchemaNotBuiltError


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

    def test_schema_location_hints(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            schema = self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xsi:schemaLocation="http://xmlschema.test/ns schema.xsd">
                  <xs:element name="root" />
                </xs:schema>"""))

        self.assertEqual(schema.schema_location, [("http://xmlschema.test/ns", "schema.xsd")])
        self.assertIsNone(schema.no_namespace_schema_location)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:noNamespaceSchemaLocation="schema.xsd">
              <xs:element name="root" />
            </xs:schema>"""))

        self.assertEqual(schema.schema_location, [])
        self.assertEqual(schema.no_namespace_schema_location, 'schema.xsd')

    def test_target_prefix(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                targetNamespace="http://xmlschema.test/ns">
              <xs:element name="root" />
            </xs:schema>"""))

        self.assertEqual(schema.target_prefix, '')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns="http://xmlschema.test/ns"
                targetNamespace="http://xmlschema.test/ns">
              <xs:element name="root" />
            </xs:schema>"""))

        self.assertEqual(schema.target_prefix, 'tns')

    def test_builtin_types(self):
        self.assertIn('string', self.schema_class.builtin_types())

        with self.assertRaises(XMLSchemaNotBuiltError):
            self.schema_class.meta_schema.builtin_types()

    def test_resolve_qname(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">    
              <xs:element name="root" />
            </xs:schema>"""))

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
        xsd_file = os.path.join(SCHEMAS_DIR, 'XML/xml_minimal.xsd')
        schema = self.schema_class(xsd_file)
        self.assertEqual(schema.target_namespace, XML_NAMESPACE)

    def test_root_elements(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>"""))
        self.assertEqual(schema.root_elements, [])

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" />
            </xs:schema>"""))
        self.assertEqual(schema.root_elements, [schema.elements['root']])

        # Test issue #107 fix
        schema = self.schema_class(dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root1" type="root"/>
                <xs:element name="root2" type="root"/>
                <xs:complexType name="root">
                    <xs:sequence>
                        <xs:element name="elementWithNoType"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:schema>"""))

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

    def test_logging(self):
        self.schema_class(self.vh_xsd_file, loglevel=logging.ERROR)
        self.assertEqual(logger.level, logging.WARNING)

        with self.assertLogs('xmlschema', level='INFO') as ctx:
            self.schema_class(self.vh_xsd_file, loglevel=logging.INFO)

        self.assertEqual(logger.level, logging.WARNING)
        self.assertEqual(len(ctx.output), 7)
        self.assertIn("INFO:xmlschema:Include schema from 'types.xsd'", ctx.output)
        self.assertIn("INFO:xmlschema:Resource 'types.xsd' is already loaded", ctx.output)

        with self.assertLogs('xmlschema', level='DEBUG') as ctx:
            self.schema_class(self.vh_xsd_file, loglevel=logging.DEBUG)

        self.assertEqual(logger.level, logging.WARNING)
        self.assertEqual(len(ctx.output), 19)
        self.assertIn("INFO:xmlschema:Include schema from 'cars.xsd'", ctx.output)
        self.assertIn("INFO:xmlschema:Resource 'cars.xsd' is already loaded", ctx.output)
        self.assertIn("DEBUG:xmlschema:Schema targetNamespace is "
                      "'http://example.com/vehicles'", ctx.output)
        self.assertIn("INFO:xmlschema:Resource 'cars.xsd' is already loaded", ctx.output)

        # With string argument
        with self.assertRaises(ValueError) as ctx:
            self.schema_class(self.vh_xsd_file, loglevel='all')
        self.assertEqual(str(ctx.exception), "'all' is not a valid loglevel")

        with self.assertLogs('xmlschema', level='INFO') as ctx:
            self.schema_class(self.vh_xsd_file, loglevel='INFO')
        self.assertEqual(len(ctx.output), 7)

        with self.assertLogs('xmlschema', level='INFO') as ctx:
            self.schema_class(self.vh_xsd_file, loglevel='  Info ')
        self.assertEqual(len(ctx.output), 7)

    def test_target_namespace(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    targetNamespace="http://xmlschema.test/ns">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(schema.target_namespace, 'http://xmlschema.test/ns')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(schema.target_namespace, '')

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        targetNamespace="">
                    <xs:element name="root"/>
                </xs:schema>"""))

        self.assertEqual(ctx.exception.message,
                         "the attribute 'targetNamespace' cannot be an empty string")

    def test_block_default(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    blockDefault="extension restriction ">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(schema.block_default, 'extension restriction ')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    blockDefault="#all">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(set(schema.block_default.split()),
                         {'substitution', 'extension', 'restriction'})

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        blockDefault="all">>
                    <xs:element name="root"/>
                </xs:schema>"""))

        self.assertEqual(ctx.exception.message,
                         "wrong value 'all' for attribute 'blockDefault'")

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        blockDefault="#all restriction">>
                    <xs:element name="root"/>
                </xs:schema>"""))

        self.assertEqual(ctx.exception.message,
                         "wrong value '#all restriction' for attribute 'blockDefault'")

    def test_final_default(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    finalDefault="extension restriction ">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(schema.final_default, 'extension restriction ')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    finalDefault="#all">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(set(schema.final_default.split()),
                         {'list', 'union', 'extension', 'restriction'})

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        finalDefault="all">>
                    <xs:element name="root"/>
                </xs:schema>"""))

        self.assertEqual(ctx.exception.message,
                         "wrong value 'all' for attribute 'finalDefault'")

    def test_use_fallback(self):
        source = dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>""")

        schema = self.schema_class(source)
        self.assertEqual(schema.fallback_locations, LOCATION_HINTS)
        schema = self.schema_class(source, use_fallback=False)
        self.assertEqual(schema.fallback_locations, {})

    def test_global_maps(self):
        source = dedent("""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:element name="root"/>
                    </xs:schema>""")
        col_schema = self.schema_class(self.col_xsd_file)

        with self.assertRaises(TypeError) as ctx:
            self.schema_class(self.col_schema, global_maps=col_schema)
        self.assertIn("'global_maps' argument must be", str(ctx.exception))

        schema = self.schema_class(source, global_maps=col_schema.maps)
        self.assertIs(col_schema.maps, schema.maps)

    def test_version_control(self):
        schema = self.schema_class(dedent("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:attribute name="a" use="required"/>
                        <xs:assert test="@a > 300" vc:minVersion="1.1" 
                            xmlns:vc="http://www.w3.org/2007/XMLSchema-versioning"/>
                    </xs:complexType>
                </xs:element>
            </xs:schema>"""))
        self.assertEqual(len(schema.root[0][0]), 1 if schema.XSD_VERSION == '1.0' else 2)

        schema = self.schema_class(dedent("""
            <xs:schema vc:minVersion="1.1" elementFormDefault="qualified" 
                    xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    xmlns:vc="http://www.w3.org/2007/XMLSchema-versioning">
                <xs:element name="root"/>
            </xs:schema>"""))
        self.assertEqual(len(schema.root), 0 if schema.XSD_VERSION == '1.0' else 1)

    def test_xsd_version_compatibility_property(self):
        self.assertEqual(self.vh_schema.xsd_version, self.vh_schema.XSD_VERSION)

    def test_explicit_locations(self):
        source = dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>""")

        locations = {'http://example.com/vehicles': self.vh_xsd_file}
        schema = self.schema_class(source, locations=locations)
        self.assertEqual(len(schema.maps.namespaces['http://example.com/vehicles']), 4)

    def test_use_meta_property(self):
        self.assertTrue(self.vh_schema.use_meta)
        self.assertTrue(self.col_schema.use_meta)

        meta_schema = self.schema_class.meta_schema

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="foo"/>
            </xs:schema>"""), use_meta=False)
        self.assertIsNot(meta_schema, schema.meta_schema)
        self.assertFalse(schema.use_meta)

    def test_other_schema_root_attributes(self):
        self.assertIsNone(self.vh_schema.id)
        self.assertIsNone(self.vh_schema.version)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" id="foo" version="2.0">
                <xs:element name="foo"/>
            </xs:schema>"""))
        self.assertEqual(schema.id, 'foo')
        self.assertEqual(schema.version, '2.0')

    def test_change_maps_attribute(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>"""))

        with self.assertRaises(ValueError) as ctx:
            schema.meta_schema.maps = XsdGlobals(schema, schema.validation)
        self.assertEqual(str(ctx.exception),
                         "cannot change the global maps instance of a meta-schema")

        self.assertTrue(schema.built)
        maps, schema.maps = schema.maps, XsdGlobals(schema, schema.validation)
        self.assertIsNot(maps, schema.maps)
        self.assertFalse(schema.built)
        schema.maps = maps
        self.assertTrue(schema.built)

    def test_listed_and_reversed_elements(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="elem1"/>
                <xs:element name="elem2"/>
                <xs:element name="elem3"/>
            </xs:schema>"""))

        elements = list(schema)
        self.assertListEqual(elements, [schema.elements['elem1'],
                                        schema.elements['elem2'],
                                        schema.elements['elem3']])
        elements.reverse()
        self.assertListEqual(elements, list(reversed(schema)))

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

    def test_default_attributes(self):
        schema = self.schema_class(dedent("""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                            defaultAttributes="attrs">
                        <xs:element name="root"/>
                        <xs:attributeGroup name="attrs">
                            <xs:attribute name="a"/>
                        </xs:attributeGroup>
                    </xs:schema>"""))
        self.assertIs(schema.default_attributes, schema.attribute_groups['attrs'])

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        defaultAttributes="attrs">
                    <xs:element name="root"/>
                </xs:schema>"""))
        self.assertIn("'attrs' doesn't match an attribute group", ctx.exception.message)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                        defaultAttributes="x:attrs">
                    <xs:element name="root"/>
                </xs:schema>"""))
        self.assertEqual("prefix 'x' not found in namespace map", ctx.exception.message)


class TestXMLSchemaMeta(unittest.TestCase):

    def test_wrong_version(self):
        with self.assertRaises(ValueError) as ctx:
            class XMLSchema12(XMLSchemaBase):
                XSD_VERSION = '1.2'
                meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')

            assert issubclass(XMLSchema12, XMLSchemaBase)

        self.assertEqual(str(ctx.exception), "XSD_VERSION must be '1.0' or '1.1'")

    def test_missing_builders(self):
        with self.assertRaises(ValueError) as ctx:
            class XMLSchema12(XMLSchemaBase):
                XSD_VERSION = '1.1'
                meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')

            assert issubclass(XMLSchema12, XMLSchemaBase)

        self.assertEqual(str(ctx.exception),
                         "validator class doesn't have defined XSD builders")

    def test_missing_builder_map(self):
        with self.assertRaises(ValueError) as ctx:
            class XMLSchema12(XMLSchemaBase):
                XSD_VERSION = '1.1'
                meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')
                BUILDERS = XMLSchema11.BUILDERS

            assert issubclass(XMLSchema12, XMLSchemaBase)

        self.assertEqual(str(ctx.exception),
                         "validator class doesn't have a builder map for XSD globals")

    def test_from_schema_class(self):
        class XMLSchema11Bis(XMLSchema11):
            pass

        self.assertTrue(issubclass(XMLSchema11Bis, XMLSchemaBase))

    def test_dummy_validator_class(self):
        class DummySchema(XMLSchemaBase):
            XSD_VERSION = '1.1'
            meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')
            BUILDERS = {
                'notation_class': None,
                'complex_type_class': None,
                'attribute_class': None,
                'any_attribute_class': None,
                'attribute_group_class': None,
                'group_class': None,
                'element_class': None,
                'any_element_class': None,
                'restriction_class': None,
                'union_class': None,
                'key_class': None,
                'keyref_class': None,
                'unique_class': None,
                'simple_type_factory': None,
            }
            BASE_SCHEMAS = {}

        self.assertTrue(issubclass(DummySchema, XMLSchemaBase))


if __name__ == '__main__':
    header_template = "Test xmlschema's schema classes with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
