#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
from abc import ABCMeta
from copy import copy
from itertools import count
from typing import TYPE_CHECKING, cast, overload, Any, Dict, List, Iterator, \
    Optional, Union, Tuple, Type, MutableMapping, MutableSequence
from elementpath import XPathContext, XPath2Parser, build_node_tree, protocols
from elementpath.etree import etree_tostring

from .exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from .aliases import ElementType, XMLSourceType, NamespacesType, BaseXsdType, DecodeType
from .helpers import get_namespace, get_prefixed_qname, local_name, raw_xml_encode
from .converters import ElementData, XMLSchemaConverter
from .resources import XMLResource
from . import validators

if TYPE_CHECKING:
    from .validators import XMLSchemaValidationError, XsdElement


class DataElement(MutableSequence['DataElement']):
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
    _children: List['DataElement']
    tag: str
    attrib: Dict[str, Any]
    nsmap: Dict[str, str]

    value: Optional[Any] = None
    tail: Optional[str] = None
    xsd_element: Optional['XsdElement'] = None
    xsd_type: Optional[BaseXsdType] = None
    _encoder: Optional['XsdElement'] = None

    def __init__(self, tag: str,
                 value: Optional[Any] = None,
                 attrib: Optional[Dict[str, Any]] = None,
                 nsmap: Optional[MutableMapping[str, str]] = None,
                 xsd_element: Optional['XsdElement'] = None,
                 xsd_type: Optional[BaseXsdType] = None) -> None:

        super(DataElement, self).__init__()
        self._children = []
        self.tag = tag
        self.attrib = {}
        self.nsmap = {}

        if value is not None:
            self.value = value
        if attrib is not None:
            self.attrib.update(attrib)
        if nsmap is not None:
            self.nsmap.update(nsmap)

        if xsd_element is not None:
            self.xsd_element = xsd_element
            self.xsd_type = xsd_type or xsd_element.type
        elif xsd_type is not None:
            self.xsd_type = xsd_type
        elif self.xsd_element is not None:
            self._encoder = self.xsd_element

    @overload
    def __getitem__(self, i: int) -> 'DataElement': ...  # pragma: no cover

    @overload
    def __getitem__(self, s: slice) -> MutableSequence['DataElement']: ...  # pragma: no cover

    def __getitem__(self, i: Union[int, slice]) \
            -> Union['DataElement', MutableSequence['DataElement']]:
        return self._children[i]

    def __setitem__(self, i: Union[int, slice], child: Any) -> None:
        self._children[i] = child

    def __delitem__(self, i: Union[int, slice]) -> None:
        del self._children[i]

    def __len__(self) -> int:
        return len(self._children)

    def insert(self, i: int, child: 'DataElement') -> None:
        assert isinstance(child, DataElement)
        self._children.insert(i, child)

    def __repr__(self) -> str:
        return '%s(tag=%r)' % (self.__class__.__name__, self.tag)

    def __iter__(self) -> Iterator['DataElement']:
        yield from self._children

    def __setattr__(self, key: str, value: Any) -> None:
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
            if not isinstance(value, (validators.XsdSimpleType, validators.XsdComplexType)):
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
    def text(self) -> Optional[str]:
        """The string value of the data element."""
        return raw_xml_encode(self.value)

    def get(self, key: str, default: Any = None) -> Any:
        """Gets a data element attribute."""
        try:
            return self.attrib[key]
        except KeyError:
            if not self.nsmap:
                return default

            # Try a match with mapped/unmapped name
            if key.startswith('{'):
                key = get_prefixed_qname(key, self.nsmap)
                return self.attrib.get(key, default)
            elif ':' in key:
                try:
                    _prefix, _local_name = key.split(':')
                    key = '{%s}%s' % (self.nsmap[_prefix], _local_name)
                except (ValueError, KeyError):
                    pass
                else:
                    return self.attrib.get(key, default)
            return default

    def set(self, key: str, value: Any) -> None:
        """Sets a data element attribute."""
        self.attrib[key] = value

    @property
    def xsd_version(self) -> str:
        return '1.0' if self.xsd_element is None else self.xsd_element.xsd_version

    @property
    def namespace(self) -> str:
        """The element's namespace."""
        if self.xsd_element is None:
            return get_namespace(self.tag)
        return get_namespace(self.tag) or self.xsd_element.target_namespace

    @property
    def name(self) -> str:
        """The element's name, that matches the tag."""
        return self.tag

    @property
    def prefixed_name(self) -> str:
        """The prefixed name, or the tag if no prefix is defined for its namespace."""
        return get_prefixed_qname(self.tag, self.nsmap)

    @property
    def local_name(self) -> str:
        """The local part of the tag."""
        return local_name(self.tag)

    def iter(self, tag: Optional[str] = None) -> Iterator['DataElement']:
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

    def iterchildren(self, tag: Optional[str] = None) -> Iterator['DataElement']:
        """
        Creates an iterator for the child data elements. If *tag* is not `None` or '*',
        only data elements whose name matches tag are returned from the iterator.
        """
        if tag == '*':
            tag = None
        for child in self:
            if tag is None or tag == child.tag:
                yield child

    def get_namespaces(self, namespaces: Optional[NamespacesType] = None) -> NamespacesType:
        """
        Returns an overall namespace map for DetaElement and its descendants,
        resolving prefix redefinitions.

        :param namespaces: builds the namespace map starting over the dictionary provided.
        """
        namespaces = copy(namespaces) if namespaces is not None else {}
        nsmap = None

        for elem in self.iter():
            if nsmap is elem.nsmap:
                continue
            else:
                nsmap = elem.nsmap
                for prefix, uri in nsmap.items():
                    if not prefix:
                        if not uri:
                            continue
                        elif '' not in namespaces:
                            if self.namespace:
                                namespaces[prefix] = uri
                                continue
                        elif namespaces[''] == uri:
                            continue
                        prefix = 'default'

                    while prefix in namespaces:
                        if namespaces[prefix] == uri:
                            break
                        match = re.search(r'(\d+)$', prefix)
                        if match:
                            index = int(match.group()) + 1
                            prefix = prefix[:match.span()[0]] + str(index)
                        else:
                            prefix += '0'
                    else:
                        namespaces[prefix] = uri

        return namespaces

    def validate(self, use_defaults: bool = True,
                 namespaces: Optional[NamespacesType] = None,
                 max_depth: Optional[int] = None) -> None:
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

    def is_valid(self, use_defaults: bool = True,
                 namespaces: Optional[NamespacesType] = None,
                 max_depth: Optional[int] = None) -> bool:
        """
        Like :meth:`validate` except it does not raise an exception on validation
        error but returns ``True`` if the XML data object is valid, ``False`` if
        it's invalid.

        :raises: :exc:`XMLSchemaValueError` if the instance has no schema bindings.
        """
        error = next(self.iter_errors(use_defaults, namespaces, max_depth), None)
        return error is None

    def iter_errors(self, use_defaults: bool = True,
                    namespaces: Optional[NamespacesType] = None,
                    max_depth: Optional[int] = None) -> Iterator['XMLSchemaValidationError']:
        """
        Generates a sequence of validation errors if the XML data object is invalid.
        Accepts the same arguments of :meth:`validate`.
        """
        if self._encoder is None:
            raise XMLSchemaValueError("%r has no schema bindings" % self)

        kwargs: Dict[str, Any] = {
            'namespaces': self.get_namespaces(namespaces),
            'converter': DataElementConverter,
            'use_defaults': use_defaults,
        }
        if isinstance(max_depth, int) and max_depth >= 0:
            kwargs['max_depth'] = max_depth

        for result in self._encoder.iter_encode(self, **kwargs):
            if isinstance(result, validators.XMLSchemaValidationError):
                yield result
            else:
                del result

    def encode(self, validation: str = 'strict', **kwargs: Any) \
            -> Union[ElementType, Tuple[ElementType, List['XMLSchemaValidationError']]]:
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
        kwargs['namespaces'] = self.get_namespaces(kwargs.get('namespaces'))
        if 'converter' not in kwargs:
            kwargs['converter'] = DataElementConverter

        encoder: Union['XsdElement', BaseXsdType]
        if self._encoder is not None:
            encoder = self._encoder
        elif validation == 'skip':
            encoder = validators.XMLSchema.builtin_types()['anyType']
        else:
            raise XMLSchemaValueError("%r has no schema bindings" % self)

        return encoder.encode(self, validation=validation, **kwargs)

    to_etree = encode

    def tostring(self, namespaces: Optional[MutableMapping[str, str]] = None,
                 indent: str = '', max_lines: Optional[int] = None,
                 spaces_for_tab: int = 4, xml_declaration: bool = False,
                 encoding: str = 'unicode', method: str = 'xml') -> str:
        """
        Serializes the data element tree to an XML source string.

        :param namespaces: is an optional mapping from namespace prefix to URI. \
        Provided namespaces are registered before serialization. Ignored if the \
        provided *elem* argument is a lxml Element instance.
        :param indent: the base line indentation.
        :param max_lines: if truncate serialization after a number of lines \
        (default: do not truncate).
        :param spaces_for_tab: number of spaces for replacing tab characters. For \
        default tabs are replaced with 4 spaces, provide `None` to keep tab characters.
        :param xml_declaration: if set to `True` inserts the XML declaration at the head.
        :param encoding: if "unicode" (the default) the output is a string, \
        otherwise it’s binary.
        :param method: is either "xml" (the default), "html" or "text".
        :return: a Unicode string.
        """
        root, _ = self.encode(validation='lax')
        if not hasattr(root, 'nsmap'):
            namespaces = self.get_namespaces(namespaces)

        _string = etree_tostring(
            elem=root,
            namespaces=namespaces,
            indent=indent,
            max_lines=max_lines,
            spaces_for_tab=spaces_for_tab,
            xml_declaration=xml_declaration,
            encoding=encoding,
            method=method
        )
        if isinstance(_string, bytes):  # pragma: no cover
            return _string.decode('utf-8')
        return _string

    def _get_xpath_context(self) -> XPathContext:
        xpath_root = build_node_tree(cast(protocols.ElementProtocol, self))
        return XPathContext(xpath_root)

    def find(self, path: str,
             namespaces: Optional[NamespacesType] = None) -> Optional['DataElement']:
        """
        Finds the first data element matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: an optional mapping from namespace prefix to namespace URI.
        :return: the first matching data element or ``None`` if there is no match.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = self._get_xpath_context()
        result = next(parser.parse(path).select_results(context), None)
        return result if isinstance(result, DataElement) else None

    def findall(self, path: str,
                namespaces: Optional[NamespacesType] = None) -> List['DataElement']:
        """
        Finds all data elements matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: a list containing all matching data elements in document order, \
        an empty list is returned if there is no match.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = self._get_xpath_context()
        results = parser.parse(path).get_results(context)
        if not isinstance(results, list):  # pragma: no cover
            return []
        return cast(List[DataElement], [e for e in results if isinstance(e, DataElement)])

    def iterfind(self, path: str,
                 namespaces: Optional[NamespacesType] = None) -> Iterator['DataElement']:
        """
        Creates and iterator for all XSD subelements matching the path.

        :param path: an XPath expression that considers the data element as the root.
        :param namespaces: is an optional mapping from namespace prefix to full name.
        :return: an iterable yielding all matching data elements in document order.
        """
        parser = XPath2Parser(namespaces, strict=False)
        context = self._get_xpath_context()
        results = parser.parse(path).select_results(context)
        yield from filter(lambda x: isinstance(x, DataElement), results)


