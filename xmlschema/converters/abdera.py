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
        super(AbderaConverter, self).__init__(
            namespaces, dict_class, list_class, **kwargs
        )

    @property
    def lossy(self) -> bool:
        return True  # Loss cdata parts

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

        if data.attributes:
            if children != []:
                return self.dict([
                    ('attributes',
                     self.dict((k, v) for k, v in self.map_attributes(data.attributes))),
                    ('children',
                     self.list([children]) if children is not None else self.list())
                ])
            else:
                return self.dict([
                    ('attributes',
                     self.dict((k, v) for k, v in self.map_attributes(data.attributes))),
                ])
        else:
            return children if children is not None else self.list()

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        tag = xsd_element.qualified_name if level == 0 else xsd_element.name

        if not isinstance(obj, MutableMapping):
            if obj == []:
                obj = None
            return ElementData(tag, obj, None, {})
        else:
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
                    return ElementData(tag, children[0], None, attributes)

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

            return ElementData(tag, None, content, attributes)
