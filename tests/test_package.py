#!/usr/bin/env python
#
# Copyright (c), 2018-2026, SISSA (International School for Advanced Studies).
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
import platform
import pathlib
from itertools import chain


class TestPackaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.package_dir = os.path.dirname(cls.test_dir)
        cls.source_dir = os.path.join(cls.package_dir, 'xmlschema')
        cls.missing_debug = re.compile(
            r"(\bimport\s+pdb\b|\bpdb\s*\.\s*set_trace\(\s*\)|\bprint\s*\()|\bbreakpoint\s*\("
        )
        cls.get_copyright_info = re.compile(
            r"(Copyright\s\(c\),\s(?:\d{4}-)?(\d{4}), SISSA)"
        )
        cls.get_version = re.compile(r"(?:\brelease|__version__)\s*=\s*(\'[^\']*\'|\"[^\"]*\")")

    def test_forgotten_debug_statements(self):
        # Exclude explicit debug statements written in the code
        exclude = {
            'cli.py': ['print('],
        }

        message = "\nFound a debug missing statement at line %d or file %r: %r"
        filename = None
        file_excluded = []
        files = glob.glob(os.path.join(self.source_dir, '*.py')) + \
            glob.glob(os.path.join(self.source_dir, 'validators/*.py')) + \
            glob.glob(os.path.join(self.source_dir, 'converters/*.py'))
        for line in fileinput.input(files):
            if fileinput.isfirstline():
                filename = fileinput.filename()
                file_excluded = exclude.get(os.path.basename(filename), [])
            lineno = fileinput.filelineno()

            if lineno in file_excluded:
                continue

            match = self.missing_debug.search(line)
            if match is None or match.group(0) in file_excluded:
                continue
            self.assertIsNone(match, message % (lineno, filename, match.group(0)))

    @unittest.skipIf(platform.system() == 'Windows', 'Skip on Windows platform')
    def test_wrong_copyright_info(self):
        message = "\nFound a wrong copyright info at line %d of file %r: %r"
        source_files = chain(pathlib.Path(self.package_dir).glob('LICENSE'),
                             pathlib.Path(self.source_dir).glob('**/*.py'),
                             pathlib.Path(self.package_dir).glob('tests/*.py'))
        package_dir = pathlib.Path(self.package_dir)
        year = '2026'

        wrong_copyright_count = 0
        for line in fileinput.input(source_files):
            match = self.get_copyright_info.search(line)
            if match and match.groups()[1] != year:
                filepath = pathlib.Path(fileinput.filename()).relative_to(package_dir)
                lineno = fileinput.filelineno()
                print(message % (lineno, str(filepath), match.groups()[0]), end='')
                wrong_copyright_count += 1
                continue
        else:
            self.assertEqual(wrong_copyright_count, 0, msg="Found wrong copyright info")

    def test_version(self):
        message = "\nFound a different version at line %d or file %r: %r (may be %r)."

        files = [os.path.join(self.source_dir, '__init__.py')]
        if self.package_dir is not None:
            files.extend([
                os.path.join(self.package_dir, 'pyproject.toml'),
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
            'DSIG/xmldsig11-schema.xsd',
            'DSIG/xmldsig-core-schema.xsd',
            'VC/XMLSchema-versioning.xsd',
            'WSDL/soap-encoding.xsd',
            'WSDL/soap-envelope.xsd',
            'WSDL/wsdl.xsd',
            'WSDL/wsdl-soap.xsd',
            'XENC/xenc-schema.xsd',
            'XENC/xenc-schema-11.xsd',
        ]
        for rel_path in base_schemas:
            filename = os.path.join(schemas_dir, rel_path)
            self.assertTrue(os.path.isfile(filename), msg="schema file %r is missing!" % filename)
            self.assertIsInstance(et.parse(filename), et.ElementTree)


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('packaging')
