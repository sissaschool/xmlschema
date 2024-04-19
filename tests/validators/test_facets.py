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
import decimal
import pathlib
from xml.etree import ElementTree
from textwrap import dedent

from xmlschema import XMLSchema10, XMLSchema11, XMLSchemaValidationError, \
    XMLSchemaParseError
from xmlschema.names import XSD_NAMESPACE, XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, \
    XSD_WHITE_SPACE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_MAX_INCLUSIVE, \
    XSD_MAX_EXCLUSIVE, XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_ENUMERATION, \
    XSD_PATTERN, XSD_ASSERTION
from xmlschema.validators import XsdEnumerationFacets, XsdPatternFacets, XsdAssertionFacet


class TestXsdFacets(unittest.TestCase):

    schema_class = XMLSchema10
    st_xsd_file: pathlib.Path
    st_schema: XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.st_xsd_file = pathlib.Path(__file__).absolute().parent.parent.joinpath(
            'test_cases/features/decoder/simple-types.xsd'
        )
        cls.st_schema = cls.schema_class(cls.st_xsd_file.as_uri())

    def test_white_space_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="string1">
                    <xs:restriction base="xs:string">
                        <xs:whiteSpace value="preserve"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string2">
                    <xs:restriction base="xs:string">
                        <xs:whiteSpace value="replace"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string3">
                    <xs:restriction base="xs:string">
                        <xs:whiteSpace value="collapse"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        xsd_type = schema.types['string1']
        self.assertEqual(xsd_type.white_space, 'preserve')
        white_space_facet = xsd_type.get_facet(XSD_WHITE_SPACE)
        self.assertIsNone(white_space_facet(' \t alpha\n  beta '))

        xsd_type = schema.types['string2']
        self.assertEqual(xsd_type.white_space, 'replace')
        white_space_facet = xsd_type.get_facet(XSD_WHITE_SPACE)
        self.assertIsNone(white_space_facet('  alpha  beta '))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            white_space_facet(' \t alpha\n  beta ')
        self.assertIn('Reason: value contains tabs or newlines', str(ec.exception))

        xsd_type = schema.types['string3']
        self.assertEqual(xsd_type.white_space, 'collapse')
        white_space_facet = xsd_type.get_facet(XSD_WHITE_SPACE)
        self.assertIsNone(white_space_facet('alpha beta'))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            white_space_facet('  alpha  beta ')
        self.assertIn('Reason: value contains non collapsed white spaces', str(ec.exception))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="string1">
                        <xs:restriction base="xs:string">
                            <xs:whiteSpace value="invalid"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn(
            "value must be one of ['preserve', 'replace', 'collapse']", str(ec.exception)
        )

    def test_white_space_restriction(self):
        valid_derivations = [
            ('preserve', 'preserve'), ('preserve', 'replace'), ('preserve', 'collapse'),
            ('replace', 'replace'), ('replace', 'collapse'), ('collapse', 'collapse'),
        ]
        for base_value, value in valid_derivations:
            schema = self.schema_class(dedent(f"""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="string1">
                        <xs:restriction base="xs:string">
                            <xs:whiteSpace value="{base_value}"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="string2">
                        <xs:restriction base="string1">
                            <xs:whiteSpace value="{value}"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

            self.assertEqual(schema.types['string1'].white_space, base_value)
            self.assertEqual(schema.types['string2'].white_space, value)

        invalid_derivations = [
            ('replace', 'preserve'), ('collapse', 'preserve'), ('collapse', 'replace')
        ]
        for base_value, value in invalid_derivations:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="string1">
                            <xs:restriction base="xs:string">
                                <xs:whiteSpace value="{base_value}"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="string2">
                            <xs:restriction base="string1">
                                <xs:whiteSpace value="{value}"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_length_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="username">
                    <xs:restriction base="xs:NCName">
                        <xs:length value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        length_facet = schema.types['username'].get_facet(XSD_LENGTH)
        self.assertIsNone(length_facet('a' * 8))

        for value in ['', 'a' * 7, 'a' * 9]:
            with self.assertRaises(XMLSchemaValidationError) as ec:
                length_facet(value)
            self.assertIn('Reason: length has to be 8', str(ec.exception))

    def test_length_facet_restriction(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="username">
                    <xs:restriction base="xs:NCName">
                        <xs:length value="8"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="username2">
                    <xs:restriction base="username">
                        <xs:length value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        length_facet = schema.types['username'].get_facet(XSD_LENGTH)
        self.assertIsNone(length_facet('a' * 8))
        length_facet2 = schema.types['username2'].get_facet(XSD_LENGTH)
        self.assertIsNone(length_facet2('a' * 8))
        self.assertIsNot(length_facet, length_facet2)

        # Not applied on xs:QName: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="qname1">
                    <xs:restriction base="xs:QName">
                        <xs:length value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        length_facet = schema.types['qname1'].get_facet(XSD_LENGTH)
        self.assertIsNone(length_facet('a' * 8))
        self.assertIsNone(length_facet('a' * 10))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="username">
                        <xs:restriction base="xs:NCName">
                            <xs:length value="8"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="username2">
                        <xs:restriction base="username">
                            <xs:length value="12"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("base facet has a different length (8)", str(ec.exception))

    def test_min_length_facet(self):
        xsd_type = self.st_schema.types['none_empty_string']
        min_length_facet = xsd_type.get_facet(XSD_MIN_LENGTH)
        self.assertIsNone(min_length_facet(' '))
        self.assertIsNone(min_length_facet(' ' * 75))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            min_length_facet('')
        self.assertIn('value length cannot be lesser than 1', str(ec.exception))

        # Not applied on xs:QName: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="qname1">
                    <xs:restriction base="xs:QName">
                        <xs:minLength value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        min_length_facet = schema.types['qname1'].get_facet(XSD_MIN_LENGTH)
        self.assertIsNone(min_length_facet('abc'))

    def test_min_length_facet_restriction(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="string20">
                    <xs:restriction base="xs:string">
                        <xs:minLength value="20"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string30">
                    <xs:restriction base="string20">
                        <xs:minLength value="30"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        self.assertEqual(schema.types['string20'].get_facet(XSD_MIN_LENGTH).value, 20)
        self.assertEqual(schema.types['string30'].get_facet(XSD_MIN_LENGTH).value, 30)

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="string40">
                        <xs:restriction base="xs:string">
                            <xs:minLength value="40"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="string30">
                        <xs:restriction base="string40">
                            <xs:minLength value="30"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_max_length_facet(self):
        xsd_type = self.st_schema.types['string_75']
        max_length_facet = xsd_type.get_facet(XSD_MAX_LENGTH)
        self.assertIsNone(max_length_facet(''))
        self.assertIsNone(max_length_facet(' '))
        self.assertIsNone(max_length_facet(' ' * 75))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            max_length_facet(' ' * 76)
        self.assertIn('value length cannot be greater than 75', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            max_length_facet(None)
        self.assertIn("invalid type <class 'NoneType'> provided", str(ec.exception))

        # Not applied on xs:QName: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="qname1">
                    <xs:restriction base="xs:QName">
                        <xs:maxLength value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        max_length_facet = schema.types['qname1'].get_facet(XSD_MAX_LENGTH)
        self.assertIsNone(max_length_facet('a' * 10))

    def test_max_length_facet_restriction(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="string30">
                    <xs:restriction base="xs:string">
                        <xs:maxLength value="30"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string20">
                    <xs:restriction base="string30">
                        <xs:maxLength value="20"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        self.assertEqual(schema.types['string30'].get_facet(XSD_MAX_LENGTH).value, 30)
        self.assertEqual(schema.types['string20'].get_facet(XSD_MAX_LENGTH).value, 20)

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="string30">
                        <xs:restriction base="xs:string">
                            <xs:maxLength value="30"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="string40">
                        <xs:restriction base="string30">
                            <xs:maxLength value="40"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_min_inclusive_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="min_type">
                    <xs:restriction base="xs:integer">
                        <xs:minInclusive value="0"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['min_type'].get_facet(XSD_MIN_INCLUSIVE)
        self.assertIsNone(facet(0))
        self.assertIsNone(facet(100))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(-1)
        self.assertIn('value has to be greater or equal than 0', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet('')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="min_type">
                        <xs:restriction base="xs:integer">
                            <xs:minInclusive value=""/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_min_inclusive_facet_restriction(self):
        for base_facet in ['minInclusive', 'maxInclusive']:
            schema = self.schema_class(dedent(f"""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="type1">
                        <xs:restriction base="xs:integer">
                            <xs:{base_facet} value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="type2">
                        <xs:restriction base="type1">
                            <xs:minInclusive value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

            facet = schema.types['type1'].get_facet(f'{{{XSD_NAMESPACE}}}{base_facet}')
            self.assertIsNone(facet(0))
            facet2 = schema.types['type2'].get_facet(XSD_MIN_INCLUSIVE)
            self.assertIsNone(facet2(0))
            self.assertIsNot(facet, facet2)

        for base_facet in ['minInclusive', 'minExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['maxInclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="-1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['minExclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_min_exclusive_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="min_type">
                    <xs:restriction base="xs:integer">
                        <xs:minExclusive value="0"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['min_type'].get_facet(XSD_MIN_EXCLUSIVE)
        self.assertIsNone(facet(1))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(0)
        self.assertIn('value has to be greater than 0', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet('')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="min_type">
                        <xs:restriction base="xs:integer">
                            <xs:minExclusive value=""/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_min_exclusive_facet_restriction(self):
        for base_facet in ['minInclusive', 'minExclusive']:
            schema = self.schema_class(dedent(f"""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="type1">
                        <xs:restriction base="xs:integer">
                            <xs:{base_facet} value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="type2">
                        <xs:restriction base="type1">
                            <xs:minExclusive value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

            facet = schema.types['type1'].get_facet(f'{{{XSD_NAMESPACE}}}{base_facet}')
            self.assertIsNone(facet(1))
            facet2 = schema.types['type2'].get_facet(XSD_MIN_EXCLUSIVE)
            self.assertIsNone(facet2(1))
            self.assertIsNot(facet, facet2)

        for base_facet in ['maxInclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['minInclusive', 'minExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['maxInclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="-1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:minExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_max_inclusive_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="max_type">
                    <xs:restriction base="xs:integer">
                        <xs:maxInclusive value="0"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['max_type'].get_facet(XSD_MAX_INCLUSIVE)
        self.assertIsNone(facet(-1))
        self.assertIsNone(facet(0))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(1)
        self.assertIn('value has to be less than or equal than 0', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet('')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="min_type">
                        <xs:restriction base="xs:integer">
                            <xs:maxInclusive value=""/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_max_inclusive_facet_restriction(self):
        for base_facet in ['minInclusive', 'maxInclusive']:
            schema = self.schema_class(dedent(f"""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="type1">
                        <xs:restriction base="xs:integer">
                            <xs:{base_facet} value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="type2">
                        <xs:restriction base="type1">
                            <xs:maxInclusive value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

            facet = schema.types['type1'].get_facet(f'{{{XSD_NAMESPACE}}}{base_facet}')
            self.assertIsNone(facet(0))
            facet2 = schema.types['type2'].get_facet(XSD_MAX_INCLUSIVE)
            self.assertIsNone(facet2(0))
            self.assertIsNot(facet, facet2)

        for base_facet in ['maxInclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="-1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['minInclusive', 'minExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['minExclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxInclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_max_exclusive_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="max_type">
                    <xs:restriction base="xs:integer">
                        <xs:maxExclusive value="0"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['max_type'].get_facet(XSD_MAX_EXCLUSIVE)
        self.assertIsNone(facet(-1))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(0)
        self.assertIn('value has to be lesser than 0', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet('')

        with self.assertRaises(XMLSchemaParseError):
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="min_type">
                        <xs:restriction base="xs:integer">
                            <xs:maxExclusive value=""/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

    def test_max_exclusive_facet_restriction(self):
        for base_facet in ['maxInclusive', 'maxExclusive']:
            schema = self.schema_class(dedent(f"""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="type1">
                        <xs:restriction base="xs:integer">
                            <xs:{base_facet} value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="type2">
                        <xs:restriction base="type1">
                            <xs:maxExclusive value="0"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

            facet = schema.types['type1'].get_facet(f'{{{XSD_NAMESPACE}}}{base_facet}')
            self.assertIsNone(facet(-1))
            facet2 = schema.types['type2'].get_facet(XSD_MAX_EXCLUSIVE)
            self.assertIsNone(facet2(-1))
            self.assertIsNot(facet, facet2)

        for base_facet in ['minInclusive', 'minExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['maxInclusive', 'maxExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="-1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

        for base_facet in ['minInclusive', 'minExclusive']:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="type1">
                            <xs:restriction base="xs:integer">
                                <xs:{base_facet} value="1"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="type2">
                            <xs:restriction base="type1">
                                <xs:maxExclusive value="0"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_total_digits_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_integer">
                    <xs:restriction base="xs:integer">
                        <xs:totalDigits value="4"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['restricted_integer'].get_facet(XSD_TOTAL_DIGITS)
        self.assertIsNone(facet(9999))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(99999)
        self.assertIn('the number of digits has to be lesser or equal than 4', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet(None)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_integer">
                    <xs:restriction base="xs:integer">
                        <xs:totalDigits value="a"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertIn("invalid literal", str(schema.all_errors[0]))
        facet = schema.types['restricted_integer'].get_facet(XSD_TOTAL_DIGITS)
        self.assertEqual(facet.value, 9999)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_integer">
                    <xs:restriction base="xs:integer">
                        <xs:totalDigits value="0"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertIn("value must be positive", str(schema.all_errors[0]))
        facet = schema.types['restricted_integer'].get_facet(XSD_TOTAL_DIGITS)
        self.assertEqual(facet.value, 9999)

    def test_fraction_digits_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_decimal">
                    <xs:restriction base="xs:decimal">
                        <xs:fractionDigits value="2"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['restricted_decimal'].get_facet(XSD_FRACTION_DIGITS)
        self.assertIsNone(facet(decimal.Decimal('99.99')))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet(decimal.Decimal('99.999'))
        self.assertIn('fraction digits has to be lesser or equal than 2', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError):
            facet(None)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_decimal">
                    <xs:restriction base="xs:decimal">
                        <xs:fractionDigits value="a"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertIn("invalid literal", str(schema.all_errors[0]))
        facet = schema.types['restricted_decimal'].get_facet(XSD_FRACTION_DIGITS)
        self.assertEqual(facet.value, 9999)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="restricted_decimal">
                    <xs:restriction base="xs:decimal">
                        <xs:fractionDigits value="-1"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertIn("value must be non negative", str(schema.all_errors[0]))
        facet = schema.types['restricted_decimal'].get_facet(XSD_FRACTION_DIGITS)
        self.assertEqual(facet.value, 9999)

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="restricted_integer">
                        <xs:restriction base="xs:integer">
                            <xs:fractionDigits value="2"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("value must be 0 for types derived from xs:integer", str(ec.exception))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="restricted_double">
                        <xs:restriction base="xs:double">
                            <xs:fractionDigits value="2"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("can be applied only to types derived from xs:decimal", str(ec.exception))

    def test_digits_facets_restriction(self):
        for facet in ['totalDigits', 'fractionDigits']:
            schema = self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="decimal1">
                            <xs:restriction base="xs:decimal">
                                <xs:{facet} value="4"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="decimal2">
                            <xs:restriction base="decimal1">
                                <xs:{facet} value="1"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

            self.assertTrue(schema.types['decimal1'].is_valid(decimal.Decimal('.01')))
            self.assertFalse(schema.types['decimal2'].is_valid(decimal.Decimal('.01')))

            with self.assertRaises(XMLSchemaParseError) as ec:
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="decimal1">
                            <xs:restriction base="xs:decimal">
                                <xs:{facet} value="2"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="decimal2">
                            <xs:restriction base="decimal1">
                                <xs:{facet} value="3"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

            self.assertIn("invalid restriction: base value is lower", str(ec.exception))

    def test_enumeration_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="enum1">
                    <xs:restriction base="xs:string">
                        <xs:enumeration value="one"/>
                        <xs:enumeration value="two"/>
                        <xs:enumeration value="three"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="enum2">
                    <xs:restriction base="enum1">
                        <xs:enumeration value="one"/>
                        <xs:enumeration value="two"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        self.assertTrue(schema.types['enum1'].is_valid('one'))
        self.assertTrue(schema.types['enum1'].is_valid('two'))
        self.assertTrue(schema.types['enum1'].is_valid('three'))
        self.assertFalse(schema.types['enum1'].is_valid('four'))

        self.assertTrue(schema.types['enum2'].is_valid('one'))
        self.assertTrue(schema.types['enum2'].is_valid('two'))
        self.assertFalse(schema.types['enum2'].is_valid('three'))
        self.assertFalse(schema.types['enum2'].is_valid('four'))

        facet = schema.types['enum2'].get_facet(XSD_ENUMERATION)
        self.assertIsInstance(facet, XsdEnumerationFacets)

        elem = ElementTree.Element(XSD_ENUMERATION, value='three')
        facet.append(elem)
        self.assertTrue(schema.types['enum2'].is_valid('three'))
        facet[-1] = elem
        self.assertTrue(schema.types['enum2'].is_valid('three'))
        del facet[-1]
        self.assertFalse(schema.types['enum2'].is_valid('three'))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="enum1">
                        <xs:restriction base="xs:string">
                            <xs:enumeration/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("missing required attribute 'value'", str(ec.exception))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="enum1">
                        <xs:restriction base="xs:NOTATION">
                            <xs:enumeration value="unknown:notation1"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("prefix 'unknown' not found in namespace map", str(ec.exception))

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="enum1">
                        <xs:restriction base="xs:NOTATION">
                            <xs:enumeration value="notation1"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("'notation1' must match a notation declaration", str(ec.exception))

    def test_enumeration_facet_representation(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="enum1">
                    <xs:restriction base="xs:string">
                        <xs:enumeration value="one"/>
                        <xs:enumeration value="two"/>
                        <xs:enumeration value="three"/>
                        <xs:enumeration value="four"/>
                        <xs:enumeration value="five"/>
                        <xs:enumeration value="six"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['enum1'].get_facet(XSD_ENUMERATION)
        self.assertEqual(
            repr(facet), "XsdEnumerationFacets(['one', 'two', 'three', 'four', 'five', ...])"
        )
        facet.pop()
        self.assertEqual(
            repr(facet), "XsdEnumerationFacets(['one', 'two', 'three', 'four', 'five'])"
        )

    def test_enumeration_facet_with_float_type(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="enum1">
                    <xs:restriction base="xs:double">
                        <xs:enumeration value="1.0"/>
                        <xs:enumeration value="2.0"/>
                        <xs:enumeration value="INF"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['enum1'].get_facet(XSD_ENUMERATION)
        self.assertIsNone(facet(1.0))
        self.assertIsNone(facet(2.0))
        self.assertIsNone(facet(float('inf')))
        self.assertRaises(XMLSchemaValidationError, facet, '3.0')
        self.assertRaises(XMLSchemaValidationError, facet, 3.0)
        self.assertRaises(XMLSchemaValidationError, facet, float('-inf'))
        self.assertRaises(XMLSchemaValidationError, facet, float('nan'))

        facet.append(ElementTree.Element(XSD_ENUMERATION, value='-INF'))
        self.assertIsNone(facet(float('-inf')))

        facet.append(ElementTree.Element(XSD_ENUMERATION, value='NaN'))
        self.assertIsNone(facet(float('nan')))

    def test_enumeration_facet_derivation(self):
        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="enum1">
                        <xs:restriction base="xs:string">
                            <xs:enumeration value="one"/>
                            <xs:enumeration value="two"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="enum2">
                        <xs:restriction base="enum1">
                            <xs:enumeration value="one"/>
                            <xs:enumeration value="two"/>
                            <xs:enumeration value="three"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("failed validating 'three'", str(ec.exception))

    def test_pattern_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="pattern1">
                    <xs:restriction base="xs:string">
                        <xs:pattern value="\\w+"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['pattern1'].get_facet(XSD_PATTERN)
        self.assertIsInstance(facet, XsdPatternFacets)
        self.assertIsNone(facet('abc'))
        self.assertRaises(XMLSchemaValidationError, facet, '')
        self.assertRaises(XMLSchemaValidationError, facet, 'a;')

        self.assertRaises(XMLSchemaValidationError, facet, 10)
        self.assertRaises(XMLSchemaValidationError, facet, None)

        self.assertIs(schema.types['pattern1'].patterns, facet)
        self.assertIs(facet[0], schema.root[0][0][0])
        self.assertEqual(facet.patterns[0].pattern, r'^(?:\w+)$(?!\n\Z)')  # translated pattern

        # Test MutableSequence API
        facet.append(ElementTree.Element(XSD_PATTERN, value=r'\s+'))
        self.assertEqual(len(facet), 2)
        self.assertEqual(facet.patterns[1].pattern, r'^(?:\s+)$(?!\n\Z)')
        facet[1] = (ElementTree.Element(XSD_PATTERN, value=r'\S+'))
        self.assertEqual(facet.patterns[1].pattern, r'^(?:\S+)$(?!\n\Z)')
        del facet[1]
        self.assertEqual(len(facet), 1)

        schema = self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="pattern1">
                        <xs:restriction base="xs:string">
                            <xs:pattern/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="pattern2">
                        <xs:restriction base="xs:string">
                            <xs:pattern value="]"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""), validation='lax')

        self.assertEqual(len(schema.all_errors), 2)
        self.assertIn("missing required attribute 'value'", str(schema.all_errors[0]))
        self.assertIn("unexpected meta character ']' at position 0", str(schema.all_errors[1]))

    def test_get_annotation__issue_255(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="enum1">
                    <xs:restriction base="xs:string">
                        <xs:enumeration value="one">
                            <xs:annotation>
                                <xs:documentation>1st facet</xs:documentation>
                            </xs:annotation>
                        </xs:enumeration>
                        <xs:enumeration value="two"/>
                        <xs:enumeration value="three">
                            <xs:annotation>
                                <xs:documentation>3rd facet</xs:documentation>
                            </xs:annotation>
                        </xs:enumeration>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['enum1'].get_facet(XSD_ENUMERATION)
        self.assertIsInstance(facet, XsdEnumerationFacets)
        self.assertEqual(facet.annotation.documentation[0].text, '1st facet')
        self.assertEqual(facet.get_annotation(0).documentation[0].text, '1st facet')
        self.assertIsNone(facet.get_annotation(1))
        self.assertEqual(facet.get_annotation(2).documentation[0].text, '3rd facet')

        with self.assertRaises(IndexError):
            facet.get_annotation(3)

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="pattern1">
                    <xs:restriction base="xs:string">
                        <xs:pattern value="\\w+"/>
                        <xs:pattern value=".+">
                            <xs:annotation>
                                <xs:documentation>2nd facet</xs:documentation>
                            </xs:annotation>
                        </xs:pattern>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['pattern1'].get_facet(XSD_PATTERN)
        self.assertIsInstance(facet, XsdPatternFacets)
        self.assertIsNone(facet.get_annotation(0))
        self.assertEqual(facet.get_annotation(1).documentation[0].text, '2nd facet')

        with self.assertRaises(IndexError):
            facet.get_annotation(2)

    def test_fixed_value(self):
        with self.assertRaises(XMLSchemaParseError) as ec:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:simpleType name="string30">
                        <xs:restriction base="xs:string">
                            <xs:maxLength value="30" fixed="true"/>
                        </xs:restriction>
                    </xs:simpleType>
                    <xs:simpleType name="string20">
                        <xs:restriction base="string30">
                            <xs:maxLength value="20"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn("'maxLength' facet value is fixed to 30", str(ec.exception))

    def test_restriction_on_list__issue_396(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="list_of_strings">
                <xs:simpleType>
                  <xs:restriction>
                    <xs:simpleType>
                      <xs:list>
                        <xs:simpleType>
                          <xs:restriction base="xs:string">
                            <xs:minLength value="5"/>
                            <xs:maxLength value="6"/>
                          </xs:restriction>
                        </xs:simpleType>
                      </xs:list>
                    </xs:simpleType>
                    <xs:minLength value="1"/>
                    <xs:maxLength value="6"/>
                  </xs:restriction>
                </xs:simpleType>
              </xs:element>
            </xs:schema>"""))

        self.assertTrue(schema.is_valid('<list_of_strings>abcde</list_of_strings>'))
        self.assertTrue(schema.is_valid('<list_of_strings>abcdef</list_of_strings>'))
        self.assertFalse(schema.is_valid('<list_of_strings>abcd</list_of_strings>'))
        self.assertFalse(schema.is_valid('<list_of_strings>abcdefg</list_of_strings>'))
        self.assertFalse(schema.is_valid('<list_of_strings>     </list_of_strings>'))

        self.assertTrue(schema.is_valid('<list_of_strings>abcde abcde abcde '
                                        'abcde abcde abcde</list_of_strings>'))
        self.assertFalse(schema.is_valid('<list_of_strings>abcde abcde abcde '
                                         'abcde abcd abcde</list_of_strings>'))
        self.assertFalse(schema.is_valid('<list_of_strings>abcde abcde abcde '
                                         'abcde abcde abcde abcde</list_of_strings>'))


class TestXsd11Identities(TestXsdFacets):

    schema_class = XMLSchema11

    def test_explicit_timezone_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="date1">
                    <xs:restriction base="xs:date">
                        <xs:explicitTimezone value="optional"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date2">
                    <xs:restriction base="xs:date">
                        <xs:explicitTimezone value="required"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date3">
                    <xs:restriction base="xs:date">
                        <xs:explicitTimezone value="prohibited"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        self.assertTrue(schema.types['date1'].is_valid('2020-03-01'))
        self.assertTrue(schema.types['date2'].is_valid('2020-03-01Z'))
        self.assertFalse(schema.types['date2'].is_valid('2020-03-01'))
        self.assertTrue(schema.types['date3'].is_valid('2020-03-01'))
        self.assertFalse(schema.types['date3'].is_valid('2020-03-01Z'))

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="date1">
                    <xs:restriction base="xs:date">
                        <xs:explicitTimezone value="none"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertIn("value must be one of ['optional',", str(schema.all_errors[0]))

    def test_explicit_timezone_facet_restriction(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="date1">
                    <xs:restriction base="xs:date">
                        <xs:explicitTimezone value="optional"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date2">
                    <xs:restriction base="date1">
                        <xs:explicitTimezone value="required"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date3">
                    <xs:restriction base="date1">
                        <xs:explicitTimezone value="prohibited"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date4">
                    <xs:restriction base="date2">
                        <xs:explicitTimezone value="required"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="date5">
                    <xs:restriction base="date3">
                        <xs:explicitTimezone value="prohibited"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        self.assertTrue(schema.types['date1'].is_valid('2020-03-01'))
        self.assertTrue(schema.types['date2'].is_valid('2020-03-01Z'))
        self.assertFalse(schema.types['date2'].is_valid('2020-03-01'))
        self.assertTrue(schema.types['date3'].is_valid('2020-03-01'))
        self.assertFalse(schema.types['date3'].is_valid('2020-03-01Z'))

        derivations = [('required', 'prohibited'), ('required', 'optional'),
                       ('prohibited', 'required'), ('prohibited', 'optional')]

        for base_facet, facet in derivations:
            with self.assertRaises(XMLSchemaParseError):
                self.schema_class(dedent(f"""\
                    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                        <xs:simpleType name="date1">
                            <xs:restriction base="xs:date">
                                <xs:explicitTimezone value="{base_facet}"/>
                            </xs:restriction>
                        </xs:simpleType>
                        <xs:simpleType name="date2">
                            <xs:restriction base="date1">
                                <xs:explicitTimezone value="{facet}"/>
                            </xs:restriction>
                        </xs:simpleType>
                    </xs:schema>"""))

    def test_assertion_facet(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="string1">
                    <xs:restriction base="xs:string">
                        <xs:assertion test="true()"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string2">
                    <xs:restriction base="xs:string">
                        <xs:assertion test="last()"
                                      xpathDefaultNamespace="http://xpath.test/ns"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string3">
                    <xs:restriction base="xs:string">
                        <xs:assertion test="position()"/>
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="integer_list">
                    <xs:list itemType="xs:integer"/>
                </xs:simpleType>
                <xs:simpleType name="integer_vector">
                   <xs:restriction base="integer_list">
                       <xs:assertion test="count($value) eq 3" />
                   </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""))

        facet = schema.types['string1'].get_facet(XSD_ASSERTION)
        self.assertIsInstance(facet, XsdAssertionFacet)
        self.assertIsNone(facet(''))
        self.assertEqual(facet.xpath_default_namespace, '')

        facet = schema.types['string2'].get_facet(XSD_ASSERTION)
        self.assertIsInstance(facet, XsdAssertionFacet)
        self.assertEqual(facet.xpath_default_namespace, 'http://xpath.test/ns')
        with self.assertRaises(XMLSchemaValidationError) as ec:
            facet('')
        self.assertIn("[err:XPDY0002] context item size is undefined", str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            schema.types['string3'].get_facet(XSD_ASSERTION)('')
        self.assertIn("[err:XPDY0002] context item position is undefined", str(ec.exception))

        facet = schema.types['integer_vector'].get_facet(XSD_ASSERTION)
        self.assertIsNone(facet([1, 2, 3]))
        self.assertIsInstance(facet, XsdAssertionFacet)
        self.assertEqual(facet.parser.variable_types, {'value': 'xs:anySimpleType'})

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:simpleType name="string1">
                    <xs:restriction base="xs:string">
                        <xs:assertion />
                    </xs:restriction>
                </xs:simpleType>
                <xs:simpleType name="string2">
                    <xs:restriction base="xs:string">
                        <xs:assertion test="???"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), validation='lax')

        self.assertEqual(len(schema.all_errors), 2)
        self.assertIn("missing attribute 'test'", str(schema.all_errors[0]))
        self.assertIn("[err:XPST0003] unexpected '?' symbol", str(schema.all_errors[1]))

    def test_use_xpath3(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="rootType"/>
                <xs:simpleType name="rootType">
                    <xs:restriction base="xs:string">
                        <xs:assertion test="let $foo := 'bar' return $foo"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>"""), use_xpath3=True)

        self.assertTrue(schema.use_xpath3)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class(dedent("""\
                <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                    <xs:element name="root" type="rootType"/>
                    <xs:simpleType name="rootType">
                        <xs:restriction base="xs:string">
                            <xs:assertion test="let $foo := 'bar' return $foo"/>
                        </xs:restriction>
                    </xs:simpleType>
                </xs:schema>"""))

        self.assertIn('XPST0003', str(ctx.exception))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD facets with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
