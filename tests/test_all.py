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
if __name__ == '__main__':
    import unittest
    import os

    from xmlschema.testing import tests_factory, make_schema_test_class, \
        make_validation_test_class, print_test_header, get_test_program_args_parser

    DEFAULT_TESTFILES = os.path.join(os.path.dirname(__file__), 'test_cases/testfiles')

    def load_tests(loader, tests, pattern):
        tests_dir = os.path.dirname(__file__)
        if pattern is not None:
            tests.addTests(loader.discover(start_dir=tests_dir, pattern=pattern))
            return tests

        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_etree.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_helpers.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_converters.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_regex.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_resources.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_xpath.py"))

        validation_dir = os.path.join(os.path.dirname(__file__), 'validation')
        tests.addTests(loader.discover(start_dir=validation_dir, pattern='test_*.py'))

        validators_dir = os.path.join(os.path.dirname(__file__), 'validators')
        tests.addTests(loader.discover(start_dir=validators_dir, pattern="test_*.py"))
        return tests

    args = get_test_program_args_parser(DEFAULT_TESTFILES).parse_args()

    schema_tests = tests_factory(
        test_class_builder=make_schema_test_class,
        testfiles=args.testfiles,
        suffix='xsd',
        check_with_lxml=args.lxml,
    )
    globals().update(schema_tests)

    validation_tests = tests_factory(
        test_class_builder=make_validation_test_class,
        testfiles=args.testfiles,
        suffix='xml',
        check_with_lxml=args.lxml,
    )
    globals().update(validation_tests)

    argv = [__file__]
    if args.tb_locals:
        argv.append('--local')
    for pattern_ in args.patterns:
        argv.append('-k')
        argv.append(pattern_)
    print_test_header()
    unittest.main(argv=argv, verbosity=args.verbosity, failfast=args.failfast,
                  catchbreak=args.catchbreak, buffer=args.buffer)
