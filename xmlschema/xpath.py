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
This module defines a mixin class for enabling XPath on schemas.
"""
from __future__ import unicode_literals
from abc import abstractmethod
from elementpath import XPath2Parser, XPathSchemaContext, AbstractSchemaProxy

from .compat import Sequence
from .qnames import XSD_SCHEMA
from .namespaces import XSD_NAMESPACE
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError


class XMLSchemaContext(XPathSchemaContext):
    """
    XPath dynamic context class for *xmlschema* library. Implements safe iteration
    methods for schema elements that recognize circular references.
    """
    def _iter_descendants(self):
        def safe_iter_descendants(context):
            elem = context.item
            yield elem
            if elem.text is not None:
                context.item = elem.text
                yield context.item
            if len(elem):
                context.size = len(elem)
                for context.position, context.item in enumerate(elem):
                    if context.item.is_global:
                        for item in safe_iter_descendants(context):
                            yield item
                    elif getattr(context.item, 'ref', None) is not None:
                        yield context.item
                    elif context.item not in local_items:
                        local_items.append(context.item)
                        for item in safe_iter_descendants(context):
                            yield item

        local_items = []
        return safe_iter_descendants(self)

    def _iter_context(self):
        def safe_iter_context(context):
            elem = context.item
            yield elem
            if elem.text is not None:
                context.item = elem.text
                yield context.item

            for item in elem.attrib.items():
                context.item = item
                yield item

            if len(elem):
                context.size = len(elem)
                for context.position, context.item in enumerate(elem):
                    if context.item.is_global:
                        for item in safe_iter_context(context):
                            yield item
                    elif getattr(context.item, 'ref', None) is not None:
                        yield context.item
                    elif context.item not in local_items:
                        local_items.append(context.item)
                        for item in safe_iter_context(context):
                            yield item

        local_items = []
        return safe_iter_context(self)


class XMLSchemaProxy(AbstractSchemaProxy):
    """XPath schema proxy for the *xmlschema* library."""
    def __init__(self, schema=None, base_element=None):
        if schema is None:
            from xmlschema import XMLSchema
            schema = XMLSchema.meta_schema
        super(XMLSchemaProxy, self).__init__(schema, base_element)

        if base_element is not None:
            try:
                if base_element.schema is not schema:
                    raise XMLSchemaValueError("%r is not an element of %r" % (base_element, schema))
            except AttributeError:
                raise XMLSchemaTypeError("%r is not an XsdElement" % base_element)

    def get_context(self):
        return XMLSchemaContext(root=self._schema, item=self._base_element)

    def get_type(self, qname):
        try:
            return self._schema.maps.types[qname]
        except KeyError:
            return None

    def get_attribute(self, qname):
        try:
            return self._schema.maps.attributes[qname]
        except KeyError:
            return None

    def get_element(self, qname):
        try:
            return self._schema.maps.elements[qname]
        except KeyError:
            return None

    def get_substitution_group(self, qname):
        try:
            return self._schema.maps.substitution_groups[qname]
        except KeyError:
            return None

    def is_instance(self, obj, type_qname):
        xsd_type = self._schema.maps.types[type_qname]
        try:
            xsd_type.encode(obj)
        except ValueError:
            return False
        else:
            return True

    def cast_as(self, obj, type_qname):
        xsd_type = self._schema.maps.types[type_qname]
        return xsd_type.decode(obj)

    def iter_atomic_types(self):
        for xsd_type in self._schema.maps.types.values():
            if xsd_type.target_namespace != XSD_NAMESPACE and hasattr(xsd_type, 'primitive_type'):
                yield xsd_type

    def get_primitive_type(self, xsd_type):
        if not xsd_type.is_simple():
            return self._schema.maps.types['{%s}anyType' % XSD_NAMESPACE]
        elif not hasattr(xsd_type, 'primitive_type'):
            if xsd_type.base_type is None:
                return xsd_type
            return self.get_primitive_type(xsd_type.base_type)
        elif xsd_type.primitive_type is not xsd_type:
            return self.get_primitive_type(xsd_type.primitive_type)
        else:
            return xsd_type


class ElementPathMixin(Sequence):
    """
    Mixin abstract class for enabling ElementTree and XPath API on XSD components.

    :cvar text: The Element text. Its value is always `None`. For compatibility with the ElementTree API.
    :cvar tail: The Element tail. Its value is always `None`. For compatibility with the ElementTree API.
    """
    _attrib = {}
    text = None
    tail = None
    namespaces = {}
    xpath_default_namespace = None
    xpath_proxy = None

    @abstractmethod
    def __iter__(self):
        pass

    def __getitem__(self, i):
        try:
            return [e for e in self][i]
        except AttributeError:
            raise IndexError('child index out of range')

    def __reversed__(self):
        return reversed([e for e in self])

    def __len__(self):
        return len([e for e in self])

    @property
    def tag(self):
        """Alias of the *name* attribute. For compatibility with the ElementTree API."""
        return getattr(self, 'name')

    @property
    def attrib(self):
        """Returns the Element attributes. For compatibility with the ElementTree API."""
        return getattr(self, 'attributes', self._attrib)

    def get(self, key, default=None):
        """Gets an Element attribute. For compatibility with the ElementTree API."""
        return self.attrib.get(key, default)

    def iterfind(self, path, namespaces=None):
        """
        Creates and iterator for all XSD subelements matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: is an optional mapping from namespace prefix to full name.
        :return: an iterable yielding all matching XSD subelements in document order.
        """
        path = path.strip()
        if path.startswith('/') and not path.startswith('//'):
            path = ''.join(['/', XSD_SCHEMA, path])
        if namespaces is None:
            namespaces = {k: v for k, v in self.namespaces.items() if k}

        parser = XPath2Parser(namespaces, strict=False, schema=self.xpath_proxy,
                              default_namespace=self.xpath_default_namespace)
        root_token = parser.parse(path)
        context = XMLSchemaContext(self)
        return root_token.select(context)

    def find(self, path, namespaces=None):
        """
        Finds the first XSD subelement matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: The first matching XSD subelement or ``None`` if there is not match.
        """
        path = path.strip()
        if path.startswith('/') and not path.startswith('//'):
            path = ''.join(['/', XSD_SCHEMA, path])
        if namespaces is None:
            namespaces = {k: v for k, v in self.namespaces.items() if k}

        parser = XPath2Parser(namespaces, strict=False, schema=self.xpath_proxy,
                              default_namespace=self.xpath_default_namespace)
        root_token = parser.parse(path)
        context = XMLSchemaContext(self)
        return next(root_token.select(context), None)

    def findall(self, path, namespaces=None):
        """
        Finds all XSD subelements matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: a list containing all matching XSD subelements in document order, an empty \
        list is returned if there is no match.
        """
        path = path.strip()
        if path.startswith('/') and not path.startswith('//'):
            path = ''.join(['/', XSD_SCHEMA, path])
        if namespaces is None:
            namespaces = {k: v for k, v in self.namespaces.items() if k}

        parser = XPath2Parser(namespaces, strict=False, schema=self.xpath_proxy,
                              default_namespace=self.xpath_default_namespace)
        root_token = parser.parse(path)
        context = XMLSchemaContext(self)
        return root_token.get_results(context)

    def iter(self, tag=None):
        """
        Creates an iterator for the XSD element and its subelements. If tag is not `None` or '*',
        only XSD elements whose matches tag are returned from the iterator. Local elements are
        expanded without repetitions. Element references are not expanded because the global
        elements are not descendants of other elements.
        """
        def safe_iter(elem):
            if tag is None or elem.is_matching(tag):
                yield elem
            for child in elem:
                if child.is_global:
                    for e in safe_iter(child):
                        yield e
                elif getattr(child, 'ref', None) is not None:
                    if tag is None or elem.is_matching(tag):
                        yield child
                elif child not in local_elements:
                    local_elements.append(child)
                    for e in safe_iter(child):
                        yield e

        if tag == '*':
            tag = None
        local_elements = []
        return safe_iter(self)

    def iterchildren(self, tag=None):
        """
        Creates an iterator for the child elements of the XSD component. If *tag* is not `None`
        or '*', only XSD elements whose name matches tag are returned from the iterator.
        """
        if tag == '*':
            tag = None
        for child in self:
            if tag is None or child.is_matching(tag):
                yield child
