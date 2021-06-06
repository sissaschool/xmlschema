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

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from .default import ElementData, XMLSchemaConverter


class ColumnarConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for columnar formats.

    :param namespaces: map from namespace prefixes to URI.
    :param dict_class: dictionary class to use for decoded data. Default is `dict`.
    :param list_class: list class to use for decoded data. Default is `list`.
    :param attr_prefix: used as separator string for renaming the decoded attributes. \
    Can be the empty string (the default) or a single/double underscore.
    """
    __slots__ = ()

    def __init__(self, namespaces=None, dict_class=None, list_class=None,
                 attr_prefix='', **kwargs):
        kwargs.update(text_key=None, cdata_prefix=None)
        super(ColumnarConverter, self).__init__(namespaces, dict_class, list_class,
                                                attr_prefix=attr_prefix, **kwargs)

    @property
    def lossy(self):
        return True  # Loss cdata parts

    def __setattr__(self, name, value):
        if name != 'attr_prefix':
            super(ColumnarConverter, self).__setattr__(name, value)
        elif not isinstance(value, str):
            msg = '{} must be a str, not {}'
            raise XMLSchemaTypeError(msg.format(name, type(value).__name__))
        elif value not in {'', '_', '__'}:
            msg = '{} can be the empty string or a single/double underscore'
            raise XMLSchemaValueError(msg.format(name))
        else:
            super(XMLSchemaConverter, self).__setattr__(name, value)

    def element_decode(self, data, xsd_element, xsd_type=None, level=0):
        xsd_type = xsd_type or xsd_element.type
        if data.attributes:
            pfx = xsd_element.local_name + self.attr_prefix
            result_dict = self.dict((pfx + self.map_qname(k), v) for k, v in data.attributes)
        else:
            result_dict = self.dict()

        if xsd_type.simple_type is not None:
            result_dict[xsd_element.local_name] = data.text or None

        if data.content:
            for name, value, xsd_child in self.map_content(data.content):
                if not value:
                    continue
                elif xsd_child.local_name:
                    name = xsd_child.local_name
                else:
                    name = name[2 + len(xsd_child.namespace):]

                if xsd_child.is_single():
                    if hasattr(xsd_child, 'type') and xsd_child.type.simple_type is not None:
                        for k in value:
                            result_dict[k] = value[k]
                    else:
                        result_dict[name] = value
                else:
                    if hasattr(xsd_child, 'type') and xsd_child.type.simple_type is not None \
                            and not xsd_child.attributes:
                        if len(xsd_element.findall('*')) == 1:
                            try:
                                result_dict.append(list(value.values())[0])
                            except AttributeError:
                                result_dict = self.list(value.values())
                        else:
                            try:
                                result_dict[name].append(list(value.values())[0])
                            except KeyError:
                                result_dict[name] = self.list(value.values())
                            except AttributeError:
                                result_dict[name] = self.list(value.values())
                    else:
                        try:
                            result_dict[name].append(value)
                        except KeyError:
                            result_dict[name] = self.list([value])
                        except AttributeError:
                            result_dict[name] = self.list([value])

        if level == 0:
            return self.dict([(xsd_element.local_name, result_dict)])
        else:
            return result_dict

    def element_encode(self, obj, xsd_element, level=0):
        if level != 0:
            tag = xsd_element.local_name
        else:
            tag = xsd_element.local_name
            try:
                obj = obj[tag]
            except (KeyError, AttributeError, TypeError):
                pass

        if not isinstance(obj, MutableMapping):
            if xsd_element.type.simple_type is not None:
                return ElementData(xsd_element.name, obj, None, {})
            elif xsd_element.type.mixed and not isinstance(obj, MutableSequence):
                return ElementData(xsd_element.name, obj, None, {})
            else:
                return ElementData(xsd_element.name, None, obj, {})

        text = None
        content = []
        attributes = {}
        pfx = tag + self.attr_prefix

        for name, value in obj.items():
            if name == tag:
                text = value
            elif name.startswith(pfx) and len(name) > len(pfx):
                attr_name = name[len(pfx):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, MutableSequence) or not value:
                content.append((self.unmap_qname(name), value))
            elif isinstance(value[0], (MutableMapping, MutableSequence)):
                ns_name = self.unmap_qname(name)
                content.extend((ns_name, item) for item in value)
            else:
                ns_name = self.unmap_qname(name)
                for xsd_child in xsd_element.type.content.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type.is_list():
                            content.append((xsd_child.name, value))
                        else:
                            content.extend((xsd_child.name, item) for item in value)
                        break
                else:
                    content.append((ns_name, value))

        return ElementData(xsd_element.name, text, content, attributes)
