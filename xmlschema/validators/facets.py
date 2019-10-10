# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
import operator
from elementpath import XPath2Parser, ElementPathError
from elementpath.datatypes import XSD_BUILTIN_TYPES

from ..compat import unicode_type, MutableSequence
from ..qnames import XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_ENUMERATION, \
    XSD_WHITE_SPACE, XSD_PATTERN, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, XSD_MIN_INCLUSIVE, \
    XSD_MIN_EXCLUSIVE, XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, XSD_ASSERTION, \
    XSD_EXPLICIT_TIMEZONE, XSD_NOTATION_TYPE, XSD_BASE64_BINARY, XSD_HEX_BINARY, XSD_QNAME
from ..helpers import count_digits
from ..regex import get_python_regex

from .exceptions import XMLSchemaValidationError, XMLSchemaDecodeError
from .xsdbase import XsdComponent


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    fixed = False

    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdFacet, self).__init__(elem, schema, parent)

    def __repr__(self):
        return '%s(value=%r, fixed=%r)' % (self.__class__.__name__, self.value, self.fixed)

    def __call__(self, value):
        try:
            for error in self.validator(value):
                yield error
        except (TypeError, ValueError) as err:
            yield XMLSchemaValidationError(self, value, unicode_type(err))

    def _parse(self):
        super(XsdFacet, self)._parse()
        if 'fixed' in self.elem.attrib and self.elem.attrib['fixed'] in ('true', '1'):
            self.fixed = True
        base_facet = self.base_facet
        self.base_value = None if base_facet is None else base_facet.value

        try:
            self._parse_value(self.elem)
        except (KeyError, ValueError, XMLSchemaDecodeError) as err:
            self.value = None
            self.parse_error(unicode_type(err))
        else:
            if base_facet is not None and base_facet.fixed and \
                    base_facet.value is not None and self.value != base_facet.value:
                self.parse_error("%r facet value is fixed to %r" % (self.elem.tag, base_facet.value))

    def _parse_value(self, elem):
        self.value = elem.attrib['value']

    @property
    def built(self):
        return True

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

    @staticmethod
    def validator(_):
        return ()


class XsdWhiteSpaceFacet(XsdFacet):
    """
    XSD *whiteSpace* facet.

    ..  <whiteSpace
          fixed = boolean : false
          id = ID
          value = (collapse | preserve | replace)
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </whiteSpace>
    """
    _ADMITTED_TAGS = XSD_WHITE_SPACE,

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


class XsdLengthFacet(XsdFacet):
    """
    XSD *length* facet.

    ..  <length
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </length>
    """
    _ADMITTED_TAGS = XSD_LENGTH,

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
        elif primitive_type.name == XSD_QNAME:
            pass  # See: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
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


class XsdMinLengthFacet(XsdFacet):
    """
    XSD *minLength* facet.

    ..  <minLength
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minLength>
    """
    _ADMITTED_TAGS = XSD_MIN_LENGTH,

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
        elif primitive_type.name != XSD_QNAME:
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


class XsdMaxLengthFacet(XsdFacet):
    """
    XSD *maxLength* facet.

    ..  <maxLength
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxLength>
    """
    _ADMITTED_TAGS = XSD_MAX_LENGTH,

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
        elif primitive_type.name != XSD_QNAME:
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


class XsdMinInclusiveFacet(XsdFacet):
    """
    XSD *minInclusive* facet.

    ..  <minInclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minInclusive>
    """
    _ADMITTED_TAGS = XSD_MIN_INCLUSIVE,

    def _parse_value(self, elem):
        try:
            self.value = self.base_type.primitive_type.decode(elem.attrib['value'])
        except AttributeError:
            self.value = self.base_type.decode(elem.attrib['value'])

        facet = self.base_type.get_facet(XSD_MIN_EXCLUSIVE)
        if facet is not None and facet.value >= self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MIN_INCLUSIVE)
        if facet is not None and facet.value > self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MAX_EXCLUSIVE)
        if facet is not None and facet.value <= self.value:
            self.parse_error("maximum value of base_type is lesser")
        facet = self.base_type.get_facet(XSD_MAX_INCLUSIVE)
        if facet is not None and facet.value < self.value:
            self.parse_error("maximum value of base_type is lesser")

    def __call__(self, value):
        try:
            if value < self.value:
                reason = "value has to be greater or equal than %r." % self.value
                yield XMLSchemaValidationError(self, value, reason)
        except (TypeError, ValueError) as err:
            yield XMLSchemaValidationError(self, value, unicode_type(err))


