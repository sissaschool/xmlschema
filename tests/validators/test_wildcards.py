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
from xmlschema.validators import XMLSchema11, XsdDefaultOpenContent
from xmlschema.testing import XsdValidatorTestCase


class TestXsdWildcards(XsdValidatorTestCase):

    def test_parsing(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:choice>
                <xs:any namespace=" ##any "/>
                <xs:any namespace="##local"/>
                <xs:any namespace="##other"/>
                <xs:any namespace="##targetNamespace foo bar"/>
                <xs:any namespace="##local foo bar"/>
                <xs:any namespace="##targetNamespace ##local foo bar"/>
              </xs:choice>
            </xs:group>
        </xs:schema>""")

        self.assertEqual(schema.groups['group1'][0].namespace, ('##any',))
        self.assertEqual(schema.groups['group1'][1].namespace, [''])
        self.assertEqual(schema.groups['group1'][2].namespace, ['##other'])
        self.assertEqual(schema.groups['group1'][3].namespace, ['tns1', 'foo', 'bar'])
        self.assertEqual(schema.groups['group1'][4].namespace, ['', 'foo', 'bar'])
        self.assertEqual(schema.groups['group1'][5].namespace, ['tns1', '', 'foo', 'bar'])

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:choice>
                <xs:any namespace="##all"/>
                <xs:any processContents="any"/>
              </xs:choice>
            </xs:group>
        </xs:schema>""", validation='lax')

        errors = schema.all_errors
        self.assertIn("wrong value '##all' in 'namespace' attribute", str(errors[1]))
        self.assertIn("value must be one of ['skip'", str(errors[0]))

    def test_overlap(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:choice>
                <xs:any namespace="##local"/>
                <xs:any namespace="##other"/>
                <xs:any namespace="##targetNamespace foo bar"/>
              </xs:choice>
            </xs:group>
        </xs:schema>""")

        any1, any2, any3 = schema.groups['group1'][:]

        self.assertFalse(any1.is_overlap(any2))
        self.assertFalse(any2.is_overlap(any1))
        self.assertTrue(any3.is_matching('{foo}x'))
        self.assertTrue(any3.is_matching('{bar}x'))
        self.assertTrue(any3.is_matching('{tns1}x'))

    def test_any_wildcard(self):
        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].namespace, ['##other'])

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="##targetNamespace" processContents="skip"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].namespace, [''])

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="ns ##targetNamespace" processContents="skip"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].namespace, ['ns', ''])

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="tns2 tns1 tns3" processContents="skip"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].namespace,
                         ['tns2', 'tns1', 'tns3'])
        self.assertEqual(schema.types['taggedType'].content[-1].min_occurs, 1)
        self.assertEqual(schema.types['taggedType'].content[-1].max_occurs, 1)

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any minOccurs="10" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].namespace, ('##any',))
        self.assertEqual(schema.types['taggedType'].content[-1].min_occurs, 10)
        self.assertIsNone(schema.types['taggedType'].content[-1].max_occurs)

    def test_any_attribute_wildcard(self):
        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:sequence>
          <xs:anyAttribute namespace="tns1:foo"/>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].attributes[None].namespace, ['tns1:foo'])

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:sequence>
          <xs:anyAttribute namespace="##targetNamespace"/>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].attributes[None].namespace, [''])

    def test_namespace_variants(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:sequence>
                <xs:any namespace="urn:a" processContents="skip"/>
                <xs:any namespace="" processContents="lax"/>
              </xs:sequence>
            </xs:group>
        </xs:schema>""")

        any1 = schema.groups['group1'][0]
        self.assertEqual(any1.namespace, ['urn:a'])
        any2 = schema.groups['group1'][1]
        self.assertEqual(any2.namespace, [])


