#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests on ElementTree data interfaces.
"""
from __future__ import unicode_literals

import unittest
import os
import sys
import importlib
import pdb

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

pdb.set_trace()

import xml.etree.ElementTree as ElementTree
import _elementtree as cElementTree
from xmlschema.etree import etree_element


class TestElementTree(unittest.TestCase):

    def test_element_tree_module(self):
        self.assertEqual(ElementTree.Element, ElementTree._Element_Py)  # C extension disabled by defusedxml
        self.assertNotEqual(ElementTree.Element, cElementTree.Element)

    def test_etree_element(self):
        self.assertEqual(etree_element, cElementTree.Element)


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
