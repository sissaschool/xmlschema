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

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.names import XSD_ELEMENT, XSD_STRING, XSD_SIMPLE_TYPE


class TestXsdGlobalsMaps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema10.meta_schema.build()
        XMLSchema11.meta_schema.build()

    @classmethod
    def tearDownClass(cls):
        XMLSchema10.meta_schema.clear()
        XMLSchema11.meta_schema.clear()

    def test_maps_repr(self):
        self.assertEqual(
            repr(XMLSchema10.meta_schema.maps),
            "XsdGlobals(validator=MetaXMLSchema10(name='XMLSchema.xsd', "
            "namespace='http://www.w3.org/2001/XMLSchema'), validation='strict')"
        )

    def test_lookup(self):
        with self.assertRaises(KeyError):
            XMLSchema10.meta_schema.maps.lookup(XSD_ELEMENT, 'wrong')

        xs_string = XMLSchema10.meta_schema.maps.lookup(XSD_SIMPLE_TYPE, XSD_STRING)
        self.assertEqual(xs_string.name, XSD_STRING)

        with self.assertRaises(ValueError):
            XMLSchema10.meta_schema.maps.lookup('simpleType', XSD_STRING)

    def test_clear(self):
        maps = XMLSchema10.meta_schema.maps.copy()

        self.assertEqual(len(list(maps.iter_globals())), 158)

        maps.clear(only_unbuilt=True)
        self.assertEqual(len(list(maps.iter_globals())), 158)

        maps.clear()
        self.assertEqual(len(list(maps.iter_globals())), 0)
        maps.build()
        self.assertEqual(len(list(maps.iter_globals())), 158)

        maps.clear(remove_schemas=True)
        self.assertEqual(len(list(maps.iter_globals())), 0)
        with self.assertRaises(ValueError):
            maps.build()  # missing XSD meta-schema

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
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attributes), 14)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.attribute_groups), 4)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.groups), 13)
        self.assertEqual(len(XMLSchema11.meta_schema.maps.elements), 47)
        self.assertEqual(
            len([e.is_global() for e in XMLSchema11.meta_schema.maps.iter_globals()]), 183
        )
        self.assertEqual(len(XMLSchema11.meta_schema.maps.substitution_groups), 1)

    def test_xsd_10_build(self):
        self.assertEqual(len([e for e in XMLSchema10.meta_schema.maps.iter_globals()]), 158)
        self.assertTrue(XMLSchema10.meta_schema.maps.built)
        XMLSchema10.meta_schema.maps.clear()
        XMLSchema10.meta_schema.maps.build()
        self.assertTrue(XMLSchema10.meta_schema.maps.built)

    def test_xsd_11_build(self):
        self.assertEqual(len([e for e in XMLSchema11.meta_schema.maps.iter_globals()]), 183)
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
        self.assertEqual(global_counter, 183)
        self.assertEqual(total_counter, 972)

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
