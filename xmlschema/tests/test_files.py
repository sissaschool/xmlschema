#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests on XSD or XML files provided by arguments.
"""
from __future__ import print_function, unicode_literals
import unittest
import os
import argparse

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.tests.test_factory import xsd_version_number, \
    make_schema_test_class, make_validator_test_class


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=True)
    parser.usage = "TEST_FILE [OPTIONS]\nTry 'TEST_FILE --help' for more information."

    parser.add_argument(
        '--version', dest='version', metavar='VERSION', type=xsd_version_number, default='1.0',
        help="XSD schema version to use for testing (default is 1.0)."
    )
    parser.add_argument(
        'files', metavar='[FILE ...]', nargs='*',
        help='Input files. Each argument can be a file path or a glob pathname. '
             'A "-" stands for standard input. If no arguments are given then processes '
             'all the files included within the scope of the selected applications.'
    )
    args = parser.parse_args()

    if args.version == '1.0':
        schema_class = XMLSchema10
        check_with_lxml = True
    else:
        schema_class = XMLSchema11
        check_with_lxml = False

    test_num = 1
    test_args = argparse.Namespace(
        errors=0, warnings=0, inspect=False, locations=(), defuse='never', skip=False, debug=False
    )

    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()

    for test_file in args.files:
        if not os.path.isfile(test_file):
            continue
        elif test_file.endswith('xsd'):
            test_class = make_schema_test_class(
                test_file, test_args, test_num, schema_class, check_with_lxml
            )
            test_num += 1
        elif test_file.endswith('xml'):
            test_class = make_validator_test_class(
                test_file, test_args, test_num, schema_class, check_with_lxml
            )
            test_num += 1
        else:
            continue

        print("Add test %r for file %r ..." % (test_class.__name__, test_file))
        test_suite.addTest(test_loader.loadTestsFromTestCase(test_class))

    if test_num == 1:
        print("No XSD or XML file to test, exiting ...")
    else:
        runner = unittest.TextTestRunner()
        runner.run(test_suite)
