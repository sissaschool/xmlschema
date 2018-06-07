#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests concerning the encoding to XML data with the 'xmlschema' package.
"""
import unittest
import os
import sys
from collections import OrderedDict
from xml.etree import ElementTree as _ElementTree


try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    test_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_base_dir = os.path.dirname(os.path.dirname(test_dir))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.tests import XMLSchemaTestCase
from xmlschema.etree import (
    etree_element, etree_tostring, etree_iselement, etree_fromstring, etree_parse,
    etree_get_namespaces, etree_elements_equal
)
from xmlschema.qnames import local_name
from xmlschema import XMLSchemaEncodeError, XMLSchemaValidationError


def make_encoding_test_function(xml_file, schema_class, expected_errors=0, inspect=False,
                                locations=None, defuse='defuse'):
    def test_decoding(self):
        schema, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
        xs = schema_class(schema, validation='lax', locations=_locations, defuse=defuse)
        errors = []
        chunks = []
        for obj in xs.iter_decode(xml_file):
            if isinstance(obj, (xmlschema.XMLSchemaDecodeError, xmlschema.XMLSchemaValidationError)):
                errors.append(obj)
            else:
                chunks.append(obj)
        if len(errors) != expected_errors:
            import pdb
            pdb.set_trace()
            raise ValueError(
                "n.%d errors expected, found %d: %s" % (
                    expected_errors, len(errors), '\n++++++\n'.join([str(e) for e in errors])
                )
            )
        if not chunks:
            raise ValueError("No decoded object returned!!")
        elif len(chunks) > 1:
            raise ValueError("Too many ({}) decoded objects returned: {}".format(len(chunks), chunks))
        elif not isinstance(chunks[0], dict):
            raise ValueError("Decoded object is not a dictionary: {}".format(chunks))
        else:
            self.assertTrue(True, "Successfully test decoding for {}".format(xml_file))

        if not errors:
            root = etree_parse(xml_file).getroot()
            namespaces = etree_get_namespaces(xml_file)
            encoded_tree = xs.encode(chunks[0], path=root.tag, namespaces=namespaces)
            if not etree_elements_equal(root, encoded_tree, strict=False):
                import pdb
                pdb.set_trace()

            self.assertTrue(
                etree_elements_equal(root, encoded_tree, strict=False),
                "Encoded element tree differs from source tree."
            )


    return test_decoding



class TestEncoding(XMLSchemaTestCase):

    def check_encode(self, xsd_component, data, expected, **kwargs):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, xsd_component.encode, data, **kwargs)
        elif etree_iselement(expected):
            elem = xsd_component.encode(data, **kwargs)
            self.assertEqual(etree_tostring(expected), etree_tostring(elem))
        else:
            obj = xsd_component.encode(data, **kwargs)
            if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[1], list) \
                    and isinstance(obj[1][0], Exception):
                self.assertEqual(expected, obj[0])
                self.assertTrue(isinstance(obj[0], type(expected)))
            elif etree_iselement(obj):
                self.assertEqual(expected, etree_tostring(obj).strip())
            else:
                self.assertEqual(expected, obj)
                self.assertTrue(isinstance(obj, type(expected)))

    def test_decode_encode(self):
        filename = os.path.join(self.test_dir, 'cases/examples/collection/collection.xml')
        xt = _ElementTree.parse(filename)
        xd = self.col_schema.to_dict(filename, dict_class=OrderedDict)
        elem = self.col_schema.encode(xd, path='./col:collection', namespaces=self.namespaces)

        self.assertEqual(
            len([e for e in elem.iter()]), 20,
            msg="The encoded tree must have 20 elements as the origin."
        )
        self.assertTrue(all([
            local_name(e1.tag) == local_name(e2.tag)
            for e1, e2 in zip(elem.iter(), xt.getroot().iter())
        ]))

    def test_builtin_string_based_types(self):
        self.check_encode(self.xsd_types['string'], 'sample string ', u'sample string ')
        self.check_encode(self.xsd_types['normalizedString'], ' sample string ', u' sample string ')
        self.check_encode(self.xsd_types['normalizedString'], '\n\r sample\tstring\n', u'   sample string ')
        self.check_encode(self.xsd_types['token'], '\n\r sample\t\tstring\n ', u'sample string')
        self.check_encode(self.xsd_types['language'], 'sample string', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['language'], ' en ', u'en')
        self.check_encode(self.xsd_types['Name'], 'first_name', u'first_name')
        self.check_encode(self.xsd_types['Name'], ' first_name ', u'first_name')
        self.check_encode(self.xsd_types['Name'], 'first name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['Name'], '1st_name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['Name'], 'first_name1', u'first_name1')
        self.check_encode(self.xsd_types['Name'], 'first:name', u'first:name')
        self.check_encode(self.xsd_types['NCName'], 'first_name', u'first_name')
        self.check_encode(self.xsd_types['NCName'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['ENTITY'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['ID'], 'first:name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['IDREF'], 'first:name', XMLSchemaValidationError)

    def test_builtin_decimal_based_types(self):
        self.check_encode(self.xsd_types['decimal'], -99.09, u'-99.09')
        self.check_encode(self.xsd_types['decimal'], '-99.09', u'-99.09')
        self.check_encode(self.xsd_types['integer'], 1000, u'1000')
        self.check_encode(self.xsd_types['integer'], 100.0, XMLSchemaEncodeError)
        self.check_encode(self.xsd_types['integer'], 100.0, u'100', validation='lax')
        self.check_encode(self.xsd_types['short'], 1999, u'1999')
        self.check_encode(self.xsd_types['short'], 10000000, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['float'], 100.0, u'100.0')
        self.check_encode(self.xsd_types['float'], 'hello', XMLSchemaEncodeError)
        self.check_encode(self.xsd_types['double'], -4531.7, u'-4531.7')
        self.check_encode(self.xsd_types['positiveInteger'], -1, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['positiveInteger'], 0, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['nonNegativeInteger'], 0, u'0')
        self.check_encode(self.xsd_types['nonNegativeInteger'], -1, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['negativeInteger'], -100, u'-100')
        self.check_encode(self.xsd_types['nonPositiveInteger'], 7, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['unsignedLong'], 101, u'101')
        self.check_encode(self.xsd_types['unsignedLong'], -101, XMLSchemaValidationError)
        self.check_encode(self.xsd_types['nonPositiveInteger'], 7, XMLSchemaValidationError)

    def test_builtin_list_types(self):
        self.check_encode(self.xsd_types['IDREFS'], 'first_name', XMLSchemaValidationError)
        self.check_encode(self.xsd_types['IDREFS'], ['first_name'], u'first_name')
        self.check_encode(self.xsd_types['IDREFS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['IDREFS'], [1, 'two', 'three'], XMLSchemaValidationError)
        self.check_encode(self.xsd_types['NMTOKENS'], ['one', 'two', 'three'], u'one two three')
        self.check_encode(self.xsd_types['ENTITIES'], ('mouse', 'cat', 'dog'), u'mouse cat dog')

    def test_list_types(self):
        list_of_strings = self.st_schema.types['list_of_strings']
        self.check_encode(list_of_strings, (10, 25, 40), u'', validation='lax')
        self.check_encode(list_of_strings, (10, 25, 40), u'10 25 40', validation='skip')
        self.check_encode(list_of_strings, ['a', 'b', 'c'], u'a b c', validation='skip')

        list_of_integers = self.st_schema.types['list_of_integers']
        self.check_encode(list_of_integers, (10, 25, 40), u'10 25 40')
        self.check_encode(list_of_integers, (10, 25.0, 40), XMLSchemaValidationError)
        self.check_encode(list_of_integers, (10, 25.0, 40), u'10 25 40', validation='lax')

        list_of_floats = self.st_schema.types['list_of_floats']
        self.check_encode(list_of_floats, [10.1, 25.0, 40.0], u'10.1 25.0 40.0')
        self.check_encode(list_of_floats, [10.1, 25, 40.0], u'10.1 25.0 40.0', validation='lax')
        self.check_encode(list_of_floats, [10.1, False, 40.0], u'10.1 0.0 40.0', validation='lax')

        list_of_booleans = self.st_schema.types['list_of_booleans']
        self.check_encode(list_of_booleans, [True, False, True], u'true false true')
        self.check_encode(list_of_booleans, [10, False, True], XMLSchemaEncodeError)
        self.check_encode(list_of_booleans, [True, False, 40.0], u'true false', validation='lax')
        self.check_encode(list_of_booleans, [True, False, 40.0], u'true false 40.0', validation='skip')

    def test_union_types(self):
        integer_or_float = self.st_schema.types['integer_or_float']
        self.check_encode(integer_or_float, -95, u'-95')
        self.check_encode(integer_or_float, -95.0, u'-95.0')
        self.check_encode(integer_or_float, True, XMLSchemaEncodeError)
        self.check_encode(integer_or_float, True, u'1', validation='lax')

        integer_or_string = self.st_schema.types['integer_or_string']
        self.check_encode(integer_or_string, 89, u'89')
        self.check_encode(integer_or_string, 89.0, u'89', validation='lax')
        self.check_encode(integer_or_string, 89.0, XMLSchemaEncodeError)
        self.check_encode(integer_or_string, False, XMLSchemaEncodeError)
        self.check_encode(integer_or_string, "Venice ", u'Venice ')

        boolean_or_integer_or_string = self.st_schema.types['boolean_or_integer_or_string']
        self.check_encode(boolean_or_integer_or_string, 89, u'89')
        self.check_encode(boolean_or_integer_or_string, 89.0, u'89', validation='lax')
        self.check_encode(boolean_or_integer_or_string, 89.0, XMLSchemaEncodeError)
        self.check_encode(boolean_or_integer_or_string, False, u'false')
        self.check_encode(boolean_or_integer_or_string, "Venice ", u'Venice ')

    def test_simple_elements(self):
        elem = etree_element('{ns}A')
        elem.text = '89'
        self.check_encode(self.get_element('A', type='string'), '89', elem)
        self.check_encode(self.get_element('A', type='integer'), 89, elem)
        elem.text = '-10.4'
        self.check_encode(self.get_element('A', type='float'), -10.4, elem)
        elem.text = 'false'
        self.check_encode(self.get_element('A', type='boolean'), False, elem)
        elem.text = 'true'
        self.check_encode(self.get_element('A', type='boolean'), True, elem)

        self.check_encode(self.get_element('A', type='short'), 128000, XMLSchemaValidationError)
        elem.text = '0'
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), 0, elem)
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), '0', XMLSchemaValidationError)
        self.check_encode(self.get_element('A', type='positiveInteger'), 0, XMLSchemaValidationError)
        elem.text = '-1'
        self.check_encode(self.get_element('A', type='negativeInteger'), -1, elem)
        self.check_encode(self.get_element('A', type='nonNegativeInteger'), -1, XMLSchemaValidationError)

    def test_complex_elements(self):
        schema = self.get_schema("""
        <element name="A" type="ns:A_type" />
        <complexType name="A_type" mixed="true">
            <simpleContent>
                <extension base="string">
                    <attribute name="a1" type="short" use="required"/>                 
                    <attribute name="a2" type="negativeInteger"/>
                </extension>
            </simpleContent>
        </complexType>
        """)
        self.check_encode(
            schema.elements['A'], data={'@a1': 10, '@a2': -1, '$': 'simple '},
            expected='<ns:A xmlns:ns="ns" a1="10" a2="-1">simple </ns:A>'
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1, '$': 'simple '},
            etree_fromstring('<A xmlns="ns" a1="10" a2="-1">simple </A>'),
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '@a2': -1},
            etree_fromstring('<A xmlns="ns" a1="10" a2="-1"/>')
        )
        self.check_encode(
            schema.elements['A'], {'@a1': 10, '$': 'simple '},
            etree_fromstring('<A xmlns="ns" a1="10">simple </A>')
        )
        self.check_encode(schema.elements['A'], {'@a2': -1, '$': 'simple '}, XMLSchemaValidationError)

        schema = self.get_schema("""
        <element name="A" type="ns:A_type" />
        <complexType name="A_type">
            <sequence>
                <element name="B1" type="string"/>
                <element name="B2" type="integer"/>
                <element name="B3" type="boolean"/>                
            </sequence>
        </complexType>
        """)
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=OrderedDict([('B1', 'abc'), ('B2', 10), ('B3', False)]),
            expected=u'<ns:A xmlns:ns="ns">\n<B1>abc</B1>\n<B2>10</B2>\n<B3>false</B3>\n  </ns:A>',
            indent=0,
        )
        self.check_encode(schema.elements['A'], {'B1': 'abc', 'B2': 10, 'B4': False}, XMLSchemaValidationError)
        self.check_encode(
            xsd_component=schema.elements['A'],
            data=OrderedDict([('B1', 'abc'), ('B2', 10), ('#1', 'hello')]),
            expected=u'<ns:A xmlns:ns="ns">\n<B1>abc</B1>\n<B2>10</B2>\n  hello</ns:A>',
            indent=0, cdata_prefix='#'
        )


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, tests_factory, get_testfiles

    print_test_header()
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    encoding_tests = tests_factory(make_encoding_test_function, testfiles, 'encoding', 'xml')
    globals().update(encoding_tests)
    unittest.main()
