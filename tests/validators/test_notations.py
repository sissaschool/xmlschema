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
from xml.etree import ElementTree

from xmlschema import XMLSchemaParseError
from xmlschema.names import XSD_NOTATION
from xmlschema.validators import XMLSchema10, XMLSchema11, XsdNotation


class TestXsd10Notations(unittest.TestCase):

    schema_class = XMLSchema10

    def test_parse(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:notation name="content" public="text/html"/>
        </xs:schema>""")
        self.assertIn('content', schema.notations)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:notation name="content"/>
            </xs:schema>""")
        self.assertIn("notation must have a 'public' or a 'system' attribute", str(ctx.exception))

        with self.assertRaises(XMLSchemaParseError) as ctx:
            self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:notation public="text/html"/>
            </xs:schema>""")
        self.assertEqual("missing required attribute 'name'", ctx.exception.message)

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:notation public="text/html"/>
        </xs:schema>""", validation='skip')
        self.assertListEqual(schema.all_errors, [])

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:notation public="text/html"/>
        </xs:schema>""", validation='lax')
        self.assertEqual(len(schema.all_errors), 2)

        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:complexType name="emptyType"/>
        </xs:schema>""")
        elem = ElementTree.Element(XSD_NOTATION)

        with self.assertRaises(XMLSchemaParseError) as ctx:
            XsdNotation(elem, schema, parent=schema.types['emptyType'])
        self.assertIn("a notation declaration must be global", str(ctx.exception))

        with self.assertRaises(XMLSchemaParseError) as ctx:
            XsdNotation(elem, schema, parent=None)
        self.assertIn("a notation must have a 'name' attribute", str(ctx.exception))

    def test_properties(self):
        schema = self.schema_class("""
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:notation name="style" public="text/css" system="style.css"/>
        </xs:schema>""")
        self.assertEqual(schema.notations['style'].public, "text/css")
        self.assertEqual(schema.notations['style'].system, "style.css")


class TestXsd11Notations(unittest.TestCase):
    schema_class = XMLSchema11


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD notations with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
