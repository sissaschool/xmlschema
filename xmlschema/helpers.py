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
This module contains various helper functions and classes.
"""
from decimal import Decimal

from .exceptions import XMLSchemaValueError
from .qnames import XSD_ANNOTATION
from .xpath import ElementPathMixin

XSD_FINAL_ATTRIBUTE_VALUES = {'restriction', 'extension', 'list', 'union'}


def is_etree_element(elem):
    """More safer test for matching ElementTree elements."""
    return hasattr(elem, 'tag') and hasattr(elem, 'attrib') and \
        not isinstance(elem, ElementPathMixin)


def get_xsd_annotation(elem):
    """
    Returns the annotation of an XSD component.

    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation, `None` if \
    the XSD information item doesn't have an annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION else None
    except (TypeError, IndexError):
        return


def get_xsd_derivation_attribute(elem, attribute, values=None):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param values: sequence of admitted values when the attribute value is not '#all'.
    :return: a string.
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
        raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute))
    return value


def get_xsd_form_attribute(elem, attribute):
    """
    Get an XSD form attribute, checking the value. If the attribute is missing returns `None`

    :param elem: the Element instance.
    :param attribute: the attribute name (maybe 'form', or 'elementFormDefault' \
    or 'attributeFormDefault').
    :return: a string.
    """
    value = elem.get(attribute)
    if value is None:
        return
    elif value != 'qualified' and value != 'unqualified':
        msg = "wrong value %r for attribute %r, it must be 'qualified' or 'unqualified'."
        raise XMLSchemaValueError(msg % (value, attribute))
    return value


def raw_xml_encode(value):
    """Encodes a simple value to XML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (list, tuple)):
        return ' '.join(str(e) for e in value)
    else:
        return str(value)


def count_digits(number):
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


def strictly_equal(obj1, obj2):
    """Checks if the objects are equal and are of the same type."""
    return obj1 == obj2 and type(obj1) is type(obj2)


def iter_nested_items(items, dict_class=dict, list_class=list):
    """Iterates a nested object composed by lists and dictionaries."""
    if isinstance(items, dict_class):
        for k, v in items.items():
            yield from iter_nested_items(v, dict_class, list_class)
    elif isinstance(items, list_class):
        for item in items:
            yield from iter_nested_items(item, dict_class, list_class)
    elif isinstance(items, dict):
        raise TypeError("%r: is a dict() instead of %r." % (items, dict_class))
    elif isinstance(items, list):
        raise TypeError("%r: is a list() instead of %r." % (items, list_class))
    else:
        yield items


class ParticleCounter(object):
    """
    An helper class for counting total min/max occurrences of XSD particles.
    """
    def __init__(self):
        self.min_occurs = self.max_occurs = 0

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.min_occurs, self.max_occurs)

    def __add__(self, other):
        self.min_occurs += other.min_occurs
        if self.max_occurs is not None:
            if other.max_occurs is None:
                self.max_occurs = None
            else:
                self.max_occurs += other.max_occurs
        return self

    def __mul__(self, other):
        self.min_occurs *= other.min_occurs
        if self.max_occurs is None:
            if other.max_occurs == 0:
                self.max_occurs = 0
        elif other.max_occurs is None:
            if self.max_occurs != 0:
                self.max_occurs = None
        else:
            self.max_occurs *= other.max_occurs
        return self

    def reset(self):
        self.min_occurs = self.max_occurs = 0
