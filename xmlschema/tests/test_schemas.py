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

try:
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

from xmlschema import XMLSchemaParseError, XMLSchemaURLError
from xmlschema.tests import SchemaObserver
from xmlschema.qnames import XSD_LIST_TAG, XSD_UNION_TAG


SCHEMA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns="http://foo.bar.test" xmlns:xs="http://www.w3.org/2001/XMLSchema" 
    targetNamespace="http://foo.bar.test" elementFormDefault="qualified" version="{0}">
{1}
</xs:schema>"""


class TestXMLSchema1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)
        cls.schema_class = xmlschema.XMLSchema
        cls.namespaces = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        }

    def check_schema(self, source, expected=None, **kwargs):
        """
        Create a schema for a test case.

        :param source: A relative path or a root Element or a portion of schema for a template.
        :param expected: If it's an Exception class test the schema for raise an error. \
        Otherwise build the schema and test a condition if expected is a callable, or make \
        a substring test if it's not `None` (maybe a string). Then returns the schema instance.
        """
        try:
            source = source.strip()
        except AttributeError:
            pass
        else:
            if source.startswith('<'):
                source = SCHEMA_TEMPLATE.format(self.schema_class.XSD_VERSION, source)
            else:
                source = os.path.join(self.test_dir, source)

        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, self.schema_class, source, **kwargs)
        else:
            schema = self.schema_class(source, **kwargs)
            if callable(expected):
                self.assertTrue(expected(schema))
            return schema

    def test_simple_types(self):
        xs = self.check_schema('cases/features/elements/test-simple-types.xsd')

        # Issue #54: set list or union element.
        xs.types['test_list'].elem = xs.root[1]  # elem.tag == xs:simpleType
        self.assertEqual(xs.types['test_list'].elem.tag, XSD_LIST_TAG)
        xs.types['test_union'].elem = xs.root[2]  # elem.tag == xs:simpleType
        self.assertEqual(xs.types['test_union'].elem.tag, XSD_UNION_TAG)

    def test_facets(self):
        # Issue #55 and a near error (derivation from xs:integer)
        self.check_schema("""
            <xs:simpleType name="dtype">
                <xs:restriction base="xs:decimal">
                    <xs:fractionDigits value="3" />
                    <xs:totalDigits value="20" />
                </xs:restriction>
            </xs:simpleType>
    
            <xs:simpleType name="ntype">
                <xs:restriction base="dtype">
                    <xs:totalDigits value="3" />
                    <xs:fractionDigits value="1" />
                </xs:restriction>
            </xs:simpleType>
            """)
        self.check_schema("""
            <xs:simpleType name="dtype">
                <xs:restriction base="xs:integer">
                    <xs:fractionDigits value="3" /> <!-- <<< value must be 0 -->
                    <xs:totalDigits value="20" />
                </xs:restriction>
            </xs:simpleType>
            """, xmlschema.XMLSchemaParseError)

        # Issue #56
        self.check_schema("""
            <xs:simpleType name="mlengthparent">
                <xs:restriction base="xs:string">
                    <xs:maxLength value="200"/>
                </xs:restriction>
            </xs:simpleType>
            <xs:simpleType name="mlengthchild">
                <xs:restriction base="mlengthparent">
                    <xs:maxLength value="20"/>
                </xs:restriction>
                </xs:simpleType>
            """)


def make_test_schema_function(xsd_file, schema_class, expected_errors=0, inspect=False, locations=None):
    def test_schema(self):
        if inspect:
            SchemaObserver.clear()
        # print("Run %s" % self.id())
        try:
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax', locations=locations)
            else:
                xs = schema_class(xsd_file, locations=locations)
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
                raise ValueError(
                    "n.%d errors expected, found %d: %s" % (expected_errors, num_errors, errors[0])
                )
        else:
            self.assertTrue(True, "Successfully created schema for {}".format(xsd_file))

    return test_schema


if __name__ == '__main__':
    from xmlschema.tests import print_test_header, tests_factory

    print_test_header()

    if '-s' not in sys.argv and '--skip-extra' not in sys.argv:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '*/testfiles')
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases/testfiles')
        try:
            sys.argv.remove('-s')
        except ValueError:
            sys.argv.remove('--skip-extra')

    schema_tests = tests_factory(make_test_schema_function, path, label='schema', suffix='xsd')
    globals().update(schema_tests)
    unittest.main()
