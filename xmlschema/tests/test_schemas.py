#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
from __future__ import print_function, unicode_literals
import unittest
import pdb
import os
import pickle
import time
import warnings

import xmlschema
from xmlschema import XMLSchemaBase, XMLSchemaParseError, XMLSchemaModelError, \
    XMLSchemaIncludeWarning, XMLSchemaImportWarning
from xmlschema.compat import PY3, unicode_type
from xmlschema.etree import lxml_etree, etree_element, py_etree_element
from xmlschema.qnames import XSD_LIST, XSD_UNION, XSD_ELEMENT, XSI_TYPE
from xmlschema.tests import tests_factory, SchemaObserver, XMLSchemaTestCase
from xmlschema.validators import XsdValidator, XMLSchema11
from xmlschema.xpath import ElementPathContext


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
                    <restriction base="ns:targetType"> 
                        {2}                    
                    </restriction>
                </{1}Content>
            </complexType>
            """.format(base.strip(), content, restriction.strip())
        self.check_schema(source, expected, **kwargs)

    def test_schema_copy(self):
        schema = self.vh_schema.copy()
        self.assertNotEqual(id(self.vh_schema), id(schema))
        self.assertNotEqual(id(self.vh_schema.namespaces), id(schema.namespaces))
        self.assertNotEqual(id(self.vh_schema.maps), id(schema.maps))

    def test_resolve_qname(self):
        schema = self.schema_class("""<xs:schema
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

            <xs:element name="root" />
        </xs:schema>""")
        self.assertEqual(schema.resolve_qname('xs:element'), XSD_ELEMENT)
        self.assertEqual(schema.resolve_qname('xsi:type'), XSI_TYPE)

        self.assertEqual(schema.resolve_qname(XSI_TYPE), XSI_TYPE)
        self.assertEqual(schema.resolve_qname('element'), 'element')
        self.assertRaises(ValueError, schema.resolve_qname, '')
        self.assertRaises(ValueError, schema.resolve_qname, 'xsi:a type ')
        self.assertRaises(ValueError, schema.resolve_qname, 'xml::lang')

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
        self.assertEqual(xs.types['test_list'].elem.tag, XSD_LIST)
        xs.types['test_union'].elem = xs.root[1]  # elem.tag == 'simpleType'
        self.assertEqual(xs.types['test_union'].elem.tag, XSD_UNION)

    def test_wrong_includes_and_imports(self):

        with warnings.catch_warnings(record=True) as context:
            warnings.simplefilter("always")
            self.check_schema("""
                <include schemaLocation="example.xsd" />
                <import schemaLocation="example.xsd" />
                <redefine schemaLocation="example.xsd"/>
                <import namespace="http://missing.example.test/" />
                <import/>
                """)
            self.assertEqual(len(context), 3, "Wrong number of include/import warnings")
            self.assertEqual(context[0].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[1].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[2].category, XMLSchemaImportWarning)
            self.assertTrue(str(context[0].message).startswith("Include"))
            self.assertTrue(str(context[1].message).startswith("Redefine"))
            self.assertTrue(str(context[2].message).startswith("Namespace import"))

    def test_wrong_references(self):
        # Wrong namespace for element type's reference
        self.check_schema("""
            <element name="dimension" type="dimensionType"/>
            <simpleType name="dimensionType">
                <restriction base="short"/>
            </simpleType>
            """, XMLSchemaParseError)

    def test_restriction_has_annotation(self):
        # Wrong namespace for element type's reference
        schema = self.check_schema("""
            <simpleType name='Magic'>
                <annotation>
                    <documentation> stuff </documentation>
                </annotation>
                <restriction base='string'>
                    <enumeration value='A'/>
                </restriction>
            </simpleType>""")
        self.assertIsNotNone(schema.types["Magic"].annotation)

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
            base, '<all><element name="C" minOccurs="0"/><element name="A"/></all>', XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="C"/></sequence>'
        )
        self.check_complex_restriction(
            base, '<sequence><element name="C" minOccurs="0"/><element name="A"/></sequence>',
        )
        self.check_complex_restriction(
            base, '<sequence><element name="C" minOccurs="0"/><element name="A" minOccurs="0"/></sequence>',
            XMLSchemaParseError
        )
        self.check_complex_restriction(
            base, '<sequence><element name="A"/><element name="X"/></sequence>', XMLSchemaParseError
        )

        base = """
        <all>
            <element name="A" minOccurs="0" maxOccurs="0"/>
        </all>
        """
        self.check_complex_restriction(base, '<all><element name="A"/></all>', XMLSchemaParseError)

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
        self.check_schema(r"""
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

    def test_wrong_attribute(self):
        self.check_schema("""
            <attributeGroup name="alpha">
                <attribute name="name" type="string"/>
                <attribute ref="phone"/>  <!-- Missing "phone" attribute -->
            </attributeGroup>
            """, XMLSchemaParseError)

    def test_wrong_attribute_group(self):
        self.check_schema("""
            <attributeGroup name="alpha">
                <attribute name="name" type="string"/>
                <attributeGroup ref="beta"/>  <!-- Missing "beta" attribute group -->
            </attributeGroup>
            """, XMLSchemaParseError)
        schema = self.check_schema("""
            <attributeGroup name="alpha">
                <attribute name="name" type="string"/>
                <attributeGroup name="beta"/>  <!-- attribute "name" instead of "ref" -->
            </attributeGroup>
            """, validation='lax')
        self.assertTrue(isinstance(schema.all_errors[1], XMLSchemaParseError))

    def test_date_time_facets(self):
        self.check_schema("""
            <simpleType name="restricted_date">
                <restriction base="date">
                    <minInclusive value="1900-01-01"/>
                    <maxInclusive value="2030-12-31"/>
                </restriction>
            </simpleType>""")

        self.check_schema("""
            <simpleType name="restricted_year">
                <restriction base="gYear">
                    <minInclusive value="1900"/>
                    <maxInclusive value="2030"/>
                </restriction>
            </simpleType>""")

    def test_base_schemas(self):
        from xmlschema.validators.schema import XML_SCHEMA_FILE
        schema = self.schema_class(XML_SCHEMA_FILE)

    def test_recursive_complex_type(self):
        schema = self.schema_class("""
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="elemA" type="typeA"/>
                <xs:complexType name="typeA">
                    <xs:sequence>
                        <xs:element ref="elemA" minOccurs="0" maxOccurs="5"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:schema>""")
        self.assertEqual(schema.elements['elemA'].type, schema.types['typeA'])

    def test_upa_violations(self):
        self.check_schema("""
            <complexType name="typeA">
                <sequence>
                    <sequence minOccurs="0" maxOccurs="unbounded">
                        <element name="A"/>
                        <element name="B"/>
                    </sequence>
                    <element name="A" minOccurs="0"/>
                </sequence>
            </complexType>""", XMLSchemaModelError)

        self.check_schema("""
            <complexType name="typeA">
                <sequence>
                    <sequence minOccurs="0" maxOccurs="unbounded">
                        <element name="B"/>
                        <element name="A"/>
                    </sequence>
                    <element name="A" minOccurs="0"/>
                </sequence>
            </complexType>""")


