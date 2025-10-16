#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
Unit tests for the SDC4 error mapper.
"""

import unittest
from sdcvalidator.core.exceptions import (
    XMLSchemaValidationError,
    XMLSchemaDecodeError,
    XMLSchemaChildrenValidationError
)
from sdcvalidator.sdc4.error_mapper import ErrorMapper
from sdcvalidator.sdc4.constants import ExceptionalValueType


class TestErrorMapper(unittest.TestCase):
    """Test cases for the ErrorMapper class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mapper = ErrorMapper()

    def test_type_violation_mapping(self):
        """Test that type violations are mapped to INV."""
        # Create a mock error with type violation reason
        error = XMLSchemaValidationError(
            validator=None,
            obj="invalid_value",
            reason="not a valid value for type xs:integer"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.INV)

    def test_enumeration_violation_mapping(self):
        """Test that enumeration violations are mapped to OTH."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="bad_value",
            reason="value not in enumeration ['option1', 'option2']"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.OTH)

    def test_missing_required_mapping(self):
        """Test that missing required elements are mapped to NI."""
        error = XMLSchemaValidationError(
            validator=None,
            obj=None,
            reason="missing required element 'field_name'"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.NI)

    def test_pattern_violation_mapping(self):
        """Test that pattern violations are mapped to INV."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="abc123",
            reason="pattern '[0-9]+' not matched"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.INV)

    def test_unexpected_content_mapping(self):
        """Test that unexpected content is mapped to NA."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="unexpected_element",
            reason="unexpected element 'field' not allowed here"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.NA)

    def test_encoding_error_mapping(self):
        """Test that encoding errors are mapped to UNC."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="bad\x00char",
            reason="encoding error: invalid character in string"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.UNC)

    def test_decode_error_mapping(self):
        """Test that decode errors are mapped to INV."""
        error = XMLSchemaDecodeError(
            validator=None,
            obj="not_a_number",
            decoder=None,
            reason="cannot be converted to integer"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.INV)

    def test_default_fallback_mapping(self):
        """Test that unknown errors fall back to NI."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="something",
            reason=None  # No reason provided
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.NI)

    def test_custom_rule_addition(self):
        """Test adding custom mapping rules."""
        # Add a custom rule that maps specific errors to MSK
        def is_masked_error(err):
            return err.reason and 'confidential' in err.reason.lower()

        self.mapper.add_rule(is_masked_error, ExceptionalValueType.MSK)

        error = XMLSchemaValidationError(
            validator=None,
            obj="secret_data",
            reason="This field contains confidential information"
        )

        # Custom rule should be checked before default rules
        # Need to insert it at the beginning
        mapper = ErrorMapper()
        mapper._rules.insert(0, (is_masked_error, ExceptionalValueType.MSK))

        ev_type = mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.MSK)

    def test_error_summary_generation(self):
        """Test that error summaries are generated correctly."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="invalid_value",
            reason="not a valid value for type xs:integer"
        )
        error._path = "/root/element[1]"

        ev_type = self.mapper.map_error(error)
        summary = self.mapper.get_error_summary(error, ev_type)

        self.assertEqual(summary['exceptional_value_type'], 'INV')
        self.assertEqual(summary['exceptional_value_name'], 'Invalid')
        self.assertEqual(summary['xpath'], '/root/element[1]')
        self.assertIn('not a valid value', summary['reason'])

    def test_constraint_violation_max_length(self):
        """Test that maxLength violations are mapped to INV."""
        error = XMLSchemaValidationError(
            validator=None,
            obj="toolongstring",
            reason="length constraint violated: maxLength is 10"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.INV)

    def test_constraint_violation_min_inclusive(self):
        """Test that minInclusive violations are mapped to INV."""
        error = XMLSchemaValidationError(
            validator=None,
            obj=-5,
            reason="value -5 is below minimum inclusive of 0"
        )

        ev_type = self.mapper.map_error(error)
        self.assertEqual(ev_type, ExceptionalValueType.INV)


if __name__ == '__main__':
    unittest.main()
