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
        dict_class = self.dict

        tag = self.map_qname(data.tag)
        has_local_root = not self and not self.strip_namespaces
        result_dict = dict_class([t for t in self.map_attributes(data.attributes)])
        if has_local_root:
            result_dict['@xmlns'] = dict_class()

        xsd_group = xsd_type.model_group
        if xsd_group is None:
            if data.text is not None:
                result_dict['$'] = data.text
        elif not data.content:
            if data.text is not None:
                result_dict['$1'] = data.text
        else:
            has_single_group = xsd_group.is_single()
            for name, value, xsd_child in self.map_content(data.content):
                try:
                    if '@xmlns' in value:
                        self.transfer(value['@xmlns'])
                        if not value['@xmlns']:
                            del value['@xmlns']
                        elif '' in value['@xmlns']:
                            value['@xmlns']['$'] = value['@xmlns'].pop('')

                    elif '@xmlns' in value[name]:
                        self.transfer(value[name]['@xmlns'])
                        if not value[name]['@xmlns']:
                            del value[name]['@xmlns']
                        elif '' in value[name]['@xmlns']:
                            value[name]['@xmlns']['$'] = value[name]['@xmlns'].pop('')

                    if len(value) == 1:
                        value = value[name]
                except (TypeError, KeyError):
                    pass

                if value is None:
                    value = self.dict()

                try:
                    result = result_dict[name]
                except KeyError:
                    if xsd_child is None or has_single_group and xsd_child.is_single():
                        result_dict[name] = value
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

        if has_local_root:
            if self:
                result_dict['@xmlns'].update(self)
                if not level:
                    result_dict['@xmlns']['$'] = result_dict['@xmlns'].pop('')
            else:
                del result_dict['@xmlns']
            return dict_class([(tag, result_dict)])
        elif level:
            return dict_class([('@xmlns', dict_class(self)), (tag, result_dict)])
        else:
            return dict_class([
                ('@xmlns', dict_class((k if k else '$', v) for k, v in self.items())),
                (tag, result_dict)
            ])

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        tag = xsd_element.qualified_name if level == 0 else xsd_element.name

        if not self.strip_namespaces:
            try:
                self.update((k if k != '$' else '', v) for k, v in obj['@xmlns'].items())
            except KeyError:
                pass

        try:
            element_data = obj[self.map_qname(xsd_element.name)]
        except KeyError:
            try:
                element_data = obj[xsd_element.name]
            except KeyError:
                element_data = obj

        text = None
        content: List[Tuple[Union[str, int], Any]] = []
        attributes = {}

        for name, value in element_data.items():
            if name == '@xmlns':
                continue
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

        return ElementData(tag, text, content, attributes)
