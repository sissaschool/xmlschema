#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs all tests of the 'xmlschema' package.
"""
if __name__ == '__main__':
    import unittest
    import os
    import sys

    try:
        import xmlschema
    except ImportError:
        # Adds the package base dir path as first search path for imports
        pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        sys.path.insert(0, pkg_base_dir)
        import xmlschema

    from xmlschema.tests import tests_factory, print_test_header
    from xmlschema.tests.test_regex import TestCodePoints, TestUnicodeSubset, TestUnicodeCategories
    from xmlschema.tests.test_xpath import XsdXPathTest
    from xmlschema.tests.test_resources import TestResources
    from xmlschema.tests.test_meta import TestBuiltinTypes, TestGlobalMaps
    from xmlschema.tests.test_schemas import make_test_schema_function, TestXMLSchema1
    from xmlschema.tests.test_decoding import make_test_decoding_function, TestDecoding
    from xmlschema.tests.test_validation import TestValidation
    from xmlschema.tests.test_package import TestPackage

    print_test_header()

    if '-s' not in sys.argv and '--skip-extra' not in sys.argv:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '*/testfiles')
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases/testfiles')
        try:
            sys.argv.remove('-s')
        except ValueError:
            sys.argv.remove('--skip-extra')

    globals().update(tests_factory(make_test_schema_function, path, 'schema', 'xsd'))
    globals().update(tests_factory(make_test_decoding_function, path, 'decoding', 'xml'))
    unittest.main()
