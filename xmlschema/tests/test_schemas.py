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
This module runs tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
import unittest
import os
import sys

import xmlschema
from xmlschema.exceptions import XMLSchemaParseError, XMLSchemaURLError, XMLSchemaKeyError
from _test_common import tests_factory


def make_test_schema_function(xsd_file, expected_errors):
    def test_schema(self):
        # print("Run %s" % self.id())
        try:
            if expected_errors > 0:
                xs = xmlschema.XMLSchema(xsd_file, validation='lax')
            else:
                xs = xmlschema.XMLSchema(xsd_file)
        except (XMLSchemaParseError, XMLSchemaURLError, XMLSchemaKeyError) as err:
            num_errors = 1
            errors = [str(err)]
        else:
            num_errors = len(xs.all_errors)
            errors = xs.all_errors

        if num_errors != expected_errors:
            print("\nTest n.%r: %r errors, %r expected." % (self.id()[-3:], num_errors, expected_errors))
            if num_errors == 0:
                raise ValueError("found no errors when %d expected." % expected_errors)
            else:
                raise ValueError(
                    "n.%d errors expected, found %d: %s" % (expected_errors, num_errors, errors[0])
                )
        else:
            self.assertTrue(True, "Successfully created schema for {}".format(xsd_file))

    return test_schema


if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    path = os.path.join(pkg_folder, "tests/*/testfiles")
    schema_tests = tests_factory(make_test_schema_function, path, 'schema', 'xsd')
    globals().update(schema_tests)
    unittest.main()
