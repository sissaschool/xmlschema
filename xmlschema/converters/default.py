#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections import namedtuple
from collections.abc import MutableMapping, MutableSequence
from typing import TYPE_CHECKING, cast, Any, Dict, Iterator, Iterable, \
    List, Optional, Type, Tuple, Union
from xml.etree.ElementTree import Element

from ..exceptions import XMLSchemaTypeError
from ..names import XSI_NAMESPACE
from ..aliases import NamespacesType, BaseXsdType
from ..namespaces import NamespaceMapper

if TYPE_CHECKING:
    from ..validators import XsdElement


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


class XMLSchemaConverter(NamespaceMapper):
    """
    Generic XML Schema based converter class. A converter is used to compose
    decoded XML data for an Element into a data structure and to build an Element
    from encoded data structure. There are two methods for interfacing the
    converter with the decoding/encoding process. The method *element_decode*
    accepts an ElementData tuple, containing the element parts, and returns
    a data structure. The method *element_encode* accepts a data structure and
    returns an ElementData tuple. For default character data parts are ignored.
    Prefixes and text key can be changed also using alphanumeric values but
    ambiguities with schema elements could affect XML data re-encoding.

    :param namespaces: map from namespace prefixes to URI.
    :param dict_class: dictionary class to use for decoded data. Default is `dict`.
    :param list_class: list class to use for decoded data. Default is `list`.
    :param etree_element_class: the class that has to be used to create new XML elements, \
    if not provided uses the ElementTree's Element class.
    :param text_key: is the key to apply to element's decoded text data.
    :param attr_prefix: controls the mapping of XML attributes, to the same name or \
    with a prefix. If `None` the converter ignores attributes.
    :param cdata_prefix: is used for including and prefixing the character data parts \
    of a mixed content, that are labeled with an integer instead of a string. \
    Character data parts are ignored if this argument is `None`.
    :param indent: number of spaces for XML indentation (default is 4).
    :param strip_namespaces: if set to `True` removes namespace declarations from data and \
    namespace information from names, during decoding or encoding. Defaults to `False`.
    :param preserve_root: if set to `True` the root element is preserved, wrapped into a \
    single-item dictionary. Applicable only to default converter, to \
    :class:`UnorderedConverter` and to :class:`ParkerConverter`.
    :param force_dict: if set to `True` complex elements with simple content are decoded \
    with a dictionary also if there are no decoded attributes. Applicable only to default \
    converter and to :class:`UnorderedConverter`. Defaults to `False`.
    :param force_list: if set to `True` child elements are decoded within a list in any case. \
    Applicable only to default converter and to :class:`UnorderedConverter`. Defaults to `False`.

    :ivar dict: dictionary class to use for decoded data.
    :ivar list: list class to use for decoded data.
    :ivar etree_element_class: Element class to use
    :ivar text_key: key for decoded Element text
    :ivar attr_prefix: prefix for attribute names
    :ivar cdata_prefix: prefix for character data parts
    :ivar indent: indentation to use for rebuilding XML trees
    :ivar preserve_root: preserve the root element on decoding
    :ivar force_dict: force dictionary for complex elements with simple content
    :ivar force_list: force list for child elements
    """
    ns_prefix: str
    dict: Type[Dict[str, Any]] = dict
    list: Type[List[Any]] = list

    etree_element_class: Type[Element] = Element

    __slots__ = ('text_key', 'ns_prefix', 'attr_prefix', 'cdata_prefix',
                 'indent', 'preserve_root', 'force_dict', 'force_list')

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 etree_element_class: Optional[Type[Element]] = None,
                 text_key: Optional[str] = '$',
                 attr_prefix: Optional[str] = '@',
                 cdata_prefix: Optional[str] = None,
                 indent: int = 4,
                 strip_namespaces: bool = False,
                 preserve_root: bool = False,
                 force_dict: bool = False,
                 force_list: bool = False,
                 **kwargs: Any) -> None:

        super(XMLSchemaConverter, self).__init__(namespaces, strip_namespaces)

        if dict_class is not None:
            self.dict = dict_class
        if list_class is not None:
            self.list = list_class
        if etree_element_class is not None:
            self.etree_element_class = etree_element_class

        self.text_key = text_key
        self.attr_prefix = attr_prefix
        self.cdata_prefix = cdata_prefix
        self.ns_prefix = 'xmlns' if attr_prefix is None else f'{attr_prefix}xmlns'

        self.indent = indent
        self.preserve_root = preserve_root
        self.force_dict = force_dict
        self.force_list = force_list

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {'attr_prefix', 'text_key', 'cdata_prefix'}:
            if value is not None and not isinstance(value, str):
                msg = "%(name)r must be a <class 'str'> instance or None, not %(type)r"
                raise XMLSchemaTypeError(msg % {'name': name, 'type': type(value)})

        elif name in {'strip_namespaces', 'preserve_root', 'force_dict', 'force_list'}:
            if not isinstance(value, bool):
                msg = "%(name)r must be a <class 'bool'> instance, not %(type)r"
                raise XMLSchemaTypeError(msg % {'name': name, 'type': type(value)})

        elif name == 'indent':
            if isinstance(value, bool) or not isinstance(value, int):
                msg = "%(name)r must be a <class 'int'> instance, not %(type)r"
                raise XMLSchemaTypeError(msg % {'name': name, 'type': type(value)})

        elif name == 'dict':
            if not issubclass(value, MutableMapping):
                msg = "%(name)r must be a MutableMapping object, not %(type)r"
                raise XMLSchemaTypeError(msg % {'name': name, 'type': type(value)})

        elif name == 'list':
            if not issubclass(value, MutableSequence):
                msg = "%(name)r must be a MutableSequence object, not %(type)r"
                raise XMLSchemaTypeError(msg % {'name': name, 'type': type(value)})

        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self) -> bool:
        """The converter ignores some kind of XML data during decoding/encoding."""
        return self.cdata_prefix is None or self.text_key is None or self.attr_prefix is None

    @property
    def losslessly(self) -> bool:
        """
        The XML data is decoded without loss of quality, neither on data nor on data model
        shape. Only losslessly converters can be always used to encode to an XML data that
        is strictly conformant to the schema.
        """
        return False

    def copy(self, **kwargs: Any) -> 'XMLSchemaConverter':
        return type(self)(
            namespaces=kwargs.get('namespaces', self._namespaces),
            dict_class=kwargs.get('dict_class', self.dict),
            list_class=kwargs.get('list_class', self.list),
            etree_element_class=kwargs.get('etree_element_class'),
            text_key=kwargs.get('text_key', self.text_key),
            attr_prefix=kwargs.get('attr_prefix', self.attr_prefix),
            cdata_prefix=kwargs.get('cdata_prefix', self.cdata_prefix),
            indent=kwargs.get('indent', self.indent),
            strip_namespaces=kwargs.get('strip_namespaces', self.strip_namespaces),
            preserve_root=kwargs.get('preserve_root', self.preserve_root),
            force_dict=kwargs.get('force_dict', self.force_dict),
            force_list=kwargs.get('force_list', self.force_list),
        )

    def map_attributes(self, attributes: Iterable[Tuple[str, Any]]) \
            -> Iterator[Tuple[str, Any]]:
        """
        Creates an iterator for converting decoded attributes to a data structure with
        appropriate prefixes. If the instance has a not-empty map of namespaces registers
        the mapped URIs and prefixes.

        :param attributes: A sequence or an iterator of couples with the name of \
        the attribute and the decoded value. Default is `None` (for `simpleType` \
        elements, that don't have attributes).
        """
        if self.attr_prefix is None or not attributes:
            return
        else:
            for name, value in attributes:
                yield self.attr_prefix + self.map_qname(name), value

    def map_content(self, content: Iterable[Tuple[str, Any, Any]]) \
            -> Iterator[Tuple[str, Any, Any]]:
        """
        A generator function for converting decoded content to a data structure.
        If the instance has a not-empty map of namespaces registers the mapped URIs
        and prefixes.

        :param content: A sequence or an iterator of tuples with the name of the \
        element, the decoded value and the `XsdElement` instance associated.
        """
        if not content:
            return

        for name, value, xsd_child in content:
            try:
                if name[0] == '{':
                    yield self.map_qname(name), value, xsd_child
                else:
                    yield name, value, xsd_child
            except TypeError:
                if self.cdata_prefix is not None:
                    yield f'{self.cdata_prefix}{name}', value, xsd_child

    def etree_element(self, tag: str,
                      text: Optional[str] = None,
                      children: Optional[List[Element]] = None,
                      attrib: Optional[Dict[str, str]] = None,
                      level: int = 0) -> Element:
        """
        Builds an ElementTree's Element using arguments and the element class and
        the indent spacing stored in the converter instance.

        :param tag: the Element tag string.
        :param text: the Element text.
        :param children: the list of Element children/subelements.
        :param attrib: a dictionary with Element attributes.
        :param level: the level related to the encoding process (0 means the root).
        :return: an instance of the Element class is set for the converter instance.
        """
        if type(self.etree_element_class) is type(Element):
            if attrib is None:
                elem = self.etree_element_class(tag)
            else:
                elem = self.etree_element_class(tag, self.dict(attrib))
        else:
            # FIXME: need a more refined check
            nsmap = {prefix if prefix else None: uri
                     for prefix, uri in self._namespaces.items() if uri}
            elem = self.etree_element_class(tag, nsmap=nsmap)  # type: ignore[arg-type]
            elem.attrib.update(attrib)  # type: ignore[arg-type]

        if children:
            elem.extend(children)
            elem.text = text or '\n' + ' ' * self.indent * (level + 1)
            elem.tail = '\n' + ' ' * self.indent * level
        else:
            elem.text = text
            elem.tail = '\n' + ' ' * self.indent * level

        return elem

    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> Any:
        """
        Converts a decoded element data to a data structure.

        :param data: ElementData instance decoded from an Element node.
        :param xsd_element: the `XsdElement` associated to decode the data.
        :param xsd_type: optional XSD type for supporting dynamic type through \
        *xsi:type* or xs:alternative.
        :param level: the level related to the decoding process (0 means the root).
        :return: a data structure containing the decoded data.
        """
        xsd_type = xsd_type or xsd_element.type
        result_dict = self.dict()
        if level == 0 and xsd_element.is_global() and not self.strip_namespaces and self:
            schema_namespaces = set(xsd_element.namespaces.values())
            result_dict.update(
                (f'{self.ns_prefix}:{k}' if k else self.ns_prefix, v)
                for k, v in self._namespaces.items()
                if v in schema_namespaces or v == XSI_NAMESPACE
            )

        xsd_group = xsd_type.model_group
        if xsd_group is None:
            if data.attributes or self.force_dict and not xsd_type.is_simple():
                result_dict.update(self.map_attributes(data.attributes))
                if data.text is not None and self.text_key is not None:
                    result_dict[self.text_key] = data.text
                return result_dict
            else:
                return data.text
        else:
            if data.attributes:
                result_dict.update(self.map_attributes(data.attributes))

            has_single_group = xsd_group.is_single()
            if data.content:
                for name, value, xsd_child in self.map_content(data.content):
                    try:
                        result = result_dict[name]
                    except KeyError:
                        if xsd_child is None or has_single_group and xsd_child.is_single():
                            result_dict[name] = self.list([value]) if self.force_list else value
                        else:
                            result_dict[name] = self.list([value])
                    else:
                        if not isinstance(result, MutableSequence) or not result:
                            result_dict[name] = self.list([result, value])
                        elif isinstance(result[0], MutableSequence) or \
                                not isinstance(value, MutableSequence):
                            result.append(value)
                        else:
                            result_dict[name] = self.list([result, value])

            elif data.text is not None and self.text_key is not None:
                result_dict[self.text_key] = data.text

            if level == 0 and self.preserve_root:
                return self.dict(
                    [(self.map_qname(data.tag), result_dict if result_dict else None)]
                )

            if not result_dict:
                return None
            elif len(result_dict) == 1 and self.text_key in result_dict:
                return result_dict[self.text_key]
            return result_dict

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        """
        Extracts XML decoded data from a data structure for encoding into an ElementTree.

        :param obj: the decoded object.
        :param xsd_element: the `XsdElement` associated to the decoded data structure.
        :param level: the level related to the encoding process (0 means the root).
        :return: an ElementData instance.
        """
        if level != 0:
            tag = xsd_element.name
        else:
            if xsd_element.is_global():
                tag = xsd_element.qualified_name
            else:
                tag = xsd_element.name
            if self.preserve_root and isinstance(obj, MutableMapping):
                match_local_name = cast(bool, self.strip_namespaces or self.default_namespace)
                match = xsd_element.get_matching_item(obj, self.ns_prefix, match_local_name)
                if match is not None:
                    obj = match

        if not isinstance(obj, MutableMapping):
            if xsd_element.type.simple_type is not None:
                return ElementData(tag, obj, None, {})
            elif xsd_element.type.mixed and isinstance(obj, (str, bytes)):
                return ElementData(tag, None, [(1, obj)], {})
            else:
                return ElementData(tag, None, obj, {})

        text = None
        content: List[Tuple[Union[int, str], Any]] = []
        attributes = {}

        for name, value in obj.items():
            if name == self.text_key:
                text = value
            elif self.cdata_prefix is not None and \
                    name.startswith(self.cdata_prefix) and \
                    name[len(self.cdata_prefix):].isdigit():
                index = int(name[len(self.cdata_prefix):])
                content.append((index, value))
            elif name == self.ns_prefix:
                self[''] = value
            elif name.startswith(f'{self.ns_prefix}:'):
                if not self.strip_namespaces:
                    self[name[len(self.ns_prefix) + 1:]] = value
            elif self.attr_prefix and \
                    name.startswith(self.attr_prefix) and \
                    name != self.attr_prefix:
                attr_name = name[len(self.attr_prefix):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, MutableSequence) or not value:
                content.append((self.unmap_qname(name), value))
            elif isinstance(value[0], (MutableMapping, MutableSequence)):
                ns_name = self.unmap_qname(name)
                content.extend((ns_name, item) for item in value)
            else:
                xsd_group = xsd_element.type.model_group
                if xsd_group is None:
                    # fallback to xs:anyType encoder
                    xsd_group = xsd_element.any_type.model_group
                    assert xsd_group is not None

                ns_name = self.unmap_qname(name)
                for xsd_child in xsd_group.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type and matched_element.type.is_list():
                            content.append((ns_name, value))
                        else:
                            content.extend((ns_name, item) for item in value)
                        break
                else:
                    if self.attr_prefix == '' and ns_name not in attributes:
                        for key, xsd_attribute in xsd_element.attributes.items():
                            if key and xsd_attribute.is_matching(ns_name):
                                attributes[key] = value
                                break
                        else:
                            content.append((ns_name, value))
                    else:
                        content.append((ns_name, value))

        return ElementData(tag, text, content, attributes)
