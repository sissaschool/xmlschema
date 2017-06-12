#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
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
from _test_common import *
import glob
import fileinput
import xmlschema
try:
    import lxml.etree as etree
except ImportError:
    etree = None


def create_validation_tests(pathname):

    def make_test_validation_function(xml_file, schema, expected_errors):
        def test_validation(self):
            xs = xmlschema.XMLSchema(schema)
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

    # Two optional int arguments: [<test_only> [<log_level>]]
    if len(sys.argv) > 2:
        log_level = int(sys.argv.pop())
        xmlschema.set_logger('xmlschema', loglevel=log_level)
    if len(sys.argv) > 1:
        test_only = int(sys.argv.pop())
    else:
        test_only = None

    tests = {}
    test_num = 0
    for line in fileinput.input(glob.iglob(pathname)):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_args = get_test_args(line)
        filename = test_args[0]
        try:
            tot_errors = int(test_args[1])
        except (IndexError, ValueError):
            tot_errors = 0

        test_file = os.path.join(os.path.dirname(fileinput.filename()), filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.xml':
            continue

        schema_file = xmlschema.fetch_schema(test_file)
        test_func = make_test_validation_function(test_file, schema_file, tot_errors)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        if test_only is None or test_num == test_only:
            klassname = 'Test_validation_{0}_{1}'.format(test_num, test_name)
            tests[klassname] = type(
                klassname, (XMLSchemaTestCase,),
                {'test_validation_{0}'.format(test_num): test_func}
            )

    return tests


class TestValidation(unittest.TestCase):

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
    globals().update(create_validation_tests(os.path.join(pkg_folder, "tests/*/testfiles")))
    unittest.main()
