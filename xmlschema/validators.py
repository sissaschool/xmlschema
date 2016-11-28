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
This module contains exception classes and functions for data validation.
"""
from .core import PY3, etree_tostring, XMLSchemaException
from .utils import str_to_number



class XMLSchemaValidatorError(XMLSchemaException, ValueError):
    """Raised when the XML data string is not validated with the XSD schema."""

    def __init__(self, validator, message):
        self.validator = validator
        self.message = message or u''
        self.reason = None
        self.schema_elem = None
        self.elem = None

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join([
            self.message,
            u'\n\nReason: %s' % self.reason if self.reason is not None else '',
            u"\n\nSchema:\n\n  %s" % etree_tostring(self.schema_elem) if self.schema_elem is not None else '',
            u"\nInstance:\n\n  %s" % etree_tostring(self.elem) if self.elem is not None else ''
        ])

    if PY3:
        __str__ = __unicode__


class XMLSchemaMultipleValidatorErrors(XMLSchemaException):
    """Raised to report a list of validator errors."""
    def __init__(self, errors, result=None):
        if not errors:
            raise ValueError("passed an empty error list!")
        self.errors = errors
        self.result = result

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.result is not None:
            return u'n.%d errors creating <%s object at %s>: %s' % (
                len(self.errors),
                self.result.__class__.__name__, hex(id(self.result)),
                u'\n'.join([u'\n%s\n%s: %s' % (u'-' * 70, type(err), err) for err in self.errors])
            )
        return u'%r' % self.errors

    if PY3:
        __str__ = __unicode__


class XMLSchemaDecodeError(XMLSchemaValidatorError):
    """Raised when an XML data string is not decodable to a Python object."""

    def __init__(self, validator, text, decoder, reason=None, schema_elem=None, elem=None):
        self.message = u"cannot decode '%s' using the type %r of validator %r." % (text, decoder, validator)
        self.validator = validator
        self.text = text
        self.decoder = decoder
        self.reason = reason
        self.elem = elem
        self.schema_elem = schema_elem


class XMLSchemaEncodeError(XMLSchemaValidatorError):
    """Raised when an object is not encodable to an XML data string."""

    def __init__(self, validator, obj, encoder, reason=None, elem=None, schema_elem=None):
        self.message = u"cannot encode %r using the type %r of validator %r." % (obj, encoder, validator)
        self.validator = validator
        self.obj = obj
        self.encoder = encoder
        self.reason = reason
        self.elem = elem
        self.schema = schema_elem


class XMLSchemaValidationError(XMLSchemaValidatorError):
    """Raised when the XML data string is not validated with the XSD schema."""

    def __init__(self, validator, value, reason=None, elem=None, schema_elem=None):
        self.message = u"failed validating %r with %r." % (value, validator)
        self.validator = validator
        self.value = value
        self.reason = reason
        self.elem = elem
        self.schema_elem = schema_elem


#
# Validator builders
def create_length_validator(value):
    def length_validator(x):
        return len(x) == length

    length = int(value)
    return length_validator


def create_min_length_validator(value):
    def min_length_validator(x):
        return len(x) >= min_length

    min_length = int(value)
    return min_length_validator


def create_max_length_validator(value):
    def max_length_validator(x):
        return len(x) <= max_length

    max_length = int(value)
    return max_length_validator


def create_min_inclusive_validator(value):
    def min_inclusive_validator(x):
        return x >= min_value

    min_value = str_to_number(value)
    return min_inclusive_validator


def create_min_exclusive_validator(value):
    def min_exclusive_validator(x):
        return x > min_value

    min_value = str_to_number(value)
    return min_exclusive_validator


def create_max_inclusive_validator(value):
    def max_inclusive_validator(x):
        return x <= max_value

    max_value = str_to_number(value)
    return max_inclusive_validator


def create_max_exclusive_validator(value):
    def max_exclusive_validator(x):
        return x < max_value

    max_value = str_to_number(value)
    return max_exclusive_validator


def create_total_digits_validator(value):
    def total_digits_validator(x):
        return len([d for d in str(x) if d.isdigit()]) <= total_digits

    total_digits = int(value)
    return total_digits_validator
