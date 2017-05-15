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

xs = XMLSchema("examples/vehicles/vehicles.xsd")


class TestXPath(unittest.TestCase):

    def test_location_path(self):
        elements = sorted(xs.elements.values(), key=lambda x: x.name)
        self.assertTrue(xs.findall('.'))
        self.assertTrue(isinstance(xs.find('.'), XMLSchema))
        self.assertTrue(sorted(xs.findall("*"), key=lambda x: x.name) == elements)
        self.assertTrue(xs.findall("*") == xs.findall("./*"))
        self.assertTrue(xs.find("./vh:bikes") == xs.elements['bikes'])
        self.assertTrue(xs.find("./vh:vehicles/vh:cars").name == xs.elements['cars'].name)
        self.assertFalse(xs.find("./vh:vehicles/vh:cars") == xs.elements['cars'])
        self.assertFalse(xs.find("/vh:vehicles/vh:cars") == xs.elements['cars'])
        self.assertTrue(xs.find("vh:vehicles/vh:cars/..") == xs.elements['vehicles'])
        self.assertTrue(xs.find("vh:vehicles/*/..") == xs.elements['vehicles'])
        self.assertTrue(xs.find("vh:vehicles/vh:cars/../vh:cars") == xs.find("vh:vehicles/vh:cars"))

    def test_axis(self):
        self.assertTrue(xs.find("vh:vehicles/child::vh:cars/..") == xs.elements['vehicles'])

    def test_subscription(self):
        cars = xs.find("./vh:vehicles/vh:cars")
        bikes = xs.find("./vh:vehicles/vh:bikes")
        self.assertTrue(len(xs.findall("./vh:vehicles/*")) == 2)
        self.assertTrue(xs.findall("./vh:vehicles/*[2]") == [bikes])
        self.assertTrue(xs.findall("./vh:vehicles/*[3]") == [])
        self.assertTrue(xs.findall("./vh:vehicles/*[last()-1]") == [cars])
        self.assertTrue(xs.findall("./vh:vehicles/*[position()=last()]") == [bikes])

    def test_group(self):
        self.assertTrue(xs.findall("/(vh:vehicles/*/*)") == xs.findall("/vh:vehicles/*/*"))
        self.assertTrue(xs.findall("/(vh:vehicles/*/*)[1]") == xs.findall("/vh:vehicles/*/*[1]"))

    def test_predicate(self):
        car = xs.elements['cars'].type.content_type[0]
        cars = xs.find("./vh:vehicles/vh:cars")
        self.assertTrue(xs.findall("./vh:vehicles/vh:cars/vh:car[@vh:make]") == [car])
        self.assertTrue(xs.findall("./vh:vehicles/vh:cars/vh:car[@make]") == [])
        self.assertTrue(xs.findall("./vh:vehicles/vh:cars['ciao']") == [cars])
        self.assertTrue(xs.findall("./vh:vehicles/*['']") == [])

    def test_wrong_paths(self):
        self.assertRaises(XMLSchemaXPathError, xs.find, './*[')
        self.assertRaises(XMLSchemaXPathError, xs.find, './*)')
        self.assertRaises(XMLSchemaXPathError, xs.find, './*3')


if __name__ == '__main__':
    unittest.main()
