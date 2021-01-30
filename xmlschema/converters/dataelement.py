#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import MutableSequence

from ..exceptions import XMLSchemaValueError
from .default import ElementData, XMLSchemaConverter


class DataElement(MutableSequence):
    """
    Data Element, an Element like object with decoded data and schema bindings.
    """
    value = None
    tail = None

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

        self.xsd_element = xsd_element
        self._xsd_type = xsd_type

    def __getitem__(self, i):
        return self._children[i]

    def __setitem__(self, i, child):
        self._children[i] = child

    def __delitem__(self, i):
        del self._children[i]

    def __len__(self):
        return len(self._children)

    def insert(self, i, child):
        self._children.insert(i, child)

    def __repr__(self):
        return '%s(tag=%r)' % (self.__class__.__name__, self.tag)

    def __iter__(self):
        yield from self._children

    @property
    def text(self):
        if self.value is None:
            return
        elif self.value is True:
            return 'true'
        elif self.value is False:
            return 'false'
        else:
            return str(self.value)

    @property
    def xsd_type(self):
        if self._xsd_type is not None:
            return self._xsd_type
        elif self.xsd_element is not None:
            return self.xsd_element.type

    @xsd_type.setter
    def xsd_type(self, xsd_type):
        self._xsd_type = xsd_type

    def encode(self, **kwargs):
        if self.xsd_element is not None:
            return self.xsd_element.encode(self, **kwargs)
        raise XMLSchemaValueError("{!r} has no schema bindings".format(self))
        # TODO: handle _xsd_type is not xml_element.type

    to_etree = encode

    def iter(self, tag=None):
        if tag is None:
            tag = '*'
        if tag == '*' or tag == self.tag:
            yield self
        for child in self._children:
            yield from child.iter(tag)


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
        xsd_type = xsd_type or xsd_element.type
        data_element = DataElement(data.tag, value=data.text, nsmap=self.namespaces,
                                   xsd_element=xsd_element, xsd_type=xsd_type)

        if xsd_type.model_group is not None:
            data_element.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        data_element.attrib.update((k, v) for k, v in self.map_attributes(data.attributes))
        if level == 0 and xsd_element.is_global() and not self.strip_namespaces and self:
            data_element.attrib.update(
                ('xmlns:%s' % k if k else 'xmlns', v) for k, v in self._namespaces.items()
            )
        return data_element

    def element_encode(self, data_element, xsd_element, level=0):
        attributes = {}
        if not xsd_element.is_matching(
                self.unmap_qname(data_element.tag), self._namespaces.get('')):
            raise XMLSchemaValueError("Unmatched tag")

        data_len = len(data_element)
        if not data_len and not data_element.attrib:
            return ElementData(xsd_element.name, None, None, attributes)

        for k, v in data_element.attrib.items():
            if k == 'xmlns':
                self[''] = v
            elif k.startswith('xmlns:'):
                self[k.split('xmlns:')[1]] = v
            else:
                attributes[self.unmap_qname(k, xsd_element.attributes)] = v

        if not data_len:
            return ElementData(xsd_element.name, None, [], attributes)

        elif data_len == 1 and \
                (xsd_element.type.simple_type is not None or not
                 xsd_element.type.content and xsd_element.type.mixed):
            return ElementData(xsd_element.name, data_element[0], [], attributes)
        else:
            cdata_num = iter(range(1, data_len))
            content = [
                (self.unmap_qname(e.tag), e) if isinstance(e, self.data_element_class)
                else (next(cdata_num), e) for e in data_element
            ]
            return ElementData(xsd_element.name, None, content, attributes)
