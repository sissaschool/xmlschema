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
This module contains base functions and classes XML Schema components.
"""
import re

from ..core import PY3, etree_tostring, etree_iselement
from ..exceptions import (
    XMLSchemaParseError, XMLSchemaValueError, XMLSchemaTypeError
)
from ..qnames import (
    local_name, XSD_ANNOTATION_TAG, XSI_NAMESPACE_PATH, XSD_APPINFO_TAG,
    XSD_DOCUMENTATION_TAG, XML_LANG
)
from ..xsdbase import XsdBaseComponent, get_xsd_int_attribute, get_xsd_component, iter_xsd_components


class XsdComponent(XsdBaseComponent):
    """
    XML Schema component base class.

    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
    :param is_global: `True` if the component is a global declaration/definition, \
    `False` if it's local.
    :param name: Name of the component, maybe overwritten by the parse of the `elem` argument.
    """
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    def __init__(self, elem, schema, name=None, is_global=None):
        super(XsdComponent, self).__init__()
        self.is_global = is_global
        self.name = name
        self.schema = schema
        self.elem = elem

    def __setattr__(self, name, value):
        if name == "elem":
            if not etree_iselement(value):
                raise XMLSchemaTypeError("%r attribute must be an Etree Element: %r" % (name, value))
            elif value.tag not in self.admitted_tags:
                raise XMLSchemaValueError(
                    "wrong XSD element %r for %r, must be one of %r." % (
                        local_name(value.tag), self,
                        [local_name(tag) for tag in self.admitted_tags]
                    )
                )
            elif hasattr(self, 'elem'):
                self._elem = self.elem  # redefinition cases
            super(XsdComponent, self).__setattr__(name, value)
            self._parse()
            return
        elif name == "schema":
            if hasattr(self, 'schema') and self.schema.target_namespace != value.target_namespace:
                raise XMLSchemaValueError(
                    "cannot change 'schema' attribute of %r: the actual %r has a different "
                    "target namespace than %r." % (self, self.schema, value)
                )
            self.target_namespace = value.target_namespace
            self.BUILDERS = value.BUILDERS
            self.namespaces = value.namespaces
            self.maps = value.maps
        super(XsdComponent, self).__setattr__(name, value)

    def __repr__(self):
        if self.name:
            return u"<%s %r at %#x>" % (self.__class__.__name__, self.name, id(self))
        else:
            return u"<%s at %#x>" % (self.__class__.__name__, id(self))

    def __str__(self):
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def _parse(self):
        if self.errors:
            del self.errors[:]

    def _parse_error(self, error, elem=None):
        if self.schema.validation == 'skip':
            return
        if isinstance(error, XMLSchemaParseError):
            error.component = self
            error.elem = elem
        else:
            error = XMLSchemaParseError(error, self, elem)
        if self.schema.validation == 'lax':
            self.errors.append(error)
        else:
            raise error

    def _parse_component(self, elem, required=True, strict=True):
        try:
            return get_xsd_component(elem, required, strict)
        except XMLSchemaValueError as err:
            self._parse_error(str(err), elem)

    def _iterparse_components(self, elem):
        try:
            for obj in iter_xsd_components(elem):
                yield obj
        except XMLSchemaValueError as err:
            self._parse_error(str(err), elem)

    def _parse_properties(self, *properties):
        for name in properties:
            try:
                getattr(self, name)
            except (ValueError, TypeError) as err:
                self._parse_error(str(err))

    def _is_namespace_allowed(self, namespace, any_namespace):
        if any_namespace == '##any' or namespace == XSI_NAMESPACE_PATH:
            return True
        elif any_namespace == '##other':
            return namespace != self.target_namespace
        else:
            any_namespaces = any_namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces

    @property
    def id(self):
        """The ``'id'`` attribute of the component tag, ``None`` if missing."""
        return self.elem.get('id')

    @property
    def validation_attempted(self):
        return 'full' if self.built else 'partial'

    @property
    def built(self):
        raise NotImplementedError

    @property
    def admitted_tags(self):
        raise NotImplementedError

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self

    def to_string(self, indent='', max_lines=None, spaces_for_tab=4):
        """
        Returns the etree node of the component as a string.
        """
        if self.elem is not None:
            return etree_tostring(self.elem, indent, max_lines, spaces_for_tab)
        else:
            return str(None)


class XsdAnnotation(XsdComponent):
    """
    Class for XSD 'annotation' definitions.
    
    <annotation
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (appinfo | documentation)*
    </annotation>
    
    <appinfo
      source = anyURI
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </appinfo>
    
    <documentation
      source = anyURI
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </documentation>
    """
    @property
    def admitted_tags(self):
        return {XSD_ANNOTATION_TAG}

    @property
    def built(self):
        return True

    def _parse(self):
        super(XsdAnnotation, self)._parse()
        self.appinfo = []
        self.documentation = []
        for child in self.elem:
            if child.tag == XSD_APPINFO_TAG:
                for key in child.attrib:
                    if key != 'source':
                        self._parse_error("wrong attribute %r for appinfo declaration." % key)
                self.appinfo.append(child)
            elif child.tag == XSD_DOCUMENTATION_TAG:
                for key in child.attrib:
                    if key not in ['source', XML_LANG]:
                        self._parse_error("wrong attribute %r for documentation declaration." % key)
                self.documentation.append(child)


class XsdAnnotated(XsdComponent):

    def _parse(self):
        super(XsdAnnotated, self)._parse()
        try:
            if self.elem[0].tag == XSD_ANNOTATION_TAG:
                self.annotation = XsdAnnotation(self.elem[0], self.schema)
            else:
                self.annotation = None
        except (TypeError, IndexError):
            self.annotation = None

    @property
    def built(self):
        raise NotImplementedError

    @property
    def admitted_tags(self):
        raise NotImplementedError


class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t
    """
    def _parse_particle(self):
        max_occurs = self.max_occurs
        if max_occurs is not None and self.min_occurs > max_occurs:
            getattr(self, '_parse_error')(
                "maxOccurs must be 'unbounded' or greater than minOccurs:"
            )

    @property
    def min_occurs(self):
        return get_xsd_int_attribute(getattr(self, 'elem'), 'minOccurs', default=1, minimum=0)

    @property
    def max_occurs(self):
        try:
            return get_xsd_int_attribute(getattr(self, 'elem'), 'maxOccurs', default=1, minimum=0)
        except (TypeError, ValueError):
            if getattr(self, 'elem').attrib['maxOccurs'] == 'unbounded':
                return None
            raise

    def is_optional(self):
        return getattr(self, 'elem').get('minOccurs', '').strip() == "0"

    def is_emptiable(self):
        return self.min_occurs == 0

    def is_single(self):
        return self.max_occurs == 1

    def is_restriction(self, other):
        return True   # raise NotImplementedError  TODO: implement concrete methods
