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

from xmlschema import XMLSchemaParseError, XMLSchemaModelError
from xmlschema.etree import etree_element
from xmlschema.tests import XsdValidatorTestCase
from xmlschema.validators import XMLSchema11


class TestXsdComplexType(XsdValidatorTestCase):

    def check_complex_restriction(self, base, restriction, expected=None, **kwargs):
        content = 'complex' if self.content_pattern.search(base) else 'simple'
        source = """
            <xs:complexType name="targetType">
                {0}
            </xs:complexType>
            <xs:complexType name="restrictedType">
                <xs:{1}Content>
                    <xs:restriction base="targetType">
                        {2}
                    </xs:restriction>
                </xs:{1}Content>
            </xs:complexType>
            """.format(base.strip(), content, restriction.strip())
        self.check_schema(source, expected, **kwargs)

    def test_element_restrictions(self):
        base = """
        <xs:sequence>
            <xs:element name="A" maxOccurs="7"/>
            <xs:element name="B" type="xs:string"/>
            <xs:element name="C" fixed="5"/>
        </xs:sequence>
        """
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
                <xs:element name="A" maxOccurs="6"/>
                <xs:element name="B" type="xs:NCName"/>
                <xs:element name="C" fixed="5"/>
            </xs:sequence>
            """
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
                <xs:element name="A" maxOccurs="8"/> <!-- <<< More occurrences -->
                <xs:element name="B" type="xs:NCName"/>
                <xs:element name="C" fixed="5"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
                <xs:element name="A" maxOccurs="6"/>
                <xs:element name="B" type="float"/> <!-- <<< Not a derived type -->
                <xs:element name="C" fixed="5"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
                <xs:element name="A" maxOccurs="6"/>
                <xs:element name="B" type="xs:NCName"/>
                <xs:element name="C" fixed="3"/> <!-- <<< Different fixed value -->
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
                <xs:element name="A" maxOccurs="6" nillable="true"/> <!-- <<< nillable is True -->
                <xs:element name="B" type="xs:NCName"/>
                <xs:element name="C" fixed="5"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )

    def test_sequence_group_restriction(self):
        # Meaningless sequence group
        base = """
        <xs:sequence>
            <xs:sequence>
                <xs:element name="A"/>
                <xs:element name="B"/>
            </xs:sequence>
        </xs:sequence>
        """
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
              <xs:element name="A"/>
              <xs:element name="B"/>
            </xs:sequence>
            """
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
              <xs:element name="A"/>
              <xs:element name="C"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )

        base = """
        <xs:sequence>
            <xs:element name="A"/>
            <xs:element name="B" minOccurs="0"/>
        </xs:sequence>
        """
        self.check_complex_restriction(base, '<xs:sequence><xs:element name="A"/></xs:sequence>')
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="B"/></xs:sequence>', XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="C"/></xs:sequence>', XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="A"/><xs:element name="B"/></xs:sequence>'
        )
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="A"/><xs:element name="C"/></xs:sequence>', XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="A" minOccurs="0"/><xs:element name="B"/></xs:sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="B" minOccurs="0"/><xs:element name="A"/></xs:sequence>',
            XMLSchemaParseError
        )

    def test_all_group_restriction(self):
        base = """
        <xs:all>
            <xs:element name="A"/>
            <xs:element name="B" minOccurs="0"/>
            <xs:element name="C" minOccurs="0"/>
        </xs:all>
        """
        self.check_complex_restriction(
            base, restriction="""
            <xs:all>
              <xs:element name="A"/>
              <xs:element name="C"/>
            </xs:all>
        """)
        self.check_complex_restriction(
            base, restriction="""
            <xs:all>
              <xs:element name="C" minOccurs="0"/>
              <xs:element name="A"/>
            </xs:all>
            """, expected=XMLSchemaParseError if self.schema_class.XSD_VERSION == '1.0' else None
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
              <xs:element name="A"/>
              <xs:element name="C"/>
            </xs:sequence>
            """)
        self.check_complex_restriction(
            base, '<xs:sequence><xs:element name="C" minOccurs="0"/><xs:element name="A"/></xs:sequence>',
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
              <xs:element name="C" minOccurs="0"/>
              <xs:element name="A" minOccurs="0"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, restriction="""
            <xs:sequence>
              <xs:element name="A"/>
              <xs:element name="X"/>
            </xs:sequence>
            """, expected=XMLSchemaParseError
        )

        base = """
        <xs:all>
            <xs:element name="A" minOccurs="0" maxOccurs="0"/>
        </xs:all>
        """
        self.check_complex_restriction(base, '<xs:all><xs:element name="A"/></xs:all>', XMLSchemaParseError)

    def test_choice_group_restriction(self):
        base = """
        <xs:choice maxOccurs="2">
            <xs:element name="A"/>
            <xs:element name="B"/>
            <xs:element name="C"/>
        </xs:choice>
        """
        self.check_complex_restriction(base, '<xs:choice><xs:element name="A"/><xs:element name="C"/></xs:choice>')
        self.check_complex_restriction(
            base, '<xs:choice maxOccurs="2"><xs:element name="C"/><xs:element name="A"/></xs:choice>',
            XMLSchemaParseError
        )

        self.check_complex_restriction(
            base, '<xs:choice maxOccurs="2"><xs:element name="A"/><xs:element name="C"/></xs:choice>',
        )

        base = """
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified" attributeFormDefault="unqualified">

    <xs:complexType name="b">
       <xs:choice>     
         <xs:element name="a" minOccurs="0" maxOccurs="5"/>
         <xs:element name="b" minOccurs="0" maxOccurs="5"/>
         <xs:element name="c" minOccurs="0" maxOccurs="unbounded"/>
         <xs:any namespace="http://one.com/" processContents="skip" minOccurs="2" maxOccurs="2"/>
       </xs:all>
    </xs:complexType>
    
    <xs:complexType name="e">
      <xs:complexContent>
        <xs:extension base="b">
          <xs:all>
            <xs:element name="e" minOccurs="0" maxOccurs="1"/>
            <xs:element name="f" minOccurs="0" maxOccurs="4"/>
            <xs:any notNamespace="http://two.com/" processContents="skip" minOccurs="2" maxOccurs="2"/>
          </xs:all>
        </xs:extension>
      </xs:complexContent>
    </xs:complexType> 
    
    <xs:element name="doc" type="e"/> 
          

</xs:schema>"""

    def test_occurs_restriction(self):
        base = """
        <xs:sequence minOccurs="3" maxOccurs="10">
            <xs:element name="A"/>
        </xs:sequence>
        """
        self.check_complex_restriction(
            base, '<xs:sequence minOccurs="3" maxOccurs="7"><xs:element name="A"/></xs:sequence>')
        self.check_complex_restriction(
            base, '<xs:sequence minOccurs="4" maxOccurs="10"><xs:element name="A"/></xs:sequence>')
        self.check_complex_restriction(
            base, '<xs:sequence minOccurs="3" maxOccurs="11"><xs:element name="A"/></xs:sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<xs:sequence minOccurs="2" maxOccurs="10"><xs:element name="A"/></xs:sequence>',
            XMLSchemaParseError
        )

    def test_recursive_complex_type(self):
        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="elemA" type="typeA"/>
                <xs:complexType name="typeA">
                    <xs:sequence>
                        <xs:element ref="elemA" minOccurs="0" maxOccurs="5"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:schema>""")
        self.assertEqual(schema.elements['elemA'].type, schema.types['typeA'])

    def test_upa_violations(self):
        self.check_schema("""
            <xs:complexType name="typeA">
                <xs:sequence>
                    <xs:sequence minOccurs="0" maxOccurs="unbounded">
                        <xs:element name="A"/>
                        <xs:element name="B"/>
                    </xs:sequence>
                    <xs:element name="A" minOccurs="0"/>
                </xs:sequence>
            </xs:complexType>""", XMLSchemaModelError)

        self.check_schema("""
            <xs:complexType name="typeA">
                <xs:sequence>
                    <xs:sequence minOccurs="0" maxOccurs="unbounded">
                        <xs:element name="B"/>
                        <xs:element name="A"/>
                    </xs:sequence>
                    <xs:element name="A" minOccurs="0"/>
                </xs:sequence>
            </xs:complexType>""")


class TestXsd11ComplexType(TestXsdComplexType):

    schema_class = XMLSchema11

    def test_complex_type_assertion(self):
        schema = self.check_schema("""
            <xs:complexType name="intRange">
              <xs:attribute name="min" type="xs:int"/>
              <xs:attribute name="max" type="xs:int"/>
              <xs:assert test="@min le @max"/>
            </xs:complexType>""")

        xsd_type = schema.types['intRange']
        xsd_type.decode(etree_element('a', attrib={'min': '10', 'max': '19'}))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '10', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '19', 'max': '19'})))
        self.assertFalse(xsd_type.is_valid(etree_element('a', attrib={'min': '25', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '25', 'max': '100'})))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
