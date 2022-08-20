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
from typing import TYPE_CHECKING, cast, Any, Dict, Union

from .default import ElementData, XMLSchemaConverter

if TYPE_CHECKING:
    from ..validators import XsdElement


class UnorderedConverter(XMLSchemaConverter):
    """
    Same as :class:`XMLSchemaConverter` but :meth:`XMLSchemaConverter.element_encode`
    returns a dictionary for the content of the element, that can be used directly
    for unordered encoding mode. In this mode the order of the elements in
    the encoded output is based on the model visitor pattern rather than
    the order in which the elements were added to the input dictionary.
    As the order of the input dictionary is not preserved, character data
    between sibling elements are interleaved between tags.
    """
    __slots__ = ()

    def element_encode(self, obj: Any, xsd_element: 'XsdElement', level: int = 0) -> ElementData:
        """
        Extracts XML decoded data from a data structure for encoding into an ElementTree.

        :param obj: the decoded object.
        :param xsd_element: the `XsdElement` associated to the decoded data structure.
        :param level: the level related to the encoding process (0 means the root).
        :return: an ElementData instance.
        """
        if level:
            tag = xsd_element.name
        else:
            tag = xsd_element.qualified_name
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
        attributes = {}

        # The unordered encoding mode assumes that the values of this dict will
        # all be lists where each item is the content of a single element. When
        # building content_lu, content which is not a list or lists to be placed
        # into a single element (element has a list content type) must be wrapped
        # in a list to retain that structure. Character data are not wrapped into
        # lists because they because they are divided from the rest of the content
        # into the unordered mode generator function of the ModelVisitor class.
        content_lu: Dict[Union[int, str], Any] = {}

        for name, value in obj.items():
            if name == self.text_key:
                text = value
            elif self.cdata_prefix is not None and \
                    name.startswith(self.cdata_prefix) and \
                    name[len(self.cdata_prefix):].isdigit():
                index = int(name[len(self.cdata_prefix):])
                content_lu[index] = value
            elif name == self.ns_prefix:
                self[''] = value
            elif name.startswith(f'{self.ns_prefix}:'):
                self[name[len(self.ns_prefix) + 1:]] = value
            elif self.attr_prefix and \
                    name.startswith(self.attr_prefix) and \
                    name != self.attr_prefix:
                attr_name = name[len(self.attr_prefix):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, MutableSequence) or not value:
                content_lu[self.unmap_qname(name)] = [value]
            elif isinstance(value[0], (MutableMapping, MutableSequence)):
                content_lu[self.unmap_qname(name)] = value
            else:
                xsd_group = xsd_element.type.model_group
                if xsd_group is None:
                    xsd_group = xsd_element.any_type.model_group
                    assert xsd_group is not None

                # `value` is a list but not a list of lists or list of dicts.
                ns_name = self.unmap_qname(name)
                for xsd_child in xsd_group.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type and matched_element.type.is_list():
                            content_lu[self.unmap_qname(name)] = [value]
                        else:
                            content_lu[self.unmap_qname(name)] = value
                        break
                else:
                    if self.attr_prefix == '' and ns_name not in attributes:
                        for xsd_attribute in xsd_element.attributes.values():
                            if xsd_attribute.is_matching(ns_name):
                                attributes[ns_name] = value
                                break
                        else:
                            content_lu[self.unmap_qname(name)] = [value]
                    else:
                        content_lu[self.unmap_qname(name)] = [value]

        return ElementData(tag, text, content_lu, attributes)
