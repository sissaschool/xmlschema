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

from xmlschema import fetch_namespaces, fetch_resource, normalize_url, XMLResource, XMLSchemaURLError
from xmlschema.tests import XMLSchemaTestCase


class TestResources(XMLSchemaTestCase):

    def test_normalize_url(self):
        url1 = "https://example.com/xsd/other_schema.xsd"
        self.assertEqual(normalize_url(url1, base_url="/path_my_schema/schema.xsd"), url1)

        parent_url = 'file://' + os.path.dirname(os.getcwd())
        self.assertEqual(normalize_url('../dir1/./dir2'), os.path.join(parent_url, 'dir1/dir2'))
        self.assertEqual(normalize_url('../dir1/./dir2', '/home', keep_relative=True), 'file:///dir1/dir2')
        self.assertEqual(normalize_url('../dir1/./dir2', 'file:///home'), 'file:///dir1/dir2')

        self.assertEqual(normalize_url('other.xsd', 'file:///home'), 'file:///home/other.xsd')
        self.assertEqual(normalize_url('other.xsd', 'file:///home/'), 'file:///home/other.xsd')
        self.assertEqual(normalize_url('file:other.xsd', 'file:///home'), 'file:///home/other.xsd')

        abs_path = 'file://{}/'.format(os.getcwd())
        self.assertEqual(normalize_url('file:other.xsd', keep_relative=True), 'file:other.xsd')
        self.assertEqual(normalize_url('file:other.xsd'), abs_path + 'other.xsd')
        self.assertEqual(normalize_url('file:other.xsd', 'http://site/base', True), 'file:other.xsd')
        self.assertEqual(normalize_url('file:other.xsd', 'http://site/base'), abs_path + 'other.xsd')

        self.assertEqual(normalize_url('dummy path.xsd'), abs_path + 'dummy path.xsd')
        self.assertEqual(normalize_url('dummy path.xsd', 'http://site/base'), 'http://site/base/dummy%20path.xsd')
        self.assertEqual(normalize_url('dummy path.xsd', 'file://host/home/'), 'file://host/home/dummy path.xsd')


    def test_fetch_resource(self):
        wrong_path = os.path.join(self.test_dir, 'resources/dummy_file.txt')
        self.assertRaises(XMLSchemaURLError, fetch_resource, wrong_path)
        right_path = os.path.join(self.test_dir, 'resources/dummy file.txt')
        self.assertTrue(fetch_resource(right_path).endswith('dummy file.txt'))

    def test_fetch_namespaces(self):
        self.assertFalse(fetch_namespaces(os.path.join(self.test_dir, 'resources/malformed.xml')))

    def test_class_get_namespaces(self):
        with open(self.vh_xml_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.url, normalize_url(self.vh_xml_file))
            self.assertEqual(resource.get_namespaces().keys(), {'vh', 'xsi'})

        with open(self.vh_schema_file) as schema_file:
            resource = XMLResource(schema_file)
            self.assertEqual(resource.url, normalize_url(self.vh_schema_file))
            self.assertEqual(resource.get_namespaces().keys(), {'xs', 'vh'})

        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.url, normalize_url(self.col_xml_file))
        self.assertEqual(resource.get_namespaces().keys(), {'col', 'xsi'})

        resource = XMLResource(self.col_schema_file)
        self.assertEqual(resource.url, normalize_url(self.col_schema_file))
        self.assertEqual(resource.get_namespaces().keys(), {'', 'xs'})

    def test_class_get_locations(self):
        resource = XMLResource(self.col_xml_file)
        self.assertEqual(resource.url, normalize_url(self.col_xml_file))
        locations = resource.get_locations([('ns', 'other.xsd')])
        self.assertEqual(len(locations), 2)
        self.assertEqual(locations[0][1], 'file://{}/other.xsd'.format(self.col_dir))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
