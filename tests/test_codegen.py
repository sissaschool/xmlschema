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
import datetime
import ast
import platform
from pathlib import Path
from textwrap import dedent
from xmlschema import XMLSchema10, XMLSchema11
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
    from xmlschema.extras.codegen import filter_method, AbstractGenerator

    class DemoGenerator(AbstractGenerator):
        formal_language = 'Demo'

        searchpaths = ['templates/demo']

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

        @staticmethod
        def not_a_static_filter(obj):
            return

        def not_an_instance_filter(self):
            return


    class PythonGenerator(AbstractGenerator):
        """
        Python code sample generator for XSD schemas.
        """
        formal_language = 'Python'

        searchpaths = ['templates/python/']

        builtin_types = {
            'string': 'str',
            'boolean': 'bool',
            'float': 'float',
            'double': 'float',
            'integer': 'int',
            'unsignedByte': 'int',
            'nonNegativeInteger': 'int',
            'positiveInteger': 'int',
        }


def casepath(relative_path):
    return str(Path(__file__).absolute().parent.joinpath('test_cases', relative_path))


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
        cls.searchpath = Path(__file__).absolute().parent.joinpath('templates/filters/')
        cls.generator = cls.generator_class(cls.schema, str(cls.searchpath))

        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')
        cls.col_schema = XMLSchema10(cls.col_xsd_file)

    def test_formal_language(self):
        self.assertEqual(self.generator_class.formal_language, 'Demo')

        with self.assertRaises(ValueError) as ec:
            type('DemoGenerator2', (DemoGenerator,),
                 dict(__module__=__file__, formal_language='Demo2'))
        self.assertIn("formal_language cannot be changed", str(ec.exception))

        class DemoGenerator2(AbstractGenerator):
            formal_language = 'Demo2'

        self.assertEqual(DemoGenerator2.formal_language, 'Demo2')

        with self.assertRaises(ValueError) as ec:
            type('DemoGenerator3', (DemoGenerator, DemoGenerator2),
                 dict(__module__=__file__))
        self.assertIn("ambiguous formal_language", str(ec.exception))

        DemoGenerator2.formal_language = 'Demo'

        class DemoGenerator3(DemoGenerator, DemoGenerator2):
            pass

        self.assertEqual(DemoGenerator3.formal_language, 'Demo')

    @unittest.skipIf(platform.system() == 'Windows',
                     'Avoiding unnecessary tests on Windows file paths ...')
    def test_searchpaths(self):
        self.assertIsInstance(DemoGenerator.searchpaths, list)
        self.assertTrue(str(DemoGenerator.searchpaths[0]).endswith('templates/demo'))

        with self.assertRaises(ValueError) as ec:
            type('DemoGenerator2', (AbstractGenerator,),
                 dict(__module__=__file__, searchpaths=['/not-a-dir']))
        self.assertIn("path '/not-a-dir' is not a directory!", str(ec.exception))

    def test_schema_argument(self):
        generator = self.generator_class(self.schema)
        class_name = generator.__class__.__name__
        namespace = 'http://xmlschema.test/ns'

        self.assertIs(generator.schema, self.schema)
        self.assertIsInstance(generator._env, jinja2.Environment)
        self.assertEqual(repr(generator), "{}(namespace={!r})".format(class_name, namespace))

        generator = self.generator_class(self.col_xsd_file)
        self.assertIsInstance(generator.schema, XMLSchema11)
        self.assertEqual(repr(generator), "{}(schema='collection.xsd')".format(class_name))

    def test_searchpath_argument(self):
        class DemoGenerator2(AbstractGenerator):
            formal_language = 'Demo2'

        with self.assertRaises(ValueError) as ec:
            DemoGenerator2(self.schema)
        self.assertIn("no search paths defined!", str(ec.exception))

        generator = DemoGenerator2(self.schema, '/tmp')
        self.assertIsInstance(generator._env.loader, jinja2.loaders.FileSystemLoader)

    def test_types_map_argument(self):
        types_map = {'foo': 'int', 'bar': 'str'}
        generator = self.generator_class(self.schema, types_map=types_map)
        self.assertNotIn('foo', generator.types_map)
        self.assertIn('{http://xmlschema.test/ns}foo', generator.types_map)
        self.assertIn(XSD_ANY_TYPE, generator.types_map)

        xsd_source = dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
              <xs:simpleType name="str32">
                <xs:restriction base="xs:string">
                  <xs:maxLength value="32"/>
                </xs:restriction>
              </xs:simpleType>
            </xs:schema>
            """)

        types_map = {'str32': 'String32'}
        generator = self.generator_class(xsd_source, types_map=types_map)
        self.assertIn('str32', generator.types_map)

    def test_builtin_types(self):
        generator = self.generator_class(self.schema)
        self.assertIn(XSD_ANY_TYPE, generator.builtin_types)
        self.assertIn(XSD_STRING, generator.builtin_types)
        self.assertIn(XSD_FLOAT, generator.builtin_types)
        self.assertIsNot(generator.builtin_types, generator.types_map)
        self.assertEqual(generator.builtin_types, generator.types_map)

    def test_list_templates(self):
        template_dir = Path(__file__).parent.joinpath('templates')
        language = self.generator_class.formal_language.lower()

        templates = set(x.name for x in template_dir.glob('{}/*'.format(language)))
        templates.update(x.name for x in template_dir.glob('filters/*'.format(language)))
        self.assertSetEqual(set(self.generator.list_templates()), templates)

    def test_matching_templates(self):
        self.assertSetEqual(set(self.generator.matching_templates('name*_filter*')),
                            {'name_filter_test.jinja', 'namespace_filter_test.jinja'})

    def test_get_template(self):
        template = self.generator.get_template('type_qname_filter_test.jinja')
        self.assertIsInstance(template, jinja2.Template)

        with self.assertRaises(jinja2.TemplateNotFound):
            self.generator.get_template('foo')

    def test_select_template(self):
        template = self.generator.select_template(['foo', 'qname_filter_test.jinja'])
        self.assertIsInstance(template, jinja2.Template)

        with self.assertRaises(jinja2.TemplateNotFound):
            self.generator.select_template(['foo'])

    def test_render(self):
        self.assertListEqual(self.generator.render('name_filter_test.jinja'), ['root'])
        self.assertListEqual(
            self.generator.render(['name_filter_test.jinja', 'namespace_filter_test.jinja']),
            ['root', 'http://xmlschema.test/ns']
        )

        with self.assertRaises(TypeError):
            self.generator.render(['name_filter_test.jinja', False])

        with self.assertRaises(jinja2.TemplateSyntaxError):
            self.generator.render(['wrong-template.jinja'])

    def test_language_type_filter(self):
        self.assertListEqual(self.generator.render('demo_type_filter_test.jinja'), ['str'])

        type4 = self.schema.types['type4']
        self.assertEqual(self.generator.filters['demo_type'](type4), 'str')

        generator = DemoGenerator(self.schema, types_map={'type4': 'demo_string'})
        self.assertEqual(generator.filters['demo_type'](type4), 'demo_string')

        class DemoGenerator2(DemoGenerator):
            @filter_method
            def demo_type(self, _):
                return 'foo'

        generator = DemoGenerator2(self.schema)
        self.assertEqual(generator.filters['demo_type'](type4), 'foo')

        generator = DemoGenerator2(self.schema, types_map={'type4': 'demo_string'})
        self.assertEqual(generator.filters['demo_type'](type4), 'foo')

    def test_filter_decorators(self):
        dt = datetime.datetime(1999, 12, 31, 23, 59, 59)

        if self.generator_class is DemoGenerator:
            demo_gen = DemoGenerator(self.schema)
            self.assertEqual(demo_gen.filters['instance_filter'](dt), '1999-12-31 23:59:59')
            self.assertEqual(demo_gen.filters['static_filter'](dt), '1999-12-31 23:59:59')
            self.assertEqual(demo_gen.filters['class_filter'](dt), '1999-12-31 23:59:59')
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
        return


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestPythonGenerator(TestAbstractGenerator):

    generator_class = PythonGenerator

    def test_formal_language(self):
        self.assertEqual(PythonGenerator.formal_language, 'Python')

    def test_language_type_filter(self):
        self.assertListEqual(
            self.generator.render('python_type_filter_test.jinja'), ['str']
        )

    def test_sample_module(self):
        generator = PythonGenerator(self.col_xsd_file)

        python_module = generator.render('sample.py.jinja')[0]
        ast_module = ast.parse(python_module)
        self.assertIsInstance(ast_module, ast.Module)


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema code generators with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
