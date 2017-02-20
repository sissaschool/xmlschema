# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from .core import set_logger
from .exceptions import XMLSchemaException
from .schema import validate, to_dict, XMLSchema

__version__ = '0.9.2'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2017, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"

set_logger(__name__)
