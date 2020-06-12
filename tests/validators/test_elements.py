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


class TestXsdElements(XsdValidatorTestCase):

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
    from xmlschema.testing import print_test_header

    print_test_header()
    unittest.main()
