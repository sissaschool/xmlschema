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
"""Tests concerning the parsing and the building of XSD schemas"""

import os

from xmlschema.testing import get_test_program_args_parser, \
    factory_tests, make_schema_test_class

DEFAULT_TESTFILES = os.path.join(os.path.dirname(__file__), 'test_cases/testfiles')


if __name__ == '__main__':
    import unittest
    import platform

    args = get_test_program_args_parser(DEFAULT_TESTFILES).parse_args()

    schema_tests = factory_tests(
        test_class_builder=make_schema_test_class,
        testfiles=args.testfiles,
        suffix='xsd',
        check_with_lxml=args.lxml,
        codegen=args.codegen,
        verbosity=args.verbosity,
    )
    globals().update(schema_tests)

    argv = [__file__]
    if args.tb_locals:
        argv.append('--local')
    for pattern in args.patterns:
        argv.append('-k')
        argv.append(pattern)

    header_template = "Schema building tests for xmlschema with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main(argv=argv, verbosity=args.verbosity, failfast=args.failfast,
                  catchbreak=args.catchbreak, buffer=args.buffer)
else:
    # Creates schema tests from XSD files
    globals().update(factory_tests(
        test_class_builder=make_schema_test_class,
        suffix='xsd',
        testfiles=DEFAULT_TESTFILES
    ))
