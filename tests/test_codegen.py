#!/usr/bin/env python
#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests concerning XSD based code generators. Requires jinja2 optional dependency."""

import unittest
import os
import datetime
from pathlib import Path
from xmlschema import XMLSchema10
from xmlschema.names import XSD_ANY_TYPE, XSD_STRING, XSD_FLOAT

try:
    import jinja2
except ImportError:
    jinja2 = None
    filter_method = None
    AbstractGenerator = None
    PythonGenerator = None
    DemoGenerator = None
else:
    from xmlschema.extras.codegen import filter_method, AbstractGenerator, PythonGenerator

    class DemoGenerator(AbstractGenerator):
        formal_language = 'Demo'

        default_paths = ['test_cases/templates/filters/']

        builtin_types = {
            'string': 'str',
            'boolean': 'bool',
            'float': 'float',
            'double': 'double',
            'integer': 'int',
            'unsignedByte': 'unsigned short',
            'nonNegativeInteger': 'unsigned int',
            'positiveInteger': 'unsigned int',
        }

        @classmethod
        @filter_method
        def class_filter(cls, obj):
            return str(obj)

        @staticmethod
        @filter_method
        def static_filter(obj):
            return str(obj)

        @filter_method
        def instance_filter(self, obj):
            return str(obj)


    @DemoGenerator.register_filter
    def function_filter(obj):
        return str(obj)


TEST_CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases/')


def casepath(relative_path):
    return os.path.join(TEST_CASES_DIR, relative_path)


XSD_TEST = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tns="http://xmlschema.test/ns" 
    targetNamespace="http://xmlschema.test/ns">
  <xs:element name="root" type="xs:string" />
  <xs:complexType name="type3">
    <xs:sequence>
      <xs:element name="elem1" type="tns:type1" />
      <xs:element name="elem2" type="tns:type2" />
    </xs:sequence>
  </xs:complexType>
  <xs:complexType name="type2">
    <xs:sequence>
      <xs:element name="elem1" type="tns:type1" />
      <xs:element name="elem4" type="tns:type4" />
    </xs:sequence>
  </xs:complexType>
  <xs:simpleType name="type4">
    <xs:restriction base="xs:string" />
  </xs:simpleType>
  <xs:complexType name="type1" />
</xs:schema>
"""


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestAbstractGenerator(unittest.TestCase):

    generator_class = DemoGenerator

    @classmethod
    def setUpClass(cls):
        cls.schema = XMLSchema10(XSD_TEST)
        cls.searchpath = Path(__file__).absolute().parent.joinpath('test_cases/templates/filters/')
        cls.generator = cls.generator_class(cls.schema, str(cls.searchpath))

    def test_initialization(self):
        generator = self.generator_class(self.schema)
        self.assertIs(generator.schema, self.schema)
        self.assertIsInstance(generator._env, jinja2.Environment)

    def test_formal_language(self):
        self.assertEqual(self.generator_class.formal_language, 'Demo')

    def test_builtin_types(self):
        generator = self.generator_class(self.schema)
        self.assertIn(XSD_ANY_TYPE, generator.builtin_types)
        self.assertIn(XSD_STRING, generator.builtin_types)
        self.assertIn(XSD_FLOAT, generator.builtin_types)
        self.assertIsNot(generator.builtin_types, generator.types_map)
        self.assertEqual(generator.builtin_types, generator.types_map)

    def test_language_type_filter(self):
        self.assertListEqual(self.generator.render('demo_type_filter_test.jinja'), ['str'])

    def test_filter_decorators(self):
        dt = datetime.datetime(1999, 12, 31, 23, 59, 59)

        if self.generator_class is DemoGenerator:
            demo_gen = DemoGenerator(self.schema)
            self.assertEqual(demo_gen.filters['instance_filter'](dt), '1999-12-31 23:59:59')
            self.assertEqual(demo_gen.filters['static_filter'](dt), '1999-12-31 23:59:59')
            self.assertEqual(demo_gen.filters['class_filter'](dt), '1999-12-31 23:59:59')
            self.assertEqual(demo_gen.filters['function_filter'](dt), '1999-12-31 23:59:59')
        else:
            with self.assertRaises(KeyError):
                self.generator.filters['instance_filter'](dt)

    def test_name_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['name'](xsd_element), 'root')
        self.assertListEqual(self.generator.render('name_filter_test.jinja'), ['root'])

    def test_qname_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['qname'](xsd_element), 'tns__root')
        self.assertListEqual(self.generator.render('qname_filter_test.jinja'), ['tns__root'])

    def test_namespace_filter(self):
        xsd_element = self.schema.elements['root']
        tns = 'http://xmlschema.test/ns'
        self.assertEqual(self.generator.filters['namespace'](xsd_element), tns)
        self.assertListEqual(self.generator.render('namespace_filter_test.jinja'), [tns])

    def test_type_name_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['type_name'](xsd_element), 'string')
        self.assertListEqual(self.generator.render('type_name_filter_test.jinja'), ['string'])

    def test_type_qname_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['type_qname'](xsd_element), 'xs__string')
        self.assertListEqual(
            self.generator.render('type_qname_filter_test.jinja'), ['xs__string'])

    def test_sort_types_filter(self):
        xsd_types = self.schema.types
        self.assertListEqual(
            self.generator.filters['sort_types'](xsd_types),
            [xsd_types['type4'], xsd_types['type1'], xsd_types['type2'], xsd_types['type3']]
        )
        self.assertListEqual(
            self.generator.render('sort_types_filter_test.jinja'), ['type4type1type2type3']
        )

    def test_extension_test(self):
        pass


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestPythonGenerator(TestAbstractGenerator):

    generator_class = PythonGenerator

    @classmethod
    def setUpClass(cls):
        super(TestPythonGenerator, cls).setUpClass()
        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')
        cls.col_schema = XMLSchema10(cls.col_xsd_file)

    def test_formal_language(self):
        self.assertEqual(PythonGenerator.formal_language, 'Python')

    def test_language_type_filter(self):
        self.assertListEqual(
            self.generator.render('python_type_filter_test.jinja'), ['str']
        )


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema code generators with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
