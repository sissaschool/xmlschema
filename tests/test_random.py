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
    import platform
    import random

    def random_key(x):
        return random.randint(0, 0xFFFFFFFF)

    from xmlschema.testing import get_test_program_args_parser

    DEFAULT_TESTFILES = os.path.join(os.path.dirname(__file__), 'test_cases/testfiles')

    def load_tests(loader, tests, pattern):
        tests_dir = os.path.dirname(__file__)
        if pattern is not None:
            tests.addTests(loader.discover(start_dir=tests_dir, pattern=pattern))
            return tests

        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_utils.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_namespaces.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_locations.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_resources.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_exports.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_xpath.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_cli.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_converters.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_documents.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_dataobjects.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_codegen.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_translations.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_wsdl.py"))

        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_xsd_testfiles.py"))
        tests.addTests(loader.discover(start_dir=tests_dir, pattern="test_xml_testfiles.py"))

        validation_dir = os.path.join(os.path.dirname(__file__), 'validation')
        tests.addTests(loader.discover(start_dir=validation_dir, pattern='test_*.py'))

        validators_dir = os.path.join(os.path.dirname(__file__), 'validators')
        tests.addTests(loader.discover(start_dir=validators_dir, pattern="test_*.py"))

        tests._tests.sort(key=random_key)  # noqa
        return tests

    args = get_test_program_args_parser(DEFAULT_TESTFILES).parse_args()

    argv = [__file__]
    if args.tb_locals:
        argv.append('--local')
    for pattern_ in args.patterns:
        argv.append('-k')
        argv.append(pattern_)

    header_template = "Test xmlschema with Python {} on {} using random order of tests"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main(argv=argv, verbosity=args.verbosity, failfast=args.failfast,
                  catchbreak=args.catchbreak, buffer=args.buffer)
