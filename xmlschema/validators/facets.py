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
from ..qnames import XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_ENUMERATION, XSD_WHITE_SPACE, \
    XSD_PATTERN, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, \
    XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_ASSERTION, XSD_EXPLICIT_TIMEZONE, XSD_NOTATION_TYPE, \
    XSD_DECIMAL, XSD_INTEGER, XSD_BASE64_BINARY, XSD_HEX_BINARY
from ..helpers import ISO_TIMEZONE_PATTERN
from ..regex import get_python_regex

from .exceptions import XMLSchemaValidationError, XMLSchemaDecodeError
from .xsdbase import XsdComponent


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

    def __call__(self, value):
        for error in self.validator(value):
            yield error

    @staticmethod
    def validator(x):
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
            self.value = None
            self.parse_error(unicode_type(err))
        else:
            if base_facet is not None and base_facet.fixed and \
                    base_facet.value is not None and self.value != base_facet.value:
                self.parse_error("%r facet value is fixed to %r" % (elem.tag, base_facet.value))

    def _parse_value(self, elem):
        self.value = elem.attrib['value']

    def __repr__(self):
        return '%s(value=%r, fixed=%r)' % (self.__class__.__name__, self.value, self.fixed)


class XsdWhiteSpaceFacet(XsdSingleFacet):
    admitted_tags = XSD_WHITE_SPACE,

    def _parse_value(self, elem):
        self.value = value = elem.attrib['value']
        if self.base_value == 'collapse' and value in ('preserve', 'replace'):
            self.parse_error("facet value can be only 'collapse'")
        elif self.base_value == 'replace' and value == 'preserve':
            self.parse_error("facet value can be only 'replace' or 'collapse'")
        elif value == 'replace':
            self.validator = self.replace_white_space_validator
        elif value == 'collapse':
            self.validator = self.collapse_white_space_validator
        elif value != 'preserve':
            self.parse_error("attribute 'value' must be one of ('preserve', 'replace', 'collapse').")

    def replace_white_space_validator(self, x):
        if '\t' in x or '\n' in x:
            yield XMLSchemaValidationError(self, x)

    def collapse_white_space_validator(self, x):
        if '\t' in x or '\n' in x or '  ' in x:
            yield XMLSchemaValidationError(self, x)


class XsdLengthFacet(XsdSingleFacet):
    admitted_tags = XSD_LENGTH,

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
    admitted_tags = XSD_MIN_LENGTH,

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
    admitted_tags = XSD_MAX_LENGTH,

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
    admitted_tags = XSD_MIN_INCLUSIVE,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.min_inclusive_validator

    def min_inclusive_validator(self, x):
        if x < self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater or equal than %r." % self.value)


class XsdMinExclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MIN_EXCLUSIVE,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.min_exclusive_validator

    def min_exclusive_validator(self, x):
        if x <= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be greater than %r." % self.value)


class XsdMaxInclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MAX_INCLUSIVE,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.max_inclusive_validator

    def max_inclusive_validator(self, x):
        if x > self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser or equal than %r." % self.value)


class XsdMaxExclusiveFacet(XsdSingleFacet):
    admitted_tags = XSD_MAX_EXCLUSIVE,

    def _parse_value(self, elem):
        self.value = self.base_type.decode(elem.attrib['value'])
        self.validator = self.max_exclusive_validator

    def max_exclusive_validator(self, x):
        if x >= self.value:
            yield XMLSchemaValidationError(self, x, "value has to be lesser than %r." % self.value)


