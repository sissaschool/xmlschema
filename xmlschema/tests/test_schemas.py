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
This module runs tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
from _test_common import *
import fileinput
import glob


def create_schema_tests(pathname):
    import xmlschema
    from xmlschema.exceptions import XMLSchemaParseError, XMLSchemaURLError, XMLSchemaKeyError

    def make_test_schema_function(xsd_file, expected_errors):
        def test_schema(self):
            # print("Run %s" % self.id())
            meta_schema = xmlschema.XMLSchema.META_SCHEMA
            errors = [str(e) for e in meta_schema.iter_errors(xsd_file)]

            try:
                xs = xmlschema.XMLSchema(xsd_file)
            except (XMLSchemaParseError, XMLSchemaURLError, XMLSchemaKeyError) as err:
                num_errors = len(errors) + 1
                errors.append(str(err))
            else:
                num_errors = len(errors) + len(xs.errors)

            if num_errors != expected_errors:
                raise ValueError(
                    "n.%d errors expected, found %d: %s" % (
                        expected_errors, num_errors, '\n++++++\n'.join(errors[:3])
                    )
                )
            else:
                self.assertTrue(True, "Successfully created schema for {}".format(xsd_file))
        return test_schema

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
            total_errors = int(test_args[1])
        except (IndexError, ValueError):
            total_errors = 0

        test_file = os.path.join(os.path.dirname(fileinput.filename()), filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.xsd':
            continue

        test_func = make_test_schema_function(test_file, total_errors)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        if test_only is None or test_num == test_only:
            klassname = 'Test_schema_{0:03d}_{1}'.format(test_num, test_name)
            tests[klassname] = type(
                klassname, (XMLSchemaTestCase,),
                {'test_schema_{0:03d}'.format(test_num): test_func}
            )

    return tests


if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    globals().update(create_schema_tests(os.path.join(pkg_folder, "tests/*/testfiles")))
    unittest.main()
