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
from __future__ import unicode_literals

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
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :type namespaces: dict
    :ivar path: the XPath of the element, calculated when the element is set or the XML resource is set.
    """
    def __init__(self, validator, message, elem=None, source=None, namespaces=None):
        self.validator = validator
        message = message.strip()
        self.message = message[:-1] if message[-1] in ('.', ':') else message
        self.namespaces = namespaces
        self.elem = elem
        self.source = source

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.elem is None:
            return '%s.' % self.message
        else:
            elem, path = self.elem, self.path
            msg = ['%s:\n' % self.message]
            if elem is not None:
                elem_as_string = etree_tostring(self.elem, self.namespaces, '  ', 20)
                if hasattr(elem, 'sourceline'):
                    msg.append("Schema (line %r):\n\n%s\n" % (elem.sourceline, elem_as_string))
                else:
                    msg.append("Schema:\n\n%s\n" % elem_as_string)
            if path is not None:
                msg.append("Path: %s\n" % path)
            return '\n'.join(msg)

    if PY3:
        __str__ = __unicode__

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and not is_etree_element(value):
            raise XMLSchemaValueError("'elem' attribute requires an Element, not %r." % type(value))
        super(XMLSchemaValidatorError, self).__setattr__(name, value)

        # Calculate and set the element's path: have to be calculated asap because is the
        # XML resource is lazy the intermediate nodes could be deleted.
        if name in ('elem', 'source'):
            elem, root = self.elem, self.root
            if not is_etree_element(elem) or not is_etree_element(root):
                self.path = None
            else:
                self.path = etree_getpath(elem, root, self.namespaces, relative=False, add_position=True)

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
    """
    Raised when there is an improper usage attempt of a not built XSD validator.

    :param validator: the XSD validator.
    :type validator: XsdValidator
    :param message: the error message.
    :type message: str or unicode
    """
    def __init__(self, validator, message):
        super(XMLSchemaNotBuiltError).__init__(
            validator=validator,
            message=message,
            elem=getattr(validator, 'elem', None),
            source=getattr(validator, 'source', None),
            namespaces=getattr(validator, 'namespaces', None)
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
            source=getattr(validator, 'source', None),
            namespaces=getattr(validator, 'namespaces', None),
        )


class XMLSchemaValidationError(XMLSchemaValidatorError, ValueError):
    """
    Raised when the XML data is not validated with the XSD component or schema.
    It's used by decoding and encoding methods. Encoding validation errors do
    not include XML data element and source, so the error is limited to a message
    containing object representation and a reason.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param obj: the not validated XML data.
    :type obj: Element or tuple or str or list or int or float or bool
    :param reason: the detailed reason of failed validation.
    :type reason: str or unicode
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :type namespaces: dict
    """
    _message = "failed validating {!r} with {!r}.\n"

    def __init__(self, validator, obj, reason=None, source=None, namespaces=None):
        super(XMLSchemaValidationError, self).__init__(
            validator=validator,
            message=self._message.format(obj, validator),
            elem=obj if is_etree_element(obj) else None,
            source=source,
            namespaces=namespaces,
        )
        self.obj = obj
        self.reason = reason

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        elem, path = self.elem, self.path
        msg = ['%s:\n' % self.message]
        if self.reason is not None:
            msg.append('Reason: %s\n' % self.reason)
        if hasattr(self.validator, 'tostring'):
            msg.append("Schema:\n\n%s\n" % self.validator.tostring('  ', 20))
        if elem is not None:
            elem_as_string = etree_tostring(elem, self.namespaces, '  ', 20)
            if hasattr(elem, 'sourceline'):
                msg.append("Instance (line %r):\n\n%s\n" % (elem.sourceline, elem_as_string))
            else:
                msg.append("Instance:\n\n%s\n" % elem_as_string)
        if path is not None:
            msg.append("Path: %s\n" % path)
        return '\n'.join(msg)

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
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :type namespaces: dict
    """
    _message = "failed decoding {!r} with {!r}.\n"

    def __init__(self, validator, obj, decoder, reason=None, source=None, namespaces=None):
        super(XMLSchemaDecodeError, self).__init__(validator, obj, reason, source, namespaces)
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
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :type namespaces: dict
    """
    _message = "failed encoding {!r} with {!r}.\n"

    def __init__(self, validator, obj, encoder, reason=None, source=None, namespaces=None):
        super(XMLSchemaEncodeError, self).__init__(validator, obj, reason, source, namespaces)
        self.encoder = encoder


class XMLSchemaChildrenValidationError(XMLSchemaValidationError):
    """
    Raised when a child element is not validated.

    :param validator: the XSD validator.
    :type validator: XsdValidator or function
    :param elem: the not validated XML element.
    :type elem: Element or ElementData
    :param index: the child index.
    :type index: int
    :param particle: the validator particle that generated the error. Maybe the validator itself.
    :type particle: ParticleMixin
    :param occurs: the particle occurrences.
    :type occurs: int
    :param expected: the expected element tags/object names.
    :type expected: str or list or tuple
    :param source: the XML resource that contains the error.
    :type source: XMLResource
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :type namespaces: dict
    """
    def __init__(self, validator, elem, index, particle, occurs=0, expected=None, source=None, namespaces=None):
        self.index = index
        self.particle = particle
        self.occurs = occurs
        self.expected = expected

        tag = qname_to_prefixed(elem.tag, validator.namespaces)
        if index >= len(elem):
            reason = "The content of element %r is not complete." % tag
        else:
            child_tag = qname_to_prefixed(elem[index].tag, validator.namespaces)
            reason = "Unexpected child with tag %r at position %d." % (child_tag, index + 1)

        if occurs and particle.is_missing(occurs):
            reason += " The particle %r occurs %d times but the minimum is %d." % (
                particle, occurs, particle.min_occurs
            )
        elif particle.is_over(occurs):
            reason += " The particle %r occurs %d times but the maximum is %d." % (
                particle, occurs, particle.max_occurs
            )

        if expected is None:
            pass
        else:
            expected_tags = []
            for xsd_element in expected:
                if xsd_element.name is not None:
                    expected_tags.append(repr(xsd_element.prefixed_name))
                elif xsd_element.process_contents == 'strict':
                    expected_tags.append('from %r namespace/s' % xsd_element.namespace)

            if not expected_tags:
                reason += " No child element is expected at this point."
            elif len(expected_tags) > 1:
                reason += " Tags %s are expected." % expected_tags
            else:
                reason += " Tag %s expected." % expected_tags[0]

        super(XMLSchemaChildrenValidationError, self).__init__(validator, elem, reason, source, namespaces)


class XMLSchemaIncludeWarning(XMLSchemaWarning):
    """A schema include fails."""
    pass


class XMLSchemaImportWarning(XMLSchemaWarning):
    """A schema namespace import fails."""
    pass
