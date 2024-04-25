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
import pathlib
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema, XMLResource
from xmlschema.helpers import is_etree_element
from xmlschema.validators.exceptions import XMLSchemaValidatorError, \
    XMLSchemaNotBuiltError, XMLSchemaParseError, XMLSchemaModelDepthError, \
    XMLSchemaValidationError, XMLSchemaDecodeError, XMLSchemaEncodeError, \
    XMLSchemaChildrenValidationError

CASES_DIR = pathlib.Path(__file__).parent.joinpath('../test_cases')


class TestValidatorExceptions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = XMLSchema(CASES_DIR.joinpath('examples/vehicles/vehicles.xsd'))

    def test_exception_init(self):
        with self.assertRaises(ValueError) as ctx:
            XMLSchemaValidatorError(self.schema, 'unknown error', elem='wrong')
        self.assertIn("'elem' attribute requires an Element", str(ctx.exception))

        error = XMLSchemaNotBuiltError(self.schema, 'schema not built!')
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

    def test_validator_error_repr(self):
        xs = self.schema

        error = XMLSchemaValidatorError(xs, 'unknown error')
        chunks = str(error).split('\n')
        self.assertEqual('unknown error:', chunks[0].strip())
        self.assertEqual(error.get_elem_as_string(indent='  '), '  None')

        error = XMLSchemaValidatorError(xs, 'unknown error', elem=xs.root)
        output = str(error)
        lines = output.split('\n')

        self.assertGreater(len(lines), 10, msg=output)
        self.assertEqual(lines[0], 'unknown error:', msg=output)
        self.assertEqual(lines[2], 'Schema component:', msg=output)
        self.assertRegex(lines[4].strip(), '^<(xs:)?schema ', msg=output)
        self.assertRegex(lines[-4].strip(), '</(xs:|xsd:)?schema>$', msg=output)

        error = XMLSchemaValidatorError(
            validator=xs.elements['vehicles'],
            message='test error message #1',
            elem=xs.source.root[1],
            source=xs.source,
            namespaces=xs.namespaces,
        )
        chunks = str(error).split('\n')
        self.assertEqual('test error message #1:', chunks[0].strip())
        self.assertEqual('Schema component:', chunks[2].strip())
        self.assertEqual('Path: /xs:schema/xs:include[2]', chunks[6].strip())
        self.assertEqual('Schema URL: ' + xs.url, chunks[8].strip())

        self.assertTrue(error.get_elem_as_string().startswith('<xs:include'))

        error = XMLSchemaValidatorError(
            validator=xs.elements['cars'],
            message='test error message #2',
            elem=xs.source.root[1],
            source=xs.source,
            namespaces=xs.namespaces,
        )
        chunks = str(error).split('\n')
        self.assertEqual('test error message #2:', chunks[0].strip())
        self.assertEqual('Schema component:', chunks[2].strip())
        self.assertEqual('Path: /xs:schema/xs:include[2]', chunks[6].strip())
        self.assertNotEqual('Schema URL: ' + xs.url, chunks[8].strip())
        self.assertTrue(chunks[8].strip().endswith('cars.xsd'))
        self.assertEqual('Origin URL: ' + xs.url, chunks[10].strip())

    def test_validator_error_repr_no_urls(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="xs:integer"/>
            </xs:schema>""")

        error = XMLSchemaValidatorError(validator=schema, message='test error message #3')
        self.assertEqual(str(error), "test error message #3")
        self.assertIsNone(error.schema_url)
        self.assertIsNone(error.origin_url)
        self.assertEqual(str(error), error.msg)

    def test_parse_error(self):
        xs = self.schema

        error = XMLSchemaParseError(xs, "test parse error message #1")
        self.assertTrue(str(error).startswith('test parse error message #1:'))

        error = XMLSchemaParseError(xs.elements['vehicles'], "test parse error message #2")
        self.assertNotEqual(str(error), 'test parse error message #2')

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
        self.assertEqual(lines[10], "Instance (line 1):")
        self.assertEqual(lines[14], "Path: /root")

        self.assertEqual(repr(ctx.exception), "XMLSchemaValidationError(reason=\"'a' "
                                              "attribute not allowed for element\")")

        error = XMLSchemaValidationError(schema.elements['root'], root)
        self.assertIsNone(error.reason)
        self.assertNotIn("Reason:", str(error))
        self.assertIn("Schema component:", str(error))
        self.assertEqual(error.get_obj_as_string(), '<root a="10"/>')

        error = XMLSchemaValidationError(schema, root)
        self.assertNotIn("Reason:", str(error))
        self.assertNotIn("Schema component:", str(error))

        error = XMLSchemaValidationError(schema, 10)
        lines = str(error).split('\n')
        self.assertEqual(lines[0], "failed validating 10 with XMLSchema10(namespace=''):")
        self.assertEqual(lines[2], "Instance type: <class 'int'>")
        self.assertEqual(error.get_obj_as_string(), '10')

        error = XMLSchemaValidationError(schema, 'a' * 201)
        lines = str(error).split('\n')
        self.assertEqual(lines[0], "failed validating <class 'str'> instance "
                                   "with XMLSchema10(namespace=''):")
        self.assertEqual(lines[2], "Instance type: <class 'str'>")
        self.assertEqual(lines[6], '  ' + repr('a' * 201))

    def test_get_obj_as_string(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" type="xs:integer"/>
            </xs:schema>""")

        error = XMLSchemaValidationError(schema, 'alpha\n')
        self.assertEqual(error.get_obj_as_string(indent='  '), "  'alpha\\n'")

        error = XMLSchemaValidationError(schema, 'alpha\nalpha\n')
        self.assertEqual(error.get_obj_as_string(indent='  '), "  'alpha\\nalpha\\n'")

        error = XMLSchemaValidationError(schema, 'alpha\n' * 2)
        self.assertEqual(error.get_obj_as_string(' '), " 'alpha\\nalpha\\n'")

        error = XMLSchemaValidationError(schema, 'alpha\n' * 200)
        obj_as_string = error.get_obj_as_string(' ')
        self.assertTrue(obj_as_string.startswith(" ('alpha\\n'"))
        self.assertEqual(len(obj_as_string.splitlines()), 200)

        obj_as_string = error.get_obj_as_string(max_lines=20)
        self.assertTrue(obj_as_string.startswith("('alpha\\n'"))
        self.assertTrue(obj_as_string.endswith("...\n..."))
        self.assertEqual(len(obj_as_string.splitlines()), 20)

        obj_as_string = error.get_obj_as_string(indent='  ', max_lines=30)
        self.assertTrue(obj_as_string.startswith("  ('alpha\\n'"))
        self.assertTrue(obj_as_string.endswith("  ...\n  ..."))
        self.assertEqual(len(obj_as_string.splitlines()), 30)

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
        self.assertIsNotNone(ctx.exception.schema_url)
        self.assertEqual(ctx.exception.origin_url, xs.source.url)
        self.assertIsNone(XMLSchemaValidatorError(None, 'unknown error').origin_url)

    def test_decode_error(self):
        error = XMLSchemaDecodeError(
            validator=XMLSchema.meta_schema.types['int'],
            obj='10.0',
            decoder=int,
            reason="invalid literal for int() with base 10: '10.0'",
        )
        self.assertIs(error.decoder, int)
        self.assertIn("Reason: invalid literal for int() with base 10: '10.0'", error.msg)
        self.assertIn('Schema component:', error.msg)

    def test_encode_error(self):
        error = XMLSchemaEncodeError(
            validator=XMLSchema.meta_schema.types['string'],
            obj=10,
            encoder=str,
            reason="10 is not an instance of <class 'str'>",
        )
        self.assertIs(error.encoder, str)
        self.assertIn('Reason: 10 is not an instance of', error.msg)
        self.assertIn('Schema component:', error.msg)

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

    def test_invalid_child_property(self):
        schema = XMLSchema("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="a">
                <xs:complexType>
                  <xs:choice>
                    <xs:element name="b1" type="bType"/>
                    <xs:element name="b2" type="bType"/>
                  </xs:choice>
                </xs:complexType>
              </xs:element>
              <xs:complexType name="bType">
                <xs:sequence>
                  <xs:element name="c1" type="xs:string"/>
                  <xs:element name="c2" type="xs:string"/>
                </xs:sequence>
              </xs:complexType>
            </xs:schema>""")

        with self.assertRaises(XMLSchemaChildrenValidationError) as ctx:
            schema.validate('<a><c1/></a>')

        lines = str(ctx.exception).split('\n')
        self.assertTrue(lines[2].endswith("Tag ('b1' | 'b2') expected."))

        invalid_child = ctx.exception.invalid_child
        self.assertTrue(is_etree_element(invalid_child))
        self.assertEqual(invalid_child.tag, 'c1')

        xml_source = '<a><b1></b1><b2><c1/><c1/></b2></a>'
        resource = XMLResource(xml_source, lazy=True)
        errors = list(schema.iter_errors(resource))
        self.assertEqual(len(errors), 3)
        self.assertIsNone(errors[0].invalid_child)
        self.assertTrue(is_etree_element(errors[1].invalid_child))
        self.assertEqual(errors[1].invalid_child.tag, 'c1')
        self.assertTrue(is_etree_element(errors[2].invalid_child))
        self.assertEqual(errors[2].invalid_child.tag, 'b2')

    def test_validation_error_logging(self):
        schema = XMLSchema("""
             <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                 <xs:element name="root" type="xs:integer"/>
             </xs:schema>""")

        with self.assertLogs('xmlschema', level='DEBUG') as ctx:
            with self.assertRaises(XMLSchemaValidationError):
                schema.validate('<root/>')
            self.assertEqual(len(ctx.output), 0)

            errors = list(schema.iter_errors('<root/>'))
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], XMLSchemaDecodeError)

            self.assertEqual(len(ctx.output), 1)
            self.assertIn('Collect XMLSchemaDecodeError', ctx.output[0])
            self.assertIn('with traceback:', ctx.output[0])


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's validator exceptions with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
