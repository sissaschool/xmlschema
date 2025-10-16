#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
Maps XML Schema validation errors to SDC4 ExceptionalValue types.
"""

import re
from typing import Optional, Callable, Dict, List
from sdcvalidator.core.exceptions import (
    XMLSchemaValidationError,
    XMLSchemaDecodeError,
    XMLSchemaChildrenValidationError
)
from .constants import ExceptionalValueType


class ErrorMapper:
    """
    Maps XMLSchema validation errors to appropriate SDC4 ExceptionalValue types.

    The mapper uses a rule-based system to classify errors. Rules can be customized
    or extended for domain-specific requirements.
    """

    def __init__(self):
        """Initialize the error mapper with default rules."""
        self._rules: List[tuple[Callable, ExceptionalValueType]] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register the default error mapping rules."""
        # Order matters - more specific rules should come first

        # Missing required elements/attributes
        self.add_rule(
            lambda err: self._is_missing_required(err),
            ExceptionalValueType.NI
        )

        # Type violations (wrong data type, invalid format)
        self.add_rule(
            lambda err: self._is_type_violation(err),
            ExceptionalValueType.INV
        )

        # Pattern, facet, or constraint violations
        self.add_rule(
            lambda err: self._is_constraint_violation(err),
            ExceptionalValueType.INV
        )

        # Enumeration violations
        self.add_rule(
            lambda err: self._is_enumeration_violation(err),
            ExceptionalValueType.OTH
        )

        # Unexpected elements/attributes in strict contexts
        self.add_rule(
            lambda err: self._is_unexpected_content(err),
            ExceptionalValueType.NA
        )

        # Encoding/format errors
        self.add_rule(
            lambda err: self._is_encoding_error(err),
            ExceptionalValueType.UNC
        )

        # Default fallback
        self.add_rule(
            lambda err: True,  # Matches everything
            ExceptionalValueType.NI
        )

    def add_rule(self, condition: Callable[[XMLSchemaValidationError], bool],
                  ev_type: ExceptionalValueType):
        """
        Add a custom mapping rule.

        :param condition: A callable that takes an error and returns True if the rule matches.
        :param ev_type: The ExceptionalValueType to return when the rule matches.
        """
        self._rules.append((condition, ev_type))

    def map_error(self, error: XMLSchemaValidationError) -> ExceptionalValueType:
        """
        Map a validation error to an ExceptionalValue type.

        :param error: The XML Schema validation error.
        :return: The appropriate ExceptionalValueType.
        """
        for condition, ev_type in self._rules:
            if condition(error):
                return ev_type

        # Should never reach here due to default rule, but just in case
        return ExceptionalValueType.NI

    # =========================================================================
    # Error classification helper methods
    # =========================================================================

    def _is_missing_required(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates missing required element/attribute."""
        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'missing required',
            r'required .* is missing',
            r'element .* is required',
            r'content .* is not complete',
            r'minimum .* is \d+',
        ]

        return any(re.search(pattern, reason) for pattern in patterns)

    def _is_type_violation(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates wrong data type."""
        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'not a valid value',
            r'invalid value',
            r'is not valid for type',
            r'type .* does not match',
            r'cannot be converted',
            r'expected type',
            r'wrong type',
            r'invalid.*format',
            r'malformed',
        ]

        # Also check if it's a decode error which typically indicates type issues
        if isinstance(error, XMLSchemaDecodeError):
            return True

        return any(re.search(pattern, reason) for pattern in patterns)

    def _is_constraint_violation(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates constraint/facet violation."""
        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'pattern.*not matched',
            r'does not match pattern',
            r'length constraint',
            r'minlength|maxlength',
            r'mininclusive|maxinclusive',
            r'minexclusive|maxexclusive',
            r'totaldigits|fractiondigits',
            r'assertion.*failed',
            r'constraint.*violated',
            r'exceeds.*maximum',
            r'below.*minimum',
        ]

        return any(re.search(pattern, reason) for pattern in patterns)

    def _is_enumeration_violation(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates enumeration violation."""
        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'not in enumeration',
            r'not.*allowed value',
            r'not.*permitted value',
            r'invalid enumeration',
            r'value.*not.*allowed',
        ]

        return any(re.search(pattern, reason) for pattern in patterns)

    def _is_unexpected_content(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates unexpected element/attribute."""
        if isinstance(error, XMLSchemaChildrenValidationError):
            # Check if it's an unexpected child element
            if error.invalid_tag is not None:
                return True

        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'unexpected',
            r'not allowed',
            r'not permitted',
            r'extra element',
            r'unknown element',
            r'element.*not expected',
        ]

        return any(re.search(pattern, reason) for pattern in patterns)

    def _is_encoding_error(self, error: XMLSchemaValidationError) -> bool:
        """Check if error indicates encoding/format problem."""
        if not error.reason:
            return False

        reason = error.reason.lower()
        patterns = [
            r'encoding error',
            r'decode error',
            r'character.*not.*allowed',
            r'invalid character',
            r'whitespace',
        ]

        return any(re.search(pattern, reason) for pattern in patterns)

    def get_error_summary(self, error: XMLSchemaValidationError,
                          ev_type: ExceptionalValueType) -> Dict[str, str]:
        """
        Generate a summary of the error mapping.

        :param error: The validation error.
        :param ev_type: The mapped ExceptionalValueType.
        :return: A dictionary with error details.
        """
        return {
            'xpath': error.path or 'unknown',
            'error_type': type(error).__name__,
            'reason': error.reason or 'No reason provided',
            'exceptional_value_type': ev_type.code,
            'exceptional_value_name': ev_type.ev_name,
            'description': ev_type.description,
        }
