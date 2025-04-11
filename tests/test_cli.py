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
import logging
import pathlib
import os
import platform
import sys

import xmlschema
from xmlschema.cli import get_loglevel, get_converter, validate, xml2json, json2xml
from xmlschema.testing import run_xmlschema_tests

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
        self.assertEqual(mock_out.getvalue(), '')
        self.assertEqual("vehicles-2_errors.xml is not valid\n", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_04(self, mock_out, mock_err):
        self.run_validate('unknown.xml')
        self.assertEqual(mock_out.getvalue(), '')
        stderr = mock_err.getvalue()
        if platform.system() == 'Windows':
            self.assertIn("The system cannot find the file specified", stderr)
        else:
            self.assertIn("No such file or directory", stderr)
        self.assertEqual('1', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_validate_command_05(self, mock_out, mock_err):
        self.run_validate(*glob.glob('vehicles*.xml'))
        stderr = mock_err.getvalue()
        stdout = mock_out.getvalue()
        self.assertIn("vehicles.xml is valid", stdout)
        self.assertIn("vehicles-3_errors.xml is not valid", stderr)
        self.assertIn("vehicles-1_error.xml is not valid", stderr)
        self.assertIn("vehicles2.xml is valid", stdout)
        self.assertIn("vehicles-2_errors.xml is not valid", stderr)
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
        self.run_xml2json('vehicles.xml', '--schema=vehicles.xsd')
        os.unlink('vehicles.json')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles.xml converted to vehicles.json\n", mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_xml2json_command_04(self, mock_out, mock_err):
        self.run_xml2json('vehicles-2_errors.xml')
        os.unlink('vehicles-2_errors.json')
        self.assertEqual(mock_err.getvalue(), '')
        msg = "vehicles-2_errors.xml converted to vehicles-2_errors.json with 2 errors\n"
        self.assertEqual(msg, mock_out.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_xml2json_command_05(self, mock_out, mock_err):
        if os.path.isfile('vehicles.json'):
            os.unlink('vehicles.json')

        self.run_xml2json('vehicles.xml')
        self.assertEqual('0', str(self.ctx.exception))
        self.run_xml2json('vehicles.xml')

        with self.assertRaises(ValueError) as ctx:
            self.run_xml2json('--output=vehicles.json', 'vehicles.xml')
        self.assertEqual(str(ctx.exception), "'vehicles.json' is not a directory")

        os.unlink('vehicles.json')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertIn("vehicles.xml converted to vehicles.json\n", mock_out.getvalue())
        self.assertIn("skip vehicles.json: the destination file exists!", mock_out.getvalue())

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
            xmlschema.to_json('vehicles.xml', fp)
        self.run_json2xml('vehicles-test.json', '--schema=vehicles.xsd')
        os.unlink('vehicles-test.json')
        os.unlink('vehicles-test.xml')
        self.assertEqual(mock_err.getvalue(), '')
        self.assertEqual("vehicles-test.json converted to vehicles-test.xml\n",
                         mock_out.getvalue())
        self.assertEqual('0', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_json2xml_command_04(self, mock_out, mock_err):
        with open('vehicles-test.json', 'w') as fp:
            xmlschema.to_json('vehicles.xml', fp)

        self.run_json2xml('vehicles-test.json', '--schema=vehicles.xsd')
        self.assertEqual('0', str(self.ctx.exception))
        self.run_json2xml('vehicles-test.json', '--schema=vehicles.xsd')

        with self.assertRaises(ValueError) as ctx:
            self.run_json2xml('vehicles-test.json', '--schema=vehicles.xsd',
                              '--output=vehicles-test.xml')
        self.assertEqual(str(ctx.exception), "'vehicles-test.xml' is not a directory")

        os.unlink('vehicles-test.json')
        os.unlink('vehicles-test.xml')

        self.assertEqual(mock_err.getvalue(), '')
        self.assertIn("vehicles-test.json converted to vehicles-test.xml\n",
                      mock_out.getvalue())
        self.assertIn("skip vehicles-test.xml: the destination file exists!",
                      mock_out.getvalue())

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_wrong_xsd_version(self, mock_out, mock_err):
        self.run_validate('--version=1.9', 'vehicles.xml')
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("'1.9' is not a valid XSD version", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_wrong_defuse(self, mock_out, mock_err):
        self.run_validate('--defuse=sometimes', 'vehicles.xml')
        self.assertEqual(mock_out.getvalue(), '')
        self.assertIn("'sometimes' is not a valid value", mock_err.getvalue())
        self.assertEqual('2', str(self.ctx.exception))

    def test_get_loglevel(self):
        self.assertEqual(get_loglevel(0), logging.ERROR)
        self.assertEqual(get_loglevel(1), logging.WARNING)
        self.assertEqual(get_loglevel(2), logging.INFO)
        self.assertEqual(get_loglevel(3), logging.DEBUG)

    def test_get_converter(self):
        self.assertIsNone(get_converter(None))
        self.assertIs(get_converter('Unordered'), xmlschema.UnorderedConverter)
        self.assertIs(get_converter('Parker'), xmlschema.ParkerConverter)

        with self.assertRaises(ValueError):
            get_converter('Unknown')


if __name__ == '__main__':
    run_xmlschema_tests('CLI')
