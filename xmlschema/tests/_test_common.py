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
Common imports and methods for unittest scripts of the 'xmlschema' package.
"""
import unittest
import re
import sys
import os

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
