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
"""Tests about the packaging of the code"""

import unittest
import glob
import fileinput
import os
import re
import importlib


class TestPackaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.package_dir = os.path.dirname(cls.test_dir)
        cls.source_dir = os.path.join(cls.package_dir, 'xmlschema')
        cls.missing_debug = re.compile(
            r"(\bimport\s+pdb\b|\bpdb\s*\.\s*set_trace\(\s*\)|\bprint\s*\()|\bbreakpoint\s*\("
        )
        cls.get_version = re.compile(r"(?:\brelease|__version__)(?:\s*=\s*)(\'[^\']*\'|\"[^\"]*\")")

    def test_missing_debug_statements(self):
        # Exclude explicit debug statements written in the code
        exclude = {
            'regex.py': [240, 241],
            'codepoints.py': [534],
            'cli.py': [117, 133, 137, 140],
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
            if match is None or filename.endswith('/cli.py') and match.group(0) == 'print(':
                continue
            self.assertIsNone(match, message % (lineno, filename, match.group(0)))

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

    def test_base_schema_files(self):
        et = importlib.import_module('xml.etree.ElementTree')
        schemas_dir = os.path.join(self.source_dir, 'schemas')
        base_schemas = [
            'XSD_1.0/XMLSchema.xsd',
            'XSD_1.1/XMLSchema.xsd',
            'XHTML/xhtml1-strict.xsd',
            'XLINK/xlink.xsd',
            'XML/xml_minimal.xsd',
            'HFP/XMLSchema-hasFacetAndProperty_minimal.xsd',
            'XSI/XMLSchema-instance_minimal.xsd'
        ]
        for rel_path in base_schemas:
            filename = os.path.join(schemas_dir, rel_path)
            self.assertTrue(os.path.isfile(filename), msg="schema file %r is missing!" % filename)
            self.assertIsInstance(et.parse(filename), et.ElementTree)


if __name__ == '__main__':
    import platform
    header_template = "Packaging tests for xmlschema with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
