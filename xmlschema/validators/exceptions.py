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
from ..etree import etree_tostring, is_etree_element, etree_getpath
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
    :type source: XMLResource
    """
    def __init__(self, validator, message, elem=None, source=None):
        self.validator = validator
        self.message = message
        self.elem = elem
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

    @property
    def path(self):
        elem, root = self.elem, self.root
        if elem is None or root is None:
            return
        else:
            return etree_getpath(elem, root)


class XMLSchemaNotBuiltError(XMLSchemaValidatorError, RuntimeError):
    """
    Raised when there is an improper usage attempt of a not built XSD validator.

    :param validator: the XSD validator.
    :type validator: XsdValidator
    :param message: the error message.
    :type message: str or unicode
    """
    def __init__(self, validator, message, elem=None):
        super(XMLSchemaNotBuiltError).__init__(
            validator=validator,
            message=message,
            elem=getattr(validator, 'elem', None),
            source=getattr(validator, 'source', None)
        )


class XMLSchemaParseError(XMLSchemaValidatorError, ValueError):
    """
    Raised when an error is found during the building of an XSD validator.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param message: the error message.
    :type message: str or unicode
    :param elem: the element that contains the error.
    :type elem: Element
    """
    def __init__(self, validator, message, elem=None):
        super(XMLSchemaParseError, self).__init__(
            validator=validator,
            message=message,
            elem=elem if elem is not None else getattr(validator, 'elem', None),
            source=getattr(validator, 'source', None)
        )


class XMLSchemaValidationError(XMLSchemaValidatorError, ValueError):
    """
    Raised when the XML data is not validated with the XSD component or schema.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param obj: the not validated XML data.
    :type obj: Element or tuple or str or list or int or float or bool
    :param reason: the detailed reason of failed validation.
    :type reason: str or unicode
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    """
    _message = u"failed validating {!r} with {!r}.\n"

    def __init__(self, validator, obj, reason=None, source=None):
        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message=self._message.format(obj, validator),
            elem=obj if is_etree_element(obj) else None,
            source=source,
        )
        self.obj = obj
        self.reason = reason
        self.schema_elem = getattr(validator, 'elem', None)

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        schema_elem, elem, sourceline = self.schema_elem, self.elem, self.sourceline
        msg = [self.message]
        if self.reason is not None:
            msg.append(u'\nReason: %s\n' % self.reason)
        if schema_elem is not None:
            msg.append(u"\nSchema:\n\n  %s\n" % etree_tostring(schema_elem, max_lines=20))
        if sourceline is not None:
            msg.append(u"\nInstance (line %r):\n\n  %s\n" % (sourceline, etree_tostring(elem, max_lines=20)))
        elif elem is not None:
            msg.append(u"\nInstance:\n\n  %s\n" % etree_tostring(self.elem, max_lines=20))
        return u''.join(msg)

    if PY3:
        __str__ = __unicode__


class XMLSchemaDecodeError(XMLSchemaValidationError):
    """
    Raised when an XML data string is not decodable to a Python object.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param obj: the not validated XML data.
    :type obj: Element or tuple or str or list or int or float or bool
    :param decoder: the XML data decoder.
    :type decoder: type or function
    :param reason: the detailed reason of failed validation.
    :type reason: str or unicode
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    """
    _message = u"failed decoding {!r} with {!r}.\n"

    def __init__(self, validator, obj, decoder, reason=None, source=None):
        super(XMLSchemaDecodeError, self).__init__(validator, obj, reason, source=None)
        self.decoder = decoder


class XMLSchemaEncodeError(XMLSchemaValidationError):
    """
    Raised when an object is not encodable to an XML data string.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param obj: the not validated XML data.
    :type obj: Element or tuple or str or list or int or float or bool
    :param encoder: the XML encoder.
    :type encoder: type or function
    :param reason: the detailed reason of failed validation.
    :type reason: str or unicode
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    """
    _message = u"failed encoding {!r} with {!r}.\n"

    def __init__(self, validator, obj, encoder, reason=None, source=None):
        super(XMLSchemaEncodeError, self).__init__(validator, obj, reason, source)
        self.encoder = encoder


class XMLSchemaChildrenValidationError(XMLSchemaValidationError):
    """
    Raised when a child element is not validated.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param elem: the not validated XML element.
    :type elem: Element
    :param index: the child index.
    :type index: int
    :param expected: the detailed reason of failed validation.
    :type expected: str or list or tuple
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    """
    def __init__(self, validator, elem, index, expected=None, source=None):
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

        super(XMLSchemaChildrenValidationError, self).__init__(validator, elem, reason, source)


class XMLSchemaIncludeWarning(XMLSchemaWarning):
    """A schema include fails."""
    pass


class XMLSchemaImportWarning(XMLSchemaWarning):
    """A schema namespace import fails."""
    pass
