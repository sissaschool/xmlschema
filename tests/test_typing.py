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
import importlib
import sys
from pathlib import Path

try:
    from mypy import api as mypy_api
except ImportError:
    mypy_api = None

try:
    lxml_stubs_module = importlib.import_module('lxml-stubs')
except ImportError:
    lxml_stubs_module = None


@unittest.skipIf(mypy_api is None, "mypy is not installed")
@unittest.skipIf(lxml_stubs_module is None, "lxml-stubs is not installed")
@unittest.skipIf(sys.version_info < (3, 8), "Python version < 3.8")
class TestTyping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cases_dir = Path(__file__).parent.joinpath('test_cases/mypy')
        cls.config_file = Path(__file__).parent.parent.joinpath('mypy.ini')

    def test_schema_source(self):
        result = mypy_api.run([
            '--strict',
            '--no-warn-unused-ignores',
            '--config-file', str(self.config_file),
            str(self.cases_dir.joinpath('schema_source.py'))
        ])
        self.assertEqual(result[2], 0, msg=result[1] or result[0])

    def test_simple_types(self):
        result = mypy_api.run([
            '--strict',
            '--no-warn-unused-ignores',
            '--config-file', str(self.config_file),
            str(self.cases_dir.joinpath('simple_types.py'))
        ])
        self.assertEqual(result[2], 0, msg=result[1] or result[0])

    def test_extra_validator__issue_291(self):
        result = mypy_api.run([
            '--strict',
            '--config-file', str(self.config_file),
            str(self.cases_dir.joinpath('extra_validator.py'))
        ])
        self.assertEqual(result[2], 0, msg=result[1] or result[0])


if __name__ == '__main__':
    unittest.main()
