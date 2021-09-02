#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module defines a proxy class and a mixin class for enabling XPath on schemas.
"""
from abc import abstractmethod
from collections.abc import Sequence
from typing import Any
import re

from elementpath import AttributeNode, TypedElement, XPath2Parser, \
    XPathSchemaContext, AbstractSchemaProxy

from .names import XSD_NAMESPACE
from .helpers import get_qname, local_name, get_prefixed_qname
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError

_REGEX_TAG_POSITION = re.compile(r'\b\[\d+]')


def iter_schema_nodes(root, with_root=True, with_attributes=False):
    """
    Iteration function for schema nodes. It doesn't yield text nodes,
    that are always `None` for schema elements, and detects visited
    element in order to skip already visited nodes.

    :param root: schema or schema's element.
    :param with_root: if `True` yields initial element.
    :param with_attributes: if `True` yields also attribute nodes.
    """
    def attribute_node(x):
        return AttributeNode(*x)

    def _iter_schema_nodes(elem):
        for child in elem:
            if child in nodes:
                continue
            elif child.ref is not None:
                nodes.add(child)
                yield child
                if child.ref not in nodes:
                    nodes.add(child.ref)
                    yield child.ref
                    if with_attributes:
                        yield from map(attribute_node, child.attributes.items())
                    yield from _iter_schema_nodes(child.ref)
            else:
                nodes.add(child)
                yield child
                if with_attributes:
                    yield from map(attribute_node, child.attributes.items())
                yield from _iter_schema_nodes(child)

    if isinstance(root, TypedElement):
        root = root.elem

    nodes = {root}
    if with_root:
        yield root
    if with_attributes:
        yield from map(attribute_node, root.attributes.items())
    yield from _iter_schema_nodes(root)


class XMLSchemaContext(XPathSchemaContext):
    """XPath dynamic schema context for the *xmlschema* library."""
    _iter_nodes = staticmethod(iter_schema_nodes)


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

    def bind_parser(self, parser):
        parser.schema = self
        parser.symbol_table = parser.__class__.symbol_table.copy()

        with self._schema.lock:
            if self._schema.xpath_tokens is None:
                self._schema.xpath_tokens = {
                    xsd_type.name: parser.schema_constructor(xsd_type.name)
                    for xsd_type in self.iter_atomic_types()
                }

        parser.symbol_table.update(self._schema.xpath_tokens)

    def get_context(self):
        return XMLSchemaContext(
            root=self._schema,
            namespaces=self._schema.namespaces,
            item=self._base_element
        )

    def is_instance(self, obj, type_qname):
        # FIXME: use elementpath.datatypes for checking atomic datatypes
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
        return xsd_type.root_type


class ElementPathMixin(Sequence):
    """
    Mixin abstract class for enabling ElementTree and XPath 2.0 API on XSD components.

    :cvar text: the Element text, for compatibility with the ElementTree API.
    :cvar tail: the Element tail, for compatibility with the ElementTree API.
    """
    text = None
    tail = None
    attributes: Any = {}
    namespaces: Any = {}
    xpath_default_namespace = ''

    @abstractmethod
    def __iter__(self):
        raise NotImplementedError

    def __getitem__(self, i):
        try:
            return [e for e in self][i]
        except IndexError:
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
        return self.attributes

    def get(self, key, default=None):
        """Gets an Element attribute. For compatibility with the ElementTree API."""
        return self.attributes.get(key, default)

    @property
    def xpath_proxy(self):
        """Returns an XPath proxy instance bound with the schema."""
        raise NotImplementedError

    def _get_xpath_namespaces(self, namespaces=None):
        """
        Returns a dictionary with namespaces for XPath selection.

        :param namespaces: an optional map from namespace prefix to namespace URI. \
        If this argument is not provided the schema's namespaces are used.
        """
        if namespaces is None:
            namespaces = {k: v for k, v in self.namespaces.items() if k}
            namespaces[''] = self.xpath_default_namespace
        elif '' not in namespaces:
            namespaces[''] = self.xpath_default_namespace

        xpath_namespaces = XPath2Parser.DEFAULT_NAMESPACES.copy()
        xpath_namespaces.update(namespaces)
        return xpath_namespaces

    def find(self, path, namespaces=None):
        """
        Finds the first XSD subelement matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: an optional mapping from namespace prefix to namespace URI.
        :return: the first matching XSD subelement or ``None`` if there is no match.
        """
        path = _REGEX_TAG_POSITION.sub('', path.strip())  # Strips tags positions from path
        namespaces = self._get_xpath_namespaces(namespaces)
        parser = XPath2Parser(namespaces, strict=False)
        context = XMLSchemaContext(self)

        return next(parser.parse(path).select_results(context), None)

    def findall(self, path, namespaces=None):
        """
        Finds all XSD subelements matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: a list containing all matching XSD subelements in document order, an empty \
        list is returned if there is no match.
        """
        path = _REGEX_TAG_POSITION.sub('', path.strip())  # Strips tags positions from path
        namespaces = self._get_xpath_namespaces(namespaces)
        parser = XPath2Parser(namespaces, strict=False)
        context = XMLSchemaContext(self)

        return parser.parse(path).get_results(context)

    def iterfind(self, path, namespaces=None):
        """
        Creates and iterator for all XSD subelements matching the path.

        :param path: an XPath expression that considers the XSD component as the root element.
        :param namespaces: is an optional mapping from namespace prefix to full name.
        :return: an iterable yielding all matching XSD subelements in document order.
        """
        path = _REGEX_TAG_POSITION.sub('', path.strip())  # Strips tags positions from path
        namespaces = self._get_xpath_namespaces(namespaces)
        parser = XPath2Parser(namespaces, strict=False)
        context = XMLSchemaContext(self)

        return parser.parse(path).select_results(context)

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
                if child.parent is None:
                    yield from safe_iter(child)
                elif getattr(child, 'ref', None) is not None:
                    if tag is None or child.is_matching(tag):
                        yield child
                elif child not in local_elements:
                    local_elements.add(child)
                    yield from safe_iter(child)

        if tag == '*':
            tag = None
        local_elements = set()
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


class XPathElement(ElementPathMixin):
    """An element node for making XPath operations on schema types."""

    parent = None

    def __init__(self, name, xsd_type):
        self.name = name
        self.type = xsd_type
        try:
            self.attributes = xsd_type.attributes
        except AttributeError:
            pass

    def __iter__(self):
        if not self.type.has_simple_content():
            yield from self.type.content.iter_elements()

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)

    @property
    def schema(self):
        return self.type.schema

    @property
    def target_namespace(self):
        return self.type.schema.target_namespace

    @property
    def namespaces(self):
        return self.type.schema.namespaces

    @property
    def local_name(self):
        return local_name(self.name)

    @property
    def qualified_name(self):
        return get_qname(self.target_namespace, self.name)

    @property
    def prefixed_name(self):
        return get_prefixed_qname(self.name, self.namespaces)