class XsdMinExclusiveFacet(XsdFacet):
    """
    XSD *minExclusive* facet.

    ..  <minExclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minExclusive>
    """
    _ADMITTED_TAGS = XSD_MIN_EXCLUSIVE,

    def _parse_value(self, elem):
        try:
            self.value = self.base_type.primitive_type.decode(elem.attrib['value'])
        except AttributeError:
            self.value = self.base_type.decode(elem.attrib['value'])

        facet = self.base_type.get_facet(XSD_MIN_EXCLUSIVE)
        if facet is not None and facet.value > self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MIN_INCLUSIVE)
        if facet is not None and facet.value > self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MAX_EXCLUSIVE)
        if facet is not None and facet.value <= self.value:
            self.parse_error("maximum value of base_type is lesser")
        facet = self.base_type.get_facet(XSD_MAX_INCLUSIVE)
        if facet is not None and facet.value <= self.value:
            self.parse_error("maximum value of base_type is lesser")

    def __call__(self, value):
        try:
            if value <= self.value:
                reason = "value has to be greater than %r." % self.value
                yield XMLSchemaValidationError(self, value, reason)
        except (TypeError, ValueError) as err:
            yield XMLSchemaValidationError(self, value, unicode_type(err))


class XsdMaxInclusiveFacet(XsdFacet):
    """
    XSD *maxInclusive* facet.

    ..  <maxInclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxInclusive>
    """
    _ADMITTED_TAGS = XSD_MAX_INCLUSIVE,

    def _parse_value(self, elem):
        try:
            self.value = self.base_type.primitive_type.decode(elem.attrib['value'])
        except AttributeError:
            self.value = self.base_type.decode(elem.attrib['value'])

        facet = self.base_type.get_facet(XSD_MIN_EXCLUSIVE)
        if facet is not None and facet.value >= self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MIN_INCLUSIVE)
        if facet is not None and facet.value > self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MAX_EXCLUSIVE)
        if facet is not None and facet.value <= self.value:
            self.parse_error("maximum value of base_type is lesser")
        facet = self.base_type.get_facet(XSD_MAX_INCLUSIVE)
        if facet is not None and facet.value < self.value:
            self.parse_error("maximum value of base_type is lesser")

    def __call__(self, value):
        try:
            if value > self.value:
                reason = "value has to be lesser or equal than %r." % self.value
                yield XMLSchemaValidationError(self, value, reason)
        except (TypeError, ValueError) as err:
            yield XMLSchemaValidationError(self, value, unicode_type(err))


class XsdMaxExclusiveFacet(XsdFacet):
    """
    XSD *maxExclusive* facet.

    ..  <maxExclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxExclusive>
    """
    _ADMITTED_TAGS = XSD_MAX_EXCLUSIVE,

    def _parse_value(self, elem):
        try:
            self.value = self.base_type.primitive_type.decode(elem.attrib['value'])
        except AttributeError:
            self.value = self.base_type.decode(elem.attrib['value'])

        facet = self.base_type.get_facet(XSD_MIN_EXCLUSIVE)
        if facet is not None and facet.value >= self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MIN_INCLUSIVE)
        if facet is not None and facet.value >= self.value:
            self.parse_error("minimum value of base_type is greater")
        facet = self.base_type.get_facet(XSD_MAX_EXCLUSIVE)
        if facet is not None and facet.value < self.value:
            self.parse_error("maximum value of base_type is lesser")
        facet = self.base_type.get_facet(XSD_MAX_INCLUSIVE)
        if facet is not None and facet.value < self.value:
            self.parse_error("maximum value of base_type is lesser")

    def __call__(self, value):
        try:
            if value >= self.value:
                reason = "value has to be lesser than %r" % self.value
                yield XMLSchemaValidationError(self, value, reason)
        except (TypeError, ValueError) as err:
            yield XMLSchemaValidationError(self, value, unicode_type(err))


class XsdTotalDigitsFacet(XsdFacet):
    """
    XSD *totalDigits* facet.

    ..  <totalDigits
          fixed = boolean : false
          id = ID
          value = positiveInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </totalDigits>
    """
    _ADMITTED_TAGS = XSD_TOTAL_DIGITS,

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 1:
            raise ValueError("'value' must be greater or equal than 1")
        self.validator = self.total_digits_validator

    def total_digits_validator(self, x):
        if operator.add(*count_digits(x)) > self.value:
            yield XMLSchemaValidationError(
                self, x, "the number of digits is greater than %r." % self.value
            )


