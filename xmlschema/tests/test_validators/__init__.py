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
This subpackage defines tests concerning the validation/decoding/encoding of XML files.
"""
from xmlschema.tests import tests_factory
from .test_validation import TestValidation, TestValidation11
from .test_decoding import TestDecoding, TestDecoding11
from .test_encoding import TestEncoding, TestEncoding11
from .test_validator_builder import make_validator_test_class

# Creates decoding/encoding tests classes from XML files
globals().update(tests_factory(make_validator_test_class, 'xml'))
