#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
SDC4-aware validation with ExceptionalValue recovery.
"""

from typing import Union, Optional, Iterator, Dict, Any, List
from pathlib import Path
from xml.etree import ElementTree as ET
import copy

from sdcvalidator import XMLSchema11
from sdcvalidator.core.exceptions import XMLSchemaValidationError
from sdcvalidator.resources import XMLResource

from .error_mapper import ErrorMapper
from .instance_modifier import InstanceModifier
from .constants import ExceptionalValueType


class SDC4Validator:
    """
    Validates XML instances against SDC4 data model schemas and inserts
    ExceptionalValue elements for validation errors.

    Uses the SDC4 "quarantine-and-tag" pattern where invalid values are
    preserved and flagged with ExceptionalValue elements for data quality
    tracking and auditing.
    """

    def __init__(self, schema: Union[str, Path, XMLSchema11],
                 error_mapper: Optional[ErrorMapper] = None,
                 namespace_prefix: str = 'sdc4',
                 validation: str = 'lax'):
        """
        Initialize the SDC4 validator.

        :param schema: Path to the XSD schema file or an XMLSchema11 instance.
        :param error_mapper: Optional custom error mapper (default: uses ErrorMapper with default rules).
        :param namespace_prefix: The XML namespace prefix to use for SDC4 elements (default: 'sdc4').
        :param validation: Schema validation mode: 'strict', 'lax', or 'skip' (default: 'lax').
        """
        # Load schema if it's a path
        if isinstance(schema, (str, Path)):
            self.schema = XMLSchema11(str(schema), validation=validation)
        else:
            self.schema = schema

        # Initialize mapper and modifier
        self.error_mapper = error_mapper or ErrorMapper()
        self.instance_modifier = InstanceModifier(namespace_prefix=namespace_prefix)

    def validate_with_recovery(self,
                                xml_source: Union[str, Path, ET.Element, XMLResource],
                                remove_existing_ev: bool = True) -> ET.ElementTree:
        """
        Validate an XML instance and insert ExceptionalValue elements for errors.

        :param xml_source: The XML instance to validate (file path, element, or XMLResource).
        :param remove_existing_ev: If True, remove any existing ExceptionalValue elements before processing.
        :return: Modified XML ElementTree with ExceptionalValue elements inserted.
        """
        # Parse the XML if it's a path
        if isinstance(xml_source, (str, Path)):
            tree = ET.parse(str(xml_source))
            root = tree.getroot()
        elif isinstance(xml_source, ET.Element):
            root = xml_source
            tree = ET.ElementTree(root)
        elif isinstance(xml_source, XMLResource):
            root = xml_source.root
            tree = ET.ElementTree(root)
        else:
            raise TypeError(f"Unsupported xml_source type: {type(xml_source)}")

        # Make a copy to avoid modifying the original
        root = copy.deepcopy(root)
        tree = ET.ElementTree(root)

        # Optionally remove existing ExceptionalValue elements
        if remove_existing_ev:
            self.instance_modifier.remove_existing_exceptional_values(root)

        # Collect validation errors
        errors = list(self.schema.iter_errors(tree))

        # Process each error
        for error in errors:
            # Map error to ExceptionalValue type
            ev_type = self.error_mapper.map_error(error)

            # Get the XPath to the error location
            xpath = error.path

            if xpath:
                # Insert the ExceptionalValue element
                success = self.instance_modifier.insert_exceptional_value(
                    root=root,
                    xpath=xpath,
                    ev_type=ev_type,
                    reason=error.reason
                )

                if not success:
                    # Log or handle insertion failure
                    # For now, we'll just continue
                    pass

        return tree

    def iter_errors_with_mapping(self,
                                   xml_source: Union[str, Path, ET.Element, XMLResource]
                                   ) -> Iterator[Dict[str, Any]]:
        """
        Iterate over validation errors with their mapped ExceptionalValue types.

        :param xml_source: The XML instance to validate.
        :yield: Dictionaries containing error details and mapped ExceptionalValue type.
        """
        # Parse the XML if needed
        if isinstance(xml_source, (str, Path)):
            tree = ET.parse(str(xml_source))
        elif isinstance(xml_source, ET.Element):
            tree = ET.ElementTree(xml_source)
        elif isinstance(xml_source, XMLResource):
            tree = ET.ElementTree(xml_source.root)
        else:
            raise TypeError(f"Unsupported xml_source type: {type(xml_source)}")

        # Collect validation errors
        for error in self.schema.iter_errors(tree):
            # Map error to ExceptionalValue type
            ev_type = self.error_mapper.map_error(error)

            # Generate summary
            summary = self.error_mapper.get_error_summary(error, ev_type)

            yield summary

    def validate_and_report(self,
                            xml_source: Union[str, Path, ET.Element, XMLResource]
                            ) -> Dict[str, Any]:
        """
        Validate an XML instance and return a detailed report.

        :param xml_source: The XML instance to validate.
        :return: Dictionary containing validation results and error summaries.
        """
        errors = list(self.iter_errors_with_mapping(xml_source))

        report = {
            'valid': len(errors) == 0,
            'error_count': len(errors),
            'errors': errors
        }

        # Group errors by ExceptionalValue type
        ev_type_counts: Dict[str, int] = {}
        for error in errors:
            ev_code = error['exceptional_value_type']
            ev_type_counts[ev_code] = ev_type_counts.get(ev_code, 0) + 1

        report['exceptional_value_type_counts'] = ev_type_counts

        return report

    def save_recovered_xml(self,
                           output_path: Union[str, Path],
                           xml_source: Union[str, Path, ET.Element, XMLResource],
                           remove_existing_ev: bool = True,
                           encoding: str = 'UTF-8',
                           xml_declaration: bool = True):
        """
        Validate an XML instance, insert ExceptionalValues, and save to file.

        :param output_path: Path where the modified XML should be saved.
        :param xml_source: The XML instance to validate.
        :param remove_existing_ev: If True, remove any existing ExceptionalValue elements.
        :param encoding: XML encoding (default: 'UTF-8').
        :param xml_declaration: Include XML declaration (default: True).
        """
        # Perform recovery
        recovered_tree = self.validate_with_recovery(xml_source, remove_existing_ev)

        # Save to file
        recovered_tree.write(
            str(output_path),
            encoding=encoding,
            xml_declaration=xml_declaration,
            method='xml'
        )


def validate_with_recovery(schema_path: Union[str, Path],
                            xml_path: Union[str, Path],
                            output_path: Optional[Union[str, Path]] = None,
                            **kwargs) -> ET.ElementTree:
    """
    Convenience function to validate an XML file and insert ExceptionalValues.

    :param schema_path: Path to the XSD schema file.
    :param xml_path: Path to the XML instance file.
    :param output_path: Optional path to save the recovered XML (if None, doesn't save).
    :param kwargs: Additional arguments to pass to SDC4Validator.
    :return: Modified XML ElementTree with ExceptionalValue elements inserted.
    """
    validator = SDC4Validator(schema_path, **kwargs)
    recovered_tree = validator.validate_with_recovery(xml_path)

    if output_path:
        recovered_tree.write(str(output_path), encoding='UTF-8', xml_declaration=True)

    return recovered_tree
