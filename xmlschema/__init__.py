#
# Copyright (c), 2016-2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from elementpath.etree import etree_tostring

from . import limits
from . import translation
from .exceptions import XMLSchemaException, XMLResourceError, XMLSchemaNamespaceError
from .resources import normalize_url, normalize_locations, fetch_resource, \
    fetch_namespaces, fetch_schema_locations, fetch_schema, XMLResource
from .xpath import ElementPathMixin
from .converters import ElementData, XMLSchemaConverter, \
    UnorderedConverter, ParkerConverter, BadgerFishConverter, \
    AbderaConverter, JsonMLConverter, ColumnarConverter
from .dataobjects import DataElement, DataElementConverter, DataBindingConverter
from .documents import validate, is_valid, iter_errors, iter_decode, \
    to_dict, to_json, to_etree, from_json, XmlDocument

from .validators import (
    XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaNotBuiltError,
    XMLSchemaModelError, XMLSchemaModelDepthError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaChildrenValidationError,
    XMLSchemaIncludeWarning, XMLSchemaImportWarning, XMLSchemaTypeTableWarning,
    XsdGlobals, XMLSchemaBase, XMLSchema, XMLSchema10, XMLSchema11,
    XsdComponent, XsdType, XsdElement, XsdAttribute
)

__version__ = '2.5.0'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2023, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"

__all__ = [
    'limits', 'translation', 'XMLSchemaException', 'XMLResourceError',
    'XMLSchemaNamespaceError', 'etree_tostring', 'normalize_url', 'normalize_locations',
    'fetch_resource', 'fetch_namespaces', 'fetch_schema_locations', 'fetch_schema',
    'XMLResource', 'ElementPathMixin', 'ElementData', 'XMLSchemaConverter',
    'UnorderedConverter', 'ParkerConverter', 'BadgerFishConverter', 'AbderaConverter',
    'JsonMLConverter', 'ColumnarConverter', 'DataElement', 'DataElementConverter',
    'DataBindingConverter', 'validate', 'is_valid', 'iter_errors', 'iter_decode',
    'to_dict', 'to_json', 'to_etree', 'from_json', 'XmlDocument', 'XMLSchemaValidatorError',
    'XMLSchemaParseError', 'XMLSchemaNotBuiltError', 'XMLSchemaModelError',
    'XMLSchemaModelDepthError', 'XMLSchemaValidationError', 'XMLSchemaDecodeError',
    'XMLSchemaEncodeError', 'XMLSchemaChildrenValidationError', 'XMLSchemaIncludeWarning',
    'XMLSchemaImportWarning', 'XMLSchemaTypeTableWarning', 'XsdGlobals', 'XMLSchemaBase',
    'XMLSchema', 'XMLSchema10', 'XMLSchema11', 'XsdComponent', 'XsdType', 'XsdElement',
    'XsdAttribute',
]
