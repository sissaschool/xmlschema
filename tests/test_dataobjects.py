#!/usr/bin/env python
#
# Copyright (c), 2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Dict

from xmlschema import XMLSchema10, XMLSchema11, fetch_namespaces, etree_tostring, \
    XMLSchemaValidationError, DataElement, DataElementConverter, XMLResource, \
    XsdElement, XsdAttribute, XsdType

from xmlschema.validators import XsdAttributeGroup
from xmlschema.utils.etree import is_etree_element
from xmlschema.names import XSI_TYPE
from xmlschema.dataobjects import DataBindingMeta, DataBindingConverter
from xmlschema.testing import etree_elements_assert_equal, run_xmlschema_tests


class TestDataElementInterface(unittest.TestCase):

    def test_repr(self):
        self.assertEqual(repr(DataElement('foo')), "DataElement(tag='foo')")

    def test_value(self):
        self.assertIsNone(DataElement('foo').value)
        self.assertEqual(DataElement('foo', value=10).value, 10)
        self.assertEqual(DataElement('foo', 1.8).value, 1.8)
        self.assertFalse(DataElement('foo', False).value)

    def test_attributes(self):
        self.assertEqual(DataElement('foo').attrib, {})
        attrib = {'a': 10, 'b': 'bar'}
        self.assertEqual(DataElement('foo', attrib=attrib).attrib, attrib)
        self.assertEqual(DataElement('foo', attrib=attrib).get('a'), 10)
        self.assertIsNone(DataElement('foo', attrib=attrib).get('c'))

        data_element = DataElement('foo')
        data_element.set('b', 9)
        self.assertIsNone(data_element.get('a'))
        self.assertEqual(data_element.get('b'), 9)

    def test_nsmap(self):
        self.assertEqual(DataElement('foo').nsmap, {})
        nsmap = {'tns': 'http://xmlschema.test/ns'}
        self.assertEqual(DataElement('foo', nsmap=nsmap).nsmap, nsmap)
        self.assertIsNot(DataElement('foo', nsmap=nsmap).nsmap, nsmap)

    def test_attributes_with_namespaces(self):
        nsmap = {'tns': 'http://xmlschema.test/ns'}
        attrib = {'tns:a': 10, '{http://xmlschema.test/ns}b': 'bar'}
        element = DataElement('foo', attrib=attrib, nsmap=nsmap)

        self.assertEqual(element.get('tns:a'), 10)
        self.assertEqual(element.get('{http://xmlschema.test/ns}a'), 10)

        self.assertEqual(element.get('{http://xmlschema.test/ns}b'), 'bar')
        self.assertEqual(element.get('tns:b'), 'bar')
        self.assertIsNone(element.get('tns:c'))

        self.assertIsNone(element.get('tns:b:c'))
        self.assertIsNone(element.get('tns0:b'))

        self.assertIsNone(element.set('tns:c', 8))
        self.assertEqual(element.get('tns:c'), 8)

    def test_text_value(self):
        self.assertIsNone(DataElement('foo').text)
        self.assertEqual(DataElement('foo', value=True).text, 'true')
        self.assertEqual(DataElement('foo', value=False).text, 'false')
        self.assertEqual(DataElement('foo', value=10.0).text, '10.0')


