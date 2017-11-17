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
Common imports and methods for unittest scripts of the 'xmlschema' package.
"""
import unittest
import re
import sys
import os
import glob
import fileinput

# Move into the test directory and adds the path of the package that contains the test.
os.chdir(os.path.dirname(__file__))
pkg_search_path = os.path.abspath('../..')
if sys.path[0] != pkg_search_path:
    sys.path.insert(0, pkg_search_path)


class XMLSchemaTestCase(unittest.TestCase):
    longMessage = True


def get_test_args(args_line):
    try:
        return re.split(r'(?<!\\) ', args_line.split('#', 1)[0])
    except IndexError:
        return re.split(r'(?<!\\) ', args_line)


def tests_factory(test_function_builder, pathname, label="validation", suffix="xml"):

    # Optional int arguments: [<test_only>]
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
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.%s' % suffix:
            continue

        test_func = test_function_builder(test_file, tot_errors)
        test_name = os.path.join(os.path.dirname(sys.argv[0]), os.path.relpath(test_file))
        test_num += 1
        if test_only is None or test_num == test_only:
            klassname = 'Test_{0}_{1}_{2}'.format(label, test_num, test_name)
            tests[klassname] = type(
                klassname, (XMLSchemaTestCase,),
                {'test_{0}_{1}'.format(label, test_num): test_func}
            )

    return tests
