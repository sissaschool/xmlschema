# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains classes for converting XML elements with XMLSchema support.
"""
from collections import OrderedDict

from .core import etree_element
from .utils import NamespaceMapper


class XMLSchemaConverter(NamespaceMapper):
    """
    Generic XML Schema based converter class. A converter is used to compose
    decoded XML data for an Element into a data structure and to build an Element
    from encoded data structure.

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param element_class: Element class to use when encode data to an ElementTree \
    structure. Default is `xml.etree.ElementTree.Element`.
    :param kwargs: Contains other optional converter parameters. The argument \
    `attr_prefix` controls the mapping of XML attributes, to the same name or \
    with a prefix. If `None` the converter ignores attributes. \
    The argument `cdata_prefix` is used for including and prefixing the CDATA \
    parts of a mixed content, that are labeled with an integer instead of a string. \
    If `None` the CDATA parts are ignored by the converter. \
    The argument 'content_key' is the key to apply to element's decoded text data \
    (simple content elements).
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, element_class=None, **kwargs):
        self.dict = dict_class or dict
        self.list = list_class or list
        self.etree_element = element_class or etree_element
        self.attr_prefix = kwargs.get('attr_prefix', '@')
        self.content_key = kwargs.get('content_key', '$')
        self.cdata_prefix = kwargs.get('cdata_prefix')
        super(XMLSchemaConverter, self).__init__(namespaces)

    def __setattr__(self, name, value):
        super(XMLSchemaConverter, self).__setattr__(name, value)

    def copy(self):
        return type(self)(self.namespaces, self.dict, self.list, self.etree_element)

    def map_attributes(self, attributes):
        """
        Creates an iterator for converting decoded attributes to a data structure with
        appropriate prefixes. If the instance has a not-empty map of namespaces registers
        the mapped URIs and prefixes.

        :param attributes: A sequence or an iterator of couples with the name of \
        the attribute and the decoded value. Default is `None` (for `simpleType` \
        elements, that don't have attributes).
        """
        if self.attr_prefix is None or not attributes:
            return
        elif self.attr_prefix:
            for name, value in attributes:
                yield u'%s%s' % (self.attr_prefix, self.map_qname(name)), value
        else:
            for name, value in attributes:
                yield self.map_qname(name), value

    def map_content(self, content):
        """
        Creates an iterator for converting decoded content to a data structure.
        If the instance has a not-empty map of namespaces registers the mapped URIs
        and prefixes.

        :param content: A sequence or an iterator of tuples with the name of the \
        element, the decoded value and the `XsdElement` instance associated.
        """
        map_qname = self.map_qname
        for name, value, xsd_child in content:
            try:
                if name[0] == '{':
                    yield map_qname(name), value, xsd_child
                else:
                    yield name, value, xsd_child
            except TypeError:
                if self.cdata_prefix is not None:
                    yield u'%s%s' % (self.cdata_prefix, name), value, xsd_child

    def element_decode(self, elem, xsd_element, content, attributes=None):
        """
        Converts a decoded element to a data structure.

        :param elem: The `Element` object that has been decoded.
        :param xsd_element: The `XsdElement` used to decode the *elem* object.
        :param content: A sequence or an iterator of tuples with the name of the \
        element, the decoded value and the `XsdElement` instance associated.
        :param attributes: A sequence or an iterator of couples with the name of \
        the attribute and the decoded value. Default is `None` (for `simpleType` \
        elements, that don't have attributes).
        :return: A data structure.
        """
        result_dict = self.dict([t for t in self.map_attributes(attributes)])
        if xsd_element.type.is_simple():
            if result_dict:
                if content is not None and content != '':
                    result_dict[self.content_key] = content
                return result_dict
            else:
                return content if content != '' else None
        else:
            for name, value, xsd_child in self.map_content(content):
                try:
                    result_dict[name].append(value)
                except KeyError:
                    if xsd_child is not None and xsd_child.is_single():
                        result_dict[name] = value
                    else:
                        result_dict[name] = self.list([value])
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])
            return result_dict if result_dict else None


class ParkerConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Parker convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-parker-convention

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `OrderedDict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param element_class: Element class to use when encode data to an ElementTree \
    structure. Default is `xml.etree.ElementTree.Element`.
    :param preserve_root: If `True` the root element will be preserved. For default \
    the Parker convention remove the document root element, returning only the value.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None,
                 element_class=None, preserve_root=False):
        super(ParkerConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, element_class,
            attr_prefix=None, content_key='', cdata_prefix=None)
        self.preserve_root = preserve_root

    def copy(self):
        return type(self)(self.namespaces, self.dict, self.list,
                          self.etree_element, self.preserve_root)

    def element_decode(self, elem, xsd_element, content, attributes=None):
        map_qname = self.map_qname
        preserve_root = self.preserve_root
        if xsd_element.type.is_simple():
            if preserve_root:
                return self.dict([(map_qname(elem.tag), content)])
            else:
                return content if content != '' else None
        else:
            result_dict = self.dict()
            for name, value, _ in self.map_content(content):
                if preserve_root:
                    try:
                        if len(value) == 1:
                            value = value[name]
                    except (TypeError, KeyError):
                        pass

                try:
                    result_dict[name].append(value)
                except KeyError:
                    result_dict[name] = value
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])
            if preserve_root:
                return self.dict([(map_qname(elem.tag), result_dict)])
            else:
                return result_dict if result_dict else None


class BadgerFishConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Badgerfish convention.

    ref: http://www.sklar.com/badgerfish/
    ref: http://badgerfish.ning.com/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `OrderedDict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param element_class: Element class to use when encode data to an ElementTree \
    structure. Default is `xml.etree.ElementTree.Element`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, element_class=None):
        super(BadgerFishConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, element_class,
            attr_prefix='@', content_key='$', cdata_prefix='#'
        )

    def element_decode(self, elem, xsd_element, content, attributes=None):
        self.clear()
        dict_class = self.dict

        tag = self.map_qname(elem.tag)
        has_local_root = not len(self)
        result_dict = dict_class([t for t in self.map_attributes(attributes)])
        if has_local_root:
            result_dict[u'@xmlns'] = dict_class()

        if xsd_element.type.is_simple():
            if content is not None and content != '':
                result_dict[self.content_key] = content
        else:
            for name, value, xsd_child in self.map_content(content):
                try:
                    if u'@xmlns' in value:
                        self.transfer(value[u'@xmlns'])
                        if not value[u'@xmlns']:
                            del value[u'@xmlns']
                    elif u'@xmlns' in value[name]:
                        self.transfer(value[name][u'@xmlns'])
                        if not value[name][u'@xmlns']:
                            del value[name][u'@xmlns']
                    if len(value) == 1:
                        value = value[name]
                except (TypeError, KeyError):
                    pass

                if value is None:
                    value = self.dict()

                try:
                    result_dict[name].append(value)
                except KeyError:
                    if xsd_child.is_single():
                        result_dict[name] = value
                    else:
                        result_dict[name] = self.list([value])
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])

        if has_local_root:
            if self:
                result_dict[u'@xmlns'].update(self)
            else:
                del result_dict[u'@xmlns']
            return dict_class([(tag, result_dict)])
        else:
            return dict_class([('@xmlns', dict_class(self)), (tag, result_dict)])


class AbderaConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Abdera convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-abdera-convention
    ref: https://cwiki.apache.org/confluence/display/ABDERA/JSON+Serialization

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `OrderedDict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param element_class: Element class to use when encode data to an ElementTree \
    structure. Default is `xml.etree.ElementTree.Element`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, element_class=None):
        super(AbderaConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, element_class,
            attr_prefix='', content_key='', cdata_prefix=None
        )

    def element_decode(self, elem, xsd_element, content, attributes=None):
        if xsd_element.type.is_simple():
            children = content if content is not None and content != '' else None
        else:
            children = self.dict()
            for name, value, xsd_child in self.map_content(content):
                if value is None:
                    value = self.list()

                try:
                    children[name].append(value)
                except KeyError:
                    if xsd_child.is_single():
                        children[name] = value
                    else:
                        children[name] = self.list([value])
                except AttributeError:
                    children[name] = self.list([children[name], value])
            if not children:
                children = None

        if attributes:
            if children:
                return self.dict([
                    ('attributes', self.dict([(k, v) for k, v in self.map_attributes(attributes)])),
                    ('children', self.list([children]) if children is not None else self.list())
                ])
            else:
                return self.dict([(k, v) for k, v in self.map_attributes(attributes)])
        else:
            return children if children is not None else self.list()


class JsonMLConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for JsonML (JSON Mark-up Language) convention.

    ref: http://www.jsonml.org/
    ref: https://www.ibm.com/developerworks/library/x-jsonml/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `OrderedDict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param element_class: Element class to use when encode data to an ElementTree \
    structure. Default is `xml.etree.ElementTree.Element`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, element_class=None):
        super(JsonMLConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, element_class,
            attr_prefix='', content_key='', cdata_prefix=None
        )

    def element_decode(self, elem, xsd_element, content, attributes=None):
        self.clear()
        result_list = self.list([self.map_qname(elem.tag)])
        element_dict = self.dict([(k, v) for k, v in self.map_attributes(attributes)])

        if xsd_element.type.is_simple():
            if content is not None and content != '':
                result_list.append(content)
        else:
            result_list.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(content)
            ])

        if self:
            element_dict.update([('xmlns:%s' % k if k else 'xmlns', v) for k, v in self.items()])
        if element_dict:
            result_list.insert(1, element_dict)
        return result_list
