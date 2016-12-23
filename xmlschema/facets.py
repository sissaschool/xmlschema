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

from .core import XSD_NAMESPACE_PATH
from .exceptions import *
from .utils import get_qname, split_qname
from .xsdbase import xsd_qname, XsdBase, get_xsd_attribute, get_xsd_int_attribute

#
#  Facets
XSD_ENUMERATION_TAG = xsd_qname('enumeration')
XSD_LENGTH_TAG = xsd_qname('length')
XSD_MIN_LENGTH_TAG = xsd_qname('minLength')
XSD_MAX_LENGTH_TAG = xsd_qname('maxLength')
XSD_PATTERN_TAG = xsd_qname('pattern')              # lexical facet
XSD_WHITE_SPACE_TAG = xsd_qname('whiteSpace')       # pre-lexical facet
XSD_MAX_INCLUSIVE_TAG = xsd_qname('maxInclusive')
XSD_MAX_EXCLUSIVE_TAG = xsd_qname('maxExclusive')
XSD_MIN_INCLUSIVE_TAG = xsd_qname('minInclusive')
XSD_MIN_EXCLUSIVE_TAG = xsd_qname('minExclusive')
XSD_TOTAL_DIGITS_TAG = xsd_qname('totalDigits')
XSD_FRACTION_DIGITS_TAG = xsd_qname('fractionDigits')
XSD_ASSERTIONS_TAG = xsd_qname('assertions')
XSD_EXPLICIT_TIMEZONE_TAG = xsd_qname('explicitTimezone')


XSD_v1_0_FACETS = {
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

XSD_v1_1_FACETS = XSD_v1_0_FACETS.copy()
XSD_v1_1_FACETS.update({XSD_ASSERTIONS_TAG, XSD_EXPLICIT_TIMEZONE_TAG})

XSD_APPLICABLE_FACETS_SETS = {
    'string': {
        XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_PATTERN_TAG,
        XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG
    },
    'boolean': {XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG, XSD_ASSERTIONS_TAG},
    'float': {
        XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG,
        XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_ASSERTIONS_TAG
    },
    'decimal': {
        XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_PATTERN_TAG, XSD_ENUMERATION_TAG,
        XSD_WHITE_SPACE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG,
        XSD_MIN_INCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_ASSERTIONS_TAG
    },
    'datetime': {
        XSD_PATTERN_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
        XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
        XSD_MAX_INCLUSIVE_TAG, XSD_ASSERTIONS_TAG, XSD_EXPLICIT_TIMEZONE_TAG
    }
}


#
# Class hierarchy for XSD facets
class XsdFacet(XsdBase):

    def __init__(self, base_type, elem=None, schema=None):
        XsdBase.__init__(self, elem=elem, schema=schema)
        self.base_type = base_type


class XsdUniqueFacet(XsdFacet):

    def __init__(self, base_type, elem=None, schema=None):
        super(XsdUniqueFacet, self).__init__(base_type, elem=elem, schema=schema)
        self.name = '%s(value=%r)' % (split_qname(elem.tag)[1], elem.attrib['value'])
        self.fixed = self._attrib.get('fixed', 'false')

        # TODO: Add checks with base_type's constraints.
        if elem.tag == XSD_WHITE_SPACE_TAG:
            self.value = get_xsd_attribute(elem, 'value', ('preserve', 'replace', 'collapse'))
            white_space = getattr(base_type, 'white_space', None)
            if getattr(base_type, 'fixed_white_space', None) and white_space != self.value:
                XMLSchemaParseError("whiteSpace can be only %r." % base_type.white_space, elem)
            elif white_space == 'collapse' and self.value in ('preserve', 'replace'):
                XMLSchemaParseError("whiteSpace can be only 'collapse', so cannot change.", elem)
            elif white_space == 'replace' and self.value == 'preserve':
                XMLSchemaParseError("whiteSpace can be only 'replace' or 'collapse'.", elem)
        elif elem.tag in (XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG):
            self.value = get_xsd_int_attribute(elem, 'value')
            if elem.tag == XSD_LENGTH_TAG:
                self.validator = self.length_validator
            elif elem.tag in XSD_MIN_LENGTH_TAG:
                self.validator = self.min_length_validator
            elif elem.tag == XSD_MAX_LENGTH_TAG:
                self.validator = self.max_length_validator
        elif elem.tag in (
                XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG
                ):
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            if elem.tag == XSD_MIN_INCLUSIVE_TAG:
                self.validator = self.min_inclusive_validator
            elif elem.tag == XSD_MIN_EXCLUSIVE_TAG:
                self.validator = self.min_exclusive_validator
            elif elem.tag == XSD_MAX_INCLUSIVE_TAG:
                self.validator = self.max_inclusive_validator
            elif elem.tag == XSD_MAX_EXCLUSIVE_TAG:
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
        self.validator(*args, **kwargs)

    def length_validator(self, x):
        if len(x) != self.value:
            raise XMLSchemaValidationError(self, x)

    def min_length_validator(self, x):
        if len(x) < self.value:
            raise XMLSchemaValidationError(self, x)

    def max_length_validator(self, x):
        if len(x) > self.value:
            raise XMLSchemaValidationError(self, x)

    def min_inclusive_validator(self, x):
        if x < self.value:
            raise XMLSchemaValidationError(self, x)

    def min_exclusive_validator(self, x):
        if x <= self.value:
            raise XMLSchemaValidationError(self, x)

    def max_inclusive_validator(self, x):
        if x > self.value:
            raise XMLSchemaValidationError(self, x)

    def max_exclusive_validator(self, x):
        if x >= self.value:
            raise XMLSchemaValidationError(self, x)

    def total_digits_validator(self, x):
        if len([d for d in str(x) if d.isdigit()]) > self.value:
            raise XMLSchemaValidationError(self, x)

    def fraction_digits_validator(self, x):
        if len(str(x).partition('.')[2]) > self.value:
            raise XMLSchemaValidationError(self, x)


class XsdEnumerationFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(values=%r)'.format(split_qname(elem.tag)[1])
        self._elements = [elem]
        self.enumeration = [base_type.decode(get_xsd_attribute(elem, 'value'))]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        self.enumeration[i] = self.base_type.decode(get_xsd_attribute(item, 'value'))

    def __delitem__(self, i):
        del self._elements[i]
        del self.enumeration[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        self.enumeration.insert(i, self.base_type.decode(get_xsd_attribute(item, 'value')))

    def __repr__(self):
        return u"<%s %r at %#x>" % (self.__class__.__name__, self.enumeration, id(self))

    def __call__(self, value):
        if value not in self.enumeration:
            raise XMLSchemaValidationError(
                self, value, reason="invalid value, it must be one of %r" % self.enumeration
            )


class XsdPatternsFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(patterns=%r)'.format(split_qname(elem.tag)[1])
        self._elements = [elem]
        self.patterns = [re.compile(re.escape(get_xsd_attribute(elem, 'value')))]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        self.patterns[i] = re.compile(re.escape(get_xsd_attribute(item, 'value')))

    def __delitem__(self, i):
        del self._elements[i]
        del self.patterns[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        self.patterns.insert(i, re.compile(re.escape(get_xsd_attribute(item, 'value'))))

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name % self.patterns, id(self))

    def __call__(self, value):
        if all(pattern.search(value) is None for pattern in self.patterns):
            msg = "value don't match any of patterns %r"
            raise XMLSchemaValidationError(self, value, reason=msg % [p.pattern for p in self.patterns])
