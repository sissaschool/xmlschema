#!/usr/bin/env python
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
if __name__ == '__main__':
    import unittest
    import os

    from xmlschema.tests import print_test_header
    from xmlschema.tests import test_cases, test_etree, test_helpers, \
        test_meta, test_models, test_regex, test_resources, test_xpath
    from xmlschema.tests.validation import test_validation, test_decoding, test_encoding

    def load_tests(loader, tests, pattern):
        tests.addTests(loader.loadTestsFromModule(test_cases))

        validators_dir = os.path.join(os.path.dirname(__file__), 'validators')
        tests.addTests(loader.discover(start_dir=validators_dir, pattern=pattern or 'test_*.py'))

        tests.addTests(loader.loadTestsFromModule(test_validation))
        tests.addTests(loader.loadTestsFromModule(test_decoding))
        tests.addTests(loader.loadTestsFromModule(test_encoding))

        tests.addTests(loader.loadTestsFromModule(test_etree))
        tests.addTests(loader.loadTestsFromModule(test_helpers))
        tests.addTests(loader.loadTestsFromModule(test_meta))
        tests.addTests(loader.loadTestsFromModule(test_models))
        tests.addTests(loader.loadTestsFromModule(test_regex))
        tests.addTests(loader.loadTestsFromModule(test_resources))
        tests.addTests(loader.loadTestsFromModule(test_xpath))

        return tests

    print_test_header()
    unittest.main()