class TestDataObjects(unittest.TestCase):

    schema_class = XMLSchema10
    converter = DataElementConverter

    col_xsd_filename: str
    col_xml_filename: str
    col_nsmap: Dict[str, str]

    @classmethod
    def setUpClass(cls):
        cls.col_xsd_filename = cls.casepath('examples/collection/collection.xsd')
        cls.col_xml_filename = cls.casepath('examples/collection/collection.xml')
        cls.col_xml_root = ElementTree.parse(cls.col_xml_filename).getroot()
        cls.col_nsmap = fetch_namespaces(cls.col_xml_filename)
        cls.col_namespace = cls.col_nsmap['col']
        cls.col_schema = cls.schema_class(cls.col_xsd_filename, converter=cls.converter)

    @classmethod
    def casepath(cls, relative_path):
        return str(Path(__file__).parent.joinpath('test_cases', relative_path))

    def test_namespace(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertIsInstance(col_data, DataElement)
        self.assertEqual(col_data.tag, '{http://example.com/ns/collection}collection')
        self.assertEqual(col_data.namespace, 'http://example.com/ns/collection')

        self.assertEqual(col_data[0].tag, 'object')
        self.assertEqual(col_data[0].namespace, 'http://example.com/ns/collection')

        self.assertEqual(DataElement('foo').namespace, '')

    def test_names(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertEqual(col_data.tag, '{http://example.com/ns/collection}collection')
        self.assertEqual(col_data.name, col_data.tag)
        self.assertEqual(col_data.prefixed_name, 'col:collection')
        self.assertEqual(col_data.local_name, 'collection')

        self.assertEqual(col_data[1].tag, 'object')
        self.assertEqual(col_data[1].prefixed_name, 'object')
        self.assertEqual(col_data[1].local_name, 'object')

    def test_xsd_version(self):
        self.assertEqual(DataElement(tag=self.col_xml_root.tag).xsd_version, '1.0')

        xsd_element = self.col_schema.elements['person']
        data_element = DataElement(tag=self.col_xml_root.tag, xsd_element=xsd_element)
        self.assertEqual(data_element.xsd_version, self.col_schema.XSD_VERSION)

    def test_xsd_element_binding(self):
        xsd_element = self.col_schema.elements['person']
        data_element = DataElement(tag=self.col_xml_root.tag, xsd_element=xsd_element)
        data_element.xsd_element = xsd_element

        with self.assertRaises(TypeError) as ec:
            DataElement(tag=xsd_element.name, xsd_element=self.col_schema)
        self.assertIn("invalid type for attribute 'xsd_element'", str(ec.exception))

        with self.assertRaises(ValueError) as ec:
            data_element.xsd_element = self.col_schema.elements['collection']
        self.assertIn('the instance is already bound to another XSD element', str(ec.exception))

    def test_xsd_type_binding(self):
        xsd_type = self.col_schema.elements['person'].type
        data_element = DataElement(tag=self.col_xml_root.tag, xsd_type=xsd_type)

        with self.assertRaises(TypeError) as ec:
            DataElement(tag=self.col_xml_root.tag, xsd_type=self.col_schema)
        self.assertIn("invalid type for attribute 'xsd_type'", str(ec.exception))

        with self.assertRaises(ValueError) as ec:
            data_element.xsd_element = self.col_schema.elements['collection']
        self.assertIn('the instance is already bound to another XSD type', str(ec.exception))

        with self.assertRaises(ValueError) as ec:
            data_element.xsd_type = self.col_schema.elements['collection'].type
        self.assertIn('the instance is already bound to another XSD type', str(ec.exception))

    def test_mutable_mapping_api(self):
        data_element = DataElement('root')

        self.assertEqual(len(data_element), 0)
        with self.assertRaises(AssertionError):
            data_element.append(1)

        data_element.append(DataElement('elem1'))
        self.assertEqual(len(data_element), 1)
        self.assertEqual(data_element[0].tag, 'elem1')

        data_element.insert(0, DataElement('elem0'))
        self.assertEqual(len(data_element), 2)
        self.assertEqual(data_element[0].tag, 'elem0')
        self.assertEqual(data_element[1].tag, 'elem1')

        data_element[0] = DataElement('elem2')
        self.assertEqual(data_element[0].tag, 'elem2')

        del data_element[0]
        self.assertEqual(len(data_element), 1)
        self.assertEqual(data_element[0].tag, 'elem1')

    def test_xpath_api(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertIs(col_data.find('.'), col_data)
        self.assertIs(col_data.find('*'), col_data[0])
        self.assertIs(col_data.find('object[2]'), col_data[1])

        self.assertListEqual(col_data.findall('*'), col_data[:])
        self.assertListEqual(list(col_data.iterfind('*')), col_data[:])

    def test_iter(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertEqual(len(list(col_data.iter())), len(list(self.col_xml_root.iter())))
        for elem, data_element in zip(self.col_xml_root.iter(), col_data.iter()):
            self.assertEqual(elem.tag, data_element.tag)
            self.assertIsInstance(data_element, DataElement)

        self.assertEqual(len(list(col_data.iter('*'))), len(list(col_data.iter())))
        self.assertEqual(len(list(col_data.iter('object'))), 2)

    def test_iterchildren(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertListEqual(list(col_data.iterchildren()), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('*')), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('object')), col_data[:])
        self.assertListEqual(list(col_data.iterchildren('position')), [])

    def test_schema_bindings(self):
        data_element = DataElement('foo')
        self.assertIsNone(data_element.xsd_type)

        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertIs(col_data.xsd_type, self.col_schema.elements['collection'].type)

        with self.assertRaises(ValueError) as ec:
            col_data.xsd_type = col_data[0].xsd_type
        self.assertEqual(str(ec.exception), "the instance is already bound to another XSD type")

    def test_xmlns_processing_argument(self):
        xsd_file = self.casepath('examples/collection/collection5.xsd')
        xml_file = self.casepath('examples/collection/collection-redef-xmlns.xml')

        xmlns0 = [('col1', 'http://example.com/ns/collection'),
                  ('col', 'http://xmlschema.test/ns'),
                  ('', 'http://xmlschema.test/ns'),
                  ('xsi', 'http://www.w3.org/2001/XMLSchema-instance')]
        nsmap0 = dict(xmlns0)
        xmlns1 = [('col', 'http://example.com/ns/collection')]
        nsmap1 = dict(xmlns0)
        nsmap1.update(xmlns1)
        schema = self.schema_class(xsd_file)
        self.assertTrue(schema.is_valid(xml_file))

        resource = XMLResource(xml_file)
        obj = schema.decode(resource, converter=self.converter)
        self.assertListEqual(obj.xmlns, xmlns0)
        self.assertDictEqual(obj.nsmap, nsmap0)
        self.assertListEqual(obj[0].xmlns, xmlns1)
        self.assertDictEqual(obj[0].nsmap, nsmap1)
        root = schema.encode(obj, converter=self.converter)
        self.assertTrue(is_etree_element(root))

        obj = schema.decode(resource, converter=self.converter, xmlns_processing='stacked')
        self.assertListEqual(obj.xmlns, xmlns0)
        self.assertDictEqual(obj.nsmap, nsmap0)
        self.assertListEqual(obj[0].xmlns, xmlns1)
        self.assertDictEqual(obj[0].nsmap, nsmap1)
        root = schema.encode(obj, converter=self.converter, xmlns_processing='stacked')
        self.assertTrue(is_etree_element(root))

        obj = schema.decode(resource, converter=self.converter, xmlns_processing='collapsed')
        root = schema.encode(obj, converter=self.converter, xmlns_processing='collapsed')
        self.assertTrue(is_etree_element(root))

        obj = schema.decode(resource, converter=self.converter, xmlns_processing='root-only')
        root = schema.encode(obj, converter=self.converter, xmlns_processing='root-only')
        self.assertTrue(is_etree_element(root))

        obj = schema.decode(resource, converter=self.converter, xmlns_processing='none')
        root = schema.encode(obj, converter=self.converter, xmlns_processing='none')
        self.assertTrue(is_etree_element(root))
        for data_element in obj.iter():
            self.assertDictEqual(data_element.nsmap, {})

    def test_encode_to_element_tree(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        obj = col_data.encode()
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, self.col_xml_root, strict=False))
        self.assertIsNone(
            etree_elements_assert_equal(obj, col_data.encode(converter=self.converter))
        )

        with self.assertRaises(ValueError) as ec:
            col_data.xsd_type = col_data[0].xsd_type
        self.assertEqual(str(ec.exception), "the instance is already bound to another XSD type")

        with self.assertRaises(ValueError) as ec:
            col_data.xsd_element = col_data[0].xsd_element
        self.assertEqual(str(ec.exception), "the instance is already bound to another XSD element")

        any_data = DataElement('a')
        any_data.append(DataElement('b1', 1999))
        any_data.append(DataElement('b2', 'alpha'))
        any_data.append(DataElement('b3', True))

        with self.assertRaises(ValueError) as ec:
            any_data.encode()
        self.assertIn("has no schema bindings", str(ec.exception))

        root = ElementTree.XML('<a><b1>1999</b1><b2>alpha</b2><b3>true</b3></a>')

        obj = any_data.encode(validation='skip')
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, root, strict=False))

        any_data = DataElement('root', attrib={'a1': 49})
        any_data.append(DataElement('child', 18.7, attrib={'a2': False}))

        root = ElementTree.XML('<root a1="49"><child a2="false">18.7</child></root>')

        obj = any_data.encode(validation='skip')
        self.assertTrue(is_etree_element(obj))
        self.assertIsInstance(etree_tostring(obj), str)
        self.assertIsNone(etree_elements_assert_equal(obj, root, strict=False))

    def test_collapsed_namespace_map(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        namespaces = col_data.get_namespaces()
        self.assertDictEqual(
            namespaces,
            {'col': 'http://example.com/ns/collection',
             'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

        namespaces = col_data.get_namespaces({'': 'http://xmlschema.test/ns'})
        self.assertDictEqual(
            namespaces,
            {'': 'http://xmlschema.test/ns',
             'col': 'http://example.com/ns/collection',
             'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

        namespaces = col_data.get_namespaces({'tns': 'http://xmlschema.test/ns'})
        self.assertDictEqual(
            namespaces,
            {'tns': 'http://xmlschema.test/ns',
             'col': 'http://example.com/ns/collection',
             'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

        namespaces = col_data.get_namespaces({'xsi': 'http://xmlschema.test/ns'})
        self.assertDictEqual(
            namespaces,
            {'xsi': 'http://xmlschema.test/ns',
             'col': 'http://example.com/ns/collection',
             'xsi0': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

        xsd_filename = self.casepath('examples/collection/collection5.xsd')
        col_schema = self.schema_class(xsd_filename, converter=self.converter)
        xml_filename = self.casepath('examples/collection/collection-default.xml')
        col_data = col_schema.decode(xml_filename)

        namespaces = col_data.get_namespaces()
        self.assertDictEqual(
            namespaces,
            {'': 'http://example.com/ns/collection',
             'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

        namespaces = col_data.get_namespaces({'': 'http://xmlschema.test/ns'})
        self.assertDictEqual(
            namespaces,
            {'': 'http://xmlschema.test/ns',
             'default': 'http://example.com/ns/collection',
             'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
        )

    def test_serialize_to_xml_source(self):
        col_data = self.col_schema.decode(self.col_xml_filename)

        with Path(self.col_xml_filename).open() as fp:
            _ = fp.read()

        result = col_data.tostring()
        self.assertTrue(result.startswith('<col:collection '))
        self.assertTrue(result.endswith('</col:collection>'))

        result = col_data.tostring(xml_declaration=True)
        self.assertTrue(self.col_schema.is_valid(result))

    def test_validation(self):
        with self.assertRaises(ValueError) as ec:
            DataElement(self.col_xml_root).validate()
        self.assertIn("has no schema bindings", str(ec.exception))

        col_data = self.col_schema.decode(self.col_xml_filename)

        self.assertIsNone(col_data.validate())
        self.assertTrue(col_data.is_valid())
        self.assertListEqual(list(col_data.iter_errors()), [])

        col_data = self.col_schema.decode(self.col_xml_root)
        self.assertEqual(col_data.nsmap, {})
        self.assertTrue(col_data.is_valid())

        # FIXME: are namespaces really needed for validation of data elements???
        #  (that use iter_encode() instead of iter_decode() ...)
        self.assertTrue(col_data.is_valid(namespaces={
            'col': 'http://example.com/ns/collection',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }))

        # Encoding back using the default namespace is simple with
        # data elements because you still have the original tags.
        self.assertTrue(col_data.is_valid(namespaces={
            '': 'http://example.com/ns/collection',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }))

    def test_invalid_value_type(self):
        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertTrue(col_data.is_valid())

        col_data[0][0].value = '1'
        with self.assertRaises(XMLSchemaValidationError) as ec:
            col_data.validate()
        self.assertIn("'1' is not an instance of <class 'int'>", str(ec.exception))
        self.assertFalse(col_data.is_valid())

        errors = list(col_data.iter_errors())
        self.assertEqual(len(errors), 1)
        self.assertIn("'1' is not an instance of <class 'int'>", str(errors[0]))

        col_data.find('object/position').value = 1
        self.assertTrue(col_data.is_valid())

    def test_missing_child(self):
        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertTrue(col_data.is_valid())

        title = col_data[0].pop(1)
        with self.assertRaises(XMLSchemaValidationError) as ec:
            col_data.validate()
        self.assertIn("Unexpected child with tag 'year' at position 2", str(ec.exception))
        self.assertFalse(col_data.is_valid())
        errors = list(col_data.iter_errors())
        self.assertEqual(len(errors), 1)
        self.assertIn("Unexpected child with tag 'year' at position 2", str(errors[0]))

        col_data[0].insert(1, title)
        self.assertTrue(col_data.is_valid())

    def test_max_depth_validation(self):
        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertTrue(col_data.is_valid())

        for child in col_data:
            child.clear()

        self.assertFalse(col_data.is_valid())
        self.assertTrue(col_data.is_valid(max_depth=0))
        self.assertTrue(col_data.is_valid(max_depth=1))
        self.assertFalse(col_data.is_valid(max_depth=2))

        col_data.clear()
        self.assertTrue(col_data.is_valid(max_depth=0))
        self.assertFalse(col_data.is_valid(max_depth=1))
        self.assertFalse(col_data.is_valid(max_depth=2))

    def test_converter_class(self):
        converter = self.converter()
        self.assertFalse(converter.lossy)
        self.assertTrue(converter.losslessly)

        class MyDataElement(DataElement):
            pass

        col_data = self.col_schema.decode(self.col_xml_filename, converter=converter)
        self.assertIsInstance(col_data, DataElement)
        self.assertNotIsInstance(col_data, MyDataElement)

        converter = self.converter(data_element_class=MyDataElement)
        self.assertIs(converter.data_element_class, MyDataElement)
        self.assertIs(converter.copy().data_element_class, MyDataElement)

        self.col_schema.maps.clear_bindings()  # needed for DataBindingConverter ...
        col_data = self.col_schema.decode(self.col_xml_filename, converter=converter)
        self.assertIsInstance(col_data, MyDataElement)

        with self.assertRaises(ValueError) as ec:
            converter.element_encode(col_data, col_data[0].xsd_element)
        self.assertEqual("Unmatched tag", str(ec.exception))

    def test_decoded_names__issue_314(self):
        xsd_file = self.casepath('issues/issue_314/issue_314.xsd')
        xml_file = self.casepath('issues/issue_314/issue_314.xml')
        schema = self.schema_class(xsd_file)

        data_element = schema.to_objects(xml_file, process_namespaces=True)
        self.assertEqual(data_element.prefixed_name, 'p:root-element')
        self.assertEqual(data_element[0].prefixed_name, 'p:container')
        self.assertEqual(data_element[0][0].prefixed_name, 'p:item')
        self.assertEqual(
            data_element[0][0].attrib,
            {'b:type': 'p:ConcreteContainterItemInfo', 'attr_2': 'value_2'}
        )
        self.assertEqual(data_element[0][0].get(XSI_TYPE), 'p:ConcreteContainterItemInfo')
        self.assertEqual(data_element[0][0].get('b:type'), 'p:ConcreteContainterItemInfo')
        self.assertIsNone(data_element[0][0].get('xsi:type'))

        data_element = schema.to_objects(xml_file, process_namespaces=False)
        self.assertEqual(data_element.prefixed_name, '{my_namespace}root-element')
        self.assertEqual(data_element[0].prefixed_name, '{my_namespace}container')
        self.assertEqual(data_element[0][0].prefixed_name, '{my_namespace}item')
        self.assertEqual(
            data_element[0][0].attrib,
            {f'{XSI_TYPE}': 'p:ConcreteContainterItemInfo', 'attr_2': 'value_2'}
        )
        self.assertEqual(data_element[0][0].get(XSI_TYPE), 'p:ConcreteContainterItemInfo')
        self.assertIsNone(data_element[0][0].get('b:type'))
        self.assertIsNone(data_element[0][0].get('xsi:type'))

        # For adding namespaces after decoding replace or update nsmap of each element
        namespaces = {'p': 'my_namespace', 'xsi': "http://www.w3.org/2001/XMLSchema-instance"}
        for e in data_element.iter():
            e.nsmap = namespaces

        self.assertEqual(data_element.prefixed_name, 'p:root-element')
        self.assertEqual(data_element[0].prefixed_name, 'p:container')
        self.assertEqual(data_element[0][0].prefixed_name, 'p:item')
        self.assertEqual(data_element[0][0].get(XSI_TYPE), 'p:ConcreteContainterItemInfo')
        self.assertIsNone(data_element[0][0].get('b:type'))
        self.assertEqual(data_element[0][0].get('xsi:type'), 'p:ConcreteContainterItemInfo')

    def test_map_attribute_names__issue_314(self):
        xsd_file = self.casepath('issues/issue_314/issue_314.xsd')
        xml_file = self.casepath('issues/issue_314/issue_314.xml')
        schema = self.schema_class(xsd_file)

        data_element = schema.to_objects(xml_file, map_attribute_names=False)
        self.assertEqual(data_element.prefixed_name, 'p:root-element')
        self.assertEqual(data_element[0].prefixed_name, 'p:container')
        self.assertEqual(data_element[0][0].prefixed_name, 'p:item')
        self.assertEqual(
            data_element[0][0].attrib,
            {f'{XSI_TYPE}': 'p:ConcreteContainterItemInfo', 'attr_2': 'value_2'}
        )
        self.assertEqual(data_element[0][0].get(XSI_TYPE), 'p:ConcreteContainterItemInfo')
        self.assertEqual(data_element[0][0].get('b:type'), 'p:ConcreteContainterItemInfo')
        self.assertIsNone(data_element[0][0].get('xsi:type'))

    def test_xsd_attribute_access__issue_331(self):
        col_data = self.col_schema.decode(self.col_xml_filename)
        self.assertIsInstance(col_data[0].xsd_element, XsdElement)
        self.assertEqual(col_data[0].xsd_element.name, 'object')
        self.assertIsInstance(
            col_data[0].xsd_element.attributes, XsdAttributeGroup
        )
        xsd_attribute = col_data[0].xsd_element.attributes.get('id')
        self.assertIsInstance(xsd_attribute, XsdAttribute)

        xsd_attribute = col_data[0].xsd_element.find('@id')
        self.assertIsInstance(xsd_attribute, XsdAttribute)
        self.assertIsInstance(xsd_attribute.type, XsdType)
        self.assertIsNone(col_data[0].xsd_element.find('@unknown'))


class TestDataBindings(TestDataObjects):

    converter = DataBindingConverter

    def test_data_binding_metaclass(self):
        xsd_element = self.col_schema.elements['collection']
        collection_class = DataBindingMeta(xsd_element.local_name.title(), (DataElement,),
                                           {'xsd_element': xsd_element})
        self.assertEqual(collection_class.__name__, 'Collection')
        self.assertEqual(collection_class.__qualname__, 'Collection')
        self.assertIsNone(collection_class.__module__)
        self.assertEqual(collection_class.namespace, 'http://example.com/ns/collection')
        self.assertEqual(collection_class.xsd_version, self.col_schema.XSD_VERSION)

        with self.assertRaises(AttributeError) as ec:
            DataBindingMeta(xsd_element.local_name.title(), (DataElement,), {})
        self.assertIn("attribute 'xsd_element' is required", str(ec.exception))

        with self.assertRaises(TypeError) as ec:
            DataBindingMeta(xsd_element.local_name.title(), (DataElement,), {'xsd_element': None})
        self.assertIn("None is not an XSD element", str(ec.exception))

    def test_element_binding(self):
        xsd_element = self.col_schema.elements['collection']
        xsd_element.binding = None

        try:
            binding_class = xsd_element.get_binding()
            self.assertEqual(binding_class.__name__, 'CollectionBinding')
            self.assertEqual(binding_class.__qualname__, 'CollectionBinding')
            self.assertIsNone(binding_class.__module__)
            self.assertIsNot(xsd_element.binding, DataElement)
            self.assertTrue(issubclass(xsd_element.binding, DataElement))
            self.assertIsInstance(xsd_element.binding, DataBindingMeta)
            self.assertIs(binding_class, xsd_element.binding)

            # regression tests for issue 300
            self.assertIs(binding_class, xsd_element.get_binding())
            self.assertIsNot(binding_class, xsd_element.get_binding(replace_existing=True))
        finally:
            xsd_element.binding = None

    def test_schema_bindings(self):
        schema = self.schema_class(self.col_xsd_filename)
        schema.maps.create_bindings()

        col_element_class = schema.elements['collection'].binding

        col_data = col_element_class.fromsource(self.col_xml_filename)

        self.assertEqual(len(list(col_data.iter())), len(list(self.col_xml_root.iter())))
        for elem, data_element in zip(self.col_xml_root.iter(), col_data.iter()):
            self.assertEqual(elem.tag, data_element.tag)
            self.assertIsInstance(data_element, DataElement)

        self.assertIsNone(
            etree_elements_assert_equal(col_data.encode(), self.col_xml_root, strict=False)
        )

        source = XMLResource(self.col_xml_filename, allow='local')
        col_data2 = col_element_class.fromsource(source, converter=self.converter)

        self.assertEqual(len(list(col_data.iter())), len(list(col_data2.iter())))
        for data_element, data_element2 in zip(col_data.iter(), col_data2.iter()):
            self.assertEqual(data_element.tag, data_element2.tag)

    def test_binding_instance(self):
        xsd_element = self.col_schema.elements['collection']
        xsd_element.binding = None

        try:
            binding_class = xsd_element.get_binding()
            collection_element = binding_class(tag=xsd_element.name)
            collection_element._encoder = xsd_element

            with self.assertRaises(ValueError) as ec:
                binding_class(tag=xsd_element.name,
                              xsd_element=self.col_schema.elements['person'])
            self.assertIn('already bound to another XSD element', str(ec.exception))

        finally:
            xsd_element.binding = None


class TestDataObjects11(TestDataObjects):
    schema_class = XMLSchema11


class TestDataBindings11(TestDataBindings):
    schema_class = XMLSchema11


if __name__ == '__main__':
    run_xmlschema_tests('data objects')