class TestXsd11Wildcards(TestXsdWildcards):

    schema_class = XMLSchema11

    def test_parsing(self):
        super(TestXsd11Wildcards, self).test_parsing()
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:choice>
                <xs:any notNamespace="##all"/>
              </xs:choice>
            </xs:group>
        </xs:schema>""", validation='lax')

        errors = schema.all_errors
        self.assertIn("wrong value '##all' in 'notNamespace' attribute", str(errors[0]))

    def test_is_restriction(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tns1="tns1"
                targetNamespace="tns1">
            <xs:group name="group1">
              <xs:sequence>
                <!-- Case #1 -->
                <xs:any notNamespace="tns1"/>
                <xs:any notNamespace="tns1 tns2"/>
                <xs:any notNamespace="tns1 tns2 tns3"/>
                <!-- Case #2 -->
                <xs:any namespace="##any"/>
                <xs:any namespace="##local" notQName="a b"/>
                <xs:any namespace="##local" notQName="##defined a b"/>
                <!-- Case #3 -->
                <xs:any namespace="##any" notQName="a b c d"/>
                <xs:any namespace="##local" notQName="a b e"/>
                <xs:any notNamespace="##local" notQName="tns1:c d e"/>
              </xs:sequence>
            </xs:group>
        </xs:schema>""")

        any1, any2, any3 = schema.groups['group1'][:3]

        self.assertEqual(repr(any1), "Xsd11AnyElement(not_namespace=['tns1'], "
                                     "process_contents='strict', occurs=[1, 1])")
        self.assertEqual(repr(any2), "Xsd11AnyElement(not_namespace=['tns1', 'tns2'], "
                                     "process_contents='strict', occurs=[1, 1])")

        self.assertTrue(any1.is_restriction(any1))
        self.assertFalse(any1.is_restriction(any2))
        self.assertFalse(any1.is_restriction(any3))
        self.assertTrue(any2.is_restriction(any1))
        self.assertTrue(any2.is_restriction(any2))
        self.assertFalse(any2.is_restriction(any3))
        self.assertTrue(any3.is_restriction(any1))
        self.assertTrue(any3.is_restriction(any2))
        self.assertTrue(any3.is_restriction(any3))

        any1, any2, any3 = schema.groups['group1'][3:6]

        self.assertEqual(repr(any1), "Xsd11AnyElement(namespace=('##any',), "
                                     "process_contents='strict', occurs=[1, 1])")
        self.assertEqual(repr(any2), "Xsd11AnyElement(namespace=[''], "
                                     "process_contents='strict', occurs=[1, 1])")

        self.assertTrue(any1.is_restriction(any1))
        self.assertTrue(any2.is_restriction(any1))
        self.assertTrue(any3.is_restriction(any1))

        any1, any2, any3 = schema.groups['group1'][6:9]
        self.assertFalse(any2.is_restriction(any1))
        self.assertTrue(any3.is_restriction(any1))

    def test_wildcard_union(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:sequence>
                <xs:any namespace="tns1"/> <xs:any namespace="tns1 tns2"/>
                <xs:any notNamespace="tns1"/> <xs:any notNamespace="tns1 tns2"/>
                <xs:any namespace="##any"/> <xs:any notNamespace="tns1"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="tns1"/>
                <xs:any notNamespace="tns1"/> <xs:any namespace="##other"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="##local tns1"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="tns2"/>
              </xs:sequence>
            </xs:group>
        </xs:schema>""")

        # <xs:any namespace="tns1"/> <xs:any namespace="tns1 tns2"/>
        any1, any2 = schema.groups['group1'][:2]
        self.assertListEqual(any1.namespace, ['tns1'])
        any1.union(any2)
        self.assertListEqual(any1.namespace, ['tns1', 'tns2'])

        # <xs:any notNamespace="tns1"/> <xs:any notNamespace="tns1 tns2"/>
        any1, any2 = schema.groups['group1'][2:4]
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1'])
        any1.union(any2)
        self.assertListEqual(any1.not_namespace, ['tns1'])
        any2.union(any1)
        self.assertListEqual(any2.not_namespace, ['tns1'])

        # <xs:any namespace="##any"/> <xs:any notNamespace="tns1"/>
        any1, any2 = schema.groups['group1'][4:6]
        any1.union(any2)
        self.assertEqual(any1.namespace, ('##any',))
        self.assertEqual(any1.not_namespace, ())

        # <xs:any namespace="##other"/> <xs:any notNamespace="tns1"/>
        any1, any2 = schema.groups['group1'][6:8]
        any1.union(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1'])

        # <xs:any notNamespace="tns1"/> <xs:any namespace="##other"/>
        any1, any2 = schema.groups['group1'][8:10]
        any1.union(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1'])

        # <xs:any namespace="##other"/> <xs:any notNamespace="##local tns1"/>
        any1, any2 = schema.groups['group1'][10:12]
        any1.union(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['', 'tns1'])

        # <xs:any namespace="##other"/> <xs:any notNamespace="tns2"/>
        any1, any2 = schema.groups['group1'][12:14]
        any1.union(any2)
        self.assertListEqual(any1.namespace, ['##any'])
        self.assertListEqual(any1.not_namespace, [])

    def test_wildcard_intersection(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="tns1">
            <xs:group name="group1">
              <xs:sequence>
                <xs:any namespace="tns1"/> <xs:any namespace="tns1 tns2"/>
                <xs:any notNamespace="tns1"/> <xs:any notNamespace="tns1 tns2"/>
                <xs:any namespace="##any"/> <xs:any notNamespace="tns1"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="tns1"/>
                <xs:any notNamespace="tns1"/> <xs:any namespace="##other"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="##local tns1"/>
                <xs:any namespace="##other"/> <xs:any notNamespace="tns2"/>
                <xs:any namespace="##any" notQName="##defined qn1"/>
                <xs:any namespace="##local" notQName="##defined"/>
              </xs:sequence>
            </xs:group>
        </xs:schema>""")

        # <xs:any namespace="tns1"/> <xs:any namespace="tns1 tns2"/>
        any1, any2 = schema.groups['group1'][:2]
        self.assertListEqual(any1.namespace, ['tns1'])
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, ['tns1'])

        # <xs:any notNamespace="tns1"/> <xs:any notNamespace="tns1 tns2"/>
        any1, any2 = schema.groups['group1'][2:4]
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1'])
        any1.intersection(any2)
        self.assertListEqual(any1.not_namespace, ['tns1', 'tns2'])
        any2.intersection(any1)
        self.assertListEqual(any2.not_namespace, ['tns1', 'tns2'])

        # <xs:any namespace="##any"/> <xs:any notNamespace="tns1"/>
        any1, any2 = schema.groups['group1'][4:6]
        any1.intersection(any2)
        self.assertEqual(any1.namespace, [])
        self.assertEqual(any1.not_namespace, ['tns1'])

        # <xs:any namespace="##other"/> <xs:any notNamespace="tns1"/>
        any1, any2 = schema.groups['group1'][6:8]
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1', ''])

        # <xs:any notNamespace="tns1"/> <xs:any namespace="##other"/>
        any1, any2 = schema.groups['group1'][8:10]
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns1', ''])

        # <xs:any namespace="##other"/> <xs:any notNamespace="##local tns1"/>
        any1, any2 = schema.groups['group1'][10:12]
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['', 'tns1'])

        # <xs:any namespace="##other"/> <xs:any notNamespace="tns2"/>
        any1, any2 = schema.groups['group1'][12:14]
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, [])
        self.assertListEqual(any1.not_namespace, ['tns2', 'tns1', ''])

        # <xs:any namespace="##any" notQName="##defined qn1"/>
        # <xs:any namespace="##local" notQName="##defined"/>
        any1, any2 = schema.groups['group1'][14:16]
        any1.intersection(any2)
        self.assertListEqual(any1.namespace, [''])
        self.assertListEqual(any1.not_qname, ['##defined', 'qn1'])

    def test_open_content_mode_interleave(self):
        schema = self.check_schema("""
        <xs:element name="Book">
          <xs:complexType>
            <xs:openContent mode="interleave">
                <xs:any />
            </xs:openContent>
            <xs:sequence>
              <xs:element name="Title" type="xs:string"/>
              <xs:element name="Author" type="xs:string" />
              <xs:element name="Date" type="xs:gYear"/>
              <xs:element name="ISBN" type="xs:string"/>
              <xs:element name="Publisher" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:element>""")
        self.assertEqual(schema.elements['Book'].type.open_content.mode, 'interleave')
        self.assertEqual(schema.elements['Book'].type.open_content.any_element.min_occurs, 0)
        self.assertIsNone(schema.elements['Book'].type.open_content.any_element.max_occurs)

        schema = self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['name'].open_content.mode, 'interleave')

        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent />
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

    def test_open_content_mode_suffix(self):
        schema = self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="suffix">
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['name'].open_content.mode, 'suffix')
        self.assertEqual(schema.types['name'].open_content.any_element.min_occurs, 0)
        self.assertIsNone(schema.types['name'].open_content.any_element.max_occurs)

        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="suffix"/>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

    def test_open_content_mode_none(self):
        schema = self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="none"/>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['name'].open_content.mode, 'none')

        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="none">
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

    def test_open_content_allowed(self):
        self.check_schema("""
        <xs:complexType name="choiceType">
          <xs:openContent>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:choice>
            <xs:element name="a" type="xs:float"/>
            <xs:element name="b" type="xs:string"/>
            <xs:element name="c" type="xs:int"/>
          </xs:choice>
        </xs:complexType>""")

    def test_open_content_not_allowed(self):
        self.check_schema("""
        <xs:complexType name="wrongType">
          <xs:openContent>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:simpleContent>
                <xs:restriction base="xs:string" />
          </xs:simpleContent>
        </xs:complexType>""", XMLSchemaParseError)

        self.check_schema("""
        <xs:complexType name="wrongType">
          <xs:openContent>
            <xs:any namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:complexContent>
                <xs:restriction base="xs:anyType" />
          </xs:complexContent>
        </xs:complexType>""", XMLSchemaParseError)

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:openContent>
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:openContent>
                <xs:element name="root" />
            </xs:schema>""")

    def test_open_content_wrong_attributes(self):
        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="wrong"/>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="suffix">
            <xs:any minOccurs="1" namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

        self.check_schema("""
        <xs:complexType name="name">
          <xs:openContent mode="suffix">
            <xs:any maxOccurs="1000" namespace="##other" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="given" type="xs:string"/>
            <xs:element name="middle" type="xs:string" minOccurs="0"/>
            <xs:element name="family" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

    def test_default_open_content(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:defaultOpenContent>
                <xs:any namespace="##other" processContents="skip"/>
            </xs:defaultOpenContent>
            <xs:element name="root" />
        </xs:schema>""")
        self.assertIsInstance(schema.default_open_content, XsdDefaultOpenContent)
        self.assertFalse(schema.default_open_content.applies_to_empty)

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:defaultOpenContent appliesToEmpty="true">
                <xs:any namespace="##other" processContents="skip"/>
            </xs:defaultOpenContent>
            <xs:element name="root" />
        </xs:schema>""")
        self.assertTrue(schema.default_open_content.applies_to_empty)

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:defaultOpenContent appliesToEmpty="wrong">
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:defaultOpenContent>
                <xs:element name="root" />
            </xs:schema>""")

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" />
                <xs:defaultOpenContent>
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:defaultOpenContent>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:defaultOpenContent>
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:defaultOpenContent>
                <xs:defaultOpenContent>
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:defaultOpenContent>
                <xs:element name="root" />
            </xs:schema>""")

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" />
                <xs:defaultOpenContent mode="wrong">
                    <xs:any namespace="##other" processContents="skip"/>
                </xs:defaultOpenContent>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" />
                <xs:defaultOpenContent mode="none" />
            </xs:schema>""")

    def test_open_content_restriction(self):
        schema = self.check_schema("""
        <xs:complexType name="baseType">
          <xs:openContent>
            <xs:any namespace="tns1 tns2" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="foo" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>

        <xs:complexType name="derivedType">
          <xs:complexContent>
            <xs:restriction base="baseType">
              <xs:openContent>
                <xs:any namespace="tns1" processContents="skip"/>
              </xs:openContent>
              <xs:sequence>
                <xs:element name="foo" type="xs:string"/>
              </xs:sequence>
            </xs:restriction>
          </xs:complexContent>
        </xs:complexType>""")
        self.assertEqual(schema.types['derivedType'].content[0].name, 'foo')

        self.check_schema("""
        <xs:complexType name="baseType">
          <xs:openContent>
            <xs:any namespace="tns1 tns2" processContents="skip"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="foo" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>

        <xs:complexType name="derivedType">
          <xs:complexContent>
            <xs:restriction base="baseType">
              <xs:openContent>
                <xs:any namespace="##any" processContents="skip"/>
              </xs:openContent>
              <xs:sequence>
                <xs:element name="foo" type="xs:string"/>
              </xs:sequence>
            </xs:restriction>
          </xs:complexContent>
        </xs:complexType>""", XMLSchemaParseError)

    def test_open_content_extension(self):
        schema = self.check_schema("""
        <xs:complexType name="baseType">
          <xs:openContent mode="suffix">
            <xs:any namespace="tns1" processContents="lax"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="foo" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>

        <xs:complexType name="derivedType">
          <xs:complexContent>
            <xs:extension base="baseType">
              <xs:openContent>
                <xs:any namespace="tns1 tns2" processContents="lax"/>
              </xs:openContent>
              <xs:sequence>
                <xs:element name="bar" type="xs:string"/>
              </xs:sequence>
            </xs:extension>
          </xs:complexContent>
        </xs:complexType>""")
        self.assertEqual(schema.types['derivedType'].content[0][0].name, 'foo')
        self.assertEqual(schema.types['derivedType'].content[1][0].name, 'bar')

        self.check_schema("""
        <xs:complexType name="baseType">
          <xs:openContent mode="interleave">
            <xs:any namespace="tns1" processContents="lax"/>
          </xs:openContent>
          <xs:sequence>
            <xs:element name="foo" type="xs:string"/>
          </xs:sequence>
        </xs:complexType>

        <xs:complexType name="derivedType">
          <xs:complexContent>
            <xs:extension base="baseType">
              <xs:openContent>
                <!-- processContents="strict" is more restrictive -->
                <xs:any namespace="tns1 tns2" processContents="strict"/>
              </xs:openContent>
              <xs:sequence>
                <xs:element name="bar" type="xs:string"/>
              </xs:sequence>
            </xs:extension>
          </xs:complexContent>
        </xs:complexType>""", XMLSchemaParseError)

    def test_not_qname_attribute(self):
        self.assertIsInstance(self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:ns="tns1" targetNamespace="tns1">
            <xs:complexType name="type1">
              <xs:openContent>
                <xs:any notQName="ns:a" processContents="lax" />
              </xs:openContent>
            </xs:complexType>
        </xs:schema>"""), XMLSchema11)

        self.assertIsInstance(self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:ns="tns1" targetNamespace="tns1">
            <xs:complexType name="type1">
              <xs:sequence>
               <xs:any notQName="ns:a" processContents="lax" />
              </xs:sequence>
            </xs:complexType>
        </xs:schema>"""), XMLSchema11)

        self.check_schema("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:group name="group1">
              <xs:sequence>
                <xs:any notNamespace="##local" notQName="c d e"/>
              </xs:sequence>
            </xs:group>
        </xs:schema>""", XMLSchemaParseError)

    def test_any_wildcard(self):
        super(TestXsd11Wildcards, self).test_any_wildcard()
        self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any namespace="##other" notNamespace="##targetNamespace" />
          </xs:sequence>
        </xs:complexType>""", XMLSchemaParseError)

        schema = self.check_schema("""
        <xs:complexType name="taggedType">
          <xs:sequence>
            <xs:element name="tag" type="xs:string"/>
            <xs:any notNamespace="##targetNamespace" />
          </xs:sequence>
        </xs:complexType>""")
        self.assertEqual(schema.types['taggedType'].content[-1].not_namespace, [''])

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns1="tns1" targetNamespace="tns1">
            <xs:complexType name="taggedType">
              <xs:sequence>
                <xs:element name="tag" type="xs:string"/>
                <xs:any namespace="##targetNamespace" notQName="tns1:foo tns1:bar"/>
              </xs:sequence>
            </xs:complexType>
        </xs:schema>""")
        self.assertEqual(schema.types['taggedType'].content[-1].not_qname,
                         ['{tns1}foo', '{tns1}bar'])

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns1="tns1" targetNamespace="tns1">
            <xs:complexType name="taggedType">
              <xs:sequence>
                <xs:element name="tag" type="xs:string"/>
                <xs:any namespace="##targetNamespace" 
                notQName="##defined tns1:foo ##definedSibling"/>
              </xs:sequence>
            </xs:complexType>
        </xs:schema>""")
        self.assertEqual(schema.types['taggedType'].content[-1].not_qname,
                         ['##defined', '{tns1}foo', '##definedSibling'])

    def test_any_attribute_wildcard(self):
        super(TestXsd11Wildcards, self).test_any_attribute_wildcard()
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns1="tns1" targetNamespace="tns1">
            <xs:complexType name="taggedType">
              <xs:sequence>
                <xs:element name="tag" type="xs:string"/>
                <xs:any namespace="##other" processContents="skip"/>
              </xs:sequence>
              <xs:anyAttribute notQName="tns1:foo"/>
            </xs:complexType>
        </xs:schema>""")
        self.assertEqual(schema.types['taggedType'].attributes[None].namespace, ('##any',))
        self.assertEqual(schema.types['taggedType'].attributes[None].not_qname, ['{tns1}foo'])

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="barType">
              <xs:anyAttribute notNamespace="tns1"/>
            </xs:complexType>
        </xs:schema>""")
        self.assertEqual(schema.types['barType'].attributes[None].not_namespace, ['tns1'])
        self.assertEqual(repr(schema.types['barType'].attributes[None]),
                         "Xsd11AnyAttribute(not_namespace=['tns1'], process_contents='strict')")


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD wildcards with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
