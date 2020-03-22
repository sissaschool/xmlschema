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
import platform
import re
import xml.etree.ElementTree as ElementTree

from xmlschema.compat import ordered_dict_class
from xmlschema.testing import print_test_header
from xmlschema.validators import XsdValidator, XsdComponent, XMLSchema10, XMLSchema11, \
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaDecodeError, XMLSchemaEncodeError
from xmlschema.qnames import XSD_ELEMENT, XSD_ANNOTATION
from xmlschema.namespaces import XSD_NAMESPACE

CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestXsdValidator(unittest.TestCase):

    def test_initialization(self):
        validator = XsdValidator()
        self.assertEqual(validator.validation, 'strict')

        validator = XsdValidator(validation='lax')
        self.assertEqual(validator.validation, 'lax')
        self.assertListEqual(validator.errors, [])

    def test_string_representation(self):
        validator = XsdValidator()
        tmpl = '<xmlschema.validators.xsdbase.XsdValidator object at {}>'
        string_repr = str(validator)
        if platform.python_implementation() == 'PyPy' or platform.system() == 'Windows':
            string_repr = re.sub(r'0x[0]+', '0x', string_repr, 1)
        self.assertEqual(string_repr.lower(), tmpl.format(hex(id(validator))).lower())

    def test_parse_error(self):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        schema = XMLSchema10(xsd_file)

        with self.assertRaises(TypeError):
            schema.parse_error("test error", elem=(1, 2))
        with self.assertRaises(TypeError):
            schema.parse_error(b"test error")

        with self.assertRaises(XMLSchemaParseError):
            schema.parse_error("test error")

        self.assertEqual(len(schema.errors), 0)
        schema.parse_error("test error", validation='skip')
        self.assertEqual(len(schema.errors), 0)
        schema.parse_error("test error", validation='lax')
        self.assertEqual(len(schema.errors), 1)
        schema.parse_error(XMLSchemaParseError(schema, "test error"), validation='lax')
        self.assertEqual(len(schema.errors), 2)
        schema.parse_error(ValueError("wrong value"), validation='lax')
        self.assertEqual(len(schema.errors), 3)
        schema.parse_error(ValueError("'invalid value'"), validation='lax')
        self.assertEqual(len(schema.errors), 4)
        self.assertEqual(schema.errors[-1].message, "invalid value")

    def test_copy(self):
        validator = XsdValidator(validation='lax')
        validator.parse_error(ValueError("test error"))
        self.assertEqual(len(validator.errors), 1)
        self.assertListEqual(validator.copy().errors, validator.errors)

    def test_valid_schema(self):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')

        schema = XMLSchema10(xsd_file, build=False)
        self.assertEqual(schema.validity, 'notKnown')
        self.assertEqual(len(schema.all_errors), 0)

        schema.build()
        self.assertEqual(schema.validity, 'valid')
        self.assertEqual(len(schema.all_errors), 0)

    def test_invalid_schema(self):
        xsd_text = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="root" minOccurs="0"/>
        </xs:schema>"""

        with self.assertRaises(XMLSchemaParseError):
            XMLSchema10(xsd_text)

        schema = XMLSchema10(xsd_text, validation='lax')
        self.assertEqual(schema.validity, 'invalid')
        self.assertEqual(len(schema.all_errors), 2)  # One by meta-schema check

        schema = XMLSchema10(xsd_text, validation='skip')
        self.assertEqual(schema.validity, 'notKnown')
        self.assertEqual(len(schema.all_errors), 0)

    def test_parse_xpath_default_namespace(self):
        xsd_text = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="root"/>
        </xs:schema>"""

        schema = XMLSchema11(xsd_text)
        elem = ElementTree.Element('A')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##local')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##defaultNamespace')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##targetNamespace')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')

        xsd_text = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns="tns0" targetNamespace="tns0">
            <xs:element name="root"/>
        </xs:schema>"""

        schema = XMLSchema11(xsd_text, validation='lax')
        elem = ElementTree.Element('A')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##local')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##defaultNamespace')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), 'tns0')
        elem = ElementTree.Element('A', xpathDefaultNamespace='##targetNamespace')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), 'tns0')

        elem = ElementTree.Element('A', xpathDefaultNamespace='tns1')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), 'tns1')

        elem = ElementTree.Element('A', xpathDefaultNamespace='tns0 tns1')
        self.assertEqual(schema._parse_xpath_default_namespace(elem), '')
        self.assertIn('tns0 tns1', schema.errors[-1].message)


class TestXsdComponent(unittest.TestCase):

    class FakeElement(XsdComponent):
        @property
        def built(self):
            return super().built

        _ADMITTED_TAGS = (XSD_ELEMENT,)

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_initialization(self):
        with self.assertRaises(TypeError):
            XsdComponent(elem=None, schema=self.schema)

        with self.assertRaises(ValueError):
            XsdComponent(elem=ElementTree.Element('A'), schema=self.schema)

    def test_schema_set(self):
        other_schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="root"/>
        </xs:schema>""")

        with self.assertRaises(ValueError):
            other_schema.elements['root'].schema = self.schema

    def test_is_override(self):
        self.assertFalse(self.schema.elements['cars'].is_override())
        self.assertFalse(self.schema.elements['cars'].type.content_type[0].is_override())

    def test_representation(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="node">
                <xs:complexType>
                    <xs:simpleContent>
                        <xs:extension base="xs:string">
                            <xs:attribute ref="slot"/>
                        </xs:extension> 
                    </xs:simpleContent>
                </xs:complexType>
            </xs:element>
            <xs:attribute name="slot" type="xs:string"/>
        </xs:schema>""")

        self.assertEqual(repr(schema.elements['node']), "XsdElement(name='node', occurs=[1, 1])")
        self.assertEqual(repr(schema.attributes['slot']), "XsdAttribute(name='slot')")
        self.assertEqual(repr(schema.elements['node'].type.attributes['slot']),
                         "XsdAttribute(ref='slot')")

    def test_parse_reference(self):
        group = self.schema.elements['vehicles'].type.content_type

        name = '{%s}motorbikes' % XSD_NAMESPACE
        elem = ElementTree.Element(XSD_ELEMENT, name=name)
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        self.assertIsNone(xsd_element._parse_reference())

        elem = ElementTree.Element(XSD_ELEMENT, name=name, ref=name)
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()

        elem = ElementTree.Element(XSD_ELEMENT, ref=name)
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()

        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        xsd_element._parse_reference()

        elem = ElementTree.Element(XSD_ELEMENT, ref='tns0:motorbikes')
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()

        elem = ElementTree.Element(XSD_ELEMENT, ref=name)
        elem.append(ElementTree.Element('child'))
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()

        elem = ElementTree.Element(XSD_ELEMENT)
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_reference()

    def test_parse_boolean_attribute(self):
        name = '{%s}motorbikes' % self.schema.target_namespace
        elem = ElementTree.Element(XSD_ELEMENT, name=name, flag='true')
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)

        self.assertIsNone(xsd_element._parse_boolean_attribute('cond'))
        self.assertTrue(xsd_element._parse_boolean_attribute('flag'))
        xsd_element.elem = ElementTree.Element(XSD_ELEMENT, name=name, flag='1')
        self.assertTrue(xsd_element._parse_boolean_attribute('flag'))
        xsd_element.elem = ElementTree.Element(XSD_ELEMENT, name=name, flag='false')
        self.assertFalse(xsd_element._parse_boolean_attribute('flag'))
        xsd_element.elem = ElementTree.Element(XSD_ELEMENT, name=name, flag='0')
        self.assertFalse(xsd_element._parse_boolean_attribute('flag'))

        xsd_element.elem = ElementTree.Element(XSD_ELEMENT, name=name, flag='False')
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_boolean_attribute('flag')

    def test_parse_child_component(self):
        name = '{%s}motorbikes' % self.schema.target_namespace
        elem = ElementTree.Element(XSD_ELEMENT, name=name)
        elem.append(ElementTree.Element(XSD_ANNOTATION))
        elem.append(ElementTree.Element('child1'))
        elem.append(ElementTree.Element('child2'))
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)

        self.assertEqual(xsd_element._parse_child_component(elem, strict=False), elem[1])
        with self.assertRaises(XMLSchemaParseError):
            xsd_element._parse_child_component(elem)

    def test_parse_target_namespace(self):
        name = '{%s}motorbikes' % self.schema.target_namespace

        elem = ElementTree.Element(XSD_ELEMENT, name=name, targetNamespace='tns0')
        group = self.schema.elements['vehicles'].type.content_type

        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_target_namespace()
        self.assertIn("must have the same namespace", ctx.exception.message)

        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        self.assertIsNone(xsd_element._parse_target_namespace())
        self.assertEqual(xsd_element.name, '{tns0}motorbikes')

        elem = ElementTree.Element(XSD_ELEMENT, targetNamespace='tns0')
        xsd_element = self.FakeElement(elem=elem, name=None, schema=self.schema, parent=group)
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_target_namespace()
        self.assertIn("attribute 'name' must be present", ctx.exception.message)

        elem = ElementTree.Element(XSD_ELEMENT, name=name, form='qualified', targetNamespace='tns0')
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=group)
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_target_namespace()
        self.assertIn("attribute 'form' must be absent", ctx.exception.message)

        elem = ElementTree.Element(
            XSD_ELEMENT, name='motobikes', targetNamespace=self.schema.target_namespace
        )
        xsd_element = self.FakeElement(elem, self.schema, parent=group, name=name)
        self.assertIsNone(xsd_element._parse_target_namespace())
        self.assertEqual(xsd_element.name, name)

        xsd_attribute = self.schema.types['vehicleType'].attributes['model']
        xsd_attribute.elem.attrib['targetNamespace'] = 'tns0'
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_attribute._parse_target_namespace()
        self.assertIn("a declaration contained in a global complexType must "
                      "have the same namespace", ctx.exception.message)
        del xsd_attribute.elem.attrib['targetNamespace']

        with self.assertRaises(XMLSchemaParseError) as ctx:
            XMLSchema11("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root" targetNamespace=""/>
            </xs:schema>""")
        self.assertIn("use of attribute 'targetNamespace' is prohibited", ctx.exception.message)

        schema = XMLSchema11("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence>
                            <xs:element name="node" targetNamespace=""/> 
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:schema>""")
        self.assertEqual(schema.elements['root'].type.content_type[0].name, 'node')

    def test_id_property(self):
        name = '{%s}motorbikes' % self.schema.target_namespace
        elem = ElementTree.Element(XSD_ELEMENT, name=name, id='1999')
        xsd_element = self.FakeElement(elem=elem, name=name, schema=self.schema, parent=None)
        self.assertEqual(xsd_element.id, '1999')

    def test_validation_attempted(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:notation name="content" public="text/html"/>
                     <xs:element name="root"/>
                 </xs:schema>""")

        self.assertEqual(schema.notations['content'].validation_attempted, 'full')

    def test_name_matching(self):
        name = '{%s}motorbikes' % self.schema.target_namespace
        elem = ElementTree.Element(XSD_ELEMENT, name=name)
        xsd_element = self.FakeElement(elem, self.schema, parent=None, name=name)

        self.assertFalse(xsd_element.is_matching('motorbikes'))
        self.assertFalse(xsd_element.is_matching(''))
        self.assertTrue(
            xsd_element.is_matching('motorbikes', default_namespace=self.schema.target_namespace)
        )
        self.assertFalse(xsd_element.is_matching('{%s}bikes' % self.schema.target_namespace))
        self.assertTrue(xsd_element.is_matching(name))
        self.assertIs(xsd_element.match(name), xsd_element)

    def test_get_global(self):
        xsd_element = self.schema.elements['vehicles']
        self.assertIs(xsd_element.get_global(), xsd_element)

        xsd_type = self.schema.types['vehicleType']
        self.assertIs(xsd_type.attributes['model'].get_global(), xsd_type)

    def test_get_parent_type(self):
        xsd_type = self.schema.types['vehicleType']
        self.assertIs(xsd_type.attributes['model'].get_parent_type(), xsd_type)
        self.assertIsNone(xsd_type.get_parent_type())

    def test_iter_components(self):
        name = '{%s}motorbikes' % self.schema.target_namespace
        elem = ElementTree.Element(XSD_ELEMENT, name=name)
        xsd_element = self.FakeElement(elem, self.schema, parent=None, name=name)

        self.assertListEqual(list(xsd_element.iter_components()), [xsd_element])
        self.assertListEqual(list(xsd_element.iter_components(str)), [])

    def test_iter_ancestors(self):
        xsd_element = self.schema.elements['cars'].type.content_type[0]
        ancestors = [e for e in xsd_element.iter_ancestors()]
        self.assertListEqual(ancestors, [
            self.schema.elements['cars'].type.content_type,
            self.schema.elements['cars'].type,
            self.schema.elements['cars'],
        ])
        self.assertListEqual(list(xsd_element.iter_ancestors(str)), [])

    def test_tostring(self):
        cars_dump = str(self.schema.elements['cars'].tostring())
        self.assertEqual(len(cars_dump.split('\n')), 7)
        self.assertIn('name="car" type="vh:vehicleType"', cars_dump)
        self.assertIsInstance(ElementTree.XML(cars_dump), ElementTree.Element)

    def test_annotation(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:element name="root">
                         <xs:annotation/>
                     </xs:element>
                 </xs:schema>""")
        self.assertTrue(schema.elements['root'].annotation.built)

        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:element name="root">
                         <xs:annotation>
                             <xs:appinfo/>
                             <xs:documentation/>
                         </xs:annotation>
                     </xs:element>
                 </xs:schema>""")
        self.assertEqual(len(schema.all_errors), 0)

        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:element name="root">
                         <xs:annotation>
                             <xs:documentation wrong="abc" source=""/>
                             <xs:appinfo wrong="10" source=""/>
                             <xs:element name="wrong"/>
                         </xs:annotation>
                     </xs:element>
                 </xs:schema>""", validation='lax')
        self.assertEqual(len(schema.all_errors), 3)


class TestXsdType(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

                     <xs:simpleType name="emptyType">
                         <xs:restriction base="xs:string">
                             <xs:length value="0"/>
                         </xs:restriction>
                     </xs:simpleType>

                     <xs:simpleType name="idType">
                         <xs:restriction base="xs:ID"/>
                     </xs:simpleType>
                     
                     <xs:simpleType name="fooType">
                         <xs:restriction base="xs:string"/>
                     </xs:simpleType>

                     <xs:simpleType name="fooListType">
                         <xs:list itemType="xs:string"/>
                     </xs:simpleType>
                     
                     <xs:complexType name="barType">
                         <xs:sequence>
                             <xs:element name="node"/>
                         </xs:sequence>
                     </xs:complexType>        

                     <xs:complexType name="barExtType">
                         <xs:complexContent>
                             <xs:extension base="barType">
                                 <xs:sequence>
                                     <xs:element name="node"/>
                                 </xs:sequence>
                             </xs:extension>
                         </xs:complexContent>
                     </xs:complexType>        

                     <xs:complexType name="mixedType" mixed="true">
                         <xs:sequence>
                             <xs:element name="node" type="xs:string"/>
                         </xs:sequence>
                     </xs:complexType>        

                 </xs:schema>""")

    def test_content_type_label(self):
        self.assertEqual(self.schema.types['emptyType'].content_type_label, 'empty')
        self.assertEqual(self.schema.types['fooType'].content_type_label, 'simple')
        self.assertEqual(self.schema.types['barType'].content_type_label, 'element-only')
        self.assertEqual(self.schema.types['mixedType'].content_type_label, 'mixed')

    def test_root_type(self):
        self.assertIs(self.schema.types['fooType'].root_type,
                      self.schema.meta_schema.types['string'])
        self.assertIs(self.schema.types['fooListType'].root_type,
                      self.schema.meta_schema.types['string'])
        self.assertIs(self.schema.types['mixedType'].root_type,
                      self.schema.types['mixedType'])
        self.assertIs(self.schema.types['barExtType'].root_type,
                      self.schema.types['barType'])

    def test_is_atomic(self):
        self.assertFalse(self.schema.types['barType'].is_atomic())

    def test_is_datetime(self):
        self.assertFalse(self.schema.types['barType'].is_datetime())

    def test_is_dynamic_consistent(self):
        self.assertFalse(self.schema.types['fooType'].is_dynamic_consistent(
            self.schema.types['fooListType']
        ))
        self.assertTrue(self.schema.types['fooType'].is_dynamic_consistent(
            self.schema.types['fooType']
        ))

    def test_is_key(self):
        self.assertFalse(self.schema.types['fooType'].is_key())
        self.assertTrue(self.schema.types['idType'].is_key())

    def test_is_extension(self):
        self.assertFalse(self.schema.types['fooType'].is_extension())
        self.assertTrue(self.schema.types['barExtType'].is_extension())

    def test_is_restriction(self):
        self.assertTrue(self.schema.types['fooType'].is_restriction())
        self.assertFalse(self.schema.types['barExtType'].is_restriction())


