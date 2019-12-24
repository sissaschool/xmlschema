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
from . import limits
from .exceptions import XMLSchemaException, XMLSchemaRegexError, XMLSchemaURLError, \
    XMLSchemaNamespaceError
from .etree import etree_tostring
from .resources import (
    normalize_url, fetch_resource, load_xml_resource, fetch_namespaces,
    fetch_schema_locations, fetch_schema, XMLResource
)
from .xpath import ElementPathMixin
from .converters import (
    ElementData, XMLSchemaConverter, UnorderedConverter, ParkerConverter,
    BadgerFishConverter, AbderaConverter, JsonMLConverter
)
from .documents import validate, is_valid, iter_errors, to_dict, to_json, from_json

from .validators import (
    XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaNotBuiltError,
    XMLSchemaModelError, XMLSchemaModelDepthError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaChildrenValidationError,
    XMLSchemaIncludeWarning, XMLSchemaImportWarning, XMLSchemaTypeTableWarning,
    XsdGlobals, XMLSchemaBase, XMLSchema, XMLSchema10, XMLSchema11
)

__version__ = '1.0.18'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2019, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"


# API deprecation warnings
def XMLSchema_v1_0(*args, **kwargs):
    import warnings
    warnings.warn("XMLSchema_v1_0 class name has been replaced by XMLSchema10 "
                  "and will be removed in 1.1 version", DeprecationWarning, stacklevel=2)
    return XMLSchema10(*args, **kwargs)


def etree_get_namespaces(*args, **kwargs):
    import warnings
    warnings.warn("etree_get_namespaces() function name has been replaced by fetch_namespaces() "
                  "and will be removed in 1.1 version", DeprecationWarning, stacklevel=2)
    return fetch_namespaces(*args, **kwargs)
