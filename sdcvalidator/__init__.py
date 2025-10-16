#
# Copyright (c), 2025, Axius-SDC, Inc.
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# Based on xmlschema library by Davide Brunato and SISSA
# Specialized for Semantic Data Charter (SDC) validation
#
"""
SDCvalidator - Semantic Data Charter XML Validation Library

This library provides XML Schema validation specialized for Semantic Data Charter (SDC)
data models with automatic ExceptionalValue injection for validation errors.

Primary API - SDC4 Validation:
    - SDC4Validator: Main validator class
    - validate_with_recovery: Convenience function
    - ExceptionalValueType: ExceptionalValue type enumeration
    - ErrorMapper: Error classification system

Core Validation (advanced users):
    - Schema: XML Schema validator (XMLSchema11)
    - validate: Validate XML against schema
    - is_valid: Check if XML is valid

Built on the excellent xmlschema library by Davide Brunato and SISSA.
"""

from . import translation
from . import limits
from .exceptions import XMLSchemaException, XMLResourceError, XMLSchemaNamespaceError
from .resources import fetch_resource, fetch_namespaces, fetch_schema_locations, \
    fetch_schema, XMLResource
from .xpath import ElementPathMixin, ElementSelector, ElementPathSelector
from .converters import ElementData, XMLSchemaConverter, \
    UnorderedConverter, ParkerConverter, BadgerFishConverter, \
    AbderaConverter, JsonMLConverter, ColumnarConverter, GDataConverter
from .dataobjects import DataElement, DataElementConverter, DataBindingConverter
from .documents import validate, is_valid, iter_errors, iter_decode, \
    to_dict, to_json, to_etree, from_json, XmlDocument
from .exports import download_schemas
from .loaders import SchemaLoader, LocationSchemaLoader, SafeSchemaLoader
from .utils.etree import etree_tostring
from .utils.urls import normalize_url, normalize_locations

from .core import (
    XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaNotBuiltError,
    XMLSchemaModelError, XMLSchemaModelDepthError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaChildrenValidationError,
    XMLSchemaStopValidation, XMLSchemaIncludeWarning, XMLSchemaImportWarning,
    XMLSchemaTypeTableWarning, XMLSchemaAssertPathWarning, XsdGlobals, XMLSchemaBase,
    XMLSchema, XMLSchema10, XMLSchema11, XsdComponent, XsdType, XsdElement, XsdAttribute
)

# Primary SDC4 API - Featured prominently
from .sdc4 import (
    SDC4Validator,
    validate_with_recovery,
    ErrorMapper,
    ExceptionalValueType,
    SDC4_NAMESPACE,
    EXCEPTIONAL_VALUE_TYPES,
)

# Alias for convenience
Schema = XMLSchema11

__version__ = '1.0.0'
__author__ = "Axius-SDC, Inc. (based on xmlschema by Davide Brunato)"
__contact__ = "tim@axius-sdc.com"
__copyright__ = "Copyright 2025, Axius-SDC, Inc. | Copyright 2016-2024, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"

__all__ = [
    # SDC4 Primary API
    'SDC4Validator', 'validate_with_recovery', 'ErrorMapper', 'ExceptionalValueType',
    'SDC4_NAMESPACE', 'EXCEPTIONAL_VALUE_TYPES',

    # Core validation
    'Schema', 'XMLSchema', 'XMLSchema10', 'XMLSchema11',
    'validate', 'is_valid', 'iter_errors',

    # Converters and data objects
    'XMLSchemaConverter', 'ElementData', 'DataElement',
    'UnorderedConverter', 'ParkerConverter', 'BadgerFishConverter', 'GDataConverter',
    'AbderaConverter', 'JsonMLConverter', 'ColumnarConverter',
    'DataElementConverter', 'DataBindingConverter',

    # Document operations
    'iter_decode', 'to_dict', 'to_json', 'to_etree', 'from_json', 'XmlDocument',

    # Resources and loaders
    'XMLResource', 'fetch_resource', 'fetch_namespaces', 'fetch_schema_locations',
    'fetch_schema', 'SchemaLoader', 'LocationSchemaLoader', 'SafeSchemaLoader',

    # XPath
    'ElementPathMixin', 'ElementSelector', 'ElementPathSelector',

    # Exceptions
    'XMLSchemaException', 'XMLResourceError', 'XMLSchemaNamespaceError',
    'XMLSchemaValidatorError', 'XMLSchemaParseError', 'XMLSchemaNotBuiltError',
    'XMLSchemaModelError', 'XMLSchemaModelDepthError', 'XMLSchemaValidationError',
    'XMLSchemaDecodeError', 'XMLSchemaEncodeError', 'XMLSchemaChildrenValidationError',
    'XMLSchemaStopValidation', 'XMLSchemaIncludeWarning', 'XMLSchemaImportWarning',
    'XMLSchemaTypeTableWarning', 'XMLSchemaAssertPathWarning',

    # Components
    'XsdGlobals', 'XMLSchemaBase', 'XsdComponent', 'XsdType', 'XsdElement', 'XsdAttribute',

    # Utilities
    'etree_tostring', 'normalize_url', 'normalize_locations', 'download_schemas',
    'limits', 'translation',
]
