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

from xmlschema import XMLSchemaParseError, XMLSchemaValidationError
from xmlschema.validators import XMLSchema11, XsdAttribute
from xmlschema.testing import XsdValidatorTestCase
from xmlschema.names import XSI_NAMESPACE, XSD_ANY_SIMPLE_TYPE, XSD_STRING


class TestXsdAttributes(XsdValidatorTestCase):

    def test_attribute_use(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="label" type="xs:string"/>
        </xs:attributeGroup>""")

        self.assertTrue(schema.attribute_groups['extra']['label'].is_optional())
        self.assertFalse(schema.attribute_groups['extra']['label'].is_required())
        self.assertFalse(schema.attribute_groups['extra']['label'].is_prohibited())

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="label" type="xs:string" use="required"/>
        </xs:attributeGroup>""")

        self.assertFalse(schema.attribute_groups['extra']['label'].is_optional())
        self.assertTrue(schema.attribute_groups['extra']['label'].is_required())
        self.assertFalse(schema.attribute_groups['extra']['label'].is_prohibited())

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="label" type="xs:string" use="prohibited"/>
        </xs:attributeGroup>""")
        self.assertNotIn('label', schema.attribute_groups['extra'])

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
        <xs:attributeGroup name="contact">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attribute ref="phone"/>  <!-- Missing "phone" attribute -->
        </xs:attributeGroup>
        """, XMLSchemaParseError)

        schema = self.schema_class("""<xs:schema
                xmlns:xs="http://www.w3.org/2001/XMLSchema" attributeFormDefault="qualified">
            <xs:attributeGroup name="contact">
                <xs:attribute name="name" type="xs:string"/>
                <xs:attribute ref="phone"/>
            </xs:attributeGroup>
            <xs:attribute name="phone" type="xs:string" default="555-0100"/>
        </xs:schema>""")
        self.assertTrue(schema.attribute_groups['contact']['phone'].qualified)
        self.assertEqual(schema.attribute_groups['contact']['phone'].default, '555-0100')

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone"/>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string" fixed="555-0100"/>
        """)
        self.assertEqual(schema.attribute_groups['extra']['phone'].fixed, '555-0100')
        self.assertIsNone(schema.attribute_groups['extra']['phone'].annotation)

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone" fixed="555-0100">
                <xs:annotation/>
            </xs:attribute>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string" fixed="555-0100"/>
        """)
        self.assertEqual(schema.attribute_groups['extra']['phone'].fixed, '555-0100')
        self.assertIsNotNone(schema.attribute_groups['extra']['phone'].annotation)

        self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone" fixed="555-0101"/>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string" fixed="555-0100"/>
        """, XMLSchemaParseError)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema("""
            <xs:attributeGroup name="extra">
                <xs:attribute ref="phone">
                    <xs:simpleType>
                        <xs:restriction base="xs:string"/>
                    </xs:simpleType>
                </xs:attribute>
            </xs:attributeGroup>""")
        self.assertEqual("a reference component cannot have child definitions/declarations",
                         ctx.exception.message)

    def test_name_attribute(self):
        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema('<xs:attribute type="xs:string"/>')
        self.assertEqual(ctx.exception.message, "missing required attribute 'name'")

        schema = self.check_schema('<xs:attribute type="xs:string"/>', validation='lax')
        self.assertEqual(len(schema.all_errors), 2)
        self.assertEqual(schema.all_errors[0].message, "missing required attribute 'name'")
        self.assertIn("missing key field '@name'", schema.all_errors[1].message)
        self.assertEqual(len(schema.attributes), 0)

        schema = self.check_schema('<xs:attribute type="xs:string"/>', validation='skip')
        self.assertEqual(len(schema.all_errors), 0)

        xsd_attribute = XsdAttribute(elem=schema.root[0], schema=schema, parent=None)
        self.assertIsNone(xsd_attribute.name)
        self.assertEqual(xsd_attribute.validation_attempted, 'full')

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema('<xs:attribute name="xmlns" type="xs:string"/>')
        self.assertEqual(ctx.exception.message, "an attribute name must be different from 'xmlns'")

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class("""<xs:schema
                    xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    targetNamespace="http://www.w3.org/2001/XMLSchema-instance" >
                <xs:attribute name="phone" type="xs:string"/>
            </xs:schema>""")
        self.assertEqual(ctx.exception.message,
                         "cannot add attributes in %r namespace" % XSI_NAMESPACE)

    def test_type_attribute(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone" type="xs:string"/>
        </xs:attributeGroup>""")
        self.assertEqual(schema.attribute_groups['extra']['phone'].type.name, XSD_STRING)

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone"/>
        </xs:attributeGroup>""")
        self.assertEqual(schema.attribute_groups['extra']['phone'].type.name, XSD_ANY_SIMPLE_TYPE)

        schema = self.check_schema('<xs:attribute name="foo" type="xs:foo"/>', validation='lax')
        self.assertEqual(schema.attributes['foo'].type.name, XSD_ANY_SIMPLE_TYPE)

        schema = self.check_schema('<xs:attribute name="foo" type="x:string"/>', validation='lax')
        self.assertEqual(schema.attributes['foo'].type.name, XSD_ANY_SIMPLE_TYPE)

        self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone" type="xs:string"/>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string"/>
        """, XMLSchemaParseError)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema("""
                <xs:attribute name="phone" type="xs:string">
                    <xs:simpleType>
                        <xs:restriction base="xs:string"/>
                    </xs:simpleType>
                </xs:attribute>""")
        self.assertEqual("ambiguous type definition for XSD attribute",
                         ctx.exception.message)

    def test_form_attribute(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone" type="xs:string" form="qualified"/>
        </xs:attributeGroup>""")
        self.assertTrue(schema.attribute_groups['extra']['phone'].qualified)
        self.assertEqual(schema.attribute_groups['extra']['phone'].form, 'qualified')

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone" type="xs:string" form="unqualified"/>
        </xs:attributeGroup>""")
        self.assertFalse(schema.attribute_groups['extra']['phone'].qualified)
        self.assertEqual(schema.attribute_groups['extra']['phone'].form, 'unqualified')

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone" type="xs:string"/>
        </xs:attributeGroup>""")
        self.assertFalse(schema.attribute_groups['extra']['phone'].qualified)
        self.assertIsNone(schema.attribute_groups['extra']['phone'].form)

        self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="phone" type="xs:string" form="mixed"/>
        </xs:attributeGroup>""", XMLSchemaParseError)

        self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone" form="qualified"/>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string"/>
        """, XMLSchemaParseError)

    def test_default_value(self):
        schema = self.check_schema(
            '<xs:attribute name="phone" type="xs:string" default="555-0100"/>'
        )
        schema.attributes['phone'].default = '555-0100'

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema(
                '<xs:attribute name="foo" type="xs:string" default="555-0100" fixed=""/>')
        self.assertEqual(ctx.exception.message,
                         "'default' and 'fixed' attributes are mutually exclusive")

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema(
                '<xs:attributeGroup name="extra">'
                '  <xs:attribute name="foo" type="xs:string" default="555-0100" use="required"/>'
                '</xs:attributeGroup>')
        self.assertEqual(ctx.exception.message,
                         "the attribute 'use' must be 'optional' "
                         "if the attribute 'default' is present")

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema(
                '<xs:attribute name="foo" type="xs:int" default="555-0100"/>')
        self.assertTrue(ctx.exception.message.startswith("default value '555-0100' "
                                                         "is not compatible with"))

        if self.schema_class.XSD_VERSION == "1.0":
            with self.assertRaises(XMLSchemaParseError) as ctx:
                self.check_schema(
                    '<xs:attribute name="foo" type="xs:ID" default="XYZ"/>')
            self.assertEqual(ctx.exception.message,
                             "xs:ID key attributes cannot have a default value")

    def test_fixed_value(self):
        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.check_schema(
                '<xs:attribute name="foo" type="xs:int" fixed="555-0100"/>')
        self.assertTrue(ctx.exception.message.startswith("fixed value '555-0100' "
                                                         "is not compatible with"))

        if self.schema_class.XSD_VERSION == "1.0":
            with self.assertRaises(XMLSchemaParseError) as ctx:
                self.check_schema(
                    '<xs:attribute name="foo" type="xs:ID" fixed="XYZ"/>')
            self.assertEqual(ctx.exception.message,
                             "xs:ID key attributes cannot have a fixed value")

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

    def test_decoding(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="code" type="xs:int"/>
            <xs:attribute name="phone" type="xs:string" default="555-0100"/>
        </xs:attributeGroup>""")

        xsd_attribute = schema.attribute_groups['extra']['phone']
        self.assertEqual(xsd_attribute.decode(None), '555-0100')
        self.assertEqual(schema.attribute_groups['extra'].decode({'code': '682'}),
                         [('code', 682), ('phone', '555-0100')])

        schema = self.check_schema(
            """<xs:attribute name="phone" type="xs:string" fixed="555-0100"/>""")
        xsd_attribute = schema.attributes['phone']
        self.assertEqual(xsd_attribute.decode(None), '555-0100')
        self.assertEqual(xsd_attribute.decode('555-0100'), '555-0100')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            xsd_attribute.decode('555-0101')
        self.assertEqual(ctx.exception.reason, "attribute 'phone' has a fixed value '555-0100'")

    def test_decoding_notation_type(self):
        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="label" type="xs:NOTATION"/>
        </xs:attributeGroup>""")

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.attribute_groups['extra'].decode({'label': 'alpha'})
        self.assertTrue(ctx.exception.reason.startswith("cannot validate against xs:NOTATION"))

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute name="label">
                <xs:simpleType>
                    <xs:restriction base="xs:NOTATION"/>
                </xs:simpleType>
            </xs:attribute>
        </xs:attributeGroup>""")

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.attribute_groups['extra'].decode({'label': 'alpha'})
        self.assertEqual(ctx.exception.reason, "missing enumeration facet in xs:NOTATION subtype")

        schema = self.check_schema("""
        <xs:notation name="jpeg" public="image/jpeg"/>
        <xs:notation name="png" public="image/png"/>
        <xs:attributeGroup name="extra">
            <xs:attribute name="label">
                <xs:simpleType>
                    <xs:restriction base="xs:NOTATION">
                        <xs:enumeration value="jpeg"/>
                        <xs:enumeration value="png"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:attribute>
        </xs:attributeGroup>""")

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.attribute_groups['extra'].decode({'label': 'alpha'})
        self.assertIn("value must be one of ['jpeg', 'png']", ctx.exception.reason)


class TestXsd11Attributes(TestXsdAttributes):

    schema_class = XMLSchema11


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD attributes with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
