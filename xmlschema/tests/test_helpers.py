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
This module runs tests on various internal helper functions.
"""
from __future__ import unicode_literals

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

from xmlschema.namespaces import get_namespace, XSD_NAMESPACE, XSI_NAMESPACE
from xmlschema.qnames import (
    xsd_qname, get_qname, local_name, prefixed_to_qname, qname_to_prefixed,
    XSI_TYPE, XSD_SCHEMA_TAG, XSD_ELEMENT_TAG, XSD_SIMPLE_TYPE_TAG
)


class TestNamespaces(unittest.TestCase):

    def test_get_namespace_function(self):
        self.assertEqual(get_namespace(XSD_SIMPLE_TYPE_TAG), XSD_NAMESPACE)
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace(None), '')


class TestQualifiedNames(unittest.TestCase):

    def test_xsd_qname_function(self):
        self.assertEqual(xsd_qname('element'), '{%s}element' % XSD_NAMESPACE)

    def test_get_qname_functions(self):
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT_TAG)
        self.assertEqual(get_qname(XSI_NAMESPACE, 'type'), XSI_TYPE)

        self.assertEqual(get_qname(XSI_NAMESPACE, ''), '')
        self.assertEqual(get_qname(XSI_NAMESPACE, None), None)
        self.assertEqual(get_qname(XSI_NAMESPACE, 0), 0)
        self.assertEqual(get_qname(XSI_NAMESPACE, False), False)
        self.assertRaises(TypeError, get_qname, XSI_NAMESPACE, True)
        self.assertEqual(get_qname(None, True), True)

        self.assertEqual(get_qname(None, 'element'), 'element')
        self.assertEqual(get_qname(None, ''), '')
        self.assertEqual(get_qname('', 'element'), 'element')

    def test_local_name_functions(self):
        self.assertEqual(local_name(XSD_SCHEMA_TAG), 'schema')
        self.assertEqual(local_name('schema'), 'schema')
        self.assertEqual(local_name(''), '')
        self.assertEqual(local_name(None), None)

        self.assertRaises(ValueError, local_name, '{ns name')
        self.assertRaises(TypeError, local_name, 1.0)
        self.assertRaises(TypeError, local_name, 0)

    def test_prefixed_to_qname_functions(self):
        namespaces = {'xs': XSD_NAMESPACE, 'xsi': XSI_NAMESPACE}
        self.assertEqual(prefixed_to_qname('xs:element', namespaces), XSD_ELEMENT_TAG)
        self.assertEqual(prefixed_to_qname('xsi:type', namespaces), XSI_TYPE)

        self.assertEqual(prefixed_to_qname(XSI_TYPE, namespaces), XSI_TYPE)
        self.assertEqual(prefixed_to_qname('element', namespaces), 'element')
        self.assertEqual(prefixed_to_qname('', namespaces), '')
        self.assertEqual(prefixed_to_qname(None, namespaces), None)

        self.assertRaises(ValueError, prefixed_to_qname, 'xsi:type', {})
        self.assertRaises(ValueError, prefixed_to_qname, 'xml:lang', namespaces)

    def test_qname_to_prefixed_functions(self):
        namespaces = {'xs': XSD_NAMESPACE, 'xsi': XSI_NAMESPACE}
        self.assertEqual(qname_to_prefixed(XSD_ELEMENT_TAG, namespaces), 'xs:element')
        self.assertEqual(qname_to_prefixed('xs:element', namespaces), 'xs:element')
        self.assertEqual(qname_to_prefixed('element', namespaces), 'element')

        self.assertEqual(qname_to_prefixed('', namespaces), '')
        self.assertEqual(qname_to_prefixed(None, namespaces), None)
        self.assertEqual(qname_to_prefixed(0, namespaces), 0)

        self.assertEqual(qname_to_prefixed(XSI_TYPE, {}), XSI_TYPE)
        self.assertEqual(qname_to_prefixed(None, {}), None)
        self.assertEqual(qname_to_prefixed('', {}), '')

        self.assertEqual(qname_to_prefixed('type', {'': XSI_NAMESPACE}), 'type')
        self.assertEqual(qname_to_prefixed('type', {'ns': ''}), 'ns:type')
        self.assertEqual(qname_to_prefixed('type', {'': ''}), 'type')


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