class TestXMLSchema11(TestXMLSchema10):

    schema_class = XMLSchema11

    def test_explicit_timezone_facet(self):
        schema = self.check_schema("""
            <simpleType name='opt-tz-date'>
              <restriction base='date'>
                <explicitTimezone value='optional'/>
              </restriction>
            </simpleType>
            <simpleType name='req-tz-date'>
              <restriction base='date'>
                <explicitTimezone value='required'/>
              </restriction>
            </simpleType>
            <simpleType name='no-tz-date'>
              <restriction base='date'>
                <explicitTimezone value='prohibited'/>
              </restriction>
            </simpleType>
            """)
        self.assertTrue(schema.types['req-tz-date'].is_valid('2002-10-10-05:00'))
        self.assertTrue(schema.types['req-tz-date'].is_valid('2002-10-10Z'))
        self.assertFalse(schema.types['req-tz-date'].is_valid('2002-10-10'))

    def test_assertion_facet(self):
        self.check_schema("""
            <simpleType name='DimensionType'>
              <restriction base='integer'>
                <assertion test='string-length($value) &lt; 2'/>
              </restriction>
            </simpleType>""", XMLSchemaParseError)

        schema = self.check_schema("""
            <simpleType name='MeasureType'>
              <restriction base='integer'>
                <assertion test='$value &gt; 0'/>
              </restriction>
            </simpleType>""")
        self.assertTrue(schema.types['MeasureType'].is_valid('10'))
        self.assertFalse(schema.types['MeasureType'].is_valid('-1.5'))

        self.check_schema("""
            <simpleType name='RestrictedDateTimeType'>
              <restriction base='dateTime'>
                <assertion test="$value > '1999-12-31T23:59:59'"/>
              </restriction>
            </simpleType>""", XMLSchemaParseError)

        schema = self.check_schema("""
            <simpleType name='RestrictedDateTimeType'>
              <restriction base='dateTime'>
                <assertion test="$value > xs:dateTime('1999-12-31T23:59:59')"/>
              </restriction>
            </simpleType>""")
        self.assertTrue(schema.types['RestrictedDateTimeType'].is_valid('2000-01-01T12:00:00'))

        schema = self.check_schema("""<simpleType name="Percentage">
              <restriction base="integer">
                <assertion test="$value >= 0"/>
                <assertion test="$value &lt;= 100"/>
              </restriction>
            </simpleType>""")
        self.assertTrue(schema.types['Percentage'].is_valid('10'))
        self.assertTrue(schema.types['Percentage'].is_valid('100'))
        self.assertTrue(schema.types['Percentage'].is_valid('0'))
        self.assertFalse(schema.types['Percentage'].is_valid('-1'))
        self.assertFalse(schema.types['Percentage'].is_valid('101'))
        self.assertFalse(schema.types['Percentage'].is_valid('90.1'))

    def test_complex_type_assertion(self):
        schema = self.check_schema("""
            <complexType name="intRange">
              <attribute name="min" type="int"/>
              <attribute name="max" type="int"/>
              <assert test="@min le @max"/>
            </complexType>""")

        xsd_type = schema.types['intRange']
        xsd_type.decode(etree_element('a', attrib={'min': '10', 'max': '19'}))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '10', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '19', 'max': '19'})))
        self.assertFalse(xsd_type.is_valid(etree_element('a', attrib={'min': '25', 'max': '19'})))
        self.assertTrue(xsd_type.is_valid(etree_element('a', attrib={'min': '25', 'max': '100'})))


