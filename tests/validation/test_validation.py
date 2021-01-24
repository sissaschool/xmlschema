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
import sys
import decimal
from textwrap import dedent

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

import xmlschema
from xmlschema import XMLSchemaValidationError

from xmlschema.etree import ElementTree
from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase


class TestValidation(XsdValidatorTestCase):
    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')

    def check_validity(self, xsd_component, data, expected, use_defaults=True):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.is_valid, data, use_defaults=use_defaults)
        elif expected:
            self.assertTrue(xsd_component.is_valid(data, use_defaults=use_defaults))
        else:
            self.assertFalse(xsd_component.is_valid(data, use_defaults=use_defaults))

    @unittest.skipIf(lxml_etree is None, "The lxml library is not available.")
    def test_lxml(self):
        xs = xmlschema.XMLSchema(self.casepath('examples/vehicles/vehicles.xsd'))
        xt1 = lxml_etree.parse(self.casepath('examples/vehicles/vehicles.xml'))
        xt2 = lxml_etree.parse(self.casepath('examples/vehicles/vehicles-1_error.xml'))
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)

    def test_document_validate_api(self):
        self.assertIsNone(xmlschema.validate(self.vh_xml_file))
        self.assertIsNone(xmlschema.validate(self.vh_xml_file, use_defaults=False))

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        self.assertRaises(XMLSchemaValidationError, xmlschema.validate, vh_2_file)

        try:
            xmlschema.validate(vh_2_file, namespaces={'vhx': "http://example.com/vehicles"})
        except XMLSchemaValidationError as err:
            path_line = str(err).splitlines()[-1]
        else:
            path_line = ''

        if sys.version_info >= (3, 6):
            self.assertEqual('Path: /vhx:vehicles/vhx:cars', path_line)
        else:
            self.assertTrue(
                'Path: /vh:vehicles/vh:cars' == path_line or
                'Path: /vhx:vehicles/vhx:cars', path_line
            )  # Due to unordered dicts

        # Issue #80
        vh_2_xt = ElementTree.parse(vh_2_file)
        self.assertRaises(XMLSchemaValidationError, xmlschema.validate, vh_2_xt, self.vh_xsd_file)

        # Issue #145
        with open(self.vh_xml_file) as f:
            self.assertIsNone(xmlschema.validate(f, schema=self.vh_xsd_file))

    def test_document_validate_api_lazy(self):
        source = xmlschema.XMLResource(self.col_xml_file, lazy=False)
        namespaces = source.get_namespaces()
        source.root[0].clear()  # Drop internal elements
        source.root[1].clear()
        xsd_element = self.col_schema.elements['collection']

        self.assertRaises(XMLSchemaValidationError, xsd_element.decode, source.root,
                          namespaces=namespaces)

        for _ in xsd_element.iter_decode(source.root, 'strict', namespaces=namespaces,
                                         source=source, max_depth=1):
            del _

        self.assertIsNone(xmlschema.validate(self.col_xml_file, lazy=True))

    def test_document_is_valid_api(self):
        self.assertTrue(xmlschema.is_valid(self.vh_xml_file))
        self.assertTrue(xmlschema.is_valid(self.vh_xml_file, use_defaults=False))

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        self.assertFalse(xmlschema.is_valid(vh_2_file))

    def test_document_iter_errors_api(self):
        self.assertListEqual(list(xmlschema.iter_errors(self.vh_xml_file)), [])
        self.assertListEqual(list(xmlschema.iter_errors(self.vh_xml_file, use_defaults=False)), [])

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        errors = list(xmlschema.iter_errors(vh_2_file))
        self.assertEqual(len(errors), 2)
        self.assertIsInstance(errors[0], XMLSchemaValidationError)
        self.assertIsInstance(errors[1], XMLSchemaValidationError)

    def test_max_depth_argument(self):
        schema = self.schema_class(self.col_xsd_file)
        self.assertEqual(
            schema.decode(self.col_xml_file, max_depth=1),
            {'@xmlns:col': 'http://example.com/ns/collection',
             '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
             '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd'})

        xmlschema.limits.MAX_XML_DEPTH = 1
        with self.assertRaises(XMLSchemaValidationError):
            schema.decode(self.col_xml_file)
        xmlschema.limits.MAX_XML_DEPTH = 9999

        self.assertEqual(
            schema.decode(self.col_xml_file, max_depth=2),
            {'@xmlns:col': 'http://example.com/ns/collection',
             '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
             '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
             'object': [{'@id': 'b0836217462', '@available': True},
                        {'@id': 'b0836217463', '@available': True}]})

    def test_issue_064(self):
        self.check_validity(self.st_schema, '<name xmlns="ns"></name>', False)

    def test_issue_171(self):
        # First schema has an assert with naive check
        schema = xmlschema.XMLSchema11(self.casepath('issues/issue_171/issue_171.xsd'))
        self.check_validity(schema, '<tag name="test" abc="10" def="0"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10" def="1"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10"/>', True)

        # Same schema with a more reliable assert expression
        schema = xmlschema.XMLSchema11(self.casepath('issues/issue_171/issue_171b.xsd'))
        self.check_validity(schema, '<tag name="test" abc="10" def="0"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10" def="1"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10"/>', True)

        # Another schema with a simple assert expression to test that EBV of abc/def='0' is True
        schema = xmlschema.XMLSchema11(self.casepath('issues/issue_171/issue_171c.xsd'))
        self.check_validity(schema, '<tag name="test" abc="0" def="1"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1" def="0"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1" def="1"/>', True)
        self.check_validity(schema, '<tag name="test" abc="0" def="0"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1"/>', False)
        self.check_validity(schema, '<tag name="test" def="1"/>', False)

    def test_issue_183(self):
        # Test for issue #183
        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns0="http://xmlschema.test/0"
                xmlns:tns1="http://xmlschema.test/1"
                xmlns="http://xmlschema.test/2"
                targetNamespace="http://xmlschema.test/0">

                <xs:element name="elem1" type="xs:string"/>
                <xs:element name="elem2" type="xs:string"/>
                <xs:element name="root" type="tns0:enumType"/>

                <xs:simpleType name="enumType">
                    <xs:restriction base="xs:QName">
                        <xs:enumeration value="tns0:elem1"/>
                        <xs:enumeration value="tns0:elem2"/>
                        <xs:enumeration value="tns1:elem1"/>
                        <xs:enumeration value="elem1"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>""")

        xml_data = '<tns0:root xmlns:tns0="http://xmlschema.test/0" >tns0:elem1</tns0:root>'
        self.check_validity(schema, xml_data, True)

        xml_data = '<ns0:root xmlns:ns0="http://xmlschema.test/0" >ns0:elem1</ns0:root>'
        self.check_validity(schema, xml_data, True)

        self.assertEqual(schema.decode(xml_data), 'ns0:elem1')

        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns="http://xmlschema.test/0"
                xmlns:tns1="http://xmlschema.test/1"
                xmlns:tns2="http://xmlschema.test/2"
                targetNamespace="http://xmlschema.test/0">

                <xs:element name="elem1" type="xs:string"/>
                <xs:element name="elem2" type="xs:string"/>
                <xs:element name="elem3" type="xs:string"/>
                <xs:element name="elem4" type="xs:string"/>
                
                <xs:element name="root" type="enumType"/>

                <xs:simpleType name="enumType">
                    <xs:restriction base="xs:QName">
                        <xs:enumeration value="elem1"/>
                        <xs:enumeration value="elem2"/>
                        <xs:enumeration value="tns1:other1"/>
                        <xs:enumeration value="elem3"/>
                        <xs:enumeration value="tns2:other2"/>                        
                        <xs:enumeration value="elem4"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>""")

        xml_data = '<ns0:root xmlns:ns0="http://xmlschema.test/0">ns0:elem2</ns0:root>'
        self.check_validity(schema, xml_data, True)

    def test_issue_213(self):
        schema = xmlschema.XMLSchema(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:element name="amount" type="xs:decimal"/>
        </xs:schema>"""))

        xml1 = """<?xml version="1.0" encoding="UTF-8"?><amount>0.000000</amount>"""
        self.assertIsInstance(schema.decode(xml1), decimal.Decimal)

        xml2 = """<?xml version="1.0" encoding="UTF-8"?><amount>0.0000000</amount>"""
        self.assertIsInstance(schema.decode(xml2), decimal.Decimal)

    def test_issue_224__validate_malformed_file(self):
        schema = xmlschema.XMLSchema(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" type="xs:string"/>
            </xs:schema>"""))

        malformed_xml_file = self.casepath('resources/malformed.xml')

        with self.assertRaises(ElementTree.ParseError):
            schema.is_valid(malformed_xml_file)


class TestValidation11(TestValidation):
    schema_class = XMLSchema11

    def test_default_attributes(self):
        xs = self.schema_class(self.casepath('features/attributes/default_attributes.xsd'))
        self.assertTrue(xs.is_valid("<tree xmlns='ns'>\n"
                                    "   <node node-id='1'>alpha</node>\n"
                                    "   <node node-id='2' colour='red'>beta</node>\n"
                                    "</tree>"))
        self.assertFalse(xs.is_valid("<tree xmlns='ns'>\n"
                                     "   <node>alpha</node>\n"  # Misses required attribute
                                     "   <node node-id='2' colour='red'>beta</node>\n"
                                     "</tree>"))


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema validation with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
