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
"""Package protection limits. Values can be changed after import to set different limits."""

MAX_XML_DEPTH = 9999
"""
Maximum depth of XML data. An `XMLSchemaValidationError` is raised if this limit is exceeded.
"""

MAX_MODEL_DEPTH = 15
"""
Maximum XSD model group depth. An `XMLSchemaModelDepthError` is raised if this limit is exceeded.
"""
