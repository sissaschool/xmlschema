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
This module runs tests concerning the decoding of XML files for xmlschema package.
"""
import fileinput
from _test_common import *


def make_test_decoding_function(xml_root, schema, expected_errors):
    def test_decoding(self):
        xs = xmlschema.XMLSchema(schema)
        try:
            xmlschema.element_to_dict(xml_root, xs)
        except XMLSchemaMultipleValidatorErrors as err:
            if len(getattr(err, 'errors', [])) != expected_errors:
                raise
        else:
            if expected_errors > 0:
                raise ValueError(
                    "No errors when {} expected!".format(expected_errors)
                )
        self.assertTrue(True, "Successfully test decoding for {}".format(xml_root))
    return test_decoding


if __name__ == '__main__':
    import glob
    import os
    import sys

    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)

    sys.path.insert(0, pkg_folder)
    import xmlschema
    from xmlschema.exceptions import XMLSchemaMultipleValidatorErrors
    from xmlschema.core import XSI_NAMESPACE_PATH
    from xmlschema.utils import get_qname
    from xmlschema.resources import load_xml
    if len(sys.argv) > 1:
        LOG_LEVEL = int(sys.argv.pop())
        xmlschema.set_logger('xmlschema', loglevel=LOG_LEVEL)

    test_files = glob.iglob(os.path.join(pkg_folder, "tests/*/testfiles"))
    for line in fileinput.input(test_files):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_args = get_test_args(line)
        filename = test_args[0]
        try:
            num_errors = int(test_args[1])
        except IndexError:
            num_errors = 0

        test_file = os.path.join(os.path.dirname(fileinput.filename()), filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.xml':
            continue

        xml_text, xml_root, xml_uri = load_xml(test_file)
        XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
        schema_locations = xml_root.find('.[@%s]' % XSI_SCHEMA_LOCATION).attrib.get(XSI_SCHEMA_LOCATION)
        for schema_location in schema_locations.strip().split():
            schema_file = os.path.join(os.path.dirname(test_file), schema_location)
            if os.path.isfile(schema_file):
                break
        else:
            raise ValueError("Not schema for the document!")

        test_func = make_test_decoding_function(xml_root, schema_file, num_errors)
        test_name = os.path.basename(test_file)
        klassname = 'Test_decoding_{0}'.format(test_name)
        globals()[klassname] = type(
            klassname, (XMLSchemaTestCase,),
            {'test_decoding_{0}'.format(test_name): test_func}
        )
    unittest.main()
