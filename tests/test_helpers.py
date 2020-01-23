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
"""Tests on internal helper functions"""
import unittest
import sys
import decimal
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict

from xmlschema import XMLSchema, XMLSchemaParseError
from xmlschema.etree import etree_element, prune_etree
from xmlschema.qnames import XSI_TYPE, XSD_SCHEMA, XSD_ELEMENT, XSD_SIMPLE_TYPE, \
    XSD_ANNOTATION, get_namespace, get_qname, local_name, qname_to_prefixed
from xmlschema.namespaces import XSD_NAMESPACE, XSI_NAMESPACE
from xmlschema.helpers import get_xsd_annotation, get_xsd_derivation_attribute, \
    get_xsd_form_attribute, raw_xml_encode, count_digits, strictly_equal, \
    iter_nested_items, ParticleCounter


class TestHelpers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema.meta_schema.build()

    @classmethod
    def tearDownClass(cls):
        XMLSchema.meta_schema.clear()

    def test_get_namespace_function(self):
        self.assertEqual(get_namespace(XSD_SIMPLE_TYPE), XSD_NAMESPACE)
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace(None), '')
        self.assertEqual(get_namespace('{}name'), '')
        self.assertEqual(get_namespace('{  }name'), '  ')
        self.assertEqual(get_namespace('{ ns }name'), ' ns ')

    def test_get_qname_functions(self):
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

    def test_local_name_functions(self):
        self.assertEqual(local_name(XSD_SCHEMA), 'schema')
        self.assertEqual(local_name('schema'), 'schema')
        self.assertEqual(local_name(''), '')
        self.assertEqual(local_name(None), None)

        self.assertRaises(ValueError, local_name, '{ns name')
        self.assertRaises(TypeError, local_name, 1.0)
        self.assertRaises(TypeError, local_name, 0)

    def test_qname_to_prefixed_functions(self):
        namespaces = {'xs': XSD_NAMESPACE, 'xsi': XSI_NAMESPACE}
        self.assertEqual(qname_to_prefixed(XSD_ELEMENT, namespaces), 'xs:element')
        self.assertEqual(qname_to_prefixed('xs:element', namespaces), 'xs:element')
        self.assertEqual(qname_to_prefixed('element', namespaces), 'element')

        self.assertEqual(qname_to_prefixed('', namespaces), '')
        self.assertEqual(qname_to_prefixed(None, namespaces), None)
        self.assertEqual(qname_to_prefixed(0, namespaces), 0)

        self.assertEqual(qname_to_prefixed(XSI_TYPE, {}), XSI_TYPE)
        self.assertEqual(qname_to_prefixed(None, {}), None)
        self.assertEqual(qname_to_prefixed('', {}), '')

        self.assertEqual(qname_to_prefixed('type', {'': XSI_NAMESPACE}), 'type')
        self.assertEqual(qname_to_prefixed('type', {'': ''}), 'type')
        self.assertEqual(qname_to_prefixed('{}type', {'': ''}), 'type')
        self.assertEqual(qname_to_prefixed('{}type', {'': ''}, use_empty=False), '{}type')

        # Attention! in XML the empty namespace (that means no namespace) can be
        # associated only with empty prefix, so these cases should never happen.
        self.assertEqual(qname_to_prefixed('{}type', {'p': ''}), 'p:type')
        self.assertEqual(qname_to_prefixed('type', {'p': ''}), 'type')

        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns'}, use_empty=True), 'type')
        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns'}, use_empty=False), '{ns}type')
        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns', 'p': 'ns'}, use_empty=True), 'p:type')
        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns', 'p': 'ns'}, use_empty=False), 'p:type')
        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns', 'p': 'ns0'}, use_empty=True), 'type')
        self.assertEqual(qname_to_prefixed('{ns}type', {'': 'ns', 'p': 'ns0'}, use_empty=False), '{ns}type')

    def test_get_xsd_annotation(self):
        elem = etree_element(XSD_SCHEMA)

        self.assertIsNone(get_xsd_annotation(elem))
        elem.append(etree_element(XSD_ANNOTATION))
        self.assertEqual(get_xsd_annotation(elem), elem[0])
        elem.append(etree_element(XSD_ELEMENT))
        self.assertEqual(get_xsd_annotation(elem), elem[0])

        elem.clear()
        elem.append(etree_element(XSD_ELEMENT))
        self.assertIsNone(get_xsd_annotation(elem))
        elem.append(etree_element(XSD_ANNOTATION))
        self.assertIsNone(get_xsd_annotation(elem))

    def test_get_xsd_derivation_attribute(self):
        elem = etree_element(XSD_ELEMENT, attrib={
            'a1': 'extension', 'a2': ' restriction', 'a3': '#all', 'a4': 'other',
            'a5': 'restriction extension restriction ', 'a6': 'other restriction'
        })
        values = ('extension', 'restriction')
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a1', values), 'extension')
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a2', values), ' restriction')
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a3', values), 'extension restriction')
        self.assertRaises(ValueError, get_xsd_derivation_attribute, elem, 'a4', values)
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a5', values), 'restriction extension restriction ')
        self.assertRaises(ValueError, get_xsd_derivation_attribute, elem, 'a6', values)
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a7', values), '')

    def test_get_xsd_form_attribute(self):
        elem = etree_element(XSD_ELEMENT, attrib={
            'a1': 'qualified', 'a2': ' qualified', 'a3': 'unqualified', 'a4': ''
        })
        self.assertEqual(get_xsd_form_attribute(elem, 'a1'), 'qualified')
        self.assertRaises(ValueError, get_xsd_form_attribute, elem, 'a2')
        self.assertEqual(get_xsd_form_attribute(elem, 'a3'), 'unqualified')
        self.assertRaises(ValueError, get_xsd_form_attribute, elem, 'a4')
        self.assertIsNone(get_xsd_form_attribute(elem, 'a5'))

    def test_parse_component(self):
        component = XMLSchema.meta_schema.types['anyType']

        elem = etree_element(XSD_SCHEMA)
        self.assertIsNone(component._parse_child_component(elem))
        elem.append(etree_element(XSD_ELEMENT))
        self.assertEqual(component._parse_child_component(elem), elem[0])
        elem.append(etree_element(XSD_SIMPLE_TYPE))
        self.assertRaises(XMLSchemaParseError, component._parse_child_component, elem)
        self.assertEqual(component._parse_child_component(elem, strict=False), elem[0])

        elem.clear()
        elem.append(etree_element(XSD_ANNOTATION))
        self.assertIsNone(component._parse_child_component(elem))
        elem.append(etree_element(XSD_SIMPLE_TYPE))
        self.assertEqual(component._parse_child_component(elem), elem[1])
        elem.append(etree_element(XSD_ELEMENT))
        self.assertRaises(XMLSchemaParseError, component._parse_child_component, elem)
        self.assertEqual(component._parse_child_component(elem, strict=False), elem[1])

        elem.clear()
        elem.append(etree_element(XSD_ANNOTATION))
        elem.append(etree_element(XSD_ANNOTATION))
        self.assertIsNone(component._parse_child_component(elem, strict=False))
        elem.append(etree_element(XSD_SIMPLE_TYPE))
        self.assertEqual(component._parse_child_component(elem), elem[2])

    def test_raw_xml_encode_function(self):
        self.assertEqual(raw_xml_encode(True), 'true')
        self.assertEqual(raw_xml_encode(False), 'false')
        self.assertEqual(raw_xml_encode(10), '10')
        self.assertEqual(raw_xml_encode(0), '0')
        self.assertEqual(raw_xml_encode(1), '1')
        self.assertEqual(raw_xml_encode('alpha'), 'alpha')
        self.assertEqual(raw_xml_encode([10, 20, 30]), '10 20 30')
        self.assertEqual(raw_xml_encode((10, 20, 30)), '10 20 30')

    def test_count_digits_function(self):
        self.assertEqual(count_digits(10), (2, 0))
        self.assertEqual(count_digits(-10), (2, 0))

        self.assertEqual(count_digits(081.2), (2, 1))
        self.assertEqual(count_digits(-081.200), (2, 1))
        self.assertEqual(count_digits(0.51), (0, 2))
        self.assertEqual(count_digits(-0.510), (0, 2))
        self.assertEqual(count_digits(-0.510), (0, 2))

        self.assertEqual(count_digits(decimal.Decimal('100.0')), (3, 0))
        self.assertEqual(count_digits(decimal.Decimal('100.01')), (3, 2))
        self.assertEqual(count_digits('100.01'), (3, 2))
        self.assertEqual(count_digits(1E-11), (0, 11))
        self.assertEqual(count_digits(b'100.0E+4'), (7, 0))

        self.assertEqual(count_digits(decimal.Decimal('100.0E+4')), (7, 0))
        self.assertEqual(count_digits(decimal.Decimal('100.00001E+4')), (7, 1))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E4')), (7, 0))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E12')), (15, 0))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E19')), (22, 0))

        self.assertEqual(count_digits(decimal.Decimal('100.0E-4')), (0, 2))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E-4')), (0, 2))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E-8')), (0, 6))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E-9')), (0, 7))
        self.assertEqual(count_digits(decimal.Decimal('0100.00E-12')), (0, 10))
        self.assertEqual(count_digits(decimal.Decimal('100.10E-4')), (0, 5))
        self.assertEqual(count_digits(decimal.Decimal('0100.10E-12')), (0, 13))

    def test_strictly_equal_function(self):
        self.assertTrue(strictly_equal(10, 10))
        self.assertFalse(strictly_equal(10, 10.0))

    def test_iter_nested_items_function(self):
        if sys.version_info >= (3, 6):
            self.assertListEqual(list(iter_nested_items({'a': 10, 'b': 20})), [10, 20])
            self.assertListEqual(list(iter_nested_items([{'a': 10, 'b': 20}, 30])), [10, 20, 30])

        with self.assertRaises(TypeError):
            list(iter_nested_items({'a': 10, 'b': 20}, dict_class=OrderedDict))

        with self.assertRaises(TypeError):
            list(iter_nested_items([10, 20], list_class=tuple))

    def test_particle_counter_class(self):
        counter = ParticleCounter()
        self.assertEqual(repr(counter), 'ParticleCounter(0, 0)')

        other = ParticleCounter()  # Only for test isolation, usually it's a particle.
        other.min_occurs = 5
        other.max_occurs = 10

        counter += other
        self.assertEqual(repr(counter), 'ParticleCounter(5, 10)')
        counter *= other
        self.assertEqual(repr(counter), 'ParticleCounter(25, 100)')

        counter = ParticleCounter()
        counter.max_occurs = None
        self.assertEqual(repr(counter), 'ParticleCounter(0, None)')
        self.assertEqual(repr(counter * other), 'ParticleCounter(0, None)')
        self.assertEqual(repr(counter + other), 'ParticleCounter(5, None)')
        self.assertEqual(repr(counter * other), 'ParticleCounter(25, None)')

        counter.reset()
        self.assertEqual(repr(counter), 'ParticleCounter(0, 0)')

        counter.max_occurs = None
        other.min_occurs = other.max_occurs = 0
        self.assertEqual(repr(counter * other), 'ParticleCounter(0, 0)')

        counter.reset()
        other.min_occurs = 0
        other.max_occurs = None
        self.assertEqual(repr(counter * other), 'ParticleCounter(0, 0)')
        self.assertEqual(repr(counter + other), 'ParticleCounter(0, None)')
        self.assertEqual(repr(counter + other), 'ParticleCounter(0, None)')

        counter.max_occurs = 1
        self.assertEqual(repr(counter * other), 'ParticleCounter(0, None)')


