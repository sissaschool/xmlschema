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
    from xmlschema.tests.test_helpers import *
    from xmlschema.tests.test_meta import *
    from xmlschema.tests.test_regex import *
    from xmlschema.tests.test_xpath import *
    from xmlschema.tests.test_resources import *
    from xmlschema.tests.test_models import *
    from xmlschema.tests.test_schemas import *
    from xmlschema.tests.test_validators import *
    from xmlschema.tests.test_package import *
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
