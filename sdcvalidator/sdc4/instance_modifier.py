#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
Modifies XML instance documents to insert SDC4 ExceptionalValue elements.
"""

from typing import Optional, Dict, Any
from xml.etree import ElementTree as ET
from .constants import (
    SDC4_NAMESPACE,
    ExceptionalValueType,
    EXCEPTIONAL_VALUE_INSERT_AFTER,
    EXCEPTIONAL_VALUE_INSERT_BEFORE
)


class InstanceModifier:
    """
    Modifies XML instance documents by inserting ExceptionalValue elements
    at validation error locations.

    Uses the SDC4 "quarantine-and-tag" pattern where invalid values are
    preserved and flagged with ExceptionalValue elements.
    """

    def __init__(self, namespace_prefix: str = 'sdc4'):
        """
        Initialize the instance modifier.

        :param namespace_prefix: The XML namespace prefix to use for SDC4 elements (default: 'sdc4').
        """
        self.namespace_prefix = namespace_prefix
        self.sdc4_ns = SDC4_NAMESPACE

    def insert_exceptional_value(self,
                                   root: ET.Element,
                                   xpath: str,
                                   ev_type: ExceptionalValueType,
                                   reason: Optional[str] = None) -> bool:
        """
        Insert an ExceptionalValue element at the specified XPath location.

        :param root: The root element of the XML document.
        :param xpath: XPath to the element where the error occurred.
        :param ev_type: The ExceptionalValueType to insert.
        :param reason: Optional additional reason text.
        :return: True if insertion was successful, False otherwise.
        """
        # Ensure namespace is registered
        self._register_namespace()

        # Find the target element using XPath
        target_elem = self._find_element_by_xpath(root, xpath)
        if target_elem is None:
            return False

        # Create the ExceptionalValue element
        ev_element = self._create_exceptional_value_element(ev_type, reason)

        # Insert at the appropriate position in the sequence
        insert_pos = self._find_insertion_position(target_elem)
        target_elem.insert(insert_pos, ev_element)

        return True

    def _register_namespace(self):
        """Register the SDC4 namespace with ElementTree."""
        try:
            ET.register_namespace(self.namespace_prefix, self.sdc4_ns)
        except Exception:
            # Namespace might already be registered
            pass

    def _find_element_by_xpath(self, root: ET.Element, xpath: str) -> Optional[ET.Element]:
        """
        Find an element by XPath.

        :param root: The root element to search from.
        :param xpath: The XPath expression.
        :return: The found element or None.
        """
        if not xpath:
            return None

        # Handle namespace prefixes in XPath
        # Convert xpath like /ns:root/ns:child to proper namespaced search
        namespaces = self._extract_namespaces(root)

        try:
            # Try direct XPath first
            elements = root.findall(xpath, namespaces)
            if elements:
                return elements[0]

            # If that fails, try a simpler approach for direct paths
            # This handles cases where the error path is relative or simplified
            if xpath.startswith('/'):
                xpath = '.' + xpath

            elements = root.findall(xpath, namespaces)
            if elements:
                return elements[0]

        except Exception as e:
            # If XPath fails, try to parse it manually
            # This is a fallback for complex XPath expressions
            return self._find_element_by_manual_parse(root, xpath)

        return None

    def _extract_namespaces(self, root: ET.Element) -> Dict[str, str]:
        """
        Extract namespace mappings from the root element.

        :param root: The root element.
        :return: Dictionary of namespace prefix to URI mappings.
        """
        namespaces = {}

        # Get namespace map from root
        for prefix, uri in root.attrib.items():
            if prefix.startswith('{http://www.w3.org/2000/xmlns/}'):
                prefix_name = prefix.split('}')[1]
                namespaces[prefix_name] = uri
            elif prefix == 'xmlns':
                namespaces[''] = root.attrib[prefix]

        # Walk through the tree to find all namespace declarations
        for elem in root.iter():
            tag = elem.tag
            if tag.startswith('{'):
                ns_uri = tag[1:tag.index('}')]
                # Try to find or assign a prefix for this namespace
                if ns_uri not in namespaces.values():
                    # Look for existing prefix in attribs
                    for key, value in elem.attrib.items():
                        if key.startswith('{http://www.w3.org/2000/xmlns/}'):
                            prefix_name = key.split('}')[1]
                            if value == ns_uri:
                                namespaces[prefix_name] = ns_uri
                                break

        # Ensure sdc4 namespace is included
        if SDC4_NAMESPACE not in namespaces.values():
            namespaces[self.namespace_prefix] = SDC4_NAMESPACE

        return namespaces

    def _find_element_by_manual_parse(self, root: ET.Element, xpath: str) -> Optional[ET.Element]:
        """
        Manually parse XPath for simple cases when ElementTree XPath fails.

        :param root: The root element.
        :param xpath: The XPath expression.
        :return: The found element or None.
        """
        # This is a simplified XPath parser for basic paths like /root/child[1]/grandchild
        # For more complex XPath, this should be enhanced or use a proper XPath library

        parts = xpath.strip('/').split('/')
        current = root

        for part in parts:
            # Handle indexed access like element[1]
            if '[' in part and ']' in part:
                elem_name = part[:part.index('[')]
                index_str = part[part.index('[') + 1:part.index(']')]
                try:
                    index = int(index_str) - 1  # XPath is 1-indexed
                except ValueError:
                    # Complex predicate, skip for now
                    return None

                children = [child for child in current if self._local_name(child.tag) == elem_name]
                if index < len(children):
                    current = children[index]
                else:
                    return None
            else:
                # Simple element name
                found = False
                for child in current:
                    if self._local_name(child.tag) == part:
                        current = child
                        found = True
                        break
                if not found:
                    return None

        return current

    def _local_name(self, tag: str) -> str:
        """Extract the local name from a namespaced tag."""
        if tag.startswith('{'):
            return tag[tag.index('}') + 1:]
        return tag

    def _create_exceptional_value_element(self,
                                           ev_type: ExceptionalValueType,
                                           reason: Optional[str] = None) -> ET.Element:
        """
        Create an ExceptionalValue element.

        :param ev_type: The ExceptionalValueType.
        :param reason: Optional additional reason text.
        :return: The created element.
        """
        # Create element with namespaced tag
        tag = f"{{{self.sdc4_ns}}}{ev_type.code}"
        ev_elem = ET.Element(tag)

        # Add the ev-name child element
        ev_name_elem = ET.SubElement(ev_elem, f"{{{self.sdc4_ns}}}ev-name")
        ev_name_elem.text = ev_type.ev_name

        # Optionally add reason as a comment or custom element
        if reason:
            comment = ET.Comment(f" Validation error: {reason} ")
            ev_elem.insert(0, comment)

        return ev_elem

    def _find_insertion_position(self, parent: ET.Element) -> int:
        """
        Find the correct position to insert the ExceptionalValue element.

        Per SDC4 schema, ExceptionalValue should come after 'label' and 'act',
        but before 'vtb', 'vte', 'tr', 'modified', etc.

        :param parent: The parent element.
        :return: The index position to insert at.
        """
        # Find the last occurrence of elements that should come before ExceptionalValue
        insert_pos = 0

        for i, child in enumerate(parent):
            local_name = self._local_name(child.tag)

            # Skip existing ExceptionalValue elements
            if local_name in ['INV', 'OTH', 'UNC', 'NI', 'NA', 'UNK', 'ASKU', 'ASKR',
                              'NASK', 'NAV', 'MSK', 'DER', 'PINF', 'NINF', 'TRC', 'QS']:
                continue

            # Check if this element should come before ExceptionalValue
            if local_name in EXCEPTIONAL_VALUE_INSERT_AFTER:
                insert_pos = i + 1
            elif local_name in EXCEPTIONAL_VALUE_INSERT_BEFORE:
                # Stop here - don't go past elements that should come after
                break
            elif local_name.endswith('-value') or local_name.endswith('-units'):
                # These are the value elements, ExceptionalValue should come before them
                break

        return insert_pos

    def remove_existing_exceptional_values(self, root: ET.Element):
        """
        Remove any existing ExceptionalValue elements from the document.

        :param root: The root element of the XML document.
        """
        ev_codes = ['INV', 'OTH', 'UNC', 'NI', 'NA', 'UNK', 'ASKU', 'ASKR',
                    'NASK', 'NAV', 'MSK', 'DER', 'PINF', 'NINF', 'TRC', 'QS']

        for elem in root.iter():
            for child in list(elem):
                local_name = self._local_name(child.tag)
                if local_name in ev_codes:
                    elem.remove(child)
