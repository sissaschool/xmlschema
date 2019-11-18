# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Test factory for creating test cases from lists of paths to XSD or XML files.

The list of cases can be defined within files named "testfiles". These are text files
that contain a list of relative paths to XSD or XML files, that are used to dinamically
build a set of test classes. Each path is followed by a list of options that defines a
custom setting for each test.
"""
import sys
import re
import argparse

TEST_FACTORY_OPTIONS = {
    'narrow': '-n' in sys.argv or '--narrow' in sys.argv,         # Skip extra checks (eg. other converters)
    'extra_cases': '-x' in sys.argv or '--extra' in sys.argv,     # Include extra test cases
    'check_with_lxml': '-l' in sys.argv or '--lxml' in sys.argv,  # Check with lxml.etree.XMLSchema (for XSD 1.0)
}
"""Command line options for test factory."""

RUN_W3C_TEST_SUITE = '-w' in sys.argv or '--w3c' in sys.argv

sys.argv = [a for a in sys.argv if a not in
            {'-x', '--extra', '-l', '--lxml', '-n', '--narrow'}]  # Clean sys.argv for unittest


def get_test_args(args_line):
    """Returns the list of arguments from provided text line."""
    try:
        args_line, _ = args_line.split('#', 1)  # Strip optional ending comment
    except ValueError:
        pass
    return re.split(r'(?<!\\) ', args_line.strip())


def xsd_version_number(value):
    if value not in ('1.0', '1.1'):
        msg = "%r is not an XSD version." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def defuse_data(value):
    if value not in ('always', 'remote', 'never'):
        msg = "%r is not a valid value." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def create_test_line_args_parser():
    """Creates an arguments parser for uncommented on not blank "testfiles" lines."""

    parser = argparse.ArgumentParser(add_help=True)
    parser.usage = "TEST_FILE [OPTIONS]\nTry 'TEST_FILE --help' for more information."
    parser.add_argument('filename', metavar='TEST_FILE', type=str, help="Test filename (relative path).")
    parser.add_argument(
        '-L', dest='locations', nargs=2, type=str, default=None, action='append',
        metavar="URI-URL", help="Schema location hint overrides."
    )
    parser.add_argument(
        '--version', dest='version', metavar='VERSION', type=xsd_version_number, default='1.0',
        help="XSD schema version to use for the test case (default is 1.0)."
    )
    parser.add_argument(
        '--errors', type=int, default=0, metavar='NUM', help="Number of errors expected (default=0)."
    )
    parser.add_argument(
        '--warnings', type=int, default=0, metavar='NUM', help="Number of warnings expected (default=0)."
    )
    parser.add_argument(
        '--inspect', action="store_true", default=False, help="Inspect using an observed custom schema class."
    )
    parser.add_argument(
        '--defuse', metavar='(always, remote, never)', type=defuse_data, default='remote',
        help="Define when to use the defused XML data loaders."
    )
    parser.add_argument(
        '--timeout', type=int, default=300, metavar='SEC', help="Timeout for fetching resources (default=300)."
    )
    parser.add_argument(
        '--defaults', action="store_true", default=False,
        help="Test data uses default or fixed values (skip strict encoding checks).",
    )
    parser.add_argument(
        '--skip', action="store_true", default=False,
        help="Skip strict encoding checks (for cases where test data uses default or "
             "fixed values or some test data are skipped by wildcards processContents)."
    )
    parser.add_argument(
        '--debug', action="store_true", default=False,
        help="Activate the debug mode (only the cases with --debug are executed).",
    )
    return parser
