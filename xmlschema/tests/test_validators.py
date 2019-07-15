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
"""
Loads and runs tests concerning the validation/decoding/encoding of XML files.
"""
if __name__ == '__main__':
    import unittest
    from xmlschema.tests import print_test_header
    from xmlschema.tests.test_validators import *

    print_test_header()
    unittest.main()