def make_schema_test_class(test_file, test_args, test_num, schema_class, check_with_lxml):
    """
    Creates a schema test class.

    :param test_file: the schema test file path.
    :param test_args: line arguments for test case.
    :param test_num: a positive integer number associated with the test case.
    :param schema_class: the schema class to use.
    :param check_with_lxml: if `True` compare with lxml XMLSchema class, reporting anomalies. \
    Works only for XSD 1.0 tests.
    """
    xsd_file = os.path.relpath(test_file)

    # Extract schema test arguments
    expected_errors = test_args.errors
    expected_warnings = test_args.warnings
    inspect = test_args.inspect
    locations = test_args.locations
    defuse = test_args.defuse
    debug_mode = test_args.debug

    class TestSchema(XMLSchemaTestCase):

        @classmethod
        def setUpClass(cls):
            cls.schema_class = schema_class
            cls.errors = []
            cls.longMessage = True

            if debug_mode:
                print("\n##\n## Testing %r schema in debug mode.\n##" % xsd_file)
                pdb.set_trace()

        def check_schema(self):
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax', locations=locations, defuse=defuse)
            else:
                xs = schema_class(xsd_file, locations=locations, defuse=defuse)
            self.errors.extend(xs.maps.all_errors)

            if inspect:
                components_ids = set([id(c) for c in xs.maps.iter_components()])
                missing = [c for c in SchemaObserver.components if id(c) not in components_ids]
                if any([c for c in missing]):
                    raise ValueError("schema missing %d components: %r" % (len(missing), missing))

            # Pickling test (only for Python 3, skip inspected schema classes test)
            if not inspect and PY3:
                try:
                    obj = pickle.dumps(xs)
                    deserialized_schema = pickle.loads(obj)
                except pickle.PicklingError:
                    # Don't raise if some schema parts (eg. a schema loaded from remote)
                    # are built with the SafeXMLParser that uses pure Python elements.
                    for e in xs.maps.iter_components():
                        elem = getattr(e, 'elem', getattr(e, 'root', None))
                        if isinstance(elem, py_etree_element):
                            break
                    else:
                        raise
                else:
                    self.assertTrue(isinstance(deserialized_schema, XMLSchemaBase))
                    self.assertEqual(xs.built, deserialized_schema.built)

            # XPath API tests
            if not inspect and not self.errors:
                context = ElementPathContext(xs)
                elements = [x for x in xs.iter()]
                context_elements = [x for x in context.iter() if isinstance(x, XsdValidator)]
                self.assertEqual(context_elements, [x for x in context.iter_descendants()])
                self.assertEqual(context_elements, elements)

        def check_lxml_schema(self, xmlschema_time):
            start_time = time.time()
            lxs = lxml_etree.parse(xsd_file)
            try:
                lxml_etree.XMLSchema(lxs.getroot())
            except lxml_etree.XMLSchemaParseError as err:
                if not self.errors:
                    print("\nSchema error with lxml.etree.XMLSchema for file {!r} ({}): {}".format(
                        xsd_file, self.__class__.__name__, unicode_type(err)
                    ))
            else:
                if self.errors:
                    print("\nUnrecognized errors with lxml.etree.XMLSchema for file {!r} ({}): {}".format(
                        xsd_file, self.__class__.__name__,
                        '\n++++++\n'.join([unicode_type(e) for e in self.errors])
                    ))
                lxml_schema_time = time.time() - start_time
                if lxml_schema_time >= xmlschema_time:
                    print(
                        "\nSlower lxml.etree.XMLSchema ({:.3f}s VS {:.3f}s) with file {!r} ({})".format(
                            lxml_schema_time, xmlschema_time, xsd_file, self.__class__.__name__
                        ))

        def test_xsd_schema(self):
            if inspect:
                SchemaObserver.clear()
            del self.errors[:]

            start_time = time.time()
            if expected_warnings > 0:
                with warnings.catch_warnings(record=True) as ctx:
                    warnings.simplefilter("always")
                    self.check_schema()
                    self.assertEqual(len(ctx), expected_warnings,
                                     "%r: Wrong number of include/import warnings" % xsd_file)
            else:
                self.check_schema()

                # Check with lxml.etree.XMLSchema class
            if check_with_lxml and lxml_etree is not None:
                self.check_lxml_schema(xmlschema_time=time.time()-start_time)
            self.check_errors(xsd_file, expected_errors)

    TestSchema.__name__ = TestSchema.__qualname__ = str('TestSchema{0:03}'.format(test_num))
    return TestSchema


# Creates schema tests from XSD files
globals().update(tests_factory(make_schema_test_class, 'xsd'))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