class XsdFractionDigitsFacet(XsdFacet):
    """
    XSD *fractionDigits* facet.

    ..  <fractionDigits
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </fractionDigits>
    """
    _ADMITTED_TAGS = XSD_FRACTION_DIGITS,

    def __init__(self, elem, schema, parent, base_type):
        super(XsdFractionDigitsFacet, self).__init__(elem, schema, parent, base_type)
        if not base_type.is_derived(self.schema.builtin_types()['decimal']):
            self.parse_error("fractionDigits facet can be applied only to types derived from xs:decimal")

    def _parse_value(self, elem):
        self.value = int(elem.attrib['value'])
        if self.value < 0:
            raise ValueError("'value' must be greater or equal than 0")
        elif self.value > 0 and self.base_type.is_derived(self.schema.builtin_types()['integer']):
            raise ValueError("fractionDigits facet value has to be 0 for types derived from xs:integer.")
        self.validator = self.fraction_digits_validator

    def fraction_digits_validator(self, x):
        if count_digits(x)[1] > self.value:
            yield XMLSchemaValidationError(
                self, x, "the number of fraction digits is greater than %r." % self.value
            )


class XsdExplicitTimezoneFacet(XsdFacet):
    """
    XSD 1.1 *explicitTimezone* facet.

    ..  <explicitTimezone
          fixed = boolean : false
          id = ID
          value = NCName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </explicitTimezone>
    """
    _ADMITTED_TAGS = XSD_EXPLICIT_TIMEZONE,

    def _parse_value(self, elem):
        self.value = value = elem.attrib['value']
        if value == 'prohibited':
            self.validator = self.prohibited_timezone_validator
        elif value == 'required':
            self.validator = self.required_timezone_validator
        elif value != 'optional':
            self.parse_error("attribute 'value' must be one of ('required', 'prohibited', 'optional').")

    def required_timezone_validator(self, x):
        if x.tzinfo is None:
            yield XMLSchemaValidationError(self, x, "time zone required for value %r." % self.value)

    def prohibited_timezone_validator(self, x):
        if x.tzinfo is not None:
            yield XMLSchemaValidationError(self, x, "time zone prohibited for value %r." % self.value)


class XsdEnumerationFacets(MutableSequence, XsdFacet):
    """
    Sequence of XSD *enumeration* facets. Values are validates if match any of enumeration values.

    ..  <enumeration
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </enumeration>
    """
    _ADMITTED_TAGS = {XSD_ENUMERATION}

    def __init__(self, elem, schema, parent, base_type):
        XsdFacet.__init__(self, elem, schema, parent, base_type)

    def _parse(self):
        super(XsdFacet, self)._parse()
        self._elements = [self.elem]
        self.enumeration = [self._parse_value(self.elem)]

    def _parse_value(self, elem):
        try:
            value = self.base_type.decode(elem.attrib['value'])
        except KeyError:
            self.parse_error("missing 'value' attribute", elem)
        except XMLSchemaDecodeError as err:
            self.parse_error(err, elem)
        else:
            if self.base_type.name == XSD_NOTATION_TYPE:
                try:
                    notation_qname = self.schema.resolve_qname(value)
                except (KeyError, ValueError, RuntimeError) as err:
                    self.parse_error(err, elem)
                else:
                    if notation_qname not in self.maps.notations:
                        msg = "value {!r} must match a notation declaration"
                        self.parse_error(msg.format(value), elem)
            return value

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, elem):
        self._elements[i] = elem
        self.enumeration[i] = self._parse_value(elem)

    def __delitem__(self, i):
        del self._elements[i]
        del self.enumeration[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, elem):
        self._elements.insert(i, elem)
        self.enumeration.insert(i, self._parse_value(elem))

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


