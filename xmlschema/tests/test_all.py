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

    from xmlschema.tests import tests_factory, print_test_header, get_testfiles
    from xmlschema.tests.test_helpers import TestNamespaces, TestQualifiedNames
    from xmlschema.tests.test_meta import TestBuiltinTypes, TestGlobalMaps
    from xmlschema.tests.test_regex import TestCodePoints, TestUnicodeSubset, TestUnicodeCategories, TestPatterns
    from xmlschema.tests.test_xpath import XsdXPathTest
    from xmlschema.tests.test_resources import TestResources
    from xmlschema.tests.test_models import TestModelValidation
    from xmlschema.tests.test_schemas import make_schema_test_class, TestXMLSchema10
    from xmlschema.tests.test_validators import (
        make_validator_test_class, TestValidation, TestDecoding, TestEncoding
    )
    from xmlschema.tests.test_package import TestPackaging

    print_test_header()

    testfiles = get_testfiles(os.path.dirname(os.path.abspath(__file__)))
    globals().update(tests_factory(make_schema_test_class, testfiles, 'xsd'))
    globals().update(tests_factory(make_validator_test_class, testfiles, 'xml'))
    unittest.main()
