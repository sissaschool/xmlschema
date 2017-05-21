#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
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
from _test_common import *

pkg_folder = os.path.dirname(os.getcwd())
sys.path.insert(0, pkg_folder)

if __name__ == '__main__':
    from test_meta import *
    from test_xpath import *
    import test_schemas
    import test_decoding
    import test_validation

    pkg_folder = os.path.dirname(os.getcwd())
    sys.path.insert(0, pkg_folder)
    pathname = os.path.join(pkg_folder, "tests/*/testfiles")
    globals().update(test_schemas.get_tests(pathname))
    globals().update(test_decoding.get_tests(pathname))
    globals().update(test_validation.get_tests(pathname))
    unittest.main()
