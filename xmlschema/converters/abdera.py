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
from typing import TYPE_CHECKING, Any, Optional, List, Dict, Type, Union

from ..exceptions import XMLSchemaValueError
from ..aliases import NamespacesType, BaseXsdType
from ..helpers import local_name
from ..resources import XMLResource
from .default import ElementData, XMLSchemaConverter

if TYPE_CHECKING:
    from ..validators import XsdElement


class AbderaConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Abdera convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-abdera-convention
    ref: https://cwiki.apache.org/confluence/display/ABDERA/JSON+Serialization

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    __slots__ = ()

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 **kwargs: Any) -> None:
        kwargs.update(attr_prefix='', text_key='', cdata_prefix=None)
        super().__init__(namespaces, dict_class, list_class, **kwargs)

    @property
    def xmlns_processing_default(self) -> str:
        return 'stacked' if isinstance(self.source, XMLResource) else 'none'

    @property
    def lossy(self) -> bool:
        return True  # Loss cdata parts

    @property
    def loss_xmlns(self) -> bool:
        return True

    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> Any:
        xsd_type = xsd_type or xsd_element.type
        if xsd_type.simple_type is not None:
            children = data.text
        else:
            children = self.dict()
            for name, value, xsd_child in self.map_content(data.content):
                if value is None:
                    value = self.list()

                try:
                    children[name].append(value)
                except KeyError:
                    if isinstance(value, MutableSequence) and value:
                        children[name] = self.list([value])
                    else:
                        children[name] = value
                except AttributeError:
                    children[name] = self.list([children[name], value])
            if not children:
                children = data.text

        result: Union[List[Any], Dict[str, Any]]
        if data.attributes:
            result = self.dict([
                ('attributes',
                 self.dict((k, v) for k, v in self.map_attributes(data.attributes)))
            ])
            if children is not None and children != []:
                result['children'] = self.list([children])

        elif children is not None:
            result = children
        else:
            result = self.list()

        return result if level else self.dict([(self.map_qname(data.tag), result)])

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        tag = xsd_element.qualified_name if level == 0 else xsd_element.name

        if not isinstance(obj, MutableMapping):
            if obj == []:
                obj = None
            return ElementData(tag, obj, None, {}, None)
        else:
            tag = xsd_element.name
            if level or len(obj) != 1:
                pass
            elif tag in obj:
                obj = obj[tag]
            else:
                try:
                    obj = obj[self.map_qname(tag)]
                except KeyError:
                    for k, v in obj.items():
                        if k.endswith(local_name(tag)):
                            obj = v
                            break

            attributes: Dict[str, Any] = {}
            children: Union[List[Any], MutableMapping[str, Any]]

            try:
                attributes.update((self.unmap_qname(k, xsd_element.attributes), v)
                                  for k, v in obj['attributes'].items())
            except KeyError:
                children = obj
            else:
                children = obj.get('children', [])

            if isinstance(children, MutableMapping):
                children = [children]
            elif children and not isinstance(children[0], MutableMapping):
                if len(children) > 1:
                    raise XMLSchemaValueError("Element %r should have only one child" % tag)
                else:
                    return ElementData(tag, children[0], None, attributes, None)

            content = []
            for child in children:
                for name, value in child.items():
                    if not isinstance(value, MutableSequence) or not value:
                        content.append((self.unmap_qname(name), value))
                    elif isinstance(value[0], (MutableMapping, MutableSequence)):
                        ns_name = self.unmap_qname(name)
                        for item in value:
                            content.append((ns_name, item))
                    else:
                        ns_name = self.unmap_qname(name)
                        xsd_child = xsd_element.match_child(ns_name)
                        if xsd_child is not None:
                            if xsd_child.type and xsd_child.type.is_list():
                                content.append((ns_name, value))
                            else:
                                content.extend((ns_name, item) for item in value)
                        else:
                            content.extend((ns_name, item) for item in value)

            return ElementData(tag, None, content, attributes, None)
