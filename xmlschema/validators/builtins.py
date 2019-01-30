# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains definitions and functions for XSD builtin datatypes.

Only atomic builtins are created, the list builtins types ('NMTOKENS', 'ENTITIES', 'IDREFS')
are created using the XSD 1.0 meta-schema or with and additional base schema for XSD 1.1.
"""
from __future__ import unicode_literals

import re
import base64
from decimal import Decimal

from elementpath import datatypes

from ..compat import PY3, long_type, unicode_type
from ..exceptions import XMLSchemaValueError
from ..qnames import *
from ..etree import etree_element, is_etree_element
from .exceptions import XMLSchemaValidationError
from .facets import XSD_10_FACETS, STRING_FACETS, BOOLEAN_FACETS, FLOAT_FACETS, DECIMAL_FACETS, DATETIME_FACETS
from .simple_types import XsdSimpleType, XsdAtomicBuiltin

HEX_BINARY_PATTERN = re.compile(r'^[0-9a-fA-F]+$')
NOT_BASE64_BINARY_PATTERN = re.compile(r'[^0-9a-zA-z+/= \t\n]')


#
# XSD numerical built-in types validator functions
def byte_validator(x):
    if not (-2**7 <= x < 2**7):
        yield XMLSchemaValidationError(int_validator, x, "value must be -128 <= x < 128.")


def short_validator(x):
    if not (-2**15 <= x < 2**15):
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
    if not (0 <= x < 2**16):
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


def hex_binary_validator(x):
    if len(x) % 2 or HEX_BINARY_PATTERN.match(x) is None:
        yield XMLSchemaValidationError(hex_binary_validator, x, "not an hexadecimal number.")


def base64_binary_validator(x):
    match = NOT_BASE64_BINARY_PATTERN.search(x)
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
PRESERVE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, attrib={'value': 'preserve'})
COLLAPSE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, attrib={'value': 'collapse'})
REPLACE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, attrib={'value': 'replace'})


XSD_COMMON_BUILTIN_TYPES = (
    # ***********************
    # *** Primitive types ***
    # ***********************

    # --- String Types ---
    {
        'name': XSD_STRING,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, PRESERVE_WHITE_SPACE_ELEMENT),
        'value': 'alpha',
    },  # character string

    # --- Numerical Types ---
    {
        'name': XSD_DECIMAL,
        'python_type': (Decimal, str, unicode_type, int, float),
        'facets': (DECIMAL_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': Decimal('1.0'),
    },  # decimal number
    {
        'name': XSD_DOUBLE,
        'python_type': float,
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': 1.0,
    },   # 64 bit floating point
    {
        'name': XSD_FLOAT,
        'python_type': float,
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': 1.0,
    },  # 32 bit floating point

    # --- Dates and Times (not year related) ---
    {
        'name': XSD_GDAY,
        'python_type': (unicode_type, str, datatypes.GregorianDay),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianDay.fromstring,
        'value': datatypes.GregorianDay.fromstring('---31'),
    },  # DD
    {
        'name': XSD_GMONTH,
        'python_type': (unicode_type, str, datatypes.GregorianMonth),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianMonth.fromstring,
        'value': datatypes.GregorianMonth.fromstring('--12'),
    },  # MM
    {
        'name': XSD_GMONTH_DAY,
        'python_type': (unicode_type, str, datatypes.GregorianMonthDay),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianMonthDay.fromstring,
        'value': datatypes.GregorianMonthDay.fromstring('--12-01'),
    },  # MM-DD
    {
        'name': XSD_TIME,
        'python_type': (unicode_type, str, datatypes.Time),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.Time.fromstring,
        'value': datatypes.Time.fromstring('09:26:54'),
    },  # hh:mm:ss
    {
        'name': XSD_DURATION,
        'python_type': (unicode_type, str, datatypes.Duration),
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.Duration.fromstring,
        'value': datatypes.Duration.fromstring('P1MT1S'),
    },  # PnYnMnDTnHnMnS

    # Other primitive types
    {
        'name': XSD_QNAME,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': 'xs:element',
    },  # prf:name (the prefix needs to be qualified with an in scope namespace)
    {
        'name': XSD_NOTATION_TYPE,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': 'alpha',
    },  # type for NOTATION attributes: QNames of xs:notation declarations as value space.
    {
        'name': XSD_ANY_URI,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'value': 'https://example.com',
    },  # absolute or relative uri (RFC 2396)
    {
        'name': XSD_BOOLEAN,
        'python_type': bool,
        'facets': (BOOLEAN_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': boolean_to_python,
        'from_python': python_to_boolean,
        'value': True,
    },  # true/false or 1/0
    {
        'name': XSD_BASE64_BINARY,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, base64_binary_validator),
        'value': b'YWxwaGE=',
    },  # base64 encoded binary value
    {
        'name': XSD_HEX_BINARY,
        'python_type': (unicode_type, str),
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT, hex_binary_validator),
        'value': b'31',
    },   # hexadecimal encoded binary value

    # *********************
    # *** Derived types ***
    # *********************

    # --- String Types ---
    {
        'name': XSD_NORMALIZED_STRING,
        'python_type': (unicode_type, str),
        'base_type': XSD_STRING,
        'facets': [REPLACE_WHITE_SPACE_ELEMENT],
    },  # line breaks are normalized
    {
        'name': XSD_TOKEN,
        'python_type': (unicode_type, str),
        'base_type': XSD_NORMALIZED_STRING,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # whitespaces are normalized
    {
        'name': XSD_LANGUAGE,
        'python_type': (unicode_type, str),
        'base_type': XSD_TOKEN,
        'facets': [
            etree_element(XSD_PATTERN, attrib={
                'value': r"([a-zA-Z]{2}|[iI]-[a-zA-Z]+|[xX]-[a-zA-Z]{1,8})(-[a-zA-Z]{1,8})*"
            })
        ]
    },  # language codes
    {
        'name': XSD_NAME,
        'python_type': (unicode_type, str),
        'base_type': XSD_TOKEN,
        'facets': [etree_element(XSD_PATTERN, attrib={'value': r"\i\c*"})]
    },  # not starting with a digit
    {
        'name': XSD_NCNAME,
        'python_type': (unicode_type, str),
        'base_type': XSD_NAME,
        'facets': [etree_element(XSD_PATTERN, attrib={'value': r"[\i-[:]][\c-[:]]*"})]
    },  # cannot contain colons
    {
        'name': XSD_ID,
        'python_type': (unicode_type, str),
        'base_type': XSD_NCNAME
    },  # unique identification in document (attribute only)
    {
        'name': XSD_IDREF,
        'python_type': (unicode_type, str),
        'base_type': XSD_NCNAME
    },  # reference to ID field in document (attribute only)
    {
        'name': XSD_ENTITY,
        'python_type': (unicode_type, str),
        'base_type': XSD_NCNAME
    },  # reference to entity (attribute only)
    {
        'name': XSD_NMTOKEN,
        'python_type': (unicode_type, str),
        'base_type': XSD_TOKEN,
        'facets': [etree_element(XSD_PATTERN, attrib={'value': r"\c+"})]
    },  # should not contain whitespace (attribute only)

    # --- Numerical derived types ---
    {
        'name': XSD_INTEGER,
        'python_type': int if PY3 else (long_type, int),
        'base_type': XSD_DECIMAL
    },  # any integer value
    {
        'name': XSD_LONG,
        'python_type': int if PY3 else (long_type, int),
        'base_type': XSD_INTEGER,
        'facets': [long_validator]
    },  # signed 128 bit value
    {
        'name': XSD_INT,
        'python_type': int,
        'base_type': XSD_LONG,
        'facets': [int_validator]
    },  # signed 64 bit value
    {
        'name': XSD_SHORT,
        'python_type': int,
        'base_type': XSD_INT,
        'facets': [short_validator]
    },  # signed 32 bit value
    {
        'name': XSD_BYTE,
        'python_type': int,
        'base_type': XSD_SHORT,
        'facets': [byte_validator]
    },  # signed 8 bit value
    {
        'name': XSD_NON_NEGATIVE_INTEGER,
        'python_type': int if PY3 else (long_type, int),
        'base_type': XSD_INTEGER,
        'facets': [non_negative_int_validator]
    },  # only zero and more value allowed [>= 0]
    {
        'name': XSD_POSITIVE_INTEGER,
        'python_type': int if PY3 else (long_type, int),
        'base_type': XSD_NON_NEGATIVE_INTEGER,
        'facets': [positive_int_validator]
    },  # only positive value allowed [> 0]
    {
        'name': XSD_UNSIGNED_LONG,
        'python_type': int if PY3 else (long_type, int),
        'base_type': XSD_NON_NEGATIVE_INTEGER,
        'facets': [unsigned_long_validator]
    },  # unsigned 128 bit value
    {
        'name': XSD_UNSIGNED_INT,
        'python_type': int,
        'base_type': XSD_UNSIGNED_LONG,
        'facets': [unsigned_int_validator]
    },  # unsigned 64 bit value
    {
        'name': XSD_UNSIGNED_SHORT,
        'python_type': int,
        'base_type': XSD_UNSIGNED_INT,
        'facets': [unsigned_short_validator]
    },  # unsigned 32 bit value
    {
        'name': XSD_UNSIGNED_BYTE,
        'python_type': int,
        'base_type': XSD_UNSIGNED_SHORT,
        'facets': [unsigned_byte_validator]
    },  # unsigned 8 bit value
    {
        'name': XSD_NON_POSITIVE_INTEGER,
        'python_type': (long_type, int),
        'base_type': XSD_INTEGER,
        'facets': [non_positive_int_validator]
    },  # only zero and smaller value allowed [<= 0]
    {
        'name': XSD_NEGATIVE_INTEGER,
        'python_type': (long_type, int),
        'base_type': XSD_NON_POSITIVE_INTEGER,
        'facets': [negative_int_validator]
    },  # only negative value allowed [< 0]
)

XSD_10_BUILTIN_TYPES = XSD_COMMON_BUILTIN_TYPES + (
    # --- Year related primitive types (year 0 not allowed) ---
    {
        'name': XSD_DATETIME,
        'python_type': (unicode_type, str, datatypes.DateTime),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.DateTime10.fromstring,
        'value': datatypes.DateTime10.fromstring('2000-01-01T12:00:00'),
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss]
    {
        'name': XSD_DATE,
        'python_type': (unicode_type, str, datatypes.Date),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.Date10.fromstring,
        'value': datatypes.Date10.fromstring('2000-01-01'),
    },  # [-][Y*]YYYY-MM-DD
    {
        'name': XSD_GYEAR,
        'python_type': (unicode_type, str, datatypes.GregorianYear),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianYear10.fromstring,
        'value': datatypes.GregorianYear10.fromstring('1999'),
    },  # [-][Y*]YYYY
    {
        'name': XSD_GYEAR_MONTH,
        'python_type': (unicode_type, str, datatypes.GregorianYearMonth),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianYearMonth10.fromstring,
        'value': datatypes.GregorianYearMonth10.fromstring('1999-09'),
    },  # [-][Y*]YYYY-MM
)

XSD_11_BUILTIN_TYPES = XSD_COMMON_BUILTIN_TYPES + (
    # --- Year related primitive types (year 0 allowed and mapped to 1 BCE) ---
    {
        'name': XSD_DATETIME,
        'python_type': (unicode_type, str, datatypes.DateTime),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.DateTime.fromstring,
        'value': datatypes.DateTime.fromstring('2000-01-01T12:00:00'),
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss]
    {
        'name': XSD_DATE,
        'python_type': (unicode_type, str, datatypes.Date),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.Date.fromstring,
        'value': datatypes.Date.fromstring('2000-01-01'),
    },  # [-][Y*]YYYY-MM-DD
    {
        'name': XSD_GYEAR,
        'python_type': (unicode_type, str, datatypes.GregorianYear),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianYear10.fromstring,
        'value': datatypes.GregorianYear10.fromstring('1999'),
    },  # [-][Y*]YYYY
    {
        'name': XSD_GYEAR_MONTH,
        'python_type': (unicode_type, str, datatypes.GregorianYearMonth),
        'facets': (DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT),
        'to_python': datatypes.GregorianYearMonth10.fromstring,
        'value': datatypes.GregorianYearMonth10.fromstring('1999-09'),
    },  # [-][Y*]YYYY-MM
    # --- Datetime derived types (XSD 1.1) ---
    {
        'name': XSD_DATE_TIME_STAMP,
        'python_type': (unicode_type, str),
        'base_type': XSD_DATETIME,
        'to_python': datatypes.DateTime.fromstring,
        'facets': [etree_element(XSD_EXPLICIT_TIMEZONE, attrib={'value': 'required'})],
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss] with required timezone
    {
        'name': XSD_DAY_TIME_DURATION,
        'python_type': (unicode_type, str),
        'base_type': XSD_DURATION,
        'to_python': datatypes.DayTimeDuration.fromstring,
        'value': datatypes.DayTimeDuration.fromstring('P1DT1S'),
    },  # PnYnMnDTnHnMnS with month an year equal to 0
    {
        'name': XSD_YEAR_MONTH_DURATION,
        'python_type': (unicode_type, str),
        'base_type': XSD_DURATION,
        'to_python': datatypes.YearMonthDuration.fromstring,
        'value': datatypes.YearMonthDuration.fromstring('P1Y1M'),
    },  # PnYnMnDTnHnMnS with day and time equals to 0
)


def xsd_build_facets(schema, parent, base_type, items):
    facets = {}
    for obj in items:
        if isinstance(obj, (list, tuple, set)):
            facets.update([(k, None) for k in obj if k in schema.FACETS])
        elif is_etree_element(obj):
            if obj.tag in schema.FACETS:
                facets[obj.tag] = schema.FACETS[obj.tag](obj, schema, parent, base_type)
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
        elem=etree_element(XSD_COMPLEX_TYPE, attrib={'name': XSD_ANY_TYPE}),
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
        elem=etree_element(XSD_SIMPLE_TYPE, attrib={'name': XSD_ANY_SIMPLE_TYPE}),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_SIMPLE_TYPE,
        facets={k: None for k in XSD_10_FACETS}
    )

    # xs:anyAtomicType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_ATOMIC_TYPE] = meta_schema.BUILDERS.restriction_class(
        elem=etree_element(XSD_SIMPLE_TYPE, attrib={'name': XSD_ANY_ATOMIC_TYPE}),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_ATOMIC_TYPE,
        base_type=xsd_types[XSD_ANY_SIMPLE_TYPE]
    )

    xsd_class = xsd_class or XsdAtomicBuiltin
    if meta_schema.XSD_VERSION == '1.1':
        builtin_types = XSD_11_BUILTIN_TYPES
    else:
        builtin_types = XSD_10_BUILTIN_TYPES

    for item in builtin_types:
        item = item.copy()
        name = item['name']
        try:
            elem, schema = xsd_types[name]
        except KeyError:
            # If builtin type element is missing create a dummy element. Necessary for the
            # meta-schema XMLSchema.xsd of XSD 1.1, that not includes builtins declarations.
            elem = etree_element(XSD_SIMPLE_TYPE, attrib={'name': name, 'id': name})
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
