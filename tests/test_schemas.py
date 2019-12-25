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
Loads and runs tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
if __name__ == '__main__':
    import unittest
    import os

    from xmlschema.testing import print_test_header, tests_factory, make_schema_test_class

    def load_tests(loader, tests, pattern):
        validators_dir = os.path.join(os.path.dirname(__file__), 'validators')
        validators_tests = loader.discover(start_dir=validators_dir, pattern=pattern or '*')
        tests.addTests(validators_tests)
        return tests

    # Creates schema tests from XSD files
    globals().update(tests_factory(
        test_class_builder=make_schema_test_class,
        suffix='xsd',
        test_dir=os.path.dirname(os.path.abspath(__file__))
    ))

    print_test_header()
    unittest.main()
