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
from collections.abc import MutableSequence
from elementpath import XPathContext, XPath2Parser

from .exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from .etree import etree_tostring
from .helpers import get_namespace, get_prefixed_qname, local_name, raw_xml_encode
from .converters import ElementData, XMLSchemaConverter
from . import validators


class DataElement(MutableSequence):
    """
    Data Element, an Element like object with decoded data and schema bindings.
    """
    value = None
    tail = None
    xsd_element = None
    _xsd_type = None

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

        if xsd_element is None:
            pass
        elif not isinstance(xsd_element, validators.XsdElement):
            msg = "argument 'xsd_element' must be an {!r} instance"
            raise XMLSchemaTypeError(msg.format(validators.XsdElement))
        elif self.xsd_element is None:
            self.xsd_element = xsd_element
        elif xsd_element is not self.xsd_element:
            raise XMLSchemaValueError("the class has a binding with a different XSD element")

        if xsd_type is None:
            pass
        elif not isinstance(xsd_type, validators.XsdType):
            msg = "argument 'xsd_type' must be an {!r} instance"
            raise XMLSchemaTypeError(msg.format(validators.XsdType))
        else:
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
    def xsd_version(self):
        return '1.0' if self.xsd_element is None else self.xsd_element.xsd_version

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
        if 'converter' not in kwargs:
            kwargs['converter'] = DataElementConverter

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


class DataBindingMeta(ABCMeta):
    """Metaclass for creating classes with bindings to XSD elements."""

    def __new__(mcs, name, bases, attrs):
        try:
            xsd_element = attrs['xsd_element']
        except KeyError:
            msg = "attribute 'xsd_element' is required for an XSD data binding class"
            raise XMLSchemaAttributeError(msg) from None

        if not isinstance(xsd_element, validators.XsdElement):
            raise XMLSchemaTypeError("{!r} is not an XSD element".format(xsd_element))

        attrs['__module__'] = None
        return super(DataBindingMeta, mcs).__new__(mcs, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        super(DataBindingMeta, cls).__init__(name, bases, attrs)
        cls.xsd_version = cls.xsd_element.xsd_version
        cls.namespace = cls.xsd_element.target_namespace

    def fromsource(cls, source, **kwargs):
        if 'converter' not in kwargs:
            kwargs['converter'] = DataBindingConverter
        return cls.xsd_element.schema.decode(source, **kwargs)


class DataElementConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for DataElement objects.

    :param namespaces: a dictionary map from namespace prefixes to URI.
    :param data_element_class: MutableSequence subclass to use for decoded data. \
    Default is `DataElement`.
    """
    data_element_class = DataElement

    def __init__(self, namespaces=None, data_element_class=None, **kwargs):
        if data_element_class is not None:
            self.data_element_class = data_element_class
        kwargs.update(attr_prefix='', text_key='', cdata_prefix='')
        super(DataElementConverter, self).__init__(namespaces, **kwargs)

    @property
    def lossy(self):
        return False

    @property
    def losslessly(self):
        return True

    def element_decode(self, data, xsd_element, xsd_type=None, level=0):
        data_element = self.data_element_class(
            tag=data.tag,
            value=data.text,
            nsmap=self.namespaces,
            xsd_element=xsd_element,
            xsd_type=xsd_type
        )
        data_element.attrib.update((k, v) for k, v in self.map_attributes(data.attributes))

        if (xsd_type or xsd_element.type).model_group is not None:
            data_element.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        return data_element

    def element_encode(self, data_element, xsd_element, level=0):
        self.namespaces.update(data_element.nsmap)
        if not xsd_element.is_matching(data_element.tag, self._namespaces.get('')):
            raise XMLSchemaValueError("Unmatched tag")

        attributes = {self.unmap_qname(k, xsd_element.attributes): v
                      for k, v in data_element.attrib.items()}

        data_len = len(data_element)
        if not data_len:
            return ElementData(data_element.tag, data_element.value, None, attributes)

        elif data_len == 1 and \
                (xsd_element.type.simple_type is not None or not
                 xsd_element.type.content and xsd_element.type.mixed):
            return ElementData(data_element.tag, data_element.value, [], attributes)
        else:
            cdata_num = iter(range(1, data_len))
            content = [
                (self.unmap_qname(e.tag), e) if isinstance(e, self.data_element_class)
                else (next(cdata_num), e) for e in data_element
            ]
            return ElementData(data_element.tag, None, content, attributes)


class DataBindingConverter(DataElementConverter):
    """
    A :class:`DataElementConverter` that uses XML data binding classes for
    decoding. Takes the same arguments of its parent class but the argument
    *data_element_class* is used for define the base for creating the missing
    XML binding classes.
    """
    def element_decode(self, data, xsd_element, xsd_type=None, level=0):
        cls = xsd_element.binding or xsd_element.create_binding(self.data_element_class)
        data_element = cls(
            tag=data.tag,
            value=data.text,
            nsmap=self.namespaces,
            xsd_type=xsd_type
        )
        data_element.attrib.update((k, v) for k, v in self.map_attributes(data.attributes))

        if (xsd_type or xsd_element.type).model_group is not None:
            data_element.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        return data_element
