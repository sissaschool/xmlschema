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
import re
from collections import MutableSequence

from ..qnames import (
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_ASSERTION_TAG,
    XSD_EXPLICIT_TIMEZONE_TAG, XSD_WHITE_SPACE_ENUM, XSD_NOTATION_TYPE, XSD_DECIMAL_TYPE,
    XSD_INTEGER_TYPE, local_name,
)
from ..regex import get_python_regex
from .exceptions import XMLSchemaParseError, XMLSchemaValidationError
from .parseutils import get_xsd_attribute, get_xsd_int_attribute, get_xsd_bool_attribute
from .xsdbase import XsdComponent


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
XSD11_FACETS.update({XSD_ASSERTION_TAG, XSD_EXPLICIT_TIMEZONE_TAG})

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

UNION_FACETS = {
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
    XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTION_TAG
}


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    def __init__(self, base_type, elem, schema):
        super(XsdFacet, self).__init__(elem=elem, schema=schema)
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

    @property
    def admitted_tags(self):
        return XSD_FACETS

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

    def __init__(self, base_type, elem, schema):
        super(XsdSingleFacet, self).__init__(base_type, elem=elem, schema=schema)
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
            if not base_type.is_subtype(XSD_DECIMAL_TYPE):
                raise XMLSchemaParseError(
                    "fractionDigits facet can be applied only to types derived from xs:decimal", self
                )
            self.value = get_xsd_int_attribute(elem, 'value', minimum=0)
            self.validator = self.fraction_digits_validator
            if self.value != 0 and base_type.is_subtype(XSD_INTEGER_TYPE):
                raise XMLSchemaParseError(
                    "fractionDigits facet value has to be 0 for types derived from xs:integer.", self
                )

    def __repr__(self):
        return u'%s(%r, value=%r, fixed=%r)' % (
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
                    raise XMLSchemaParseError(
                        "%r facet value is fixed to %r." % (self.elem.tag, base_facet.value), self
                    )
                elif self.elem.tag == XSD_WHITE_SPACE_TAG:
                    if base_facet.value == 'collapse' and value in ('preserve', 'replace'):
                        raise XMLSchemaParseError("facet value can be only 'collapse'.", self)
                    elif base_facet.value == 'replace' and value == 'preserve':
                        raise XMLSchemaParseError(
                            "facet value can be only 'replace' or 'collapse'.", self
                        )
                elif self.elem.tag == XSD_LENGTH_TAG:
                    if base_facet is not None and value != base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has different 'length': %r" % base_facet.value, self
                        )
                elif self.elem.tag == XSD_MIN_LENGTH_TAG:
                    if value < base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has greater 'minLength': %r" % base_facet.value, self
                        )
                elif self.elem.tag == XSD_MAX_LENGTH_TAG:
                    if value > base_facet.value:
                        raise XMLSchemaParseError(
                            "base type has lesser 'maxLength': %r" % base_facet.value, self
                        )
        super(XsdSingleFacet, self).__setattr__(name, value)

    @property
    def admitted_tags(self):
        return {XSD_WHITE_SPACE_TAG, XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG,
                XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG,
                XSD_MAX_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG}

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

    def __init__(self, base_type, elem, schema):
        XsdFacet.__init__(self, base_type, elem, schema=schema)
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
            return u'%s(%r)' % (
                self.__class__.__name__, '[%s, ...]' % ', '.join(map(repr, self.enumeration[:5]))
            )
        else:
            return u'%s(%r)' % (self.__class__.__name__, self.enumeration)

    def __call__(self, value):
        if value not in self.enumeration:
            yield XMLSchemaValidationError(
                self, value, reason="invalid value %r, it must be one of %r" % (value, self.enumeration)
            )

    @property
    def admitted_tags(self):
        return {XSD_ENUMERATION_TAG}


class XsdPatternsFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema):
        XsdFacet.__init__(self, base_type, elem, schema=schema)
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
        return u'%s(%r)' % (self.__class__.__name__, self.regexps)

    def __call__(self, text):
        if all(pattern.search(text) is None for pattern in self.patterns):
            msg = "value don't match any pattern of %r."
            yield XMLSchemaValidationError(self, text, reason=msg % self.regexps)

    @property
    def admitted_tags(self):
        return {XSD_PATTERN_TAG}
