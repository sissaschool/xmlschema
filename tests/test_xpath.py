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
import pathlib
from xml.etree import ElementTree

from elementpath import XPath1Parser, XPath2Parser, Selector, LazyElementNode

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.names import XSD_NAMESPACE
from xmlschema.xpath import XMLSchemaProxy, XPathElement
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
        self.assertIs(context.root.value, self.xs1)

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


class XPathElementTest(unittest.TestCase):

    schema_class = XMLSchema10
    col_xsd_path = None

    @classmethod
    def setUpClass(cls):
        cls.col_xsd_path = pathlib.Path(CASES_DIR).joinpath("examples/collection/collection.xsd")
        cls.col_schema = cls.schema_class(cls.col_xsd_path)

    def test_is_matching(self):
        # The mixin method is used by schema class but overridden for XSD components.
        # A schema has no formal name, so it takes the source's filename, if any.
        # This does not have effect on validation because schema is the root.
        self.assertEqual(self.col_schema.default_namespace, 'http://example.com/ns/collection')
        self.assertEqual(self.col_schema.name, 'collection.xsd')
        self.assertTrue(self.col_schema.is_matching('collection.xsd'))
        self.assertFalse(
            self.col_schema.is_matching('collection.xsd', 'http://example.com/ns/collection')
        )

    def test_iteration(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        self.assertListEqual(
            [child.name for child in elem],
            ['position', 'title', 'year', 'author', 'estimation', 'characters']
        )

        elem = XPathElement('foo', self.col_schema.builtin_types()['string'])
        self.assertListEqual(list(elem), [])

    def test_xpath_proxy(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        xpath_proxy = elem.xpath_proxy
        self.assertIsInstance(xpath_proxy, XMLSchemaProxy)
        self.assertIs(xpath_proxy._schema, self.col_schema)

    def test_xpath_node(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        xpath_node = elem.xpath_node
        self.assertIsInstance(xpath_node, LazyElementNode)
        self.assertIs(xpath_node, elem._xpath_node)
        self.assertIs(xpath_node, elem.xpath_node)

    def test_schema(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        self.assertIs(elem.schema, self.col_schema)
        self.assertIs(elem.namespaces, self.col_schema.namespaces)

    def test_target_namespace(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        self.assertEqual(elem.target_namespace, 'http://example.com/ns/collection')

    def test_xsd_version(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        self.assertEqual(elem.xsd_version, self.col_schema.xsd_version)

    def test_maps(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        self.assertIs(elem.maps, self.col_schema.maps)

    def test_elem_name(self):
        elem = XPathElement('foo', self.col_schema.types['objType'])
        try:
            elem.namespaces['col'] = 'http://example.com/ns/collection'

            self.assertEqual(elem.local_name, 'foo')
            self.assertEqual(elem.qualified_name, '{http://example.com/ns/collection}foo')
            self.assertEqual(elem.prefixed_name, 'foo')

            elem = XPathElement('{http://example.com/ns/collection}foo',
                                self.col_schema.types['objType'])
            self.assertEqual(elem.local_name, 'foo')
            self.assertEqual(elem.qualified_name, '{http://example.com/ns/collection}foo')
            self.assertEqual(elem.prefixed_name, 'col:foo')
        finally:
            elem.namespaces.pop('col')


class XMLSchemaXPathTest(unittest.TestCase):

    schema_class = XMLSchema10
    xs1: XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.xs1 = cls.schema_class(os.path.join(CASES_DIR, "examples/vehicles/vehicles.xsd"))
        cls.xs2 = cls.schema_class(os.path.join(CASES_DIR, "examples/collection/collection.xsd"))
        cls.cars = cls.xs1.elements['vehicles'].type.content[0]
        cls.bikes = cls.xs1.elements['vehicles'].type.content[1]

    def test_xpath_wrong_syntax(self):
        self.assertRaises(SyntaxError, self.xs1.find, './*[')
        self.assertRaises(SyntaxError, self.xs1.find, './*)')
        self.assertRaises(SyntaxError, self.xs1.find, './*3')
        self.assertRaises(SyntaxError, self.xs1.find, './@3')

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
        car = self.xs1.elements['cars'].type.content[0]

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
        self.assertEqual(xsd_element[0], xsd_element.type.content[0])
        self.assertEqual(xsd_element[1], xsd_element.type.content[1])
        with self.assertRaises(IndexError):
            _ = xsd_element[2]

    def test_reversed(self):
        xsd_element = self.xs1.elements['vehicles']
        self.assertListEqual(
            list(reversed(xsd_element)),
            [xsd_element.type.content[1], xsd_element.type.content[0]]
        )

    def test_iterfind(self):
        car = self.xs1.find('//vh:car')
        bike = self.xs1.find('//vh:bike')
        self.assertIsNotNone(car)
        self.assertIsNotNone(bike)
        self.assertListEqual(list(self.xs1.iterfind("/(vh:vehicles/*/*)")), [car, bike])

    def test_iter(self):
        xsd_element = self.xs1.elements['vehicles']
        descendants = list(xsd_element.iter())
        self.assertListEqual(descendants, [xsd_element] + xsd_element.type.content[:])

        descendants = list(xsd_element.iter('*'))
        self.assertListEqual(descendants, [xsd_element] + xsd_element.type.content[:])

        descendants = list(xsd_element.iter(self.xs1.elements['cars'].name))
        self.assertListEqual(descendants, [xsd_element.type.content[0]])

    def test_iterchildren(self):
        children = list(self.xs1.elements['vehicles'].iterchildren())
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content[:])
        children = list(self.xs1.elements['vehicles'].iterchildren('*'))
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content[:])
        children = list(self.xs1.elements['vehicles'].iterchildren(self.xs1.elements['bikes'].name))
        self.assertListEqual(children, self.xs1.elements['vehicles'].type.content[1:])


class ElementTreeXPathTest(unittest.TestCase):

    def test_rel_xpath_boolean(self):
        root = ElementTree.XML('<A><B><C/></B></A>')
        el = root[0]
        self.assertTrue(Selector('boolean(C)').iter_select(el))
        self.assertFalse(next(Selector('boolean(D)').iter_select(el)))


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('XPath processor')
