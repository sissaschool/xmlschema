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
This module contains declarations and classes for XML Schema constraint facets.
"""
from __future__ import unicode_literals
import re
from collections import MutableSequence

from ..qnames import (
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_ASSERTION_TAG,
    XSD_EXPLICIT_TIMEZONE_TAG, XSD_WHITE_SPACE_ENUM, XSD_NOTATION_TYPE, XSD_DECIMAL_TYPE,
    XSD_INTEGER_TYPE, local_name, xsd_qname
)
from ..regex import get_python_regex
from .exceptions import XMLSchemaValidationError
from .parseutils import get_xsd_attribute, get_xsd_int_attribute, get_xsd_bool_attribute
from .xsdbase import XsdComponent


XSD_BASE64_BINARY = xsd_qname('base64Binary')
XSD_HEX_BINARY = xsd_qname('hexBinary')

XSD_10_FACETS = {
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

XSD_11_FACETS = XSD_10_FACETS.copy()
XSD_11_FACETS.update({XSD_ASSERTION_TAG, XSD_EXPLICIT_TIMEZONE_TAG})

#
# Admitted facets sets for Atomic Types, List Type and Union Type
STRING_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTION_TAG
}

BOOLEAN_FACETS = {XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTION_TAG}

FLOAT_FACETS = {
    XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG,
    XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTION_TAG
}

DECIMAL_FACETS = {
    XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_PATTERN_TAG, XSD_ENUMERATION_TAG,
    XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTION_TAG
}

DATETIME_FACETS = {
    XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
    XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_ASSERTION_TAG, XSD_EXPLICIT_TIMEZONE_TAG
}

LIST_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTION_TAG
}

UNION_FACETS = {XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_ASSERTION_TAG}


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    def __init__(self, elem, schema, parent, base_type):
        super(XsdFacet, self).__init__(elem, schema, parent)
        self.base_type = base_type

    @property
    def built(self):
        return self.base_type.is_global or self.base_type.built

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        else:
            return self.base_type.validation_attempted

    def __call__(self, *args, **kwargs):
        return


class XsdSingleFacet(XsdFacet):
    """
    Class for XSD facets that are singular for each restriction,
    the facets for whom the repetition is an error.
    The facets of this group are: whiteSpace, length, minLength,
    maxLength, minInclusive, minExclusive, maxInclusive, maxExclusive,
    totalDigits, fractionDigits.
    """
    admitted_tags = {
        XSD_WHITE_SPACE_TAG, XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG,
        XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG,
        XSD_MAX_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG
    }

    def __init__(self, elem, schema, parent, base_type):
        super(XsdSingleFacet, self).__init__(elem, schema, parent, base_type)
        self.fixed = get_xsd_bool_attribute(elem, 'fixed', default=False)

        # TODO: Add checks with base_type's constraints.
        if elem.tag == XSD_WHITE_SPACE_TAG:
            self.value = get_xsd_attribute(elem, 'value', XSD_WHITE_SPACE_ENUM)
            self.validator = self.white_space_validator

        elif elem.tag == XSD_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            primitive_type = getattr(self.base_type, 'primitive_type', None)
            if primitive_type is None:
                self.validator = self.length_validator
            elif primitive_type.name == XSD_HEX_BINARY:
                self.validator = self.hex_length_validator
            elif primitive_type.name == XSD_BASE64_BINARY:
                self.validator = self.base64_length_validator
            else:
                self.validator = self.length_validator

        elif elem.tag == XSD_MIN_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            primitive_type = getattr(self.base_type, 'primitive_type', None)
            if primitive_type is None:
                self.validator = self.min_length_validator
            elif primitive_type.name == XSD_HEX_BINARY:
                self.validator = self.hex_min_length_validator
            elif primitive_type.name == XSD_BASE64_BINARY:
                self.validator = self.base64_min_length_validator
            else:
                self.validator = self.min_length_validator

        elif elem.tag == XSD_MAX_LENGTH_TAG:
            self.value = get_xsd_int_attribute(elem, 'value')
            primitive_type = getattr(self.base_type, 'primitive_type', None)
            if primitive_type is None:
                self.validator = self.max_length_validator
            elif primitive_type.name == XSD_HEX_BINARY:
                self.validator = self.hex_max_length_validator
            elif primitive_type.name == XSD_BASE64_BINARY:
                self.validator = self.base64_max_length_validator
            else:
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
            if not base_type.is_subtype(XSD_DECIMAL_TYPE):
                self.parse_error("fractionDigits facet can be applied only to types derived from xs:decimal")
            self.value = get_xsd_int_attribute(elem, 'value', minimum=0)
            self.validator = self.fraction_digits_validator
            if self.value != 0 and base_type.is_subtype(XSD_INTEGER_TYPE):
                self.parse_error("fractionDigits facet value has to be 0 for types derived from xs:integer.")

    def __repr__(self):
        return '%s(%r, value=%r, fixed=%r)' % (
            self.__class__.__name__, local_name(self.elem.tag), self.value, self.fixed
        )

    def __call__(self, *args, **kwargs):
        for error in self.validator(*args, **kwargs):
            yield error

    def __setattr__(self, name, value):
        if name == "value":
            base_facet = self.get_base_facet(self.elem.tag)
            if base_facet is not None:
                if base_facet.fixed and value != base_facet.value:
                    self.parse_error("%r facet value is fixed to %r" % (self.elem.tag, base_facet.value))
                elif self.elem.tag == XSD_WHITE_SPACE_TAG:
                    if base_facet.value == 'collapse' and value in ('preserve', 'replace'):
                        self.parse_error("facet value can be only 'collapse'")
                    elif base_facet.value == 'replace' and value == 'preserve':
                        self.parse_error("facet value can be only 'replace' or 'collapse'")
                elif self.elem.tag == XSD_LENGTH_TAG:
                    if base_facet is not None and value != base_facet.value:
                        self.parse_error("base type has a different 'length': %r" % base_facet.value)
                elif self.elem.tag == XSD_MIN_LENGTH_TAG:
                    if value < base_facet.value:
                        self.parse_error("base type has a greater 'minLength': %r" % base_facet.value)
                elif self.elem.tag == XSD_MAX_LENGTH_TAG:
                    if value > base_facet.value:
                        self.parse_error("base type has a lesser 'maxLength': %r" % base_facet.value)
        super(XsdSingleFacet, self).__setattr__(name, value)

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
            if '\t' in x or '\n' in x:
                yield XMLSchemaValidationError(self, x)
            if self.value == 'collapse' and '  ' in x:
                yield XMLSchemaValidationError(self, x)

    def length_validator(self, x):
        if len(x) != self.value:
            yield XMLSchemaValidationError(self, x, "length has to be %r." % self.value)

    def hex_length_validator(self, x):
        if len(x) != self.value * 2:
            yield XMLSchemaValidationError(self, x, "binary length has to be %r." % self.value)

    def base64_length_validator(self, x):
        x = x.replace(' ', '')
        if (len(x) // 4 * 3 - (x[-1] == '=') - (x[-2] == '=')) != self.value:
            yield XMLSchemaValidationError(self, x, "binary length has to be %r." % self.value)

    def min_length_validator(self, x):
        if len(x) < self.value:
            yield XMLSchemaValidationError(self, x, "length cannot be lesser than %r." % self.value)

    def hex_min_length_validator(self, x):
        if len(x) < self.value * 2:
            yield XMLSchemaValidationError(self, x, "binary length cannot be lesser than %r." % self.value)

    def base64_min_length_validator(self, x):
        x = x.replace(' ', '')
        if (len(x) // 4 * 3 - (x[-1] in ('=', 61)) - (x[-2] in ('=', 61))) < self.value:
            yield XMLSchemaValidationError(self, x, "binary length cannot be lesser than %r." % self.value)

    def max_length_validator(self, x):
        if len(x) > self.value:
            yield XMLSchemaValidationError(self, x, "length cannot be greater than %r." % self.value)

    def hex_max_length_validator(self, x):
        if len(x) > self.value * 2:
            yield XMLSchemaValidationError(self, x, "binary length cannot be greater than %r." % self.value)

    def base64_max_length_validator(self, x):
        x = x.replace(' ', '')
        if (len(x) // 4 * 3 - (x[-1] == '=') - (x[-2] == '=')) > self.value:
            yield XMLSchemaValidationError(self, x, "binary length cannot be greater than %r." % self.value)

    def min_inclusive_validator(self, x):
        if x < self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater or equal than %r." % self.value)

    def min_exclusive_validator(self, x):
        if x <= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater than %r." % self.value)

    def max_inclusive_validator(self, x):
        if x > self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser or equal than %r." % self.value)

    def max_exclusive_validator(self, x):
        if x >= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser than %r." % self.value)

    def total_digits_validator(self, x):
        if len([d for d in str(x).strip('0') if d.isdigit()]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of digits is greater than %r." % self.value)

    def fraction_digits_validator(self, x):
        if len(str(x).strip('0').partition('.')[2]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of fraction digits is greater than %r." % self.value)


class XsdEnumerationFacet(MutableSequence, XsdFacet):

    admitted_tags = {XSD_ENUMERATION_TAG}

    def __init__(self, elem, schema, parent, base_type):
        XsdFacet.__init__(self, elem, schema, parent, base_type)
        self._elements = []
        self.enumeration = []
        self.append(elem)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        value = self.base_type.decode(get_xsd_attribute(item, 'value'))
        if self.base_type.name == XSD_NOTATION_TYPE and value not in self.schema.notations:
            self.parse_error("value must match a notation global declaration", item)
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
            self.parse_error("value must match a notation global declaration", item)
        self.enumeration.insert(i, value)

    def __repr__(self):
        if len(self.enumeration) > 5:
            return '%s(%r)' % (
                self.__class__.__name__, '[%s, ...]' % ', '.join(map(repr, self.enumeration[:5]))
            )
        else:
            return '%s(%r)' % (self.__class__.__name__, self.enumeration)

    def __call__(self, value):
        if value not in self.enumeration:
            yield XMLSchemaValidationError(
                self, value, reason="invalid value %r, it must be one of %r" % (value, self.enumeration)
            )


class XsdPatternsFacet(MutableSequence, XsdFacet):

    admitted_tags = {XSD_PATTERN_TAG}

    def __init__(self, elem, schema, parent, base_type):
        XsdFacet.__init__(self, elem, schema, parent, base_type)
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
        return '%s(%r)' % (self.__class__.__name__, self.regexps)

    def __call__(self, text):
        if all(pattern.search(text) is None for pattern in self.patterns):
            msg = "value don't match any pattern of %r."
            yield XMLSchemaValidationError(self, text, reason=msg % self.regexps)
