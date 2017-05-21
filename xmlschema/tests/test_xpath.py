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
This module runs tests on XPath selector and find functions.
"""
from _test_common import *

from xmlschema.exceptions import XMLSchemaXPathError
from xmlschema import XMLSchema


class TestXPath(unittest.TestCase):
    xs = XMLSchema("examples/vehicles/vehicles.xsd")
    cars = xs.elements['vehicles'].type.content_type[0]
    bikes = xs.elements['vehicles'].type.content_type[1]

    def test_wrong_syntax(self):
        self.assertRaises(XMLSchemaXPathError, self.xs.find, './*[')
        self.assertRaises(XMLSchemaXPathError, self.xs.find, './*)')
        self.assertRaises(XMLSchemaXPathError, self.xs.find, './*3')
        self.assertRaises(XMLSchemaXPathError, self.xs.find, './@3')

    def test_correct_syntax(self):
        self.assertTrue(self.xs.find('./ *') is not None)
        self.assertTrue(self.xs.find("\t\n vh:vehicles / vh:cars / .. /  vh:cars") == self.cars)

    def test_location_path(self):
        elements = sorted(self.xs.elements.values(), key=lambda x: x.name)
        self.assertTrue(self.xs.findall('.'))
        self.assertTrue(isinstance(self.xs.find('.'), XMLSchema))
        self.assertTrue(sorted(self.xs.findall("*"), key=lambda x: x.name) == elements)
        self.assertTrue(self.xs.findall("*") == self.xs.findall("./*"))
        self.assertTrue(self.xs.find("./vh:bikes") == self.xs.elements['bikes'])
        self.assertTrue(self.xs.find("./vh:vehicles/vh:cars").name == self.xs.elements['cars'].name)
        self.assertFalse(self.xs.find("./vh:vehicles/vh:cars") == self.xs.elements['cars'])
        self.assertFalse(self.xs.find("/vh:vehicles/vh:cars") == self.xs.elements['cars'])
        self.assertTrue(self.xs.find("vh:vehicles/vh:cars/..") == self.xs.elements['vehicles'])
        self.assertTrue(self.xs.find("vh:vehicles/*/..") == self.xs.elements['vehicles'])
        self.assertTrue(self.xs.find("vh:vehicles/vh:cars/../vh:cars") == self.xs.find("vh:vehicles/vh:cars"))

    def test_axis(self):
        self.assertTrue(self.xs.find("vh:vehicles/child::vh:cars/..") == self.xs.elements['vehicles'])

    def test_subscription(self):
        self.assertTrue(len(self.xs.findall("./vh:vehicles/*")) == 2)
        self.assertTrue(self.xs.findall("./vh:vehicles/*[2]") == [self.bikes])
        self.assertTrue(self.xs.findall("./vh:vehicles/*[3]") == [])
        self.assertTrue(self.xs.findall("./vh:vehicles/*[last()-1]") == [self.cars])
        self.assertTrue(self.xs.findall("./vh:vehicles/*[position()=last()]") == [self.bikes])

    def test_group(self):
        self.assertTrue(self.xs.findall("/(vh:vehicles/*/*)") == self.xs.findall("/vh:vehicles/*/*"))
        self.assertTrue(self.xs.findall("/(vh:vehicles/*/*)[1]") == self.xs.findall("/vh:vehicles/*/*[1]"))

    def test_predicate(self):
        car = self.xs.elements['cars'].type.content_type[0]
        self.assertTrue(self.xs.findall("./vh:vehicles/vh:cars/vh:car[@vh:make]") == [car])
        self.assertTrue(self.xs.findall("./vh:vehicles/vh:cars/vh:car[@make]") == [])
        self.assertTrue(self.xs.findall("./vh:vehicles/vh:cars['ciao']") == [self.cars])
        self.assertTrue(self.xs.findall("./vh:vehicles/*['']") == [])


if __name__ == '__main__':
    unittest.main()
