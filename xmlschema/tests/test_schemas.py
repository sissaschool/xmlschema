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


def get_tests(pathname):
    import xmlschema

    def make_test_schema_function(xsd_file):
        def test_schema(self):
            self.assertTrue(xmlschema.XMLSchema(xsd_file), "Successfully created schema for {}".format(xsd_file))
        return test_schema

    if len(sys.argv) > 1:
        log_level = int(sys.argv.pop())
        xmlschema.set_logger('xmlschema', loglevel=log_level)

    tests = {}
    for line in fileinput.input(glob.iglob(pathname)):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_file = os.path.join(os.path.dirname(fileinput.filename()), line)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.xsd':
            continue

        test_func = make_test_schema_function(test_file)
        test_name = os.path.basename(test_file)
        klassname = 'Test_schema_{0}'.format(test_name)
        tests[klassname] = type(
            klassname, (XMLSchemaTestCase,),
            {'test_schema_{0}'.format(test_name): test_func}
        )
    return tests

if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    globals().update(get_tests(os.path.join(pkg_folder, "tests/*/testfiles")))
    unittest.main()
