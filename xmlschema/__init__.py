# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from . import limits
from .exceptions import XMLSchemaException, XMLResourceError, XMLSchemaNamespaceError
from .etree import etree_tostring
from .resources import normalize_url, normalize_locations, fetch_resource, \
    fetch_namespaces, fetch_schema_locations, fetch_schema, XMLResource
from .xpath import ElementPathMixin
from .converters import (
    ElementData, XMLSchemaConverter, UnorderedConverter, ParkerConverter,
    BadgerFishConverter, AbderaConverter, JsonMLConverter, ColumnarConverter
)
from .documents import validate, is_valid, iter_errors, to_dict, to_json, \
    from_json, XmlDocument

from .validators import (
    XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaNotBuiltError,
    XMLSchemaModelError, XMLSchemaModelDepthError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaChildrenValidationError,
    XMLSchemaIncludeWarning, XMLSchemaImportWarning, XMLSchemaTypeTableWarning,
    XsdGlobals, XMLSchemaBase, XMLSchema, XMLSchema10, XMLSchema11,
    XsdComponent, XsdType, XsdElement, XsdAttribute
)

__version__ = '1.4.2'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2021, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"


__all__ = [
    'limits', 'XMLSchemaException', 'XMLResourceError', 'XMLSchemaNamespaceError',
    'etree_tostring', 'normalize_url', 'normalize_locations', 'fetch_resource',
    'fetch_namespaces', 'fetch_schema_locations', 'fetch_schema', 'XMLResource',
    'ElementPathMixin', 'ElementData', 'XMLSchemaConverter', 'UnorderedConverter',
    'ParkerConverter', 'BadgerFishConverter', 'AbderaConverter', 'JsonMLConverter',
    'ColumnarConverter', 'validate', 'is_valid', 'iter_errors', 'to_dict', 'to_json',
    'from_json', 'XmlDocument', 'XMLSchemaValidatorError', 'XMLSchemaParseError',
    'XMLSchemaNotBuiltError', 'XMLSchemaModelError', 'XMLSchemaModelDepthError',
    'XMLSchemaValidationError', 'XMLSchemaDecodeError', 'XMLSchemaEncodeError',
    'XMLSchemaChildrenValidationError', 'XMLSchemaIncludeWarning',
    'XMLSchemaImportWarning', 'XMLSchemaTypeTableWarning',
    'XsdGlobals', 'XMLSchemaBase', 'XMLSchema', 'XMLSchema10', 'XMLSchema11',
    'XsdComponent', 'XsdType', 'XsdElement', 'XsdAttribute',
]
