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
from itertools import count
from elementpath import XPathContext, XPath2Parser

from .exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from .etree import etree_tostring
from .helpers import get_namespace, get_prefixed_qname, local_name, raw_xml_encode
from .converters import ElementData, XMLSchemaConverter
from .resources import XMLResource
from . import validators


class DataElement(MutableSequence):
    """
    Data Element, an Element like object with decoded data and schema bindings.

    :param tag: a string containing a QName in extended format.
    :param value: the simple typed value of the element.
    :param attrib: the typed attributes of the element.
    :param nsmap: an optional map from prefixes to namespaces.
    :param xsd_element: an optional XSD element association.
    :param xsd_type: an optional XSD type association. Can be provided \
    also if the instance is not bound with an XSD element.
    """
    value = None
    tail = None
    xsd_element = None
    xsd_type = None
    _encoder = None

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

        if xsd_element is not None:
            self.xsd_element = xsd_element
            self.xsd_type = xsd_type or xsd_element.type
        elif xsd_type is not None:
            self.xsd_type = xsd_type
        elif self.xsd_element is not None:
            self._encoder = self.xsd_element

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

    def __setattr__(self, key, value):
        if key == 'xsd_element':
            if not isinstance(value, validators.XsdElement):
                raise XMLSchemaTypeError("invalid type for attribute 'xsd_element'")
            elif self.xsd_element is value:
                pass
            elif self.xsd_element is not None:
                raise XMLSchemaValueError("the instance is already bound to another XSD element")
            elif self.xsd_type is not None and self.xsd_type is not value.type:
                raise XMLSchemaValueError("the instance is already bound to another XSD type")

        elif key == 'xsd_type':
            if not isinstance(value, validators.XsdType):
                raise XMLSchemaTypeError("invalid type for attribute 'xsd_type'")
            elif self.xsd_type is not None and self.xsd_type is not value:
                raise XMLSchemaValueError("the instance is already bound to another XSD type")
            elif self.xsd_element is None or value is not self.xsd_element.type:
                self._encoder = value.schema.create_element(
                    self.tag, parent=value, form='unqualified'
                )
                self._encoder.type = value
            else:
                self._encoder = self.xsd_element

        super(DataElement, self).__setattr__(key, value)

    @property
    def text(self):
        """The string value of the data element."""
        return raw_xml_encode(self.value)

    def get(self, key, default=None):
        """Gets a data element attribute."""
        return self.attrib.get(key, default)

    def set(self, key, value):
        """Sets a data element attribute."""
        self.attrib[key] = value

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

    def validate(self, use_defaults=True, namespaces=None, max_depth=None):
        """
        Validates the XML data object.

        :param use_defaults: whether to use default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI. \
        For default uses the namespace map of the XML data object.
        :param max_depth: maximum depth for validation, for default there is no limit.
        :raises: :exc:`XMLSchemaValidationError` if XML data object is not valid.
        :raises: :exc:`XMLSchemaValueError` if the instance has no schema bindings.
        """
        for error in self.iter_errors(use_defaults, namespaces, max_depth):
            raise error

    def is_valid(self, use_defaults=True, namespaces=None, max_depth=None):
        """
        Like :meth:`validate` except it does not raise an exception on validation
        error but returns ``True`` if the XML data object is valid, ``False`` if
        it's invalid.

        :raises: :exc:`XMLSchemaValueError` if the instance has no schema bindings.
        """
        error = next(self.iter_errors(use_defaults, namespaces, max_depth), None)
        return error is None

    def iter_errors(self, use_defaults=True, namespaces=None, max_depth=None):
        """
        Generates a sequence of validation errors if the XML data object is invalid.
        Accepts the same arguments of :meth:`validate`.
        """
        if self._encoder is None:
            raise XMLSchemaValueError("{!r} has no schema bindings".format(self))

        kwargs = {
            'converter': DataElementConverter,
            'use_defaults': use_defaults,
        }
        if namespaces:
            kwargs['namespaces'] = namespaces
        if isinstance(max_depth, int) and max_depth >= 0:
            kwargs['max_depth'] = max_depth

        for result in self._encoder.iter_encode(self, **kwargs):
            if isinstance(result, validators.XMLSchemaValidationError):
                yield result
            else:
                del result

    def encode(self, validation='strict', **kwargs):
        """
        Encodes the data object to XML.

        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_encode` \
        of :class:`XsdElement`.
        :return: An ElementTree's Element. If *validation* argument is 'lax' a \
        2-items tuple is returned, where the first item is the encoded object and \
        the second item is a list with validation errors.
        :raises: :exc:`XMLSchemaValidationError` if the object is invalid \
        and ``validation='strict'``.
        """
        if 'converter' not in kwargs:
            kwargs['converter'] = DataElementConverter

        if self._encoder is not None:
            encoder = self._encoder
        elif validation == 'skip':
            encoder = validators.XMLSchema.builtin_types()['anyType']
        else:
            raise XMLSchemaValueError("{!r} has no schema bindings".format(self))

        return encoder.encode(self, validation=validation, **kwargs)

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

    xsd_element = None

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

    def fromsource(cls, source, allow='all', defuse='remote', timeout=300, **kwargs):
        if not isinstance(source, XMLResource):
            source = XMLResource(source, allow=allow, defuse=defuse, timeout=timeout)
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
    __slots__ = 'data_element_class',

    def __init__(self, namespaces=None, data_element_class=None, **kwargs):
        self.data_element_class = data_element_class or DataElement
        kwargs.update(attr_prefix='', text_key='', cdata_prefix='')
        super(DataElementConverter, self).__init__(namespaces, **kwargs)

    @property
    def lossy(self):
        return False

    @property
    def losslessly(self):
        return True

    def copy(self, **kwargs):
        obj = super().copy(**kwargs)
        obj.data_element_class = kwargs.get('data_element_class', self.data_element_class)
        return obj

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
            for name, value, _ in self.map_content(data.content):
                if not name.isdigit():
                    data_element.append(value)
                else:
                    try:
                        data_element[-1].tail = value
                    except IndexError:
                        data_element.value = value

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

        content = []
        cdata_num = count(1)
        if data_element.value is not None:
            content.append((next(cdata_num), data_element.value))

        for e in data_element:
            content.append((e.tag, e))
            if e.tail is not None:
                content.append((next(cdata_num), e.tail))

        return ElementData(data_element.tag, None, content, attributes)


class DataBindingConverter(DataElementConverter):
    """
    A :class:`DataElementConverter` that uses XML data binding classes for
    decoding. Takes the same arguments of its parent class but the argument
    *data_element_class* is used for define the base for creating the missing
    XML binding classes.
    """
    __slots__ = ()

    def element_decode(self, data, xsd_element, xsd_type=None, level=0):
        cls = xsd_element.get_binding(self.data_element_class)
        data_element = cls(
            tag=data.tag,
            value=data.text,
            nsmap=self.namespaces,
            xsd_type=xsd_type
        )
        data_element.attrib.update((k, v) for k, v in self.map_attributes(data.attributes))

        if (xsd_type or xsd_element.type).model_group is not None:
            for name, value, _ in self.map_content(data.content):
                if not name.isdigit():
                    data_element.append(value)
                else:
                    try:
                        data_element[-1].tail = value
                    except IndexError:
                        data_element.value = value

        return data_element
