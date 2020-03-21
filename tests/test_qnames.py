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
    qname_to_prefixed, qname_to_extended, XSD_ELEMENT
from xmlschema.namespaces import XSD_NAMESPACE


class TestQNameHelpers(unittest.TestCase):

    def test_get_namespace(self):
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace('local'), '')
        self.assertEqual(get_namespace(XSD_ELEMENT), XSD_NAMESPACE)
        self.assertEqual(get_namespace('{wrong'), '')

    def test_get_qname(self):
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT)

    def test_local_name(self):
        self.assertEqual(local_name('element'), 'element')
        self.assertEqual(local_name(XSD_ELEMENT), 'element')
        self.assertEqual(local_name('xs:element'), 'element')

    def test_qname_to_prefixed(self):
        namespaces = {'xsd': XSD_NAMESPACE}
        self.assertEqual(qname_to_prefixed(XSD_ELEMENT, namespaces), 'xsd:element')

    def test_qname_to_extended(self):
        namespaces = {'xsd': XSD_NAMESPACE}
        self.assertEqual(qname_to_extended('xsd:element', namespaces), XSD_ELEMENT)
        self.assertEqual(qname_to_extended(XSD_ELEMENT, namespaces), XSD_ELEMENT)
        self.assertEqual(qname_to_extended('xsd:element', namespaces={}), 'xsd:element')
        self.assertEqual(qname_to_extended('', namespaces), '')

        namespaces = {'xs': XSD_NAMESPACE}
        self.assertEqual(qname_to_extended('xsd:element', namespaces), 'xsd:element')

        namespaces = {'': XSD_NAMESPACE}
        self.assertEqual(qname_to_extended('element', namespaces), XSD_ELEMENT)


if __name__ == '__main__':
    print_test_header()
    unittest.main()
