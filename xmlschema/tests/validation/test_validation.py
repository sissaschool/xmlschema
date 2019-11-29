#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import sys

import xmlschema
from xmlschema import XMLSchemaValidationError

from xmlschema.etree import ElementTree, lxml_etree
from xmlschema.tests import XsdValidatorTestCase
from xmlschema.validators import XMLSchema11


class TestValidation(XsdValidatorTestCase):

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

    def test_issue_064(self):
        self.check_validity(self.st_schema, '<name xmlns="ns"></name>', False)

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
                'Path: /vh:vehicles/vh:cars' == path_line or 'Path: /vhx:vehicles/vhx:cars', path_line
            )  # Due to unordered dicts

        # Issue #80
        vh_2_xt = ElementTree.parse(vh_2_file)
        self.assertRaises(XMLSchemaValidationError, xmlschema.validate, vh_2_xt, self.vh_xsd_file)

        # Issue #145
        with open(self.vh_xml_file) as f:
            self.assertIsNone(xmlschema.validate(f, schema=self.vh_xsd_file))

    def test_document_validate_api_lazy(self):
        source = xmlschema.XMLResource(self.col_xml_file, lazy=True)
        namespaces = source.get_namespaces()
        source.root[0].clear()  # Drop internal elements
        source.root[1].clear()
        xsd_element = self.col_schema.elements['collection']

        self.assertRaises(XMLSchemaValidationError, xsd_element.decode, source.root, namespaces=namespaces)

        for result in xsd_element.iter_decode(source.root, 'strict', namespaces=namespaces,
                                              source=source, max_depth=1):
            del result

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
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
