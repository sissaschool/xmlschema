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
import warnings

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.validators.exceptions import XMLSchemaParseError
from xmlschema.namespaces import NamespaceView
import xmlschema.names as nm


class TestGlobalMapsViews(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema10.meta_schema.build()
        cls.comp0 = XMLSchema10.meta_schema.maps.types[nm.XSD_STRING]
        cls.comp1 = XMLSchema10.meta_schema.maps.types[nm.XSD_DOUBLE]
        cls.comp2 = XMLSchema10.meta_schema.maps.types[nm.XSD_INT]

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()

    def test_init(self):
        components = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(components, 'tns1')
        self.assertEqual(ns_view, {'name1': 1})

    def test_repr(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns0')
        self.assertEqual(repr(ns_view), "NamespaceView({'name0': 0})")

    def test_getitem(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns1')

        self.assertEqual(ns_view['name1'], 1)

        with self.assertRaises(KeyError):
            ns_view['name0']

    def test_contains(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns1')

        self.assertIn('name1', ns_view)
        self.assertNotIn('{tns1}name1', ns_view)
        self.assertNotIn('{tns0}name0', ns_view)
        self.assertNotIn('name0', ns_view)
        self.assertNotIn('name2', ns_view)
        self.assertNotIn(1, ns_view)

    def test_as_dict(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, '{tns1}name2': 2, 'name3': 3}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertEqual(ns_view.as_dict(), {'name1': 1, 'name2': 2})

        ns_view = NamespaceView(qnames, '')
        self.assertEqual(ns_view.as_dict(), {'name3': 3})

    def test_iter(self):
        qnames = {'{tns0}name0': 0, '{tns1}name1': 1, '{tns1}name2': 2, 'name3': 3}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertListEqual(list(ns_view), ['name1', 'name2'])
        ns_view = NamespaceView(qnames, '')
        self.assertListEqual(list(ns_view), ['name3'])


class TestXsdGlobalsMaps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema10.meta_schema.build()
        XMLSchema11.meta_schema.build()
        cls.tot_xsd10_components = XMLSchema10.meta_schema.maps.total_globals
        cls.tot_xsd11_components = XMLSchema11.meta_schema.maps.total_globals

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()
        XMLSchema11.meta_schema.clear()

    def test_maps_repr(self):
        self.assertEqual(
            repr(XMLSchema10.meta_schema.maps),
            "XsdGlobals(validator=MetaXMLSchema10(name='XMLSchema.xsd', "
            "namespace='http://www.w3.org/2001/XMLSchema'))"
        )

    def test_lookup(self):
        with self.assertRaises(KeyError):
            XMLSchema10.meta_schema.maps.lookup(nm.XSD_ELEMENT, 'wrong')

        xs_string = XMLSchema10.meta_schema.maps.lookup(nm.XSD_SIMPLE_TYPE, nm.XSD_STRING)
        self.assertEqual(xs_string.name, nm.XSD_STRING)

        with self.assertRaises(ValueError):
            XMLSchema10.meta_schema.maps.lookup('simpleType', nm.XSD_STRING)

    def test_deprecated_api(self):
        with warnings.catch_warnings(record=True) as ctx:
            warnings.simplefilter("always")

            maps_dir = dir(XMLSchema10.meta_schema.maps)
            for k, name in enumerate(filter(lambda x: x.startswith('lookup_'), maps_dir)):
                with self.assertRaises(KeyError):
                    getattr(XMLSchema10.meta_schema.maps, name)('wrong')

                self.assertEqual(len(ctx), k+1)
                self.assertEqual(ctx[k].category, DeprecationWarning)
                self.assertIn('will be removed in v5.0', ctx[k].message.args[0])

    def test_copy(self):
        maps = XMLSchema10.meta_schema.maps.copy()
        orig = XMLSchema10.meta_schema.maps

        self.assertIsNot(maps, orig)
        for name in ('types', 'attributes', 'elements', 'groups', 'attribute_groups',
                     'notations', 'identities', 'substitution_groups'):
            self.assertIsNot(getattr(maps, name), getattr(orig, name))

        self.assertEqual(maps.validation, orig.validation)
        self.assertIsNot(maps.validator, orig.validator)
        self.assertIsNot(maps.loader, orig.loader)
        self.assertEqual(maps.total_globals, 0)

        self.assertEqual(len(maps.namespaces), len(orig.namespaces))
        for k, v in orig.namespaces.items():
            self.assertIn(k, maps.namespaces)
            self.assertEqual(len(maps.namespaces[k]), len(v))

        maps.build()
        self.assertEqual(maps.total_globals, self.tot_xsd10_components)

    def test_clear(self):
        maps = XMLSchema10.meta_schema.maps.copy()
        orig = XMLSchema10.meta_schema.maps

        self.assertEqual(len(list(maps.iter_globals())), 0)
        self.assertEqual(len(list(orig.iter_globals())), 158)

        maps.build()
        self.assertEqual(len(list(maps.iter_globals())), 158)
        maps.clear()
        self.assertEqual(len(list(maps.iter_globals())), 0)
        maps.build()
        self.assertEqual(len(list(maps.iter_globals())), 158)

        maps.clear(remove_schemas=True)
        self.assertEqual(len(list(maps.iter_globals())), 0)
        with self.assertRaises(XMLSchemaParseError):
            maps.build()  # XSD meta-schema is still there but incomplete

        maps.clear()
        maps.loader.load_namespace(nm.XML_NAMESPACE)
        maps.build()

        self.assertEqual(maps.total_globals, 154)  # missing XSI namespace
        self.assertEqual(XMLSchema10.meta_schema.maps.total_globals, 158)

    def test_xsd_10_globals(self):
        self.assertEqual(len(XMLSchema10.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.types), 92)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attributes), 8)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attribute_groups), 3)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.groups), 12)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.elements), 41)
        self.assertEqual(
            len([e.is_global() for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158
        )
        self.assertEqual(len(XMLSchema10.meta_schema.maps.substitution_groups), 0)

    def test_xsd_11_globals(self):
        self.assertEqual(len(XMLSchema11.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.types), 103)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attributes), 8)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attribute_groups), 4)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.groups), 13)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.elements), 47)
        self.assertEqual(
            len([e.is_global() for e in XMLSchema11.meta_schema.maps.iter_globals()]), 177
        )
        self.assertEqual(len(XMLSchema11.meta_schema.maps.substitution_groups), 1)

    def test_xsd_10_build(self):
        self.assertEqual(len([e for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158)
        self.assertTrue(XMLSchema10.meta_schema.maps.built)
        XMLSchema10.meta_schema.maps.clear()
        XMLSchema10.meta_schema.maps.build()
        self.assertTrue(XMLSchema10.meta_schema.maps.built)

    def test_xsd_11_build(self):
        self.assertEqual(len([e for e in XMLSchema11.meta_schema.maps.iter_globals()]), 177)
        self.assertTrue(XMLSchema11.meta_schema.maps.built)
        XMLSchema11.meta_schema.maps.clear()
        XMLSchema11.meta_schema.maps.build()
        self.assertTrue(XMLSchema11.meta_schema.maps.built)

    def test_xsd_10_components(self):
        total_counter = 0
        global_counter = 0
        for g in XMLSchema10.meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global():
                    global_counter += 1
        self.assertEqual(global_counter, 158)
        self.assertEqual(total_counter, 808)

    def test_xsd_11_components(self):
        total_counter = 0
        global_counter = 0
        for g in XMLSchema11.meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global():
                    global_counter += 1
        self.assertEqual(global_counter, 177)
        self.assertEqual(total_counter, 962)

    def test_xsd_11_restrictions(self):
        all_model_type = XMLSchema11.meta_schema.types['all']
        self.assertTrue(
            all_model_type.content.is_restriction(all_model_type.base_type.content)
        )


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's global maps with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
