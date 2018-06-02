#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests concerning the validation of XML files with the 'xmlschema' package.
"""
import unittest
import os
import sys
try:
    import lxml.etree as etree
except ImportError:
    etree = None

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.tests import XMLSchemaTestCase


def make_test_validation_function(xml_file, schema_class, expected_errors=0, inspect=False,
                                  locations=None, defuse='remote'):
    def test_validation(self):
        schema, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        xs = schema_class(schema, validation='lax', locations=_locations, defuse=defuse)
        errors = [str(e) for e in xs.iter_errors(xml_file)]
        if len(errors) != expected_errors:
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (expected_errors, len(errors), '\n++++++\n'.join(errors))
            )
        if expected_errors == 0:
            self.assertTrue(True, "Successfully validated {} with schema {}".format(xml_file, schema))
        else:
            self.assertTrue(
                True,
                "Validation of {} under the schema {} with n.{} errors".format(xml_file, schema, expected_errors)
            )

    return test_validation


class TestValidation(XMLSchemaTestCase):

    def check_validity(self, xsd_component, data, expected, use_defaults=True):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.is_valid, data, use_defaults)
        elif expected:
            self.assertTrue(xsd_component.is_valid(data, use_defaults))
        else:
            self.assertFalse(xsd_component.is_valid(data, use_defaults))

    @unittest.skipIf(etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        xs = xmlschema.XMLSchema(self.abspath('cases/examples/vehicles/vehicles.xsd'))
        xt1 = etree.parse(self.abspath('cases/examples/vehicles/vehicles.xml'))
        xt2 = etree.parse(self.abspath('cases/examples/vehicles/vehicles-1_error.xml'))
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)

    def test_issue_064(self):
        self.check_validity(self.st_schema, '<name xmlns="ns"></name>', False)


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, get_testfiles, tests_factory

    print_test_header()

    # Validation test cases: those test don't run with the test_all.py script
    # because are a duplication of similar decoding tests.
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    validation_tests = tests_factory(make_test_validation_function, testfiles, 'validation', 'xml')
    globals().update(validation_tests)
    unittest.main()
