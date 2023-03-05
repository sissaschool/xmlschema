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
from typing import TYPE_CHECKING, Any, Optional, List, Dict, Type

from ..aliases import NamespacesType, BaseXsdType
from .default import ElementData, XMLSchemaConverter

if TYPE_CHECKING:
    from ..validators import XsdElement


class ParkerConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Parker convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-parker-convention
    ref: https://developer.mozilla.org/en-US/docs/Archive/JXON#The_Parker_Convention

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param preserve_root: If `True` the root element will be preserved. For default \
    the Parker convention remove the document root element, returning only the value.
    """
    __slots__ = ()

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 preserve_root: bool = False, **kwargs: Any) -> None:
        kwargs.update(attr_prefix=None, text_key='', cdata_prefix=None)
        super(ParkerConverter, self).__init__(
            namespaces, dict_class, list_class,
            preserve_root=preserve_root, **kwargs
        )

    @property
    def lossy(self) -> bool:
        return True

    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> Any:
        xsd_type = xsd_type or xsd_element.type
        preserve_root = self.preserve_root
        if xsd_type.simple_type is not None:
            if preserve_root:
                return self.dict([(self.map_qname(data.tag), data.text)])
            else:
                return data.text
        else:
            result_dict = self.dict()
            for name, value, xsd_child in self.map_content(data.content):
                if preserve_root:
                    try:
                        if len(value) == 1:
                            value = value[name]
                    except (TypeError, KeyError):
                        pass

                try:
                    result_dict[name].append(value)
                except KeyError:
                    if isinstance(value, MutableSequence):
                        result_dict[name] = self.list([value])
                    else:
                        result_dict[name] = value
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])

            for k, v in result_dict.items():
                if isinstance(v, MutableSequence) and len(v) == 1:
                    value = v.pop()
                    v.extend(value)

            if preserve_root:
                return self.dict([(self.map_qname(data.tag), result_dict)])
            else:
                return result_dict if result_dict else None

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        name: str = xsd_element.name
        if not isinstance(obj, MutableMapping):
            if obj == '':
                obj = None
            if xsd_element.type.simple_type is not None:
                return ElementData(xsd_element.name, obj, None, {})
            else:
                return ElementData(xsd_element.name, None, obj, {})
        else:
            if not obj:
                return ElementData(xsd_element.name, None, None, {})
            elif self.preserve_root:
                try:
                    items = obj[self.map_qname(name)]
                except KeyError:
                    return ElementData(xsd_element.name, None, None, {})
            else:
                items = obj

            try:
                xsd_group = xsd_element.type.model_group
                if xsd_group is None:
                    xsd_group = xsd_element.any_type.model_group
                    assert xsd_group is not None

                content = []
                for name, value in obj.items():
                    ns_name = self.unmap_qname(name)
                    if not isinstance(value, MutableSequence) or not value:
                        content.append((ns_name, value))
                    elif any(isinstance(v, MutableSequence) for v in value):
                        for item in value:
                            content.append((ns_name, item))
                    else:
                        for xsd_child in xsd_group.iter_elements():
                            matched_element = xsd_child.match(ns_name, resolve=True)
                            if matched_element is not None:
                                if matched_element.type and matched_element.type.is_list():
                                    content.append((ns_name, value))
                                else:
                                    content.extend((ns_name, item) for item in value)
                                break
                        else:
                            content.extend((ns_name, item) for item in value)

            except AttributeError:
                return ElementData(xsd_element.name, items, None, {})
            else:
                return ElementData(xsd_element.name, None, content, {})
