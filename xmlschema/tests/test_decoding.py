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
This module runs tests concerning the decoding of XML files with the 'xmlschema' package.
"""
from _test_common import *
import glob
import fileinput


def get_tests(pathname):
    import xmlschema
    from xmlschema.exceptions import XMLSchemaDecodeError, XMLSchemaValidationError
    from xmlschema.core import XSI_NAMESPACE_PATH
    from xmlschema.utils import get_qname
    from xmlschema.resources import load_xml_resource

    def make_test_decoding_function(xml_file, schema, expected_errors):
        def test_decoding(self):
            xs = xmlschema.XMLSchema(schema)
            errors = []
            chunks = []
            for obj in xs.iter_decode(xml_file):
                if isinstance(obj, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    errors.append(obj)
                else:
                    chunks.append(obj)
            if len(errors) != expected_errors:
                raise ValueError(
                    "n.%d errors expected, found %d: %s" % (
                        expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors[:3]])
                    )
                )
            if not chunks:
                raise ValueError("No decoded object returned!!")
            elif len(chunks) > 1:
                raise ValueError("Too many ({}) decoded objects returned: {}".format(len(chunks), chunks))
            elif not isinstance(chunks[0], dict):
                raise ValueError("Decoded object is not a dictionary: {}".format(chunks))
            else:
                self.assertTrue(True, "Successfully test decoding for {}".format(xml_file))

        return test_decoding

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

        xml_root = load_xml_resource(test_file)
        xsi_schema_location = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
        schema_locations = xml_root.find('.[@%s]' % xsi_schema_location).attrib.get(xsi_schema_location)
        for schema_location in schema_locations.strip().split():
            schema_file = os.path.join(os.path.dirname(test_file), schema_location)
            if os.path.isfile(schema_file):
                break
        else:
            raise ValueError("Not schema for the document!")

        test_func = make_test_decoding_function(test_file, schema_file, tot_errors)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        if test_only is None or test_num == test_only:
            klassname = 'Test_decoding_{0}_{1}'.format(test_num, test_name)
            tests[klassname] = type(
                klassname, (XMLSchemaTestCase,),
                {'test_decoding_{0}'.format(test_num): test_func}
            )

    return tests


if __name__ == '__main__':
    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    globals().update(get_tests(os.path.join(pkg_folder, "tests/*/testfiles")))
    unittest.main()
