# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
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
from collections import OrderedDict, namedtuple
import string

from .exceptions import XMLSchemaValueError
from .namespaces import NamespaceMapper


XSD_VALIDATION_MODES = {'strict', 'lax', 'skip'}
"""
XML Schema validation modes
Ref.: https://www.w3.org/TR/xmlschema11-1/#key-va
"""

# Namedtuple for a generic Element data representation.
ElementData = namedtuple('ElementData', ['tag', 'text', 'content', 'attributes'])


class XMLSchemaConverter(NamespaceMapper):
    """
    Generic XML Schema based converter class. A converter is used to compose
    decoded XML data for an Element into a data structure and to build an Element
    from encoded data structure.

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param text_key: is the key to apply to element's decoded text data.
    :param attr_prefix: controls the mapping of XML attributes, to the same name or \
    with a prefix. If `None` the converter ignores attributes.
    :param cdata_prefix: is used for including and prefixing the CDATA parts of a \
    mixed content, that are labeled with an integer instead of a string. \
    CDATA parts are ignored if this argument is `None`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None,
                 text_key='$', attr_prefix='@', cdata_prefix=None, **kwargs):
        self.dict = dict_class or dict
        self.list = list_class or list
        self.text_key = text_key
        self.attr_prefix = attr_prefix
        self.cdata_prefix = cdata_prefix
        super(XMLSchemaConverter, self).__init__(namespaces)

    def __setattr__(self, name, value):
        if name == ('attr_prefix', 'text_key', 'cdata_prefix') and value is not None:
            if any(c in string.ascii_letters or c == '_' for c in value):
                raise XMLSchemaValueError(
                    '%r cannot include letters or underscores: %r' % (name, value))
        super(NamespaceMapper, self).__setattr__(name, value)

    def copy(self, **kwargs):
        return type(self)(
            namespaces=kwargs.get('namespaces', self.namespaces),
            dict_class=kwargs.get('dict_class', self.dict),
            list_class=kwargs.get('list_class', self.list),
            text_key=kwargs.get('text_key', self.text_key),
            attr_prefix=kwargs.get('attr_prefix', self.attr_prefix),
            cdata_prefix=kwargs.get('cdata_prefix', self.cdata_prefix),
        )

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

    def unmap_attributes(self, attributes):
        if self.attr_prefix is None or not attributes:
            return
        elif self.attr_prefix:
            k = len(self.attr_prefix)
            try:
                for name, value in attributes.items():
                    if name.startswith(self.attr_prefix):
                        yield self.unmap_qname(name[k:]), value
            except AttributeError:
                return
        else:
            try:
                for name, value in attributes.items():
                    yield self.unmap_qname(name), value
            except AttributeError:
                return

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

    def element_decode(self, data, xsd_element):
        """
        Converts a decoded element data to a data structure.

        :param data: Decoded ElementData from an Element node.
        :param xsd_element: The `XsdElement` associated to decoded the data.
        :return: A dictionary-based data structure containing the decoded data.
        """
        result_dict = self.dict([t for t in self.map_attributes(data.attributes)])
        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if result_dict:
                if data.text is not None and data.text != '':
                    result_dict[self.text_key] = data.text
                return result_dict
            else:
                return data.text if data.text != '' else None
        else:
            for name, value, xsd_child in self.map_content(data.content):
                try:
                    result_dict[name].append(value)
                except KeyError:
                    if xsd_child is None or xsd_child.is_single() and xsd_element.type.content_type.is_single():
                        result_dict[name] = value
                    else:
                        result_dict[name] = self.list([value])
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])
            return result_dict if result_dict else None

    def element_encode(self, data, xsd_element, validation='lax'):
        """
        Extracts XML decoded data from a data structure for encoding into an ElementTree.
        Uses the XSD element for recognizing errors.

        :param data: Decoded data structure.
        :param xsd_element: The `XsdElement` associated to the decoded data structure.
        :param validation: The XSD validation mode ('strict'/'lax'/'skip').
        :return: A couple with encoded ElementData and a list of errors.
        """
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation mode argument can be 'strict', 'lax' or 'skip'.")
        attributes = []
        errors = []
        unmap_qname = self.unmap_qname
        text_key = self.text_key
        attr_prefix = self.attr_prefix
        cdata_prefix = self.cdata_prefix

        try:
            text = data[text_key]
        except TypeError:
            # simpleType
            return ElementData(xsd_element.name, data, None, attributes), errors
        except KeyError:
            # complexType with a complex content
            text = None
            content = []
            for name, value in data.items():
                if (cdata_prefix and name.startswith(cdata_prefix)) or \
                                name[0].isdigit() and cdata_prefix == '':
                    content.append((int(name[len(cdata_prefix):]), value))
                elif attr_prefix and name.startswith(attr_prefix):
                    attributes.append((unmap_qname(name[len(attr_prefix):]), value))
                elif attr_prefix == '' and name in xsd_element.attributes:
                    attributes.append((unmap_qname(name), value))
                else:
                    if isinstance(value, (self.list, list)):
                        for obj in value:
                            content.append((unmap_qname(name), obj))
                    else:
                        content.append((unmap_qname(name), value))
        else:
            # complexType with a simple content
            content = None
            for name, value in data.items():
                if name == text_key:
                    continue
                if attr_prefix is not None and name.startswith(attr_prefix):
                    attributes.append((unmap_qname(name[len(attr_prefix):]), value))
                elif validation != 'skip':
                    errors.append(XMLSchemaValueError('unexpected key %r in %r.' % (name, data)))
        return ElementData(xsd_element.name, text, content, attributes), errors


class ParkerConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Parker convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-parker-convention

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `OrderedDict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param preserve_root: If `True` the root element will be preserved. For default \
    the Parker convention remove the document root element, returning only the value.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, preserve_root=False, **kwargs):
        kwargs.update(attr_prefix=None, text_key='', cdata_prefix=None)
        super(ParkerConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, **kwargs
        )
        self.preserve_root = preserve_root

    def copy(self, **kwargs):
        return type(self)(
            namespaces=kwargs.get('namespaces', self.namespaces),
            dict_class=kwargs.get('dict_class', self.dict),
            list_class=kwargs.get('list_class', self.list),
            preserve_root=kwargs.get('preserve_root', self.preserve_root),
        )

    def element_decode(self, data, xsd_element):
        map_qname = self.map_qname
        preserve_root = self.preserve_root
        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if preserve_root:
                return self.dict([(map_qname(data.tag), data.text)])
            else:
                return data.text if data.text != '' else None
        else:
            result_dict = self.dict()
            for name, value, _ in self.map_content(data.content):
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
                return self.dict([(map_qname(data.tag), result_dict)])
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
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='@', text_key='$', cdata_prefix='#')
        super(BadgerFishConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, **kwargs
        )

    def element_decode(self, data, xsd_element):
        self.clear()
        dict_class = self.dict

        tag = self.map_qname(data.tag)
        has_local_root = not len(self)
        result_dict = dict_class([t for t in self.map_attributes(data.attributes)])
        if has_local_root:
            result_dict[u'@xmlns'] = dict_class()

        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if data.text is not None and data.text != '':
                result_dict[self.text_key] = data.text
        else:
            for name, value, xsd_child in self.map_content(data.content):
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
                    if xsd_child is None or xsd_child.is_single():
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
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='', text_key='', cdata_prefix=None)
        super(AbderaConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, **kwargs
        )

    def element_decode(self, data, xsd_element):
        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            children = data.text if data.text is not None and data.text != '' else None
        else:
            children = self.dict()
            for name, value, xsd_child in self.map_content(data.content):
                if value is None:
                    value = self.list()

                try:
                    children[name].append(value)
                except KeyError:
                    if xsd_child is None or xsd_child.is_single():
                        children[name] = value
                    else:
                        children[name] = self.list([value])
                except AttributeError:
                    children[name] = self.list([children[name], value])
            if not children:
                children = None

        if data.attributes:
            if children:
                return self.dict([
                    ('attributes', self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])),
                    ('children', self.list([children]) if children is not None else self.list())
                ])
            else:
                return self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])
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
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='', text_key='', cdata_prefix=None)
        super(JsonMLConverter, self).__init__(
            namespaces, dict_class or OrderedDict, list_class, **kwargs
        )

    def element_decode(self, data, xsd_element):
        self.clear()
        result_list = self.list([self.map_qname(data.tag)])
        element_dict = self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])

        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if data.text is not None and data.text != '':
                result_list.append(data.text)
        else:
            result_list.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        if self:
            element_dict.update([('xmlns:%s' % k if k else 'xmlns', v) for k, v in self.items()])
        if element_dict:
            result_list.insert(1, element_dict)
        return result_list
