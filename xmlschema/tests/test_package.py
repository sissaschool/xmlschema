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
import unittest
import glob
import fileinput
import os
import re


class TestPackage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)
        cls.source_dir = os.path.dirname(cls.test_dir)
        cls.package_dir = os.path.dirname(cls.source_dir)
        if not os.path.dirname(cls.package_dir).endswith('/xmlschema'):
            cls.package_dir = None

        cls.missing_debug = re.compile(r"(\bimport\s+pdb\b|\bpdb\s*\.\s*set_trace\(\s*\)|\bprint\s*\()")
        cls.get_version = re.compile(r"(?:\bversion|__version__)(?:\s*=\s*)(\'[^\']*\'|\"[^\"]*\")")

    def test_missing_debug_statements(self):
        # Exclude explicit debug statements written in the code
        exclude = {
            'regex.py': [236, 237],
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
        message = "\nFound a different version at line %d or file %r: %r (maybe %r)."

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
