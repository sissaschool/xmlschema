#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from ..exceptions import XMLSchemaValueError
from ..dataobjects import ElementData, DataElement
from .default import XMLSchemaConverter


class DataElementConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for DataElement objects.

    :param namespaces: Map from namespace prefixes to URI.
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