class XsdPatternFacets(MutableSequence, XsdFacet):
    """
    Sequence of XSD *pattern* facets. Values are validates if match any of patterns.

    ..  <pattern
          id = ID
          value = string
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </pattern>
    """
    _ADMITTED_TAGS = {XSD_PATTERN}

    def __init__(self, elem, schema, parent, base_type):
        XsdFacet.__init__(self, elem, schema, parent, base_type)

    def _parse(self):
        super(XsdFacet, self)._parse()
        self._elements = [self.elem]
        self.patterns = [self._parse_value(self.elem)]

    def _parse_value(self, elem):
        try:
            return re.compile(get_python_regex(elem.attrib['value'], self.xsd_version))
        except KeyError:
            self.parse_error("missing 'value' attribute", elem)
            return re.compile(r'^$')
        except (re.error, XMLSchemaDecodeError) as err:
            self.parse_error(err, elem)
            return re.compile(r'^$')

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, elem):
        self._elements[i] = elem
        self.patterns[i] = self._parse_value(elem)

    def __delitem__(self, i):
        del self._elements[i]
        del self.patterns[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, elem):
        self._elements.insert(i, elem)
        self.patterns.insert(i, self._parse_value(elem))

    def __repr__(self):
        s = repr(self.regexps)
        if len(s) < 70:
            return '%s(%s)' % (self.__class__.__name__, s)
        else:
            return '%s(%s...\'])' % (self.__class__.__name__, s[:70])

    def __call__(self, text):
        try:
            if all(pattern.match(text) is None for pattern in self.patterns):
                msg = "value doesn't match any pattern of %r."
                yield XMLSchemaValidationError(self, text, reason=msg % self.regexps)
        except TypeError as err:
            yield XMLSchemaValidationError(self, text, unicode_type(err))

    @property
    def regexps(self):
        return [e.get('value', '') for e in self._elements]


class XsdAssertionXPathParser(XPath2Parser):
    """Parser for XSD 1.1 assertion facets."""


XsdAssertionXPathParser.unregister('last')
XsdAssertionXPathParser.unregister('position')


@XsdAssertionXPathParser.method(XsdAssertionXPathParser.function('last', nargs=0))
def evaluate(self, context=None):
    self.missing_context("Context item size is undefined")


@XsdAssertionXPathParser.method(XsdAssertionXPathParser.function('position', nargs=0))
def evaluate(self, context=None):
    self.missing_context("Context item position is undefined")


XsdAssertionXPathParser.build_tokenizer()


class XsdAssertionFacet(XsdFacet):
    """
    XSD 1.1 *assertion* facet for simpleType definitions.

    ..  <assertion
          id = ID
          test = an XPath expression
          xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </assertion>
    """
    _ADMITTED_TAGS = {XSD_ASSERTION}

    def __repr__(self):
        return '%s(test=%r)' % (self.__class__.__name__, self.path)

    def _parse(self):
        super(XsdFacet, self)._parse()
        try:
            self.path = self.elem.attrib['test']
        except KeyError as err:
            self.parse_error(str(err), elem=self.elem)
            self.path = 'true()'

        try:
            builtin_type_name = self.base_type.primitive_type.local_name
            variables = {'value': XSD_BUILTIN_TYPES[builtin_type_name].value}
        except AttributeError:
            variables = {'value': XSD_BUILTIN_TYPES['anySimpleType'].value}

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace
        self.parser = XsdAssertionXPathParser(self.namespaces, strict=False, variables=variables,
                                              default_namespace=self.xpath_default_namespace)

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.parse_error(err, elem=self.elem)
            self.token = self.parser.parse('true()')

    def __call__(self, value):
        self.parser.variables['value'] = value
        try:
            if not self.token.evaluate():
                msg = "value is not true with test path %r."
                yield XMLSchemaValidationError(self, value, reason=msg % self.path)
        except ElementPathError as err:
            yield XMLSchemaValidationError(self, value, reason=str(err))


XSD_10_FACETS_BUILDERS = {
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
    XSD_ENUMERATION: XsdEnumerationFacets,
    XSD_PATTERN: XsdPatternFacets
}

XSD_11_FACETS_BUILDERS = XSD_10_FACETS_BUILDERS.copy()
XSD_11_FACETS_BUILDERS.update({
    XSD_ASSERTION: XsdAssertionFacet,
    XSD_EXPLICIT_TIMEZONE: XsdExplicitTimezoneFacet
})

XSD_10_FACETS = set(XSD_10_FACETS_BUILDERS)
XSD_11_FACETS = set(XSD_11_FACETS_BUILDERS)

XSD_10_LIST_FACETS = {XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_PATTERN, XSD_ENUMERATION, XSD_WHITE_SPACE}
XSD_11_LIST_FACETS = XSD_10_LIST_FACETS | {XSD_ASSERTION}

XSD_10_UNION_FACETS = {XSD_PATTERN, XSD_ENUMERATION}
XSD_11_UNION_FACETS = MULTIPLE_FACETS = {XSD_PATTERN, XSD_ENUMERATION, XSD_ASSERTION}
