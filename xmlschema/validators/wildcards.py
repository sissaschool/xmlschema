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
This module contains classes for XML Schema wildcards.
"""
from __future__ import unicode_literals

from ..exceptions import XMLSchemaValueError
from ..qnames import XSD_ANY, XSD_ANY_ATTRIBUTE
from ..helpers import get_namespace
from ..namespaces import XSI_NAMESPACE
from ..xpath import ElementPathMixin

from .exceptions import XMLSchemaNotBuiltError
from .xsdbase import ValidationMixin, XsdComponent, ParticleMixin


class XsdWildcard(XsdComponent, ValidationMixin):
    names = {}

    def __init__(self, elem, schema, parent):
        if parent is None:
            raise XMLSchemaValueError("'parent' attribute is None but %r cannot be global!" % self)
        super(XsdWildcard, self).__init__(elem, schema, parent)

    def __repr__(self):
        return '%s(namespace=%r, process_contents=%r)' % (
            self.__class__.__name__, self.namespace, self.process_contents
        )

    def _parse(self):
        super(XsdWildcard, self)._parse()

        # Parse namespace and processContents
        namespace = self.elem.get('namespace', '##any')
        items = namespace.strip().split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            self.namespace = namespace.strip()
        elif not all([s not in ('##any', '##other') for s in items]):
            self.parse_error("wrong value %r for 'namespace' attribute." % namespace)
            self.namespace = '##any'
        else:
            self.namespace = namespace.strip()

        self.process_contents = self.elem.get('processContents', 'strict')
        if self.process_contents not in ('lax', 'skip', 'strict'):
            self.parse_error("wrong value %r for 'processContents' attribute." % self.process_contents)

    def _load_namespace(self, namespace):
        if namespace in self.schema.maps.namespaces:
            return

        for url in self.schema.get_locations(namespace):
            try:
                schema = self.schema.import_schema(namespace, url, base_url=self.schema.base_url)
                if schema is not None:
                    try:
                        schema.maps.build()
                    except XMLSchemaNotBuiltError:
                        # Namespace build fails: remove unbuilt schemas and the url hint
                        schema.maps.clear(remove_schemas=True, only_unbuilt=True)
                        self.schema.locations[namespace].remove(url)
                    else:
                        break
            except (OSError, IOError):
                pass

    @property
    def built(self):
        return True

    def is_matching(self, name, default_namespace=None):
        if name is None:
            return False
        elif not name or name[0] == '{':
            return self.is_namespace_allowed(get_namespace(name))
        elif default_namespace is None:
            return self.is_namespace_allowed('')
        else:
            return self.is_namespace_allowed(default_namespace)

    def is_namespace_allowed(self, namespace):
        if self.namespace == '##any' or namespace == XSI_NAMESPACE:
            return True
        elif self.namespace == '##other':
            if namespace:
                return namespace != self.target_namespace
            else:
                return False
        else:
            any_namespaces = self.namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces

    def iter_decode(self, source, validation='lax', *args, **kwargs):
        raise NotImplementedError

    def iter_encode(self, obj, validation='lax', *args, **kwargs):
        raise NotImplementedError


class XsdAnyElement(XsdWildcard, ParticleMixin, ElementPathMixin):
    """
    Class for XSD 1.0 'any' wildcards.

    <any
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )  : ##any
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </any>
    """
    admitted_tags = {XSD_ANY}

    def __repr__(self):
        return '%s(namespace=%r, process_contents=%r, occurs=%r)' % (
            self.__class__.__name__, self.namespace, self.process_contents, self.occurs
        )

    def _parse(self):
        super(XsdAnyElement, self)._parse()
        self._parse_particle(self.elem)

    def is_emptiable(self):
        return self.min_occurs == 0 or self.process_contents != 'strict'

    def match(self, name, default_namespace=None):
        if self.is_matching(name, default_namespace):
            try:
                if name[0] != '{' and default_namespace:
                    return self.maps.lookup_element('{%s}%s' % (default_namespace, name))
                else:
                    return self.maps.lookup_element(name)
            except LookupError:
                pass

    def __iter__(self):
        return iter(())

    def iter(self, tag=None):
        return iter(())

    def iterchildren(self, tag=None):
        return iter(())

    def iter_decode(self, elem, validation='lax', converter=None, **kwargs):
        if self.process_contents == 'skip':
            return

        namespace = get_namespace(elem.tag)
        if self.is_namespace_allowed(namespace):
            self._load_namespace(namespace)
            try:
                xsd_element = self.maps.lookup_element(elem.tag)
            except LookupError:
                if self.process_contents == 'strict' and validation != 'skip':
                    reason = "element %r not found." % elem.tag
                    yield self.validation_error(validation, reason, elem, **kwargs)
            else:
                for result in xsd_element.iter_decode(elem, validation, converter, **kwargs):
                    yield result
        elif validation != 'skip':
            reason = "element %r not allowed here." % elem.tag
            yield self.validation_error(validation, reason, elem, **kwargs)

    def iter_encode(self, obj, validation='lax', converter=None, **kwargs):
        if self.process_contents == 'skip':
            return

        name, value = obj
        namespace = get_namespace(name)
        if self.is_namespace_allowed(namespace):
            self._load_namespace(namespace)
            try:
                xsd_element = self.maps.lookup_element(name)
            except LookupError:
                if self.process_contents == 'strict' and validation != 'skip':
                    reason = "element %r not found." % name
                    yield self.validation_error(validation, reason, **kwargs)
            else:
                for result in xsd_element.iter_encode(value, validation, converter, **kwargs):
                    yield result
        elif validation != 'skip':
            reason = "element %r not allowed here." % name
            yield self.validation_error(validation, reason, value, **kwargs)

    def is_restriction(self, other):
        if not ParticleMixin.is_restriction(self, other):
            return False
        return True


class XsdAnyAttribute(XsdWildcard):
    """
    Class for XSD 1.0 'anyAttribute' wildcards.
    
    <anyAttribute
      id = ID
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </anyAttribute>
    """
    admitted_tags = {XSD_ANY_ATTRIBUTE}

    def match(self, name, default_namespace=None):
        if self.is_matching(name, default_namespace):
            try:
                if name[0] != '{' and default_namespace:
                    return self.maps.lookup_attribute('{%s}%s' % (default_namespace, name))
                else:
                    return self.maps.lookup_attribute(name)
            except LookupError:
                pass

    def iter_decode(self, attribute, validation='lax', **kwargs):
        if self.process_contents == 'skip':
            return

        name, value = attribute
        namespace = get_namespace(name)
        if self.is_namespace_allowed(namespace):
            self._load_namespace(namespace)
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if self.process_contents == 'strict' and validation != 'skip':
                    reason = "attribute %r not found." % name
                    yield self.validation_error(validation, reason, attribute, **kwargs)
            else:
                for result in xsd_attribute.iter_decode(value, validation, **kwargs):
                    yield result
        elif validation != 'skip':
            reason = "attribute %r not allowed." % name
            yield self.validation_error(validation, reason, attribute, **kwargs)

    def iter_encode(self, attribute, validation='lax', **kwargs):
        if self.process_contents == 'skip':
            return

        name, value = attribute
        namespace = get_namespace(name)
        if self.is_namespace_allowed(namespace):
            self._load_namespace(namespace)
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if self.process_contents == 'strict' and validation != 'skip':
                    reason = "attribute %r not found." % name
                    yield self.validation_error(validation, reason, attribute, **kwargs)
            else:
                for result in xsd_attribute.iter_encode(value, validation, **kwargs):
                    yield result
        elif validation != 'skip':
            reason = "attribute %r not allowed." % name
            yield self.validation_error(validation, reason, attribute, **kwargs)


class Xsd11Wildcard(XsdWildcard):

    def _parse(self):
        super(Xsd11Wildcard, self)._parse()

        # Parse notNamespace attribute
        try:
            not_namespace = self.elem.attrib['notNamespace'].strip()
        except KeyError:
            self.not_namespace = None
        else:
            if 'namespace' in self.elem.attrib:
                self.not_namespace = None
                self.parse_error("'namespace' and 'notNamespace' attributes are mutually exclusive.")
            elif not_namespace in ('##local', '##targetNamespace'):
                self.not_namespace = not_namespace
            else:
                self.not_namespace = not_namespace.split()

        # Parse notQName attribute
        try:
            not_qname = self.elem.attrib['notQName'].strip()
        except KeyError:
            self.not_qname = None
        else:
            if not_qname in ('##defined', '##definedSibling'):
                self.not_qname = not_qname
            else:
                self.not_qname = not_qname.split()

    def is_namespace_allowed(self, namespace):
        if self.namespace == '##any' or namespace == XSI_NAMESPACE:
            return True
        elif self.namespace == '##other':
            if namespace:
                return namespace != self.target_namespace
            else:
                return False
        else:
            any_namespaces = self.namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces


class Xsd11AnyElement(XsdAnyElement):
    """
    Class for XSD 1.1 'any' declarations.

    <any
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      notNamespace = List of (anyURI | (##targetNamespace | ##local))
      notQName = List of (QName | (##defined | ##definedSibling))
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </any>
    """
    pass


class Xsd11AnyAttribute(XsdAnyAttribute):
    """
    Class for XSD 1.1 'anyAttribute' declarations.

    <anyAttribute
      id = ID
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      notNamespace = List of (anyURI | (##targetNamespace | ##local))
      notQName = List of (QName | ##defined)
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </anyAttribute>
    """
    pass


class XsdOpenContent(XsdComponent):
    """
    Class for XSD 1.1 'openContent' model definitions.

    <openContent
      id = ID
      mode = (none | interleave | suffix) : interleave
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?), (any?)
    </openContent>
    """
    def __init__(self, elem, schema, parent):
        super(XsdOpenContent, self).__init__(elem, schema, parent)
        self.mode = self.elem.get('mode', 'interleave')
        if self.mode not in ('none', 'interleave', 'suffix'):
            self.parse_error("wrong value %r for 'mode' attribute." % self.mode)

