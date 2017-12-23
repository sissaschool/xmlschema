#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
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
    from _test_common import tests_factory

    from test_regex import TestCodePoints, TestUnicodeSubset, TestUnicodeCategories
    from test_xpath import TestXPath
    from test_resources import TestResources
    from test_meta import TestBuiltinTypes, TestGlobalMaps
    from test_schemas import make_test_schema_function
    from test_decoding import make_test_decoding_function, TestDecoding
    from test_validation import make_test_validation_function, TestValidation

    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    path = os.path.join(pkg_folder, "tests/*/testfiles")
    globals().update(tests_factory(make_test_schema_function, path, 'schema', 'xsd'))
    globals().update(tests_factory(make_test_validation_function, path, 'validation', 'xml'))
    globals().update(tests_factory(make_test_decoding_function, path, 'decoding', 'xml'))
    unittest.main()
