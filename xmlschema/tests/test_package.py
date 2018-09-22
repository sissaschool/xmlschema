#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Tests concerning packaging and installation environment.
"""
import unittest
import importlib
import glob
import fileinput
import os
import re
import sys

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.etree import defused_etree, etree_tostring

# Import ElementTree and defusedxml.ElementTree
import xml.etree.ElementTree as ElementTree         # Original module with C extensions
defused_etree.fromstring('<A/>')                    # Lazy import of defusedxml.ElementTree
import xml.etree.ElementTree as PyElementTree       # Pure Python import


class TestEnvironment(unittest.TestCase):

    def test_element_tree(self):
        self.assertNotEqual(ElementTree.Element, ElementTree._Element_Py, msg="cElementTree not available!")
        elem = PyElementTree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element />')
        self.assertEqual(importlib.import_module('xml.etree.ElementTree'), ElementTree)

    def test_pure_python_element_tree(self):
        if sys.version_info >= (3,):
            self.assertEqual(PyElementTree.Element, PyElementTree._Element_Py)  # C extensions disabled by defusedxml
            self.assertNotEqual(ElementTree.Element, PyElementTree.Element)
        else:
            self.assertNotEqual(PyElementTree.Element, PyElementTree._Element_Py)

        elem = PyElementTree.Element('element')
        self.assertEqual(etree_tostring(elem), '<element />')

    def test_defused_etree(self):
        self.assertEqual(defused_etree.element_tree, PyElementTree)
        self.assertEqual(defused_etree.etree_element, PyElementTree.Element)


class TestPackaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.source_dir = os.path.dirname(cls.test_dir)
        cls.package_dir = os.path.dirname(cls.source_dir)
        if not cls.package_dir.endswith('/xmlschema'):
            cls.package_dir = None

        cls.missing_debug = re.compile(r"(\bimport\s+pdb\b|\bpdb\s*\.\s*set_trace\(\s*\)|\bprint\s*\()")
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


if __name__ == '__main__':

    unittest.main()
