#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import MutableMapping, MutableSequence
from typing import TYPE_CHECKING, Any, Optional, List, Dict, Type, Union, Tuple

from ..aliases import NamespacesType, BaseXsdType
from ..names import XSD_ANY_TYPE
from ..helpers import local_name
from .default import ElementData, XMLSchemaConverter

if TYPE_CHECKING:
    from ..validators import XsdElement


class BadgerFishConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Badgerfish convention.

    ref: http://www.sklar.com/badgerfish/
    ref: http://badgerfish.ning.com/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    __slots__ = ()

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 **kwargs: Any) -> None:
        kwargs.update(attr_prefix='@', text_key='$', cdata_prefix='$')
        super(BadgerFishConverter, self).__init__(
            namespaces, dict_class, list_class, **kwargs
        )

    @property
    def lossy(self) -> bool:
        return False

    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> Any:
        xsd_type = xsd_type or xsd_element.type

        tag = self.map_qname(data.tag)
        result_dict = self.dict([t for t in self.map_attributes(data.attributes)])

        if self._use_xmlns:
            if data.xmlns:
                result_dict['@xmlns'] = self.dict((k or '$', v) for k, v in data.xmlns)
            elif not level and xsd_element.is_global() and self:
                result_dict['@xmlns'] = self.dict((k or '$', v) for k, v in self.items())

        xsd_group = xsd_type.model_group
        if xsd_group is None or not data.content:
            if data.text is not None:
                result_dict['$'] = data.text
        else:
            has_single_group = xsd_group.is_single()
            for name, item, xsd_child in self.map_content(data.content):
                if name.startswith('$') and name[1:].isdigit():
                    result_dict[name] = item
                    continue

                assert isinstance(item, MutableMapping) and xsd_child is not None

                item = item[name]
                if name in result_dict:
                    other = result_dict[name]
                    if not isinstance(other, MutableSequence) or not other:
                        result_dict[name] = self.list([other, item])
                    elif isinstance(other[0], MutableSequence) or \
                            not isinstance(item, MutableSequence):
                        other.append(item)
                    else:
                        result_dict[name] = self.list([other, item])
                else:
                    if xsd_type.name == XSD_ANY_TYPE or \
                            has_single_group and xsd_child.is_single():
                        result_dict[name] = item
                    else:
                        result_dict[name] = self.list([item])

        return self.dict([(tag, result_dict)])

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        assert isinstance(obj, MutableMapping)

        tag = xsd_element.name
        if len(obj) != 1 or '$' in obj:
            element_data = obj
        elif tag in obj:
            element_data = obj[tag]
        else:
            try:
                element_data = obj[self.map_qname(tag)]
            except KeyError:
                for k, v in obj.items():
                    if not k.startswith(('$', '@')) and local_name(k) == local_name(tag):
                        element_data = v
                        break
                else:
                    element_data = obj

        if self._use_xmlns and '@xmlns' in element_data:
            self._namespaces.update(
                (k if k != '$' else '', v) for k, v in element_data['@xmlns'].items()
            )

        text = None
        content: List[Tuple[Union[str, int], Any]] = []
        attributes = {}
        xmlns: List[Tuple[str, str]] = []

        for name, value in element_data.items():
            if name == '@xmlns':
                xmlns.extend((k if k != '$' else '', v) for k, v in value.items())
            elif name == '$':
                text = value
            elif name[0] == '$' and name[1:].isdigit():
                content.append((int(name[1:]), value))
            elif name[0] == '@':
                attr_name = name[1:]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, MutableSequence) or not value:
                content.append((self.unmap_qname(name), value))
            elif isinstance(value[0], (MutableMapping, MutableSequence)):
                ns_name = self.unmap_qname(name)
                for item in value:
                    content.append((ns_name, item))
            else:
                xsd_group = xsd_element.type.model_group
                if xsd_group is None:
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
                    content.append((ns_name, value))

        return ElementData(tag, text, content, attributes, xmlns)
