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
Test factory subpackage for creating test cases from lists of paths to XSD or XML files.

The list of cases can be defined within files named "testfiles". These are text files
that contain a list of relative paths to XSD or XML files, that are used to dinamically
build a set of test classes. Each path is followed by a list of options that defines a
custom setting for each test.
"""
from .arguments import TEST_FACTORY_OPTIONS, xsd_version_number, create_test_line_args_parser
from .factory import tests_factory
from .observers import SchemaObserver, ObservedXMLSchema10, ObservedXMLSchema11
from .schema_tests import make_schema_test_class
from .validation_tests import make_validator_test_class
