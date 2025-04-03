#!/usr/bin/env python
#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import pathlib
from textwrap import dedent

from xmlschema import XMLSchemaParseError, XMLSchemaValidationError
from xmlschema.validators import XMLSchema11, XsdAttribute, XsdAttributeGroup
from xmlschema.testing import XsdValidatorTestCase
from xmlschema.names import XSI_NAMESPACE, XSD_ANY_SIMPLE_TYPE, XSD_STRING


class TestXsdAttributes(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')

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

        xsd_attribute = schema.attribute_groups['contact']['phone']
        self.assertTrue(xsd_attribute.qualified)
        self.assertEqual(xsd_attribute.default, '555-0100')

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone"/>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string" fixed="555-0100"/>
        """)

        xsd_attribute = schema.attribute_groups['extra']['phone']
        self.assertEqual(xsd_attribute.fixed, '555-0100')
        self.assertIsNone(xsd_attribute.annotation)

        schema = self.check_schema("""
        <xs:attributeGroup name="extra">
            <xs:attribute ref="phone" fixed="555-0100">
                <xs:annotation/>
            </xs:attribute>
        </xs:attributeGroup>
        <xs:attribute name="phone" type="xs:string" fixed="555-0100"/>
        """)

        xsd_attribute = schema.attribute_groups['extra']['phone']
        self.assertEqual(xsd_attribute.fixed, '555-0100')
        self.assertIsNotNone(xsd_attribute.annotation)

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

    def test_attribute_group_mapping(self):
        schema = self.get_schema("""
            <xs:attributeGroup name="attrs">
                <xs:attribute name="a1" type="xs:string"/>
                <xs:attribute name="a2" type="xs:string"/>
            </xs:attributeGroup>""")

        attribute_group = schema.attribute_groups['attrs']
        self.assertEqual(repr(attribute_group), "XsdAttributeGroup(name='attrs')")

        with self.assertRaises(ValueError) as ec:
            attribute_group['a3'] = attribute_group['a2']
        self.assertIn("mismatch", str(ec.exception))

        xsd_attribute = attribute_group['a2']
        del attribute_group['a2']
        self.assertNotIn('a2', attribute_group)
        attribute_group['a2'] = xsd_attribute

    def test_attribute_group_reference(self):
        schema = self.get_schema("""
            <xs:attributeGroup name="alpha">
                <xs:attribute name="name" type="xs:string"/>
                <xs:attributeGroup ref="beta"/>
            </xs:attributeGroup>
            <xs:attributeGroup name="beta">
                <xs:attribute name="foo" type="xs:string"/>
                <xs:attribute name="bar" type="xs:string"/>
            </xs:attributeGroup>""")

        # ref="beta" does not imply a reference but only a copy
        # of the attributes of referred attribute group.
        attribute_group = schema.attribute_groups['alpha']
        self.assertNotIn('beta', attribute_group)
        self.assertEqual(len(attribute_group), 3)
        self.assertIn('name', attribute_group)
        self.assertIn('foo', attribute_group)
        self.assertIn('bar', attribute_group)

    def test_missing_attribute_group_name(self):
        schema = self.get_schema("""
            <xs:attributeGroup>
                <xs:annotation/>
                <xs:attribute name="a1" type="xs:string"/>
                <xs:attribute name="a2" type="xs:string"/>
            </xs:attributeGroup>""", validation='lax')

        self.assertEqual(len(schema.all_errors), 2)
        self.assertTrue(isinstance(schema.all_errors[0], XMLSchemaParseError))
        self.assertIn("missing required attribute 'name'", str(schema.all_errors[0]))
        self.assertTrue(isinstance(schema.all_errors[1], XMLSchemaParseError))
        self.assertIn("missing key field '@name'", str(schema.all_errors[1]))

        self.assertEqual(len(schema.attribute_groups), 0)
        attribute_group = XsdAttributeGroup(schema.root[0], schema, parent=None)
        self.assertIsNone(attribute_group.name)

    def test_missing_attribute_group_reference(self):
        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attributeGroup ref="beta"/>  <!-- Missing "beta" attribute group -->
        </xs:attributeGroup>
        """, XMLSchemaParseError)

        self.check_schema("""
        <xs:attributeGroup name="alpha">
            <xs:attribute name="name" type="xs:string"/>
            <xs:attributeGroup ref="x:beta"/>  <!-- Unresolved name -->
        </xs:attributeGroup>
        <xs:attributeGroup name="beta">
            <xs:attribute name="foo" type="xs:string"/>
            <xs:attribute name="bar" type="xs:string"/>
        </xs:attributeGroup>
        """, XMLSchemaParseError)

        schema = self.get_schema("""
            <xs:attributeGroup name="alpha">
                <xs:attribute name="name" type="xs:string"/>
                <xs:attributeGroup name="beta"/>  <!-- attribute "name" instead of "ref" -->
            </xs:attributeGroup>
            """, validation='lax')
        self.assertTrue(isinstance(schema.all_errors[1], XMLSchemaParseError))

    def test_attribute_wildcards(self):
        schema = self.get_schema("""
            <xs:attributeGroup name="attrs">
                <xs:attribute name="a1" type="xs:string"/>
                <xs:attribute name="a2" type="xs:string"/>
                <xs:anyAttribute namespace="other"/>
            </xs:attributeGroup>""")

        attribute_group = schema.attribute_groups['attrs']
        self.assertEqual(len(attribute_group), 3)
        self.assertIn(None, attribute_group)

        schema = self.get_schema("""
            <xs:attributeGroup name="attrs">
                <xs:attribute name="a1" type="xs:string"/>
                <xs:attribute name="a2" type="xs:string"/>
                <xs:anyAttribute namespace="other"/>
                <xs:anyAttribute namespace="#all"/>
                <xs:attribute name="a3" type="xs:string"/>
            </xs:attributeGroup>""", validation='lax')

        self.assertEqual(len(schema.all_errors), 3)
        self.assertTrue(isinstance(schema.all_errors[0], XMLSchemaParseError))
        self.assertIn("Unexpected child with tag 'xs:anyAttribute'", str(schema.all_errors[0]))
        self.assertTrue(isinstance(schema.all_errors[1], XMLSchemaParseError))
        self.assertIn("more anyAttribute declarations", str(schema.all_errors[1]))
        self.assertTrue(isinstance(schema.all_errors[2], XMLSchemaParseError))
        self.assertIn("another declaration after anyAttribute", str(schema.all_errors[2]))

    def test_duplicated_attribute(self):
        with self.assertRaises(XMLSchemaParseError) as ec:
            self.get_schema("""
                <xs:attributeGroup name="attrs">
                    <xs:attribute name="a1" type="xs:string"/>
                    <xs:attribute name="a2" type="xs:string"/>
                    <xs:attribute name="a2" type="xs:string"/>
                </xs:attributeGroup>""")

        self.assertIn("multiple declaration for attribute 'a2'", str(ec.exception))

    def test_duplicated_attribute_group_ref(self):
        with self.assertRaises(XMLSchemaParseError) as ec:
            self.get_schema("""
                <xs:attributeGroup name="attrs">
                    <xs:attribute name="a1" type="xs:string"/>
                    <xs:attributeGroup ref="other"/>
                    <xs:attributeGroup ref="other"/>
                </xs:attributeGroup>
                <xs:attributeGroup name="other">
                    <xs:attribute name="a2" type="xs:string"/>
                    <xs:attribute name="a3" type="xs:string"/>
                </xs:attributeGroup>""")

        self.assertIn("duplicated attributeGroup 'other'", str(ec.exception))

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
        self.assertTrue(ctx.exception.reason.startswith(
            "attribute label='alpha': cannot validate against xs:NOTATION"
        ))

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
        self.assertEqual(
            ctx.exception.reason,
            "attribute label='alpha': missing enumeration facet in xs:NOTATION subtype"
        )

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

    def test_target_namespace(self):
        xs = self.get_schema('<xs:attribute name="a" type="xs:string"/>')
        self.assertEqual(xs.attributes['a'].target_namespace, '')

        with self.assertRaises(XMLSchemaParseError) as ec:
            self.get_schema('<xs:attribute name="foo" targetNamespace="bar" type="xs:string"/>')
        self.assertIn("'targetNamespace' is prohibited", str(ec.exception))

        xs = self.get_schema(dedent("""\
            <xs:attributeGroup name="attrs">
                <xs:attribute name="a" type="xs:string"
                    targetNamespace="http://xmlschema.test/ns"/>
                <xs:attribute ref="b"/>
            </xs:attributeGroup>
            <xs:attribute name="b" type="xs:string"/>"""))

        self.assertNotIn('a', xs.attribute_groups['attrs'])
        self.assertIn('{http://xmlschema.test/ns}a', xs.attribute_groups['attrs'])

        xsd_attribute = xs.attribute_groups['attrs']['{http://xmlschema.test/ns}a']
        self.assertEqual(xsd_attribute.target_namespace, 'http://xmlschema.test/ns')
        self.assertEqual(xs.attribute_groups['attrs']['b'].target_namespace, '')

    def test_prohibited_and_fixed_incompatibility(self):
        with self.assertRaises(XMLSchemaParseError) as ec:
            self.get_schema(dedent("""\
                <xs:attributeGroup name="attrs">
                    <xs:attribute name="a" type="xs:string"
                        use="prohibited" fixed="foo"/>
                </xs:attributeGroup>"""))

        self.assertIn("'fixed' with use=prohibited is not allowed in XSD 1.1", str(ec.exception))

    def test_inheritable_attribute(self):
        xs = self.get_schema(dedent("""\
            <xs:attributeGroup name="attrs">
                <xs:attribute name="a" type="xs:string" />
                <xs:attribute name="b" type="xs:string" inheritable="true"/>
                <xs:attribute name="c" type="xs:string" inheritable="false"/>
            </xs:attributeGroup>"""))

        self.assertFalse(xs.attribute_groups['attrs']['a'].inheritable)
        self.assertTrue(xs.attribute_groups['attrs']['b'].inheritable)
        self.assertFalse(xs.attribute_groups['attrs']['c'].inheritable)


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('XSD attributes')
