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
import json
import os
import re
import importlib
import platform
import sys
import decimal
import subprocess

try:
    import memory_profiler
except ImportError:
    memory_profiler = None


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


@unittest.skipIf(memory_profiler is None or sys.version_info[:2] != (3, 7), "Test only with Python 3.7")
class TestMemoryUsage(unittest.TestCase):

    @staticmethod
    def check_memory_profile(output):
        """Check the output of a memory memory profile run on a function."""
        mem_usage = []
        func_num = 0
        for line in output.split('\n'):
            parts = line.split()
            if 'def' in parts:
                func_num += 1
            if not parts or not parts[0].isdigit() or len(parts) == 1 \
                    or not parts[1].replace('.', '').isdigit():
                continue
            mem_usage.append(decimal.Decimal(parts[1]))

        if func_num > 1:
            raise ValueError("Cannot the a memory profile output of more than one function!")
        return max(v - mem_usage[0] for v in mem_usage[1:])

    @unittest.skip
    def test_package_memory_usage(self):
        test_dir = os.path.dirname(__file__) or '.'
        cmd = [os.path.join(test_dir, 'check_memory.py'), '1']
        output = subprocess.check_output(cmd, universal_newlines=True)
        package_mem = self.check_memory_profile(output)
        self.assertLess(package_mem, 20)

    def test_element_tree_memory_usage(self):
        test_dir = os.path.dirname(__file__) or '.'
        xsd10_schema_file = os.path.join(
            os.path.dirname(os.path.abspath(test_dir)), 'validators/schemas/XSD_1.0/XMLSchema.xsd'
        )

        cmd = [os.path.join(test_dir, 'check_memory.py'), '2', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        parse_mem = self.check_memory_profile(output)

        cmd = [os.path.join(test_dir, 'check_memory.py'), '3', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        iterparse_mem = self.check_memory_profile(output)

        cmd = [os.path.join(test_dir, 'check_memory.py'), '4', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        lazy_iterparse_mem = self.check_memory_profile(output)

        self.assertLess(parse_mem, 2)
        self.assertLessEqual(lazy_iterparse_mem, parse_mem / 2)
        self.assertLessEqual(lazy_iterparse_mem, iterparse_mem)

    def test_decode_memory_usage(self):
        test_dir = os.path.dirname(__file__) or '.'
        xsd10_schema_file = os.path.join(
            os.path.dirname(os.path.abspath(test_dir)), 'validators/schemas/XSD_1.0/XMLSchema.xsd'
        )

        cmd = [os.path.join(test_dir, 'check_memory.py'), '5', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        decode_mem = self.check_memory_profile(output)

        cmd = [os.path.join(test_dir, 'check_memory.py'), '6', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        lazy_decode_mem = self.check_memory_profile(output)

        self.assertLess(decode_mem, 2)
        self.assertLessEqual(lazy_decode_mem, decode_mem / decimal.Decimal(1.5))

    def test_validate_memory_usage(self):
        test_dir = os.path.dirname(__file__) or '.'
        xsd10_schema_file = os.path.join(
            os.path.dirname(os.path.abspath(test_dir)), 'validators/schemas/XSD_1.0/XMLSchema.xsd'
        )

        cmd = [os.path.join(test_dir, 'check_memory.py'), '7', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        validate_mem = self.check_memory_profile(output)

        cmd = [os.path.join(test_dir, 'check_memory.py'), '8', xsd10_schema_file]
        output = subprocess.check_output(cmd, universal_newlines=True)
        lazy_validate_mem = self.check_memory_profile(output)

        self.assertLess(validate_mem, 2)
        self.assertLessEqual(lazy_validate_mem, validate_mem / 2)


@unittest.skipIf(platform.system() == 'Windows', "Skip packaging test on Windows platform.")
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
            'codepoints.py': [543],
        }

        message = "\nFound a debug missing statement at line %d or file %r: %r"
        filename = None
        file_excluded = []
        files = glob.glob(os.path.join(self.source_dir, '*.py')) + \
            glob.glob(os.path.join(self.source_dir, 'validators/*.py'))
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

    def test_json_unicode_categories(self):
        filename = os.path.join(self.source_dir, 'unicode_categories.json')
        self.assertTrue(os.path.isfile(filename), msg="file %r is missing!" % filename)
        with open(filename, 'r') as fp:
            self.assertIsInstance(json.load(fp), dict, msg="file %r is not encoded in JSON format!" % filename)

    def test_base_schema_files(self):
        et = importlib.import_module('xml.etree.ElementTree')
        schemas_dir = os.path.join(self.source_dir, 'validators/schemas')
        base_schemas = [
            'XSD_1.0/XMLSchema.xsd', 'XSD_1.1/XMLSchema.xsd', 'xhtml1-strict.xsd', 'xlink.xsd',
            'xml_minimal.xsd', 'XMLSchema-hasFacetAndProperty_minimal.xsd', 'XMLSchema-instance_minimal.xsd'
        ]
        for rel_path in base_schemas:
            filename = os.path.join(schemas_dir, rel_path)
            self.assertTrue(os.path.isfile(filename), msg="schema file %r is missing!" % filename)
            self.assertIsInstance(et.parse(filename), et.ElementTree)


if __name__ == '__main__':
    header1 = "Test package %r installation" % os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    header2 = "with Python {} on platform {}".format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{2}\n{0}'.format("*" * max(len(header1), len(header2)), header1, header2))

    unittest.main()
