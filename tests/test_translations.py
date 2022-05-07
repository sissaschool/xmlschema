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

from xmlschema import XMLSchema, use_translation, translation


class TestTranslations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        XMLSchema.meta_schema.build()

    @classmethod
    def tearDownClass(cls):
        XMLSchema.meta_schema.clear()

    def test_use_translation(self):
        self.assertIsNone(translation._translation)
        try:
            use_translation()
            self.assertIsInstance(translation._translation, gettext.GNUTranslations)
        finally:
            translation._translation = None

    def test_it_translation(self):
        self.assertIsNone(translation._translation)
        try:
            use_translation(languages=['it'])
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "non è una ridefinizione!")
        finally:
            translation._translation = None

        try:
            use_translation(languages=['it', 'en'])
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "non è una ridefinizione!")

            use_translation(languages=['en', 'it'])
            result = translation.gettext("not a redefinition!")
            self.assertEqual(result, "not a redefinition!")
        finally:
            translation._translation = None


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema translations with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
