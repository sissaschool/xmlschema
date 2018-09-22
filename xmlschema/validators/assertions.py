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
This module contains classes for other XML Schema 1.1 assertions.
"""
from __future__ import unicode_literals
from ..qnames import XSD_ASSERT_TAG, XSD_ASSERTION_TAG
from .xsdbase import XsdComponent, ValidationMixin


class XsdAssert(XsdComponent, ValidationMixin):
    admitted_tags = {XSD_ASSERT_TAG}


class XsdAssertion(XsdComponent, ValidationMixin):
    admitted_tags = {XSD_ASSERTION_TAG}