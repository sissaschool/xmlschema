#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests of console scripts."""
import unittest
from unittest.mock import patch
import glob
import io
import pathlib
import os
import platform
import sys

from xmlschema.cli import validate, xml2json, json2xml
from xmlschema import to_json

WORK_DIRECTORY = os.getcwd()


class TestConsoleScripts(unittest.TestCase):
    ctx = None

    def run_validate(self, *args):
        with patch.object(sys, 'argv', ['xmlschema-validate'] + list(args)):
            with self.assertRaises(SystemExit) as self.ctx:
                validate()

    def run_xml2json(self, *args):
        with patch.object(sys, 'argv', ['xmlschema-xml2json'] + list(args)):
            with self.assertRaises(SystemExit) as self.ctx:
                xml2json()

    def run_json2xml(self, *args):
        with patch.object(sys, 'argv', ['xmlschema-json2xml'] + list(args)):
            with self.assertRaises(SystemExit) as self.ctx:
                json2xml()

    def setUp(self):
        vehicles_dir = pathlib.Path(__file__).parent.joinpath('test_cases/examples/vehicles/')
        os.chdir(str(vehicles_dir))

    def tearDown(self):
        os.chdir(WORK_DIRECTORY)

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_01(self, mock_out, mock_err):
        self.run_validate()
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("the following arguments are required", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_02(self, mock_out, mock_err):
        self.run_validate('vehicles.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml is valid\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_03(self, mock_out, mock_err):
        self.run_validate('vehicles-2_errors.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles-2_errors.xml is not valid\n", mock_out.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_04(self, mock_out, mock_err):
        self.run_validate('unknown.xml')
        self.assertEqual(mock_err.getvalue(), '')
        output = mock_out.getvalue()
        if platform.system() == 'Windows':
            self.assertIn("The system cannot find the file specified", output)
        else:
            self.assertIn("No such file or directory", output)
        self.assertEqual('1', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_05(self, mock_out, mock_err):
        self.run_validate(*glob.glob('vehicles*.xml'))
        self.assertEqual(mock_err.getvalue(), '')
        output = mock_out.getvalue()
        self.assertIn("vehicles.xml is valid", output)
        self.assertIn("vehicles-3_errors.xml is not valid", output)
        self.assertIn("vehicles-1_error.xml is not valid", output)
        self.assertIn("vehicles2.xml is valid", output)
        self.assertIn("vehicles-2_errors.xml is not valid", output)
        self.assertEqual('6', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_06(self, mock_out, mock_err):
        self.run_validate('--schema=vehicles.xsd', 'vehicles.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml is valid\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_07(self, mock_out, mock_err):
        self.run_validate('--version=1.1', 'vehicles.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml is valid\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_08(self, mock_out, mock_err):
        self.run_validate('--lazy', 'vehicles.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml is valid\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_xml2json_command_01(self, mock_out, mock_err):
        self.run_xml2json()
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("the following arguments are required", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_xml2json_command_02(self, mock_out, mock_err):
        self.run_xml2json('vehicles.xml')
        os.unlink('vehicles.json')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml converted to vehicles.json\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_xml2json_command_03(self, mock_out, mock_err):
        self.run_xml2json('vehicles-2_errors.xml')
        os.unlink('vehicles-2_errors.json')
        self.assertEqual(mock_err.getvalue(), '')
        msg = "vehicles-2_errors.xml converted to vehicles-2_errors.json with 2 errors\n"
        self.assertEqual(msg, mock_out.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_json2xml_command_01(self, mock_out, mock_err):
        self.run_json2xml()
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("the following arguments are required: [JSON_FILE", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_json2xml_command_02(self, mock_out, mock_err):
        self.run_json2xml('--schema=vehicles.xsd')
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("the following arguments are required: [JSON_FILE", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_json2xml_command_03(self, mock_out, mock_err):
        with open('vehicles-test.json', 'w') as fp:
            to_json('vehicles.xml', fp)
        self.run_json2xml('vehicles-test.json', '--schema=vehicles.xsd')
        os.unlink('vehicles-test.json')
        os.unlink('vehicles-test.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles-test.json converted to vehicles-test.xml\n",
                         mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))


if __name__ == '__main__':
    header_template = "Test xmlschema CLI with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
