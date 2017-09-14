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
This module runs tests URL based access to resources.
"""
from _test_common import *

from xmlschema import XMLSchema
from xmlschema.resources import normalize_url


class TestURL(unittest.TestCase):
    xs1 = XMLSchema("examples/vehicles/vehicles.xsd")
    xs2 = XMLSchema("examples/collection/collection.xsd")
    cars = xs1.elements['vehicles'].type.content_type[0]
    bikes = xs1.elements['vehicles'].type.content_type[1]

    def test_absolute_path(self):
        url1 = "https://example.com/xsd/other_schema.xsd"
        self.assertTrue(normalize_url(url1, base_url="/path_my_schema/schema.xsd") == url1)


if __name__ == '__main__':
    unittest.main()
