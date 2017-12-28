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

from xmlschema import XMLSchemaParseError, XMLSchemaURLError
from _test_common import tests_factory, SchemaObserver


def make_test_schema_function(xsd_file, schema_class, expected_errors=0, inspect=False):
    def test_schema(self):
        if inspect:
            SchemaObserver.clear()
        # print("Run %s" % self.id())
        try:
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax')
            else:
                xs = schema_class(xsd_file)
        except (XMLSchemaParseError, XMLSchemaURLError, KeyError) as err:
            num_errors = 1
            errors = [str(err)]
        else:
            num_errors = len(xs.all_errors)
            errors = xs.all_errors

            if inspect:
                components_ids = set([id(c) for c in xs.iter_components()])
                missing = [c for c in SchemaObserver.components if id(c) not in components_ids]
                if any([c for c in missing]):
                    raise ValueError("schema missing %d components: %r" % (len(missing), missing))

        if num_errors != expected_errors:
            print("\n%s: %r errors, %r expected." % (self.id()[13:], num_errors, expected_errors))
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
    schema_tests = tests_factory(make_test_schema_function, path, label='schema', suffix='xsd')
    globals().update(schema_tests)
    unittest.main()
