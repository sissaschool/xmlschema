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
"""Tests concerning the validation/decoding/encoding of XML files"""

import os

from xmlschema.testing import get_test_program_args_parser, \
    factory_tests, make_validation_test_class

DEFAULT_TESTFILES = os.path.join(os.path.dirname(__file__), 'test_cases/testfiles')


if __name__ == '__main__':
    import unittest
    import platform

    args = get_test_program_args_parser(DEFAULT_TESTFILES).parse_args()

    validation_tests = factory_tests(
        test_class_builder=make_validation_test_class,
        testfiles=args.testfiles,
        suffix='xml',
        check_with_lxml=args.lxml,
    )
    globals().update(validation_tests)

    argv = [__file__]
    if args.tb_locals:
        argv.append('--local')
    for pattern in args.patterns:
        argv.append('-k')
        argv.append(pattern)

    header_template = "XML validation tests for xmlschema with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main(argv=argv, verbosity=args.verbosity, failfast=args.failfast,
                  catchbreak=args.catchbreak, buffer=args.buffer)
else:
    # Creates schema tests from XSD files
    globals().update(factory_tests(
        test_class_builder=make_validation_test_class,
        suffix='xml',
        testfiles=DEFAULT_TESTFILES
    ))
