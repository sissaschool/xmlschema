# SDC4 Integration Module

This module provides integration between the sdcvalidator library and the Semantic Data Charter Release 4 (SDC4) reference model for handling validation errors.

## Overview

The SDC4 module implements the **"quarantine-and-tag" pattern** where XML validation errors are captured and translated into SDC4 `ExceptionalValue` elements that are inserted into the XML instance document. Invalid values are preserved for auditing and data quality analysis.

## Features

- **Automatic Error Classification**: Maps XML Schema validation errors to appropriate SDC4 ExceptionalValue types
- **XML Instance Modification**: Inserts ExceptionalValue elements at error locations while preserving invalid data
- **Extensible Mapping**: Pluggable rule system for custom error-to-ExceptionalValue mappings
- **Data Quality Reporting**: Generate detailed reports of validation errors with ExceptionalValue classifications
- **Non-invasive**: Works as a wrapper around existing sdcvalidator validation

## ExceptionalValue Types

The following SDC4 ExceptionalValue types are supported (based on ISO 21090 NULL Flavors):

| Code | Name | Description | Use Case |
|------|------|-------------|----------|
| **INV** | Invalid | Value not a member of permitted data values | Type violations, pattern/facet violations |
| **OTH** | Other | Value not in coding system | Enumeration violations |
| **NI** | No Information | Missing/omitted value (default) | Missing required elements |
| **NA** | Not Applicable | No proper value applicable | Unexpected elements in strict contexts |
| **UNC** | Unencoded | Raw source information | Encoding/format errors |
| **UNK** | Unknown | Proper value applicable but not known | - |
| **ASKU** | Asked but Unknown | Information sought but not found | - |
| **ASKR** | Asked and Refused | Information sought but refused | - |
| **NASK** | Not Asked | Information not sought | - |
| **NAV** | Not Available | Information not available | - |
| **MSK** | Masked | Information masked for privacy/security | - |

## Usage

### Basic Validation with Recovery

```python
from sdcvalidator.sdc4 import SDC4Validator

# Create validator with SDC4 schema
validator = SDC4Validator('sdc4/example/dm-jsi5yxnvzsmsisgn2bvelkni.xsd')

# Validate and insert ExceptionalValue elements
recovered_tree = validator.validate_with_recovery('my_instance.xml')

# Save recovered XML
validator.save_recovered_xml(
    output_path='my_instance_recovered.xml',
    xml_source='my_instance.xml'
)
```

### Generate Validation Report

```python
from sdcvalidator.sdc4 import SDC4Validator

validator = SDC4Validator('my_schema.xsd')

# Get detailed validation report
report = validator.validate_and_report('my_instance.xml')

print(f"Valid: {report['valid']}")
print(f"Error count: {report['error_count']}")

# Show ExceptionalValue type distribution
for ev_code, count in report['exceptional_value_type_counts'].items():
    print(f"  {ev_code}: {count} errors")

# Examine individual errors
for error in report['errors']:
    print(f"XPath: {error['xpath']}")
    print(f"ExceptionalValue: {error['exceptional_value_type']} ({error['exceptional_value_name']})")
    print(f"Reason: {error['reason']}")
    print()
```

### Iterate Over Errors with Mappings

```python
validator = SDC4Validator('my_schema.xsd')

for error_info in validator.iter_errors_with_mapping('my_instance.xml'):
    xpath = error_info['xpath']
    ev_type = error_info['exceptional_value_type']
    ev_name = error_info['exceptional_value_name']
    reason = error_info['reason']

    print(f"{xpath}: {ev_type} - {reason}")
```

### Custom Error Mapping Rules

