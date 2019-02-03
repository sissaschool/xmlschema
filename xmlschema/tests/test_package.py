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
import unittest
import glob
import fileinput
import os
import re
import importlib
import sys
import subprocess


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

    @unittest.skipIf(sys.version_info[:2] == (3, 4), "Python 3.4 doesn't have subprocess.run API")
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


class TestPackaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.source_dir = os.path.dirname(cls.test_dir)
        cls.package_dir = os.path.dirname(cls.source_dir)
        if not cls.package_dir.endswith('/xmlschema'):
            cls.package_dir = None

        cls.missing_debug = re.compile(
            r"(\bimport\s+pdb\b|\bpdb\s*\.\s*set_trace\(\s*\)|\bprint\s*\()|\bbreakpoint\s*\("
        )
        cls.get_version = re.compile(r"(?:\brelease|__version__)(?:\s*=\s*)(\'[^\']*\'|\"[^\"]*\")")

    def test_missing_debug_statements(self):
        # Exclude explicit debug statements written in the code
        exclude = {
            'regex.py': [240, 241],
        }

        message = "\nFound a debug missing statement at line %d or file %r: %r"
        filename = None
        file_excluded = []
        files = (
            glob.glob(os.path.join(self.source_dir, '*.py')) +
            glob.glob(os.path.join(self.source_dir, 'validators/*.py'))
        )

        for line in fileinput.input(files):
            if fileinput.isfirstline():
                filename = fileinput.filename()
                file_excluded = exclude.get(os.path.basename(filename), [])
            lineno = fileinput.filelineno()

            if lineno in file_excluded:
                continue

            match = self.missing_debug.search(line)
            self.assertIsNone(match, message % (lineno, filename, match.group(0) if match else None))

    def test_version(self):
        message = "\nFound a different version at line %d or file %r: %r (may be %r)."

        files = [os.path.join(self.source_dir, '__init__.py')]
        if self.package_dir is not None:
            files.extend([
                os.path.join(self.package_dir, 'setup.py'),
                os.path.join(self.package_dir, 'doc/conf.py'),
            ])
        version = filename = None
        for line in fileinput.input(files):
            if fileinput.isfirstline():
                filename = fileinput.filename()
            lineno = fileinput.filelineno()

            match = self.get_version.search(line)
            if match is not None:
                if version is None:
                    version = match.group(1).strip('\'\"')
                else:
                    self.assertTrue(
                        version == match.group(1).strip('\'\"'),
                        message % (lineno, filename, match.group(1).strip('\'\"'), version)
                    )


# TODO: Add tests for checking base schemas files and other package files.


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
