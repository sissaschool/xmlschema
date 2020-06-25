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

from xmlschema.testing import print_test_header
from xmlschema.qnames import get_namespace, get_qname, local_name, \
    get_prefixed_qname, get_extended_qname, XSD_SCHEMA, XSD_ELEMENT, \
    XSI_TYPE
from xmlschema.namespaces import XSD_NAMESPACE, XSI_NAMESPACE


class TestQNameHelpers(unittest.TestCase):

    def test_get_namespace(self):
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace('local'), '')
        self.assertEqual(get_namespace(XSD_ELEMENT), XSD_NAMESPACE)
        self.assertEqual(get_namespace('{wrong'), '')
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace(None), '')
        self.assertEqual(get_namespace('{}name'), '')
        self.assertEqual(get_namespace('{  }name'), '  ')
        self.assertEqual(get_namespace('{ ns }name'), ' ns ')

    def test_get_qname(self):
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT)
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT)
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

    def test_local_name(self):
        self.assertEqual(local_name('element'), 'element')
        self.assertEqual(local_name(XSD_ELEMENT), 'element')
        self.assertEqual(local_name('xs:element'), 'element')

        self.assertEqual(local_name(XSD_SCHEMA), 'schema')
        self.assertEqual(local_name('schema'), 'schema')
        self.assertEqual(local_name(''), '')
        self.assertEqual(local_name(None), None)

        self.assertRaises(ValueError, local_name, '{ns name')
        self.assertRaises(TypeError, local_name, 1.0)
        self.assertRaises(TypeError, local_name, 0)

    def test_get_prefixed_qname(self):
        namespaces = {'xsd': XSD_NAMESPACE}
        self.assertEqual(get_prefixed_qname(XSD_ELEMENT, namespaces), 'xsd:element')

        namespaces = {'xs': XSD_NAMESPACE, 'xsi': XSI_NAMESPACE}
        self.assertEqual(get_prefixed_qname(XSD_ELEMENT, namespaces), 'xs:element')
        self.assertEqual(get_prefixed_qname('xs:element', namespaces), 'xs:element')
        self.assertEqual(get_prefixed_qname('element', namespaces), 'element')

        self.assertEqual(get_prefixed_qname('', namespaces), '')
        self.assertEqual(get_prefixed_qname(None, namespaces), None)
        self.assertEqual(get_prefixed_qname(0, namespaces), 0)

        self.assertEqual(get_prefixed_qname(XSI_TYPE, {}), XSI_TYPE)
        self.assertEqual(get_prefixed_qname(None, {}), None)
        self.assertEqual(get_prefixed_qname('', {}), '')

        self.assertEqual(get_prefixed_qname('type', {'': XSI_NAMESPACE}), 'type')
        self.assertEqual(get_prefixed_qname('type', {'': ''}), 'type')
        self.assertEqual(get_prefixed_qname('{}type', {'': ''}), 'type')
        self.assertEqual(get_prefixed_qname('{}type', {'': ''}, use_empty=False), '{}type')

        # Attention! in XML the empty namespace (that means no namespace) can be
        # associated only with empty prefix, so these cases should never happen.
        self.assertEqual(get_prefixed_qname('{}type', {'p': ''}), 'p:type')
        self.assertEqual(get_prefixed_qname('type', {'p': ''}), 'type')

        self.assertEqual(get_prefixed_qname('{ns}type', {'': 'ns'}, use_empty=True), 'type')
        self.assertEqual(get_prefixed_qname('{ns}type', {'': 'ns'}, use_empty=False), '{ns}type')
        self.assertEqual(
            get_prefixed_qname('{ns}type', {'': 'ns', 'p': 'ns'}, use_empty=True), 'p:type')
        self.assertEqual(
            get_prefixed_qname('{ns}type', {'': 'ns', 'p': 'ns'}, use_empty=False), 'p:type')
        self.assertEqual(
            get_prefixed_qname('{ns}type', {'': 'ns', 'p': 'ns0'}, use_empty=True), 'type')
        self.assertEqual(
            get_prefixed_qname('{ns}type', {'': 'ns', 'p': 'ns0'}, use_empty=False), '{ns}type')

    def test_get_extended_qname(self):
        namespaces = {'xsd': XSD_NAMESPACE}
        self.assertEqual(get_extended_qname('xsd:element', namespaces), XSD_ELEMENT)
        self.assertEqual(get_extended_qname(XSD_ELEMENT, namespaces), XSD_ELEMENT)
        self.assertEqual(get_extended_qname('xsd:element', namespaces={}), 'xsd:element')
        self.assertEqual(get_extended_qname('', namespaces), '')

        namespaces = {'xs': XSD_NAMESPACE}
        self.assertEqual(get_extended_qname('xsd:element', namespaces), 'xsd:element')

        namespaces = {'': XSD_NAMESPACE}
        self.assertEqual(get_extended_qname('element', namespaces), XSD_ELEMENT)


if __name__ == '__main__':
    print_test_header()
    unittest.main()