class TestElementTreeHelpers(unittest.TestCase):

    def test_prune_etree_function(self):
        root = ElementTree.XML('<A id="0"><B/><C/><D/></A>')
        self.assertFalse(prune_etree(root, lambda x: x.tag == 'C'))
        self.assertListEqual([e.tag for e in root.iter()], ['A', 'B', 'D'])
        self.assertEqual(root.attrib, {'id': '0'})

        root = ElementTree.XML('<A id="1"><B/><C/><D/></A>')
        self.assertTrue(prune_etree(root, lambda x: x.tag != 'C'))
        self.assertListEqual([e.tag for e in root.iter()], ['A'])
        self.assertEqual(root.attrib, {'id': '1'})

        class SelectorClass:
            tag = 'C'

            @classmethod
            def class_method(cls, elem):
                return elem.tag == cls.tag

            def method(self, elem):
                return elem.tag != self.tag

        selector = SelectorClass()

        root = ElementTree.XML('<A id="0"><B/><C/><D/></A>')
        self.assertFalse(prune_etree(root, selector.class_method))
        self.assertListEqual([e.tag for e in root.iter()], ['A', 'B', 'D'])
        self.assertEqual(root.attrib, {'id': '0'})

        root = ElementTree.XML('<A id="1"><B/><C/><D/></A>')
        self.assertTrue(prune_etree(root, selector.method))
        self.assertListEqual([e.tag for e in root.iter()], ['A'])
        self.assertEqual(root.attrib, {'id': '1'})


if __name__ == '__main__':
    from xmlschema.testing import print_test_header

    print_test_header()
    unittest.main()
