#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import os

from xmlschema.testing import print_test_header
from xmlschema.namespaces import XSD_NAMESPACE, XSI_NAMESPACE, \
    NamespaceResourcesMap, NamespaceMapper, NamespaceView


CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestNamespaceResourcesMap(unittest.TestCase):

    def test_init(self):
        nsmap = [('tns0', 'schema1.xsd')]
        self.assertEqual(NamespaceResourcesMap(), {})
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd']})
        nsmap.append(('tns0', 'schema2.xsd'))
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd', 'schema2.xsd']})

    def test_repr(self):
        namespaces = NamespaceResourcesMap()
        namespaces['tns0'] = 'schema1.xsd'
        namespaces['tns1'] = 'schema2.xsd'
        self.assertEqual(repr(namespaces), "{'tns0': ['schema1.xsd'], 'tns1': ['schema2.xsd']}")

    def test_dictionary_methods(self):
        namespaces = NamespaceResourcesMap()
        namespaces['tns0'] = 'schema1.xsd'
        namespaces['tns1'] = 'schema2.xsd'
        self.assertEqual(namespaces, {'tns0': ['schema1.xsd'], 'tns1': ['schema2.xsd']})

        self.assertEqual(len(namespaces), 2)
        self.assertEqual(list(x for x in namespaces), ['tns0', 'tns1'])

        del namespaces['tns0']
        self.assertEqual(namespaces, {'tns1': ['schema2.xsd']})
        self.assertEqual(len(namespaces), 1)

        namespaces.clear()
        self.assertEqual(namespaces, {})


class TestNamespaceMapper(unittest.TestCase):

    def test_init(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper, namespaces)

    def test_dictionary_methods(self):
        namespaces = dict(xs=XSD_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        mapper['xsi'] = XSI_NAMESPACE
        self.assertEqual(mapper, dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE))

        del mapper['xs']
        self.assertEqual(len(mapper), 1)
        self.assertEqual(mapper, dict(xsi=XSI_NAMESPACE))

        mapper.clear()
        self.assertEqual(mapper, {})

    def test_strip_namespaces(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces, strip_namespaces=True)

        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'name')
        self.assertEqual(mapper.map_qname('{unknown}name'), 'name')

        mapper.strip_namespaces = False
        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'xs:name')
        self.assertEqual(mapper.map_qname('{unknown}name'), '{unknown}name')

    def test_default_namespace(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        self.assertIsNone(mapper.default_namespace)
        mapper[''] = 'tns0'
        self.assertEqual(mapper.default_namespace, 'tns0')

    def test_insert_item(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        mapper.insert_item('xs', XSD_NAMESPACE)
        self.assertEqual(len(mapper), 2)

        mapper.insert_item('', XSD_NAMESPACE)
        self.assertEqual(len(mapper), 3)
        mapper.insert_item('', XSD_NAMESPACE)
        self.assertEqual(len(mapper), 3)
        mapper.insert_item('', 'tns0')
        self.assertEqual(len(mapper), 4)

        mapper.insert_item('xs', XSD_NAMESPACE)
        self.assertEqual(len(mapper), 4)
        mapper.insert_item('xs', 'tns1')
        self.assertEqual(len(mapper), 5)
        mapper.insert_item('xs', 'tns2')
        self.assertEqual(len(mapper), 6)


if __name__ == '__main__':
    print_test_header()
    unittest.main()
