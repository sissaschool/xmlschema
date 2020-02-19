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
"""Tests for XPath parsing and selectors"""

import unittest
import os
import xml.etree.ElementTree as ElementTree
from elementpath import XPath1Parser, XPath2Parser, Selector, ElementPathSyntaxError

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.namespaces import XSD_NAMESPACE
from xmlschema.xpath import XMLSchemaProxy
from xmlschema.validators import XsdAtomic, XsdAtomicRestriction

CASES_DIR = os.path.join(os.path.dirname(__file__), 'test_cases/')


class XMLSchemaProxyTest(unittest.TestCase):

    schema_class = XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.xs1 = cls.schema_class(os.path.join(CASES_DIR, "examples/vehicles/vehicles.xsd"))
        cls.xs2 = cls.schema_class(os.path.join(CASES_DIR, "examples/collection/collection.xsd"))
        cls.xs3 = cls.schema_class(os.path.join(CASES_DIR, "features/decoder/simple-types.xsd"))

    def test_initialization(self):
        schema_proxy = XMLSchemaProxy()
        self.assertIs(schema_proxy._schema, self.schema_class.meta_schema)

        schema_proxy = XMLSchemaProxy(self.xs1, base_element=self.xs1.elements['vehicles'])
        self.assertIs(schema_proxy._schema, self.xs1)

        with self.assertRaises(ValueError):
            XMLSchemaProxy(self.xs1, base_element=self.xs2.elements['collection'])

        with self.assertRaises(TypeError):
            XMLSchemaProxy(self.xs1, base_element=ElementTree.Element('vehicles'))

    def test_bind_parser_method(self):
        schema_proxy1 = XMLSchemaProxy(self.xs1)
        schema_proxy2 = XMLSchemaProxy(self.xs2)
        parser = XPath2Parser(strict=False, schema=schema_proxy1)
        self.assertIs(parser.schema, schema_proxy1)
        schema_proxy1.bind_parser(parser)
        self.assertIs(parser.schema, schema_proxy1)
        schema_proxy2.bind_parser(parser)
        self.assertIs(parser.schema, schema_proxy2)

    def test_get_context_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        context = schema_proxy.get_context()
        self.assertIs(context.root, self.xs1)

    def test_get_type_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        qname = '{%s}vehicleType' % self.xs1.target_namespace
        self.assertIs(schema_proxy.get_type(qname), self.xs1.types['vehicleType'])
        qname = '{%s}unknown' % self.xs1.target_namespace
        self.assertIsNone(schema_proxy.get_type(qname))

    def test_get_attribute_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        qname = '{%s}step' % self.xs1.target_namespace
        self.assertIs(schema_proxy.get_attribute(qname), self.xs1.attributes['step'])
        qname = '{%s}unknown' % self.xs1.target_namespace
        self.assertIsNone(schema_proxy.get_attribute(qname))

    def test_get_element_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        qname = '{%s}cars' % self.xs1.target_namespace
        self.assertIs(schema_proxy.get_element(qname), self.xs1.elements['cars'])
        qname = '{%s}unknown' % self.xs1.target_namespace
        self.assertIsNone(schema_proxy.get_element(qname))

    def test_get_substitution_group_method(self):
        schema = XMLSchema11.meta_schema
        schema.build()
        schema_proxy = XMLSchemaProxy(schema)
        qname = '{%s}facet' % schema.target_namespace
        self.assertIs(schema_proxy.get_substitution_group(qname),
                      schema.substitution_groups['facet'])
        qname = '{%s}unknown' % schema.target_namespace
        self.assertIsNone(schema_proxy.get_substitution_group(qname))

    def test_find_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        qname = '{%s}cars' % self.xs1.target_namespace
        self.assertIs(schema_proxy.find(qname), self.xs1.elements['cars'])

    def test_is_instance_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        type_qname = '{%s}string' % self.xs1.meta_schema.target_namespace
        self.assertFalse(schema_proxy.is_instance(10, type_qname))
        self.assertTrue(schema_proxy.is_instance('10', type_qname))

    def test_cast_as_method(self):
        schema_proxy = XMLSchemaProxy(self.xs1)
        type_qname = '{%s}short' % self.xs1.meta_schema.target_namespace
        self.assertEqual(schema_proxy.cast_as('10', type_qname), 10)

    def test_iter_atomic_types_method(self):
        schema_proxy = XMLSchemaProxy(self.xs3)
        k = 0
        for k, xsd_type in enumerate(schema_proxy.iter_atomic_types(), start=1):
            self.assertNotIn(XSD_NAMESPACE, xsd_type.name)
            self.assertIsInstance(xsd_type, (XsdAtomic, XsdAtomicRestriction))
        self.assertGreater(k, 10)

    def test_get_primitive_type_method(self):
        schema_proxy = XMLSchemaProxy(self.xs3)

        string_type = self.xs3.meta_schema.types['string']
        xsd_type = self.xs3.types['list_of_strings']
        self.assertIs(schema_proxy.get_primitive_type(xsd_type), string_type)

        xsd_type = self.xs3.types['integer_or_float']
        self.assertIs(schema_proxy.get_primitive_type(xsd_type), xsd_type)


