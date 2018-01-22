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
This module runs tests concerning resources.
"""
import unittest
import os
import sys

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema


class TestResources(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)
        cls.xs1 = xmlschema.XMLSchema(os.path.join(cls.test_dir, "cases/examples/vehicles/vehicles.xsd"))
        cls.xs2 = xmlschema.XMLSchema(os.path.join(cls.test_dir, "cases/examples/collection/collection.xsd"))
        cls.cars = cls.xs1.elements['vehicles'].type.content_type[0]
        cls.bikes = cls.xs1.elements['vehicles'].type.content_type[1]

    def test_absolute_path(self):
        url1 = "https://example.com/xsd/other_schema.xsd"
        self.assertTrue(xmlschema.normalize_url(url1, base_url="/path_my_schema/schema.xsd") == url1)

    def test_fetch_resource(self):
        wrong_path = os.path.join(self.test_dir, 'resources/dummy_file.txt')
        self.assertRaises(xmlschema.XMLSchemaURLError, xmlschema.fetch_resource, wrong_path)
        right_path = os.path.join(self.test_dir, 'resources/dummy file.txt')
        self.assertTrue(xmlschema.fetch_resource(right_path).endswith('y%20file.txt'))

    def test_get_namespace(self):
        self.assertFalse(xmlschema.etree_get_namespaces(os.path.join(self.test_dir, 'resources/malformed.xml')))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
