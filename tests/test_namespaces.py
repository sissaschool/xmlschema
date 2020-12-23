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
import sys

from xmlschema.names import XSD_NAMESPACE, XSI_NAMESPACE
from xmlschema.namespaces import NamespaceResourcesMap, NamespaceMapper, NamespaceView


CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestNamespaceResourcesMap(unittest.TestCase):

    def test_init(self):
        nsmap = [('tns0', 'schema1.xsd')]
        self.assertEqual(NamespaceResourcesMap(), {})
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd']})
        nsmap.append(('tns0', 'schema2.xsd'))
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd', 'schema2.xsd']})

    @unittest.skipIf(sys.version_info[:2] < (3, 6), "Python 3.6+ needed")
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
        self.assertEqual(set(x for x in namespaces), {'tns0', 'tns1'})

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
        self.assertIs(namespaces, mapper.namespaces)

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

    def test_map_qname(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        mapper.insert_item('', XSD_NAMESPACE)
        self.assertEqual(mapper.map_qname(''), '')
        self.assertEqual(mapper.map_qname('{%s}element' % XSD_NAMESPACE), 'xs:element')
        mapper.pop('xs')
        self.assertEqual(mapper.map_qname('{%s}element' % XSD_NAMESPACE), 'element')

        with self.assertRaises(ValueError) as ctx:
            mapper.map_qname('{%selement' % XSD_NAMESPACE)
        self.assertIn("wrong format", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            mapper.map_qname('{%s}element}' % XSD_NAMESPACE)
        self.assertIn("wrong format", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.map_qname(None)
        self.assertIn("must be a string-like object", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.map_qname(99)
        self.assertIn("must be a string-like object", str(ctx.exception))

    def test_unmap_qname(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        self.assertEqual(mapper.unmap_qname(''), '')
        self.assertEqual(mapper.unmap_qname('xs:element'), '{%s}element' % XSD_NAMESPACE)
        self.assertEqual(mapper.unmap_qname('{foo}bar'), '{foo}bar')
        self.assertEqual(mapper.unmap_qname('xsd:element'), 'xsd:element')

        with self.assertRaises(ValueError) as ctx:
            mapper.unmap_qname('xs::element')
        self.assertIn("wrong format", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.unmap_qname(None)
        self.assertIn("must be a string-like object", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.unmap_qname(99)
        self.assertIn("must be a string-like object", str(ctx.exception))

        self.assertEqual(mapper.unmap_qname('element'), 'element')
        mapper[''] = 'foo'
        self.assertEqual(mapper.unmap_qname('element'), '{foo}element')
        self.assertEqual(mapper.unmap_qname('element', name_table=['element']), 'element')

    def test_transfer(self):
        mapper = NamespaceMapper(namespaces={'xs': XSD_NAMESPACE, 'xsi': XSI_NAMESPACE})

        namespaces = {'xs': 'foo'}
        mapper.transfer(namespaces)
        self.assertEqual(len(mapper), 2)
        self.assertEqual(len(namespaces), 1)

        namespaces = {'xs': XSD_NAMESPACE}
        mapper.transfer(namespaces)
        self.assertEqual(len(mapper), 2)
        self.assertEqual(len(namespaces), 0)

        namespaces = {'xs': XSI_NAMESPACE, 'tns0': 'http://xmlschema.test/ns'}
        mapper.transfer(namespaces)
        self.assertEqual(len(mapper), 3)
        self.assertIn('tns0', mapper)
        self.assertEqual(len(namespaces), 1)
        self.assertIn('xs', namespaces)

        mapper = NamespaceMapper()
        namespaces = {'xs': XSD_NAMESPACE}
        mapper.transfer(namespaces)
        self.assertEqual(mapper, {'xs': XSD_NAMESPACE})
        self.assertEqual(namespaces, {})


class TestNamespaceView(unittest.TestCase):

    def test_init(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertEqual(ns_view, {'name1': 1})

    def test_repr(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns0')
        self.assertEqual(repr(ns_view), "NamespaceView({'name0': 0})")

    def test_as_dict(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, '{tns1}name2': 2, 'name3': 3}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertEqual(ns_view.as_dict(), {'name1': 1, 'name2': 2})
        self.assertEqual(ns_view.as_dict(True), {'{tns1}name1': 1, '{tns1}name2': 2})


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema namespaces with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
