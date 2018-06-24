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
This module runs tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
import unittest
import os
import sys
import pickle

try:
    # noinspection PyPackageRequirements
    import lxml.etree as _lxml_etree
except ImportError:
    _lxml_etree = None

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema import XMLSchemaParseError, XMLSchemaURLError, XMLSchemaBase
from xmlschema.compat import PY3
from xmlschema.tests import SchemaObserver, XMLSchemaTestCase
from xmlschema.qnames import XSD_LIST_TAG, XSD_UNION_TAG


class TestXMLSchema10(XMLSchemaTestCase):

    def check_schema(self, source, expected=None, **kwargs):
        """
        Create a schema for a test case.

        :param source: A relative path or a root Element or a portion of schema for a template.
        :param expected: If it's an Exception class test the schema for raise an error. \
        Otherwise build the schema and test a condition if expected is a callable, or make \
        a substring test if it's not `None` (maybe a string). Then returns the schema instance.
        """
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, self.schema_class, self.retrieve_schema_source(source), **kwargs)
        else:
            schema = self.schema_class(self.retrieve_schema_source(source), **kwargs)
            if callable(expected):
                self.assertTrue(expected(schema))
            return schema

    def check_complex_restriction(self, base, restriction, expected=None, **kwargs):
        content = 'complex' if self.content_pattern.search(base) else 'simple'
        source = """
            <complexType name="targetType">
                {0}
            </complexType>        
            <complexType name="restrictedType">
                <{1}Content>
                    <restriction base="targetType">
                        {2}                    
                    </restriction>
                </{1}Content>
            </complexType>
            """.format(base.strip(), content, restriction.strip())
        self.check_schema(source, expected, **kwargs)

    def test_simple_types(self):
        # Issue #54: set list or union schema element.
        xs = self.check_schema("""
            <simpleType name="test_list">
                <annotation/>
                <list itemType="string"/>
            </simpleType>
    
            <simpleType name="test_union">
                <annotation/>
                <union memberTypes="string integer boolean"/>
            </simpleType>
        """)
        xs.types['test_list'].elem = xs.root[0]  # elem.tag == 'simpleType'
        self.assertEqual(xs.types['test_list'].elem.tag, XSD_LIST_TAG)
        xs.types['test_union'].elem = xs.root[1]  # elem.tag == 'simpleType'
        self.assertEqual(xs.types['test_union'].elem.tag, XSD_UNION_TAG)

    def test_wrong_includes_and_imports(self):
        self.check_schema("""
            <include schemaLocation="example.xsd" />
            <import schemaLocation="example.xsd" />
            <redefine schemaLocation="example.xsd"/>
            <import namespace="http://missing.example.test/" />
            <import/>
            """)

    def test_wrong_references(self):
        # Wrong namespace for element type's reference
        self.check_schema("""
            <element name="dimension" type="dimensionType"/>
            <simpleType name="dimensionType">
                <restriction base="short"/>
            </simpleType>
            """, XMLSchemaParseError)

    def test_facets(self):
        # Issue #55 and a near error (derivation from xs:integer)
        self.check_schema("""
            <simpleType name="dtype">
                <restriction base="decimal">
                    <fractionDigits value="3" />
                    <totalDigits value="20" />
                </restriction>
            </simpleType>
    
            <simpleType name="ntype">
                <restriction base="ns:dtype">
                    <totalDigits value="3" />
                    <fractionDigits value="1" />
                </restriction>
            </simpleType>
            """)
        self.check_schema("""
            <simpleType name="dtype">
                <restriction base="integer">
                    <fractionDigits value="3" /> <!-- <<< value must be 0 -->
                    <totalDigits value="20" />
                </restriction>
            </simpleType>
            """, xmlschema.XMLSchemaParseError)

        # Issue #56
        self.check_schema("""
            <simpleType name="mlengthparent">
                <restriction base="string">
                    <maxLength value="200"/>
                </restriction>
            </simpleType>
            <simpleType name="mlengthchild">
                <restriction base="ns:mlengthparent">
                    <maxLength value="20"/>
                </restriction>
            </simpleType>
            """)

    @unittest.skip("The feature is still under development")
    def test_element_restrictions(self):
        base = """
        <sequence>
            <element name="A" maxOccurs="7"/>
            <element name="B" type="string"/>
            <element name="C" fixed="5"/>
        </sequence>
        """
        self.check_complex_restriction(
            base, restriction="""
            <sequence>
                <element name="A" maxOccurs="6"/>
                <element name="B" type="NCName"/>
                <element name="C" fixed="5"/>
            </sequence>
            """)

        self.check_complex_restriction(
            base, restriction="""
            <sequence>
                <element name="A" maxOccurs="8"/> <!-- <<< More occurrences -->
                <element name="B" type="NCName"/>
                <element name="C" fixed="5"/>
            </sequence>
            """, expected=XMLSchemaParseError)

        self.check_complex_restriction(
            base, restriction="""
            <sequence>
                <element name="A" maxOccurs="6"/>
                <element name="B" type="float"/> <!-- <<< Not a derived type -->
                <element name="C" fixed="5"/>
            </sequence>
            """, expected=XMLSchemaParseError)

        self.check_complex_restriction(
            base, restriction="""
            <sequence>
                <element name="A" maxOccurs="6"/>
                <element name="B" type="NCName"/>
                <element name="C" fixed="3"/> <!-- <<< Different fixed value -->
            </sequence>
            """, expected=XMLSchemaParseError)

        self.check_complex_restriction(
            base, restriction="""
            <sequence>
                <element name="A" maxOccurs="6" nillable="true"/> <!-- <<< nillable is True -->
                <element name="B" type="NCName"/>
                <element name="C" fixed="5"/>
            </sequence>
            """, expected=XMLSchemaParseError)

    @unittest.skip("The feature is still under development")
    def test_sequence_group_restriction(self):
        # Meaningless sequence group
        base = """
        <sequence>
            <sequence>
                <element name="A"/>
                <element name="B"/>
            </sequence>
        </sequence>
        """
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="B"/></sequence>'
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="C"/></sequence>', XMLSchemaParseError
        )

        base = """
        <sequence>
            <element name="A"/>
            <element name="B" minOccurs="0"/>
        </sequence>
        """
        self.check_complex_restriction(base, '<sequence><element name="A"/></sequence>')
        self.check_complex_restriction(base, '<sequence><element name="B"/></sequence>', XMLSchemaParseError)
        self.check_complex_restriction(base, '<sequence><element name="C"/></sequence>', XMLSchemaParseError)
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="B"/></sequence>'
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="C"/></sequence>', XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A" minOccurs="0"/><element name="B"/></sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="B" minOccurs="0"/><element name="A"/></sequence>',
            XMLSchemaParseError
        )

    @unittest.skip("The feature is still under development")
    def test_all_group_restriction(self):
        base = """
        <all>
            <element name="A"/>
            <element name="B" minOccurs="0"/>
            <element name="C" minOccurs="0"/>
        </all>
        """
        self.check_complex_restriction(base, '<all><element name="A"/><element name="C"/></all>')
        self.check_complex_restriction(
            base, '<all><element name="C" minOccurs="0"/><element name="A"/></all>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="C"/></sequence>'
        )
        self.check_complex_restriction(
            base, '<sequence><element name="C" minOccurs="0"/><element name="A"/></sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="X"/></sequence>',
            XMLSchemaParseError
        )

    @unittest.skip("The feature is still under development")
    def test_choice_group_restriction(self):
        base = """
        <choice maxOccurs="2">
            <element name="A"/>
            <element name="B"/>
            <element name="C"/>
        </choice>
        """
        self.check_complex_restriction(base, '<choice><element name="A"/><element name="C"/></choice>')
        self.check_complex_restriction(
            base, '<choice maxOccurs="2"><element name="C"/><element name="A"/></choice>',
            XMLSchemaParseError
        )

        self.check_complex_restriction(
            base, '<choice maxOccurs="2"><element name="A"/><element name="C"/></choice>',
        )

    @unittest.skip("The feature is still under development")
    def test_occurs_restriction(self):
        base = """
        <sequence minOccurs="3" maxOccurs="10">
            <element name="A"/>
        </sequence>
        """
        self.check_complex_restriction(
            base, '<sequence minOccurs="3" maxOccurs="7"><element name="A"/></sequence>')
        self.check_complex_restriction(
            base, '<sequence minOccurs="4" maxOccurs="10"><element name="A"/></sequence>')
        self.check_complex_restriction(
            base, '<sequence minOccurs="3" maxOccurs="11"><element name="A"/></sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence minOccurs="2" maxOccurs="10"><element name="A"/></sequence>',
            XMLSchemaParseError
        )

    def test_union_restrictions(self):
        # Wrong union restriction (not admitted facets, see issue #67)
        self.check_schema("""
            <simpleType name="Percentage">
                <restriction base="ns:Integer">
                    <minInclusive value="0"/>
                    <maxInclusive value="100"/>
                </restriction>
            </simpleType>
            
            <simpleType name="Integer">
                <union memberTypes="int ns:IntegerString"/>
            </simpleType>
                        
            <simpleType name="IntegerString">
                <restriction base="string">
                    <pattern value="-?[0-9]+(\.[0-9]+)?%"/>
                </restriction>
            </simpleType>
            """, XMLSchemaParseError)

    def test_final_attribute(self):
        self.check_schema("""
            <simpleType name="aType" final="list restriction">
		        <restriction base="string"/>
	        </simpleType>
	        """)


