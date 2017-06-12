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
This module contains declarations and classes for XML Schema constraint facets.
"""
import re
from collections import MutableSequence

from ..exceptions import XMLSchemaParseError, XMLSchemaValidationError
from ..qnames import *
from ..regex import get_python_regex
from .xsdbase import (
    XsdComponent, get_xsd_attribute, get_xsd_int_attribute, get_xsd_bool_attribute
)

XSD_FACETS = {
    XSD_LENGTH_TAG,
    XSD_MIN_LENGTH_TAG,
    XSD_MAX_LENGTH_TAG,
    XSD_ENUMERATION_TAG,
    XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG,
    XSD_MAX_INCLUSIVE_TAG,
    XSD_MAX_EXCLUSIVE_TAG,
    XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG,
    XSD_TOTAL_DIGITS_TAG,
    XSD_FRACTION_DIGITS_TAG
}

XSD11_FACETS = XSD_FACETS.copy()
XSD11_FACETS.update({XSD_ASSERTIONS_TAG, XSD_EXPLICIT_TIMEZONE_TAG})

#
# Admitted facets sets for Atomic Types, List Type and Union Type
STRING_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG
}

BOOLEAN_FACETS = {XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG}

FLOAT_FACETS = {
    XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG,
    XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTIONS_TAG
}

DECIMAL_FACETS = {
    XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_PATTERN_TAG, XSD_ENUMERATION_TAG,
    XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTIONS_TAG
}

DATETIME_FACETS = {
    XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
    XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTIONS_TAG, XSD_EXPLICIT_TIMEZONE_TAG
}

LIST_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG
}

UNION_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG
}


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    def __init__(self, base_type, elem=None, schema=None):
        super(XsdFacet, self).__init__(elem=elem, schema=schema)
        self.base_type = base_type

    def iter_decode(self, text, validate=True, namespaces=None, use_defaults=True):
        return self.base_type.iter_decode(text, validate, namespaces, use_defaults)

    def iter_encode(self, text, validate=True, **kwargs):
        return self.base_type.iter_encode(text, validate, **kwargs)

    def __call__(self, *args, **kwargs):
        return


class XsdUniqueFacet(XsdFacet):

    def __init__(self, base_type, elem=None, schema=None):
        super(XsdUniqueFacet, self).__init__(base_type, elem=elem, schema=schema)
        self.name = '%s(value=%r)' % (local_name(elem.tag), elem.attrib['value'])
        self.fixed = get_xsd_bool_attribute(elem, 'fixed', default=False)

        # TODO: Add checks with base_type's constraints.
        if elem.tag == XSD_WHITE_SPACE_TAG:
            self.value = get_xsd_attribute(elem, 'value', XSD_WHITE_SPACE_ENUM)
            self.validator = self.white_space_validator
        elif elem.tag == XSD_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            self.validator = self.length_validator
        elif elem.tag == XSD_MIN_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            self.validator = self.min_length_validator
        elif elem.tag == XSD_MAX_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            self.validator = self.max_length_validator
        elif elem.tag == XSD_MIN_INCLUSIVE_TAG:
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            self.validator = self.min_inclusive_validator
        elif elem.tag == XSD_MIN_EXCLUSIVE_TAG:
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            self.validator = self.min_exclusive_validator
        elif elem.tag == XSD_MAX_INCLUSIVE_TAG:
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            self.validator = self.max_inclusive_validator
        elif elem.tag == XSD_MAX_EXCLUSIVE_TAG:
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            self.validator = self.max_exclusive_validator
        elif elem.tag == XSD_TOTAL_DIGITS_TAG:
            self.value = get_xsd_int_attribute(elem, 'value', minimum=1)
            self.validator = self.total_digits_validator
        elif elem.tag == XSD_FRACTION_DIGITS_TAG:
            if base_type.name != get_qname(XSD_NAMESPACE_PATH, 'decimal'):
                raise XMLSchemaParseError("fractionDigits require a {%s}decimal base type!" % XSD_NAMESPACE_PATH)
            self.value = get_xsd_int_attribute(elem, 'value', minimum=0)
            self.validator = self.fraction_digits_validator

    def __call__(self, *args, **kwargs):
        for error in self.validator(*args, **kwargs):
            yield error

    def __setattr__(self, name, value):
        if name == "value":
            base_facet = self.get_base_facet(self.elem.tag)
            if base_facet is not None:
                if base_facet.fixed and value != base_facet.value:
                    raise XMLSchemaParseError(
                        "%r facet value is fixed to %r." % (self.elem.tag, base_facet.value), self.elem
                    )
                elif self.elem.tag == XSD_WHITE_SPACE_TAG:
                    if base_facet.value == 'collapse' and value in ('preserve', 'replace'):
                        XMLSchemaParseError("facet value can be only 'collapse'.", self.elem)
                    elif base_facet.value == 'replace' and value == 'preserve':
                        XMLSchemaParseError("facet value can be only 'replace' or 'collapse'.", self.elem)
                elif self.elem.tag == XSD_LENGTH_TAG:
                    if base_facet is not None and value != base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has different 'length': %r" % base_facet.value, self.elem
                        )
                elif self.elem.tag == XSD_MIN_LENGTH_TAG:
                    if value < base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has greater 'minLength': %r" % base_facet.value, self.elem
                        )
                elif self.elem.tag == XSD_MAX_LENGTH_TAG:
                    if value > base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has lesser 'maxLength': %r" % base_facet.value, self.elem
                        )
        super(XsdUniqueFacet, self).__setattr__(name, value)

    def get_base_facet(self, tag):
        """
        Retrieve the first base_type facet corresponding to the tag.

        :return: XsdUniqueFacet instance or None.
        """
        base_type = self.base_type
        while True:
            try:
                return base_type.facets[tag]
            except (AttributeError, KeyError):
                if hasattr(base_type, 'base_type'):
                    base_type = base_type.base_type
                else:
                    return None

    def white_space_validator(self, x):
        if self.value in ('collapse', 'replace'):
            if u'\t' in x or u'\n' in x:
                yield XMLSchemaValidationError(self, x)
            if self.value == 'collapse' and u'  ' in x:
                yield XMLSchemaValidationError(self, x)

    def length_validator(self, x):
        if len(x) != self.value:
            yield XMLSchemaValidationError(self, x)

    def min_length_validator(self, x):
        if len(x) < self.value:
            yield XMLSchemaValidationError(self, x)

    def max_length_validator(self, x):
        if len(x) > self.value:
            yield XMLSchemaValidationError(self, x)

    def min_inclusive_validator(self, x):
        if x < self.value:
            yield XMLSchemaValidationError(self, x)

    def min_exclusive_validator(self, x):
        if x <= self.value:
            yield XMLSchemaValidationError(self, x)

    def max_inclusive_validator(self, x):
        if x > self.value:
            yield XMLSchemaValidationError(self, x)

    def max_exclusive_validator(self, x):
        if x >= self.value:
            yield XMLSchemaValidationError(self, x)

    def total_digits_validator(self, x):
        if len([d for d in str(x).strip('0') if d.isdigit()]) > self.value:
            yield XMLSchemaValidationError(self, x)

    def fraction_digits_validator(self, x):
        if len(str(x).strip('0').partition('.')[2]) > self.value:
            yield XMLSchemaValidationError(self, x)


class XsdEnumerationFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(values=%r)'.format(local_name(elem.tag))
        self._elements = []
        self.enumeration = []
        self.append(elem)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        value = self.base_type.decode(get_xsd_attribute(item, 'value'))
        if self.base_type.name == XSD_NOTATION_TYPE and value not in self.schema.notations:
            raise XMLSchemaParseError("value must match a notation global declaration.", item)
        self._elements[i] = item
        self.enumeration[i] = value

    def __delitem__(self, i):
        del self._elements[i]
        del self.enumeration[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        value = self.base_type.decode(get_xsd_attribute(item, 'value'))
        if self.base_type.name == XSD_NOTATION_TYPE and value not in self.schema.notations:
            raise XMLSchemaParseError("value must match a notation global declaration.", item)
        self.enumeration.insert(i, value)

    def __repr__(self):
        if len(self.enumeration) > 5:
            enum_repr = '[%s, ...]' % ', '.join(self.enumeration[:5])
        else:
            enum_repr = repr(self.enumeration)
        return u"<%s %r at %#x>" % (self.__class__.__name__, enum_repr, id(self))

    def __call__(self, value):
        if value not in self.enumeration:
            yield XMLSchemaValidationError(
                self, value, reason="invalid value %r, it must be one of %r" % (value, self.enumeration)
            )


class XsdPatternsFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(patterns=%r)'.format(local_name(elem.tag))
        self._elements = [elem]
        value = get_xsd_attribute(elem, 'value')
        regex = get_python_regex(value)
        self.patterns = [re.compile(regex)]
        self.regexps = [value]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        value = get_xsd_attribute(item, 'value')
        self.patterns[i] = re.compile(get_python_regex(value))
        self.regexps.insert(i, value)

    def __delitem__(self, i):
        del self._elements[i]
        del self.regexps[i]
        del self.patterns[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        value = get_xsd_attribute(item, 'value')
        self.patterns.insert(i, re.compile(get_python_regex(value)))
        self.regexps.insert(i, value)

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name % self.regexps, id(self))

    def __call__(self, text):
        if all(pattern.search(text) is None for pattern in self.patterns):
            msg = "value don't match any pattern of %r."
            yield XMLSchemaValidationError(self, text, reason=msg % self.regexps)


def check_facets_group(facets, admitted_facets, elem=None):
    """
    Verify the applicability and the mutual incompatibility of a group of facets.

    :param facets: Dictionary of facets.
    :param admitted_facets: A set including the qualified names
    of admitted facets.
    :param elem: Restriction element including the facets group.
    """
    # Checks the applicability of the facets
    if not admitted_facets.issuperset(set(facets.keys())):
        admitted_facets = {local_name(e) for e in admitted_facets if e}
        msg = "one or more facets are not applicable, admitted set is %r:"
        raise XMLSchemaParseError(msg % admitted_facets, elem)

    # Checks length based facets
    length = getattr(facets.get(XSD_LENGTH_TAG), 'value', None)
    min_length = getattr(facets.get(XSD_MIN_LENGTH_TAG), 'value', 0)
    max_length = getattr(facets.get(XSD_MAX_LENGTH_TAG), 'value', None)
    if max_length is not None and min_length > max_length:
        raise XMLSchemaParseError("value of 'minLength' is greater than 'maxLength'.", elem)

    # TODO: complete the checks on facets
    if length is not None:
        if min_length > length:
            raise XMLSchemaParseError("value of 'minLength' is greater than 'length'.", elem)

        if max_length is not None and max_length < length:
            raise XMLSchemaParseError("value of 'maxLength' is lesser than 'length'.", elem)

        lengths = (0, max_length)
    elif min_length is not None or max_length is not None:
        pass
    else:
        lengths = (length, length)
