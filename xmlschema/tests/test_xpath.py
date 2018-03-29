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
This module runs tests on XPath selector and find functions.
"""
import unittest
import os
import sys
from xml.etree import ElementTree as et

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from elementpath import XPath1Parser, Selector, ElementPathSyntaxError

from xmlschema import XMLSchema


class XsdXPathTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)
        cls.xs1 = XMLSchema(os.path.join(cls.test_dir, "cases/examples/vehicles/vehicles.xsd"))
        cls.xs2 = XMLSchema(os.path.join(cls.test_dir, "cases/examples/collection/collection.xsd"))
        cls.cars = cls.xs1.elements['vehicles'].type.content_type[0]
        cls.bikes = cls.xs1.elements['vehicles'].type.content_type[1]

    def test_xpath_wrong_syntax(self):
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*[')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*)')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*3')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './@3')

    def test_xpath_extra_spaces(self):
        self.assertTrue(self.xs1.find('./ *') is not None)
        self.assertTrue(self.xs1.find("\t\n vh:vehicles / vh:cars / .. /  vh:cars") == self.cars)

    def test_xpath_location_path(self):
        elements = sorted(self.xs1.elements.values(), key=lambda x: x.name)
        self.assertTrue(self.xs1.findall('.'))
        self.assertTrue(isinstance(self.xs1.find('.'), XMLSchema))
        self.assertTrue(sorted(self.xs1.findall("*"), key=lambda x: x.name) == elements)
        self.assertTrue(self.xs1.findall("*") == self.xs1.findall("./*"))
        self.assertTrue(self.xs1.find("./vh:bikes") == self.xs1.elements['bikes'])
        self.assertTrue(self.xs1.find("./vh:vehicles/vh:cars").name == self.xs1.elements['cars'].name)
        self.assertFalse(self.xs1.find("./vh:vehicles/vh:cars") == self.xs1.elements['cars'])
        self.assertFalse(self.xs1.find("/vh:vehicles/vh:cars") == self.xs1.elements['cars'])
        self.assertTrue(self.xs1.find("vh:vehicles/vh:cars/..") == self.xs1.elements['vehicles'])
        self.assertTrue(self.xs1.find("vh:vehicles/*/..") == self.xs1.elements['vehicles'])
        self.assertTrue(self.xs1.find("vh:vehicles/vh:cars/../vh:cars") == self.xs1.find("vh:vehicles/vh:cars"))

    def test_xpath_axis(self):
        self.assertTrue(self.xs1.find("vh:vehicles/child::vh:cars/..") == self.xs1.elements['vehicles'])

    def test_xpath_subscription(self):
        self.assertTrue(len(self.xs1.findall("./vh:vehicles/*")) == 2)
        self.assertTrue(self.xs1.findall("./vh:vehicles/*[2]") == [self.bikes])
        self.assertTrue(self.xs1.findall("./vh:vehicles/*[3]") == [])
        self.assertTrue(self.xs1.findall("./vh:vehicles/*[last()-1]") == [self.cars])
        self.assertTrue(self.xs1.findall("./vh:vehicles/*[position()=last()]") == [self.bikes])

    def test_xpath_group(self):
        self.assertTrue(self.xs1.findall("/(vh:vehicles/*/*)") == self.xs1.findall("/vh:vehicles/*/*"))
        self.assertTrue(self.xs1.findall("/(vh:vehicles/*/*)[1]") == self.xs1.findall("/vh:vehicles/*/*[1]"))

    def test_xpath_predicate(self):
        car = self.xs1.elements['cars'].type.content_type[0]
        self.assertTrue(self.xs1.findall("./vh:vehicles/vh:cars/vh:car[@make]") == [car])
        self.assertTrue(self.xs1.findall("./vh:vehicles/vh:cars/vh:car[@make]") == [car])
        self.assertTrue(self.xs1.findall("./vh:vehicles/vh:cars['ciao']") == [self.cars])
        self.assertTrue(self.xs1.findall("./vh:vehicles/*['']") == [])

    def test_xpath_descendants(self):
        selector = Selector('.//xs:element', self.xs2.namespaces, parser=XPath1Parser)
        elements = list(selector.iter_select(self.xs2.root))
        self.assertTrue(len(elements) == 14)
        selector = Selector('.//xs:element|.//xs:attribute|.//xs:keyref', self.xs2.namespaces, parser=XPath1Parser)
        elements = list(selector.iter_select(self.xs2.root))
        self.assertTrue(len(elements) == 17)

    def test_xpath_issues(self):
        namespaces = {'ps': "http://schemas.microsoft.com/powershell/2004/04"}
        selector = Selector("./ps:Props/*|./ps:MS/*", namespaces=namespaces, parser=XPath1Parser)
        self.assertTrue(selector.root_token.tree,
                        '(| (/ (/ (.) (: (ps) (Props))) (*)) (/ (/ (.) (: (ps) (MS))) (*)))')


class ElementTreeXPathTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)

    def test_rel_xpath_boolean(self):
        root = et.XML('<A><B><C/></B></A>')
        el = root[0]
        self.assertTrue(Selector('boolean(C)').iter_select(el))
        self.assertFalse(next(Selector('boolean(D)').iter_select(el)))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
