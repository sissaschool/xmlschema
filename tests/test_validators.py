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
"""
Loads and runs tests concerning the validation/decoding/encoding of XML files.
"""
if __name__ == '__main__':
    import unittest
    import os

    from xmlschema.testing import tests_factory, make_validator_test_class, print_test_header

    def load_tests(loader, tests, pattern):
        validation_dir = os.path.join(os.path.dirname(__file__), 'validation')
        validation_tests = loader.discover(start_dir=validation_dir, pattern=pattern or '*')
        tests.addTests(validation_tests)
        return tests

    # Creates schema tests from XML files
    globals().update(tests_factory(
        test_class_builder=make_validator_test_class,
        suffix='xml',
        test_dir=os.path.dirname(os.path.abspath(__file__))
    ))

    print_test_header()
    unittest.main()
