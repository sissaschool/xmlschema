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
"""Tests about static typing of xmlschema objects."""

import unittest
import subprocess
import re
from pathlib import Path

try:
    import mypy
except ImportError:
    mypy = None


@unittest.skipIf(mypy is None, "mypy is not installed")
class TestTyping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases_dir = Path(__file__).parent.joinpath('test_cases/mypy')
        cls.config_file = Path(__file__).parent.parent.joinpath('mypy.ini')
        cls.error_pattern = re.compile(r'Found \d+ error', re.IGNORECASE)

    def check_mypy_output(self, testfile, *options):
        cmd = ['mypy', '--config-file', str(self.config_file), testfile]
        if options:
            cmd.extend(str(opt) for opt in options)
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.assertEqual(process.stderr, b'')
        output = process.stdout.decode('utf-8').strip()
        output_lines = output.split('\n')

        self.assertGreater(len(output_lines), 0, msg=output)
        self.assertNotRegex(output_lines[-1], self.error_pattern, msg=output)
        return output_lines

    def test_schema_source(self):
        case_path = self.cases_dir.joinpath('schema_source.py')
        output_lines = self.check_mypy_output(case_path, '--strict', '--no-warn-unused-ignores')
        self.assertTrue(output_lines[0].startswith('Success:'), msg='\n'.join(output_lines))

    def test_simple_types(self):
        case_path = self.cases_dir.joinpath('simple_types.py')
        output_lines = self.check_mypy_output(case_path, '--strict', '--no-warn-unused-ignores')
        self.assertTrue(output_lines[0].startswith('Success:'), msg='\n'.join(output_lines))

    def test_extra_validator__issue_291(self):
        case_path = self.cases_dir.joinpath('extra_validator.py')
        output_lines = self.check_mypy_output(case_path, '--strict')
        self.assertTrue(output_lines[0].startswith('Success:'), msg='\n'.join(output_lines))


if __name__ == '__main__':
    unittest.main()