class DataBindingMeta(ABCMeta):
    """Metaclass for creating classes with bindings to XSD elements."""

    xsd_element: 'XsdElement'

    def __new__(mcs, name: str, bases: Tuple[Type[Any], ...],
                attrs: Dict[str, Any]) -> 'DataBindingMeta':
        try:
            xsd_element = attrs['xsd_element']
        except KeyError:
            msg = "attribute 'xsd_element' is required for an XSD data binding class"
            raise XMLSchemaAttributeError(msg) from None

        if not isinstance(xsd_element, validators.XsdElement):
            raise XMLSchemaTypeError("{!r} is not an XSD element".format(xsd_element))

        attrs['__module__'] = None
        return super(DataBindingMeta, mcs).__new__(mcs, name, bases, attrs)

    def __init__(cls, name: str, bases: Tuple[Type[Any], ...], attrs: Dict[str, Any]) -> None:
        super(DataBindingMeta, cls).__init__(name, bases, attrs)
        cls.xsd_version = cls.xsd_element.xsd_version
        cls.namespace = cls.xsd_element.target_namespace

    def fromsource(cls, source: Union[XMLSourceType, XMLResource],
                   allow: str = 'all', defuse: str = 'remote',
                   timeout: int = 300, **kwargs: Any) -> DecodeType[Any]:
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
    :param map_attribute_names: define if map the names of attributes to prefixed \
    form. Defaults to `True`. If `False` the names are kept to extended format.
    """
    __slots__ = 'data_element_class', 'map_attribute_names'

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 data_element_class: Optional[Type['DataElement']] = None,
                 map_attribute_names: bool = True,
                 **kwargs: Any) -> None:
        if data_element_class is None:
            self.data_element_class = DataElement
        else:
            self.data_element_class = data_element_class

        self.map_attribute_names = map_attribute_names
        kwargs.update(attr_prefix='', text_key='', cdata_prefix='')
        super(DataElementConverter, self).__init__(namespaces, **kwargs)

    @property
    def lossy(self) -> bool:
        return False

    @property
    def losslessly(self) -> bool:
        return True

    def copy(self, **kwargs: Any) -> 'DataElementConverter':
        obj = cast(DataElementConverter, super().copy(**kwargs))
        obj.data_element_class = kwargs.get('data_element_class', self.data_element_class)
        return obj

    def get_data_element(self, data: ElementData, xsd_element: 'XsdElement',
                         xsd_type: Optional[BaseXsdType] = None) -> DataElement:
        return self.data_element_class(
            tag=data.tag,
            value=data.text,
            nsmap=self.namespaces,
            xsd_element=xsd_element,
            xsd_type=xsd_type
        )

    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> 'DataElement':
        data_element = self.get_data_element(data, xsd_element, xsd_type)
        if self.map_attribute_names:
            data_element.attrib.update(self.map_attributes(data.attributes))
        elif data.attributes:
            data_element.attrib.update(data.attributes)

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

    def element_encode(self, data_element: 'DataElement', xsd_element: 'XsdElement',
                       level: int = 0) -> ElementData:
        self.namespaces.update(data_element.nsmap)
        if not xsd_element.is_matching(data_element.tag):
            raise XMLSchemaValueError("Unmatched tag")

        attributes = {self.unmap_qname(k, xsd_element.attributes): v
                      for k, v in data_element.attrib.items()}

        data_len = len(data_element)
        if not data_len:
            return ElementData(data_element.tag, data_element.value, None, attributes)

        content: List[Tuple[Union[str, int], Any]] = []
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

    def get_data_element(self, data: ElementData, xsd_element: 'XsdElement',
                         xsd_type: Optional[BaseXsdType] = None) -> DataElement:
        cls = xsd_element.get_binding(self.data_element_class)
        return cls(
            tag=data.tag,
            value=data.text,
            nsmap=self.namespaces,
            xsd_type=xsd_type
        )
