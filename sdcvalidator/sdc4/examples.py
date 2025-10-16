#!/usr/bin/env python
#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
Example usage of the SDC4 validation module.

This script demonstrates various ways to use the SDC4Validator
to validate XML instances and insert ExceptionalValue elements.
"""

from pathlib import Path
from sdcvalidator.sdc4 import SDC4Validator, validate_with_recovery


def example_basic_validation():
    """Basic validation with recovery example."""
    print("=" * 70)
    print("Example 1: Basic Validation with Recovery")
    print("=" * 70)

    schema_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xsd'
    xml_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xml'

    if not schema_path.exists() or not xml_path.exists():
        print("Example files not found. Skipping...")
        return

    # Create validator
    validator = SDC4Validator(schema_path)

    # Perform validation and recovery
    recovered_tree = validator.validate_with_recovery(xml_path)

    print(f"Validation complete!")
    print(f"Recovered XML tree has root: {recovered_tree.getroot().tag}")
    print()


def example_validation_report():
    """Generate a detailed validation report."""
    print("=" * 70)
    print("Example 2: Detailed Validation Report")
    print("=" * 70)

    schema_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xsd'
    xml_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xml'

    if not schema_path.exists() or not xml_path.exists():
        print("Example files not found. Skipping...")
        return

    # Create validator
    validator = SDC4Validator(schema_path)

    # Get validation report
    report = validator.validate_and_report(xml_path)

    print(f"Validation Report:")
    print(f"  Valid: {report['valid']}")
    print(f"  Total errors: {report['error_count']}")
    print()

    if report['error_count'] > 0:
        print("  ExceptionalValue Type Distribution:")
        for ev_code, count in report['exceptional_value_type_counts'].items():
            print(f"    {ev_code}: {count} occurrence(s)")
        print()

        print("  Error Details:")
        for i, error in enumerate(report['errors'][:5], 1):  # Show first 5 errors
            print(f"    Error {i}:")
            print(f"      XPath: {error['xpath']}")
            print(f"      Type: {error['exceptional_value_type']} ({error['exceptional_value_name']})")
            print(f"      Reason: {error['reason'][:100]}...")
            print()

        if report['error_count'] > 5:
            print(f"    ... and {report['error_count'] - 5} more errors")
    print()


def example_iterate_errors():
    """Iterate over errors with mappings."""
    print("=" * 70)
    print("Example 3: Iterate Over Validation Errors")
    print("=" * 70)

    schema_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xsd'
    xml_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xml'

    if not schema_path.exists() or not xml_path.exists():
        print("Example files not found. Skipping...")
        return

    # Create validator
    validator = SDC4Validator(schema_path)

    # Iterate over errors
    print("Validation errors found:")
    for i, error_info in enumerate(validator.iter_errors_with_mapping(xml_path), 1):
        print(f"\n  {i}. {error_info['exceptional_value_type']} - {error_info['exceptional_value_name']}")
        print(f"     Location: {error_info['xpath']}")
        print(f"     Reason: {error_info['reason'][:80]}...")

        if i >= 5:  # Limit output
            print(f"\n  ... (showing first 5 errors only)")
            break
    print()


def example_save_recovered_xml():
    """Save recovered XML to file."""
    print("=" * 70)
    print("Example 4: Save Recovered XML to File")
    print("=" * 70)

    schema_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xsd'
    xml_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xml'

    if not schema_path.exists() or not xml_path.exists():
        print("Example files not found. Skipping...")
        return

    output_path = Path('/tmp/recovered_sdc4_example.xml')

    # Create validator
    validator = SDC4Validator(schema_path)

    # Validate and save
    validator.save_recovered_xml(
        output_path=output_path,
        xml_source=xml_path
    )

    if output_path.exists():
        print(f"Recovered XML saved to: {output_path}")
        print(f"File size: {output_path.stat().st_size} bytes")
    else:
        print("Failed to save recovered XML")
    print()


def example_convenience_function():
    """Use the convenience function."""
    print("=" * 70)
    print("Example 5: Convenience Function")
    print("=" * 70)

    schema_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xsd'
    xml_path = Path(__file__).parent.parent.parent / 'sdc4' / 'example' / 'dm-jsi5yxnvzsmsisgn2bvelkni.xml'

    if not schema_path.exists() or not xml_path.exists():
        print("Example files not found. Skipping...")
        return

    output_path = Path('/tmp/recovered_convenience.xml')

    # One-line validation and recovery
    recovered_tree = validate_with_recovery(
        schema_path=schema_path,
        xml_path=xml_path,
        output_path=output_path
    )

    print(f"Validation and recovery complete using convenience function!")
    if output_path.exists():
        print(f"Output saved to: {output_path}")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("*" * 70)
    print("SDC4 Validation Examples")
    print("*" * 70)
    print()

    try:
        example_basic_validation()
        example_validation_report()
        example_iterate_errors()
        example_save_recovered_xml()
        example_convenience_function()

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

    print("*" * 70)
    print("Examples complete!")
    print("*" * 70)
    print()


if __name__ == '__main__':
    main()
