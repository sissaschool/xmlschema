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
This module contains XSD types builtins.
"""
import datetime
import re
from decimal import Decimal

from .qnames import xsd_qname
from .exceptions import XMLSchemaValidationError
from .core import PY3
from .validators import (
    XsdAttributeGroup, XsdGroup, XsdSimpleType, XsdAtomicType,
    XsdList, XsdComplexType, XsdAnyAttribute, XsdAnyElement
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
# XSD builtin datatypes declaration map
_XSD_BUILTIN_ATOMIC_TYPES = (
    # --- String Types ---
    ('string', str),  # character string
    ('normalizedString', str),  # line breaks are normalized
    ('token', str),  # whitespace is normalized
    ('NMTOKEN', str),  # should not contain whitespace (attribute only)
    ('Name', str),  # not starting with a digit
    ('NCName', str),  # cannot contain colons
    ('ID', str),  # unique identification in document (attribute only)
    ('IDREF', str),  # reference to ID field in document (attribute only)
    ('ENTITY', str),  # reference to entity (attribute only)
    ('language', str),  # language codes

    # --- Numerical Types ---
    ('byte', int, [byte_validator]),  # signed 8 bit value
    ('decimal', Decimal),  # decimal number
    ('double', float),  # 64 bit floating point
    ('float', float),  # 32 bit floating point
    ('int', int, [int_validator]),  # signed 64 bit value
    ('integer', int),  # any integer value
    ('long', long_type, [long_validator]),  # signed 128 bit value
    ('negativeInteger', long_type, [negative_int_validator]),  # only negative value allowed [< 0]
    ('positiveInteger', long_type, [positive_int_validator]),  # only positive value allowed [> 0]
    ('nonPositiveInteger', long_type, [non_positive_int_validator]),  # only zero and smaller value allowed [<= 0]
    ('nonNegativeInteger', long_type, [non_negative_int_validator]),  # only zero and more value allowed [>= 0]
    ('short', int, [short_validator]),  # signed 32 bit value
    ('unsignedByte', int, [unsigned_byte_validator]),  # unsigned 8 bit value
    ('unsignedInt', int, [unsigned_int_validator]),  # unsigned 64 bit value
    ('unsignedLong', long_type, [unsigned_long_validator]),  # unsigned 128 bit value
    ('unsignedShort', int, [unsigned_short_validator]),  # unsigned 32 bit value

    # ---Dates and Times---
    ('date', str, [lambda x: datetime_iso8601_validator(x)]),  # CCYY-MM-DD
    ('dateTime', str, [lambda x: datetime_iso8601_validator(x, '%Y-%m-%dT%H:%M:%S')]),  # CCYY-MM-DDThh:mm:ss
    ('gDay', str, [lambda x: datetime_iso8601_validator(x, '%d')]),  # DD
    ('gMonth', str, [lambda x: datetime_iso8601_validator(x, '%m')]),  # MM
    ('gMonthDay', str, [lambda x: datetime_iso8601_validator(x, '%m-%d')]),  # MM-DD
    ('gYear', str, [lambda x: datetime_iso8601_validator(x, '%Y')]),  # CCYY
    ('gYearMonth', str, [lambda x: datetime_iso8601_validator(x, '%Y-%m')]),  # CCYY-MM
    ('time', str, [lambda x: datetime_iso8601_validator(x, '%H:%M:%S')]),  # hh:mm:ss
    ('duration', str),  # PnYnMnDTnHnMnS

    # Other types
    ('QName', str),  # prf:name (the prefix needs to be qualified with an in scope namespace)
    ('anyURI', str),  # absolute or relative uri (RFC 2396)
    ('boolean', bool, None,
     lambda x: True if x.strip() in ('true', '1') else False if x.strip() in ('false', '0') else None,
     lambda x: str(x).lower()),  # true/false or 1/0
    ('base64Binary', str),  # base64 encoded binary value
    ('hexBinary', str)  # hexadecimal encoded binary value
)

_XSD_BUILTIN_LIST_TYPES = (
    ('NMTOKENS', 'NMTOKEN'),    # list of NMTOKENs (attribute only)
    ('ENTITIES', 'ENTITY'),     # list of references to entities (attribute only)
    ('IDREFS', 'IDREF')         # list of references to ID fields in document (attribute only)
)

ANY_TYPE = XsdComplexType(
    content_type=XsdGroup(initlist=[XsdAnyElement()]),
    name=xsd_qname('anyType'),
    attributes=XsdAttributeGroup(initdict={None: XsdAnyAttribute()}),
    mixed=True
)
ANY_SIMPLE_TYPE = XsdSimpleType(xsd_qname('anySimpleType'))

#
# Build XSD built-in types dictionary
_builtin_types = {
    ANY_TYPE.name: ANY_TYPE,
    ANY_SIMPLE_TYPE.name: ANY_SIMPLE_TYPE
}
_builtin_types.update({
    name: XsdAtomicType(name, *args)
    for name, args in map(lambda x: (xsd_qname(x[0]), x[1:]), _XSD_BUILTIN_ATOMIC_TYPES)
})
_builtin_types.update({
    name: XsdList(_builtin_types[type_name], name)
    for name, type_name in map(lambda x: (xsd_qname(x[0]), xsd_qname(x[1])), _XSD_BUILTIN_LIST_TYPES)
})

XSD_BUILTIN_TYPES = _builtin_types
"""Dictionary for XML Schema built-in types mapping. The values are XSDType instances"""

ANY_URI_TYPE = XSD_BUILTIN_TYPES[xsd_qname('anyURI')]