```python
from sdcvalidator.sdc4 import SDC4Validator, ErrorMapper, ExceptionalValueType

# Create custom error mapper
error_mapper = ErrorMapper()

# Add custom rule for domain-specific errors
def is_confidential_error(error):
    return error.reason and 'confidential' in error.reason.lower()

# Insert rule before default rules
error_mapper._rules.insert(0, (is_confidential_error, ExceptionalValueType.MSK))

# Use custom mapper
validator = SDC4Validator('my_schema.xsd', error_mapper=error_mapper)
```

### Convenience Function

```python
from sdcvalidator.sdc4 import validate_with_recovery

# One-line validation and recovery
recovered_tree = validate_with_recovery(
    schema_path='my_schema.xsd',
    xml_path='my_instance.xml',
    output_path='recovered_instance.xml'
)
```

## Example: StatePopulation Data Model

```python
from sdcvalidator.sdc4 import SDC4Validator
from pathlib import Path

# Load the StatePopulation example schema
schema_path = Path('sdc4/example/dm-jsi5yxnvzsmsisgn2bvelkni.xsd')
validator = SDC4Validator(schema_path)

# Validate an instance with errors
instance_path = Path('sdc4/example/dm-jsi5yxnvzsmsisgn2bvelkni.xml')
recovered = validator.validate_with_recovery(instance_path)

# The recovered XML now contains ExceptionalValue elements
# marking any validation errors while preserving the invalid data
validator.save_recovered_xml('recovered.xml', instance_path)
```

## Result XML Structure

When validation errors are found, ExceptionalValue elements are inserted into the appropriate XdAnyType elements:

```xml
<sdc4:ms-q1ey1sf5otsa97e76kb06hco>
    <label>Adult Population</label>

    <!-- ExceptionalValue inserted here to flag the error -->
    <sdc4:INV>
        <sdc4:ev-name>Invalid</sdc4:ev-name>
        <!-- Validation error: not a valid value for type xs:integer -->
    </sdc4:INV>

    <!-- Invalid value is preserved for auditing -->
    <xdcount-value>not_a_number</xdcount-value>

    <xdcount-units>
        <label>Count Units</label>
        <xdstring-value>people</xdstring-value>
    </xdcount-units>
</sdc4:ms-q1ey1sf5otsa97e76kb06hco>
```

## Architecture

The SDC4 module consists of four main components:

1. **constants.py**: Defines SDC4 namespaces and ExceptionalValue type enumerations
2. **error_mapper.py**: Maps XMLSchemaValidationError to ExceptionalValue types using pattern matching
3. **instance_modifier.py**: Modifies XML trees to insert ExceptionalValue elements at error locations
4. **validator.py**: High-level API that orchestrates validation, error mapping, and XML modification

## Analytics Usage

To select only valid data for processing, filter out elements containing ExceptionalValue:

```python
# XPath to select valid instances only
valid_elements = root.findall("//MyElement[not(sdc4:ExceptionalValue)]", namespaces)

# Or check programmatically
from xml.etree import ElementTree as ET

def has_exceptional_value(element):
    """Check if element contains any ExceptionalValue."""
    for child in element:
        local_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
        if local_name in ['INV', 'OTH', 'NI', 'NA', 'UNK', 'MSK',
                          'ASKU', 'ASKR', 'NASK', 'NAV', 'UNC',
                          'DER', 'PINF', 'NINF', 'TRC', 'QS']:
            return True
    return False
```

## Testing

Run the test suite:

```bash
# Unit tests
pytest tests/sdc4/test_error_mapper.py -v

# Integration tests
pytest tests/sdc4/test_sdc4_integration.py -v

# All SDC4 tests
pytest tests/sdc4/ -v
```

## References

- [Semantic Data Charter (SDC) Specification](https://semanticdatacharter.com/)
- [ISO 21090 NULL Flavors](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=15)
- SDC4 Reference Model Schema: `sdc4/sdc4.xsd`
- Example Data Model: `sdc4/example/dm-jsi5yxnvzsmsisgn2bvelkni.xsd`

## License

This module is distributed under the MIT License, consistent with the sdcvalidator library.
