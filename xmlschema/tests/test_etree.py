#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2018-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Tests concerning packaging and installation environment.
"""
import unittest
import importlib
import sys

from xmlschema.etree import ElementTree as CElementTree
from xmlschema.etree import PyElementTree, etree_tostring

import xml.etree.ElementTree as ElementTree


class TestEnvironment(unittest.TestCase):

    def test_element_tree(self):
        self.assertNotEqual(ElementTree.Element, ElementTree._Element_Py, msg="cElementTree not available!")
        elem = PyElementTree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element />')
        self.assertEqual(importlib.import_module('xml.etree.ElementTree'), ElementTree)
        self.assertEqual(CElementTree, ElementTree)

    def test_pure_python_element_tree(self):
        if sys.version_info >= (3,):
            self.assertEqual(PyElementTree.Element, PyElementTree._Element_Py)  # C extensions disabled by defusedxml
            self.assertNotEqual(ElementTree.Element, PyElementTree.Element)
        else:
            self.assertNotEqual(PyElementTree.Element, PyElementTree._Element_Py)

        elem = PyElementTree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element />')


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
