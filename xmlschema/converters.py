#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains converter classes and definitions.
"""
from __future__ import unicode_literals
from collections import namedtuple
from types import MethodType
import string
import warnings

from .compat import ordered_dict_class, unicode_type
from .exceptions import XMLSchemaValueError
from .namespaces import XSI_NAMESPACE
from .qnames import local_name
from .etree import etree_element, lxml_etree_element, etree_register_namespace, lxml_etree_register_namespace
from xmlschema.namespaces import NamespaceMapper

ElementData = namedtuple('ElementData', ['tag', 'text', 'content', 'attributes'])
"""
Namedtuple for Element data interchange between decoders and converters.
The field *tag* is a string containing the Element's tag, *text* can be `None`
or a string representing the Element's text, *content* can be `None`, a list
containing the Element's children or a dictionary containing element name to
list of element contents for the Element's children (used for unordered input
data), *attributes* can be `None` or a dictionary containing the Element's
attributes.
"""


def raw_xml_encode(value):
    """Encodes a simple value to XML."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (list, tuple)):
        return ' '.join(unicode_type(e) for e in value)
    else:
        return unicode_type(value)


class XMLSchemaConverter(NamespaceMapper):
    """
    Generic XML Schema based converter class. A converter is used to compose
    decoded XML data for an Element into a data structure and to build an Element
    from encoded data structure. There are two methods for interfacing the
    converter with the decoding/encoding process. The method *element_decode*
    accepts ElementData instance, containing the element parts, and returns
    a data structure. The method *element_encode* accepts a data structure
    and returns an ElementData that can be

    :param namespaces: map from namespace prefixes to URI.
    :param dict_class: dictionary class to use for decoded data. Default is `dict`.
    :param list_class: list class to use for decoded data. Default is `list`.
    :param etree_element_class: the class that has to be used to create new XML elements, \
    if not provided uses the ElementTree's Element class.
    :param text_key: is the key to apply to element's decoded text data.
    :param attr_prefix: controls the mapping of XML attributes, to the same name or \
    with a prefix. If `None` the converter ignores attributes.
    :param cdata_prefix: is used for including and prefixing the character data parts \
    of a mixed content, that are labeled with an integer instead of a string. \
    Character data parts are ignored if this argument is `None`.
    :param indent: number of spaces for XML indentation (default is 4).
    :param strip_namespaces: if set to `True` removes namespace declarations from data and \
    namespace information from names, during decoding or encoding. Defaults to `False`.
    :param preserve_root: if set to `True` the root element is preserved, wrapped into a \
    single-item dictionary. Applicable only to default converter and to :class:`ParkerConverter`.
    :param force_dict: if set to `True` complex elements with simple content are decoded \
    with a dictionary also if there are no decoded attributes. Applicable to default converter \
    only. Defaults to `False`.
    :param force_list: if set to `True` child elements are decoded within a list in any case. \
    Applicable to default converter only. Defaults to `False`.

    :ivar dict: dictionary class to use for decoded data.
    :ivar list: list class to use for decoded data.
    :ivar etree_element_class: Element class to use
    :ivar text_key: key for decoded Element text
    :ivar attr_prefix: prefix for attribute names
    :ivar cdata_prefix: prefix for character data parts
    :ivar indent: indentation to use for rebuilding XML trees
    :ivar strip_namespaces: remove namespace information
    :ivar preserve_root: preserve the root element on decoding
    :ivar force_dict: force dictionary for complex elements with simple content
    :ivar force_list: force list for child elements
    """
    # Deprecation from release v1.0.14
    def _unmap_attribute_qname(self, name):
        warnings.warn("the _unmap_attribute_qname method is deprecated and will "
                      "be removed in 1.1 version. Use the unmap_qname() instead, "
                      "providing the attribute group of the XSD element for the "
                      "optional *name_table* argument.",
                      DeprecationWarning, stacklevel=2)
        if name[0] == '{' or ':' not in name:
            return name
        else:
            return self.unmap_qname(name)

    @property
    def lossless(self):
        """The negation of *lossy* property, preserved for backward compatibility."""
        warnings.warn("the lossless property will be removed in 1.1 version, "
                      "use 'not self.lossy' instead", DeprecationWarning, stacklevel=2)
        return not self.lossy

    def __init__(self, namespaces=None, dict_class=None, list_class=None, etree_element_class=None,
                 text_key='$', attr_prefix='@', cdata_prefix=None, indent=4, strip_namespaces=False,
                 preserve_root=False, force_dict=False, force_list=False, **kwargs):
        if etree_element_class is not None and etree_element_class not in (etree_element, lxml_etree_element):
            raise XMLSchemaValueError("%r: unsupported element.")

        self.dict = dict_class or dict
        self.list = list_class or list
        self.etree_element_class = etree_element_class or etree_element
        self.text_key = text_key
        self.attr_prefix = attr_prefix
        self.cdata_prefix = cdata_prefix
        self.indent = indent
        self.strip_namespaces = strip_namespaces
        self.preserve_root = preserve_root
        self.force_dict = force_dict
        self.force_list = force_list

        if self.etree_element_class is etree_element:
            super(XMLSchemaConverter, self).__init__(namespaces, etree_register_namespace)
        else:
            super(XMLSchemaConverter, self).__init__(namespaces, lxml_etree_register_namespace)

    def __setattr__(self, name, value):
        if name in ('attr_prefix', 'text_key', 'cdata_prefix'):
            if value is not None and any(c in string.ascii_letters or c == '_' for c in value):
                raise XMLSchemaValueError('%r cannot includes letters or underscores: %r' % (name, value))
            elif name == 'attr_prefix':
                self.ns_prefix = (value or '') + 'xmlns'
        elif name == 'strip_namespaces':
            if value:
                self.map_qname = MethodType(local_name, self)
                self.unmap_qname = MethodType(lambda x, y=None: local_name(x), self)
            elif getattr(self, 'strip_namespaces', False):
                # Rebuild instance methods only if necessary
                self.map_qname = MethodType(XMLSchemaConverter.map_qname, self)
                self.unmap_qname = MethodType(XMLSchemaConverter.unmap_qname, self)
        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self):
        """The converter ignores some kind of XML data during decoding/encoding."""
        return not self.cdata_prefix or not self.text_key or not self.attr_prefix

    @property
    def losslessly(self):
        """
        The XML data is decoded without loss of quality, neither on data nor on data model
        shape. Only losslessly converters can be always used to encode to an XML data that
        is strictly conformant to the schema.
        """
        return False

    def copy(self, **kwargs):
        return type(self)(
            namespaces=kwargs.get('namespaces', self._namespaces),
            dict_class=kwargs.get('dict_class', self.dict),
            list_class=kwargs.get('list_class', self.list),
            etree_element_class=kwargs.get('etree_element_class'),
            text_key=kwargs.get('text_key', self.text_key),
            attr_prefix=kwargs.get('attr_prefix', self.attr_prefix),
            cdata_prefix=kwargs.get('cdata_prefix', self.cdata_prefix),
            indent=kwargs.get('indent', self.indent),
            strip_namespaces=kwargs.get('strip_namespaces', self.strip_namespaces),
            preserve_root=kwargs.get('preserve_root', self.preserve_root),
            force_dict=kwargs.get('force_dict', self.force_dict),
            force_list=kwargs.get('force_list', self.force_list),
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
                yield '%s%s' % (self.attr_prefix, self.map_qname(name)), value
        else:
            for name, value in attributes:
                yield self.map_qname(name), value

    def map_content(self, content):
        """
        A generator function for converting decoded content to a data structure.
        If the instance has a not-empty map of namespaces registers the mapped URIs
        and prefixes.

        :param content: A sequence or an iterator of tuples with the name of the \
        element, the decoded value and the `XsdElement` instance associated.
        """
        if not content:
            return

        map_qname = self.map_qname
        for name, value, xsd_child in content:
            try:
                if name[0] == '{':
                    yield map_qname(name), value, xsd_child
                else:
                    yield name, value, xsd_child
            except TypeError:
                if self.cdata_prefix is not None:
                    yield '%s%s' % (self.cdata_prefix, name), value, xsd_child

    def etree_element(self, tag, text=None, children=None, attrib=None, level=0):
        """
        Builds an ElementTree's Element using arguments and the element class and
        the indent spacing stored in the converter instance.

        :param tag: the Element tag string.
        :param text: the Element text.
        :param children: the list of Element children/subelements.
        :param attrib: a dictionary with Element attributes.
        :param level: the level related to the encoding process (0 means the root).
        :return: an instance of the Element class setted for the converter instance.
        """
        if type(self.etree_element_class) is type(etree_element):
            if attrib is None:
                elem = self.etree_element_class(tag)
            else:
                elem = self.etree_element_class(tag, self.dict(attrib))
        else:
            nsmap = {prefix if prefix else None: uri for prefix, uri in self._namespaces.items()}
            elem = self.etree_element_class(tag, nsmap=nsmap)
            elem.attrib.update(attrib)

        if children:
            elem.extend(children)
            elem.text = text or '\n' + ' ' * self.indent * (level + 1)
            elem.tail = '\n' + ' ' * self.indent * level
        else:
            elem.text = text
            elem.tail = '\n' + ' ' * self.indent * level

        return elem

    def element_decode(self, data, xsd_element, level=0):
        """
        Converts a decoded element data to a data structure.

        :param data: ElementData instance decoded from an Element node.
        :param xsd_element: the `XsdElement` associated to decoded the data.
        :param level: the level related to the decoding process (0 means the root).
        :return: a data structure containing the decoded data.
        """
        result_dict = self.dict()
        if level == 0 and xsd_element.is_global() and not self.strip_namespaces and self:
            schema_namespaces = set(xsd_element.namespaces.values())
            result_dict.update(
                ('%s:%s' % (self.ns_prefix, k) if k else self.ns_prefix, v)
                for k, v in self._namespaces.items()
                if v in schema_namespaces or v == XSI_NAMESPACE
            )

        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if data.attributes or self.force_dict and not xsd_element.type.is_simple():
                result_dict.update(t for t in self.map_attributes(data.attributes))
                if data.text is not None and data.text != '':
                    result_dict[self.text_key] = data.text
                return result_dict
            else:
                return data.text if data.text != '' else None
        else:
            if data.attributes:
                result_dict.update(t for t in self.map_attributes(data.attributes))

            has_single_group = xsd_element.type.content_type.is_single()
            list_types = list if self.list is list else (self.list, list)
            if data.content:
                for name, value, xsd_child in self.map_content(data.content):
                    try:
                        result = result_dict[name]
                    except KeyError:
                        if xsd_child is None or has_single_group and xsd_child.is_single():
                            result_dict[name] = self.list([value]) if self.force_list else value
                        else:
                            result_dict[name] = self.list([value])
                    else:
                        if not isinstance(result, list_types) or not result:
                            result_dict[name] = self.list([result, value])
                        elif isinstance(result[0], list_types) or not isinstance(value, list_types):
                            result.append(value)
                        else:
                            result_dict[name] = self.list([result, value])

            elif data.text is not None and data.text != '':
                result_dict[self.text_key] = data.text

            if level == 0 and self.preserve_root:
                return self.dict([(self.map_qname(data.tag), result_dict if result_dict else None)])
            return result_dict if result_dict else None

    def element_encode(self, obj, xsd_element, level=0):
        """
        Extracts XML decoded data from a data structure for encoding into an ElementTree.

        :param obj: the decoded object.
        :param xsd_element: the `XsdElement` associated to the decoded data structure.
        :param level: the level related to the encoding process (0 means the root).
        :return: an ElementData instance.
        """
        if level != 0:
            tag = xsd_element.name
        elif not self.preserve_root:
            tag = xsd_element.qualified_name
        else:
            tag = xsd_element.qualified_name
            try:
                obj = obj.get(tag, xsd_element.local_name)
            except (KeyError, AttributeError, TypeError):
                pass

        if not isinstance(obj, (self.dict, dict)):
            if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
                return ElementData(tag, obj, None, {})
            elif xsd_element.type.mixed and not isinstance(obj, list):
                return ElementData(tag, obj, None, {})
            else:
                return ElementData(tag, None, obj, {})

        text_key = self.text_key
        attr_prefix = self.attr_prefix
        ns_prefix = self.ns_prefix
        cdata_prefix = self.cdata_prefix

        text = None
        content = []
        attributes = {}
        for name, value in obj.items():
            if text_key and name == self.text_key:
                text = obj[text_key]
            elif (cdata_prefix and name.startswith(cdata_prefix)) or \
                    name[0].isdigit() and cdata_prefix == '':
                index = int(name[len(cdata_prefix):])
                content.append((index, value))
            elif name == ns_prefix:
                self[''] = value
            elif name.startswith('%s:' % ns_prefix):
                if not self.strip_namespaces:
                    self[name[len(ns_prefix) + 1:]] = value
            elif attr_prefix and name.startswith(attr_prefix):
                attr_name = name[len(attr_prefix):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, (self.list, list)) or not value:
                content.append((self.unmap_qname(name), value))
            elif isinstance(value[0], (self.dict, dict, self.list, list)):
                ns_name = self.unmap_qname(name)
                content.extend((ns_name, item) for item in value)
            else:
                ns_name = self.unmap_qname(name)
                for xsd_child in xsd_element.type.content_type.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type.is_list():
                            content.append((ns_name, value))
                        else:
                            content.extend((ns_name, item) for item in value)
                        break
                else:
                    if attr_prefix == '' and ns_name not in attributes:
                        for key, xsd_attribute in xsd_element.attributes.items():
                            if xsd_attribute.is_matching(ns_name):
                                attributes[key] = value
                                break
                        else:
                            content.append((ns_name, value))
                    else:
                        content.append((ns_name, value))

        return ElementData(tag, text, content, attributes)


class UnorderedConverter(XMLSchemaConverter):
    """
    Same as :class:`XMLSchemaConverter` but :meth:`element_encode` returns
    a dictionary for the content of the element, that can be used directly
    for unordered encoding mode. In this mode the order of the elements in
    the encoded output is based on the model visitor pattern rather than
    the order in which the elements were added to the input dictionary.
    As the order of the input dictionary is not preserved, character data
    between sibling elements are interleaved between tags.
    """
    def element_encode(self, obj, xsd_element, level=0):
        """
        Extracts XML decoded data from a data structure for encoding into an ElementTree.

        :param obj: the decoded object.
        :param xsd_element: the `XsdElement` associated to the decoded data structure.
        :param level: the level related to the encoding process (0 means the root).
        :return: an ElementData instance.
        """
        if level != 0:
            tag = xsd_element.name
        elif not self.preserve_root:
            tag = xsd_element.qualified_name
        else:
            tag = xsd_element.qualified_name
            try:
                obj = obj.get(tag, xsd_element.local_name)
            except (KeyError, AttributeError, TypeError):
                pass

        if not isinstance(obj, (self.dict, dict)):
            if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
                return ElementData(tag, obj, None, {})
            else:
                return ElementData(tag, None, obj, {})

        text_key = self.text_key
        attr_prefix = self.attr_prefix
        ns_prefix = self.ns_prefix
        cdata_prefix = self.cdata_prefix

        text = None
        attributes = {}

        # The unordered encoding mode assumes that the values of this dict will
        # all be lists where each item is the content of a single element. When
        # building content_lu, content which is not a list or lists to be placed
        # into a single element (element has a list content type) must be wrapped
        # in a list to retain that structure. Character data are not wrapped into
        # lists because they because they are divided from the rest of the content
        # into the unordered mode generator function of the ModelVisitor class.
        content_lu = {}

        for name, value in obj.items():
            if text_key and name == text_key:
                text = obj[text_key]
            elif (cdata_prefix and name.startswith(cdata_prefix)) or \
                    name[0].isdigit() and cdata_prefix == '':
                index = int(name[len(cdata_prefix):])
                content_lu[index] = value
            elif name == ns_prefix:
                self[''] = value
            elif name.startswith('%s:' % ns_prefix):
                self[name[len(ns_prefix) + 1:]] = value
            elif attr_prefix and name.startswith(attr_prefix):
                attr_name = name[len(attr_prefix):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, (self.list, list)) or not value:
                content_lu[self.unmap_qname(name)] = [value]
            elif isinstance(value[0], (self.dict, dict, self.list, list)):
                content_lu[self.unmap_qname(name)] = value
            else:
                # `value` is a list but not a list of lists or list of dicts.
                ns_name = self.unmap_qname(name)
                for xsd_child in xsd_element.type.content_type.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type.is_list():
                            content_lu[self.unmap_qname(name)] = [value]
                        else:
                            content_lu[self.unmap_qname(name)] = value
                        break
                else:
                    if attr_prefix == '' and ns_name not in attributes:
                        for xsd_attribute in xsd_element.attributes.values():
                            if xsd_attribute.is_matching(ns_name):
                                attributes[ns_name] = value
                                break
                        else:
                            content_lu[self.unmap_qname(name)] = [value]
                    else:
                        content_lu[self.unmap_qname(name)] = [value]

        return ElementData(tag, text, content_lu, attributes)


class ParkerConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Parker convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-parker-convention
    ref: https://developer.mozilla.org/en-US/docs/Archive/JXON#The_Parker_Convention

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict` for \
    Python 3.6+ or `OrderedDict` for previous versions.
    :param list_class: List class to use for decoded data. Default is `list`.
    :param preserve_root: If `True` the root element will be preserved. For default \
    the Parker convention remove the document root element, returning only the value.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, preserve_root=False, **kwargs):
        kwargs.update(attr_prefix=None, text_key='', cdata_prefix=None)
        super(ParkerConverter, self).__init__(
            namespaces, dict_class or ordered_dict_class, list_class, preserve_root=preserve_root, **kwargs
        )

    def __setattr__(self, name, value):
        if name == 'text_key' and value != '' or name in ('attr_prefix', 'cdata_prefix') and value is not None:
            raise XMLSchemaValueError('Wrong value %r for the attribute %r of a %r.' % (value, name, type(self)))
        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self):
        return True

    def element_decode(self, data, xsd_element, level=0):
        map_qname = self.map_qname
        preserve_root = self.preserve_root
        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if preserve_root:
                return self.dict([(map_qname(data.tag), data.text)])
            else:
                return data.text if data.text != '' else None
        else:
            result_dict = self.dict()
            list_types = list if self.list is list else (self.list, list)
            for name, value, xsd_child in self.map_content(data.content):
                if preserve_root:
                    try:
                        if len(value) == 1:
                            value = value[name]
                    except (TypeError, KeyError):
                        pass

                try:
                    result_dict[name].append(value)
                except KeyError:
                    if isinstance(value, list_types):
                        result_dict[name] = self.list([value])
                    else:
                        result_dict[name] = value
                except AttributeError:
                    result_dict[name] = self.list([result_dict[name], value])

            for k, v in result_dict.items():
                if isinstance(v, (self.list, list)) and len(v) == 1:
                    value = v.pop()
                    v.extend(value)

            if preserve_root:
                return self.dict([(map_qname(data.tag), result_dict)])
            else:
                return result_dict if result_dict else None

    def element_encode(self, obj, xsd_element, level=0):
        if not isinstance(obj, (self.dict, dict)):
            if obj == '':
                obj = None
            if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
                return ElementData(xsd_element.name, obj, None, {})
            else:
                return ElementData(xsd_element.name, None, obj, {})
        else:
            unmap_qname = self.unmap_qname
            if not obj:
                return ElementData(xsd_element.name, None, None, {})
            elif self.preserve_root:
                try:
                    items = obj[self.map_qname(xsd_element.name)]
                except KeyError:
                    return ElementData(xsd_element.name, None, None, {})
            else:
                items = obj

            try:
                content = []
                for name, value in obj.items():
                    ns_name = unmap_qname(name)
                    if not isinstance(value, (self.list, list)) or not value:
                        content.append((ns_name, value))
                    elif any(isinstance(v, (self.list, list)) for v in value):
                        for item in value:
                            content.append((ns_name, item))
                    else:
                        for xsd_child in xsd_element.type.content_type.iter_elements():
                            matched_element = xsd_child.match(ns_name, resolve=True)
                            if matched_element is not None:
                                if matched_element.type.is_list():
                                    content.append((ns_name, value))
                                else:
                                    content.extend((ns_name, item) for item in value)
                                break
                        else:
                            content.extend((ns_name, item) for item in value)

            except AttributeError:
                return ElementData(xsd_element.name, items, None, {})
            else:
                return ElementData(xsd_element.name, None, content, {})


class BadgerFishConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Badgerfish convention.

    ref: http://www.sklar.com/badgerfish/
    ref: http://badgerfish.ning.com/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict` for \
    Python 3.6+ or `OrderedDict` for previous versions.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='@', text_key='$', cdata_prefix='$')
        super(BadgerFishConverter, self).__init__(
            namespaces, dict_class or ordered_dict_class, list_class, **kwargs
        )

    def __setattr__(self, name, value):
        if name == 'text_key' and value != '$' or name == 'attr_prefix' and value != '@' or \
                name == 'cdata_prefix' and value != '$':
            raise XMLSchemaValueError('Wrong value %r for the attribute %r of a %r.' % (value, name, type(self)))
        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self):
        return False

    def element_decode(self, data, xsd_element, level=0):
        dict_class = self.dict

        tag = self.map_qname(data.tag)
        has_local_root = not self and not self.strip_namespaces
        result_dict = dict_class([t for t in self.map_attributes(data.attributes)])
        if has_local_root:
            result_dict['@xmlns'] = dict_class()

        if xsd_element.type.is_simple() or xsd_element.type.has_simple_content():
            if data.text is not None and data.text != '':
                result_dict[self.text_key] = data.text
        else:
            has_single_group = xsd_element.type.content_type.is_single()
            list_types = list if self.list is list else (self.list, list)
            for name, value, xsd_child in self.map_content(data.content):
                try:
                    if '@xmlns' in value:
                        self.transfer(value['@xmlns'])
                        if not value['@xmlns']:
                            del value['@xmlns']
                    elif '@xmlns' in value[name]:
                        self.transfer(value[name]['@xmlns'])
                        if not value[name]['@xmlns']:
                            del value[name]['@xmlns']
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
                    if not isinstance(result, list_types) or not result:
                        result_dict[name] = self.list([result, value])
                    elif isinstance(result[0], list_types) or not isinstance(value, list_types):
                        result.append(value)
                    else:
                        result_dict[name] = self.list([result, value])

        if has_local_root:
            if self:
                result_dict['@xmlns'].update(self)
            else:
                del result_dict['@xmlns']
            return dict_class([(tag, result_dict)])
        else:
            return dict_class([('@xmlns', dict_class(self)), (tag, result_dict)])

    def element_encode(self, obj, xsd_element, level=0):
        map_qname = self.map_qname
        unmap_qname = self.unmap_qname
        tag = xsd_element.qualified_name if level == 0 else xsd_element.name

        if not self.strip_namespaces:
            try:
                self.update(obj['@xmlns'])
            except KeyError:
                pass

        try:
            element_data = obj[map_qname(xsd_element.name)]
        except KeyError:
            element_data = obj

        text_key = self.text_key
        attr_prefix = self.attr_prefix
        cdata_prefix = self.cdata_prefix
        text = None
        content = []
        attributes = {}
        for name, value in element_data.items():
            if name == '@xmlns':
                continue
            elif text_key and name == text_key:
                text = element_data[text_key]
            elif (cdata_prefix and name.startswith(cdata_prefix)) or \
                    name[0].isdigit() and cdata_prefix == '':
                index = int(name[len(cdata_prefix):])
                content.append((index, value))
            elif attr_prefix and name.startswith(attr_prefix):
                attr_name = name[len(attr_prefix):]
                ns_name = self.unmap_qname(attr_name, xsd_element.attributes)
                attributes[ns_name] = value
            elif not isinstance(value, (self.list, list)) or not value:
                content.append((unmap_qname(name), value))
            elif isinstance(value[0], (self.dict, dict, self.list, list)):
                ns_name = unmap_qname(name)
                for item in value:
                    content.append((ns_name, item))
            else:
                ns_name = unmap_qname(name)
                for xsd_child in xsd_element.type.content_type.iter_elements():
                    matched_element = xsd_child.match(ns_name, resolve=True)
                    if matched_element is not None:
                        if matched_element.type.is_list():
                            content.append((ns_name, value))
                        else:
                            content.extend((ns_name, item) for item in value)
                        break
                else:
                    if attr_prefix == '' and ns_name not in attributes:
                        for xsd_attribute in xsd_element.attributes.values():
                            if xsd_attribute.is_matching(ns_name):
                                attributes[ns_name] = value
                                break
                        else:
                            content.append((ns_name, value))
                    else:
                        content.append((ns_name, value))

        return ElementData(tag, text, content, attributes)


class AbderaConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for Abdera convention.

    ref: http://wiki.open311.org/JSON_and_XML_Conversion/#the-abdera-convention
    ref: https://cwiki.apache.org/confluence/display/ABDERA/JSON+Serialization

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict` for \
    Python 3.6+ or `OrderedDict` for previous versions.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='', text_key='', cdata_prefix=None)
        super(AbderaConverter, self).__init__(
            namespaces, dict_class or ordered_dict_class, list_class, **kwargs
        )

    def __setattr__(self, name, value):
        if name in ('text_key', 'attr_prefix') and value != '' or name == 'cdata_prefix' and value is not None:
            raise XMLSchemaValueError('Wrong value %r for the attribute %r of a %r.' % (value, name, type(self)))
        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self):
        return True  # Loss cdata parts

    def element_decode(self, data, xsd_element, level=0):
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
                    if isinstance(value, (self.list, list)) and value:
                        children[name] = self.list([value])
                    else:
                        children[name] = value
                except AttributeError:
                    children[name] = self.list([children[name], value])
            if not children:
                children = data.text if data.text is not None and data.text != '' else None

        if data.attributes:
            if children != []:
                return self.dict([
                    ('attributes', self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])),
                    ('children', self.list([children]) if children is not None else self.list())
                ])
            else:
                return self.dict([
                    ('attributes', self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])),
                ])
        else:
            return children if children is not None else self.list()

    def element_encode(self, obj, xsd_element, level=0):
        tag = xsd_element.qualified_name if level == 0 else xsd_element.name

        if not isinstance(obj, (self.dict, dict)):
            if obj == []:
                obj = None
            return ElementData(tag, obj, None, {})
        else:
            unmap_qname = self.unmap_qname
            attributes = {}
            try:
                attributes.update([(self.unmap_qname(k, xsd_element.attributes), v)
                                   for k, v in obj['attributes'].items()])
            except KeyError:
                children = obj
            else:
                children = obj.get('children', [])

            if isinstance(children, (self.dict, dict)):
                children = [children]
            elif children and not isinstance(children[0], (self.dict, dict)):
                if len(children) > 1:
                    raise XMLSchemaValueError("Wrong format")
                else:
                    return ElementData(tag, children[0], None, attributes)

            content = []
            for child in children:
                for name, value in child.items():
                    if not isinstance(value, (self.list, list)) or not value:
                        content.append((unmap_qname(name), value))
                    elif isinstance(value[0], (self.dict, dict, self.list, list)):
                        ns_name = unmap_qname(name)
                        for item in value:
                            content.append((ns_name, item))
                    else:
                        ns_name = unmap_qname(name)
                        for xsd_child in xsd_element.type.content_type.iter_elements():
                            matched_element = xsd_child.match(ns_name, resolve=True)
                            if matched_element is not None:
                                if matched_element.type.is_list():
                                    content.append((ns_name, value))
                                else:
                                    content.extend((ns_name, item) for item in value)
                                break
                        else:
                            content.append((ns_name, value))

            return ElementData(tag, None, content, attributes)


class JsonMLConverter(XMLSchemaConverter):
    """
    XML Schema based converter class for JsonML (JSON Mark-up Language) convention.

    ref: http://www.jsonml.org/
    ref: https://www.ibm.com/developerworks/library/x-jsonml/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict` for \
    Python 3.6+ or `OrderedDict` for previous versions.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    def __init__(self, namespaces=None, dict_class=None, list_class=None, **kwargs):
        kwargs.update(attr_prefix='', text_key='', cdata_prefix='')
        super(JsonMLConverter, self).__init__(
            namespaces, dict_class or ordered_dict_class, list_class, **kwargs
        )

    def __setattr__(self, name, value):
        if name in ('text_key', 'attr_prefix', 'cdata_prefix') and value != '':
            raise XMLSchemaValueError('Wrong value %r for the attribute %r of a %r.' % (value, name, type(self)))
        super(XMLSchemaConverter, self).__setattr__(name, value)

    @property
    def lossy(self):
        return False

    @property
    def losslessly(self):
        return True

    def element_decode(self, data, xsd_element, level=0):
        result_list = self.list()
        result_list.append(self.map_qname(data.tag))
        if data.text is not None and data.text != '':
            result_list.append(data.text)

        if not xsd_element.type.has_simple_content():
            result_list.extend([
                value if value is not None else self.list([name])
                for name, value, _ in self.map_content(data.content)
            ])

        attributes = self.dict([(k, v) for k, v in self.map_attributes(data.attributes)])
        if level == 0 and xsd_element.is_global() and not self.strip_namespaces and self:
            attributes.update(
                [('xmlns:%s' % k if k else 'xmlns', v) for k, v in self._namespaces.items()]
            )
        if attributes:
            result_list.insert(1, attributes)

        return result_list

    def element_encode(self, obj, xsd_element, level=0):
        unmap_qname = self.unmap_qname
        attributes = {}
        if not isinstance(obj, (self.list, list)) or not obj:
            raise XMLSchemaValueError("Wrong data format, a not empty list required: %r." % obj)

        data_len = len(obj)
        if data_len == 1:
            if not xsd_element.is_matching(unmap_qname(obj[0]), self._namespaces.get('')):
                raise XMLSchemaValueError("Unmatched tag")
            return ElementData(xsd_element.name, None, None, attributes)

        try:
            for k, v in obj[1].items():
                if k == 'xmlns':
                    self[''] = v
                elif k.startswith('xmlns:'):
                    self[k.split('xmlns:')[1]] = v
                else:
                    attributes[self.unmap_qname(k, xsd_element.attributes)] = v
        except AttributeError:
            content_index = 1
        else:
            content_index = 2

        if not xsd_element.is_matching(unmap_qname(obj[0]), self._namespaces.get('')):
            raise XMLSchemaValueError("Unmatched tag")

        if data_len <= content_index:
            return ElementData(xsd_element.name, None, [], attributes)
        elif data_len == content_index + 1 and \
                (xsd_element.type.is_simple() or xsd_element.type.has_simple_content()):
            return ElementData(xsd_element.name, obj[content_index], [], attributes)
        else:
            cdata_num = iter(range(1, data_len))
            list_types = list if self.list is list else (self.list, list)
            content = [
                (unmap_qname(e[0]), e) if isinstance(e, list_types) else (next(cdata_num), e)
                for e in obj[content_index:]
            ]
            return ElementData(xsd_element.name, None, content, attributes)
