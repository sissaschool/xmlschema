#!/usr/bin/env python
#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Tests concerning the parsing and the building of XSD schemas"""
import sys
from pathlib import Path
from xmlschema.testing import xmlschema_tests_factory, make_schema_test_class

if __name__ == '__main__':
    import random
    from xmlschema.testing import parse_xmlschema_args, run_xmlschema_tests

    def load_tests(_loader, tests, _pattern):
        if args.random:
            tests._tests.sort(key=lambda x: random.randint(0, 0xFFFFFFFF))  # noqa
        return tests

    args = parse_xmlschema_args()

    validation_tests = xmlschema_tests_factory(
        test_class_builder=make_schema_test_class,
        testfiles=args.testfiles,
        suffix='xsd',
        check_with_lxml=args.lxml,
        codegen=args.codegen,
        verbosity=args.verbosity,
    )
    globals().update(validation_tests)

    run_xmlschema_tests('schema building cases', args)

elif sys.argv and not sys.argv[0].endswith('run_all_tests.py'):
    testfiles = Path(__file__).absolute().parent.joinpath('test_cases/testfiles')

    schema_tests = xmlschema_tests_factory(
        test_class_builder=make_schema_test_class,
        suffix='xsd',
        testfiles=testfiles,
    )
    globals().update(schema_tests)
