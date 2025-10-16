# SDCvalidator

**XML Schema Validation with Semantic Data Charter (SDC4) ExceptionalValue Recovery**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## Overview

SDCvalidator is a specialized XML Schema validation library designed for **Semantic Data Charter Release 4 (SDC4)** data models. It extends standard XML Schema 1.1 validation with automatic **ExceptionalValue injection** for validation errors, implementing the SDC4 "quarantine-and-tag" pattern.

When validation errors occur, SDCvalidator:
1. **Preserves** the invalid data in the XML instance
2. **Inserts** SDC4 ExceptionalValue elements to flag the errors
3. **Classifies** errors into 15 ISO 21090-based ExceptionalValue types
4. **Enables** data quality tracking and auditing workflows

This library is based on the excellent [xmlschema](https://github.com/brunato/xmlschema) library by Davide Brunato and SISSA.

## Key Features

- **SDC4 ExceptionalValue Recovery**: Automatic error classification and injection
- **Full XML Schema 1.1 Support**: XSD 1.0 and 1.1 validation
- **Data Quality Tracking**: 15 ISO 21090 NULL Flavor-based ExceptionalValue types
- **Quarantine-and-Tag Pattern**: Preserves invalid data for forensic analysis
- **Extensible Error Mapping**: Customizable error-to-ExceptionalValue rules
- **High-Level API**: Simple SDC4Validator interface for common workflows
- **Comprehensive Validation Reports**: Detailed error summaries with ExceptionalValue classifications

## Installation

```bash
pip install sdcvalidator
```

## Quick Start

### Basic SDC4 Validation with Recovery

```python
from sdcvalidator import SDC4Validator

# Initialize validator with your SDC4 data model schema
validator = SDC4Validator('my_sdc4_datamodel.xsd')

# Validate XML instance and inject ExceptionalValues for errors
recovered_tree = validator.validate_with_recovery('my_instance.xml')

# Save the recovered XML with ExceptionalValue elements
validator.save_recovered_xml('recovered_instance.xml', 'my_instance.xml')
```

### Generate Validation Reports

```python
from sdcvalidator import SDC4Validator

validator = SDC4Validator('my_schema.xsd')
report = validator.validate_and_report('my_instance.xml')

print(f"Valid: {report['valid']}")
print(f"Error count: {report['error_count']}")
print(f"ExceptionalValue types: {report['exceptional_value_type_counts']}")

# Examine individual errors
for error in report['errors']:
    print(f"{error['xpath']}: {error['exceptional_value_type']} - {error['reason']}")
```

### Standard XML Schema Validation

SDCvalidator also supports traditional XML Schema validation:

```python
from sdcvalidator import Schema, validate, is_valid

# Create schema (XSD 1.1 by default)
schema = Schema('my_schema.xsd')

# Validate instances
is_valid('my_instance.xml', schema)
validate('my_instance.xml', schema)

# Decode XML to dictionaries
data = schema.to_dict('my_instance.xml')
```

## SDC4 ExceptionalValue Types

SDCvalidator maps validation errors to 15 ISO 21090 NULL Flavor-based ExceptionalValue types:

| Code | Name | Description | Typical Use Case |
|------|------|-------------|------------------|
| **INV** | Invalid | Value not a member of permitted data values | Type violations, pattern mismatches |
| **OTH** | Other | Value not in coding system | Enumeration violations |
| **NI** | No Information | Missing/omitted value | Missing required elements |
| **NA** | Not Applicable | No proper value applicable | Unexpected content |
| **UNC** | Unencoded | Raw source information | Encoding/format errors |
| **UNK** | Unknown | Proper value applicable but not known | - |
| **ASKU** | Asked but Unknown | Information sought but not found | - |
| **ASKR** | Asked and Refused | Information sought but refused | - |
| **NASK** | Not Asked | Information not sought | - |
| **NAV** | Not Available | Information not available | - |
| **MSK** | Masked | Information masked for privacy/security | - |
| **DER** | Derived | Derived or calculated value | - |
| **PINF** | Positive Infinity | Positive infinity | - |
| **NINF** | Negative Infinity | Negative infinity | - |
| **TRC** | Trace | Trace amount detected | - |

## ExceptionalValue Injection Example

When validation errors occur, SDCvalidator inserts ExceptionalValue elements while preserving the invalid data:

**Input XML (invalid):**
```xml
<sdc4:AdultPopulation>
    <label>Adult Population</label>
    <xdcount-value>not_a_number</xdcount-value>
    <xdcount-units>
        <label>Count Units</label>
        <xdstring-value>people</xdstring-value>
    </xdcount-units>
</sdc4:AdultPopulation>
```

**Output XML (after recovery):**
```xml
<sdc4:AdultPopulation>
    <label>Adult Population</label>

    <!-- ExceptionalValue inserted to flag the error -->
    <sdc4:INV>
        <sdc4:ev-name>Invalid</sdc4:ev-name>
        <!-- Validation error: not a valid value for type xs:integer -->
    </sdc4:INV>

    <!-- Invalid value preserved for auditing -->
    <xdcount-value>not_a_number</xdcount-value>

    <xdcount-units>
        <label>Count Units</label>
        <xdstring-value>people</xdstring-value>
    </xdcount-units>
</sdc4:AdultPopulation>
```

## Command-Line Interface

Validate and recover XML instances from the command line:

```bash
# Validate with ExceptionalValue recovery
sdcvalidate --recover my_instance.xml -o recovered.xml --schema my_schema.xsd

# Generate validation report
sdcvalidate --report my_instance.xml --schema my_schema.xsd

# Standard validation (no recovery)
sdcvalidate my_instance.xml --schema my_schema.xsd
```

Convert between XML and JSON:

```bash
# XML to JSON
sdcvalidator-xml2json my_instance.xml -o output.json --schema my_schema.xsd

# JSON to XML
sdcvalidator-json2xml my_data.json -o output.xml --schema my_schema.xsd
```

## Advanced Usage

### Custom Error Mapping Rules

```python
from sdcvalidator import SDC4Validator, ErrorMapper, ExceptionalValueType

# Create custom error mapper
error_mapper = ErrorMapper()

# Add custom rule for confidential data errors
def is_confidential_error(error):
    return error.reason and 'confidential' in error.reason.lower()

error_mapper._rules.insert(0, (is_confidential_error, ExceptionalValueType.MSK))

# Use custom mapper
validator = SDC4Validator('my_schema.xsd', error_mapper=error_mapper)
```

### Filtering Valid Data for Analytics

To select only valid data (excluding elements with ExceptionalValues):

```python
from xml.etree import ElementTree as ET

def has_exceptional_value(element):
    """Check if element contains any ExceptionalValue."""
    for child in element:
        local_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
        if local_name in ['INV', 'OTH', 'NI', 'NA', 'UNC', 'UNK', 'MSK',
                          'ASKU', 'ASKR', 'NASK', 'NAV', 'DER',
                          'PINF', 'NINF', 'TRC', 'QS']:
            return True
    return False

# Filter valid elements
tree = ET.parse('recovered_instance.xml')
valid_elements = [elem for elem in tree.iter() if not has_exceptional_value(elem)]
```

## Architecture

SDCvalidator consists of:

1. **Core Validation** (`sdcvalidator.core`): Full XML Schema 1.0/1.1 validation engine
2. **SDC4 Module** (`sdcvalidator.sdc4`): ExceptionalValue injection and error mapping
3. **Resources** (`sdcvalidator.resources`): XML resource loading and caching
4. **Converters** (`sdcvalidator.converters`): XML ↔ Python data conversion
5. **XPath** (`sdcvalidator.xpath`): XPath-based element selection

## Documentation

- [SDC4 Module Documentation](sdcvalidator/sdc4/README.md)
- [API Reference](https://sdcvalidator.readthedocs.io/)
- [Semantic Data Charter Specification](https://semanticdatacharter.com/)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run SDC4 tests only
pytest tests/sdc4/ -v

# Run with coverage
pytest --cov=sdcvalidator --cov-report=html
```

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Credits

**SDCvalidator** is developed by [Axius-SDC, Inc.](https://axius-sdc.com) and is based on the [xmlschema](https://github.com/brunato/xmlschema) library by:
- **Davide Brunato** (brunato@sissa.it)
- **SISSA** (International School for Advanced Studies)

The core XML Schema validation engine and much of the underlying architecture are from the xmlschema project.

## License

This software is distributed under the terms of the **MIT License**.

**Copyright (c) 2025, Axius-SDC, Inc.**
**Copyright (c) 2016-2024, SISSA (International School for Advanced Studies)**

See the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/Axius-SDC/sdcvalidator/issues)
- **Contact**: tim@axius-sdc.com

## Acknowledgments

Special thanks to:
- Davide Brunato and SISSA for the excellent xmlschema library
- The Semantic Data Charter community for the SDC4 specification
- All contributors to the project
