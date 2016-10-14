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
Common imports and methods for unittest scripts of 'xmlschema' package.
"""
import unittest
import re


class XMLSchemaTestCase(unittest.TestCase):
    longMessage = True


def get_test_args(args_line):
    return re.split(r'(?<!\\) ', args_line)