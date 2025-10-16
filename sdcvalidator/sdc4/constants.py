#
# Copyright (c), 2025, Axius-SDC, Inc.
# All rights reserved.
# This file is distributed under the terms of the MIT License.
#
"""
Constants and type definitions for SDC4 integration.
"""

from enum import Enum
from typing import Dict

# SDC4 Namespace URIs
SDC4_NAMESPACE = "https://semanticdatacharter.com/ns/sdc4/"
SDC4_META_NAMESPACE = "https://semanticdatacharter.com/ontology/sdc4-meta/"
XSD_NAMESPACE = "http://www.w3.org/2001/XMLSchema"


class ExceptionalValueType(Enum):
    """
    SDC4 ExceptionalValue types based on ISO 21090 NULL Flavors.

    These types indicate why data is missing or invalid. All types inherit
    from ExceptionalValueType in the SDC4 reference model.
    """

    # Primary types for validation errors
    INV = ("INV", "Invalid",
           "The value as represented in the instance is not a member of the "
           "set of permitted data values in the constrained value domain of a variable.")

    OTH = ("OTH", "Other",
           "The actual value is not a member of the permitted data values in the "
           "variable (e.g., when the value of the variable is not by the coding system).")

    UNC = ("UNC", "Unencoded",
           "No attempt has been made to encode the information correctly but the "
           "raw source information is represented, usually in free text.")

    # Missing data types
    NI = ("NI", "No Information",
          "The value is exceptional (missing, omitted, incomplete, improper). "
          "No information as to the reason for being an exceptional value is provided. "
          "This is the most general exceptional value and the default.")

    NA = ("NA", "Not Applicable",
          "No proper value is applicable in this context (e.g., the number of "
          "cigarettes smoked per day by a non-smoker subject).")

    UNK = ("UNK", "Unknown",
           "A proper value is applicable, but not known.")

    ASKU = ("ASKU", "Asked but Unknown",
            "Information was sought but not found (e.g., patient was asked but did not know).")

    ASKR = ("ASKR", "Asked and Refused",
            "Information was sought but refused to be provided (e.g., patient was "
            "asked but refused to answer).")

    NASK = ("NASK", "Not Asked",
            "This information has not been sought (e.g., patient was not asked).")

    NAV = ("NAV", "Not Available",
           "This information is not available and the specific reason is not known.")

    MSK = ("MSK", "Masked",
           "There is information on this item available but it has not been provided "
           "by the sender due to security, privacy or other reasons.")

    # Special value types
    DER = ("DER", "Derived",
           "An actual value may exist, but it must be derived from the provided "
           "information; usually an expression is provided directly.")

    PINF = ("PINF", "Positive Infinity", "Positive infinity of numbers.")

    NINF = ("NINF", "Negative Infinity", "Negative infinity of numbers.")

    TRC = ("TRC", "Trace",
           "The content is greater or less than zero but too small to be quantified.")

    QS = ("QS", "Sufficient Quantity",
          "The specific quantity is not known, but is known to non-zero and it is "
          "not specified because it makes up the bulk of the material.")

    def __init__(self, code: str, name: str, description: str):
        self.code = code
        self.ev_name = name
        self.description = description

    @classmethod
    def from_code(cls, code: str) -> 'ExceptionalValueType':
        """Get ExceptionalValueType from its code string."""
        for ev_type in cls:
            if ev_type.code == code:
                return ev_type
        raise ValueError(f"Unknown ExceptionalValue code: {code}")


# Mapping of ExceptionalValue types to their codes and names
EXCEPTIONAL_VALUE_TYPES: Dict[str, tuple] = {
    ev_type.code: (ev_type.ev_name, ev_type.description)
    for ev_type in ExceptionalValueType
}


# XPath patterns for locating elements in SDC4 data model instances
XDANY_TYPE_PATTERN = r"xd(?:string|count|quantity|boolean|file|link|temporal|ordinal|ratio|interval)-value"

# Element sequence position for ExceptionalValue in XdAnyType
# Per SDC4 schema: label, act, ExceptionalValue, vtb, vte, tr, modified, latitude, longitude, ...
EXCEPTIONAL_VALUE_INSERT_AFTER = ['label', 'act']
EXCEPTIONAL_VALUE_INSERT_BEFORE = ['vtb', 'vte', 'tr', 'modified', 'latitude', 'longitude']
