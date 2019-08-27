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
import os
import decimal
import subprocess


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

        self.assertLess(decode_mem, 2.6)
        self.assertLessEqual(lazy_decode_mem, decode_mem / decimal.Decimal('1.1'))

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

        self.assertLess(validate_mem, 2.6)
        self.assertLessEqual(lazy_validate_mem, validate_mem / decimal.Decimal('1.1'))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
