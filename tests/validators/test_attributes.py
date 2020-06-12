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

    def test_wrong_attribute(self):
        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attribute ref="phone"/>  <!-- Missing "phone" attribute -->
        </xs:attributeGroup>
        """, XMLSchemaParseError)

    def test_wrong_attribute_group(self):
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
    from xmlschema.testing import print_test_header

    print_test_header()
    unittest.main()
