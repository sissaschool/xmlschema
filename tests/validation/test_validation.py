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
import pathlib
import decimal
from textwrap import dedent
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

import xmlschema
from xmlschema import XMLSchema10, XMLSchemaValidationError, XMLSchemaStopValidation, \
    XMLSchemaChildrenValidationError

from xmlschema.validators import XMLSchema11
from xmlschema.testing import XsdValidatorTestCase
from xmlschema import DataElement, XMLResource
from xmlschema.converters import XMLSchemaConverter, JsonMLConverter, get_converter
from xmlschema.validators import ValidationContext

CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestValidationContext(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_get_converter(self):
        schema = XMLSchema10(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root"/>
            </xs:schema>"""), converter=JsonMLConverter)

        resource = XMLResource('<root xmlns:tns="http://example.test/ns1"/>')
        namespaces = {'tns': 'http://example.test/ns0'}
        obj = {'root': {'@xmlns:tns="http://example.test/ns1'}}

        kwargs = {
            'source': resource,
            'preserve_root': True,
            'namespaces': namespaces
        }
        converter = get_converter(**kwargs)
        self.assertIsInstance(converter, XMLSchemaConverter)
        self.assertIsNot(converter.namespaces, kwargs['namespaces'])
        self.assertDictEqual(
            kwargs['namespaces'], {'tns': 'http://example.test/ns0'}
        )
        self.assertDictEqual(
            converter.namespaces,
            {'tns': 'http://example.test/ns0', 'tns0': 'http://example.test/ns1'}
        )
        self.assertTrue(converter.preserve_root)
        self.assertIs(resource, kwargs['source'])

        converter = get_converter(JsonMLConverter, source=resource)
        self.assertIsInstance(converter, JsonMLConverter)

        kwargs = {'preserve_root': True, 'source': obj}
        converter = get_converter(**kwargs)
        self.assertIs(converter.source, obj)

        converter = schema.get_converter(source=resource)
        self.assertIsInstance(converter, JsonMLConverter)

        converter = schema.get_converter(XMLSchemaConverter, source=resource)
        self.assertIsInstance(converter, XMLSchemaConverter)
        self.assertNotIsInstance(converter, JsonMLConverter)

    def test_validation_error(self):
        elem = ElementTree.XML('<foo/>')
        context = ValidationContext(elem)

        with self.assertRaises(XMLSchemaValidationError):
            context.validation_error('strict', self.schema, 'Test error', obj=elem)

        self.assertIsInstance(context.validation_error('lax', self.schema, 'Test error'),
                              XMLSchemaValidationError)

        self.assertIsInstance(context.validation_error('lax', self.schema, 'Test error'),
                              XMLSchemaValidationError)

        self.assertIsInstance(context.validation_error('skip', self.schema, 'Test error'),
                              XMLSchemaValidationError)

        error = context.validation_error('lax', self.schema, 'Test error')
        self.assertIsNone(error.obj)
        self.assertEqual(context.validation_error('lax', self.schema, error, obj=10).obj, 10)


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

    def test_decode_to_objects(self):
        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xml')
        root = ElementTree.parse(xml_file).getroot()

        obj = self.schema.elements['vehicles'].to_objects(root)
        self.assertIsInstance(obj, DataElement)
        self.assertEqual(self.schema.elements['vehicles'].name, obj.tag)
        self.assertIs(obj.__class__, DataElement)

        obj = self.schema.elements['vehicles'].to_objects(root, with_bindings=True)
        self.assertIsInstance(obj, DataElement)
        self.assertEqual(self.schema.elements['vehicles'].name, obj.tag)
        self.assertIsNot(obj.__class__, DataElement)
        self.assertTrue(issubclass(obj.__class__, DataElement))
        self.assertEqual(obj.__class__.__name__, 'VehiclesBinding')

    def test_encode(self):
        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xml')
        obj = self.schema.decode(xml_file)

        root = self.schema.elements['vehicles'].encode(obj)
        self.assertEqual(root.tag, self.schema.elements['vehicles'].name)

        xml_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles-2_errors.xml')
        obj, errors = self.schema.decode(xml_file, validation='lax')

        root, errors2 = self.schema.elements['vehicles'].encode(obj, validation='lax')
        self.assertEqual(root.tag, self.schema.elements['vehicles'].name)


class TestValidation(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')

    def check_validity(self, xsd_component, data, expected, use_defaults=True):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.is_valid, data, use_defaults=use_defaults)
        elif expected:
            self.assertTrue(xsd_component.is_valid(data, use_defaults=use_defaults))
        else:
            self.assertFalse(xsd_component.is_valid(data, use_defaults=use_defaults))

    @unittest.skipIf(lxml_etree is None, "The lxml library is not available.")
    def test_lxml(self):
        xs = self.schema_class(self.casepath('examples/vehicles/vehicles.xsd'))
        xt1 = lxml_etree.parse(self.casepath('examples/vehicles/vehicles.xml'))
        xt2 = lxml_etree.parse(self.casepath('examples/vehicles/vehicles-1_error.xml'))
        self.assertTrue(xs.is_valid(xt1))
        self.assertFalse(xs.is_valid(xt2))
        self.assertTrue(xs.validate(xt1) is None)
        self.assertRaises(xmlschema.XMLSchemaValidationError, xs.validate, xt2)

    def test_document_validate_api(self):
        self.assertIsNone(xmlschema.validate(self.vh_xml_file))
        self.assertIsNone(xmlschema.validate(self.vh_xml_file, use_defaults=False))

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        self.assertRaises(XMLSchemaValidationError, xmlschema.validate, vh_2_file)

        try:
            xmlschema.validate(vh_2_file, namespaces={'vhx': "http://example.com/vehicles"})
        except XMLSchemaValidationError as err:
            path_line = str(err).splitlines()[-1]
        else:
            path_line = ''

        self.assertEqual('Path: /vhx:vehicles/vhx:cars', path_line)

        # Issue #80
        vh_2_xt = ElementTree.parse(vh_2_file)
        self.assertRaises(XMLSchemaValidationError, xmlschema.validate, vh_2_xt, self.vh_xsd_file)

        # Issue #145
        with open(self.vh_xml_file) as f:
            self.assertIsNone(xmlschema.validate(f, schema=self.vh_xsd_file))

    def test_document_validate_api_lazy(self):
        source = xmlschema.XMLResource(self.col_xml_file, lazy=False)
        namespaces = source.get_namespaces()
        source.root[0].clear()  # Drop internal elements
        source.root[1].clear()
        xsd_element = self.col_schema.elements['collection']

        self.assertRaises(XMLSchemaValidationError, xsd_element.decode, source.root,
                          namespaces=namespaces)

        for _ in xsd_element.iter_decode(
                source.root, 'strict', namespaces=namespaces, max_depth=1):
            del _

        self.assertIsNone(xmlschema.validate(self.col_xml_file, lazy=True))

    def test_document_is_valid_api(self):
        self.assertTrue(xmlschema.is_valid(self.vh_xml_file))
        self.assertTrue(xmlschema.is_valid(self.vh_xml_file, use_defaults=False))

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        self.assertFalse(xmlschema.is_valid(vh_2_file))

    def test_document_iter_errors_api(self):
        self.assertListEqual(list(xmlschema.iter_errors(self.vh_xml_file)), [])
        self.assertListEqual(list(xmlschema.iter_errors(self.vh_xml_file, use_defaults=False)), [])

        vh_2_file = self.casepath('examples/vehicles/vehicles-2_errors.xml')
        errors = list(xmlschema.iter_errors(vh_2_file))
        self.assertEqual(len(errors), 2)
        self.assertIsInstance(errors[0], XMLSchemaValidationError)
        self.assertIsInstance(errors[1], XMLSchemaValidationError)

    def test_max_depth_argument(self):
        schema = self.schema_class(self.col_xsd_file)
        invalid_col_xml_file = self.casepath('examples/collection/collection-1_error.xml')
        self.assertFalse(schema.is_valid(invalid_col_xml_file))
        self.assertTrue(schema.is_valid(invalid_col_xml_file, max_depth=1))
        self.assertTrue(schema.is_valid(invalid_col_xml_file, max_depth=2))
        self.assertFalse(schema.is_valid(invalid_col_xml_file, max_depth=3))

        root = ElementTree.parse(invalid_col_xml_file).getroot()
        xsd_element = schema.elements['collection']
        self.assertFalse(xsd_element.is_valid(root))
        self.assertTrue(xsd_element.is_valid(root, max_depth=1))
        self.assertTrue(xsd_element.is_valid(root, max_depth=2))
        self.assertFalse(xsd_element.is_valid(root, max_depth=3))

        # Need to provide namespace explicitly because the default namespace is '' in this case.
        xsd_element = schema.find('collection/object', namespaces={'': schema.target_namespace})

        self.assertIsNotNone(xsd_element)
        self.assertTrue(xsd_element.is_valid(root[0]))
        self.assertFalse(xsd_element.is_valid(root[1]))
        self.assertTrue(xsd_element.is_valid(root[1], max_depth=1))
        self.assertFalse(xsd_element.is_valid(root[1], max_depth=2))

    def test_extra_validator_argument(self):
        # Related to issue 227

        def bikes_validator(elem, xsd_element_):
            if elem.tag == '{http://example.com/vehicles}bike' and \
                    xsd_element_.name == elem.tag and \
                    elem.attrib['make'] != 'Harley-Davidson':
                raise XMLSchemaValidationError(xsd_element_, elem, 'not an Harley-Davidson')

        with self.assertRaises(XMLSchemaValidationError) as ec:
            self.vh_schema.validate(self.vh_xml_file, extra_validator=bikes_validator)
        self.assertIn('Reason: not an Harley-Davidson', str(ec.exception))

        root = ElementTree.parse(self.vh_xml_file).getroot()
        xsd_element = self.vh_schema.elements['vehicles']
        with self.assertRaises(XMLSchemaValidationError) as ec:
            xsd_element.validate(root, extra_validator=bikes_validator)
        self.assertIn('Reason: not an Harley-Davidson', str(ec.exception))

        with self.assertRaises(XMLSchemaValidationError) as ec:
            self.vh_schema.decode(self.vh_xml_file, extra_validator=bikes_validator)
        self.assertIn('Reason: not an Harley-Davidson', str(ec.exception))

        def bikes_validator(elem, xsd_element_):
            if elem.tag == '{http://example.com/vehicles}bike' and \
                    xsd_element_.name == elem.tag and \
                    elem.attrib['make'] != 'Harley-Davidson':
                yield XMLSchemaValidationError(xsd_element_, elem, 'not an Harley-Davidson')

        with self.assertRaises(XMLSchemaValidationError) as ec:
            self.vh_schema.validate(self.vh_xml_file, extra_validator=bikes_validator)
        self.assertIn('Reason: not an Harley-Davidson', str(ec.exception))

    def test_validation_hook_argument(self):
        resource = xmlschema.XMLResource(
            self.casepath('examples/collection/collection-1_error.xml')
        )

        with self.assertRaises(XMLSchemaValidationError) as ec:
            self.col_schema.validate(resource)
        self.assertIn('invalid literal for int() with base 10', str(ec.exception))

        def stop_validation(e, _xsd_element):
            if e is ec.exception.elem:
                raise XMLSchemaStopValidation()
            return False

        self.assertIsNone(self.col_schema.validate(resource, validation_hook=stop_validation))

        def skip_validation(e, _xsd_element):
            return e is ec.exception.elem

        self.assertIsNone(self.col_schema.validate(resource, validation_hook=skip_validation))

    def test_path_argument(self):
        schema = self.schema_class(self.casepath('examples/vehicles/vehicles.xsd'))

        self.assertTrue(schema.is_valid(self.vh_xml_file, path='*'))
        self.assertTrue(schema.is_valid(self.vh_xml_file, path='/vh:vehicles'))
        self.assertTrue(schema.is_valid(self.vh_xml_file, path='/vh:vehicles/vh:cars'))
        self.assertTrue(schema.is_valid(self.vh_xml_file, path='vh:cars'))
        self.assertTrue(schema.is_valid(self.vh_xml_file, path='/vh:vehicles/vh:cars/vh:car'))
        self.assertTrue(schema.is_valid(self.vh_xml_file, path='.//vh:car'))

        self.assertTrue(schema.is_valid(self.vh_xml_file, path='xs:vehicles'))
        self.assertFalse(
            schema.is_valid(self.vh_xml_file, path='xs:vehicles', allow_empty=False)
        )

    def test_schema_path_argument__issue_326(self):
        schema = self.schema_class(self.casepath('examples/vehicles/vehicles.xsd'))
        document = ElementTree.parse(self.vh_xml_file)

        entries = document.findall('vh:cars', {'vh': 'http://example.com/vehicles'})
        self.assertListEqual(entries, [document.getroot()[0]])
        for entry in entries:
            self.assertTrue(schema.is_valid(
                entry,
                schema_path='/vh:vehicles/vh:cars',
                namespaces={'vh': 'http://example.com/vehicles'}
            ))

        entries = document.findall('vh:cars/vh:car', {'vh': 'http://example.com/vehicles'})
        self.assertListEqual(entries, list(document.getroot()[0][:]))
        for entry in entries:
            self.assertTrue(schema.is_valid(
                entry,
                schema_path='.//vh:cars/vh:car',
                namespaces={'vh': 'http://example.com/vehicles'}
            ))

    def test_issue_064(self):
        self.check_validity(self.st_schema, '<name xmlns="ns"></name>', False)

    def test_issue_183(self):
        # Test for issue #183
        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:tns0="http://xmlschema.test/0"
                xmlns:tns1="http://xmlschema.test/1"
                xmlns="http://xmlschema.test/2"
                targetNamespace="http://xmlschema.test/0">

                <xs:element name="elem1" type="xs:string"/>
                <xs:element name="elem2" type="xs:string"/>
                <xs:element name="root" type="tns0:enumType"/>

                <xs:simpleType name="enumType">
                    <xs:restriction base="xs:QName">
                        <xs:enumeration value="tns0:elem1"/>
                        <xs:enumeration value="tns0:elem2"/>
                        <xs:enumeration value="tns1:elem1"/>
                        <xs:enumeration value="elem1"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>""")

        xml_data = '<tns0:root xmlns:tns0="http://xmlschema.test/0" >tns0:elem1</tns0:root>'
        self.check_validity(schema, xml_data, True)

        xml_data = '<ns0:root xmlns:ns0="http://xmlschema.test/0" >ns0:elem1</ns0:root>'
        self.check_validity(schema, xml_data, True)

        self.assertEqual(schema.decode(xml_data),
                         {'@xmlns:ns0': 'http://xmlschema.test/0', '$': 'ns0:elem1'})

        self.assertEqual(schema.decode(xml_data, strip_namespaces=True), 'ns0:elem1')

        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns="http://xmlschema.test/0"
                xmlns:tns1="http://xmlschema.test/1"
                xmlns:tns2="http://xmlschema.test/2"
                targetNamespace="http://xmlschema.test/0">

                <xs:element name="elem1" type="xs:string"/>
                <xs:element name="elem2" type="xs:string"/>
                <xs:element name="elem3" type="xs:string"/>
                <xs:element name="elem4" type="xs:string"/>

                <xs:element name="root" type="enumType"/>

                <xs:simpleType name="enumType">
                    <xs:restriction base="xs:QName">
                        <xs:enumeration value="elem1"/>
                        <xs:enumeration value="elem2"/>
                        <xs:enumeration value="tns1:other1"/>
                        <xs:enumeration value="elem3"/>
                        <xs:enumeration value="tns2:other2"/>
                        <xs:enumeration value="elem4"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:schema>""")

        xml_data = '<ns0:root xmlns:ns0="http://xmlschema.test/0">ns0:elem2</ns0:root>'
        self.check_validity(schema, xml_data, True)

    def test_issue_213(self):
        schema = self.schema_class(dedent("""\
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
          <xs:element name="amount" type="xs:decimal"/>
        </xs:schema>"""))

        xml1 = """<?xml version="1.0" encoding="UTF-8"?><amount>0.000000</amount>"""
        self.assertIsInstance(schema.decode(xml1), decimal.Decimal)

        xml2 = """<?xml version="1.0" encoding="UTF-8"?><amount>0.0000000</amount>"""
        self.assertIsInstance(schema.decode(xml2), decimal.Decimal)

    def test_issue_224__validate_malformed_file(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="root" type="xs:string"/>
            </xs:schema>"""))

        malformed_xml_file = self.casepath('resources/malformed.xml')

        with self.assertRaises(ElementTree.ParseError):
            schema.is_valid(malformed_xml_file)

    def test_issue_238__validate_bytes_strings(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="value" type="xs:int"/>
            </xs:schema>"""))

        self.assertTrue(schema.is_valid('<value>11</value>'))
        self.assertTrue(schema.is_valid(b'<value>\n11\n</value>'))

        with open(self.col_xml_file, 'rb') as fp:
            col_xml_data = fp.read()

        self.assertIsInstance(col_xml_data, bytes)
        self.assertTrue(self.col_schema.is_valid(col_xml_data))

    def test_issue_350__ignore_xsi_type_for_schema_validation(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

                <xs:element name="root" xsi:type="non-empty-string" />

                <xs:simpleType name="non-empty-string">
                  <xs:restriction base="xs:string">
                    <xs:minLength value="1" />
                  </xs:restriction>
                </xs:simpleType>

            </xs:schema>"""))

        self.assertTrue(schema.is_valid('<root></root>'))
        self.assertTrue(schema.is_valid('<root>foo</root>'))

        self.assertFalse(schema.is_valid(
            '<root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:type="non-empty-string"></root>'
        ))
        self.assertTrue(schema.is_valid(
            '<root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:type="non-empty-string">foo</root>'
        ))

    def test_issue_356__validate_empty_simple_elements(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

                <xs:element name="root1" type="emptyString" />
                <xs:element name="root2" type="emptyList" />
                <xs:element name="root3" type="emptiableUnion" />

                <xs:simpleType name="emptyString">
                    <xs:restriction base='xs:string'>
                      <xs:length value="0"/>
                    </xs:restriction>
                </xs:simpleType>

                <xs:simpleType name="emptyList">
                    <xs:list itemType="emptyString"/>
                </xs:simpleType>

                <xs:simpleType name="emptiableUnion">
                    <xs:union memberTypes="xs:int emptyString"/>
                </xs:simpleType>

            </xs:schema>"""))

        self.assertTrue(schema.is_valid('<root1></root1>'))
        self.assertFalse(schema.is_valid('<root1>foo</root1>'))

        self.assertTrue(schema.is_valid('<root2></root2>'))
        self.assertFalse(schema.is_valid('<root2>foo</root2>'))
        self.assertFalse(schema.is_valid('<root2>foo bar</root2>'))

        self.assertTrue(schema.is_valid('<root3>1</root3>'))
        self.assertTrue(schema.is_valid('<root3></root3>'))
        self.assertFalse(schema.is_valid('<root3>foo</root3>'))

    def test_element_form(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                targetNamespace="http://xmlschema.test/ns">

                <xs:element name="root">
                  <xs:complexType>
                    <xs:sequence>
                      <xs:element name="c1" minOccurs="0" />
                      <xs:element name="c2" minOccurs="0" form="qualified"/>
                      <xs:element name="c3" minOccurs="0" form="unqualified"/>
                    </xs:sequence>
                  </xs:complexType>
                </xs:element>

            </xs:schema>"""))

        self.assertFalse(schema.is_valid('<root></root>'))
        self.assertTrue(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"></root>')
        )
        self.assertTrue(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c1 xmlns=""/></root>'
        ))
        self.assertFalse(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c1/></root>'
        ))
        self.assertFalse(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c2 xmlns=""/></root>'
        ))
        self.assertTrue(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c2/></root>'
        ))
        self.assertTrue(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c3 xmlns=""/></root>'
        ))
        self.assertFalse(schema.is_valid(
            '<root xmlns="http://xmlschema.test/ns"><c3/></root>'
        ))

    def test_attribute_form(self):
        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                targetNamespace="http://xmlschema.test/ns">

                <xs:element name="root">
                  <xs:complexType>
                    <xs:attribute name="a1"/>
                    <xs:attribute name="a2" form="qualified"/>
                    <xs:attribute name="a3" form="unqualified"/>
                  </xs:complexType>
                </xs:element>

            </xs:schema>"""))

        self.assertTrue(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" a1="foo"/>'
        ))
        self.assertFalse(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" tns:a1="foo"/>'
        ))
        self.assertFalse(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" a2="foo"/>'
        ))
        self.assertTrue(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" tns:a2="foo"/>'
        ))
        self.assertTrue(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" a3="foo"/>'
        ))
        self.assertFalse(schema.is_valid(
            '<tns:root xmlns:tns="http://xmlschema.test/ns" tns:a3="foo"/>'
        ))

    def test_issue_363(self):
        schema = self.schema_class(self.casepath('issues/issue_363/issue_363.xsd'))

        self.assertTrue(schema.is_valid(self.casepath('issues/issue_363/issue_363.xml')))
        self.assertFalse(
            schema.is_valid(self.casepath('issues/issue_363/issue_363-invalid-1.xml')))
        self.assertFalse(
            schema.is_valid(self.casepath('issues/issue_363/issue_363-invalid-2.xml')))

        # Issue instance case (no default namespace and namespace mismatch)
        self.assertFalse(
            schema.is_valid(self.casepath('issues/issue_363/issue_363-invalid-3.xml')))
        self.assertFalse(
            schema.is_valid(self.casepath('issues/issue_363/issue_363-invalid-3.xml'),
                            namespaces={'': "http://xmlschema.test/ns"}))

    def test_dynamic_schema_load(self):
        xml_file = self.casepath('features/namespaces/dynamic-case1.xml')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            xmlschema.validate(xml_file, cls=self.schema_class)

        self.assertIn("schemaLocation declaration after namespace start",
                      str(ctx.exception))

    def test_issue_410(self):
        schema = self.schema_class(dedent("""\
            <?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:element name="muclient">
                <xs:complexType>
                  <xs:choice minOccurs="0" maxOccurs="unbounded">
                    <xs:element name="include"/>
                    <xs:choice>
                      <xs:element name="plugin"/>
                      <xs:element name="world"/>
                      <xs:element name="triggers"/>
                      <xs:element name="aliases"/>
                      <xs:element name="timers"/>
                      <xs:element name="macros"/>
                      <xs:element name="variables"/>
                      <xs:element name="colours"/>
                      <xs:element name="keypad"/>
                      <xs:element name="printing"/>
                    </xs:choice>
                  </xs:choice>
                </xs:complexType>
              </xs:element>
            </xs:schema>"""))

        xml_data = '<muclient></muclient>'
        self.check_validity(schema, xml_data, True)

        xml_data = '<muclient><include/></muclient>'
        self.check_validity(schema, xml_data, True)

        xml_data = '<muclient><world/><include/></muclient>'
        self.check_validity(schema, xml_data, True)


class TestValidation11(TestValidation):
    schema_class = XMLSchema11

    def test_default_attributes(self):
        xs = self.schema_class(self.casepath('features/attributes/default_attributes.xsd'))
        self.assertTrue(xs.is_valid("<tree xmlns='ns'>\n"
                                    "   <node node-id='1'>alpha</node>\n"
                                    "   <node node-id='2' colour='red'>beta</node>\n"
                                    "</tree>"))
        self.assertFalse(xs.is_valid("<tree xmlns='ns'>\n"
                                     "   <node>alpha</node>\n"  # Misses required attribute
                                     "   <node node-id='2' colour='red'>beta</node>\n"
                                     "</tree>"))

    def test_issue_171(self):
        # First schema has an assert with a naive check
        schema = self.schema_class(self.casepath('issues/issue_171/issue_171.xsd'))
        self.check_validity(schema, '<tag name="test" abc="10" def="0"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10" def="1"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10"/>', True)

        # Same schema with a more reliable assert expression
        schema = self.schema_class(self.casepath('issues/issue_171/issue_171b.xsd'))
        self.check_validity(schema, '<tag name="test" abc="10" def="0"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10" def="1"/>', False)
        self.check_validity(schema, '<tag name="test" abc="10"/>', True)

        # Another schema with a simple assert expression to test that EBV of abc/def='0' is True
        schema = self.schema_class(self.casepath('issues/issue_171/issue_171c.xsd'))
        self.check_validity(schema, '<tag name="test" abc="0" def="1"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1" def="0"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1" def="1"/>', True)
        self.check_validity(schema, '<tag name="test" abc="0" def="0"/>', True)
        self.check_validity(schema, '<tag name="test" abc="1"/>', False)
        self.check_validity(schema, '<tag name="test" def="1"/>', False)

    def test_optional_errors_collector(self):
        schema = self.schema_class(self.col_xsd_file)
        invalid_col_xml_file = self.casepath('examples/collection/collection-1_error.xml')

        errors = []
        chunks = list(schema.iter_decode(invalid_col_xml_file, errors=errors))
        self.assertTrue(len(chunks), 2)
        self.assertIsInstance(chunks[0], XMLSchemaValidationError)
        self.assertTrue(len(errors), 1)
        self.assertIs(chunks[0], errors[0])

    def test_dynamic_schema_load(self):
        xml_file = self.casepath('features/namespaces/dynamic-case1.xml')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            xmlschema.validate(xml_file, cls=self.schema_class)

        self.assertIn("global xs:element with name='elem1' is already loaded",
                      str(ctx.exception))

        xml_file = self.casepath('features/namespaces/dynamic-case1-2.xml')

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            xmlschema.validate(xml_file, cls=self.schema_class)

        self.assertIn("change the assessment outcome of previous items",
                      str(ctx.exception))

    def test_incorrect_validation_errors__issue_372(self):
        schema = self.schema_class(self.casepath('issues/issue_372/issue_372.xsd'))

        xml_file = self.casepath('issues/issue_372/issue_372-1.xml')
        errors = list(schema.iter_errors(xml_file))
        self.assertEqual(len(errors), 1)

        err = errors[0]
        self.assertIsInstance(err, XMLSchemaChildrenValidationError)
        self.assertEqual(err.invalid_child, err.elem[err.index])
        self.assertEqual(err.invalid_tag, 'invalidTag')

        xml_file = self.casepath('issues/issue_372/issue_372-2.xml')
        errors = list(schema.iter_errors(xml_file))
        self.assertEqual(len(errors), 1)

        err = errors[0]
        self.assertIsInstance(err, XMLSchemaChildrenValidationError)
        self.assertEqual(err.invalid_child, err.elem[err.index])
        self.assertEqual(err.invalid_tag, 'optionalSecondChildTag')

    def test_invalid_default_open_content__issue_397(self):
        schema = self.schema_class('''\
        <xs:schema elementFormDefault="qualified" attributeFormDefault="unqualified"
            vc:minVersion="1.1"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:vc="http://www.w3.org/2007/XMLSchema-versioning" xmlns="urn:us:mil:nga:ntb:soddxa"
            targetNamespace="urn:us:mil:nga:ntb:soddxa">
            <xs:defaultOpenContent mode="interleave">
                <xs:any />
            </xs:defaultOpenContent>
            <xs:complexType name="SecurityDataType">
                <xs:sequence>
                    <xs:element name="smRestrictedCollection" type="xs:boolean" minOccurs="0" />
                    <xs:element name="accmClassification" type="xs:string" minOccurs="0" />
                </xs:sequence>
            </xs:complexType>

            <xs:element name="spaceObjectDescriptionData">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="securityData" type="SecurityDataType" />
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
        </xs:schema>''')

        self.assertTrue(schema.is_valid('''\
            <spaceObjectDescriptionData xmlns="urn:us:mil:nga:ntb:soddxa">
                <securityData>
                    <smRestrictedCollection>false</smRestrictedCollection>
                    <accmClassification>text</accmClassification>
                </securityData>
            </spaceObjectDescriptionData>'''))

        self.assertTrue(schema.is_valid('''
            <spaceObjectDescriptionData xmlns="urn:us:mil:nga:ntb:soddxa">
                <securityData>
                    <accmClassification>text</accmClassification>
                </securityData>
            </spaceObjectDescriptionData>
        '''))

    def test_all_model_with_emptiable_particles(self):
        schema = self.schema_class('''
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="doc">
              <xs:complexType>
                <xs:all>
                  <xs:element name="a" maxOccurs="2"/>
                  <xs:element name="b" minOccurs="0"/>
                  <xs:element name="c" minOccurs="0"/>
                </xs:all>
              </xs:complexType>
            </xs:element>
        </xs:schema>
        ''')

        with self.assertRaises(XMLSchemaValidationError) as ec:
            schema.validate('<doc>\n<c/>\n<b/>\n</doc>')

        self.assertEqual(
            ec.exception.reason,
            "The content of element 'doc' is not complete. Tag 'a' expected."
        )

    def test_nested_all_groups_and_wildcard(self):
        schema = self.schema_class('''
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

        <xs:group name="group1">
          <xs:all>
            <xs:element name="a" maxOccurs="2"/>
            <xs:element name="b" minOccurs="0"/>
            <xs:element name="c" minOccurs="0"/>
          </xs:all>
        </xs:group>

        <xs:element name="doc">
          <xs:complexType>
            <xs:all>
              <xs:group ref="group1"/>
              <xs:any namespace="http://open.com/" processContents="lax"
                  minOccurs="0" maxOccurs="unbounded"/>
            </xs:all>
              </xs:complexType>
            </xs:element>

            </xs:schema>''')

        with self.assertRaises(XMLSchemaValidationError) as ec:
            schema.validate('''
                <doc>
                  <c/>
                  <b/>
                  <extra xmlns="http://open.com/">42</extra>
                  <extra xmlns="http://open.com/">97</extra>
                </doc>
                ''')

        self.assertEqual(
            ec.exception.reason,
            "The content of element 'doc' is not complete. Tag 'a' expected."
        )


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('validation')