class XsdTotalDigitsFacet(XsdSingleFacet):
    admitted_tags = XSD_TOTAL_DIGITS,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 1:
            raise ValueError("'value' must be greater or equal than 1")
        self.validator = self.total_digits_validator

    def total_digits_validator(self, x):
        if len([d for d in str(x).strip('0') if d.isdigit()]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of digits is greater than %r." % self.value)


class XsdFractionDigitsFacet(XsdSingleFacet):
    admitted_tags = XSD_FRACTION_DIGITS,

    def __init__(self, elem, schema, parent, base_type):
        super(XsdFractionDigitsFacet, self).__init__(elem, schema, parent, base_type)
        if not base_type.is_subtype(XSD_DECIMAL):
            self.parse_error("fractionDigits facet can be applied only to types derived from xs:decimal")

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 0:
            raise ValueError("'value' must be greater or equal than 0")
        elif self.value > 0 and self.base_type.is_subtype(XSD_INTEGER):
            raise ValueError("fractionDigits facet value has to be 0 for types derived from xs:integer.")
        self.validator = self.fraction_digits_validator

    def fraction_digits_validator(self, x):
        if len(str(x).strip('0').partition('.')[2]) > self.value:
            yield XMLSchemaValidationError(self, x, "the number of fraction digits is greater than %r." % self.value)


class XsdExplicitTimezoneFacet(XsdSingleFacet):
    admitted_tags = XSD_EXPLICIT_TIMEZONE,

    def _parse_value(self, elem):
        self.value = value = elem.attrib['value']
        if value == 'prohibited':
            self.validator = self.prohibited_timezone_validator
        elif value == 'required':
            self.validator = self.required_timezone_validator
        elif value != 'optional':
            self.parse_error("attribute 'value' must be one of ('required', 'prohibited', 'optional').")

    def required_timezone_validator(self, x):
        if ISO_TIMEZONE_PATTERN.search(x) is None:
            yield XMLSchemaValidationError(self, x, "time zone required for value %r." % self.value)

    def prohibited_timezone_validator(self, x):
        if ISO_TIMEZONE_PATTERN.search(x) is not None:
            yield XMLSchemaValidationError(self, x, "time zone prohibited for value %r." % self.value)


class XsdEnumerationFacet(MutableSequence, XsdFacet):

    admitted_tags = {XSD_ENUMERATION}

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

    admitted_tags = {XSD_PATTERN}

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
    XSD_WHITE_SPACE: XsdWhiteSpaceFacet,
    XSD_LENGTH: XsdLengthFacet,
    XSD_MIN_LENGTH: XsdMinLengthFacet,
    XSD_MAX_LENGTH: XsdMaxLengthFacet,
    XSD_MIN_INCLUSIVE: XsdMinInclusiveFacet,
    XSD_MIN_EXCLUSIVE: XsdMinExclusiveFacet,
    XSD_MAX_INCLUSIVE: XsdMaxInclusiveFacet,
    XSD_MAX_EXCLUSIVE: XsdMaxExclusiveFacet,
    XSD_TOTAL_DIGITS: XsdTotalDigitsFacet,
    XSD_FRACTION_DIGITS: XsdFractionDigitsFacet,
    XSD_ENUMERATION: XsdEnumerationFacet,
    XSD_PATTERN: XsdPatternsFacet,
}

XSD_11_FACETS = XSD_10_FACETS.copy()
XSD_11_FACETS.update({
    XSD_ASSERTION: None,
    XSD_EXPLICIT_TIMEZONE: XsdExplicitTimezoneFacet
})

#
# Admitted facets sets for Atomic Types, List Type and Union Type
STRING_FACETS = {
    XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_PATTERN,
    XSD_ENUMERATION, XSD_WHITE_SPACE, XSD_ASSERTION
}

BOOLEAN_FACETS = {XSD_PATTERN, XSD_WHITE_SPACE, XSD_ASSERTION}

FLOAT_FACETS = {
    XSD_PATTERN, XSD_ENUMERATION, XSD_WHITE_SPACE, XSD_MAX_INCLUSIVE,
    XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_ASSERTION
}

DECIMAL_FACETS = {
    XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_PATTERN, XSD_ENUMERATION,
    XSD_WHITE_SPACE, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE,
    XSD_MIN_EXCLUSIVE, XSD_ASSERTION
}

DATETIME_FACETS = {
    XSD_PATTERN, XSD_ENUMERATION, XSD_WHITE_SPACE,
    XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE,
    XSD_MIN_EXCLUSIVE, XSD_ASSERTION, XSD_EXPLICIT_TIMEZONE
}

LIST_FACETS = {
    XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_PATTERN,
    XSD_ENUMERATION, XSD_WHITE_SPACE, XSD_ASSERTION
}

UNION_FACETS = {XSD_PATTERN, XSD_ENUMERATION, XSD_ASSERTION}

XSD_MIN_MAX_FACETS = {
    XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE
}
