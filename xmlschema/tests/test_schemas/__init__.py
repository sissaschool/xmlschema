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
This subpackage defines tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
from xmlschema.tests import tests_factory
from .test_schema_class import TestXMLSchema10, TestXMLSchema11
from .test_simple_types import TestXsdSimpleTypes, TestXsd11SimpleTypes
from .test_attributes import TestXsdAttributes, TestXsd11Attributes
from .test_complex_types import TestXsdComplexType, TestXsd11ComplexType
from .test_identities import TestXsdIdentities, TestXsd11Identities
from .test_wildcards import TestXsdWildcards, TestXsd11Wildcards
from .test_schema_builder import make_schema_test_class

# Creates schema tests from XSD files
globals().update(tests_factory(make_schema_test_class, 'xsd'))
