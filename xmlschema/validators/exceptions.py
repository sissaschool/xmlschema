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
This module contains exception and warning classes for the 'xmlschema.validators' subpackage.
"""
from ..compat import PY3
from ..exceptions import XMLSchemaException, XMLSchemaWarning, XMLSchemaValueError
from ..etree import etree_tostring, is_etree_element
from ..qnames import qname_to_prefixed


class XMLSchemaValidatorError(XMLSchemaException):
    """Base class for XSD validator errors."""
    def __init__(self, validator):
        self.validator = validator


class XMLSchemaNotBuiltError(XMLSchemaException, RuntimeError):
    """Raised when there is an improper usage attempt of a not built XSD validator."""
    pass


class XMLSchemaParseError(XMLSchemaException, ValueError):
    """
    Raised when an error is found during the building of an XSD validator.

    :param message: the error message.
    :type message: str or unicode
    :param validator: the XSD validator.
    :type validator: XsdValidator
    :param elem: the XML element that contains the error.
    :type elem: Element
    """
    def __init__(self, message, validator=None, elem=None):
        self.message = message or u''
        self.validator = validator

        elem = elem or getattr(validator, 'elem', None)
        if elem is not None and not is_etree_element(elem):
            raise XMLSchemaValueError("'elem' attribute requires an Element, not %r." % type(elem))
        self.elem = elem

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.elem is None:
            return self.message
        else:
            return u"{}\n\n  {}\n".format(self.message, etree_tostring(self.elem, max_lines=20))

    if PY3:
        __str__ = __unicode__


class XMLSchemaValidationError(XMLSchemaException, ValueError):
    """Raised when the XML data is not validated with the XSD component or schema."""

    def __init__(self, validator, obj, reason=None, schema_elem=None, elem=None):
        self.validator = validator
        self.obj = obj
        self.reason = reason
        self.schema_elem = schema_elem or getattr(validator, 'elem', None)
        self.elem = elem or obj if is_etree_element(obj) else None
        self.message = None

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        msg = [self.message or u"failed validating %r with %r.\n" % (self.obj, self.validator)]
        if self.reason is not None:
            msg.append(u'\nReason: %s\n' % self.reason)
        if self.schema_elem is not None:
            msg.append(u"\nSchema:\n\n  %s\n" % etree_tostring(self.schema_elem, max_lines=20))

        elem = self.elem
        if elem is not None:
            if hasattr(elem, 'sourceline'):
                msg.append(u"\nInstance (line %r):\n\n  %s\n" % (
                    elem.sourceline, etree_tostring(elem, max_lines=20)
                ))
            else:
                msg.append(u"\nInstance:\n\n  %s\n" % etree_tostring(elem, max_lines=20))
        return u''.join(msg)

    if PY3:
        __str__ = __unicode__


class XMLSchemaDecodeError(XMLSchemaValidationError):
    """Raised when an XML data string is not decodable to a Python object."""

    def __init__(self, validator, obj, decoder, reason=None):
        super(XMLSchemaDecodeError, self).__init__(validator, obj, reason)
        self.decoder = decoder
        self.message = u"failed decoding %r with %r.\n" % (obj, validator)


class XMLSchemaEncodeError(XMLSchemaValidationError):
    """Raised when an object is not encodable to an XML data string."""

    def __init__(self, validator, obj, encoder, reason=None):
        super(XMLSchemaEncodeError, self).__init__(validator, obj, reason)
        self.encoder = encoder
        self.message = u"failed encoding %r with %r.\n" % (obj, validator)


class XMLSchemaChildrenValidationError(XMLSchemaValidationError):

    def __init__(self, validator, elem, index, expected=None):
        elem_ref = qname_to_prefixed(elem.tag, validator.namespaces)
        self.index = index
        self.expected = expected

        if index >= len(elem):
            reason = "The content of element %r is not complete." % elem_ref
        else:
            child_ref = qname_to_prefixed(elem[index].tag, validator.namespaces)
            reason = "The child n.%d of element %r has a unexpected tag %r." % (index+1, elem_ref, child_ref)

        if isinstance(expected, (list, tuple)):
            if len(expected) > 1:
                reason += " One of %r is expected." % expected
            else:
                reason += " Tag %r expected." % expected[0]
        elif expected is not None:
            reason += " Tag %r expected." % expected

        super(XMLSchemaChildrenValidationError, self).__init__(validator, elem, reason)


class XMLSchemaIncludeWarning(XMLSchemaWarning):
    """A schema include fails."""
    pass


class XMLSchemaImportWarning(XMLSchemaWarning):
    """A schema namespace import fails."""
    pass
