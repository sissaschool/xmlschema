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
Only atomic builtins are created because the 3 list builtins types ('NMTOKENS',
'ENTITIES', 'IDREFS') are created using the XSD meta-schema.
"""
import datetime
import re
from decimal import Decimal

from ..core import long_type, unicode_type, etree_element, etree_iselement
from ..exceptions import XMLSchemaValidationError, XMLSchemaValueError
from ..qnames import (
    xsd_qname, XSD_COMPLEX_TYPE_TAG, XSD_SIMPLE_TYPE_TAG, XSD_ANY_TAG,
    XSD_ANY_ATTRIBUTE_TAG, XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG, XSD_ANY_TYPE,
    XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE, XSD_SEQUENCE_TAG
)
from .facets import (
    XsdUniqueFacet, XsdPatternsFacet, XSD_FACETS, STRING_FACETS,
    BOOLEAN_FACETS, FLOAT_FACETS, DECIMAL_FACETS, DATETIME_FACETS
)
from .simple_types import XsdSimpleType, XsdAtomicBuiltin, XsdAtomicRestriction
from .wildcards import XsdAnyAttribute, XsdAnyElement
from .attributes import XsdAttributeGroup
from .complex_types import XsdComplexType
from .groups import XsdGroup

_RE_ISO_TIMEZONE = re.compile(r"(Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9])$")


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
        yield XMLSchemaValidationError(
            non_negative_int_validator, date_string, "invalid datetime for format %r." % date_format
        )


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


XSD_BUILTIN_PRIMITIVE_TYPES = [
    # --- String Types ---
    {
        'name': xsd_qname('string'),
        'python_type': unicode_type,
        'facets': (STRING_FACETS, PRESERVE_WHITE_SPACE_ELEMENT)
    },  # character string

    # --- Numerical Types ---
    {
        'name': xsd_qname('decimal'),
        'python_type': Decimal,
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
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x)
        )
    },  # CCYY-MM-DD
    {
        'name': xsd_qname('dateTime'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%Y-%m-%dT%H:%M:%S')
        )
    },  # CCYY-MM-DDThh:mm:ss
    {
        'name': xsd_qname('gDay'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%d')
        )
    },  # DD
    {
        'name': xsd_qname('gMonth'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%m')
        )
    },  # MM
    {
        'name': xsd_qname('gMonthDay'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%m-%d')
        )
    },  # MM-DD
    {
        'name': xsd_qname('gYear'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%Y')
        )
    },  # CCYY
    {
        'name': xsd_qname('gYearMonth'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%Y-%m')
        )
    },  # CCYY-MM
    {
        'name': xsd_qname('time'),
        'python_type': unicode_type,
        'facets': (
            DATETIME_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT,
            lambda x: datetime_iso8601_validator(x, '%H:%M:%S')
        )
    },  # hh:mm:ss
    {
        'name': xsd_qname('duration'),
        'python_type': unicode_type,
        'facets': (FLOAT_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # PnYnMnDTnHnMnS

    # Other primitive types
    {
        'name': xsd_qname('QName'),
        'python_type': unicode_type,
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # prf:name (the prefix needs to be qualified with an in scope namespace)
    {
        'name': xsd_qname('NOTATION'),
        'python_type': unicode_type,
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # type for NOTATION attributes: QNames of xs:notation declarations as value space.
    {
        'name': xsd_qname('anyURI'),
        'python_type': unicode_type,
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
        'python_type': unicode_type,
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    },  # base64 encoded binary value
    {
        'name': xsd_qname('hexBinary'),
        'python_type': unicode_type,
        'facets': (STRING_FACETS, COLLAPSE_WHITE_SPACE_ELEMENT)
    }   # hexadecimal encoded binary value
]


XSD_BUILTIN_OTHER_ATOMIC_TYPES = [
    # --- String Types ---
    (
        xsd_qname('normalizedString'), unicode_type, xsd_qname('string'), [REPLACE_WHITE_SPACE_ELEMENT]
    ),  # line breaks are normalized
    (
        xsd_qname('token'), unicode_type, xsd_qname('normalizedString'), [COLLAPSE_WHITE_SPACE_ELEMENT]
    ),  # whitespace is normalized
    (
        xsd_qname('language'), unicode_type, xsd_qname('token'), [
            etree_element(XSD_PATTERN_TAG, attrib={
                'value': r"([a-zA-Z]{2}|[iI]-[a-zA-Z]+|[xX]-[a-zA-Z]{1,8})(-[a-zA-Z]{1,8})*"
            })
        ]
    ),  # language codes
    (
        xsd_qname('Name'), unicode_type, xsd_qname('token'),
        [etree_element(XSD_PATTERN_TAG, attrib={'value': r"\i\c*"})]
    ),  # not starting with a digit
    (
        xsd_qname('NCName'), unicode_type, xsd_qname('Name'),
        [etree_element(XSD_PATTERN_TAG, attrib={'value': r"[\i-[:]][\c-[:]]*"})]
    ),  # cannot contain colons
    (
        xsd_qname('ID'), unicode_type, xsd_qname('NCName')
    ),  # unique identification in document (attribute only)
    (
        xsd_qname('IDREF'), unicode_type, xsd_qname('NCName')
    ),  # reference to ID field in document (attribute only)
    (
        xsd_qname('ENTITY'), unicode_type, xsd_qname('NCName')
    ),  # reference to entity (attribute only)
    (
        xsd_qname('NMTOKEN'), unicode_type, xsd_qname('token'),
        [etree_element(XSD_PATTERN_TAG, attrib={'value': r"\c+"})]
    ),  # should not contain whitespace (attribute only)

    # --- Numerical Types ---
    (
        xsd_qname('integer'), long_type, xsd_qname('decimal')
    ),  # any integer value
    (
        xsd_qname('long'), long_type, xsd_qname('integer'), [long_validator]
    ),  # signed 128 bit value
    (
        xsd_qname('int'), int, xsd_qname('long'), [int_validator]
    ),  # signed 64 bit value
    (
        xsd_qname('short'), int, xsd_qname('int'), [short_validator]
    ),  # signed 32 bit value
    (
        xsd_qname('byte'), int, xsd_qname('short'), [byte_validator]
    ),  # signed 8 bit value
    (
        xsd_qname('nonNegativeInteger'), long_type, xsd_qname('integer'), [non_negative_int_validator]
    ),  # only zero and more value allowed [>= 0]
    (
        xsd_qname('positiveInteger'), long_type, xsd_qname('nonNegativeInteger'), [positive_int_validator]
    ),  # only positive value allowed [> 0]
    (
        xsd_qname('unsignedLong'), long_type, xsd_qname('nonNegativeInteger'), [unsigned_long_validator]
    ),  # unsigned 128 bit value
    (
        xsd_qname('unsignedInt'), int, xsd_qname('unsignedLong'), [unsigned_int_validator]
    ),  # unsigned 64 bit value
    (
        xsd_qname('unsignedShort'), int, xsd_qname('unsignedInt'), [unsigned_short_validator]
    ),  # unsigned 32 bit value
    (
        xsd_qname('unsignedByte'), int, xsd_qname('unsignedShort'), [unsigned_byte_validator]
    ),  # unsigned 8 bit value
    (
        xsd_qname('nonPositiveInteger'), long_type, xsd_qname('integer'), [non_positive_int_validator]
    ),  # only zero and smaller value allowed [<= 0]
    (
        xsd_qname('negativeInteger'), long_type, xsd_qname('nonPositiveInteger'), [negative_int_validator]
    )   # only negative value allowed [< 0]
]


def xsd_build_facets(items, base_type, schema, keys):
    facets = {}
    for obj in items:
        if isinstance(obj, (list, tuple, set)):
            facets.update([(k, None) for k in obj if k in keys])
        elif etree_iselement(obj):
            if obj.tag in keys:
                if obj.tag == XSD_PATTERN_TAG:
                    facets[obj.tag] = XsdPatternsFacet(base_type, obj, schema)
                else:
                    facets[obj.tag] = XsdUniqueFacet(base_type, obj, schema)
        elif isinstance(obj, (XsdUniqueFacet, XsdPatternsFacet)):
            if obj.name in keys:
                facets[obj.name] = obj
        elif callable(obj):
            if None in facets:
                raise XMLSchemaValueError("Almost one callable required!!")
            facets[None] = obj
    return facets


def xsd_build_any_content_group(schema):
    return XsdGroup(
        schema=schema,
        elem=etree_element(XSD_SEQUENCE_TAG),
        mixed=True,
        initlist=[XsdAnyElement(
            schema=schema,
            elem=etree_element(
                XSD_ANY_TAG,
                attrib={
                    'namespace': '##any',
                    'processContents': 'lax',
                    'minOccurs': '0',
                    'maxOccurs': 'unbounded'
                })
        )]
    )


def xsd_build_any_attribute_group(schema):
    return XsdAttributeGroup(
        schema=schema,
        elem=etree_element(XSD_ANY_ATTRIBUTE_TAG),
        base_attributes={
            None: XsdAnyAttribute(
                schema=schema,
                elem=etree_element(
                    XSD_ANY_ATTRIBUTE_TAG,
                    attrib={'namespace': '##any', 'processContents': 'lax'}
                )
            )
        })


def xsd_builtin_types_factory(meta_schema, xsd_types, xsd_class=None):
    """
    Builds the dictionary for XML Schema built-in types mapping.
    """

    #
    # Special builtin types.
    #
    # xs:anyType
    # Ref: https://www.w3.org/TR/xmlschema11-1/#builtin-ctd
    xsd_types[XSD_ANY_TYPE] = XsdComplexType(
        elem=etree_element(XSD_COMPLEX_TYPE_TAG, attrib={'name': XSD_ANY_TYPE}),
        schema=meta_schema,
        content_type=xsd_build_any_content_group(meta_schema),
        attributes=xsd_build_any_attribute_group(meta_schema),
        mixed=True,
        is_global=True
    )
    # xs:anySimpleType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_SIMPLE_TYPE] = XsdSimpleType(
        elem=etree_element(XSD_SIMPLE_TYPE_TAG, attrib={'name': XSD_ANY_SIMPLE_TYPE}),
        schema=meta_schema,
        name=XSD_ANY_SIMPLE_TYPE,
        facets={k: None for k in XSD_FACETS},
        is_global=True
    )
    # xs:anyAtomicType
    # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
    xsd_types[XSD_ANY_ATOMIC_TYPE] = XsdAtomicRestriction(
        elem=etree_element(XSD_SIMPLE_TYPE_TAG, attrib={'name': XSD_ANY_ATOMIC_TYPE}),
        schema=meta_schema,
        name=XSD_ANY_ATOMIC_TYPE,
        base_type=xsd_types[XSD_ANY_SIMPLE_TYPE],
        is_global=True
    )

    xsd_class = xsd_class or XsdAtomicBuiltin
    for item in XSD_BUILTIN_PRIMITIVE_TYPES + XSD_BUILTIN_OTHER_ATOMIC_TYPES:
        if isinstance(item, (tuple, list)):
            name = item[0]
            elem, schema = xsd_types[name]
            if schema is not meta_schema:
                raise XMLSchemaValueError("loaded entry schema doesn't match meta_schema!")

            try:
                base_type = xsd_types[item[2]]
            except IndexError:
                xsd_types[name] = xsd_class(elem, schema, *item)
            else:
                try:
                    facets = xsd_build_facets(item[3], base_type, meta_schema, XSD_FACETS)
                except IndexError:
                    xsd_types[name] = xsd_class(elem, schema, name, item[1], base_type, *item[3:])
                else:
                    xsd_types[name] = xsd_class(elem, schema, name, item[1], base_type, facets, *item[4:])

        elif isinstance(item, dict):
            item = item.copy()
            elem, schema = xsd_types[item['name']]
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
                item['facets'] = xsd_build_facets(item['facets'], base_type, schema, XSD_FACETS)
            xsd_types[item['name']] = xsd_class(elem, schema, **item)
        else:
            raise XMLSchemaValueError("Require a sequence of list/tuples or dictionaries")
