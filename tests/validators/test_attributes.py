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

from xmlschema import XMLSchemaParseError
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


class TestXsdAttributes(XsdValidatorTestCase):

    def test_attribute_use(self):
        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema('<xs:attribute name="label" type="xs:string" use="optional"/>')
        self.assertEqual("use of attribute 'use' is prohibited", ctx.exception.message)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema("""
            <xs:attributeGroup name="extra">
                <xs:attribute name="label" type="xs:string" use="mandatory"/>
            </xs:attributeGroup>""")
        self.assertEqual(ctx.exception.message,
                         "attribute use='mandatory': value must "
                         "be one of ['prohibited', 'optional', 'required']")

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema("""
            <xs:attributeGroup name="extra">
                <xs:attribute name="label" type="xs:string" use=""/>
            </xs:attributeGroup>""")
        self.assertEqual(ctx.exception.message,
                         "attribute use='': value doesn't match any pattern of ['\\\\c+']")

    def test_wrong_attribute_type(self):
        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:anyType"/>
        </xs:attributeGroup>
        """, XMLSchemaParseError)

    def test_attribute_reference(self):
        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attribute ref="phone"/>  <!-- Missing "phone" attribute -->
        </xs:attributeGroup>
        """, XMLSchemaParseError)

        schema = self.schema_class("""<xs:schema
                xmlns:xs="http://www.w3.org/2001/XMLSchema" attributeFormDefault="qualified">
            <xs:attributeGroup name="alpha">
                <xs:attribute name="name" type="xs:string"/>
                <xs:attribute ref="phone"/>
            </xs:attributeGroup>
            <xs:attribute name="phone" type="xs:string"/>
        </xs:schema>""")
        self.assertTrue(schema.attribute_groups['alpha']['phone'].qualified)

    def test_missing_attribute_group_reference(self):
        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attributeGroup ref="beta"/>  <!-- Missing "beta" attribute group -->
        </xs:attributeGroup>
        """, XMLSchemaParseError)

        schema = self.check_schema("""
            <xs:attributeGroup name="alpha">
                <xs:attribute name="name" type="xs:string"/>
                <xs:attributeGroup name="beta"/>  <!-- attribute "name" instead of "ref" -->
            </xs:attributeGroup>
            """, validation='lax')
        self.assertTrue(isinstance(schema.all_errors[1], XMLSchemaParseError))

    def test_scope_property(self):
        schema = self.check_schema("""
        <xs:attribute name="global_attr" type="xs:string"/>
        <xs:attributeGroup name="attrGroup">
            <xs:attribute name="local_attr" type="xs:string"/>
        </xs:attributeGroup>
        """)
        self.assertEqual(schema.attributes['global_attr'].scope, 'global')
        self.assertEqual(schema.attribute_groups['attrGroup']['local_attr'].scope, 'local')

    def test_value_constraint_property(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="attrGroup">
            <xs:attribute name="attr1" type="xs:string"/>
            <xs:attribute name="attr2" type="xs:string" default="alpha"/>
            <xs:attribute name="attr3" type="xs:string" default="beta"/>
        </xs:attributeGroup>
        """)
        attribute_group = schema.attribute_groups['attrGroup']
        self.assertIsNone(attribute_group['attr1'].value_constraint)
        self.assertEqual(attribute_group['attr2'].value_constraint, 'alpha')
        self.assertEqual(attribute_group['attr3'].value_constraint, 'beta')


class TestXsd11Attributes(TestXsdAttributes):

    schema_class = XMLSchema11


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD attributes with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
