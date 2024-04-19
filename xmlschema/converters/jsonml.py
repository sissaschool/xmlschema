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
from typing import TYPE_CHECKING, Any, Optional, List, Dict, Tuple, Type

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..aliases import NamespacesType, BaseXsdType
from .default import ElementData, stackable, XMLSchemaConverter

if TYPE_CHECKING:
    from ..validators import XsdElement


class JsonMLConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for JsonML (JSON Mark-up Language) convention.

    ref: http://www.jsonml.org/
    ref: https://www.ibm.com/developerworks/library/x-jsonml/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    __slots__ = ()

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 **kwargs: Any) -> None:
        kwargs.update(attr_prefix='', text_key='', cdata_prefix='')
        super().__init__(namespaces, dict_class, list_class, **kwargs)

    @property
    def lossy(self) -> bool:
        return False

    @property
    def losslessly(self) -> bool:
        return True

    def get_xmlns_from_data(self, obj: Any) -> Optional[List[Tuple[str, str]]]:
        if not self._use_namespaces or not isinstance(obj, MutableSequence) \
                or len(obj) < 2 or not isinstance(obj[1], MutableMapping):
            return None

        xmlns = []
        for k, v in obj[1].items():
            if k == 'xmlns':
                xmlns.append(('', v))
            elif k.startswith('xmlns:'):
                xmlns.append((k.split('xmlns:')[1], v))

        return xmlns

    @stackable
    def element_decode(self, data: ElementData, xsd_element: 'XsdElement',
                       xsd_type: Optional[BaseXsdType] = None, level: int = 0) -> Any:
        xsd_type = xsd_type or xsd_element.type
        result_list = self.list()
        xmlns = self.get_effective_xmlns(data.xmlns, level, xsd_element)

        result_list.append(self.map_qname(data.tag))

        attributes = self.dict(self.map_attributes(data.attributes))
        if xmlns and self._use_namespaces:
            attributes.update(
                (f'{self.ns_prefix}:{k}' if k else self.ns_prefix, v) for k, v in xmlns
            )
        if attributes:
            result_list.append(attributes)

        if data.text is not None:
            result_list.append(data.text)

        if xsd_type.model_group is not None:
            result_list.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        return result_list

    @stackable
    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        if not isinstance(obj, MutableSequence):
            msg = "The first argument must be a sequence, {} provided"
            raise XMLSchemaTypeError(msg.format(type(obj)))
        elif not obj:
            raise XMLSchemaValueError("The first argument is an empty sequence")

        xmlns = self.set_context(obj, level)

        data_len = len(obj)
        if data_len == 1:
            if not xsd_element.is_matching(self.unmap_qname(obj[0]), self._namespaces.get('')):
                raise XMLSchemaValueError("Unmatched tag")
            return ElementData(xsd_element.name, None, None, {}, None)

        attributes: Dict[str, Any] = {}
        if isinstance(obj[1], MutableMapping):
            content_index = 2
            for k, v in obj[1].items():
                if k != 'xmlns' and not k.startswith('xmlns:'):
                    attributes[self.unmap_qname(k, xsd_element.attributes)] = v
        else:
            content_index = 1

        if not xsd_element.is_matching(self.unmap_qname(obj[0]), self._namespaces.get('')):
            raise XMLSchemaValueError("Unmatched tag")

        if data_len <= content_index:
            return ElementData(xsd_element.name, None, [], attributes, xmlns)
        elif data_len == content_index + 1 and \
                (xsd_element.type.simple_type is not None or not
                 xsd_element.type.content and xsd_element.type.mixed):
            return ElementData(xsd_element.name, obj[content_index], [], attributes, xmlns)
        else:
            cdata_num = iter(range(1, data_len))
            content = [
                (self.unmap_qname(e[0], xmlns=self.get_xmlns_from_data(e)), e)
                if isinstance(e, MutableSequence)
                else (next(cdata_num), e) for e in obj[content_index:]
            ]
            return ElementData(xsd_element.name, None, content, attributes, xmlns)