class TestValidationMixin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_validate(self):
        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xml')
        root = ElementTree.parse(xml_file).getroot()
        self.assertIsNone(self.schema.elements['vehicles'].validate(root))

        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles-1_error.xml')
        root = ElementTree.parse(xml_file).getroot()
        with self.assertRaises(XMLSchemaValidationError):
            self.schema.elements['vehicles'].validate(root)

    def test_decode(self):
        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xml')
        root = ElementTree.parse(xml_file).getroot()

        obj = self.schema.elements['vehicles'].decode(root)
        self.assertIsInstance(obj, dict)
        self.assertIn(self.schema.elements['cars'].name, obj)
        self.assertIn(self.schema.elements['bikes'].name, obj)

        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles-2_errors.xml')
        root = ElementTree.parse(xml_file).getroot()

        obj, errors = self.schema.elements['vehicles'].decode(root, validation='lax')
        self.assertIsInstance(obj, dict)
        self.assertIn(self.schema.elements['cars'].name, obj)
        self.assertIn(self.schema.elements['bikes'].name, obj)
        self.assertEqual(len(errors), 2)

    def test_encode(self):
        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xml')
        obj = self.schema.decode(xml_file, dict_class=ordered_dict_class)

        root = self.schema.elements['vehicles'].encode(obj)
        self.assertEqual(root.tag, self.schema.elements['vehicles'].name)

        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles-2_errors.xml')
        obj, errors = self.schema.decode(xml_file, validation='lax')

        root, errors2 = self.schema.elements['vehicles'].encode(obj, validation='lax')
        self.assertEqual(root.tag, self.schema.elements['vehicles'].name)

    def test_validation_error(self):
        with self.assertRaises(XMLSchemaValidationError):
            self.schema.validation_error('strict', 'Test error')

        self.assertIsInstance(self.schema.validation_error('lax', 'Test error'),
                              XMLSchemaValidationError)

        self.assertIsInstance(self.schema.validation_error('skip', 'Test error'),
                              XMLSchemaValidationError)

    def test_decode_error(self):
        with self.assertRaises(XMLSchemaDecodeError):
            self.schema.decode_error('strict', 'alpha', int, 'Test error')

        self.assertIsInstance(self.schema.decode_error('lax', 'alpha', int, 'Test error'),
                              XMLSchemaDecodeError)

        self.assertIsInstance(self.schema.decode_error('skip', 'alpha', int, 'Test error'),
                              XMLSchemaDecodeError)

    def test_encode_error(self):
        with self.assertRaises(XMLSchemaEncodeError):
            self.schema.encode_error('strict', 'alpha', str, 'Test error')

        self.assertIsInstance(self.schema.encode_error('lax', 'alpha', str, 'Test error'),
                              XMLSchemaEncodeError)

        self.assertIsInstance(self.schema.encode_error('skip', 'alpha', str, 'Test error'),
                              XMLSchemaEncodeError)


