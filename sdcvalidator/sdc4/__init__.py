#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
SDC4 (Semantic Data Charter Release 4) integration module.

This module provides functionality for validating XML instances against SDC4
data model schemas and translating validation errors into SDC4 ExceptionalValue
elements that are inserted into the XML instance.

The SDC4 pattern uses the "quarantine-and-tag" approach where invalid values
are preserved in the instance and flagged with ExceptionalValue elements for
data quality tracking and auditing.
"""

from .validator import SDC4Validator, validate_with_recovery
from .constants import (
    SDC4_NAMESPACE,
    SDC4_META_NAMESPACE,
    EXCEPTIONAL_VALUE_TYPES,
    ExceptionalValueType
)
from .error_mapper import ErrorMapper

__all__ = [
    'SDC4Validator',
    'validate_with_recovery',
    'ErrorMapper',
    'SDC4_NAMESPACE',
    'SDC4_META_NAMESPACE',
    'EXCEPTIONAL_VALUE_TYPES',
    'ExceptionalValueType',
]

__version__ = '1.0.0'
