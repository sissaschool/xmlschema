# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains definitions and functions for XSD builtin datatypes.
Only atomic builtins are created because the 3 list builtins types ('NMTOKENS',
'ENTITIES', 'IDREFS') are created using the XSD meta-schema.
"""
from __future__ import unicode_literals
import datetime
import re
import base64
from decimal import Decimal

from ..compat import long_type, unicode_type
from ..exceptions import XMLSchemaValueError
from ..etree import etree_element, is_etree_element
from ..qnames import (
    xsd_qname, XSD_COMPLEX_TYPE_TAG, XSD_SIMPLE_TYPE_TAG, XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG, XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE
)

from .exceptions import XMLSchemaValidationError
from .facets import (
    XsdSingleFacet, XsdPatternsFacet, XSD_10_FACETS, STRING_FACETS,
    BOOLEAN_FACETS, FLOAT_FACETS, DECIMAL_FACETS, DATETIME_FACETS
)
from .simple_types import XsdSimpleType, XsdAtomicBuiltin

_RE_ISO_TIMEZONE = re.compile(r"(Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9])$")
_RE_DURATION = re.compile(r"(-)?P(?=(\d|T))(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$")
_RE_HEX_BINARY = re.compile(r"^[0-9a-fA-F]+$")
_RE_NOT_BASE64_BINARY = re.compile(r"[^0-9a-zA-z+/= \t\n]")


#
# XSD builtin validator functions
def byte_validator(x):
    if not (-2**7 <= x < 2**7):
        yield XMLSchemaValidationError(int_validator, x, "value must be -128 <= x < 128.")


def short_validator(x):
    if not (-2**16 <= x < 2**16):
        yield XMLSchemaValidationError(short_validator, x, "value must be -2^16 <= x < 2^16.")


def int_validator(x):
    if not (-2**63 <= x < 2**63):
        yield XMLSchemaValidationError(int_validator, x, "value must be -2^63 <= x < 2^63.")


def long_validator(x):
    if not (-2**127 <= x < 2**127):
        yield XMLSchemaValidationError(long_validator, x, "value must be -2^127 <= x < 2^127.")


def unsigned_byte_validator(x):
    if not (0 <= x < 2**8):
        yield XMLSchemaValidationError(unsigned_byte_validator, x, "value must be 0 <= x < 256.")


def unsigned_short_validator(x):
    if not (0 <= x < 2**32):
        yield XMLSchemaValidationError(unsigned_short_validator, x, "value must be 0 <= x < 2^32.")


def unsigned_int_validator(x):
    if not (0 <= x < 2**64):
        yield XMLSchemaValidationError(unsigned_int_validator, x, "value must be 0 <= x < 2^64.")


def unsigned_long_validator(x):
    if not (0 <= x < 2**128):
        yield XMLSchemaValidationError(unsigned_long_validator, x, "value must be 0 <= x < 2^128.")


def negative_int_validator(x):
    if x >= 0:
        yield XMLSchemaValidationError(negative_int_validator, x, reason="value must be negative.")


def positive_int_validator(x):
    if x <= 0:
        yield XMLSchemaValidationError(positive_int_validator, x, "value must be positive.")


def non_positive_int_validator(x):
    if x > 0:
        yield XMLSchemaValidationError(non_positive_int_validator, x, "value must be non positive.")


def non_negative_int_validator(x):
    if x < 0:
        yield XMLSchemaValidationError(non_negative_int_validator, x, "value must be non negative.")


def time_validator(x):
    for e in datetime_iso8601_validator(x, '%H:%M:%S', '%H:%M:%S.%f', '24:00:00'):
        yield e
        return

    # Additional XSD restrictions
    try:
        h, m, s = x[:8].split(':')
    except ValueError:
        yield XMLSchemaValidationError(time_validator, x, "wrong format for time (hh:mm:ss.sss required).")
    else:
        if len(h) < 2 or len(m) < 2 or len(s) < 2:
            yield XMLSchemaValidationError(time_validator, x, "hours, minutes and seconds must be two digits each.")


def date_validator(x):
    k = 1 if x.startswith('-') else 0
    try:
        while x[k].isnumeric():
            k += 1
    except IndexError:
        pass

    for e in datetime_iso8601_validator(x[k-4:], '%Y-%m-%d', '-%Y-%m-%d'):
        yield e
        return

    _, m, d = x[k-4:k+6].split('-')
    if len(m) < 2 or len(d) < 2:
        yield XMLSchemaValidationError(date_validator, x, "months and days must be two digits each.")


def datetime_validator(x):
    for e in datetime_iso8601_validator(x, '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
        yield e
        return

    if 'T' not in x:
        yield XMLSchemaValidationError(datetime_validator, x, "T separator must be uppercase.")


def g_year_validator(x):
    k = 1 if x.startswith('-') else 0
    try:
        while x[k].isnumeric():
            k += 1
    except IndexError:
        pass

    for e in datetime_iso8601_validator(x[k-4:], '%Y'):
        yield e


def g_year_month_validator(x):
    for e in datetime_iso8601_validator(x, '%Y-%m'):
        yield e
        return

    # Additional XSD restrictions
    if len(x.strip()[:7].split('-')[1]) < 2:
        yield XMLSchemaValidationError(g_year_month_validator, x, "the month must be two digits.")


def g_month_validator(x):
    for e in datetime_iso8601_validator(x, '--%m'):
        yield e
        return

    # Additional XSD restrictions
    if len(x) < 4:
        yield XMLSchemaValidationError(g_month_validator, x, "the month must be two digits.")


def g_month_day_validator(x):
    for e in datetime_iso8601_validator(x, '--%m-%d'):
        yield e
        return

    # Additional XSD restrictions
    m, d = x[2:].split('-')
    if len(m) < 2 or len(d) < 2:
        yield XMLSchemaValidationError(g_month_day_validator, x, "months and days must be two digits each.")


def g_day_validator(x):
    for e in datetime_iso8601_validator(x, '---%d'):
        yield e
        return

    # Additional XSD restrictions
    if len(x) < 5:
        yield XMLSchemaValidationError(g_day_validator, x, "the day must be two digits.")


def duration_validator(x):
    if _RE_DURATION.match(x) is None:
        yield XMLSchemaValidationError(duration_validator, x, "wrong format (PnYnMnDTnHnMnS required).")


def datetime_iso8601_validator(date_string, *date_formats):
    """
    Validate a string represents a valid datetime ISO 8601 like, according to the
    specified formatting, plus optional timezone specification as suffix.

    :param date_string: The string containing the datetime
    :param date_formats: The reference formatting for datetime
    :return: True if the string is a valid datetime, False if not.
    """
    try:
        date_string, time_zone, _ = _RE_ISO_TIMEZONE.split(date_string)
    except ValueError:
        pass

    if not date_formats:
        date_formats = ('%Y-%m-%d',)

    for fmt in date_formats:
        try:
            datetime.datetime.strptime(date_string, fmt)
        except ValueError:
            pass
        else:
            break
    else:
        yield XMLSchemaValidationError(
            non_negative_int_validator, date_string, "invalid datetime for formats {}.".format(date_formats)
        )


def hex_binary_validator(x):
    if len(x) % 2 or _RE_HEX_BINARY.match(x) is None:
        yield XMLSchemaValidationError(hex_binary_validator, x, "not an hexadecimal number.")


def base64_binary_validator(x):
    match = _RE_NOT_BASE64_BINARY.search(x)
    if match is not None:
        reason = "not a base64 encoding: illegal character %r at position %d." % (match.group(0), match.span()[0])
        yield XMLSchemaValidationError(base64_binary_validator, x, reason)
    else:
        try:
            base64.standard_b64decode(x)
        except (ValueError, TypeError) as err:
            yield XMLSchemaValidationError(base64_binary_validator, x, "not a base64 encoding: %s." % err)


#
# XSD builtin decoding functions
def boolean_to_python(s):
    if s in ('true', '1'):
        return True
    elif s in ('false', '0'):
        return False
    else:
        raise XMLSchemaValueError('not a boolean value: %r' % s)


def python_to_boolean(obj):
    return unicode_type(obj).lower()


#
# Element facets instances for builtin types.
PRESERVE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE_TAG, attrib={'value': 'preserve'})
COLLAPSE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE_TAG, attrib={'value': 'collapse'})
REPLACE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE_TAG, attrib={'value': 'replace'})


XSD_BUILTIN_TYPES = (
    # ***********************
    # *** Primitive types ***
    # ***********************

    # --- String Types ---
    {
        'name': xsd_qname('string'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, PRESERVE_WHITE_SPACE_ELEMENT)
    },  # character string

    # --- Numerical Types ---
    {
        'name': xsd_qname('decimal'),
        'python_type': (Decimal, str, unicode_type, int, float),
        'facets': (DECIMAL_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # decimal number
    {
        'name': xsd_qname('double'),
        'python_type': float,
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },   # 64 bit floating point
    {
        'name': xsd_qname('float'),
        'python_type': float,
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # 32 bit floating point

    # ---Dates and Times---
    {
        'name': xsd_qname('date'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, date_validator)
    },  # CCYY-MM-DD
    {
        'name': xsd_qname('dateTime'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, datetime_validator)
    },  # CCYY-MM-DDThh:mm:ss
    {
        'name': xsd_qname('gDay'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, g_day_validator)
    },  # DD
    {
        'name': xsd_qname('gMonth'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, g_month_validator)
    },  # MM
    {
        'name': xsd_qname('gMonthDay'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, g_month_day_validator)
    },  # MM-DD
    {
        'name': xsd_qname('gYear'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, g_year_validator)
    },  # CCYY
    {
        'name': xsd_qname('gYearMonth'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, g_year_month_validator)
    },  # CCYY-MM
    {
        'name': xsd_qname('time'),
        'python_type': (unicode_type, str),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, time_validator)
    },  # hh:mm:ss
    {
        'name': xsd_qname('duration'),
        'python_type': (unicode_type, str),
        'facets': (
            FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, duration_validator
        )
    },  # PnYnMnDTnHnMnS

    # Other primitive types
    {
        'name': xsd_qname('QName'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # prf:name (the prefix needs to be qualified with an in scope namespace)
    {
        'name': xsd_qname('NOTATION'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # type for NOTATION attributes: QNames of xs:notation declarations as value space.
    {
        'name': xsd_qname('anyURI'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # absolute or relative uri (RFC 2396)
    {
        'name': xsd_qname('boolean'),
        'python_type': bool,
        'facets': (BOOLEAN_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': boolean_to_python,
        'from_python': python_to_boolean,
    },  # true/false or 1/0
    {
        'name': xsd_qname('base64Binary'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, base64_binary_validator)
    },  # base64 encoded binary value
    {
        'name': xsd_qname('hexBinary'),
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, hex_binary_validator)
    },   # hexadecimal encoded binary value

    # *********************
    # *** Derived types ***
    # *********************

    # --- String Types ---
    {
        'name': xsd_qname('normalizedString'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('string'),
        'facets': [REPLACE_WHITE_SPACE_ELEMENT]
    },  # line breaks are normalized
    {
        'name': xsd_qname('token'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('normalizedString'),
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT]
    },  # whitespaces are normalized
    {
        'name': xsd_qname('language'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('token'),
        'facets': [
            etree_element(XSD_PATTERN_TAG, attrib={
                'value': r"([a-zA-Z]{2}|[iI]-[a-zA-Z]+|[xX]-[a-zA-Z]{1,8})(-[a-zA-Z]{1,8})*"
            })
        ]
    },  # language codes
    {
        'name': xsd_qname('Name'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('token'),
        'facets': [etree_element(XSD_PATTERN_TAG, attrib={'value': r"\i\c*"})]
    },  # not starting with a digit
    {
        'name': xsd_qname('NCName'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('Name'),
        'facets': [etree_element(XSD_PATTERN_TAG, attrib={'value': r"[\i-[:]][\c-[:]]*"})]
    },  # cannot contain colons
    {
        'name': xsd_qname('ID'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('NCName')
    },  # unique identification in document (attribute only)
    {
        'name': xsd_qname('IDREF'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('NCName')
    },  # reference to ID field in document (attribute only)
    {
        'name': xsd_qname('ENTITY'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('NCName')
    },  # reference to entity (attribute only)
    {
        'name': xsd_qname('NMTOKEN'),
        'python_type': (unicode_type, str),
        'base_type': xsd_qname('token'),
        'facets': [etree_element(XSD_PATTERN_TAG, attrib={'value': r"\c+"})]
    },  # should not contain whitespace (attribute only)

    # --- Numerical derived types ---
    {
        'name': xsd_qname('integer'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('decimal')
    },  # any integer value
    {
        'name': xsd_qname('long'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('integer'),
        'facets': [long_validator]
    },  # signed 128 bit value
    {
        'name': xsd_qname('int'),
        'python_type': int,
        'base_type': xsd_qname('long'),
        'facets': [int_validator]
    },  # signed 64 bit value
    {
        'name': xsd_qname('short'),
        'python_type': int,
        'base_type': xsd_qname('int'),
        'facets': [short_validator]
    },  # signed 32 bit value
    {
        'name': xsd_qname('byte'),
        'python_type': int,
        'base_type': xsd_qname('short'),
        'facets': [byte_validator]
    },  # signed 8 bit value
    {
        'name': xsd_qname('nonNegativeInteger'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('integer'),
        'facets': [non_negative_int_validator]
    },  # only zero and more value allowed [>= 0]
    {
        'name': xsd_qname('positiveInteger'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('nonNegativeInteger'),
        'facets': [positive_int_validator]
    },  # only positive value allowed [> 0]
    {
        'name': xsd_qname('unsignedLong'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('nonNegativeInteger'),
        'facets': [unsigned_long_validator]
    },  # unsigned 128 bit value
    {
        'name': xsd_qname('unsignedInt'),
        'python_type': int,
        'base_type': xsd_qname('unsignedLong'),
        'facets': [unsigned_int_validator]
    },  # unsigned 64 bit value
    {
        'name': xsd_qname('unsignedShort'),
        'python_type': int,
        'base_type': xsd_qname('unsignedInt'),
        'facets': [unsigned_short_validator]
    },  # unsigned 32 bit value
    {
        'name': xsd_qname('unsignedByte'),
        'python_type': int,
        'base_type': xsd_qname('unsignedShort'),
        'facets': [unsigned_byte_validator]
    },  # unsigned 8 bit value
    {
        'name': xsd_qname('nonPositiveInteger'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('integer'),
        'facets': [non_positive_int_validator]
    },  # only zero and smaller value allowed [<= 0]
    {
        'name': xsd_qname('negativeInteger'),
        'python_type': (long_type, int),
        'base_type': xsd_qname('nonPositiveInteger'),
        'facets': [negative_int_validator]
    }  # only negative value allowed [< 0]
)


def xsd_build_facets(schema, parent, base_type, items):
    facets = {}
    keys = schema.FACETS
    for obj in items:
        if isinstance(obj, (list, tuple, set)):
            facets.update([(k, None) for k in obj if k in keys])
        elif is_etree_element(obj):
            if obj.tag in keys:
                if obj.tag == XSD_PATTERN_TAG:
                    facets[obj.tag] = XsdPatternsFacet(obj, schema, parent, base_type)
                else:
                    facets[obj.tag] = XsdSingleFacet(obj, schema, parent, base_type)
        elif callable(obj):
            if None in facets:
                raise XMLSchemaValueError("Almost one callable for facet group!!")
            facets[None] = obj
        else:
            raise XMLSchemaValueError("Wrong type for item %r" % obj)
    return facets


def xsd_builtin_types_factory(meta_schema, xsd_types, xsd_class=None):
    """
    Builds the dictionary for XML Schema built-in types mapping.
    """
    #
    # Special builtin types.
    #
    # xs:anyType
    # Ref: https://www.w3.org/TR/xmlschema11-1/#builtin-ctd
    any_type = meta_schema.BUILDERS.complex_type_class(
        elem=etree_element(XSD_COMPLEX_TYPE_TAG, attrib={'name': XSD_ANY_TYPE}),
        schema=meta_schema,
        parent=None,
        mixed=True
    )
    any_type.content_type = meta_schema.create_any_content_group(any_type)
    any_type.attributes = meta_schema.create_any_attribute_group(any_type)
    xsd_types[XSD_ANY_TYPE] = any_type

    # xs:anySimpleType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_SIMPLE_TYPE] = XsdSimpleType(
        elem=etree_element(XSD_SIMPLE_TYPE_TAG, attrib={'name': XSD_ANY_SIMPLE_TYPE}),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_SIMPLE_TYPE,
        facets={k: None for k in XSD_10_FACETS}
    )

    # xs:anyAtomicType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_ATOMIC_TYPE] = meta_schema.BUILDERS.restriction_class(
        elem=etree_element(XSD_SIMPLE_TYPE_TAG, attrib={'name': XSD_ANY_ATOMIC_TYPE}),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_ATOMIC_TYPE,
        base_type=xsd_types[XSD_ANY_SIMPLE_TYPE]
    )

    xsd_class = xsd_class or XsdAtomicBuiltin
    for item in XSD_BUILTIN_TYPES:
        item = item.copy()
        name = item['name']
        try:
            elem, schema = xsd_types[name]
        except KeyError:
            # If builtin type element is missing create a dummy element. Necessary for the
            # meta-schema XMLSchema.xsd of XSD 1.1, that not includes builtins declarations.
            elem = etree_element(XSD_SIMPLE_TYPE_TAG, attrib={'name': name, 'id': name})
        else:
            if schema is not meta_schema:
                raise XMLSchemaValueError("loaded entry schema doesn't match meta_schema!")

        if item.get('base_type'):
            base_type = item.get('base_type')
            item['base_type'] = xsd_types[base_type]
        elif item.get('item_type'):
            base_type = item.get('item_type')
            item['item_type'] = xsd_types[base_type]
        else:
            base_type = None

        if 'facets' in item:
            facets = item.pop('facets')
            builtin_type = xsd_class(elem, meta_schema, **item)
            builtin_type.facets = xsd_build_facets(meta_schema, builtin_type, base_type, facets)
        else:
            builtin_type = xsd_class(elem, meta_schema, **item)

        xsd_types[item['name']] = builtin_type
