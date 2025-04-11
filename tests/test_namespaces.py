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
import io
import unittest
import copy
from textwrap import dedent

from xmlschema import XMLResource, XMLSchemaConverter
from xmlschema.locations import get_locations
from xmlschema.names import XSD_NAMESPACE, XSI_NAMESPACE
from xmlschema.namespaces import NamespaceMapper, NamespaceResourcesMap


class TestNamespaceMapper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.xml_data = dedent("""\
            <root xmlns="http://example.test/foo">
               <elem1 xmlns="http://example.test/bar"/>
               <bar:elem2 xmlns:bar="http://example.test/bar"/>
               <elem3 xmlns="http://example.test/foo"/>
               <foo:elem4 xmlns:foo="http://example.test/foo"/>
               <foo:elem5 xmlns:foo="http://example.test/bar"/>
               <foo:elem6 xmlns:foo="http://example.test/foo2"/>
               <elem7 xmlns=""/>
            </root>""")

    def test_init(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper, namespaces)
        self.assertIsNot(namespaces, mapper.namespaces)

    def test_dictionary_methods(self):
        namespaces = dict(xs=XSD_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        mapper['xsi'] = XSI_NAMESPACE
        self.assertEqual(mapper, dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE))

        del mapper['xs']
        self.assertEqual(len(mapper), 1)
        self.assertEqual(mapper, dict(xsi=XSI_NAMESPACE))

        mapper.clear()
        self.assertEqual(mapper, {})

    def test_strip_namespaces_and_process_namespaces_arguments(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)

        mapper = NamespaceMapper(namespaces, strip_namespaces=False)
        self.assertFalse(mapper.strip_namespaces)
        self.assertTrue(mapper.process_namespaces)
        self.assertTrue(mapper._use_namespaces)
        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'xs:name')
        self.assertEqual(mapper.map_qname('{unknown}name'), '{unknown}name')

        mapper = NamespaceMapper(namespaces, strip_namespaces=True)
        self.assertTrue(mapper.strip_namespaces)
        self.assertTrue(mapper.process_namespaces)
        self.assertFalse(mapper._use_namespaces)
        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'name')
        self.assertEqual(mapper.map_qname('{unknown}name'), 'name')

        mapper = NamespaceMapper(namespaces, process_namespaces=True)
        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'xs:name')
        self.assertEqual(mapper.map_qname('{unknown}name'), '{unknown}name')

        mapper = NamespaceMapper(namespaces, process_namespaces=False)
        self.assertEqual(mapper.map_qname(f'{XSD_NAMESPACE}name'), f'{XSD_NAMESPACE}name')
        self.assertEqual(mapper.map_qname('{unknown}name'), '{unknown}name')

        mapper = NamespaceMapper(namespaces, process_namespaces=False, strip_namespaces=True)
        self.assertEqual(mapper.map_qname('{%s}name' % XSD_NAMESPACE), 'name')
        self.assertEqual(mapper.map_qname('{unknown}name'), 'name')

    def test_xmlns_processing_argument_with_resource(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        resource = XMLResource('<root/>')

        kwargs = {
            'namespaces': namespaces,
            'source': resource,
        }
        mapper = NamespaceMapper(**kwargs)
        self.assertEqual(mapper.xmlns_processing, 'stacked')
        self.assertIsNotNone(mapper._xmlns_getter)

        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper.xmlns_processing, 'none')
        self.assertIsNone(mapper._xmlns_getter)

        mapper = NamespaceMapper(xmlns_processing='collapsed', **kwargs)
        self.assertEqual(mapper.xmlns_processing, 'collapsed')
        self.assertIsNotNone(mapper._xmlns_getter)

        mapper = NamespaceMapper(xmlns_processing='root-only', **kwargs)
        self.assertEqual(mapper.xmlns_processing, 'root-only')
        self.assertIsNotNone(mapper._xmlns_getter)

        mapper = NamespaceMapper(xmlns_processing='none', **kwargs)
        self.assertEqual(mapper.xmlns_processing, 'none')
        self.assertIsNone(mapper._xmlns_getter)

    def test_xmlns_processing_argument_with_data_source(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)

        mapper = NamespaceMapper(namespaces, source=dict())
        self.assertEqual(mapper.xmlns_processing, 'none')
        self.assertIsNone(mapper._xmlns_getter)

        mapper = NamespaceMapper(namespaces, xmlns_processing='collapsed', source=dict())
        self.assertEqual(mapper.xmlns_processing, 'collapsed')
        self.assertIsNotNone(mapper._xmlns_getter)

        # None can be a valid decoded value in certain cases
        mapper = NamespaceMapper(namespaces, xmlns_processing='collapsed', source=None)
        self.assertEqual(mapper.xmlns_processing, 'collapsed')
        self.assertIsNotNone(mapper._xmlns_getter)

    def test_invalid_xmlns_processing_argument(self):
        with self.assertRaises(ValueError):
            NamespaceMapper(xmlns_processing='nothing')

        with self.assertRaises(TypeError):
            NamespaceMapper(xmlns_processing=False)

    def test_source_argument(self):
        resource = XMLResource('<root/>')
        mapper = NamespaceMapper(source=resource)
        self.assertIs(mapper.source, resource)
        self.assertIsNotNone(mapper._xmlns_getter)

        mapper = NamespaceMapper()
        self.assertIsNone(mapper.source)
        self.assertIsNone(mapper._xmlns_getter)

    def test_get_xmlns_from_data(self):
        self.assertIsNone(NamespaceMapper().get_xmlns_from_data({}))

    def test_get_namespaces(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        resource = XMLResource('<root xmlns="http://example.test/foo"/>')
        data = {'@xmlns:xs': "http://example.test/foo", 'value': [1, 2]}

        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper.get_namespaces(), {})

        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper.get_namespaces(namespaces), namespaces)

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked')
        self.assertEqual(mapper.get_namespaces(), {})

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked')
        self.assertEqual(mapper.get_namespaces(namespaces), namespaces)

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked', source=data)
        self.assertEqual(mapper.get_namespaces(), {})

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked', source=data)
        self.assertEqual(mapper.get_namespaces(namespaces), namespaces)

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked', source=resource)
        self.assertEqual(mapper.get_namespaces(), {'': 'http://example.test/foo'})

        mapper = NamespaceMapper(namespaces, xmlns_processing='stacked', source=resource)
        self.assertEqual(mapper.get_namespaces(namespaces),
                         {**namespaces, **{'': 'http://example.test/foo'}})

        mapper = XMLSchemaConverter(namespaces, xmlns_processing='stacked', source=data)
        self.assertEqual(mapper.get_namespaces(), {'xs': 'http://example.test/foo'})

        mapper = XMLSchemaConverter(namespaces, xmlns_processing='stacked', source=data)
        self.assertEqual(mapper.get_namespaces(namespaces),
                         {**namespaces, **{'xs0': 'http://example.test/foo'}})

    def test_copy(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)

        mapper = NamespaceMapper(namespaces, strip_namespaces=True)
        other = copy.copy(mapper)

        self.assertIsNot(mapper.namespaces, other.namespaces)
        self.assertDictEqual(mapper.namespaces, other.namespaces)

    def test_default_namespace(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        self.assertIsNone(mapper.default_namespace)
        mapper[''] = 'tns0'
        self.assertEqual(mapper.default_namespace, 'tns0')

    def test_map_qname(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        mapper[''] = XSD_NAMESPACE
        self.assertEqual(mapper.map_qname(''), '')
        self.assertEqual(mapper.map_qname('foo'), 'foo')
        self.assertEqual(mapper.map_qname('{%s}element' % XSD_NAMESPACE), 'element')
        mapper.pop('')
        self.assertEqual(mapper.map_qname('{%s}element' % XSD_NAMESPACE), 'xs:element')

        with self.assertRaises(ValueError) as ctx:
            mapper.map_qname('{%selement' % XSD_NAMESPACE)
        self.assertIn("invalid value", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            mapper.map_qname('{%s}element}' % XSD_NAMESPACE)
        self.assertIn("invalid value", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.map_qname(None)
        self.assertIn("must be a string-like object", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.map_qname(99)
        self.assertIn("must be a string-like object", str(ctx.exception))

        mapper = NamespaceMapper(namespaces, process_namespaces=False)
        self.assertEqual(mapper.map_qname('bar'), 'bar')
        self.assertEqual(mapper.map_qname('xs:bar'), 'xs:bar')

        mapper = NamespaceMapper(namespaces, strip_namespaces=True)
        self.assertEqual(mapper.map_qname('bar'), 'bar')
        self.assertEqual(mapper.map_qname('xs:bar'), 'bar')

    def test_unmap_qname(self):
        namespaces = dict(xs=XSD_NAMESPACE, xsi=XSI_NAMESPACE)
        mapper = NamespaceMapper(namespaces)

        self.assertEqual(mapper.unmap_qname(''), '')
        self.assertEqual(mapper.unmap_qname('xs:element'), '{%s}element' % XSD_NAMESPACE)
        self.assertEqual(mapper.unmap_qname('{foo}bar'), '{foo}bar')
        self.assertEqual(mapper.unmap_qname('xsd:element'), 'xsd:element')

        with self.assertRaises(ValueError) as ctx:
            mapper.unmap_qname('xs::element')
        self.assertIn("invalid value", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.unmap_qname(None)
        self.assertIn("must be a string-like object", str(ctx.exception))

        with self.assertRaises(TypeError) as ctx:
            mapper.unmap_qname(99)
        self.assertIn("must be a string-like object", str(ctx.exception))

        self.assertEqual(mapper.unmap_qname('element'), 'element')
        mapper[''] = 'foo'
        self.assertEqual(mapper.unmap_qname('element'), '{foo}element')
        self.assertEqual(mapper.unmap_qname('element', name_table=['element']), 'element')

        mapper.strip_namespaces = True  # don't do tricks, create a new instance ...
        self.assertEqual(mapper.unmap_qname('element'), '{foo}element')

        mapper = NamespaceMapper(namespaces, process_namespaces=False)
        self.assertEqual(mapper.unmap_qname('bar'), 'bar')
        self.assertEqual(mapper.unmap_qname('xs:bar'), 'xs:bar')

        mapper = NamespaceMapper(namespaces, strip_namespaces=True)
        self.assertEqual(mapper.unmap_qname('bar'), 'bar')
        self.assertEqual(mapper.unmap_qname('xs:bar'), 'bar')

        mapper = NamespaceMapper(namespaces)
        self.assertEqual(mapper.unmap_qname('foo:bar'), 'foo:bar')
        xmlns = [('foo', 'http://example.com/foo')]
        self.assertEqual(
            mapper.unmap_qname('foo:bar', xmlns=xmlns),
            '{http://example.com/foo}bar'
        )

    def test_set_context_with_stacked_xmlns_processing(self):
        resource = XMLResource(io.StringIO(self.xml_data))

        mapper = NamespaceMapper(source=resource)
        self.assertEqual(mapper.xmlns_processing, 'stacked')
        self.assertEqual(len(mapper._contexts), 0)

        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 1)
        self.assertIs(mapper._contexts[-1].obj, resource.root)
        self.assertEqual(mapper._contexts[-1].level, 0)
        self.assertIs(mapper._contexts[-1].xmlns, xmlns)
        self.assertEqual(mapper._contexts[-1].namespaces,
                         {'': 'http://example.test/foo'})
        self.assertEqual(mapper._contexts[-1].reverse,
                         {'http://example.test/foo': ''})
        self.assertListEqual(xmlns, [('', 'http://example.test/foo')])

        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 1)
        self.assertIs(mapper._contexts[-1].obj, resource.root)
        self.assertListEqual(xmlns, [('', 'http://example.test/foo')])

        mapper.set_context(resource.root[0], 1)
        self.assertEqual(len(mapper._contexts), 2)
        self.assertIs(mapper._contexts[-1].obj, resource.root[0])

        mapper.set_context(resource.root[1], 1)
        self.assertEqual(len(mapper._contexts), 2)
        self.assertIs(mapper._contexts[-1].obj, resource.root[1])

        resource = XMLResource('<root/>')

        mapper = NamespaceMapper(source=resource)
        self.assertEqual(mapper.xmlns_processing, 'stacked')
        self.assertEqual(len(mapper._contexts), 0)

        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 0)
        self.assertIsNone(xmlns)

    def test_set_context_with_collapsed_xmlns_processing(self):
        resource = XMLResource(io.StringIO(self.xml_data))

        mapper = NamespaceMapper(source=resource, xmlns_processing='collapsed')
        self.assertEqual(mapper.xmlns_processing, 'collapsed')

        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 0)
        self.assertIsNone(xmlns)
        self.assertEqual(mapper.namespaces, {'': 'http://example.test/foo'})

        mapper.set_context(resource.root[0], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar'})

        mapper.set_context(resource.root[1], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar'})

        mapper.set_context(resource.root[2], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar'})

        mapper.set_context(resource.root[3], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar',
                          'foo': 'http://example.test/foo'})

        mapper.set_context(resource.root[4], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar',
                          'foo': 'http://example.test/foo',
                          'foo0': 'http://example.test/bar'})

        mapper.set_context(resource.root[4], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar',
                          'foo': 'http://example.test/foo',
                          'foo0': 'http://example.test/bar'})

        mapper.set_context(resource.root[5], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar',
                          'foo': 'http://example.test/foo',
                          'foo0': 'http://example.test/bar',
                          'foo1': 'http://example.test/foo2'})

        mapper.set_context(resource.root[6], 1)
        self.assertEqual(mapper.namespaces,
                         {'': 'http://example.test/foo',
                          'default': 'http://example.test/bar',
                          'bar': 'http://example.test/bar',
                          'foo': 'http://example.test/foo',
                          'foo0': 'http://example.test/bar',
                          'foo1': 'http://example.test/foo2'})

        # With default namespaces in non-root elements
        xml_data = dedent("""\
                    <foo:root xmlns:foo="http://example.test/foo">
                       <elem1 xmlns="http://example.test/bar"/>
                       <elem2 xmlns="http://example.test/foo"/>
                    </foo:root>""")
        resource = XMLResource(io.StringIO(xml_data))

        mapper = NamespaceMapper(source=resource, xmlns_processing='collapsed')
        mapper.set_context(resource.root[0], 1)
        self.assertEqual(mapper.namespaces,
                         {'foo': 'http://example.test/foo',
                          'default': 'http://example.test/bar'})

        mapper = NamespaceMapper(source=resource, xmlns_processing='collapsed')
        mapper.set_context(resource.root[0], 0)
        self.assertEqual(mapper.namespaces,
                         {'foo': 'http://example.test/foo',
                          '': 'http://example.test/bar'})

        mapper = NamespaceMapper(source=resource, xmlns_processing='collapsed')
        mapper.set_context(resource.root[1], 0)
        self.assertEqual(mapper.namespaces,
                         {'foo': 'http://example.test/foo',
                          '': 'http://example.test/foo'})

    def test_set_context_with_root_only_xmlns_processing(self):
        resource = XMLResource(io.StringIO(self.xml_data))

        mapper = NamespaceMapper(source=resource, xmlns_processing='root-only')
        self.assertEqual(mapper.xmlns_processing, 'root-only')

        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 0)
        self.assertIsNone(xmlns)
        self.assertEqual(mapper.namespaces, {'': 'http://example.test/foo'})

        mapper.set_context(resource.root[0], 1)
        self.assertEqual(mapper.namespaces, {'': 'http://example.test/foo'})

    def test_set_context_with_none_xmlns_processing(self):
        resource = XMLResource(io.StringIO(self.xml_data))
        namespaces = {'foo': 'http://example.test/foo'}

        mapper = NamespaceMapper(source=resource, xmlns_processing='none')
        self.assertEqual(mapper.xmlns_processing, 'none')
        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(len(mapper._contexts), 0)
        self.assertIsNone(xmlns)
        self.assertEqual(mapper.namespaces, {})

        mapper = NamespaceMapper(namespaces, source=resource, xmlns_processing='none')
        xmlns = mapper.set_context(resource.root, 0)
        self.assertEqual(mapper.namespaces, namespaces)
        self.assertIsNone(xmlns)

    def test_set_context_with_encoding(self):
        mapper = NamespaceMapper()
        obj = {'@xmlns:foo': 'http://example.test/foo'}

        xmlns = mapper.set_context(obj, level=0)
        self.assertEqual(len(mapper._contexts), 0)
        self.assertIsNone(xmlns)


