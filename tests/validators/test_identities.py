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
from xmlschema.testing import XsdValidatorTestCase, print_test_header


class TestXsdIdentities(XsdValidatorTestCase):

    def test_key_definition(self):
        self.check_schema("""
            <xs:element name="primary_key" type="xs:string">
              <xs:key name="key1">
                <xs:selector xpath="."/>
                <xs:field xpath="."/>
              </xs:key>
            </xs:element>
            """)

        self.check_schema("""
            <xs:element name="primary_key" type="xs:string">
              <xs:key name="key1">
                <xs:selector xpath="."/>
                <xs:field xpath="."/>
              </xs:key>
            </xs:element>
            <xs:element name="secondary_key" type="xs:string">
              <xs:key name="key1">
                <xs:selector xpath="."/>
                <xs:field xpath="."/>
              </xs:key>
            </xs:element>
            """, XMLSchemaParseError)


class TestXsd11Identities(TestXsdIdentities):

    schema_class = XMLSchema11

    def test_ref_definition(self):
        self.check_schema("""
        <xs:element name="primary_key" type="xs:string">
          <xs:key name="key1">
            <xs:selector xpath="."/>
            <xs:field xpath="."/>
          </xs:key>
        </xs:element>
        <xs:element name="secondary_key" type="xs:string">
          <xs:key ref="key1"/>
        </xs:element>
        """)


if __name__ == '__main__':
    print_test_header()
    unittest.main()
