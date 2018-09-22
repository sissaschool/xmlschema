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
import warnings

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

from xmlschema import (
    XMLSchemaParseError, XMLSchemaBase, XMLSchema, XMLSchemaIncludeWarning, XMLSchemaImportWarning
)
from xmlschema.compat import PY3
from xmlschema.tests import SKIP_REMOTE_TESTS, SchemaObserver, XMLSchemaTestCase
from xmlschema.qnames import XSD_LIST_TAG, XSD_UNION_TAG
from xmlschema.etree import defused_etree
from xmlschema.xpath import ElementPathContext
from xmlschema.validators import XsdValidator


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

        with warnings.catch_warnings(record=True) as context:
            warnings.simplefilter("always")
            self.check_schema("""
                <include schemaLocation="example.xsd" />
                <import schemaLocation="example.xsd" />
                <redefine schemaLocation="example.xsd"/>
                <import namespace="http://missing.example.test/" />
                <import/>
                """)
            self.assertEqual(len(context), 4, "Wrong number of include/import warnings")
            self.assertEqual(context[0].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[1].category, XMLSchemaIncludeWarning)
            self.assertEqual(context[2].category, XMLSchemaImportWarning)
            self.assertEqual(context[3].category, XMLSchemaImportWarning)
            self.assertTrue(str(context[0].message).startswith("Include"))
            self.assertTrue(str(context[1].message).startswith("Redefine"))
            self.assertTrue(str(context[2].message).startswith("Namespace import"))
            self.assertTrue(str(context[3].message).startswith("Namespace import"))
            self.assertTrue(str(context[3].message).endswith("no schema location provided."))

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

    @unittest.skipIf(SKIP_REMOTE_TESTS, "Remote networks are not accessible.")
    def test_remote_schemas(self):
        # Tests with Dublin Core schemas that also use imports
        dc_schema = self.schema_class("http://dublincore.org/schemas/xmls/qdc/2008/02/11/dc.xsd")
        self.assertTrue(isinstance(dc_schema, self.schema_class))
        dcterms_schema = self.schema_class("http://dublincore.org/schemas/xmls/qdc/2008/02/11/dcterms.xsd")
        self.assertTrue(isinstance(dcterms_schema, self.schema_class))

        # Check XML resource defusing
        self.assertEqual(dc_schema.source.parse, defused_etree.parse)
        self.assertEqual(dc_schema.source.iterparse, defused_etree.iterparse)
        self.assertEqual(dc_schema.source.fromstring, defused_etree.fromstring)
        self.assertEqual(dcterms_schema.source.parse, defused_etree.parse)
        self.assertEqual(dcterms_schema.source.iterparse, defused_etree.iterparse)
        self.assertEqual(dcterms_schema.source.fromstring, defused_etree.fromstring)


def make_schema_test_class(test_file, test_args, test_num=0, schema_class=XMLSchema):

    xsd_file = test_file

    # Extract schema test arguments
    expected_errors = test_args.errors
    expected_warnings = test_args.warnings
    inspect = test_args.inspect
    locations = test_args.locations
    defuse = test_args.defuse
    debug_mode = test_args.debug

    def test_schema(self):
        if debug_mode:
            print("\n##\n## Testing schema %s in debug mode.\n##" % rel_path)
            import pdb
            pdb.set_trace()

        if inspect:
            SchemaObserver.clear()

        def check_schema():
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax', locations=locations, defuse=defuse)
            else:
                xs = schema_class(xsd_file, locations=locations, defuse=defuse)

            errors_ = xs.all_errors

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

            # XPath API tests
            if not inspect and not errors_:
                context = ElementPathContext(xs)
                elements = [e for e in xs.iter()]
                context_elements = [e for e in context.iter() if isinstance(e, XsdValidator)]
                self.assertEqual(context_elements, [e for e in context.iter_descendants()])
                self.assertEqual(context_elements, elements)

            return errors_

        if expected_warnings > 0:
            with warnings.catch_warnings(record=True) as ctx:
                warnings.simplefilter("always")
                errors = check_schema()
                self.assertEqual(len(ctx), expected_warnings, "Wrong number of include/import warnings")
        else:
            errors = check_schema()

        # Checks errors completeness
        for e in errors:
            self.assertTrue(e.path, "Missing path for: %s" % str(e))
            self.assertTrue(e.namespaces, "Missing namespaces for: %s" % str(e))

        num_errors = len(errors)
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

    rel_path = os.path.relpath(test_file)
    class_name = 'TestSchema{0:03}'.format(test_num)
    return type(
        class_name, (unittest.TestCase,),
        {'test_schema_{0:03}_{1}'.format(test_num, rel_path): test_schema}
    )


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, get_testfiles, tests_factory

    print_test_header()
    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    schema_tests = tests_factory(make_schema_test_class, testfiles, suffix='xsd')
    globals().update(schema_tests)
    unittest.main()
