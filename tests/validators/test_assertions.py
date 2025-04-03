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
import pathlib
from xmlschema.testing import XsdValidatorTestCase


class TestXsdAssert(XsdValidatorTestCase):

    cases_dir = pathlib.Path(__file__).parent.joinpath('../test_cases')


if __name__ == '__main__':
    from xmlschema.testing import run_xmlschema_tests
    run_xmlschema_tests('XSD 1.1 assertions')