class TestParticleMixin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_occurs_property(self):
        self.assertListEqual(self.schema.elements['cars'].occurs, [1, 1])
        self.assertListEqual(self.schema.elements['cars'].type.content_type[0].occurs, [0, None])

    def test_effective_min_occurs_property(self):
        self.assertEqual(self.schema.elements['cars'].effective_min_occurs, 1)
        self.assertEqual(self.schema.elements['cars'].type.content_type[0].effective_min_occurs, 0)

    def test_effective_max_occurs_property(self):
        self.assertEqual(self.schema.elements['cars'].effective_max_occurs, 1)
        self.assertIsNone(self.schema.elements['cars'].type.content_type[0].effective_max_occurs)

    def test_is_emptiable(self):
        self.assertFalse(self.schema.elements['cars'].is_emptiable())
        self.assertTrue(self.schema.elements['cars'].type.content_type[0].is_emptiable())

    def test_is_empty(self):
        self.assertFalse(self.schema.elements['cars'].is_empty())

    def test_is_single(self):
        self.assertTrue(self.schema.elements['cars'].is_single())
        self.assertFalse(self.schema.elements['cars'].type.content_type[0].is_single())

    def test_is_ambiguous(self):
        self.assertFalse(self.schema.elements['cars'].is_ambiguous())
        self.assertTrue(self.schema.elements['cars'].type.content_type[0].is_ambiguous())

    def test_is_univocal(self):
        self.assertTrue(self.schema.elements['cars'].is_univocal())
        self.assertFalse(self.schema.elements['cars'].type.content_type[0].is_univocal())

    def test_is_missing(self):
        self.assertTrue(self.schema.elements['cars'].is_missing(0))
        self.assertFalse(self.schema.elements['cars'].is_missing(1))
        self.assertFalse(self.schema.elements['cars'].is_missing(2))
        self.assertFalse(self.schema.elements['cars'].type.content_type[0].is_missing(0))

    def test_is_over(self):
        self.assertFalse(self.schema.elements['cars'].is_over(0))
        self.assertTrue(self.schema.elements['cars'].is_over(1))
        self.assertFalse(self.schema.elements['cars'].type.content_type[0].is_over(1000))

    def test_has_occurs_restriction(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:complexType name="barType">
                         <xs:sequence>
                             <xs:element name="node0" />
                             <xs:element name="node1" minOccurs="0"/>
                             <xs:element name="node2" minOccurs="0" maxOccurs="unbounded"/>
                             <xs:element name="node3" minOccurs="2" maxOccurs="unbounded"/>
                             <xs:element name="node4" minOccurs="2" maxOccurs="10"/>
                             <xs:element name="node5" minOccurs="4" maxOccurs="10"/>
                             <xs:element name="node6" minOccurs="4" maxOccurs="9"/>
                             <xs:element name="node7" minOccurs="1" maxOccurs="9"/>
                             <xs:element name="node8" minOccurs="3" maxOccurs="11"/>
                         </xs:sequence>
                     </xs:complexType>                             
                 </xs:schema>""")

        xsd_group = schema.types['barType'].content_type

        for k in range(9):
            self.assertTrue(
                xsd_group[k].has_occurs_restriction(xsd_group[k]), msg="Fail for node%d" % k
            )

        self.assertTrue(xsd_group[0].has_occurs_restriction(xsd_group[1]))
        self.assertFalse(xsd_group[1].has_occurs_restriction(xsd_group[0]))
        self.assertTrue(xsd_group[3].has_occurs_restriction(xsd_group[2]))
        self.assertFalse(xsd_group[2].has_occurs_restriction(xsd_group[1]))
        self.assertFalse(xsd_group[2].has_occurs_restriction(xsd_group[3]))
        self.assertTrue(xsd_group[4].has_occurs_restriction(xsd_group[3]))
        self.assertTrue(xsd_group[4].has_occurs_restriction(xsd_group[2]))
        self.assertFalse(xsd_group[4].has_occurs_restriction(xsd_group[5]))
        self.assertTrue(xsd_group[5].has_occurs_restriction(xsd_group[4]))
        self.assertTrue(xsd_group[6].has_occurs_restriction(xsd_group[5]))
        self.assertFalse(xsd_group[5].has_occurs_restriction(xsd_group[6]))
        self.assertFalse(xsd_group[7].has_occurs_restriction(xsd_group[6]))
        self.assertFalse(xsd_group[5].has_occurs_restriction(xsd_group[7]))
        self.assertTrue(xsd_group[6].has_occurs_restriction(xsd_group[7]))
        self.assertFalse(xsd_group[7].has_occurs_restriction(xsd_group[8]))
        self.assertFalse(xsd_group[8].has_occurs_restriction(xsd_group[7]))

    def test_parse_particle(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:element name="root"/>
                 </xs:schema>""")
        xsd_element = schema.elements['root']

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='1')
        xsd_element._parse_particle(elem)

        elem = ElementTree.Element('root', minOccurs='2', maxOccurs='1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs must be 'unbounded' or greater than minOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='-1', maxOccurs='1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs value must be a non negative integer", str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='-1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs must be 'unbounded' or greater than minOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='none')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs value must be a non negative integer or 'unbounded'",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='2')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs must be lesser or equal than maxOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='none')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs value is not an integer value",
                      str(ctx.exception))


if __name__ == '__main__':
    print_test_header()
    unittest.main()
