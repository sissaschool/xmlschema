#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2018-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests for ElementTree import and for a pure-python version with a safe parser."""
import unittest
import os
import importlib
import sys
import subprocess
import platform


@unittest.skipIf(sys.version_info < (3,), "In Python 2 ElementTree is not overwritten by cElementTree")
class TestElementTree(unittest.TestCase):

    def test_element_string_serialization(self):
        ElementTree = importlib.import_module('xml.etree.ElementTree')
        xmlschema_etree = importlib.import_module('xmlschema.etree')

        elem = ElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        elem = xmlschema_etree.ElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        elem = xmlschema_etree.PyElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')

    def test_import_element_tree_before(self):
        ElementTree = importlib.import_module('xml.etree.ElementTree')
        xmlschema_etree = importlib.import_module('xmlschema.etree')

        self.assertIsNot(ElementTree.Element, ElementTree._Element_Py, msg="cElementTree not available!")
        elem = xmlschema_etree.PyElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        self.assertIs(importlib.import_module('xml.etree.ElementTree'), ElementTree)
        self.assertIs(xmlschema_etree.ElementTree, ElementTree)

    def test_import_element_tree_after(self):
        xmlschema_etree = importlib.import_module('xmlschema.etree')
        ElementTree = importlib.import_module('xml.etree.ElementTree')

        self.assertIsNot(ElementTree.Element, ElementTree._Element_Py, msg="cElementTree not available!")
        elem = xmlschema_etree.PyElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        self.assertIs(importlib.import_module('xml.etree.ElementTree'), ElementTree)
        self.assertIs(xmlschema_etree.ElementTree, ElementTree)

    @unittest.skipIf(platform.system() == 'Windows', "Run only for UNIX based systems.")
    def test_element_tree_import_script(self):
        test_dir = os.path.dirname(__file__) or '.'

        cmd = [os.path.join(test_dir, 'check_etree_import.py')]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = process.stdout.decode('utf-8')
        self.assertTrue("\nTest OK:" in output, msg="Wrong import of ElementTree after xmlschema")

        cmd.append('--before')
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = process.stdout.decode('utf-8')
        self.assertTrue("\nTest OK:" in output, msg="Wrong import of ElementTree before xmlschema")

    def test_safe_xml_parser(self):
        test_dir = os.path.dirname(__file__) or '.'
        xmlschema_etree = importlib.import_module('xmlschema.etree')
        parser = xmlschema_etree.SafeXMLParser(target=xmlschema_etree.PyElementTree.TreeBuilder())
        PyElementTree = xmlschema_etree.PyElementTree

        xml_file = os.path.join(test_dir, 'test_cases/resources/with_entity.xml')
        elem = xmlschema_etree.ElementTree.parse(xml_file).getroot()
        self.assertEqual(elem.text, 'abc')
        self.assertRaises(
            PyElementTree.ParseError, xmlschema_etree.ElementTree.parse, xml_file, parser=parser
        )

        xml_file = os.path.join(test_dir, 'test_cases/resources/unused_external_entity.xml')
        elem = xmlschema_etree.ElementTree.parse(xml_file).getroot()
        self.assertEqual(elem.text, 'abc')
        self.assertRaises(
            PyElementTree.ParseError, xmlschema_etree.ElementTree.parse, xml_file, parser=parser
        )

        xml_file = os.path.join(test_dir, 'test_cases/resources/external_entity.xml')
        self.assertRaises(xmlschema_etree.ParseError, xmlschema_etree.ElementTree.parse, xml_file)
        self.assertRaises(
            PyElementTree.ParseError, xmlschema_etree.ElementTree.parse, xml_file, parser=parser
        )


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
