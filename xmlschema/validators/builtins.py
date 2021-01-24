#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains definitions and a factory function for XSD builtin datatypes.

Only atomic builtins are created, the list builtins types ('NMTOKENS', 'ENTITIES', 'IDREFS')
are created using the XSD 1.0 meta-schema or with and additional base schema for XSD 1.1.
"""
from decimal import Decimal
from elementpath import datatypes

from ..exceptions import XMLSchemaValueError
from ..names import XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_ENUMERATION, \
    XSD_PATTERN, XSD_WHITE_SPACE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_MAX_INCLUSIVE, \
    XSD_MAX_EXCLUSIVE, XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_EXPLICIT_TIMEZONE, \
    XSD_STRING, XSD_NORMALIZED_STRING, XSD_NAME, XSD_NCNAME, XSD_QNAME, XSD_TOKEN, \
    XSD_NMTOKEN, XSD_ID, XSD_IDREF, XSD_LANGUAGE, XSD_DECIMAL, XSD_DOUBLE, XSD_FLOAT, \
    XSD_INTEGER, XSD_BYTE, XSD_SHORT, XSD_INT, XSD_LONG, XSD_UNSIGNED_BYTE, \
    XSD_UNSIGNED_SHORT, XSD_UNSIGNED_INT, XSD_UNSIGNED_LONG, XSD_POSITIVE_INTEGER, \
    XSD_NEGATIVE_INTEGER, XSD_NON_NEGATIVE_INTEGER, XSD_NON_POSITIVE_INTEGER, \
    XSD_GDAY, XSD_GMONTH, XSD_GMONTH_DAY, XSD_GYEAR, XSD_GYEAR_MONTH, XSD_TIME, XSD_DATE, \
    XSD_DATETIME, XSD_DATE_TIME_STAMP, XSD_ENTITY, XSD_ANY_URI, XSD_BOOLEAN, \
    XSD_DURATION, XSD_DAY_TIME_DURATION, XSD_YEAR_MONTH_DURATION, XSD_BASE64_BINARY, \
    XSD_HEX_BINARY, XSD_NOTATION_TYPE, XSD_ERROR, XSD_ASSERTION, XSD_SIMPLE_TYPE, \
    XSD_ANY_TYPE, XSD_ANY_ATOMIC_TYPE, XSD_ANY_SIMPLE_TYPE
from ..etree import etree_element

from .helpers import decimal_validator, qname_validator, byte_validator, \
    short_validator, int_validator, long_validator, unsigned_byte_validator, \
    unsigned_short_validator, unsigned_int_validator, unsigned_long_validator, \
    negative_int_validator, positive_int_validator, non_positive_int_validator, \
    non_negative_int_validator, hex_binary_validator, base64_binary_validator, \
    error_type_validator, boolean_to_python, python_to_boolean
from .facets import XSD_10_FACETS_BUILDERS, XSD_11_FACETS_BUILDERS
from .simple_types import XsdSimpleType, XsdAtomicBuiltin

#
# Admitted facets sets for XSD atomic types
STRING_FACETS = {
    XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_PATTERN,
    XSD_ENUMERATION, XSD_WHITE_SPACE, XSD_ASSERTION
}

BOOLEAN_FACETS = {XSD_PATTERN, XSD_WHITE_SPACE, XSD_ASSERTION}

FLOAT_FACETS = {
    XSD_PATTERN, XSD_ENUMERATION, XSD_WHITE_SPACE, XSD_MAX_INCLUSIVE,
    XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_ASSERTION
}

DECIMAL_FACETS = {
    XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_PATTERN, XSD_ENUMERATION,
    XSD_WHITE_SPACE, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE,
    XSD_MIN_EXCLUSIVE, XSD_ASSERTION
}

DATETIME_FACETS = {
    XSD_PATTERN, XSD_ENUMERATION, XSD_WHITE_SPACE,
    XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE,
    XSD_MIN_EXCLUSIVE, XSD_ASSERTION, XSD_EXPLICIT_TIMEZONE
}


#
# Element facets instances for builtin types.
PRESERVE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, value='preserve')
COLLAPSE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, value='collapse')
REPLACE_WHITE_SPACE_ELEMENT = etree_element(XSD_WHITE_SPACE, value='replace')
XSD10_FLOAT_PATTERN_ELEMENT = etree_element(
    XSD_PATTERN, value=r"(\+|-)?([0-9]+(\.[0-9]*)?|\.[0-9]+)([Ee](\+|-)?[0-9]+)?|INF|-INF|NaN"
)
XSD11_FLOAT_PATTERN_ELEMENT = etree_element(
    XSD_PATTERN, value=r"(\+|-)?([0-9]+(\.[0-9]*)?|\.[0-9]+)([Ee](\+|-)?[0-9]+)?|(\+|-)?INF|NaN"
)


XSD_COMMON_BUILTIN_TYPES = (
    # ***********************
    # *** Primitive types ***
    # ***********************

    # --- String Types ---
    {
        'name': XSD_STRING,
        'python_type': str,
        'admitted_facets': STRING_FACETS,
        'facets': [PRESERVE_WHITE_SPACE_ELEMENT],
    },  # character string

    # --- Numerical Types ---
    {
        'name': XSD_DECIMAL,
        'python_type': (Decimal, str, int, float),
        'admitted_facets': DECIMAL_FACETS,
        'to_python': datatypes.DecimalProxy,
        'facets': [decimal_validator, COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # decimal number

    # --- Dates and Times (not year related) ---
    {
        'name': XSD_GDAY,
        'python_type': (datatypes.GregorianDay, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianDay.fromstring,
    },  # DD
    {
        'name': XSD_GMONTH,
        'python_type': (datatypes.GregorianMonth, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianMonth.fromstring,
    },  # MM
    {
        'name': XSD_GMONTH_DAY,
        'python_type': (datatypes.GregorianMonthDay, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianMonthDay.fromstring,
    },  # MM-DD
    {
        'name': XSD_TIME,
        'python_type': (datatypes.Time, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.Time.fromstring,
    },  # hh:mm:ss
    {
        'name': XSD_DURATION,
        'python_type': (datatypes.Duration, str),
        'admitted_facets': FLOAT_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.Duration.fromstring,
    },  # PnYnMnDTnHnMnS

    # Other primitive types
    {
        'name': XSD_QNAME,
        'python_type': str,
        'admitted_facets': STRING_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT, qname_validator],
    },  # prf:name (the prefix needs to be qualified with an in-scope namespace)
    {
        'name': XSD_NOTATION_TYPE,
        'python_type': str,
        'admitted_facets': STRING_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # type for NOTATION attributes: QNames of xs:notation declarations as value space.
    {
        'name': XSD_ANY_URI,
        'python_type': str,
        'admitted_facets': STRING_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # absolute or relative uri (RFC 2396)
    {
        'name': XSD_BOOLEAN,
        'python_type': bool,
        'admitted_facets': BOOLEAN_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': boolean_to_python,
        'from_python': python_to_boolean,
    },  # true/false or 1/0
    {
        'name': XSD_BASE64_BINARY,
        'python_type': (datatypes.Base64Binary, str, bytes),
        'admitted_facets': STRING_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT, base64_binary_validator],
    },  # base64 encoded binary value
    {
        'name': XSD_HEX_BINARY,
        'python_type': (datatypes.HexBinary, str, bytes),
        'admitted_facets': STRING_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT, hex_binary_validator],
    },   # hexadecimal encoded binary value

    # *********************
    # *** Derived types ***
    # *********************

    # --- String Types ---
    {
        'name': XSD_NORMALIZED_STRING,
        'python_type': str,
        'base_type': XSD_STRING,
        'facets': [REPLACE_WHITE_SPACE_ELEMENT],
    },  # line breaks are normalized
    {
        'name': XSD_TOKEN,
        'python_type': str,
        'base_type': XSD_NORMALIZED_STRING,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # whitespaces are normalized
    {
        'name': XSD_LANGUAGE,
        'python_type': str,
        'base_type': XSD_TOKEN,
        'facets': [etree_element(XSD_PATTERN, value=r"[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*")]
    },  # language codes
    {
        'name': XSD_NAME,
        'python_type': str,
        'base_type': XSD_TOKEN,
        'facets': [etree_element(XSD_PATTERN, value=r"\i\c*")]
    },  # not starting with a digit
    {
        'name': XSD_NCNAME,
        'python_type': str,
        'base_type': XSD_NAME,
        'facets': [etree_element(XSD_PATTERN, value=r"[\i-[:]][\c-[:]]*")]
    },  # cannot contain colons
    {
        'name': XSD_ID,
        'python_type': str,
        'base_type': XSD_NCNAME
    },  # unique identification in document (attribute only)
    {
        'name': XSD_IDREF,
        'python_type': str,
        'base_type': XSD_NCNAME
    },  # reference to ID field in document (attribute only)
    {
        'name': XSD_ENTITY,
        'python_type': str,
        'base_type': XSD_NCNAME
    },  # reference to entity (attribute only)
    {
        'name': XSD_NMTOKEN,
        'python_type': str,
        'base_type': XSD_TOKEN,
        'facets': [etree_element(XSD_PATTERN, value=r"\c+")]
    },  # should not contain whitespace (attribute only)

    # --- Numerical derived types ---
    {
        'name': XSD_INTEGER,
        'python_type': int,
        'base_type': XSD_DECIMAL
    },  # any integer value
    {
        'name': XSD_LONG,
        'python_type': int,
        'base_type': XSD_INTEGER,
        'facets': [long_validator,
                   etree_element(XSD_MIN_INCLUSIVE, value='-9223372036854775808'),
                   etree_element(XSD_MAX_INCLUSIVE, value='9223372036854775807')]
    },  # signed 128 bit value
    {
        'name': XSD_INT,
        'python_type': int,
        'base_type': XSD_LONG,
        'facets': [int_validator,
                   etree_element(XSD_MIN_INCLUSIVE, value='-2147483648'),
                   etree_element(XSD_MAX_INCLUSIVE, value='2147483647')]
    },  # signed 64 bit value
    {
        'name': XSD_SHORT,
        'python_type': int,
        'base_type': XSD_INT,
        'facets': [short_validator,
                   etree_element(XSD_MIN_INCLUSIVE, value='-32768'),
                   etree_element(XSD_MAX_INCLUSIVE, value='32767')]
    },  # signed 32 bit value
    {
        'name': XSD_BYTE,
        'python_type': int,
        'base_type': XSD_SHORT,
        'facets': [byte_validator,
                   etree_element(XSD_MIN_INCLUSIVE, value='-128'),
                   etree_element(XSD_MAX_INCLUSIVE, value='127')]
    },  # signed 8 bit value
    {
        'name': XSD_NON_NEGATIVE_INTEGER,
        'python_type': int,
        'base_type': XSD_INTEGER,
        'facets': [non_negative_int_validator, etree_element(XSD_MIN_INCLUSIVE, value='0')]
    },  # only zero and more value allowed [>= 0]
    {
        'name': XSD_POSITIVE_INTEGER,
        'python_type': int,
        'base_type': XSD_NON_NEGATIVE_INTEGER,
        'facets': [positive_int_validator, etree_element(XSD_MIN_INCLUSIVE, value='1')]
    },  # only positive value allowed [> 0]
    {
        'name': XSD_UNSIGNED_LONG,
        'python_type': int,
        'base_type': XSD_NON_NEGATIVE_INTEGER,
        'facets': [unsigned_long_validator,
                   etree_element(XSD_MAX_INCLUSIVE, value='18446744073709551615')]
    },  # unsigned 128 bit value
    {
        'name': XSD_UNSIGNED_INT,
        'python_type': int,
        'base_type': XSD_UNSIGNED_LONG,
        'facets': [unsigned_int_validator, etree_element(XSD_MAX_INCLUSIVE, value='4294967295')]
    },  # unsigned 64 bit value
    {
        'name': XSD_UNSIGNED_SHORT,
        'python_type': int,
        'base_type': XSD_UNSIGNED_INT,
        'facets': [unsigned_short_validator, etree_element(XSD_MAX_INCLUSIVE, value='65535')]
    },  # unsigned 32 bit value
    {
        'name': XSD_UNSIGNED_BYTE,
        'python_type': int,
        'base_type': XSD_UNSIGNED_SHORT,
        'facets': [unsigned_byte_validator, etree_element(XSD_MAX_INCLUSIVE, value='255')]
    },  # unsigned 8 bit value
    {
        'name': XSD_NON_POSITIVE_INTEGER,
        'python_type': int,
        'base_type': XSD_INTEGER,
        'facets': [non_positive_int_validator, etree_element(XSD_MAX_INCLUSIVE, value='0')]
    },  # only zero and smaller value allowed [<= 0]
    {
        'name': XSD_NEGATIVE_INTEGER,
        'python_type': int,
        'base_type': XSD_NON_POSITIVE_INTEGER,
        'facets': [negative_int_validator, etree_element(XSD_MAX_INCLUSIVE, value='-1')]
    },  # only negative value allowed [< 0]
)

XSD_10_BUILTIN_TYPES = XSD_COMMON_BUILTIN_TYPES + (
    {
        'name': XSD_DOUBLE,
        'python_type': float,
        'admitted_facets': FLOAT_FACETS,
        'facets': [XSD10_FLOAT_PATTERN_ELEMENT, COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # 64 bit floating point
    {
        'name': XSD_FLOAT,
        'python_type': float,
        'admitted_facets': FLOAT_FACETS,
        'facets': [XSD10_FLOAT_PATTERN_ELEMENT, COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # 32 bit floating point

    # --- Year related primitive types (year 0 not allowed) ---
    {
        'name': XSD_DATETIME,
        'python_type': (datatypes.DateTime10, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.DateTime10.fromstring,
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss]
    {
        'name': XSD_DATE,
        'python_type': (datatypes.Date10, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.Date10.fromstring,
    },  # [-][Y*]YYYY-MM-DD
    {
        'name': XSD_GYEAR,
        'python_type': (datatypes.GregorianYear10, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianYear10.fromstring,
    },  # [-][Y*]YYYY
    {
        'name': XSD_GYEAR_MONTH,
        'python_type': (datatypes.GregorianYearMonth10, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianYearMonth10.fromstring,
    },  # [-][Y*]YYYY-MM
)

XSD_11_BUILTIN_TYPES = XSD_COMMON_BUILTIN_TYPES + (
    {
        'name': XSD_DOUBLE,
        'python_type': float,
        'admitted_facets': FLOAT_FACETS,
        'facets': [XSD11_FLOAT_PATTERN_ELEMENT, COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # 64 bit floating point
    {
        'name': XSD_FLOAT,
        'python_type': float,
        'admitted_facets': FLOAT_FACETS,
        'facets': [XSD11_FLOAT_PATTERN_ELEMENT, COLLAPSE_WHITE_SPACE_ELEMENT],
    },  # 32 bit floating point

    # --- Year related primitive types (year 0 allowed and mapped to 1 BCE) ---
    {
        'name': XSD_DATETIME,
        'python_type': (datatypes.DateTime, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.DateTime.fromstring,
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss]
    {
        'name': XSD_DATE,
        'python_type': (datatypes.Date, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.Date.fromstring,
    },  # [-][Y*]YYYY-MM-DD
    {
        'name': XSD_GYEAR,
        'python_type': (datatypes.GregorianYear, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianYear.fromstring,
    },  # [-][Y*]YYYY
    {
        'name': XSD_GYEAR_MONTH,
        'python_type': (datatypes.GregorianYearMonth, str),
        'admitted_facets': DATETIME_FACETS,
        'facets': [COLLAPSE_WHITE_SPACE_ELEMENT],
        'to_python': datatypes.GregorianYearMonth.fromstring,
    },  # [-][Y*]YYYY-MM
    # --- Datetime derived types (XSD 1.1) ---
    {
        'name': XSD_DATE_TIME_STAMP,
        'python_type': (datatypes.DateTimeStamp, str),
        'base_type': XSD_DATETIME,
        'to_python': datatypes.DateTime.fromstring,
        'facets': [etree_element(XSD_EXPLICIT_TIMEZONE, value='required')],
    },  # [-][Y*]YYYY-MM-DD[Thh:mm:ss] with required timezone
    {
        'name': XSD_DAY_TIME_DURATION,
        'python_type': (datatypes.DayTimeDuration, str),
        'base_type': XSD_DURATION,
        'to_python': datatypes.DayTimeDuration.fromstring,
    },  # PnYnMnDTnHnMnS with month an year equal to 0
    {
        'name': XSD_YEAR_MONTH_DURATION,
        'python_type': (datatypes.YearMonthDuration, str),
        'base_type': XSD_DURATION,
        'to_python': datatypes.YearMonthDuration.fromstring,
    },  # PnYnMnDTnHnMnS with day and time equals to 0
    # --- xs:error primitive type (XSD 1.1) ---
    {
        'name': XSD_ERROR,
        'python_type': type(None),
        'admitted_facets': (),
        'facets': [error_type_validator],
    },  # xs:error has no value space and no lexical space
)


def xsd_builtin_types_factory(meta_schema, xsd_types, atomic_builtin_class=None):
    """
    Builds the dictionary for XML Schema built-in types mapping.
    """
    atomic_builtin_class = atomic_builtin_class or XsdAtomicBuiltin
    if meta_schema.XSD_VERSION == '1.1':
        builtin_types = XSD_11_BUILTIN_TYPES
        facets_map = XSD_11_FACETS_BUILDERS
    else:
        builtin_types = XSD_10_BUILTIN_TYPES
        facets_map = XSD_10_FACETS_BUILDERS

    #
    # Special builtin types.
    #
    # xs:anyType
    # Ref: https://www.w3.org/TR/xmlschema11-1/#builtin-ctd
    xsd_types[XSD_ANY_TYPE] = meta_schema.create_any_type()

    # xs:anySimpleType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_SIMPLE_TYPE] = XsdSimpleType(
        elem=etree_element(XSD_SIMPLE_TYPE, name=XSD_ANY_SIMPLE_TYPE),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_SIMPLE_TYPE
    )

    # xs:anyAtomicType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_ATOMIC_TYPE] = meta_schema.BUILDERS.restriction_class(
        elem=etree_element(XSD_SIMPLE_TYPE, name=XSD_ANY_ATOMIC_TYPE),
        schema=meta_schema,
        parent=None,
        name=XSD_ANY_ATOMIC_TYPE,
        base_type=xsd_types[XSD_ANY_SIMPLE_TYPE]
    )

    for item in builtin_types:
        item = item.copy()
        name = item['name']
        try:
            elem, schema = xsd_types[name]
        except KeyError:
            # If builtin type element is missing create a dummy element. Necessary for the
            # meta-schema XMLSchema.xsd of XSD 1.1, that not includes builtins declarations.
            elem = etree_element(XSD_SIMPLE_TYPE, name=name, id=name)
        else:
            if schema is not meta_schema:
                raise XMLSchemaValueError("loaded entry schema is not the meta-schema!")

        if 'base_type' in item:
            base_type = item['base_type'] = xsd_types[item['base_type']]
        else:
            base_type = None

        facets = item.pop('facets', None)
        builtin_type = atomic_builtin_class(elem, meta_schema, **item)
        if facets:
            built_facets = builtin_type.facets
            for e in facets:
                try:
                    cls = facets_map[e.tag]
                except AttributeError:
                    built_facets[None] = e
                else:
                    built_facets[e.tag] = cls(e, meta_schema, builtin_type, base_type)
            builtin_type.facets = built_facets

        xsd_types[name] = builtin_type