def make_test_schema_function(xsd_file, schema_class, expected_errors=0, inspect=False,
                              locations=None, defuse='remote'):
    def test_schema(self):
        if inspect:
            SchemaObserver.clear()

        # print("Run %s" % self.id())
        try:
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax', locations=locations, defuse=defuse)
            else:
                xs = schema_class(xsd_file, locations=locations, defuse=defuse)
        except (XMLSchemaParseError, XMLSchemaURLError, KeyError) as err:
            num_errors = 1
            errors = [str(err)]
        else:
            num_errors = len(xs.all_errors)
            errors = xs.all_errors

            if inspect:
                components_ids = set([id(c) for c in xs.iter_components()])
                missing = [c for c in SchemaObserver.components if id(c) not in components_ids]
                if any([c for c in missing]):
                    raise ValueError("schema missing %d components: %r" % (len(missing), missing))

            # Pickling test (only for Python 3, skip inspected schema classes test)
            if not inspect and PY3:
                deserialized_schema = pickle.loads(pickle.dumps(xs))
                self.assertTrue(isinstance(deserialized_schema, XMLSchemaBase))
                self.assertEqual(xs.built, deserialized_schema.built)

            # Check with lxml.etree.XMLSchema if it's installed
        if False and _lxml_etree is not None and not num_errors:
            xsd = _lxml_etree.parse(xsd_file)
            try:
                _lxml_etree.XMLSchema(xsd.getroot())
            except _lxml_etree.XMLSchemaParseError as err:
                self.assertTrue(
                    False, "Schema without errors but lxml's validator report an error: {}".format(err)
                )

        if num_errors != expected_errors:
            print("\n%s: %r errors, %r expected." % (self.id()[13:], num_errors, expected_errors))
            if num_errors == 0:
                raise ValueError("found no errors when %d expected." % expected_errors)
            else:
                raise ValueError("n.%d errors expected, found %d: %s" % (
                    expected_errors, num_errors, '\n++++++\n'.join([str(e) for e in errors])
                ))
        else:
            self.assertTrue(True, "Successfully created schema for {}".format(xsd_file))

    return test_schema


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, get_testfiles, tests_factory

    print_test_header()
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    schema_tests = tests_factory(make_test_schema_function, testfiles, label='schema', suffix='xsd')
    globals().update(schema_tests)
    unittest.main()
