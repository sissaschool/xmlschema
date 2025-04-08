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
import sys
import unittest
import decimal
import logging
import warnings
from collections import OrderedDict
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import XMLSchema, XMLSchemaParseError
from xmlschema.names import XSD_NAMESPACE, XSI_NAMESPACE, XSD_SCHEMA, \
    XSD_ELEMENT, XSD_SIMPLE_TYPE, XSD_ANNOTATION, XSI_TYPE
from xmlschema.utils.etree import prune_etree, etree_get_ancestors, etree_getpath, \
    etree_iter_location_hints, etree_tostring
from xmlschema.utils.qnames import get_namespace, get_qname, local_name, \
    get_prefixed_qname, get_extended_qname, update_namespaces
from xmlschema.utils.logger import set_logging_level, logged, format_xmlschema_stack, \
    dump_data
from xmlschema.utils.decoding import raw_encode_value, raw_encode_attributes, \
    count_digits, strictly_equal
from xmlschema.utils.misc import deprecated, will_change

from xmlschema.testing import iter_nested_items, etree_elements_assert_equal, \
    run_xmlschema_tests
from xmlschema.validators.exceptions import XMLSchemaValidationError
from xmlschema.validators.helpers import get_xsd_derivation_attribute, \
    decimal_validator, qname_validator, \
    base64_binary_validator, hex_binary_validator, \
    int_validator, long_validator, unsigned_byte_validator, \
    unsigned_short_validator, negative_int_validator, error_type_validator
from xmlschema.validators.particles import OccursCalculator
from xmlschema.resources import XMLResource

XML_WITH_NAMESPACES = '<pfa:root xmlns:pfa="http://xpath.test/nsa">\n' \
                      '  <pfb:elem xmlns:pfb="http://xpath.test/nsb"/>\n' \
                      '</pfa:root>'


class TestUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema.meta_schema.build()

    @classmethod
    def tearDownClass(cls):
        XMLSchema.meta_schema.clear()

    def test_get_xsd_derivation_attribute(self):
        elem = ElementTree.Element(XSD_ELEMENT, attrib={
            'a1': 'extension', 'a2': ' restriction', 'a3': '#all', 'a4': 'other',
            'a5': 'restriction extension restriction ', 'a6': 'other restriction'
        })
        values = {'extension', 'restriction'}
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a1', values), 'extension')
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a2', values), ' restriction')

        result = get_xsd_derivation_attribute(elem, 'a3', values)
        self.assertSetEqual(set(result.strip().split()),
                            set('extension restriction'.split()))

        self.assertRaises(ValueError, get_xsd_derivation_attribute, elem, 'a4', values)

        result = get_xsd_derivation_attribute(elem, 'a5', values)
        self.assertEqual(set(result.strip().split()),
                         set('restriction extension restriction'.split()))

        self.assertRaises(ValueError, get_xsd_derivation_attribute, elem, 'a6', values)
        self.assertEqual(get_xsd_derivation_attribute(elem, 'a7', values), '')

    def test_parse_component(self):
        component = XMLSchema.meta_schema.types['anyType']

        elem = ElementTree.Element(XSD_SCHEMA)
        self.assertIsNone(component._parse_child_component(elem))
        elem.append(ElementTree.Element(XSD_ELEMENT))
        self.assertEqual(component._parse_child_component(elem), elem[0])
        elem.append(ElementTree.Element(XSD_SIMPLE_TYPE))
        self.assertRaises(XMLSchemaParseError, component._parse_child_component, elem)
        self.assertEqual(component._parse_child_component(elem, strict=False), elem[0])

        elem.clear()
        elem.append(ElementTree.Element(XSD_ANNOTATION))
        self.assertIsNone(component._parse_child_component(elem))
        elem.append(ElementTree.Element(XSD_SIMPLE_TYPE))
        self.assertEqual(component._parse_child_component(elem), elem[1])
        elem.append(ElementTree.Element(XSD_ELEMENT))
        self.assertRaises(XMLSchemaParseError, component._parse_child_component, elem)
        self.assertEqual(component._parse_child_component(elem, strict=False), elem[1])

        elem.clear()
        elem.append(ElementTree.Element(XSD_ANNOTATION))
        elem.append(ElementTree.Element(XSD_ANNOTATION))
        self.assertIsNone(component._parse_child_component(elem, strict=False))
        elem.append(ElementTree.Element(XSD_SIMPLE_TYPE))
        self.assertEqual(component._parse_child_component(elem), elem[2])

    def test_raw_encode_value_function(self):
        self.assertIsNone(raw_encode_value(None))
        self.assertEqual(raw_encode_value(True), 'true')
        self.assertEqual(raw_encode_value(False), 'false')
        self.assertEqual(raw_encode_value(10), '10')
        self.assertEqual(raw_encode_value(0), '0')
        self.assertEqual(raw_encode_value(1), '1')
        self.assertEqual(raw_encode_value('alpha'), 'alpha')
        self.assertEqual(raw_encode_value([10, 20, 30]), '10 20 30')
        self.assertEqual(raw_encode_value((10, 20, 30)), '10 20 30')

    def test_raw_encode_attributes_function(self):
        self.assertEqual(raw_encode_attributes(None), {})
        self.assertEqual(raw_encode_attributes({}), {})
        self.assertEqual(raw_encode_attributes({'a': 89, 'b': None}), {'a': '89'})

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
        self.assertListEqual(list(iter_nested_items({'a': 10, 'b': 20})), [10, 20])
        self.assertListEqual(list(iter_nested_items([{'a': 10, 'b': 20}, 30])), [10, 20, 30])

        with self.assertRaises(TypeError):
            list(iter_nested_items({'a': 10, 'b': 20}, dict_class=OrderedDict))

        with self.assertRaises(TypeError):
            list(iter_nested_items([10, 20], list_class=tuple))

    def test_occurs_calculator_class(self):
        counter = OccursCalculator()
        self.assertEqual(repr(counter), 'OccursCalculator(0, 0)')

        other = OccursCalculator()  # Only for test isolation, usually it's a particle.
        other.min_occurs = 5
        other.max_occurs = 10

        counter += other
        self.assertEqual(repr(counter), 'OccursCalculator(5, 10)')
        counter *= other
        self.assertEqual(repr(counter), 'OccursCalculator(25, 100)')

        counter = OccursCalculator()
        counter.max_occurs = None
        self.assertEqual(repr(counter), 'OccursCalculator(0, None)')
        self.assertEqual(repr(counter * other), 'OccursCalculator(0, None)')
        self.assertEqual(repr(counter + other), 'OccursCalculator(5, None)')
        self.assertEqual(repr(counter * other), 'OccursCalculator(25, None)')

        counter.reset()
        self.assertEqual(repr(counter), 'OccursCalculator(0, 0)')

        counter.max_occurs = None
        other.min_occurs = other.max_occurs = 0
        self.assertEqual(repr(counter * other), 'OccursCalculator(0, 0)')

        counter.reset()
        other.min_occurs = 0
        other.max_occurs = None
        self.assertEqual(repr(counter * other), 'OccursCalculator(0, 0)')
        self.assertEqual(repr(counter + other), 'OccursCalculator(0, None)')
        self.assertEqual(repr(counter + other), 'OccursCalculator(0, None)')

        counter.max_occurs = 1
        self.assertEqual(repr(counter * other), 'OccursCalculator(0, None)')

    def test_get_namespace(self):
        self.assertEqual(get_namespace(''), '')
        self.assertEqual(get_namespace('local'), '')
        self.assertEqual(get_namespace(XSD_ELEMENT), XSD_NAMESPACE)
        self.assertEqual(get_namespace('{wrong'), '')
        self.assertEqual(get_namespace(''), '')
        self.assertRaises(TypeError, get_namespace, None)
        self.assertEqual(get_namespace('{}name'), '')
        self.assertEqual(get_namespace('{  }name'), '  ')
        self.assertEqual(get_namespace('{ ns }name'), ' ns ')

    def test_get_qname(self):
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT)
        self.assertEqual(get_qname(XSD_NAMESPACE, 'element'), XSD_ELEMENT)
        self.assertEqual(get_qname(XSI_NAMESPACE, 'type'), XSI_TYPE)

        self.assertEqual(get_qname(XSI_NAMESPACE, ''), '')
        self.assertRaises(TypeError, get_qname, XSI_NAMESPACE, None)
        self.assertRaises(TypeError, get_qname, XSI_NAMESPACE, 0)
        self.assertRaises(TypeError, get_qname, XSI_NAMESPACE, False)
        self.assertRaises(TypeError, get_qname, XSI_NAMESPACE, True)
        self.assertRaises(TypeError, get_qname, None, True)

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

        self.assertRaises(TypeError, local_name, None)
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
        self.assertEqual(get_prefixed_qname('{uri}element', namespaces), '{uri}element')

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

    def test_update_namespaces(self):
        nsmap = {}
        update_namespaces(nsmap, [('xs', XSD_NAMESPACE)])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE})
        update_namespaces(nsmap, [('xs', XSD_NAMESPACE)])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE})
        update_namespaces(nsmap, [('tns0', 'http://example.com/ns')])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE, 'tns0': 'http://example.com/ns'})
        update_namespaces(nsmap, [('xs', 'http://example.com/ns')])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'tns0': 'http://example.com/ns'})
        update_namespaces(nsmap, [('xs', 'http://example.com/ns')])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'tns0': 'http://example.com/ns'})

        update_namespaces(nsmap, [('xs', 'http://example.com/ns2')])
        self.assertEqual(nsmap, {'xs': XSD_NAMESPACE,
                                 'xs0': 'http://example.com/ns',
                                 'xs1': 'http://example.com/ns2',
                                 'tns0': 'http://example.com/ns'})

        nsmap = {}
        update_namespaces(nsmap, [('', XSD_NAMESPACE)])
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema'})
        update_namespaces(nsmap, [('', XSD_NAMESPACE)])
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema'})
        update_namespaces(nsmap, [('', 'http://example.com/ns')])
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema',
                                 'default0': 'http://example.com/ns'})
        update_namespaces(nsmap, [('', 'http://example.com/ns2')], root_declarations=True)
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema',
                                 'default0': 'http://example.com/ns',
                                 '': 'http://example.com/ns2'})
        update_namespaces(nsmap, [('', 'http://example.com/ns2')])
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema',
                                 'default0': 'http://example.com/ns',
                                 '': 'http://example.com/ns2'})
        update_namespaces(nsmap, [('', 'http://example.com/ns3')])
        self.assertEqual(nsmap, {'default': 'http://www.w3.org/2001/XMLSchema',
                                 'default0': 'http://example.com/ns',
                                 '': 'http://example.com/ns2',
                                 'default1': 'http://example.com/ns3'})

    def test_etree_get_ancestors(self):
        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/><b3><c3/></b3></a>')
        elem = ElementTree.XML('<a/>')

        self.assertIsNone(etree_get_ancestors(elem, root))
        self.assertListEqual(etree_get_ancestors(root, root), [])
        self.assertListEqual(etree_get_ancestors(root[0], root), [root])
        self.assertListEqual(etree_get_ancestors(root[0][0], root), [root, root[0]])
        self.assertListEqual(etree_get_ancestors(root[2][0], root), [root, root[2]])

    def test_etree_getpath(self):
        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/><b3><c3/></b3></a>')

        self.assertEqual(etree_getpath(root, root), '.')
        self.assertEqual(etree_getpath(root[0], root), './b1')
        self.assertEqual(etree_getpath(root[2][0], root), './b3/c3')
        self.assertEqual(etree_getpath(root[0], root, parent_path=True), '.')
        self.assertEqual(etree_getpath(root[2][0], root, parent_path=True), './b3')

        self.assertEqual(etree_getpath(root, root, relative=False), '/a')
        self.assertEqual(etree_getpath(root[0], root, relative=False), '/a/b1')
        self.assertEqual(etree_getpath(root[2][0], root, relative=False), '/a/b3/c3')
        self.assertEqual(
            etree_getpath(root[0], root, relative=False, parent_path=True), '/a'
        )
        self.assertEqual(
            etree_getpath(root[2][0], root, relative=False, parent_path=True), '/a/b3'
        )

        self.assertIsNone(etree_getpath(root, root[0]))
        self.assertIsNone(etree_getpath(root[0], root[1]))
        self.assertIsNone(etree_getpath(root, root, parent_path=True))

        self.assertIsNone(etree_getpath(root, root[0], relative=False))
        self.assertIsNone(etree_getpath(root[0], root[1], relative=False))
        self.assertIsNone(etree_getpath(root, root, relative=False, parent_path=True))

    def test_etree_elements_assert_equal(self):
        e1 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')
        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')

        self.assertIsNone(etree_elements_assert_equal(e1, e1))
        self.assertIsNone(etree_elements_assert_equal(e1, e2))

        if lxml_etree is not None:
            e2 = lxml_etree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')
            self.assertIsNone(etree_elements_assert_equal(e1, e2))

        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/><b4/></a>\n')
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2)
        self.assertIn("has lesser children than <Element 'a'", str(ctx.exception))

        e2 = ElementTree.XML('<a><b1>text  <c1 a="1"/></b1>\n<b2/><b3/></a>\n')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2)
        self.assertIn("texts differ: 'text' != 'text  '", str(ctx.exception))

        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2>text</b2><b3/></a>\n')
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("texts differ: None != 'text'", str(ctx.exception))

        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>')
        self.assertIsNone(etree_elements_assert_equal(e1, e2))

        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1><b2/><b3/></a>\n')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2)
        self.assertIn(r"tails differ: '\n' != None", str(ctx.exception))

        e2 = ElementTree.XML('<a><b1>text<c1 a="1 "/></b1>\n<b2/><b3/></a>\n')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2)
        self.assertIn("attributes differ: {'a': '1'} != {'a': '1 '}", str(ctx.exception))

        e2 = ElementTree.XML('<a><b1>text<c1 a="2 "/></b1>\n<b2/><b3/></a>\n')
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("attribute 'a' values differ: '1' != '2'", str(ctx.exception))

        e2 = ElementTree.XML('<a><!--comment--><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')
        self.assertIsNone(etree_elements_assert_equal(e1, e2))
        self.assertIsNone(etree_elements_assert_equal(e1, e2, skip_comments=False))

        if lxml_etree is not None:
            e2 = lxml_etree.XML('<a><!--comment--><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')
            self.assertIsNone(etree_elements_assert_equal(e1, e2))

        e1 = ElementTree.XML('<a><b1>+1</b1></a>')
        e2 = ElementTree.XML('<a><b1>+ 1 </b1></a>')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))

        e1 = ElementTree.XML('<a><b1>+1</b1></a>')
        e2 = ElementTree.XML('<a><b1>+1.1 </b1></a>')

        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("texts differ: '+1' != '+1.1 '", str(ctx.exception))

        e1 = ElementTree.XML('<a><b1>1</b1></a>')
        e2 = ElementTree.XML('<a><b1>true </b1></a>')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))
        self.assertIsNone(etree_elements_assert_equal(e2, e1, strict=False))

        e2 = ElementTree.XML('<a><b1>false </b1></a>')
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("texts differ: '1' != 'false '", str(ctx.exception))

        e1 = ElementTree.XML('<a><b1> 0</b1></a>')
        self.assertIsNone(etree_elements_assert_equal(e1, e2, strict=False))
        self.assertIsNone(etree_elements_assert_equal(e2, e1, strict=False))

        e2 = ElementTree.XML('<a><b1>true </b1></a>')
        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("texts differ: ' 0' != 'true '", str(ctx.exception))

        e1 = ElementTree.XML('<a><b1>text<c1 a="1"/></b1>\n<b2/><b3/></a>\n')
        e2 = ElementTree.XML('<a><b1>text<c1 a="1"/>tail</b1>\n<b2/><b3/></a>\n')

        with self.assertRaises(AssertionError) as ctx:
            etree_elements_assert_equal(e1, e2, strict=False)
        self.assertIn("tails differ: None != 'tail'", str(ctx.exception))

    def test_iter_location_hints(self):
        elem = ElementTree.XML(
            """<root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="http://example.com/xmlschema/ns-A import-case4a.xsd"/>"""
        )
        self.assertListEqual(
            list(etree_iter_location_hints(elem)),
            [('http://example.com/xmlschema/ns-A', 'import-case4a.xsd')]
        )
        elem = ElementTree.XML(
            """<foo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:noNamespaceSchemaLocation="schema.xsd"/>"""
        )
        self.assertListEqual(
            list(etree_iter_location_hints(elem)), [('', 'schema.xsd')]
        )

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

        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/><b3><c3/></b3></a>')
        prune_etree(root, selector=lambda x: x.tag == 'b1')
        self.assertListEqual([e.tag for e in root.iter()], ['a', 'b2', 'b3', 'c3'])

        root = ElementTree.XML('<a><b1><c1/><c2/></b1><b2/><b3><c3/></b3></a>')
        prune_etree(root, selector=lambda x: x.tag.startswith('c'))
        self.assertListEqual([e.tag for e in root.iter()], ['a', 'b1', 'b2', 'b3'])

    def test_etree_tostring(self):
        self.assertRaises(TypeError, etree_tostring, '<element/>')

        elem = ElementTree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element />')
        self.assertEqual(etree_tostring(elem, xml_declaration=True), '<element />')

        self.assertEqual(etree_tostring(elem, encoding='us-ascii'), b'<element />')
        self.assertEqual(etree_tostring(elem, encoding='us-ascii', indent='    '),
                         b'    <element />')
        self.assertEqual(etree_tostring(elem, encoding='us-ascii', xml_declaration=True),
                         b'<?xml version="1.0" encoding="us-ascii"?>\n<element />')

        elem.text = '\t'
        self.assertEqual(etree_tostring(elem), '<element>    </element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=2), '<element>  </element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=0), '<element></element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=None), '<element>\t</element>')

        elem.text = '\n\n'
        self.assertEqual(etree_tostring(elem), '<element>\n\n</element>')
        self.assertEqual(etree_tostring(elem, indent='  '), '  <element>\n\n  </element>')

        elem.text = '\nfoo\n'
        self.assertEqual(etree_tostring(elem), '<element>\nfoo\n</element>')
        self.assertEqual(etree_tostring(elem, indent=' '), ' <element>\n foo\n </element>')

        elem.text = None

        self.assertEqual(etree_tostring(elem, encoding='ascii'),
                         b"<?xml version='1.0' encoding='ascii'?>\n<element />")
        self.assertEqual(etree_tostring(elem, encoding='ascii', xml_declaration=False),
                         b'<element />')
        self.assertEqual(etree_tostring(elem, encoding='utf-8'), b'<element />')
        self.assertEqual(etree_tostring(elem, encoding='utf-8', xml_declaration=True),
                         b'<?xml version="1.0" encoding="utf-8"?>\n<element />')

        self.assertEqual(etree_tostring(elem, encoding='iso-8859-1'),
                         b"<?xml version='1.0' encoding='iso-8859-1'?>\n<element />")
        self.assertEqual(etree_tostring(elem, encoding='iso-8859-1', xml_declaration=False),
                         b"<element />")

        self.assertEqual(etree_tostring(elem, method='html'), '<element></element>')
        self.assertEqual(etree_tostring(elem, method='text'), '')

        root = ElementTree.XML('<root>\n'
                               '  text1\n'
                               '  <elem>text2</elem>\n'
                               '</root>')
        self.assertEqual(etree_tostring(root, method='text'), '\n  text1\n  text2')
        self.assertEqual(etree_tostring(root, max_lines=1), '<root>\n  ...\n  ...\n</root>')

        root = ElementTree.XML(XML_WITH_NAMESPACES)
        result = etree_tostring(root)
        self.assertNotEqual(result, XML_WITH_NAMESPACES)
        self.assertNotIn('pxa', result)
        self.assertNotIn('pxa', result)
        self.assertRegex(result, r'xmlns:ns\d="http://xpath.test/nsa')
        self.assertRegex(result, r'xmlns:ns\d="http://xpath.test/nsb')

        namespaces = {
            'pxa': "http://xpath.test/nsa",
            'pxb': "http://xpath.test/nsb"
        }
        expected = '<pxa:root xmlns:pxa="http://xpath.test/nsa" ' \
                   'xmlns:pxb="http://xpath.test/nsb">\n' \
                   '  <pxb:elem />\n' \
                   '</pxa:root>'
        self.assertEqual(etree_tostring(root, namespaces), expected)

        namespaces = {
            '': "http://xpath.test/nsa",
            'pxa': "http://xpath.test/nsa",
            'pxb': "http://xpath.test/nsb"
        }
        self.assertEqual(etree_tostring(root, namespaces), expected)

        namespaces = {
            '': "http://xpath.test/nsa",
            'pxb': "http://xpath.test/nsb"
        }
        expected = '<root xmlns="http://xpath.test/nsa" ' \
                   'xmlns:pxb="http://xpath.test/nsb">\n' \
                   '  <pxb:elem />\n' \
                   '</root>'
        self.assertEqual(etree_tostring(root, namespaces), expected)

    @unittest.skipIf(lxml_etree is None, 'lxml is not installed ...')
    def test_etree_tostring_with_lxml_element(self):
        elem = lxml_etree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element/>')
        self.assertEqual(etree_tostring(elem, xml_declaration=True), '<element/>')

        self.assertEqual(etree_tostring(elem, encoding='us-ascii'), b'<element/>')
        self.assertEqual(etree_tostring(elem, encoding='us-ascii', indent='    '),
                         b'    <element/>')

        elem.text = '\t'
        self.assertEqual(etree_tostring(elem), '<element>    </element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=2), '<element>  </element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=0), '<element></element>')
        self.assertEqual(etree_tostring(elem, spaces_for_tab=None), '<element>\t</element>')
        elem.text = None

        self.assertEqual(etree_tostring(elem, encoding='us-ascii'), b'<element/>')
        self.assertEqual(etree_tostring(elem, encoding='us-ascii', xml_declaration=True),
                         b'<?xml version="1.0" encoding="us-ascii"?>\n<element/>')

        self.assertEqual(etree_tostring(elem, encoding='ascii'), b'<element/>')
        self.assertEqual(etree_tostring(elem, encoding='ascii', xml_declaration=True),
                         b'<?xml version="1.0" encoding="ascii"?>\n<element/>')

        self.assertEqual(etree_tostring(elem, encoding='utf-8'), b'<element/>')
        self.assertEqual(etree_tostring(elem, encoding='utf-8', xml_declaration=True),
                         b'<?xml version="1.0" encoding="utf-8"?>\n<element/>')

        self.assertEqual(etree_tostring(elem, encoding='iso-8859-1'),
                         b"<?xml version='1.0' encoding='iso-8859-1'?>\n<element/>")
        self.assertEqual(etree_tostring(elem, encoding='iso-8859-1', xml_declaration=False),
                         b"<element/>")

        self.assertEqual(etree_tostring(elem, method='html'), '<element></element>')
        self.assertEqual(etree_tostring(elem, method='text'), '')

        root = lxml_etree.XML('<root>\n'
                              '  text1\n'
                              '  <elem>text2</elem>\n'
                              '</root>')
        self.assertEqual(etree_tostring(root, method='text'), '\n  text1\n  text2')

        root = lxml_etree.XML(XML_WITH_NAMESPACES)
        self.assertEqual(etree_tostring(root), XML_WITH_NAMESPACES)

        namespaces = {
            'tns0': "http://xpath.test/nsa",
            'tns1': "http://xpath.test/nsb"
        }
        self.assertEqual(etree_tostring(root, namespaces), XML_WITH_NAMESPACES)

        for prefix, uri in namespaces.items():
            lxml_etree.register_namespace(prefix, uri)
        self.assertEqual(etree_tostring(root), XML_WITH_NAMESPACES)

    def test_decimal_validator(self):
        self.assertIsNone(decimal_validator(10))
        self.assertIsNone(decimal_validator(10.1))
        self.assertIsNone(decimal_validator(10E9))
        self.assertIsNone(decimal_validator('34.21'))

        with self.assertRaises(XMLSchemaValidationError):
            decimal_validator(float('inf'))
        with self.assertRaises(XMLSchemaValidationError):
            decimal_validator(float('nan'))
        with self.assertRaises(XMLSchemaValidationError):
            decimal_validator('NaN')
        with self.assertRaises(XMLSchemaValidationError):
            decimal_validator('10E9')
        with self.assertRaises(XMLSchemaValidationError):
            decimal_validator('ten')

    def test_qname_validator(self):
        self.assertIsNone(qname_validator("foo"))
        self.assertIsNone(qname_validator("bar:foo"))

        with self.assertRaises(XMLSchemaValidationError):
            qname_validator("foo:bar:foo")
        with self.assertRaises(XMLSchemaValidationError):
            qname_validator("foo: bar")
        with self.assertRaises(XMLSchemaValidationError):
            qname_validator(" foo:bar")  # strip already done by white-space facet

    def test_hex_binary_validator(self):
        self.assertIsNone(hex_binary_validator("aff1c9"))
        self.assertIsNone(hex_binary_validator("2aF3Bc"))
        self.assertIsNone(hex_binary_validator(""))

        with self.assertRaises(XMLSchemaValidationError):
            hex_binary_validator("aff1c")
        with self.assertRaises(XMLSchemaValidationError):
            hex_binary_validator("aF3Bc")
        with self.assertRaises(XMLSchemaValidationError):
            hex_binary_validator("xaF3Bc")

    def test_base64_binary_validator(self):
        self.assertIsNone(base64_binary_validator("YWVpb3U="))
        self.assertIsNone(base64_binary_validator("YWVpb 3U="))
        self.assertIsNone(base64_binary_validator(''))

        with self.assertRaises(XMLSchemaValidationError):
            base64_binary_validator("YWVpb3U==")

    def test_int_validator(self):
        self.assertIsNone(int_validator(2 ** 31 - 1))
        self.assertIsNone(int_validator(-2 ** 31))

        with self.assertRaises(XMLSchemaValidationError):
            int_validator(2 ** 31)

    def test_long_validator(self):
        self.assertIsNone(long_validator(2 ** 63 - 1))
        self.assertIsNone(long_validator(-2 ** 63))

        with self.assertRaises(XMLSchemaValidationError):
            long_validator(2 ** 63)

    def test_unsigned_byte_validator(self):
        self.assertIsNone(unsigned_byte_validator(255))
        self.assertIsNone(unsigned_byte_validator(0))

        with self.assertRaises(XMLSchemaValidationError):
            unsigned_byte_validator(256)

    def test_unsigned_short_validator(self):
        self.assertIsNone(unsigned_short_validator(2 ** 16 - 1))
        self.assertIsNone(unsigned_short_validator(0))

        with self.assertRaises(XMLSchemaValidationError):
            unsigned_short_validator(2 ** 16)

    def test_negative_int_validator(self):
        self.assertIsNone(negative_int_validator(-1))
        self.assertIsNone(negative_int_validator(-2 ** 65))

        with self.assertRaises(XMLSchemaValidationError):
            negative_int_validator(0)

    def test_error_type_validator(self):
        with self.assertRaises(XMLSchemaValidationError):
            error_type_validator('alpha')
        with self.assertRaises(XMLSchemaValidationError):
            error_type_validator(0)

    def test_set_logging_level(self):
        logger = logging.getLogger('xmlschema')
        current_level = logger.level
        try:
            self.assertRaises(TypeError, set_logging_level, None)
            self.assertEqual(logger.level, current_level)

            set_logging_level(logging.DEBUG)
            self.assertEqual(logger.level, logging.DEBUG)

            set_logging_level('ERROR')
            self.assertEqual(logger.level, logging.ERROR)

            self.assertRaises(ValueError, set_logging_level, 'WRONG')
        finally:
            logger.setLevel(current_level)

    def test_logged_decorator(self):
        logger = logging.getLogger('xmlschema')

        def func(*args, **kwargs):
            logger.warning('Warning log line')
            logger.info('Info log line')
            logger.debug('Debug log line')

        with self.assertLogs('xmlschema', level='DEBUG') as ctx:
            logged(func)(loglevel='ERROR')
            self.assertEqual(logger.level, logging.DEBUG)
            self.assertEqual(len(ctx.output), 0)

            logged(func)(loglevel='WARNING')
            self.assertEqual(logger.level, logging.DEBUG)
            self.assertEqual(len(ctx.output), 1)
            self.assertIn("Warning log line", ctx.output[-1])

            logged(func)(loglevel='INFO')
            self.assertEqual(logger.level, logging.DEBUG)
            self.assertEqual(len(ctx.output), 3)
            self.assertIn("Warning log line", ctx.output[-2])
            self.assertIn("Info log line", ctx.output[-1])

            logged(func)()
            self.assertEqual(logger.level, logging.DEBUG)
            self.assertEqual(len(ctx.output), 6)
            self.assertIn("Warning log line", ctx.output[-3])
            self.assertIn("Info log line", ctx.output[-2])
            self.assertIn("Debug log line", ctx.output[-1])

    def test_format_xmlschema_stack(self):
        phrase = 'this is a test'
        self.assertNotIn(phrase, format_xmlschema_stack(phrase), '')
        self.assertIn(phrase, format_xmlschema_stack('this is a test'), '')

    def test_dump_data(self):
        if sys.version_info >= (3, 11):
            with self.assertNoLogs('xmlschema', 'WARNING'):
                dump_data()

        xml_data = XMLResource('<root><child/></root>', lazy=True)
        with self.assertLogs('xmlschema', 'WARNING') as cm:
            dump_data(xml_data, 1, 2, 3, 'foo')

        self.assertIn('dump data for xmlschema', cm.output[0])
        self.assertNotIn('URL:', cm.output[0])

        with self.assertLogs('xmlschema', 'WARNING') as cm:
            dump_data(XMLSchema.meta_schema.source)

        self.assertIn('dump data for xmlschema', cm.output[0])
        self.assertIn('URL:', cm.output[0])

    def test_will_change_decorator(self):
        @will_change('2.0')
        def f():
            pass

        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")
            _ = f()

        self.assertEqual(len(ctx), 1, "Wrong number of include/import warnings")
        self.assertEqual(ctx[0].category, FutureWarning)
        self.assertTrue(str(ctx[0].message).endswith(" will change from v2.0."))

    def test_deprecated_decorator(self):
        @deprecated('2.0')
        def f():
            pass

        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")
            _ = f()

        self.assertEqual(len(ctx), 1, "Wrong number of include/import warnings")
        self.assertEqual(ctx[0].category, DeprecationWarning)
        self.assertTrue(str(ctx[0].message).endswith(" will be removed in v2.0."))


if __name__ == '__main__':
    run_xmlschema_tests('utils')