class TestNamespaceResourcesMap(unittest.TestCase):

    def test_init(self):
        nsmap = [('tns0', 'schema1.xsd')]
        self.assertEqual(NamespaceResourcesMap(), {})
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd']})
        nsmap.append(('tns0', 'schema2.xsd'))
        self.assertEqual(NamespaceResourcesMap(nsmap), {'tns0': ['schema1.xsd', 'schema2.xsd']})

    def test_repr(self):
        namespaces = NamespaceResourcesMap()
        namespaces['tns0'] = 'schema1.xsd'
        namespaces['tns1'] = 'schema2.xsd'
        self.assertEqual(repr(namespaces), "{'tns0': ['schema1.xsd'], 'tns1': ['schema2.xsd']}")

    def test_dictionary_methods(self):
        namespaces = NamespaceResourcesMap()
        namespaces['tns0'] = 'schema1.xsd'
        namespaces['tns1'] = 'schema2.xsd'
        self.assertEqual(namespaces, {'tns0': ['schema1.xsd'], 'tns1': ['schema2.xsd']})

        self.assertEqual(len(namespaces), 2)
        self.assertEqual({x for x in namespaces}, {'tns0', 'tns1'})

        del namespaces['tns0']
        self.assertEqual(namespaces, {'tns1': ['schema2.xsd']})
        self.assertEqual(len(namespaces), 1)

        namespaces.clear()
        self.assertEqual(namespaces, {})

    def test_copy(self):
        namespaces = NamespaceResourcesMap(
            (('tns0', 'schema1.xsd'), ('tns1', 'schema2.xsd'), ('tns0', 'schema3.xsd'))
        )
        self.assertEqual(namespaces, namespaces.copy())

    def test_get_locations(self):
        self.assertEqual(get_locations(None), NamespaceResourcesMap())
        self.assertRaises(TypeError, get_locations, 1)
        locations = (('tns0', 'schema1.xsd'), ('tns1', 'schema2.xsd'), ('tns0', 'schema3.xsd'))

        self.assertEqual(get_locations(locations), NamespaceResourcesMap(locations))


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('helpers for namespaces')
