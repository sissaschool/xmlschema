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
from textwrap import dedent
from xmlschema import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


class TestXsdAssert(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')
    schema_class = XMLSchema11

    def test_base_api(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="intRange">
                <xs:attribute name="min" type="xs:int"/>
                <xs:attribute name="max" type="xs:int"/>
                <xs:assert test="@min le @max"/>
            </xs:complexType>
            <xs:element name="root" type="intRange"/>
        </xs:schema>
        """))

        self.assertEqual(len(schema.types['intRange'].assertions), 1)
        assertion = schema.types['intRange'].assertions[0]

        self.assertEqual(repr(assertion), "XsdAssert(test='@min le @max')")

        self.assertTrue(assertion.built)
        assertion.build()
        self.assertTrue(assertion.built)

        self.assertEqual(len(list(iter(assertion))), 0)

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="intRange">
                <xs:simpleContent>
                    <xs:extension base="xs:string">
                        <xs:attribute name="min" type="xs:int"/>
                        <xs:attribute name="max" type="xs:int"/>
                        <xs:assert test="@min le @max"/>
                    </xs:extension>
                </xs:simpleContent>
            </xs:complexType>
            <xs:element name="root" type="intRange"/>
        </xs:schema>
        """))

        assertion = schema.types['intRange'].assertions[0]
        self.assertEqual(len(list(iter(assertion))), 0)
        self.assertEqual(repr(assertion), "XsdAssert(test='@min le @max')")

        self.assertTrue(schema.is_valid('<root min="2" max="4">foo</root>'))
        self.assertFalse(schema.is_valid('<root min="5" max="4">foo</root>'))

    def test_assertion_on_text_content(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="rootType" mixed="true">
                <xs:sequence>
                    <xs:element name="child"/>
                </xs:sequence>
                <xs:assert test="child/text()='foo'"/>
            </xs:complexType>
            <xs:element name="root" type="rootType"/>
        </xs:schema>
        """))

        self.assertTrue(schema.is_valid('<root>bar<child>foo</child></root>'))
        self.assertFalse(schema.is_valid('<root>bar<child></child></root>'))
        self.assertFalse(schema.is_valid('<root>bar<child> foo </child></root>'))

    def test_invalid_assertions(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:simpleType name="rootType">
                <xs:restriction base="xs:string"/>
                <xs:assert test="child/text()='foo'"/>
            </xs:simpleType>
            <xs:element name="root" type="rootType"/>
        </xs:schema>
        """), validation='lax')

        self.assertEqual(len(schema.all_errors), 1)

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="rootType" mixed="true">
                <xs:sequence>
                    <xs:element name="child"/>
                </xs:sequence>
                <xs:assert/>
            </xs:complexType>
            <xs:element name="root" type="rootType"/>
        </xs:schema>
        """), validation='lax')

        self.assertEqual(len(schema.all_errors), 1)

    def test_xpath_default_namespace(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                targetNamespace="http://xmlschema.test/ns"
                xmlns="http://xmlschema.test/ns"
                xpathDefaultNamespace="http://xmlschema.test/ns"
                elementFormDefault="qualified">
            <xs:complexType name="rootType" mixed="true">
                <xs:sequence>
                    <xs:element name="child"/>
                </xs:sequence>
                <xs:assert test="child/text()='foo'"/>
                <xs:assert test="true()"
                    xpathDefaultNamespace="http://xmlschema.test/other-ns"/>
            </xs:complexType>
            <xs:element name="root" type="rootType"/>
        </xs:schema>
        """))

        self.assertEqual(len(schema.types['rootType'].assertions), 2)
        assertion = schema.types['rootType'].assertions[0]
        self.assertEqual(assertion.xpath_default_namespace, 'http://xmlschema.test/ns')

        assertion = schema.types['rootType'].assertions[1]
        self.assertEqual(assertion.xpath_default_namespace, 'http://xmlschema.test/other-ns')

        self.assertIsNone(schema.validate(
            '<root xmlns="http://xmlschema.test/ns"><child>foo</child></root>'
        ))
        self.assertFalse(schema.is_valid('<root><child>foo</child></root>'))

    def test_typed_value(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="rootType" mixed="true">
                <xs:sequence>
                    <xs:element name="child" type="xs:int"/>
                </xs:sequence>
                <xs:assert test="child le 10"/>
            </xs:complexType>
            <xs:element name="root" type="rootType"/>
        </xs:schema>
        """))

        self.assertTrue(schema.is_valid('<root><child>10</child></root>'))
        self.assertTrue(schema.is_valid('<root><child>9</child></root>'))
        self.assertFalse(schema.is_valid('<root><child>11</child></root>'))
        self.assertFalse(schema.is_valid('<root><child>ten</child></root>'))


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('XSD 1.1 assertions')
