# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains definitions and functions for XSD builtin datatypes.
"""
import datetime
import re
from decimal import Decimal

from .core import PY3
from .exceptions import XMLSchemaValidationError
from .xsdbase import xsd_qname
from .structures import (
    XsdSimpleType, XsdAtomicType, XsdRestriction, XsdList, XsdAttributeGroup,
    XsdGroup, XsdComplexType, XsdAnyAttribute, XsdAnyElement
)

_RE_ISO_TIMEZONE = re.compile(r"(Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9])$")

long_type = int if PY3 else long


#
# XSD builtin validator functions
def byte_validator(x):
    if not (-2**7 <= x < 2**7):
        raise XMLSchemaValidationError(int_validator, x, "value must be -128 <= x < 128.")


def short_validator(x):
    if not (-2**16 <= x < 2**16):
        raise XMLSchemaValidationError(short_validator, x, "value must be -2^16 <= x < 2^16.")


def int_validator(x):
    if not (-2**63 <= x < 2**63):
        raise XMLSchemaValidationError(int_validator, x, "value must be -2^63 <= x < 2^63.")


def long_validator(x):
    if not (-2**127 <= x < 2**127):
        raise XMLSchemaValidationError(long_validator, x, "value must be -2^127 <= x < 2^127.")


def unsigned_byte_validator(x):
    if not (0 <= x < 2**8):
        raise XMLSchemaValidationError(unsigned_byte_validator, x, "value must be 0 <= x < 256.")


def unsigned_short_validator(x):
    if not (0 <= x < 2**32):
        raise XMLSchemaValidationError(unsigned_short_validator, x, "value must be 0 <= x < 2^32.")


def unsigned_int_validator(x):
    if not (0 <= x < 2**64):
        raise XMLSchemaValidationError(unsigned_int_validator, x, "value must be 0 <= x < 2^64.")


def unsigned_long_validator(x):
    if not (0 <= x < 2**128):
        raise XMLSchemaValidationError(unsigned_long_validator, x, "value must be 0 <= x < 2^128.")


def negative_int_validator(x):
    if x >= 0:
        raise XMLSchemaValidationError(negative_int_validator, x, reason="value must be negative.")


def positive_int_validator(x):
    if x <= 0:
        raise XMLSchemaValidationError(positive_int_validator, x, "value must be positive.")


def non_positive_int_validator(x):
    if x > 0:
        raise XMLSchemaValidationError(non_positive_int_validator, x, "value must be non positive.")


def non_negative_int_validator(x):
    if x < 0:
        raise XMLSchemaValidationError(non_negative_int_validator, x, "value must be non negative.")


def datetime_iso8601_validator(date_string, date_format='%Y-%m-%d'):
    """
    Validate a string represents a valid datetime ISO 8601 like, according to the
    specified formatting, plus optional timezone specification as suffix.

    :param date_string: The string containing the datetime
    :param date_format: The reference formatting for datetime
    :return: True if the string is a valid datetime, False if not.
    """
    try:
        date_string, time_zone, _ = _RE_ISO_TIMEZONE.split(date_string)
    except ValueError:
        pass

    try:
        datetime.datetime.strptime(date_string, date_format)
    except ValueError:
        raise XMLSchemaValidationError(
            non_negative_int_validator, date_string, "invalid datetime for format %r." % date_format
        )


#
# XSD builtin datatypes qualified names
XSD_STRING_TAG = xsd_qname('string')
XSD_NMTOKEN_TAG = xsd_qname('NMTOKEN')
XSD_NMTOKENS_TAG = xsd_qname('NMTOKENS')
XSD_ENTITY_TAG = xsd_qname('ENTITY')
XSD_ENTITIES_TAG = xsd_qname('ENTITIES')
XSD_IDREF_TAG = xsd_qname('IDREF')
XSD_IDREFS_TAG = xsd_qname('IDREFS')
XSD_DECIMAL_TAG = xsd_qname('decimal')
XSD_QNAME_TAG = xsd_qname('QName')
XSD_ANYURI_TAG = xsd_qname('anyURI')
XSD_BOOLEAN_TAG = xsd_qname('boolean')
XSD_BASE64BINARY_TAG = xsd_qname('base64Binary')
XSD_HEXBINARY_TAG = xsd_qname('hexBinary')


def _build_xsd_builtin(builtin_dict):
    for key, value in builtin_dict.items():
        if isinstance(value, XsdAtomicType):
            continue
        elif isinstance(value, tuple):
            builtin_dict[key] = XsdAtomicType(key, *value)
        else:
            builtin_dict[key] = XsdAtomicType(key, value)
    return builtin_dict


XSD_BUILTIN_PRIMITIVE_TYPES = _build_xsd_builtin({
    # --- String Types ---
    XSD_STRING_TAG: str,  # character string

    # --- Numerical Types ---
    XSD_DECIMAL_TAG: Decimal,  # decimal number
    xsd_qname('double'): float,  # 64 bit floating point
    xsd_qname('float'): float,  # 32 bit floating point

    # ---Dates and Times---
    xsd_qname('date'): (str, None, [lambda x: datetime_iso8601_validator(x)]),  # CCYY-MM-DD
    xsd_qname('dateTime'):
        (str, None, [lambda x: datetime_iso8601_validator(x, '%Y-%m-%dT%H:%M:%S')]),  # CCYY-MM-DDThh:mm:ss
    xsd_qname('gDay'): (str, None, [lambda x: datetime_iso8601_validator(x, '%d')]),  # DD
    xsd_qname('gMonth'): (str, None, [lambda x: datetime_iso8601_validator(x, '%m')]),  # MM
    xsd_qname('gMonthDay'): (str, None, [lambda x: datetime_iso8601_validator(x, '%m-%d')]),  # MM-DD
    xsd_qname('gYear'): (str, None, [lambda x: datetime_iso8601_validator(x, '%Y')]),  # CCYY
    xsd_qname('gYearMonth'): (str, None, [lambda x: datetime_iso8601_validator(x, '%Y-%m')]),  # CCYY-MM
    xsd_qname('time'): (str, None, [lambda x: datetime_iso8601_validator(x, '%H:%M:%S')]),  # hh:mm:ss
    xsd_qname('duration'): str,  # PnYnMnDTnHnMnS

    # Other primitive types
    xsd_qname('QName'): str,  # prf:name (the prefix needs to be qualified with an in scope namespace)
    XSD_ANYURI_TAG: str,  # absolute or relative uri (RFC 2396)
    xsd_qname('boolean'): (
        bool, None, None,
        lambda x: True if x.strip() in ('true', '1') else False if x.strip() in ('false', '0') else None,
        lambda x: str(x).lower()
    ),  # true/false or 1/0
    xsd_qname('base64Binary'): str,  # base64 encoded binary value
    xsd_qname('hexBinary'): str  # hexadecimal encoded binary value
})

XSD_STRING_TYPE = XSD_BUILTIN_PRIMITIVE_TYPES[XSD_STRING_TAG]
XSD_DECIMAL_TYPE = XSD_BUILTIN_PRIMITIVE_TYPES[XSD_DECIMAL_TAG]
ANY_URI_TYPE = XSD_BUILTIN_PRIMITIVE_TYPES[XSD_ANYURI_TAG]


XSD_BUILTIN_OTHER_ATOMIC_TYPES = _build_xsd_builtin({
    # --- String Types ---
    xsd_qname('normalizedString'): (str, XSD_STRING_TYPE),  # line breaks are normalized
    xsd_qname('token'): (str, XSD_STRING_TYPE),  # whitespace is normalized
    xsd_qname('NMTOKEN'): (str, XSD_STRING_TYPE),  # should not contain whitespace (attribute only)
    xsd_qname('Name'): (str, XSD_STRING_TYPE),  # not starting with a digit
    xsd_qname('NCName'): (str, XSD_STRING_TYPE),  # cannot contain colons
    xsd_qname('ID'): (str, XSD_STRING_TYPE),  # unique identification in document (attribute only)
    xsd_qname('IDREF'): (str, XSD_STRING_TYPE),  # reference to ID field in document (attribute only)
    xsd_qname('ENTITY'): (str, XSD_STRING_TYPE),  # reference to entity (attribute only)
    xsd_qname('language'): (str, XSD_STRING_TYPE),  # language codes

    # --- Numerical Types ---
    xsd_qname('byte'): (int, XSD_DECIMAL_TYPE, [byte_validator]),  # signed 8 bit value
    xsd_qname('int'): (int, XSD_DECIMAL_TYPE, [int_validator]),  # signed 64 bit value
    xsd_qname('integer'): (int, XSD_DECIMAL_TYPE),  # any integer value
    xsd_qname('long'): (long_type, XSD_DECIMAL_TYPE, [long_validator]),  # signed 128 bit value
    xsd_qname('negativeInteger'):
        (long_type, XSD_DECIMAL_TYPE, [negative_int_validator]),  # only negative value allowed [< 0]
    xsd_qname('positiveInteger'):
        (long_type, XSD_DECIMAL_TYPE, [positive_int_validator]),  # only positive value allowed [> 0]
    xsd_qname('nonPositiveInteger'):
        (long_type, XSD_DECIMAL_TYPE, [non_positive_int_validator]),  # only zero and smaller value allowed [<= 0]
    xsd_qname('nonNegativeInteger'):
        (long_type, XSD_DECIMAL_TYPE, [non_negative_int_validator]),  # only zero and more value allowed [>= 0]
    xsd_qname('short'):
        (int, XSD_DECIMAL_TYPE, [short_validator]),  # signed 32 bit value
    xsd_qname('unsignedByte'):
        (int, XSD_DECIMAL_TYPE, [unsigned_byte_validator]),  # unsigned 8 bit value
    xsd_qname('unsignedInt'):
        (int, XSD_DECIMAL_TYPE, [unsigned_int_validator]),  # unsigned 64 bit value
    xsd_qname('unsignedLong'):
        (long_type, XSD_DECIMAL_TYPE, [unsigned_long_validator]),  # unsigned 128 bit value
    xsd_qname('unsignedShort'):
        (int, XSD_DECIMAL_TYPE, [unsigned_short_validator]),  # unsigned 32 bit value
})

XSD_NMTOKEN_TYPE = XSD_BUILTIN_OTHER_ATOMIC_TYPES[XSD_NMTOKEN_TAG]
XSD_ENTITY_TYPE = XSD_BUILTIN_OTHER_ATOMIC_TYPES[XSD_ENTITY_TAG]
XSD_IDREF_TYPE = XSD_BUILTIN_OTHER_ATOMIC_TYPES[XSD_IDREF_TAG]

XSD_BUILTIN_LIST_TYPES = {
    XSD_NMTOKENS_TAG: XsdList(XSD_NMTOKEN_TYPE, XSD_NMTOKENS_TAG),
    XSD_ENTITIES_TAG: XsdList(XSD_ENTITY_TYPE, XSD_ENTITIES_TAG),
    XSD_IDREFS_TAG: XsdList(XSD_IDREF_TYPE, XSD_IDREFS_TAG)
}

ANY_TYPE = XsdComplexType(
    content_type=XsdGroup(initlist=[XsdAnyElement()]),
    name=xsd_qname('anyType'),
    attributes=XsdAttributeGroup(initdict={None: XsdAnyAttribute()}),
    mixed=True
)
ANY_SIMPLE_TYPE = XsdSimpleType(xsd_qname('anySimpleType'))
ANY_ATOMIC_TYPE = XsdRestriction(base_type=ANY_SIMPLE_TYPE, name=xsd_qname('anyAtomicType'))

#
# Build XSD built-in types dictionary
_builtin_types = {
    ANY_TYPE.name: ANY_TYPE,
    ANY_SIMPLE_TYPE.name: ANY_SIMPLE_TYPE,
    ANY_ATOMIC_TYPE.name: ANY_ATOMIC_TYPE
}

_builtin_types.update(XSD_BUILTIN_PRIMITIVE_TYPES)
_builtin_types.update(XSD_BUILTIN_OTHER_ATOMIC_TYPES)
_builtin_types.update(XSD_BUILTIN_LIST_TYPES)

XSD_BUILTIN_TYPES = _builtin_types
"""Dictionary for XML Schema built-in types mapping. The values are XSDType instances"""
