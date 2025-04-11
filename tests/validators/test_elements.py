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

from xmlschema import XMLSchemaParseError
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


class TestXsdElements(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')

    def test_element_ref(self):
        schema = self.check_schema("""
        <xs:element name="node" type="xs:string"/>
        <xs:group name="group">
            <xs:sequence>
                <xs:element ref="node"/>
            </xs:sequence>
        </xs:group>""")
        self.assertIs(schema.elements['node'].type, schema.groups['group'][0].type)

        self.check_schema("""
        <xs:element name="node" type="xs:string"/>
        <xs:group name="group">
            <xs:sequence>
                <xs:element ref="unknown"/>
            </xs:sequence>
        </xs:group>""", XMLSchemaParseError)

        self.check_schema("""
        <xs:element name="node" type="xs:string"/>
        <xs:group name="group">
            <xs:sequence>
                <xs:element ref="node" default="foo"/>
            </xs:sequence>
        </xs:group>""", XMLSchemaParseError)

    def test_name_attribute(self):
        schema = self.check_schema("""
        <xs:group name="group">
            <xs:sequence>
                <xs:element/>
            </xs:sequence>
        </xs:group>""", validation='lax')
        self.assertEqual(len(schema.all_errors), 1)

    def test_form_attribute(self):
        schema = self.check_schema("""
        <xs:group name="group">
            <xs:sequence>
                <xs:element name="elem1" form="qualified"/>
                <xs:element name="elem2" form="unqualified"/>
            </xs:sequence>
        </xs:group>""")
        self.assertTrue(schema.groups['group'][0].qualified)
        self.assertFalse(schema.groups['group'][1].qualified)

    def test_nillable_attribute(self):
        schema = self.check_schema("""
        <xs:group name="group">
            <xs:sequence>
                <xs:element name="elem1" nillable=" true "/>
                <xs:element name="elem2" nillable=" false "/>
                <xs:element name="elem3" nillable=" True "/>
            </xs:sequence>
        </xs:group>""", validation='lax')

        self.assertTrue(schema.groups['group'][0].nillable)
        self.assertFalse(schema.groups['group'][1].nillable)
        self.assertFalse(schema.groups['group'][2].nillable)
        self.assertEqual(len(schema.all_errors), 1)
        self.assertIn("'True' is not a boolean value", schema.all_errors[0].message)

    def test_scope_property(self):
        schema = self.check_schema("""
        <xs:element name="global_elem" type="xs:string"/>
        <xs:group name="group">
            <xs:sequence>
                <xs:element name="local_elem" type="xs:string"/>
            </xs:sequence>
        </xs:group>
        """)
        self.assertEqual(schema.elements['global_elem'].scope, 'global')
        self.assertEqual(schema.groups['group'][0].scope, 'local')

    def test_value_constraint_property(self):
        schema = self.check_schema("""
        <xs:group name="group">
            <xs:sequence>
                <xs:element name="elem1" type="xs:string"/>
                <xs:element name="elem2" type="xs:string" default="alpha"/>
                <xs:element name="elem3" type="xs:string" default="beta"/>
            </xs:sequence>
        </xs:group>
        """)
        model_group = schema.groups['group']
        self.assertIsNone(model_group[0].value_constraint)
        self.assertEqual(model_group[1].value_constraint, 'alpha')
        self.assertEqual(model_group[2].value_constraint, 'beta')


class TestXsd11Elements(TestXsdElements):

    schema_class = XMLSchema11


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('XSD elements')
