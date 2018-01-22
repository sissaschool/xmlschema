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
This module contains exception classes for the 'xmlschema.components' subpackage.
"""
from ..compat import PY3
from ..exceptions import XMLSchemaException
from ..etree import etree_tostring, etree_iselement
from ..qnames import qname_to_prefixed


class XMLSchemaNotBuiltError(XMLSchemaException, RuntimeError):
    """Raised when a not built XSD component or schema is used."""
    pass


class XMLSchemaParseError(XMLSchemaException, ValueError):
    """Raised when an error is found when parsing an XML Schema component."""

    def __init__(self, message, component=None, elem=None):
        self.message = message or u''
        self.component = component
        self.elem = elem if elem is not None else getattr(component, 'elem', None)

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if etree_iselement(self.elem):
            return u''.join([
                self.message,
                u"\n\n  %s\n" % etree_tostring(self.elem, max_lines=20)
            ])
        else:
            return self.message

    if PY3:
        __str__ = __unicode__


class XMLSchemaValidationError(XMLSchemaException, ValueError):
    """Raised when the XML data is not validated with the XSD component or schema."""

    def __init__(self, validator, obj, reason=None, schema_elem=None, elem=None):
        self.validator = validator
        self.obj = obj
        self.reason = reason
        self.schema_elem = schema_elem or getattr(validator, 'elem', None)
        self.elem = elem or obj if etree_iselement(obj) else None
        self.message = None

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join([
            self.message or u"failed validating %r with %r.\n" % (self.obj, self.validator),
            u'\nReason: %s\n' % self.reason if self.reason is not None else '',
            u"\nSchema:\n\n  %s\n" % etree_tostring(
                self.schema_elem, max_lines=20
            ) if self.schema_elem is not None else '',
            u"\nInstance:\n\n  %s\n" % etree_tostring(
                self.elem, max_lines=20
            ) if self.elem is not None else ''
        ])

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
