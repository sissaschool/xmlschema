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
"""Tests on internal helper functions"""
import unittest
import gettext

from xmlschema import XMLSchema, translation


class TestTranslations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema.meta_schema.build()
        cls.translation_classes = (gettext.NullTranslations,  # in case of fallback
                                   gettext.GNUTranslations)

    @classmethod
    def tearDownClass(cls):
        XMLSchema.meta_schema.clear()

    def test_activation(self):
        self.assertIsNone(translation._translation)
        try:
            translation.activate()
            self.assertIsInstance(translation._translation, self.translation_classes)
        finally:
            translation._translation = None

    def test_deactivation(self):
        self.assertIsNone(translation._translation)
        try:
            translation.activate()
            self.assertIsInstance(translation._translation, self.translation_classes)
            translation.deactivate()
            self.assertIsNone(translation._translation)
        finally:
            translation._translation = None

    def test_install(self):
        import builtins

        self.assertIsNone(translation._translation)
        self.assertFalse(translation._installed)

        try:
            translation.activate(install=True)
            self.assertIsInstance(translation._translation, self.translation_classes)
            self.assertTrue(translation._installed)
            self.assertEqual(builtins.__dict__['_'], translation._translation.gettext)

            translation.deactivate()
            self.assertIsNone(translation._translation)
            self.assertFalse(translation._installed)
            self.assertNotIn('_', builtins.__dict__)
        finally:
            translation._translation = None
            translation._installed = False
            builtins.__dict__.pop('_', None)

    def test_it_translation(self):
        self.assertIsNone(translation._translation)
        try:
            translation.activate(languages=['it'])
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "non è una ridefinizione!")
        finally:
            translation._translation = None

        try:
            translation.activate(languages=['it', 'en'])
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "non è una ridefinizione!")

            translation.activate(languages=['en', 'it'])
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "not a redefinition!")
        finally:
            translation._translation = None

    def test_pl_translation(self):
        self.assertIsNone(translation._translation)
        try:
            translation.activate(languages=['pl'])
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
            result = translation.gettext("The content of element %r is not complete.")
            self.assertEqual(result, "Zawartość elementu %r nie jest kompletna.")
        finally:
            translation._translation = None

        try:
            translation.activate(languages=['pl', 'en'])
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
            result = translation.gettext("The content of element %r is not complete.")
            self.assertEqual(result, "Zawartość elementu %r nie jest kompletna.")
        finally:
            translation._translation = None

    def test_pl_validation_translation(self):
        xml_path = "tests//test_cases//translations//pl//tytul_wykonawczy_niekompletny.xml"
        xsd_path = "tests//test_cases//translations//pl//tw-1(5)8e.xsd"
        expected_errors = [
            "Zawartość elementu 'com:Opisowy' nie jest kompletna. "
            "Oczekiwany znacznik 'com:Miejscowosc'.",
            "atrybut rodzaj='8': wartość musi być jedną z [1, 2]",
            "Zawartość elementu 'com:Beneficjent' nie jest kompletna. "
            "Oczekiwany znacznik 'com:NrRachunkuPL'.",
        ]
        try:
            translation.activate(languages=['pl'])
            schema = XMLSchema(
                xsd_path,
                defuse="never",
                validation="lax",
            )
            errors = [error.reason for error in schema.iter_errors(xml_path)]
            assert errors == expected_errors
        finally:
            translation._translation = None


if __name__ == '__main__':
    import platform

    header_template = "Test xmlschema translations with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
