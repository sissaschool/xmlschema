#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from decimal import Decimal
from typing import Any, Iterator, List, MutableMapping, MutableSequence, \
    Optional, Tuple, Union

from xmlschema.aliases import AtomicValueType, NumericValueType


def count_digits(number: NumericValueType) -> Tuple[int, int]:
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
        significand, _, _exponent = number.partition('E')
    elif 'e' in number:
        significand, _, _exponent = number.partition('e')
    elif '.' not in number:
        return len(number.lstrip('0')), 0
    else:
        integer_part, _, decimal_part = number.partition('.')
        return len(integer_part.lstrip('0')), len(decimal_part.rstrip('0'))

    significand = significand.strip('0')
    exponent = int(_exponent)

    num_digits = len(significand) - 1 if '.' in significand else len(significand)
    if exponent > 0:
        return num_digits + exponent, 0
    else:
        return 0, num_digits - exponent - 1


def strictly_equal(obj1: object, obj2: object) -> bool:
    """Checks if the objects are equal and are of the same type."""
    return obj1 == obj2 and type(obj1) is type(obj2)


def raw_xml_encode(value: Union[None, AtomicValueType, List[AtomicValueType],
                                Tuple[AtomicValueType, ...]]) -> Optional[str]:
    """Encodes a simple value to XML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (list, tuple)):
        return ' '.join(str(e) for e in value)
    else:
        return str(value) if value is not None else None


def iter_decoded_data(obj: Any, level: int = 0) \
        -> Iterator[Tuple[Union[MutableMapping[Any, Any], MutableSequence[Any]], int]]:
    """
    Iterates a nested object composed by lists and dictionaries,
    pairing with the level depth.
    """
    if isinstance(obj, MutableMapping):
        yield obj, level
        for value in obj.values():
            yield from iter_decoded_data(value, level + 1)
    elif isinstance(obj, MutableSequence):
        yield obj, level
        for item in obj:
            yield from iter_decoded_data(item, level + 1)
