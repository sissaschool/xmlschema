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

from xmlschema import XMLSchemaParseError, XMLSchemaValidationError
from xmlschema.names import XSD_LIST, XSD_UNION
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


class TestXsdSimpleTypes(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')

    def test_simple_types(self):
        # Issue #54: set list or union schema element.
        xs = self.check_schema("""
        <xs:simpleType name="test_list">
            <xs:annotation/>
            <xs:list itemType="xs:string"/>
        </xs:simpleType>
        <xs:simpleType name="test_union">
            <xs:annotation/>
            <xs:union memberTypes="xs:string xs:integer xs:boolean"/>
        </xs:simpleType>
        """)
        xs.types['test_list'].parse(xs.root[0])  # elem.tag == 'simpleType'
        self.assertEqual(xs.types['test_list'].elem.tag, XSD_LIST)
        xs.types['test_union'].parse(xs.root[1])  # elem.tag == 'simpleType'
        self.assertEqual(xs.types['test_union'].elem.tag, XSD_UNION)

    def test_variety_property(self):
        schema = self.check_schema("""
        <xs:simpleType name="atomicType">
            <xs:restriction base="xs:string"/>
        </xs:simpleType>

        <xs:simpleType name="listType">
            <xs:list itemType="xs:string"/>
        </xs:simpleType>
        <xs:simpleType name="listType2">
            <xs:restriction base="listType"/>
        </xs:simpleType>

        <xs:simpleType name="unionType">
            <xs:union memberTypes="xs:string xs:integer xs:boolean"/>
        </xs:simpleType>
        <xs:simpleType name="unionType2">
            <xs:restriction base="unionType"/>
        </xs:simpleType>
        """)
        self.assertEqual(schema.types['atomicType'].variety, 'atomic')
        self.assertEqual(schema.types['listType'].variety, 'list')
        self.assertEqual(schema.types['listType2'].variety, 'list')
        self.assertEqual(schema.types['unionType'].variety, 'union')
        self.assertEqual(schema.types['unionType2'].variety, 'union')

    def test_final_attribute(self):
        self.check_schema("""
        <xs:simpleType name="aType" final="list restriction">
            <xs:restriction base="xs:string"/>
        </xs:simpleType>
        """)

    def test_facets(self):
        # Issue #55 and a near error (derivation from xs:integer)
        self.check_schema("""
        <xs:simpleType name="dtype">
            <xs:restriction base="xs:decimal">
                <xs:fractionDigits value="3" />
                <xs:totalDigits value="20" />
            </xs:restriction>
        </xs:simpleType>
        <xs:simpleType name="ntype">
            <xs:restriction base="dtype">
                <xs:totalDigits value="3" />
                <xs:fractionDigits value="1" />
            </xs:restriction>
        </xs:simpleType>
        """)
        self.check_schema("""
        <xs:simpleType name="dtype">
            <xs:restriction base="xs:integer">
                <xs:fractionDigits value="3" /> <!-- <<< value must be 0 -->
                <xs:totalDigits value="20" />
            </xs:restriction>
        </xs:simpleType>
        """, XMLSchemaParseError)

        # Issue #56
        self.check_schema("""
        <xs:simpleType name="mlengthparent">
            <xs:restriction base="xs:string">
                <xs:maxLength value="200"/>
            </xs:restriction>
        </xs:simpleType>
        <xs:simpleType name="mlengthchild">
            <xs:restriction base="mlengthparent">
                <xs:maxLength value="20"/>
            </xs:restriction>
        </xs:simpleType>
        """)

    def test_union_restrictions(self):
        # Wrong union restriction (not admitted facets, see issue #67)
        self.check_schema(r"""
        <xs:simpleType name="Percentage">
            <xs:restriction base="Integer">
                <xs:minInclusive value="0"/>
                <xs:maxInclusive value="100"/>
            </xs:restriction>
        </xs:simpleType>
        <xs:simpleType name="Integer">
            <xs:union memberTypes="xs:int IntegerString"/>
        </xs:simpleType>
        <xs:simpleType name="IntegerString">
            <xs:restriction base="xs:string">
                <xs:pattern value="-?[0-9]+(\.[0-9]+)?%"/>
            </xs:restriction>
        </xs:simpleType>
        """, XMLSchemaParseError)

    def test_date_time_facets(self):
        self.check_schema("""
            <xs:simpleType name="restricted_date">
                <xs:restriction base="xs:date">
                    <xs:minInclusive value="1900-01-01"/>
                    <xs:maxInclusive value="2030-12-31"/>
                </xs:restriction>
            </xs:simpleType>""")

        self.check_schema("""
            <xs:simpleType name="restricted_year">
                <xs:restriction base="xs:gYear">
                    <xs:minInclusive value="1900"/>
                    <xs:maxInclusive value="2030"/>
                </xs:restriction>
            </xs:simpleType>""")

    def test_is_empty(self):
        schema = self.check_schema("""
            <xs:simpleType name="emptyType1">
                <xs:restriction base="xs:string">
                    <xs:maxLength value="0"/>
                </xs:restriction>
            </xs:simpleType>

            <xs:simpleType name="emptyType2">
                <xs:restriction base="xs:string">
                    <xs:length value="0"/>
                </xs:restriction>
            </xs:simpleType>

            <xs:simpleType name="emptyType3">
                <xs:restriction base="xs:string">
                    <xs:enumeration value=""/>
                </xs:restriction>
            </xs:simpleType>

            <xs:simpleType name="notEmptyType1">
                <xs:restriction base="xs:string">
                    <xs:enumeration value=" "/>
                </xs:restriction>
            </xs:simpleType>""")

        self.assertTrue(schema.types['emptyType1'].is_empty())
        self.assertTrue(schema.types['emptyType2'].is_empty())
        self.assertTrue(schema.types['emptyType3'].is_empty())
        self.assertFalse(schema.types['notEmptyType1'].is_empty())


class TestXsd11SimpleTypes(TestXsdSimpleTypes):

    schema_class = XMLSchema11

    def test_explicit_timezone_facet(self):
        schema = self.check_schema("""
            <xs:simpleType name='opt-tz-date'>
              <xs:restriction base='xs:date'>
                <xs:explicitTimezone value='optional'/>
              </xs:restriction>
            </xs:simpleType>
            <xs:simpleType name='req-tz-date'>
              <xs:restriction base='xs:date'>
                <xs:explicitTimezone value='required'/>
              </xs:restriction>
            </xs:simpleType>
            <xs:simpleType name='no-tz-date'>
              <xs:restriction base='xs:date'>
                <xs:explicitTimezone value='prohibited'/>
              </xs:restriction>
            </xs:simpleType>
            """)
        self.assertTrue(schema.types['req-tz-date'].is_valid('2002-10-10-05:00'))
        self.assertTrue(schema.types['req-tz-date'].is_valid('2002-10-10Z'))
        self.assertFalse(schema.types['req-tz-date'].is_valid('2002-10-10'))

    def test_assertion_facet(self):
        self.check_schema("""
            <xs:simpleType name='DimensionType'>
              <xs:restriction base='xs:integer'>
                <xs:assertion test='string-length($value) &lt; 2'/>
              </xs:restriction>
            </xs:simpleType>""")

        schema = self.check_schema("""
            <xs:simpleType name='MeasureType'>
              <xs:restriction base='xs:integer'>
                <xs:assertion test='$value &gt; 0'/>
              </xs:restriction>
            </xs:simpleType>""")
        self.assertTrue(schema.types['MeasureType'].is_valid('10'))
        self.assertFalse(schema.types['MeasureType'].is_valid('-1.5'))

        # Schema is valid but data value can't be compared with the string on the right
        schema = self.check_schema("""
            <xs:simpleType name='RestrictedDateTimeType'>
              <xs:restriction base='xs:dateTime'>
                <xs:assertion test="$value > '1999-12-31T23:59:59'"/>
              </xs:restriction>
            </xs:simpleType>""")
        self.assertFalse(schema.types['RestrictedDateTimeType'].is_valid('2000-01-01T12:00:00'))

        # '>' not supported between instances of 'DateTime' and 'str'
        with self.assertRaises(XMLSchemaValidationError):
            schema.types['RestrictedDateTimeType'].validate('2000-01-01T12:00:00')

        schema = self.check_schema("""
        <xs:simpleType name='RestrictedDateTimeType'>
          <xs:restriction base='xs:dateTime'>
            <xs:assertion test="$value > xs:dateTime('1999-12-31T23:59:59')"/>
          </xs:restriction>
        </xs:simpleType>""")
        self.assertTrue(schema.types['RestrictedDateTimeType'].is_valid('2000-01-01T12:00:00'))

        schema = self.check_schema("""
        <xs:simpleType name="Percentage">
          <xs:restriction base="xs:integer">
            <xs:assertion test="$value >= 0"/>
            <xs:assertion test="$value &lt;= 100"/>
          </xs:restriction>
        </xs:simpleType>""")
        self.assertTrue(schema.types['Percentage'].is_valid('10'))
        self.assertTrue(schema.types['Percentage'].is_valid('100'))
        self.assertTrue(schema.types['Percentage'].is_valid('0'))
        self.assertFalse(schema.types['Percentage'].is_valid('-1'))
        self.assertFalse(schema.types['Percentage'].is_valid('101'))
        self.assertFalse(schema.types['Percentage'].is_valid('90.1'))


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('simple types')
