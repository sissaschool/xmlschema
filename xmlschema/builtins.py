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
from decimal import Decimal
from .utils import is_datetime_iso8601
from .qnames import xsd_qname
from .validators import (
    XsdAttributeGroup, XsdGroup, XsdSimpleType, XsdAtomicType,
    XsdList, XsdComplexType, XsdAnyAttribute, XsdAnyElement
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
    ('byte', int, [lambda x: -2**7 <= x < 2**7]),  # signed 8 bit value
    ('decimal', Decimal),  # decimal number
    ('double', float),  # 64 bit floating point
    ('float', float),  # 32 bit floating point
    ('int', int, [lambda x: -2**63 <= x < 2**63]),  # signed 64 bit value
    ('integer', int),  # any integer value
    ('long', int, [lambda x: -2**127 <= x < 2**127]),  # signed 128 bit value
    ('negativeInteger', int, [lambda x: x < 0]),  # only negative value allowed [< 0]
    ('positiveInteger', int, [lambda x: x > 0]),  # only positive value allowed [> 0]
    ('nonPositiveInteger', int, [lambda x: x <= 0]),  # only zero and smaller value allowed [<= 0]
    ('nonNegativeInteger', int, [lambda x: x >= 0]),  # only zero and more value allowed [>= 0]
    ('short', int, [lambda x: -2**16 <= x < 2**16]),  # signed 32 bit value
    ('unsignedByte', int, [lambda x: 0 <= x < 2**8]),  # unsigned 8 bit value
    ('unsignedInt', int, [lambda x: 0 <= x < 2**64]),  # unsigned 64 bit value
    ('unsignedLong', int, [lambda x: 0 <= x < 2**128]),  # unsigned 128 bit value
    ('unsignedShort', int, [lambda x: 0 <= x < 2**32]),  # unsigned 32 bit value

    # ---Dates and Times---
    ('date', str, [lambda x: is_datetime_iso8601(x)]),  # CCYY-MM-DD
    ('dateTime', str, [lambda x: is_datetime_iso8601(x, '%Y-%m-%dT%H:%M:%S')]),  # CCYY-MM-DDThh:mm:ss
    ('gDay', str, [lambda x: is_datetime_iso8601(x, '%d')]),  # DD
    ('gMonth', str, [lambda x: is_datetime_iso8601(x, '%m')]),  # MM
    ('gMonthDay', str, [lambda x: is_datetime_iso8601(x, '%m-%d')]),  # MM-DD
    ('gYear', str, [lambda x: is_datetime_iso8601(x, '%Y')]),  # CCYY
    ('gYearMonth', str, [lambda x: is_datetime_iso8601(x, '%Y-%m')]),  # CCYY-MM
    ('time', str, [lambda x: is_datetime_iso8601(x, '%H:%M:%S')]),  # hh:mm:ss
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
