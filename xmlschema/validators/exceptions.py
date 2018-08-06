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
from ..resources import XMLResource


class XMLSchemaValidatorError(XMLSchemaException):
    """
    Base class for XSD validator errors.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param message: the error message.
    :type message: str or unicode
    :param elem: the element that contains the error.
    :type elem: Element
    :param source: the XML resource that contains the error.
    :type elem: XMLResource
    """
    def __init__(self, validator, message=None, elem=None, source=None):
        self.validator = validator
        self.message = message if message is not None else u''
        self.elem = elem
        self.schema_elem = getattr(validator, 'elem', None)
        self.source = source

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

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and not is_etree_element(value):
            raise XMLSchemaValueError("'elem' attribute requires an Element, not %r." % type(value))
        super(XMLSchemaValidatorError, self).__setattr__(name, value)

    @property
    def sourceline(self):
        return getattr(self.elem, 'sourceline', None)

    @property
    def root(self):
        try:
            return self.source.root
        except AttributeError:
            return None


class XMLSchemaNotBuiltError(XMLSchemaValidatorError, RuntimeError):
    """Raised when there is an improper usage attempt of a not built XSD validator."""
    pass


class XMLSchemaParseError(XMLSchemaValidatorError, ValueError):
    """Raised when an error is found during the building of an XSD validator."""
    def __init__(self, validator, message, elem=None):
        super(XMLSchemaParseError, self).__init__(
            validator=validator,
            message=message,
            elem=elem if elem is not None else self.schema_elem,
            source=getattr(validator, 'source', None)
        )


class XMLSchemaValidationError(XMLSchemaValidatorError, ValueError):
    """Raised when the XML data is not validated with the XSD component or schema."""

    def __init__(self, validator, obj, reason=None):
        self.obj = obj
        self.reason = reason
        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message=u"failed validating %r with %r.\n",
            elem=obj if is_etree_element(obj) else None
        )

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        schema_elem, elem, sourceline = self.schema_elem, self.elem, self.sourceline
        msg = [self.message % (self.obj, self.validator)]
        if self.reason is not None:
            msg.append(u'\nReason: %s\n' % self.reason)
        if schema_elem is not elem:
            msg.append(u"\nSchema:\n\n  %s\n" % etree_tostring(schema_elem, max_lines=20))
        if sourceline is not None:
            msg.append(u"\nInstance (line %r):\n\n  %s\n" % (sourceline, etree_tostring(elem, max_lines=20)))
        elif elem is not None:
            msg.append(u"\nInstance:\n\n  %s\n" % etree_tostring(self.elem, max_lines=20))
        return u''.join(msg)

    if PY3:
        __str__ = __unicode__


class XMLSchemaDecodeError(XMLSchemaValidationError):
    """Raised when an XML data string is not decodable to a Python object."""

    def __init__(self, validator, obj, decoder, reason=None):
        self.obj = obj
        self.decoder = decoder
        self.reason = reason
        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message=u"failed decoding %r with %r.\n",
            elem=obj if is_etree_element(obj) else None
        )


class XMLSchemaEncodeError(XMLSchemaValidationError):
    """Raised when an object is not encodable to an XML data string."""

    def __init__(self, validator, obj, encoder, reason=None):
        self.obj = obj
        self.encoder = encoder
        self.reason = reason
        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message=u"failed encoding %r with %r.\n",
            elem=obj if is_etree_element(obj) else None
        )


class XMLSchemaChildrenValidationError(XMLSchemaValidationError):

    def __init__(self, validator, elem, index, expected=None):
        self.index = index
        self.expected = expected

        elem_ref = qname_to_prefixed(elem.tag, validator.namespaces)
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
