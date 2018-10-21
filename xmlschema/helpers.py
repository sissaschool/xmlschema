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
This module contains various helper functions for XML/XSD processing and parsing.
"""
import re

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaKeyError
from .qnames import XSD_ANNOTATION


NAMESPACE_PATTERN = re.compile(r'{([^}]*)}')
FRACTION_DIGITS_PATTERN = re.compile(r'\.(\d+)$')
ISO_TIMEZONE_PATTERN = re.compile(r'(Z|[+-](?:(?:0[0-9]|1[0-3]):[0-5][0-9]|14:00))$')
DURATION_PATTERN = re.compile(r'^(-)?P(?=(\d|T))(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$')
DAY_TIME_DURATION_PATTERN = re.compile(r'^[^YM]*(T.*)?$')
YEAR_MONTH_DURATION_PATTERN = re.compile(r'^[^DT]*$')
HEX_BINARY_PATTERN = re.compile(r'^[0-9a-fA-F]+$')
NOT_BASE64_BINARY_PATTERN = re.compile(r'[^0-9a-zA-z+/= \t\n]')


def get_namespace(name):
    try:
        return NAMESPACE_PATTERN.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


def get_qname(uri, name):
    """
    Returns a fully qualified name from URI and local part. If any argument has boolean value
    `False` or if the name is already a fully qualified name, returns the *name* argument.

    :param uri: namespace URI
    :param name: local or qualified name
    :return: string or the name argument
    """
    if not uri or not name or name[0] in ('{', '.', '/', '['):
        return name
    else:
        return '{%s}%s' % (uri, name)


def local_name(qname):
    """
    Return the local part of a qualified name. If the name is `None` or empty
    returns the *name* argument.

    :param qname: QName or universal name formatted string, or `None`.
    """
    try:
        if qname[0] != '{':
            return qname
        return qname[qname.rindex('}') + 1:]
    except IndexError:
        return ''
    except ValueError:
        raise XMLSchemaValueError("wrong format for a universal name! %r" % qname)
    except TypeError:
        if qname is None:
            return qname
        raise XMLSchemaTypeError("required a string-like object or None! %r" % qname)


def prefixed_to_qname(name, namespaces):
    """
    Transforms a prefixed name into a fully qualified name using a namespace map. Returns
    the *name* argument if it's not a prefixed name or if it has boolean value `False`.

    :param name: a local name or a prefixed name or a fully qualified name or `None`.
    :param namespaces: a map from prefixes to namespace URIs.
    :return: string with a FQN or a local name or the name argument.
    """
    if not name or name[0] == '{':
        return name

    try:
        prefix, name = name.split(':')
    except ValueError:
        if ':' in name:
            raise XMLSchemaValueError("wrong format for reference name %r" % name)
        try:
            uri = namespaces['']
        except KeyError:
            return name
        else:
            return '{%s}%s' % (uri, name) if uri else name
    else:
        if not prefix or not name:
            raise XMLSchemaValueError("wrong format for reference name %r" % name)
        try:
            uri = namespaces[prefix]
        except KeyError:
            raise XMLSchemaValueError("prefix %r not found in namespace map" % prefix)
        else:
            return '{%s}%s' % (uri, name) if uri else name


def qname_to_prefixed(qname, namespaces):
    """
    Transforms a fully qualified name into a prefixed name using a namespace map. Returns the
    *qname* argument if it's not a fully qualified name or if it has boolean value `False`.

    :param qname: a fully qualified name or a local name.
    :param namespaces: a map from prefixes to namespace URIs.
    :return: string with a prefixed or local reference.
    """
    if not qname:
        return qname

    namespace = get_namespace(qname)
    for prefix, uri in sorted(filter(lambda x: x[1] == namespace, namespaces.items()), reverse=True):
        if not uri:
            return '%s:%s' % (prefix, qname) if prefix else qname
        elif prefix:
            return qname.replace('{%s}' % uri, '%s:' % prefix)
        else:
            return qname.replace('{%s}' % uri, '')
    else:
        return qname


def get_xsd_annotation(elem):
    """
    Returns the annotation of an XSD component.

    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation, `None` if \
    the XSD information item doesn't have an annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION else None
    except (TypeError, IndexError):
        return


def iter_xsd_components(elem, start=0):
    """
    Returns an iterator for XSD child components, excluding the annotation.

    :param elem: the parent Element.
    :param start: the start child component to yield, the optional annotation is not counted. \
    With the default value 0 starts from the first component.
    """
    counter = 0
    for child in elem:
        if child.tag == XSD_ANNOTATION:
            if counter > 0:
                raise XMLSchemaValueError("XSD annotation not allowed after the first position.")
        else:
            if start > 0:
                start -= 1
            else:
                yield child
            counter += 1


def has_xsd_components(elem, start=0):
    try:
        next(iter_xsd_components(elem, start))
    except StopIteration:
        return False
    else:
        return True


def get_xsd_component(elem, required=True, strict=True):
    """
    Returns the first XSD component child, excluding the annotation.

    :param elem: the parent Element.
    :param required: if `True`, that is the default, raises a *ValueError* if there \
    is not any component; with `False` in those cases `None` is returned.
    :param strict: raises a *ValueError* if there is more than one component.
    """
    components_iterator = iter_xsd_components(elem)
    try:
        xsd_component = next(components_iterator)
    except StopIteration:
        if required:
            raise XMLSchemaValueError("missing XSD component")
        return None
    else:
        if not strict:
            return xsd_component
        try:
            next(components_iterator)
        except StopIteration:
            return xsd_component
        else:
            raise XMLSchemaValueError("too many XSD components")


def get_xml_bool_attribute(elem, attribute, default=None):
    """
    Get an XML boolean attribute.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param default: default value, accepted values are `True` or `False`.
    :return: `True` or `False`.
    """
    value = elem.get(attribute, default)
    if value is None:
        raise XMLSchemaKeyError(attribute)
    elif value in ('true', '1') or value is True:
        return True
    elif value in ('false', '0') or value is False:
        return False
    else:
        raise XMLSchemaTypeError("an XML boolean value is required for attribute %r" % attribute)


def get_xsd_derivation_attribute(elem, attribute, values):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param values: sequence of admitted values when the attribute value is not '#all'.
    :return: a string.
    """
    value = elem.get(attribute, '')
    items = value.split()
    if len(items) == 1 and items[0] == '#all':
        return ' '.join(values)
    elif not all([s in values for s in items]):
        raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute))
    return value


def get_xpath_default_namespace(elem, default_namespace, target_namespace, default=None):
    """
    Get the xpathDefaultNamespace attribute value for alternative, assert, assertion, selector
    and field XSD 1.1 declarations, checking if the value is conforming to the specification.
    """
    value = elem.get('xpathDefaultNamespace')
    if value is None:
        return default

    value = value.strip()
    if value == '##local':
        return ''
    elif value == '##defaultNamespace':
        return default_namespace
    elif value == '##targetNamespace':
        return target_namespace
    elif len(value.split()) == 1:
        return value
    else:
        admitted_values = ('##defaultNamespace', '##targetNamespace', '##local')
        msg = "wrong value %r for 'xpathDefaultNamespace' attribute, can be (anyURI | %s)."
        raise XMLSchemaValueError(msg % (value, ' | '.join(admitted_values)))
