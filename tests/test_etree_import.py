#!/usr/bin/env python
#
# Copyright (c), 2018-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
import os
import sys
import importlib
import subprocess
import platform


def is_element_tree_imported():
    return '_elementtree' in sys.modules or 'xml.etree.ElementTree' in sys.modules


@unittest.skipUnless(platform.python_implementation() == 'CPython', "requires CPython")
class TestElementTreeImport(unittest.TestCase):
    """
    Test ElementTree imports using external script or with single-run import tests.
    For running a single-run import test use one of these commands:

      python -m unittest  tests/test_etree_import.py -k <pattern>
      python tests/test_etree_import.py -k <pattern>

    The pattern must match only one test method to be effective, because the import
    test can be executed once for each run.

    Example:

      python -m unittest tests/test_etree_import.py -k before

    """

    @unittest.skipUnless(platform.system() == 'Linux', "requires Linux")
    def test_element_tree_import_script(self):
        test_dir = os.path.dirname(__file__) or '.'

        cmd = [sys.executable, os.path.join(test_dir, 'check_etree_import.py')]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stderr = process.stderr.decode('utf-8')
        self.assertTrue("ModuleNotFoundError" not in stderr,
                        msg="Test script fails because a package is missing:\n\n{}".format(stderr))

        self.assertIn("\nTest OK:", process.stdout.decode('utf-8'),
                      msg="Wrong import of ElementTree after xmlschema:\n\n{}".format(stderr))

        cmd.append('--before')
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertTrue("\nTest OK:" in process.stdout.decode('utf-8'),
                        msg="Wrong import of ElementTree before xmlschema:\n\n{}".format(stderr))

    def test_import_etree_after(self):
        if is_element_tree_imported():
            return  # skip if ElementTree is already imported

        xmlschema_etree = importlib.import_module('xmlschema.etree')
        ElementTree = importlib.import_module('xml.etree.ElementTree')

        self.assertIsNot(ElementTree.Element, ElementTree._Element_Py,
                         msg="cElementTree not available!")
        elem = xmlschema_etree.PyElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        self.assertIs(importlib.import_module('xml.etree.ElementTree'), ElementTree)
        self.assertIs(importlib.import_module('xml.etree').ElementTree, ElementTree)
        self.assertIs(xmlschema_etree.ElementTree, ElementTree)

    def test_import_etree_before(self):
        if is_element_tree_imported():
            return  # skip if ElementTree is already imported

        ElementTree = importlib.import_module('xml.etree.ElementTree')
        xmlschema_etree = importlib.import_module('xmlschema.etree')

        self.assertIsNot(ElementTree.Element, ElementTree._Element_Py,
                         msg="cElementTree not available!")
        elem = xmlschema_etree.PyElementTree.Element('element')
        self.assertEqual(xmlschema_etree.etree_tostring(elem), '<element />')
        self.assertIs(importlib.import_module('xml.etree.ElementTree'), ElementTree)
        self.assertIs(importlib.import_module('xml.etree').ElementTree, ElementTree)
        self.assertIs(xmlschema_etree.ElementTree, ElementTree)

    def test_inconsistent_etree(self):
        if is_element_tree_imported():
            return  # skip if ElementTree is already imported

        importlib.import_module('xml.etree.ElementTree')
        sys.modules.pop('xml.etree.ElementTree')

        with self.assertRaises(RuntimeError) as ctx:
            importlib.import_module('xmlschema')
        self.assertIn('Inconsistent status for ElementTree module', str(ctx.exception))


if __name__ == '__main__':
    header_template = "ElementTree import tests for xmlschema with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
