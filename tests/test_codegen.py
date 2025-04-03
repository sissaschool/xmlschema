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
import ast
import logging
import platform
import importlib.util
import tempfile
from collections import namedtuple
from pathlib import Path
from textwrap import dedent
from xml.etree import ElementTree

from elementpath import datatypes

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
    from xmlschema.extras.codegen import filter_method, AbstractGenerator, PythonGenerator

    class DemoGenerator(AbstractGenerator):
        formal_language = 'Demo'

        searchpaths = ['templates/demo']

        builtin_types = {
            'string': 'str',
            'boolean': 'bool',
            'float': 'float',
            'double': 'double',
            'integer': 'int',
            'decimal': 'float',
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


def casepath(relative_path):
    return str(Path(__file__).absolute().parent.joinpath('test_cases', relative_path))


XSD_TEST = """\
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tns="http://xmlschema.test/ns"
    targetNamespace="http://xmlschema.test/ns">

  <xs:import /> <!-- for resolving local names in tests -->
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
      <xs:element name="elem4" type="tns:type4" maxOccurs="10" />
    </xs:sequence>
  </xs:complexType>

  <xs:simpleType name="type4">
    <xs:restriction base="xs:string" />
  </xs:simpleType>

  <xs:complexType name="type1" />

  <xs:simpleType name="type5">
    <xs:restriction base="xs:decimal" />
  </xs:simpleType>

  <xs:simpleType name="type6">
    <xs:restriction base="xs:float" />
  </xs:simpleType>

</xs:schema>
"""


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestAbstractGenerator(unittest.TestCase):

    schema_class = XMLSchema10
    generator_class = DemoGenerator

    schema: XMLSchema10
    searchpath: Path
    col_dir: str
    col_xsd_file: str
    col_xml_file: str
    col_schema: XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.schema = cls.schema_class(XSD_TEST)
        cls.searchpath = Path(__file__).absolute().parent.joinpath('templates/filters/')
        cls.generator = cls.generator_class(cls.schema, str(cls.searchpath))

        cls.col_dir = casepath('examples/collection')
        cls.col_xsd_file = casepath('examples/collection/collection.xsd')
        cls.col_xml_file = casepath('examples/collection/collection.xml')
        cls.col_schema = cls.schema_class(cls.col_xsd_file)

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
        self.assertEqual(repr(generator), f"{class_name}(namespace={namespace!r})")

        generator = self.generator_class(self.col_xsd_file)
        self.assertIsInstance(generator.schema, XMLSchema11)
        self.assertEqual(repr(generator), f"{class_name}(schema='collection.xsd')")

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

        templates = {x.name for x in template_dir.glob(f'{language}/*')}
        templates.update(x.name for x in template_dir.glob('filters/*'))
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

        logger = logging.getLogger('xmlschema-codegen')

        with self.assertLogs(logger, level=logging.DEBUG):
            self.generator.render('unknown')

    def test_render_to_files(self):
        with tempfile.TemporaryDirectory() as outdir:
            files = self.generator.render_to_files('name_filter_test.jinja', output_dir=outdir)
            self.assertListEqual(files, [os.path.join(outdir, 'name_filter_test')])

            files = self.generator.render_to_files(
                ['name_filter_test.jinja', 'namespace_filter_test.jinja'], output_dir=outdir)
            self.assertListEqual(files, [os.path.join(outdir, 'namespace_filter_test')])

        with tempfile.TemporaryDirectory() as outdir:
            files = self.generator.render_to_files(
                ['name_filter_test.jinja', 'namespace_filter_test.jinja'], output_dir=outdir
            )
            self.assertSetEqual(set(files), {
                os.path.join(outdir, 'name_filter_test'),
                os.path.join(outdir, 'namespace_filter_test'),
            })

        with tempfile.TemporaryDirectory() as outdir:
            files = self.generator.render_to_files('name*', output_dir=outdir)

            self.assertSetEqual(set(files), {
                os.path.join(outdir, 'name_filter_test'),
                os.path.join(outdir, 'namespace_filter_test'),
            })

        with tempfile.TemporaryDirectory() as outdir:
            with self.assertRaises(TypeError):
                self.generator.render_to_files(
                    ['name_filter_test.jinja', False], output_dir=outdir)

            with self.assertRaises(jinja2.TemplateSyntaxError):
                self.generator.render_to_files(['wrong-template.jinja'], output_dir=outdir)

            logger = logging.getLogger('xmlschema-codegen')

            with self.assertLogs(logger, level=logging.DEBUG):
                with self.assertRaises(jinja2.TemplateSyntaxError):
                    self.generator.render_to_files('*', output_dir=outdir)

            with self.assertLogs(logger, level=logging.DEBUG):
                self.generator.render_to_files('unknown', output_dir=outdir)

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

    def test_map_type(self):
        self.assertEqual(self.generator.map_type(None), '')
        self.assertEqual(self.generator.map_type(self.schema.elements['root']), 'str')
        self.assertEqual(self.generator.map_type(self.schema.types['type1']), '')
        self.assertEqual(self.generator.map_type(self.schema.types['type2']), '')
        self.assertEqual(self.generator.map_type(self.schema.types['type4']), 'str')
        self.assertEqual(self.generator.map_type(self.schema.types['type5']), 'float')
        self.assertEqual(self.generator.map_type(self.schema.types['type6']), 'float')

        date_type = self.schema.meta_schema.types['date']
        self.assertEqual(self.generator.map_type(date_type), '')

    def test_name_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['name'](xsd_element), 'root')
        self.assertListEqual(self.generator.render('name_filter_test.jinja'), ['root'])

        self.assertEqual(self.generator.name(None), 'none')
        self.assertEqual(self.generator.name(''), '')
        self.assertEqual(self.generator.name('foo'), 'foo')
        self.assertEqual(self.generator.name('{http://xmlschema.test/ns}foo'), 'foo')
        self.assertEqual(self.generator.name('ns:foo'), 'foo')
        self.assertEqual(self.generator.name('0:foo'), '')
        self.assertEqual(self.generator.name('1'), 'none')

        FakeElement = namedtuple('XsdElement', 'local_name name')
        fake_element = FakeElement(1, 2)
        self.assertEqual(self.generator.name(fake_element), '')

    def test_qname_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['qname'](xsd_element), 'tns__root')
        self.assertListEqual(self.generator.render('qname_filter_test.jinja'), ['tns__root'])

        self.assertEqual(self.generator.qname(None), 'none')
        self.assertEqual(self.generator.qname(''), '')
        self.assertEqual(self.generator.qname('{wrong'), 'none')
        self.assertEqual(self.generator.qname('foo'), 'foo')
        self.assertEqual(self.generator.qname('{http://xmlschema.test/ns}foo'), 'tns__foo')
        self.assertEqual(self.generator.qname('{http://unknown.test/ns}foo'), 'foo')
        self.assertEqual(self.generator.qname('ns:foo'), 'ns__foo')
        self.assertEqual(self.generator.qname('0:foo'), 'none')
        self.assertEqual(self.generator.qname('1'), 'none')

    def test_namespace_filter(self):
        xsd_element = self.schema.elements['root']
        tns = 'http://xmlschema.test/ns'
        self.assertEqual(self.generator.filters['namespace'](xsd_element), tns)
        self.assertListEqual(self.generator.render('namespace_filter_test.jinja'), [tns])

        self.assertEqual(self.generator.namespace(None), '')
        self.assertEqual(self.generator.namespace(''), '')
        self.assertEqual(self.generator.namespace('{wrong'), '')
        self.assertEqual(self.generator.namespace('foo'), '')
        self.assertEqual(self.generator.namespace('{bar}foo'), 'bar')
        self.assertEqual(self.generator.namespace('tns:foo'), 'http://xmlschema.test/ns')
        self.assertEqual(self.generator.namespace('0:foo'), '')
        self.assertEqual(self.generator.namespace('1'), '')

        qname = datatypes.QName('http://xmlschema.test/ns', 'tns:foo')
        self.assertEqual(self.generator.namespace(qname), 'http://xmlschema.test/ns')

    def test_type_name_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['type_name'](xsd_element), 'string')
        self.assertListEqual(self.generator.render('type_name_filter_test.jinja'), ['string'])

        self.assertEqual(self.generator.type_name(None), 'none')

        unnamed_type = self.col_schema.types['objType'].content[5].type
        self.assertEqual(self.generator.type_name(unnamed_type), 'none')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:complexType name="a_type"/>
                <xs:complexType name="bType"/>
                <xs:complexType name="c"/>
                <xs:complexType name="c-1"/>
                <xs:complexType name="c.2"/>
            </xs:schema>"""))

        self.assertEqual(self.generator.type_name(schema.types['a_type']), 'a')
        self.assertEqual(self.generator.type_name(schema.types['bType']), 'b')
        self.assertEqual(self.generator.type_name(schema.types['c']), 'c')

        self.assertEqual(self.generator.type_name(schema.types['a_type'], suffix='Type'), 'aType')
        self.assertEqual(self.generator.type_name(schema.types['bType'], suffix='Type'), 'bType')
        self.assertEqual(self.generator.type_name(schema.types['c'], suffix='Type'), 'cType')

        self.assertEqual(self.generator.type_name(schema.types['c-1']), 'c_1')
        self.assertEqual(self.generator.type_name(schema.types['c.2']), 'c_2')

    def test_type_qname_filter(self):
        xsd_element = self.schema.elements['root']
        self.assertEqual(self.generator.filters['type_qname'](xsd_element), 'xs__string')
        self.assertListEqual(
            self.generator.render('type_qname_filter_test.jinja'), ['xs__string'])

        self.assertEqual(self.generator.type_qname(None), 'none')

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                    xmlns:tns="http://xmlschema.test/ns"
                    targetNamespace="http://xmlschema.test/ns">
               <xs:complexType name="a_type"/>
               <xs:complexType name="bType"/>
               <xs:complexType name="c"/>
               <xs:complexType name="c-1"/>
               <xs:complexType name="c.2"/>
            </xs:schema>"""))

        self.assertEqual(self.generator.type_qname(schema.types['a_type']), 'tns__a')
        self.assertEqual(self.generator.type_qname(schema.types['bType']), 'tns__b')
        self.assertEqual(self.generator.type_qname(schema.types['c']), 'tns__c')

        self.assertEqual(self.generator.type_qname(schema.types['a_type'], suffix='Type'),
                         'tns__aType')
        self.assertEqual(self.generator.type_qname(schema.types['bType'], suffix='Type'),
                         'tns__bType')
        self.assertEqual(self.generator.type_qname(schema.types['c'], suffix='Type'),
                         'tns__cType')

        self.assertEqual(self.generator.type_qname(schema.types['c-1']), 'tns__c_1')
        self.assertEqual(self.generator.type_qname(schema.types['c.2']), 'tns__c_2')

    def test_sort_types_filter(self):
        xsd_types = self.schema.types
        sorted_types = [xsd_types['type4'], xsd_types['type5'], xsd_types['type6'],
                        xsd_types['type1'], xsd_types['type2'], xsd_types['type3']]

        self.assertListEqual(
            self.generator.filters['sort_types'](xsd_types), sorted_types
        )
        self.assertListEqual(
            self.generator.filters['sort_types'](xsd_types.values()), sorted_types
        )
        self.assertListEqual(
            self.generator.filters['sort_types'](list(xsd_types.values())), sorted_types
        )

        self.assertListEqual(
            self.generator.render('sort_types_filter_test.jinja'),
            ['type4type5type6type1type2type3']
        )

        schema = self.schema_class(dedent("""\
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">

                <xs:complexType name="type1">
                    <xs:sequence>
                        <xs:element name="elem1" type="xs:string" />
                        <xs:element name="elem2" type="type2" />
                    </xs:sequence>
                </xs:complexType>

                <xs:complexType name="type2">
                    <xs:sequence>
                        <xs:element name="elem1" type="type1" />
                        <xs:element name="elem2" type="xs:string" />
                    </xs:sequence>
                </xs:complexType>

            </xs:schema>"""))

        with self.assertRaises(ValueError) as ec:
            self.generator.sort_types(schema.types)
        self.assertIn("circularity found", str(ec.exception))

        self.assertListEqual(
            self.generator.sort_types(schema.types, accept_circularity=True),
            list(schema.types.values())
        )

    def test_unknown_filter(self):
        logger = logging.getLogger('xmlschema-codegen')

        with self.assertLogs(logger, level=logging.DEBUG):
            self.assertListEqual(self.generator.render('unknown_filter_test.jinja'), [])

    def test_is_derivation(self):
        self.assertFalse(self.generator.extension(self.schema.types['type1']))
        self.assertFalse(self.generator.extension(self.schema.types['type1'], 'tns:type1'))
        self.assertFalse(self.generator.restriction(self.schema.types['type1'], 'tns:type1'))
        self.assertTrue(self.generator.derivation(self.schema.types['type1'], 'type1'))
        self.assertFalse(self.generator.restriction(self.schema.types['type6'], 'xs:decimal'))
        self.assertFalse(self.generator.restriction(self.schema.types['type6'], None))
        self.assertFalse(self.generator.derivation(self.schema.types['type1'], 'tns0:type1'))

        self.assertTrue(self.generator.derivation(self.schema.types['type1'], 'tns:type1'))
        self.assertTrue(self.generator.restriction(self.schema.types['type6'], 'xs:float'))

        self.assertFalse(self.generator.is_derived(
            self.schema.types['type1'], '{http://xmlschema.test/ns}foo'
        ))
        self.assertFalse(self.generator.is_derived(
            self.schema.types['type1'], '{http://xmlschema.test/ns}bar'
        ))
        self.assertFalse(self.generator.is_derived(self.schema.types['type1'], 'bar', 'foo'))

    def test_multi_sequence(self):
        self.assertFalse(self.generator.multi_sequence(self.schema.types['type3']))
        self.assertTrue(self.generator.multi_sequence(self.schema.types['type2']))
        self.assertFalse(self.generator.multi_sequence(self.schema.types['type5']))


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestAbstractGenerator11(TestAbstractGenerator):
    schema_class = XMLSchema11


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestPythonGenerator(TestAbstractGenerator):

    generator_class = PythonGenerator

    def test_formal_language(self):
        self.assertEqual(PythonGenerator.formal_language, 'Python')

    def test_map_type(self):
        self.assertEqual(self.generator.map_type(None), '')
        self.assertEqual(self.generator.map_type(self.schema.elements['root']), 'str')
        self.assertEqual(self.generator.map_type(self.schema.types['type1']), '')
        self.assertEqual(self.generator.map_type(self.schema.types['type2']), '')
        self.assertEqual(self.generator.map_type(self.schema.types['type4']), 'str')
        self.assertEqual(self.generator.map_type(self.schema.types['type5']), 'decimal.Decimal')
        self.assertEqual(self.generator.map_type(self.schema.types['type6']), 'float')

    def test_language_type_filter(self):
        self.assertListEqual(
            self.generator.render('python_type_filter_test.jinja'), ['str']
        )

    def test_list_templates(self):
        template_dir = Path(__file__).parent.joinpath('templates')

        templates = {'sample.py.jinja', 'bindings.py.jinja'}
        templates.update(x.name for x in template_dir.glob('filters/*'))
        self.assertSetEqual(set(self.generator.list_templates()), templates)

    def test_sample_module(self):
        generator = PythonGenerator(self.col_xsd_file)

        python_module = generator.render('sample.py.jinja')[0]
        ast_module = ast.parse(python_module)
        self.assertIsInstance(ast_module, ast.Module)

    def test_bindings_module(self):
        generator = PythonGenerator(self.col_xsd_file)

        python_module = generator.render('bindings.py.jinja')[0]

        ast_module = ast.parse(python_module)
        self.assertIsInstance(ast_module, ast.Module)

        collection_dir = Path(__file__).parent.joinpath('test_cases/examples/collection')
        cwd = os.getcwd()
        try:
            os.chdir(str(collection_dir))
            with open('collection.py', 'w') as fp:
                fp.write(python_module)

            spec = importlib.util.spec_from_file_location('collection', 'collection.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except SyntaxError:
            pass
        else:
            col_data = module.CollectionBinding.fromsource('collection.xml')
            col_root = ElementTree.XML(col_data.tostring())
            self.assertEqual(col_root.tag, '{http://example.com/ns/collection}collection')
        finally:
            os.chdir(cwd)


@unittest.skipIf(jinja2 is None, "jinja2 library is not installed!")
class TestPythonGenerator11(TestPythonGenerator):
    schema_class = XMLSchema11


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('code generators')
