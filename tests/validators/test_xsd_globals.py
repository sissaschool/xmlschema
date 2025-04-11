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
from typing import Any

from xmlschema import XMLSchema10, XMLSchema11
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
        components: Any = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(components, 'tns1')
        self.assertEqual(ns_view, {'name1': 1})

    def test_repr(self):
        qnames: Any = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns0')
        self.assertEqual(repr(ns_view), "NamespaceView({'name0': 0})")

    def test_getitem(self):
        qnames: Any = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns1')

        self.assertEqual(ns_view['name1'], 1)

        with self.assertRaises(KeyError):
            ns_view['name0']  # noqa

    def test_contains(self):
        qnames: Any = {'{tns0}name0': 0, '{tns1}name1': 1, 'name2': 2}
        ns_view = NamespaceView(qnames, 'tns1')

        self.assertIn('name1', ns_view)
        self.assertNotIn('{tns1}name1', ns_view)
        self.assertNotIn('{tns0}name0', ns_view)
        self.assertNotIn('name0', ns_view)
        self.assertNotIn('name2', ns_view)
        self.assertNotIn(1, ns_view)

    def test_as_dict(self):
        qnames: Any = {'{tns0}name0': 0, '{tns1}name1': 1, '{tns1}name2': 2, 'name3': 3}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertEqual(ns_view.as_dict(), {'name1': 1, 'name2': 2})

        ns_view = NamespaceView(qnames, '')
        self.assertEqual(ns_view.as_dict(), {'name3': 3})

    def test_iter(self):
        qnames: Any = {'{tns0}name0': 0, '{tns1}name1': 1, '{tns1}name2': 2, 'name3': 3}
        ns_view = NamespaceView(qnames, 'tns1')
        self.assertListEqual(list(ns_view), ['name1', 'name2'])
        ns_view = NamespaceView(qnames, '')
        self.assertListEqual(list(ns_view), ['name3'])


class TestXsd10GlobalsMaps(unittest.TestCase):

    schema_class = XMLSchema10

    @classmethod
    def setUpClass(cls):
        cls.schema_class.meta_schema.build()
        cls.total_globals = cls.schema_class.meta_schema.maps.global_maps.total
        cls.total_components = len(list(cls.schema_class.meta_schema.maps.iter_components()))

    @classmethod
    def tearDownClass(cls):
        cls.schema_class.meta_schema.clear()

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
        maps = self.schema_class.meta_schema.maps.copy()
        orig = self.schema_class.meta_schema.maps

        self.assertIsNot(maps, orig)
        for name in ('types', 'attributes', 'elements', 'groups', 'attribute_groups',
                     'notations', 'identities', 'substitution_groups'):
            self.assertIsNot(getattr(maps, name), getattr(orig, name))

        self.assertEqual(maps.validation, orig.validation)
        self.assertIsNot(maps.validator, orig.validator)
        self.assertEqual(maps.global_maps.total, 0)

        self.assertEqual(len(maps.namespaces), len(orig.namespaces))
        for k, v in orig.namespaces.items():
            self.assertIn(k, maps.namespaces)
            self.assertEqual(len(maps.namespaces[k]), len(v))

        maps.build()
        self.assertEqual(maps.global_maps.total, self.total_globals)

    def test_clear(self):
        maps = self.schema_class.meta_schema.maps.copy()
        orig = self.schema_class.meta_schema.maps

        self.assertEqual(maps.global_maps.total, 0)
        self.assertEqual(orig.global_maps.total, self.total_globals)

        maps.build()
        self.assertEqual(maps.global_maps.total, self.total_globals)
        self.assertEqual(orig.global_maps.total, self.total_globals)
        maps.clear()
        self.assertEqual(maps.global_maps.total, 0)
        self.assertEqual(orig.global_maps.total, self.total_globals)
        maps.build()
        self.assertEqual(maps.global_maps.total, self.total_globals)
        self.assertEqual(orig.global_maps.total, self.total_globals)

        maps.clear(remove_schemas=True)
        self.assertEqual(maps.global_maps.total, 0)
        self.assertEqual(orig.global_maps.total, self.total_globals)

        # XSD meta-schema is still there but incomplete
        self.assertEqual(len(maps.schemas), 1)

        maps.build()
        self.assertEqual(maps.global_maps.total, self.total_globals)
        self.assertEqual(orig.global_maps.total, self.total_globals)

    def test_totals(self):
        self.assertEqual(len(XMLSchema10.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.types), 92)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attributes), 8)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.attribute_groups), 3)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.groups), 12)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.elements), 41)
        self.assertEqual(
            len([e.is_global() for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158
        )
        self.assertEqual(self.total_components, 809)
        self.assertEqual(len(XMLSchema10.meta_schema.maps.substitution_groups), 0)

    def test_build(self):
        self.assertEqual(len([
            e for e in self.schema_class.meta_schema.maps.iter_globals()
        ]), self.total_globals)
        self.assertTrue(self.schema_class.meta_schema.maps.built)
        self.schema_class.meta_schema.maps.clear()
        self.schema_class.meta_schema.maps.build()
        self.assertTrue(self.schema_class.meta_schema.maps.built)

    def test_components(self):
        total_counter = 0
        global_counter = 0
        for g in self.schema_class.meta_schema.maps.iter_globals():
            for c in g.iter_components():
                total_counter += 1
                if c.is_global():
                    global_counter += 1
        self.assertEqual(global_counter, self.total_globals)
        # self.assertEqual(total_counter, self.total_components)


class TestXsd11GlobalsMaps(TestXsd10GlobalsMaps):

    schema_class = XMLSchema11

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def test_totals(self):
        self.assertEqual(len(XMLSchema11.meta_schema.maps.notations), 2)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.types), 103)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attributes), 10)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attribute_groups), 4)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.groups), 13)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.elements), 47)
        self.assertEqual(
            len([e.is_global() for e in XMLSchema11.meta_schema.maps.iter_globals()]), 179
        )
        self.assertEqual(self.total_globals, 179)
        self.assertEqual(self.total_components, 965)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.substitution_groups), 1)

    def test_xsd_11_restrictions(self):
        all_model_type = self.schema_class.meta_schema.types['all']
        self.assertTrue(
            all_model_type.content.is_restriction(all_model_type.base_type.content)
        )


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('global maps')
