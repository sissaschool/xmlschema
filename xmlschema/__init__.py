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
from .compat import ordered_dict_class as _ordered_dict_class
from .exceptions import XMLSchemaException, XMLSchemaRegexError, XMLSchemaURLError
from .resources import (
    normalize_url, fetch_resource, load_xml_resource, fetch_namespaces,
    fetch_schema_locations, fetch_schema, XMLResource
)
from .xpath import ElementPathMixin
from .converters import (
    ElementData, XMLSchemaConverter, ParkerConverter, BadgerFishConverter, AbderaConverter, JsonMLConverter
)
from .documents import validate, to_dict, to_json, from_json

from .validators import (
    XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaNotBuiltError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaChildrenValidationError, XMLSchemaIncludeWarning,
    XMLSchemaImportWarning, XsdGlobals, XMLSchemaBase, XMLSchema, XMLSchema10
)

__version__ = '1.0.6'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2018, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"

# Backward compatibility
XMLSchema_v1_0 = XMLSchema10
etree_get_namespaces = fetch_namespaces