class XMLSchemaXPathTest(unittest.TestCase):

    schema_class = XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.xs1 = cls.schema_class(os.path.join(CASES_DIR, "examples/vehicles/vehicles.xsd"))
        cls.xs2 = cls.schema_class(os.path.join(CASES_DIR, "examples/collection/collection.xsd"))
        cls.cars = cls.xs1.elements['vehicles'].type.content_type[0]
        cls.bikes = cls.xs1.elements['vehicles'].type.content_type[1]

    def test_xpath_wrong_syntax(self):
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*[')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*)')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './*3')
        self.assertRaises(ElementPathSyntaxError, self.xs1.find, './@3')

    def test_xpath_extra_spaces(self):
        self.assertTrue(self.xs1.find('./ *') is not None)
        self.assertTrue(self.xs1.find("\t\n vh:vehicles / vh:cars / .. /  vh:cars") == self.cars)

    def test_xpath_location_path(self):
        elements = sorted(self.xs1.elements.values(), key=lambda x: x.name)
        self.assertTrue(self.xs1.findall('.'))
        self.assertTrue(isinstance(self.xs1.find('.'), self.schema_class))
        self.assertTrue(sorted(self.xs1.findall("*"), key=lambda x: x.name) == elements)
        self.assertListEqual(self.xs1.findall("*"), self.xs1.findall("./*"))
        self.assertEqual(self.xs1.find("./vh:bikes"), self.xs1.elements['bikes'])
        self.assertEqual(self.xs1.find("./vh:vehicles/vh:cars").name,
                         self.xs1.elements['cars'].name)
        self.assertNotEqual(self.xs1.find("./vh:vehicles/vh:cars"), self.xs1.elements['cars'])
        self.assertNotEqual(self.xs1.find("/vh:vehicles/vh:cars"), self.xs1.elements['cars'])
        self.assertEqual(self.xs1.find("vh:vehicles/vh:cars/.."), self.xs1.elements['vehicles'])
        self.assertEqual(self.xs1.find("vh:vehicles/*/.."), self.xs1.elements['vehicles'])
        self.assertEqual(self.xs1.find("vh:vehicles/vh:cars/../vh:cars"),
                         self.xs1.find("vh:vehicles/vh:cars"))

    def test_xpath_axis(self):
        self.assertEqual(self.xs1.find("vh:vehicles/child::vh:cars/.."),
                         self.xs1.elements['vehicles'])

    def test_xpath_subscription(self):
        self.assertEqual(len(self.xs1.findall("./vh:vehicles/*")), 2)
        self.assertListEqual(self.xs1.findall("./vh:vehicles/*[2]"), [self.bikes])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/*[3]"), [])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/*[last()-1]"), [self.cars])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/*[position()=last()]"), [self.bikes])

    def test_xpath_group(self):
        self.assertEqual(self.xs1.findall("/(vh:vehicles/*/*)"),
                         self.xs1.findall("/vh:vehicles/*/*"))
        self.assertEqual(self.xs1.findall("/(vh:vehicles/*/*)[1]"),
                         self.xs1.findall("/vh:vehicles/*/*[1]")[:1])

    def test_xpath_predicate(self):
        car = self.xs1.elements['cars'].type.content_type[0]
        self.assertListEqual(self.xs1.findall("./vh:vehicles/vh:cars/vh:car[@make]"), [car])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/vh:cars/vh:car[@make]"), [car])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/vh:cars['ciao']"), [self.cars])
        self.assertListEqual(self.xs1.findall("./vh:vehicles/*['']"), [])

    def test_xpath_descendants(self):
        selector = Selector('.//xs:element', self.xs2.namespaces, parser=XPath1Parser)
        elements = list(selector.iter_select(self.xs2.root))
        self.assertEqual(len(elements), 14)
        selector = Selector('.//xs:element|.//xs:attribute|.//xs:keyref',
                            self.xs2.namespaces, parser=XPath1Parser)
        elements = list(selector.iter_select(self.xs2.root))
        self.assertEqual(len(elements), 17)

    def test_xpath_issues(self):
        namespaces = {'ps': "http://schemas.microsoft.com/powershell/2004/04"}
        selector = Selector("./ps:Props/*|./ps:MS/*", namespaces=namespaces, parser=XPath1Parser)
        self.assertTrue(selector.root_token.tree,
                        '(| (/ (/ (.) (: (ps) (Props))) (*)) (/ (/ (.) (: (ps) (MS))) (*)))')

    def test_get(self):
        xsd_element = self.xs1.elements['vehicles']
        self.assertIsNone(xsd_element.get('unknown'))
        self.assertEqual(xsd_element[0][0].get('model'), xsd_element[0][0].attributes['model'])

    def test_getitem(self):
        xsd_element = self.xs1.elements['vehicles']
        self.assertEqual(xsd_element[0], xsd_element.type.content_type[0])
        self.assertEqual(xsd_element[1], xsd_element.type.content_type[1])
        with self.assertRaises(IndexError):
            _ = xsd_element[2]

    def test_reversed(self):
        xsd_element = self.xs1.elements['vehicles']
        self.assertListEqual(
            list(reversed(xsd_element)),
            [xsd_element.type.content_type[1], xsd_element.type.content_type[0]]
        )

    def test_iter(self):
        xsd_element = self.xs1.elements['vehicles']
        descendants = list(xsd_element.iter())
        self.assertListEqual(descendants, [xsd_element] + xsd_element.type.content_type[:])

        descendants = list(xsd_element.iter('*'))
        self.assertListEqual(descendants, [xsd_element] + xsd_element.type.content_type[:])

        descendants = list(xsd_element.iter(self.xs1.elements['cars'].name))
        self.assertListEqual(descendants, [xsd_element.type.content_type[0]])

    def test_iterchildren(self):
        children = list(self.xs1.elements['vehicles'].iterchildren())
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content_type[:])
        children = list(self.xs1.elements['vehicles'].iterchildren('*'))
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content_type[:])
        children = list(self.xs1.elements['vehicles'].iterchildren(self.xs1.elements['bikes'].name))
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content_type[1:])


class ElementTreeXPathTest(unittest.TestCase):

    def test_rel_xpath_boolean(self):
        root = ElementTree.XML('<A><B><C/></B></A>')
        el = root[0]
        self.assertTrue(Selector('boolean(C)').iter_select(el))
        self.assertFalse(next(Selector('boolean(D)').iter_select(el)))


if __name__ == '__main__':
    from xmlschema.testing import print_test_header

    print_test_header()
    unittest.main()
