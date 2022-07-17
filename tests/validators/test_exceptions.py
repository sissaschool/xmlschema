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
import os
import io
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema, XMLResource
from xmlschema.validators.exceptions import XMLSchemaValidatorError, \
    XMLSchemaNotBuiltError, XMLSchemaModelDepthError, XMLSchemaValidationError, \
    XMLSchemaChildrenValidationError

CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestValidatorExceptions(unittest.TestCase):

    def test_exception_init(self):
        xs = XMLSchema(os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd'))

        with self.assertRaises(ValueError) as ctx:
            XMLSchemaValidatorError(xs, 'unknown error', elem='wrong')
        self.assertIn("'elem' attribute requires an Element", str(ctx.exception))

        error = XMLSchemaNotBuiltError(xs, 'schema not built!')
        self.assertEqual(error.message, 'schema not built!')

        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:group name="group1">
                <xs:choice>
                  <xs:element name="root" type="xs:integer"/>
                </xs:choice>
              </xs:group>
            </xs:schema>""")

        error = XMLSchemaModelDepthError(schema.groups['group1'])
        self.assertEqual("maximum model recursion depth exceeded", error.message[:38])

    def test_exception_repr(self):
        xs = XMLSchema(os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd'))

        error = XMLSchemaValidatorError(xs, 'unknown error')
        self.assertEqual(str(error), 'unknown error')
        self.assertEqual(error.msg, 'unknown error')

        error = XMLSchemaValidatorError(xs, 'unknown error', elem=xs.root)
        output = str(error)
        lines = output.split('\n')

        self.assertGreater(len(lines), 10, msg=output)
        self.assertEqual(lines[0], 'unknown error:', msg=output)
        self.assertEqual(lines[2], 'Schema:', msg=output)
        self.assertRegex(lines[4].strip(), '^<(xs:)?schema ', msg=output)
        self.assertRegex(lines[-2].strip(), '</(xs:|xsd:)?schema>$', msg=output)

    @unittest.skipIf(lxml_etree is None, 'lxml is not installed ...')
    def test_exception_repr_lxml(self):

        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="xs:integer"/>
            </xs:schema>""")
        root = lxml_etree.XML('<root a="10"/>')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate(root)

        lines = str(ctx.exception).split('\n')
        self.assertEqual(lines[0], "failed validating {'a': '10'} with XsdAttributeGroup():")
        self.assertEqual(lines[2], "Reason: 'a' attribute not allowed for element")
        self.assertEqual(lines[8], "Instance (line 1):")
        self.assertEqual(lines[12], "Path: /root")

        self.assertEqual(repr(ctx.exception), "XMLSchemaValidationError(reason=\"'a' "
                                              "attribute not allowed for element\")")

        error = XMLSchemaValidationError(schema.elements['root'], root)
        self.assertIsNone(error.reason)
        self.assertNotIn("Reason:", str(error))
        self.assertIn("Schema:", str(error))

        error = XMLSchemaValidationError(schema, root)
        self.assertNotIn("Reason:", str(error))
        self.assertNotIn("Schema:", str(error))

        error = XMLSchemaValidationError(schema, 10)
        self.assertEqual(str(error), "failed validating 10 with XMLSchema10(namespace='')")

    def test_setattr(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="xs:integer"/>
            </xs:schema>""")

        root = ElementTree.XML('<root a="10"/>')
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate(root)

        self.assertIsInstance(ctx.exception.source, XMLResource)
        self.assertFalse(ctx.exception.source.is_lazy())

        resource = XMLResource(io.StringIO('<root a="10"/>'), lazy=True)
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate(resource)

        self.assertIsInstance(ctx.exception.source, XMLResource)
        self.assertTrue(ctx.exception.source.is_lazy())
        self.assertIsNone(ctx.exception.elem)
        self.assertEqual(ctx.exception.source, resource)
        self.assertEqual(ctx.exception.path, '/root')

    @unittest.skipIf(lxml_etree is None, 'lxml is not installed ...')
    def test_sourceline_property(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="xs:integer"/>
            </xs:schema>""")

        root = lxml_etree.XML('<root a="10"/>')
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate(root)

        self.assertEqual(ctx.exception.sourceline, 1)
        self.assertEqual(ctx.exception.root, root)

    def test_other_properties(self):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        xs = XMLSchema(xsd_file)

        with self.assertRaises(XMLSchemaValidatorError) as ctx:
            raise XMLSchemaValidatorError(xs, 'unknown error')

        self.assertIsNone(ctx.exception.root)
        self.assertIsNone(ctx.exception.schema_url)
        self.assertEqual(ctx.exception.origin_url, xs.source.url)
        self.assertIsNone(XMLSchemaValidatorError(None, 'unknown error').origin_url)

    def test_children_validation_error(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="a">
                <xs:complexType>
                  <xs:sequence>
                    <xs:element name="b1" type="xs:string"/>
                    <xs:element name="b2" type="xs:string"/>
                    <xs:element name="b3" type="xs:string" minOccurs="2" maxOccurs="3"/>
                  </xs:sequence>
                </xs:complexType>
              </xs:element>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            schema.validate('<a><b1/><b2/><b3/><b3/><b3/><b3/></a>')

        lines = str(ctx.exception).split('\n')
        self.assertEqual(lines[2], "Reason: Unexpected child with tag 'b3' at position 6.")
        self.assertEqual(lines[-2], "Path: /a")

        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            schema.validate('<a><b1/><b2/><b3/></a>')

        lines = str(ctx.exception).split('\n')
        self.assertEqual(lines[2][:51], "Reason: The content of element 'a' is not complete.")
        self.assertEqual(lines[-2], "Path: /a")

        root = ElementTree.XML('<a><b1/><b2/><b2/><b3/><b3/><b3/></a>')
        validator = schema.elements['a'].type.content
        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            raise XMLSchemaChildrenValidationError(validator, root, 2, validator[1], 2)

        lines = str(ctx.exception).split('\n')
        self.assertTrue(lines[2].endswith("occurs 2 times but the maximum is 1."))

        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="a">
                <xs:complexType>
                  <xs:sequence>
                    <xs:element name="b1" type="xs:string"/>
                    <xs:any/>
                  </xs:sequence>
                </xs:complexType>
              </xs:element>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            schema.validate('<a><b1/></a>')

        lines = str(ctx.exception).split('\n')
        self.assertTrue(lines[2].endswith("Tag from \'##any\' namespace/s expected."))

        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="a">
                <xs:complexType>
                  <xs:sequence>
                    <xs:element name="b1" type="xs:string"/>
                    <xs:choice>
                        <xs:any namespace="tns0" processContents="lax"/>
                        <xs:element name="b2" type="xs:string"/>
                    </xs:choice>
                  </xs:sequence>
                </xs:complexType>
              </xs:element>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            schema.validate('<a><b1/></a>')

        lines = str(ctx.exception).split('\n')
        self.assertTrue(lines[2].endswith("Tag 'b2' expected."))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's validator exceptions with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
