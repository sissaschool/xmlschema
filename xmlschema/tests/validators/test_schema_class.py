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
from __future__ import print_function, unicode_literals
import unittest
import platform
import warnings
import os

from xmlschema import XMLSchemaParseError, XMLSchemaIncludeWarning, XMLSchemaImportWarning
from xmlschema.etree import etree_element
from xmlschema.namespaces import SCHEMAS_DIR
from xmlschema.qnames import XSD_ELEMENT, XSI_TYPE
from xmlschema.tests import SKIP_REMOTE_TESTS, XsdValidatorTestCase
from xmlschema.validators import XMLSchema11


class TestXMLSchema10(XsdValidatorTestCase):

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

        self.assertEqual(set(schema.root_elements), {schema.elements['root1'], schema.elements['root2']})

    def test_is_restriction_method(self):
        # Test issue #111 fix
        schema = self.schema_class(source=self.casepath('issues/issue_111/issue_111.xsd'))
        extended_header_def = schema.types['extendedHeaderDef']
        self.assertTrue(extended_header_def.is_derived(schema.types['blockDef']))

    @unittest.skipIf(SKIP_REMOTE_TESTS or platform.system() == 'Windows',
                     "Remote networks are not accessible or avoid SSL verification error on Windows.")
    def test_remote_schemas_loading(self):
        col_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                       "xmlschema/tests/test_cases/examples/collection/collection.xsd",
                                       timeout=300)
        self.assertTrue(isinstance(col_schema, self.schema_class))
        vh_schema = self.schema_class("https://raw.githubusercontent.com/brunato/xmlschema/master/"
                                      "xmlschema/tests/test_cases/examples/vehicles/vehicles.xsd",
                                      timeout=300)
        self.assertTrue(isinstance(vh_schema, self.schema_class))

    def test_schema_defuse(self):
        vh_schema = self.schema_class(self.vh_xsd_file, defuse='always')
        self.assertIsInstance(vh_schema.root, etree_element)
        for schema in vh_schema.maps.iter_schemas():
            self.assertIsInstance(schema.root, etree_element)


class TestXMLSchema11(TestXMLSchema10):

    schema_class = XMLSchema11


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
