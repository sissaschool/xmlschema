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

from ..compat import unicode_type
from ..qnames import (
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_ENUMERATION_TAG, XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_ASSERTION_TAG,
    XSD_EXPLICIT_TIMEZONE_TAG, XSD_NOTATION_TYPE, XSD_DECIMAL_TYPE, XSD_INTEGER_TYPE,
    local_name, xsd_qname
)
from ..regex import get_python_regex
from .exceptions import XMLSchemaValidationError, XMLSchemaDecodeError
from .parseutils import RE_ISO_TIMEZONE
from .xsdbase import XsdComponent


XSD_BASE64_BINARY = xsd_qname('base64Binary')
XSD_HEX_BINARY = xsd_qname('hexBinary')

XSD_WHITE_SPACE_ENUM = {'preserve', 'replace', 'collapse'}
XSD_EXPLICIT_TIMEZONE_ENUM = {'required', 'prohibited', 'optional'}


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdFacet, self).__init__(elem, schema, parent)

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
        return ()

    @property
    def base_facet(self):
        """
        An object of the same type if the instance has a base facet, `None` otherwise.
        """
        base_type = self.base_type
        tag = self.elem.tag
        while True:
            try:
                return base_type.facets[tag]
            except (AttributeError, KeyError):
                if hasattr(base_type, 'base_type'):
                    base_type = base_type.base_type
                else:
                    return None


class XsdSingleFacet(XsdFacet):
    """
    Class for XSD facets that are singular for each restriction,
    the facets for whom the repetition is an error.
    The facets of this group are: whiteSpace, length, minLength,
    maxLength, minInclusive, minExclusive, maxInclusive, maxExclusive,
    totalDigits, fractionDigits.
    """
    def _parse(self):
        super(XsdFacet, self)._parse()
        elem = self.elem
        self.fixed = elem.get('fixed', False)
        base_facet = self.base_facet
        self.base_value = None if base_facet is None else base_facet.value

        try:
            self._parse_value(elem)
        except (KeyError, ValueError, XMLSchemaDecodeError) as err:
            self.value, self.validator = None, self.dummy_validator
            self.parse_error(unicode_type(err))
        else:
            if base_facet is not None and base_facet.fixed and \
                    base_facet.value is not None and self.value != base_facet.value:
                self.parse_error("%r facet value is fixed to %r" % (elem.tag, base_facet.value))

    def _parse_value(self, elem):
        self.value = elem.attrib['value']

    def __repr__(self):
        return '%s(%r, value=%r, fixed=%r)' % (
            self.__class__.__name__, local_name(self.elem.tag), self.value, self.fixed
        )

    def __call__(self, *args, **kwargs):
        for error in self.validator(*args, **kwargs):
            yield error

    @staticmethod
    def dummy_validator(x):
        return ()


class XsdWhiteSpaceFacet(XsdSingleFacet):
    admitted_tags = XSD_WHITE_SPACE_TAG,

    def _parse_value(self, elem):
        self.value = value = elem.attrib['value']
        self.validator = self.white_space_validator

        if value not in XSD_WHITE_SPACE_ENUM:
            self.parse_error("attribute 'value' must be one of %r" % XSD_WHITE_SPACE_ENUM)

        if self.base_value == 'collapse' and value in ('preserve', 'replace'):
            self.parse_error("facet value can be only 'collapse'")
        elif self.base_value == 'replace' and value == 'preserve':
            self.parse_error("facet value can be only 'replace' or 'collapse'")

    def white_space_validator(self, x):
        if self.value in ('collapse', 'replace'):
            if '\t' in x or '\n' in x:
                yield XMLSchemaValidationError(self, x)
            if self.value == 'collapse' and '  ' in x:
                yield XMLSchemaValidationError(self, x)


class XsdLengthFacet(XsdSingleFacet):
    admitted_tags = XSD_LENGTH_TAG,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value != self.base_value:
            self.parse_error("base type has a different 'length': %r" % self.base_value)

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None:
            self.validator = self.length_validator
        elif primitive_type.name == XSD_HEX_BINARY:
            self.validator = self.hex_length_validator
        elif primitive_type.name == XSD_BASE64_BINARY:
            self.validator = self.base64_length_validator
        else:
            self.validator = self.length_validator

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


class XsdMinLengthFacet(XsdSingleFacet):
    admitted_tags = XSD_MIN_LENGTH_TAG,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value < self.base_value:
            self.parse_error("base type has a greater 'minLength': %r" % self.base_value)

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None:
            self.validator = self.min_length_validator
        elif primitive_type.name == XSD_HEX_BINARY:
            self.validator = self.hex_min_length_validator
        elif primitive_type.name == XSD_BASE64_BINARY:
            self.validator = self.base64_min_length_validator
        else:
            self.validator = self.min_length_validator

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


class XsdMaxLengthFacet(XsdSingleFacet):
    admitted_tags = XSD_MAX_LENGTH_TAG,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value > self.base_value:
            self.parse_error("base type has a lesser 'maxLength': %r" % self.base_value)

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None:
            self.validator = self.max_length_validator
        elif primitive_type.name == XSD_HEX_BINARY:
            self.validator = self.hex_max_length_validator
        elif primitive_type.name == XSD_BASE64_BINARY:
            self.validator = self.base64_max_length_validator
        else:
            self.validator = self.max_length_validator

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


class XsdMinInclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MIN_INCLUSIVE_TAG,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.min_inclusive_validator

    def min_inclusive_validator(self, x):
        if x < self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater or equal than %r." % self.value)


class XsdMinExclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MIN_EXCLUSIVE_TAG,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.min_exclusive_validator

    def min_exclusive_validator(self, x):
        if x <= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater than %r." % self.value)


class XsdMaxInclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MAX_INCLUSIVE_TAG,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.max_inclusive_validator

    def max_inclusive_validator(self, x):
        if x > self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser or equal than %r." % self.value)


class XsdMaxExclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MAX_EXCLUSIVE_TAG,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.max_exclusive_validator

    def max_exclusive_validator(self, x):
        if x >= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser than %r." % self.value)


class XsdTotalDigitsFacet(XsdSingleFacet):
    admitted_tags = XSD_TOTAL_DIGITS_TAG,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 1:
            raise ValueError("'value' must be greater or equal than 1")
        self.validator = self.total_digits_validator

    def total_digits_validator(self, x):
        if len([d for d in str(x).strip('0') if d.isdigit()]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of digits is greater than %r." % self.value)


class XsdFractionDigitsFacet(XsdSingleFacet):
    admitted_tags = XSD_FRACTION_DIGITS_TAG,

    def __init__(self, elem, schema, parent, base_type):
        super(XsdFractionDigitsFacet, self).__init__(elem, schema, parent, base_type)
        if not base_type.is_subtype(XSD_DECIMAL_TYPE):
            self.parse_error("fractionDigits facet can be applied only to types derived from xs:decimal")

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 0:
            raise ValueError("'value' must be greater or equal than 0")
        elif self.value > 0 and self.base_type.is_subtype(XSD_INTEGER_TYPE):
            raise ValueError("fractionDigits facet value has to be 0 for types derived from xs:integer.")
        self.validator = self.fraction_digits_validator

    def fraction_digits_validator(self, x):
        if len(str(x).strip('0').partition('.')[2]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of fraction digits is greater than %r." % self.value)


class XsdExplicitTimezoneFacet(XsdSingleFacet):
    admitted_tags = XSD_EXPLICIT_TIMEZONE_TAG,

    def _parse_value(self, elem):
        self.value = value = elem.attrib['value']
        if value == 'optional':
            self.validator = self.dummy_validator
        elif value == 'prohibited':
            self.validator = self.prohibited_timezone_validator
        elif value == 'required':
            self.validator = self.required_timezone_validator
        else:
            self.parse_error("attribute 'value' must be one of %r" % XSD_EXPLICIT_TIMEZONE_ENUM)

    def required_timezone_validator(self, x):
        if RE_ISO_TIMEZONE.search(x) is None:
            yield XMLSchemaValidationError(self, x, "time zone required for value %r." % self.value)

    def prohibited_timezone_validator(self, x):
        if RE_ISO_TIMEZONE.search(x) is not None:
            yield XMLSchemaValidationError(self, x, "time zone prohibited for value %r." % self.value)


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
        value = self.base_type.decode(item.attrib['value'])
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
        value = self.base_type.decode(item.attrib['value'])
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
        value = elem.attrib['value']
        regex = get_python_regex(value)
        self.patterns = [re.compile(regex)]
        self.regexps = [value]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        value = item.attrib['value']
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
        value = item.attrib['value']
        self.patterns.insert(i, re.compile(get_python_regex(value)))
        self.regexps.insert(i, value)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.regexps)

    def __call__(self, text):
        if all(pattern.search(text) is None for pattern in self.patterns):
            msg = "value don't match any pattern of %r."
            yield XMLSchemaValidationError(self, text, reason=msg % self.regexps)


XSD_10_FACETS = {
    XSD_WHITE_SPACE_TAG: XsdWhiteSpaceFacet,
    XSD_LENGTH_TAG: XsdLengthFacet,
    XSD_MIN_LENGTH_TAG: XsdMinLengthFacet,
    XSD_MAX_LENGTH_TAG: XsdMaxLengthFacet,
    XSD_MIN_INCLUSIVE_TAG: XsdMinInclusiveFacet,
    XSD_MIN_EXCLUSIVE_TAG: XsdMinExclusiveFacet,
    XSD_MAX_INCLUSIVE_TAG: XsdMaxInclusiveFacet,
    XSD_MAX_EXCLUSIVE_TAG: XsdMaxExclusiveFacet,
    XSD_TOTAL_DIGITS_TAG: XsdTotalDigitsFacet,
    XSD_FRACTION_DIGITS_TAG: XsdFractionDigitsFacet,
    XSD_ENUMERATION_TAG: XsdEnumerationFacet,
    XSD_PATTERN_TAG: XsdPatternsFacet,
}

XSD_11_FACETS = XSD_10_FACETS.copy()
XSD_11_FACETS.update({
    XSD_ASSERTION_TAG: None,
    XSD_EXPLICIT_TIMEZONE_TAG: None
})

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

XSD_MIN_MAX_FACETS = {
    XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG
}
