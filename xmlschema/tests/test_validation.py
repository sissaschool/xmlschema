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


def make_test_validation_function(xml_file, schema_class, expected_errors=0, inspect=False,
                                  locations=None, defuse='remote'):
    def test_validation(self):
        schema, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        xs = schema_class(schema, locations=_locations, defuse=defuse)
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


class TestValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)

    @unittest.skipIf(etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        xs = xmlschema.XMLSchema(os.path.join(self.test_dir, 'cases/examples/vehicles/vehicles.xsd'))
        xt1 = etree.parse(os.path.join(self.test_dir, 'cases/examples/vehicles/vehicles.xml'))
        xt2 = etree.parse(os.path.join(self.test_dir, 'cases/examples/vehicles/vehicles-1_error.xml'))
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, tests_factory

    print_test_header()

    if '-s' not in sys.argv and '--skip-extra' not in sys.argv:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '*/testfiles')
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases/testfiles')
        try:
            sys.argv.remove('-s')
        except ValueError:
            sys.argv.remove('--skip-extra')

    # Validation test cases: those test don't run with the test_all.py script because are
    # a duplication of similar decoding tests.
    validation_tests = tests_factory(make_test_validation_function, path, 'validation', 'xml')
    globals().update(validation_tests)
    unittest.main()
