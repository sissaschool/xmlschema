#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from abc import ABCMeta
from collections import namedtuple
from collections.abc import MutableSequence
from elementpath import XPathContext, XPath2Parser

from .exceptions import XMLSchemaValueError
from .etree import etree_tostring
from .helpers import get_namespace, get_prefixed_qname, local_name, raw_xml_encode


ElementData = namedtuple('ElementData', ['tag', 'text', 'content', 'attributes'])
"""
Namedtuple for Element data interchange between decoders and converters.
The field *tag* is a string containing the Element's tag, *text* can be `None`
or a string representing the Element's text, *content* can be `None`, a list
containing the Element's children or a dictionary containing element name to
list of element contents for the Element's children (used for unordered input
data), *attributes* can be `None` or a dictionary containing the Element's
attributes.
"""


class DataElement(MutableSequence):
    """
    Data Element, an Element like object with decoded data and schema bindings.
    """
    value = None
    tail = None

    def __init__(self, tag, value=None, attrib=None, nsmap=None, xsd_element=None, xsd_type=None):
        super(DataElement, self).__init__()
        self._children = []
        self.tag = tag
        self.attrib = {}
        self.nsmap = {}

        if value is not None:
            self.value = value
        if attrib:
            self.attrib.update(attrib)
        if nsmap:
            self.nsmap.update(nsmap)

        self.xsd_element = xsd_element
        self._xsd_type = xsd_type

    def __getitem__(self, i):
        return self._children[i]

    def __setitem__(self, i, child):
        assert isinstance(child, DataElement)
        self._children[i] = child

    def __delitem__(self, i):
        del self._children[i]

    def __len__(self):
        return len(self._children)

    def insert(self, i, child):
        assert isinstance(child, DataElement)
        self._children.insert(i, child)

    def __repr__(self):
        return '%s(tag=%r)' % (self.__class__.__name__, self.tag)

    def __iter__(self):
        yield from self._children

    @property
    def text(self):
        """The string value of the data element."""
        return raw_xml_encode(self.value)

    def get(self, key, default=None):
        """Gets a data element attribute."""
        return self.attrib.get(key, default)

    @property
    def namespace(self):
        """The element's namespace."""
        if self.xsd_element is None:
            return get_namespace(self.tag)
        return get_namespace(self.tag) or self.xsd_element.target_namespace

    @property
    def name(self):
        """The element's name, that matches the tag."""
        return self.tag

    @property
    def prefixed_name(self):
        """The prefixed name, or the tag if no prefix is defined for its namespace."""
        return get_prefixed_qname(self.tag, self.nsmap)

    @property
    def local_name(self):
        """The local part of the tag."""
        return local_name(self.tag)

    @property
    def xsd_type(self):
        if self._xsd_type is not None:
            return self._xsd_type
        elif self.xsd_element is not None:
            return self.xsd_element.type

    @xsd_type.setter
    def xsd_type(self, xsd_type):
        self._xsd_type = xsd_type

    def encode(self, **kwargs):
        if self._xsd_type is None:
            if self.xsd_element is not None:
                return self.xsd_element.encode(self, **kwargs)
        elif self.xsd_element is not None and self.xsd_element.type is self._xsd_type:
            return self.xsd_element.encode(self, **kwargs)
        else:
            xsd_element = self._xsd_type.schema.create_element(
                self.tag, parent=self._xsd_type, form='unqualified'
            )
            xsd_element.type = self._xsd_type
            return xsd_element.encode(self, **kwargs)

        if kwargs.get('validation') != 'skip':
            msg = "{!r} has no schema bindings and valition mode is not 'skip'"
            raise XMLSchemaValueError(msg.format(self))

        from . import XMLSchema
        any_type = XMLSchema.builtin_types()['anyType']
        return any_type.encode(self, **kwargs)

    to_etree = encode

    def tostring(self, indent='', max_lines=None, spaces_for_tab=4):
        """Serializes the data element tree to an XML source string."""
        root, _ = self.encode(validation='lax')
        return etree_tostring(root, self.nsmap, indent, max_lines, spaces_for_tab)

    def find(self, path, namespaces=None):
        """
        Finds the first data element matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: an optional mapping from namespace prefix to namespace URI.
        :return: the first matching data element or ``None`` if there is no match.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = XPathContext(self)
        return next(parser.parse(path).select_results(context), None)

    def findall(self, path, namespaces=None):
        """
        Finds all data elements matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: a list containing all matching data elements in document order, \
        an empty list is returned if there is no match.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = XPathContext(self)
        return parser.parse(path).get_results(context)

    def iterfind(self, path, namespaces=None):
        """
        Creates and iterator for all XSD subelements matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: is an optional mapping from namespace prefix to full name.
        :return: an iterable yielding all matching data elements in document order.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = XPathContext(self)
        return parser.parse(path).select_results(context)

    def iter(self, tag=None):
        """
        Creates an iterator for the data element and its subelements. If tag
        is not `None` or '*', only data elements whose matches tag are returned
        from the iterator.
        """
        if tag == '*':
            tag = None
        if tag is None or tag == self.tag:
            yield self
        for child in self._children:
            yield from child.iter(tag)

    def iterchildren(self, tag=None):
        """
        Creates an iterator for the child data elements. If *tag* is not `None` or '*',
        only data elements whose name matches tag are returned from the iterator.
        """
        if tag == '*':
            tag = None
        for child in self:
            if tag is None or tag == child.tag:
                yield child


class DataElementMeta(ABCMeta):
    """
    TODO: A metaclass for defining derived data element classes.
     The underlining idea is to develop schema API for XSD elements
     that can be generated by option and stored in a registry if
     necessary.
    """
