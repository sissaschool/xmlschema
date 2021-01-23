#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from decimal import Decimal
from math import isinf, isnan
from typing import Optional, Union, Tuple
from xml.etree.ElementTree import Element
from elementpath import datatypes

from ..exceptions import XMLSchemaValueError
from .exceptions import XMLSchemaValidationError

XSD_FINAL_ATTRIBUTE_VALUES = {'restriction', 'extension', 'list', 'union'}


def get_xsd_derivation_attribute(elem: Element, attribute: str,
                                 values: Optional[set] = None) -> str:
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param values: a set of admitted values when the attribute value is not '#all'.
    """
    value = elem.get(attribute)
    if value is None:
        return ''

    if values is None:
        values = XSD_FINAL_ATTRIBUTE_VALUES

    items = value.split()
    if len(items) == 1 and items[0] == '#all':
        return ' '.join(values)
    elif not all(s in values for s in items):
        raise ValueError("wrong value %r for attribute %r" % (value, attribute))
    return value


def not_whitespace(s: Optional[str]) -> bool:
    return s and s.strip()


def count_digits(number: Union[str, bytes, int, float, Decimal]) -> Tuple[int, int]:
    """
    Counts the digits of a number.

    :param number: an int or a float or a Decimal or a string representing a number.
    :return: a couple with the number of digits of the integer part and \
    the number of digits of the decimal part.
    """
    if isinstance(number, str):
        number = str(Decimal(number)).lstrip('-+')
    elif isinstance(number, bytes):
        number = str(Decimal(number.decode())).lstrip('-+')
    else:
        number = str(number).lstrip('-+')

    if 'E' in number:
        significand, _, exponent = number.partition('E')
    elif 'e' in number:
        significand, _, exponent = number.partition('e')
    elif '.' not in number:
        return len(number.lstrip('0')), 0
    else:
        integer_part, _, decimal_part = number.partition('.')
        return len(integer_part.lstrip('0')), len(decimal_part.rstrip('0'))

    significand = significand.strip('0')
    exponent = int(exponent)

    num_digits = len(significand) - 1 if '.' in significand else len(significand)
    if exponent > 0:
        return num_digits + exponent, 0
    else:
        return 0, num_digits - exponent - 1


def strictly_equal(obj1: object, obj2: object) -> bool:
    """Checks if the objects are equal and are of the same type."""
    return obj1 == obj2 and type(obj1) is type(obj2)


#
# XSD built-in types validator functions

def decimal_validator(value: Union[Decimal, int, float, str]) -> None:
    try:
        if not isinstance(value, (Decimal, float)):
            datatypes.DecimalProxy.validate(value)
        elif isinf(value) or isnan(value):
            raise ValueError()
    except (ValueError, TypeError):
        raise XMLSchemaValidationError(decimal_validator, value,
                                       "value is not a valid xs:decimal") from None


def qname_validator(value: str) -> None:
    if datatypes.QName.pattern.match(value) is None:
        raise XMLSchemaValidationError(qname_validator, value,
                                       "value is not an xs:QName")


def byte_validator(value: int) -> None:
    if not (-2**7 <= value < 2 ** 7):
        raise XMLSchemaValidationError(int_validator, value,
                                       "value must be -128 <= x < 128")


def short_validator(value: int) -> None:
    if not (-2**15 <= value < 2 ** 15):
        raise XMLSchemaValidationError(short_validator, value,
                                       "value must be -2^15 <= x < 2^15")


def int_validator(value: int) -> None:
    if not (-2**31 <= value < 2 ** 31):
        raise XMLSchemaValidationError(int_validator, value,
                                       "value must be -2^31 <= x < 2^31")


def long_validator(value: int) -> None:
    if not (-2**63 <= value < 2 ** 63):
        raise XMLSchemaValidationError(long_validator, value,
                                       "value must be -2^63 <= x < 2^63")


def unsigned_byte_validator(value: int) -> None:
    if not (0 <= value < 2 ** 8):
        raise XMLSchemaValidationError(unsigned_byte_validator, value,
                                       "value must be 0 <= x < 256")


def unsigned_short_validator(value: int) -> None:
    if not (0 <= value < 2 ** 16):
        raise XMLSchemaValidationError(unsigned_short_validator, value,
                                       "value must be 0 <= x < 2^16")


def unsigned_int_validator(value: int) -> None:
    if not (0 <= value < 2 ** 32):
        raise XMLSchemaValidationError(unsigned_int_validator, value,
                                       "value must be 0 <= x < 2^32")


def unsigned_long_validator(value: int) -> None:
    if not (0 <= value < 2 ** 64):
        raise XMLSchemaValidationError(unsigned_long_validator, value,
                                       "value must be 0 <= x < 2^64")


def negative_int_validator(value: int) -> None:
    if value >= 0:
        raise XMLSchemaValidationError(negative_int_validator, value,
                                       "value must be negative")


def positive_int_validator(value: int) -> None:
    if value <= 0:
        raise XMLSchemaValidationError(positive_int_validator, value,
                                       "value must be positive")


def non_positive_int_validator(value: int) -> None:
    if value > 0:
        raise XMLSchemaValidationError(non_positive_int_validator, value,
                                       "value must be non positive")


def non_negative_int_validator(value: int) -> None:
    if value < 0:
        raise XMLSchemaValidationError(non_negative_int_validator, value,
                                       "value must be non negative")


def hex_binary_validator(value: Union[str, datatypes.HexBinary]) -> None:
    if not isinstance(value, datatypes.HexBinary) and \
            datatypes.HexBinary.pattern.match(value) is None:
        raise XMLSchemaValidationError(hex_binary_validator, value,
                                       "not an hexadecimal number")


def base64_binary_validator(value: Union[str, datatypes.Base64Binary]) -> None:
    if isinstance(value, datatypes.Base64Binary):
        return
    value = value.replace(' ', '')
    if not value:
        return

    match = datatypes.Base64Binary.pattern.match(value)
    if match is None or match.group(0) != value:
        raise XMLSchemaValidationError(base64_binary_validator, value,
                                       "not a base64 encoding")


def error_type_validator(value: object) -> None:
    raise XMLSchemaValidationError(error_type_validator, value,
                                   "no value is allowed for xs:error type")


#
# XSD builtin decoding functions

def boolean_to_python(value: str) -> bool:
    if value in {'true', '1'}:
        return True
    elif value in {'false', '0'}:
        return False
    else:
        raise XMLSchemaValueError('{!r} is not a boolean value'.format(value))


def python_to_boolean(value: object) -> str:
    return str(value).lower()


def raw_xml_encode(value: Union[str, bytes, bool, int, float, Decimal, list, tuple]) -> str:
    """Encodes a simple value to XML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (list, tuple)):
        return ' '.join(str(e) for e in value)
    else:
        return str(value)
