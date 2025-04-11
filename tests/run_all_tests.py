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
    import os
    import random

    from xmlschema.testing import make_schema_test_class, make_validation_test_class, \
        xmlschema_tests_factory, parse_xmlschema_args, run_xmlschema_tests

    def load_tests(loader, tests, pattern):
        tests.addTests(loader.discover(
            start_dir=os.path.dirname(__file__),
            pattern=pattern or 'test_*.py',
        ))
        if args.random:
            tests._tests.sort(key=lambda x: random.randint(0, 0xFFFFFFFF))  # noqa
        return tests

    args = parse_xmlschema_args()

    schema_tests = xmlschema_tests_factory(
        test_class_builder=make_schema_test_class,
        testfiles=args.testfiles,
        suffix='xsd',
        check_with_lxml=args.lxml,
        codegen=args.codegen,
        verbosity=args.verbosity,
    )
    globals().update(schema_tests)

    validation_tests = xmlschema_tests_factory(
        test_class_builder=make_validation_test_class,
        testfiles=args.testfiles,
        suffix='xml',
        check_with_lxml=args.lxml,
        codegen=args.codegen,
        verbosity=args.verbosity,
    )
    globals().update(validation_tests)

    run_xmlschema_tests('package', args)
