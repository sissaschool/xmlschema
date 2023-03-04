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
from textwrap import dedent
from xml.etree.ElementTree import Element

from xmlschema import XMLSchemaParseError, XMLSchemaModelError
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


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
            base, '<xs:sequence><xs:element name="A"/><xs:element name="C"/></xs:sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base,
            '<xs:sequence><xs:element name="A" minOccurs="0"/><xs:element name="B"/></xs:sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base,
            '<xs:sequence><xs:element name="B" minOccurs="0"/><xs:element name="A"/></xs:sequence>',
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
            base,
            '<xs:sequence><xs:element name="C" minOccurs="0"/><xs:element name="A"/></xs:sequence>'
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
        self.check_complex_restriction(base, '<xs:all><xs:element name="A"/></xs:all>',
                                       XMLSchemaParseError)

    def test_choice_group_restriction(self):
        base = """
        <xs:choice maxOccurs="2">
            <xs:element name="A"/>
            <xs:element name="B"/>
            <xs:element name="C"/>
        </xs:choice>
        """
        self.check_complex_restriction(
            base, '<xs:choice><xs:element name="A"/><xs:element name="C"/></xs:choice>')
        self.check_complex_restriction(
            base,
            '<xs:choice maxOccurs="2"><xs:element name="C"/><xs:element name="A"/></xs:choice>',
            XMLSchemaParseError if self.schema_class.XSD_VERSION == '1.0' else None
        )
        self.check_complex_restriction(
            base,
            '<xs:choice maxOccurs="2"><xs:element name="A"/><xs:element name="C"/></xs:choice>',
        )

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

    def test_upa_violation_with_wildcard(self):
        self.check_schema("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
            targetNamespace="tns" xmlns:ns="tns" elementFormDefault="unqualified">

            <xs:complexType name="baseType">
                <xs:sequence>
                   <xs:any processContents="lax" minOccurs="0" maxOccurs="unbounded"></xs:any>
                </xs:sequence>
            </xs:complexType>

            <xs:complexType name="addressType">
                <xs:complexContent>
                    <xs:extension base="ns:baseType">
                        <xs:sequence>
                            <xs:element name="state" type="xs:string" />
                            <xs:element name="currency" type="xs:string" />
                            <xs:element name="zip" type="xs:int" />
                        </xs:sequence>
                    </xs:extension>
                </xs:complexContent>
            </xs:complexType>

        </xs:schema>
        """, XMLSchemaModelError if self.schema_class.XSD_VERSION == '1.0' else None)

    def test_content_type(self):
        # Ref: https://www.w3.org/TR/xmlschema11-1/#Complex_Type_Definition_details

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

            <xs:complexType name="emptyContentType1">
                <xs:attribute name="a1"/>
            </xs:complexType>

            <xs:simpleType name="emptyContentType2">
                <xs:restriction base="xs:string">
                    <xs:length value="0"/>
                </xs:restriction>
            </xs:simpleType>

            <xs:complexType name="emptyContentType3">
                <xs:simpleContent>
                    <xs:extension base="emptyContentType2">
                        <xs:attribute name="a1"/>
                    </xs:extension>
                </xs:simpleContent>
            </xs:complexType>

            <xs:simpleType name="simpleContentType1">
                <xs:restriction base="xs:string">
                    <xs:length value="1"/>
                </xs:restriction>
            </xs:simpleType>

            <xs:complexType name="simpleContentType2">
                <xs:simpleContent>
                    <xs:extension base="xs:string">
                        <xs:attribute name="a1"/>
                    </xs:extension>
                </xs:simpleContent>
            </xs:complexType>

            <xs:complexType name="elementOnlyContentType">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>

            <xs:complexType name="mixedContentType" mixed="true">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>

        </xs:schema>
        """)

        xsd_type = schema.types['emptyContentType1']
        self.assertTrue(xsd_type.is_empty())
        self.assertFalse(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'empty')

        xsd_type = schema.types['emptyContentType2']
        self.assertTrue(xsd_type.is_empty())
        self.assertFalse(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'empty')

        xsd_type = schema.types['emptyContentType3']
        self.assertTrue(xsd_type.is_empty())
        self.assertFalse(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'empty')

        xsd_type = schema.types['simpleContentType1']
        self.assertFalse(xsd_type.is_empty())
        self.assertTrue(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'simple')

        xsd_type = schema.types['simpleContentType2']
        self.assertFalse(xsd_type.is_empty())
        self.assertTrue(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'simple')

        xsd_type = schema.types['elementOnlyContentType']
        self.assertFalse(xsd_type.is_empty())
        self.assertFalse(xsd_type.has_simple_content())
        self.assertTrue(xsd_type.is_element_only())
        self.assertFalse(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'element-only')

        xsd_type = schema.types['mixedContentType']
        self.assertFalse(xsd_type.is_empty())
        self.assertFalse(xsd_type.has_simple_content())
        self.assertFalse(xsd_type.is_element_only())
        self.assertTrue(xsd_type.has_mixed_content())
        self.assertEqual(xsd_type.content_type_label, 'mixed')

    def test_is_empty(self):
        schema = self.check_schema("""
            <xs:complexType name="emptyType1"/>

            <xs:complexType name="emptyType2">
                <xs:sequence/>
            </xs:complexType>

            <xs:complexType name="emptyType3">
                <xs:complexContent>
                    <xs:restriction base="xs:anyType"/>
                </xs:complexContent>
            </xs:complexType>

            <xs:complexType name="notEmptyType1">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>

            <xs:complexType name="notEmptyType2">
                <xs:complexContent>
                    <xs:extension base="xs:anyType"/>
                </xs:complexContent>
            </xs:complexType>
            """)

        self.assertTrue(schema.types['emptyType1'].is_empty())
        self.assertTrue(schema.types['emptyType2'].is_empty())
        self.assertTrue(schema.types['emptyType3'].is_empty())
        self.assertFalse(schema.types['notEmptyType1'].is_empty())
        self.assertFalse(schema.types['notEmptyType2'].is_empty())

    def test_restriction_with_empty_particle__issue_323(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:complexType name="ED" mixed="true">
            <xs:complexContent>
              <xs:restriction base="xs:anyType">
                <xs:sequence>
                  <xs:element name="reference" type="xs:string" minOccurs="0" maxOccurs="1"/>
                  <xs:element name="thumbnail" type="thumbnail" minOccurs="0" maxOccurs="1"/>
                </xs:sequence>
              </xs:restriction>
            </xs:complexContent>
          </xs:complexType>

          <xs:complexType name="thumbnail" mixed="true">
            <xs:complexContent>
              <xs:restriction base="ED">
                <xs:sequence>
                    <xs:element name="reference" type="xs:string" minOccurs="0" maxOccurs="0"/>
                    <xs:element name="thumbnail" type="thumbnail" minOccurs="0" maxOccurs="0"/>
                </xs:sequence>
              </xs:restriction>
            </xs:complexContent>
          </xs:complexType>

          <xs:complexType name="ST" mixed="true">
            <xs:complexContent>
              <xs:restriction base="ED">
                <xs:sequence>
                    <xs:element name="reference" type="xs:string" minOccurs="0" maxOccurs="0"/>
                    <xs:element name="thumbnail" type="ED" minOccurs="0" maxOccurs="0"/>
                </xs:sequence>
              </xs:restriction>
            </xs:complexContent>
          </xs:complexType>
        </xs:schema>"""), build=False)

        self.assertIsNone(schema.build())
        self.assertTrue(schema.built)

    def test_mixed_content_extension__issue_334(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

            <xs:complexType name="mixedContentType" mixed="true">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>

            <xs:element name="foo">
              <xs:complexType>
                <xs:complexContent>
                  <xs:extension base="mixedContentType">
                    <xs:attribute name="bar" type="xs:string" use="required" />
                  </xs:extension>
                </xs:complexContent>
              </xs:complexType>
            </xs:element>

        </xs:schema>
        """))

        self.assertTrue(schema.types['mixedContentType'].mixed)
        self.assertTrue(schema.elements['foo'].type.mixed)
        self.assertTrue(schema.elements['foo'].type.content.mixed)

    def test_mixed_content_extension__issue_337(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <!-- Valid schema: the derived type adds empty content -->
            <xs:complexType name="baseType" mixed="true">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>
            <xs:complexType name="derivedType">
                <xs:complexContent>
                    <xs:extension base="baseType">
                    </xs:extension>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertTrue(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'mixed')
        self.assertTrue(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'mixed')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <!-- Invalid schema: the derived type adds element-only content -->
                <xs:complexType name="baseType" mixed="true">
                    <xs:sequence>
                        <xs:element name="elem1"/>
                    </xs:sequence>
                </xs:complexType>
                <xs:complexType name="derivedType">
                    <xs:complexContent>
                        <xs:extension base="baseType">
                            <xs:sequence>
                                <xs:element name="elem2"/>
                            </xs:sequence>
                        </xs:extension>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>"""))

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <!-- Valid schema: the derived type adds mixed content -->
            <xs:complexType name="baseType" mixed="true">
            </xs:complexType>
            <xs:complexType name="derivedType">
                <xs:complexContent mixed="true">
                    <xs:extension base="baseType">
                        <xs:sequence>
                            <xs:element name="elem1"/>
                        </xs:sequence>
                    </xs:extension>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertTrue(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'mixed')
        self.assertTrue(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'mixed')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <!-- Invalid schema: the derived type adds element-only content -->
                <xs:complexType name="baseType" mixed="true">
                </xs:complexType>
                <xs:complexType name="derivedType">
                    <xs:complexContent>
                        <xs:extension base="baseType">
                            <xs:sequence>
                                <xs:element name="elem1"/>
                            </xs:sequence>
                        </xs:extension>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>"""))

    def test_empty_content_extension(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="baseType" mixed="false">
            </xs:complexType>
            <xs:complexType name="derivedType" mixed="true">
                <xs:complexContent>
                    <xs:extension base="baseType"/>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertFalse(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'empty')
        self.assertTrue(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'mixed')

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="baseType" mixed="false">
            </xs:complexType>
            <xs:complexType name="derivedType">
                <xs:complexContent>
                    <xs:extension base="baseType"/>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertFalse(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'empty')
        self.assertFalse(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'empty')

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="baseType" mixed="false">
            </xs:complexType>
            <xs:complexType name="derivedType">
                <xs:complexContent>
                    <xs:extension base="baseType">
                        <xs:sequence>
                            <xs:element name="elem1"/>
                        </xs:sequence>
                    </xs:extension>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertFalse(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'empty')
        self.assertFalse(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'element-only')

    def test_element_only_content_extension(self):

        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="baseType" mixed="false">
                <xs:sequence>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:complexType>
            <xs:complexType name="derivedType">
                <xs:complexContent>
                    <xs:extension base="baseType"/>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertFalse(schema.types['baseType'].mixed)
        self.assertEqual(schema.types['baseType'].content_type_label, 'element-only')
        self.assertFalse(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'element-only')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <!-- Invalid schema: the derived type adds mixed content -->
                <xs:complexType name="baseType">
                    <xs:sequence>
                        <xs:element name="elem1"/>
                    </xs:sequence>
                </xs:complexType>
                <xs:complexType name="derivedType" mixed="true">
                    <xs:complexContent>
                        <xs:extension base="baseType">
                            <xs:sequence>
                                <xs:element name="elem2"/>
                            </xs:sequence>
                        </xs:extension>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>"""))

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <!-- Invalid schema: the derived type adds mixed content -->
                <xs:complexType name="baseType">
                    <xs:sequence>
                        <xs:element name="elem1"/>
                    </xs:sequence>
                </xs:complexType>
                <xs:complexType name="derivedType" mixed="true">
                    <xs:complexContent>
                        <xs:extension base="baseType"/>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>"""))

    def test_any_type_extension(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="derivedType">
                <xs:complexContent>
                    <xs:extension base="xs:anyType"/>
                </xs:complexContent>
            </xs:complexType>
        </xs:schema>"""))

        self.assertTrue(schema.types['derivedType'].mixed)
        self.assertEqual(schema.types['derivedType'].content_type_label, 'mixed')

        xsd_source = dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:complexType name="derivedType">
                    <xs:complexContent mixed="true">
                        <xs:extension base="xs:anyType">
                            <xs:sequence>
                                <xs:element name="elem1"/>
                            </xs:sequence>
                        </xs:extension>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>""")

        if self.schema_class.XSD_VERSION == '1.0':
            with self.assertRaises(XMLSchemaModelError):
                self.schema_class(xsd_source)
        else:
            schema = self.schema_class(xsd_source)
            self.assertTrue(schema.types['derivedType'].mixed)
            self.assertEqual(schema.types['derivedType'].content_type_label, 'mixed')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <!-- Invalid schema: derived type content is element-only -->
                <xs:complexType name="derivedType">
                    <xs:complexContent>
                        <xs:extension base="xs:anyType">
                            <xs:sequence>
                                <xs:element name="elem1"/>
                            </xs:sequence>
                        </xs:extension>
                    </xs:complexContent>
                </xs:complexType>
            </xs:schema>"""))


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
        xsd_type.decode(Element('a', attrib={'min': '10', 'max': '19'}))
        self.assertTrue(xsd_type.is_valid(Element('a', attrib={'min': '10', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(Element('a', attrib={'min': '19', 'max': '19'})))
        self.assertFalse(xsd_type.is_valid(Element('a', attrib={'min': '25', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(Element('a', attrib={'min': '25', 'max': '100'})))

    def test_sequence_extension(self):
        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:complexType name="base">
                <xs:openContent mode="suffix">
                  <xs:any namespace="tns1" processContents="lax"/>
                </xs:openContent>
                <xs:sequence>
                  <xs:element name="a" maxOccurs="unbounded"/>
                  <xs:element name="b" minOccurs="0"/>
                  <xs:element name="c" minOccurs="0"/>
                </xs:sequence>
              </xs:complexType>

              <xs:complexType name="ext">
                <xs:complexContent>
                  <xs:extension base="base">
                    <xs:sequence>
                      <xs:element name="d" minOccurs="0"/>
                    </xs:sequence>
                  </xs:extension>
                </xs:complexContent>
              </xs:complexType>
            </xs:schema>""")

        base_group = schema.types['base'].content
        self.assertEqual(base_group.model, 'sequence')
        self.assertEqual(base_group[0].name, 'a')
        self.assertEqual(base_group[1].name, 'b')
        self.assertEqual(base_group[2].name, 'c')
        self.assertEqual(len(base_group), 3)

        ext_group = schema.types['ext'].content
        self.assertEqual(ext_group.model, 'sequence')
        self.assertEqual(len(ext_group), 2)
        self.assertEqual(ext_group[0].model, 'sequence')
        self.assertEqual(ext_group[1].model, 'sequence')
        self.assertEqual(ext_group[0][0].name, 'a')
        self.assertEqual(ext_group[0][1].name, 'b')
        self.assertEqual(ext_group[0][2].name, 'c')
        self.assertEqual(len(ext_group[0]), 3)
        self.assertEqual(ext_group[1][0].name, 'd')
        self.assertEqual(len(ext_group[1]), 1)


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD complex types with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
