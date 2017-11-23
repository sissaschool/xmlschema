#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
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
import xmlschema
try:
    import lxml.etree as etree
except ImportError:
    etree = None

from _test_common import XMLSchemaTestCase, tests_factory


def make_test_validation_function(xml_file, schema_class=xmlschema.XMLSchema, expected_errors=0, inspect=False):
    def test_validation(self):
        schema = xmlschema.fetch_schema(xml_file)
        xs = schema_class(schema)
        errors = [str(e) for e in xs.iter_errors(xml_file)]
        if len(errors) != expected_errors:
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (expected_errors, len(errors), '\n++++++\n'.join(errors[:3]))
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

    @unittest.skipIf(etree is None, "Skip if lxml library is not installed.")
    def test_lxml(self):
        xs = xmlschema.XMLSchema('examples/vehicles/vehicles.xsd')
        xt1 = etree.parse('examples/vehicles/vehicles.xml')
        xt2 = etree.parse('examples/vehicles/vehicles-1_error.xml')
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)


if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    path = os.path.join(pkg_folder, "tests/*/testfiles")
    validation_tests = tests_factory(make_test_validation_function, path, 'validation', 'xml')
    globals().update(validation_tests)
    unittest.main()
