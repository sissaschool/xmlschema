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
This module runs tests concerning the schema's validation for XML files for xmlschema package.
"""
from _test_common import *
import fileinput


def make_test_validation_function(xml_file, schema, num_errors):
    def test_validation(self):
        xs = xmlschema.XMLSchema(schema)
        errors = [str(e) for e in xs.iter_errors(xml_file)]
        if len(errors) != num_errors:
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (num_errors, len(errors), '\n++++++\n'.join(errors[:3]))
            )
        if num_errors == 0:
            self.assertTrue(True, "Successfully validated {} with schema {}".format(xml_file, schema))
        else:
            self.assertTrue(
                True,
                "Validation of {} under the schema {} with n.{} errors".format(xml_file, schema, num_errors)
            )
    return test_validation


if __name__ == '__main__':
    import glob
    import os
    import sys

    if os.path.dirname(__file__):
        rel_path = os.path.dirname(os.path.dirname(__file__))
        pkg_folder = os.path.realpath(rel_path)
    else:
        rel_path = ".."
        pkg_folder = os.path.realpath(rel_path)

    sys.path.insert(0, pkg_folder)
    import xmlschema
    from xmlschema.resources import load_xml
    from xmlschema.core import XSI_NAMESPACE_PATH
    from xmlschema.qnames import get_qname
    if len(sys.argv) > 1:
        LOG_LEVEL = int(sys.argv.pop())
        xmlschema.set_logger('xmlschema', loglevel=LOG_LEVEL)

    test_files = glob.iglob(os.path.join(rel_path, "tests/*/testfiles"))
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
            raise ValueError("Schema not found for the document!")

        test_func = make_test_validation_function(test_file, schema_file, num_errors)
        test_name = os.path.basename(test_file)
        klassname = 'Test_validation_{0}'.format(test_name)
        globals()[klassname] = type(
            klassname, (XMLSchemaTestCase,),
            {'test_validation_{0}'.format(test_name): test_func}
        )
    unittest.main()
