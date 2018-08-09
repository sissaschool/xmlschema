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
Check xmlschema memory usage.

Refs:
    https://pypi.org/project/memory_profiler/
    https://github.com/brunato/xmlschema/issues/32
"""
import os.path
from memory_profiler import profile


@profile
def my_func(xsd_file):
    import xmlschema
    xs = xmlschema.XMLSchema(xsd_file)
    return xs


if __name__ == '__main__':
    my_func(os.path.join(os.path.dirname(__file__), 'cases/examples/vehicles/vehicles.xsd'))
