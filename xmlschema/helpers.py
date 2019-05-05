# -*- coding: utf-8 -*-
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
This module contains various helper functions and classes.
"""
import re

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaKeyError
from .qnames import XSD_ANNOTATION

XSD_FINAL_ATTRIBUTE_VALUES = {'restriction', 'extension', 'list', 'union'}
NAMESPACE_PATTERN = re.compile(r'{([^}]*)}')


def get_namespace(name):
    try:
        return NAMESPACE_PATTERN.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


def get_qname(uri, name):
    """
    Returns an expanded QName from URI and local part. If any argument has boolean value
    `False` or if the name is already an expanded QName, returns the *name* argument.

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
    Return the local part of an expanded QName. If the name is `None` or empty
    returns the *name* argument.

    :param qname: an expanded QName or a local name.
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


def get_xsd_derivation_attribute(elem, attribute, values=None):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: the Element instance.
    :param attribute: the attribute name.
    :param values: sequence of admitted values when the attribute value is not '#all'.
    :return: a string.
    """
    value = elem.get(attribute)
    if value is None:
        return ''

    if values is None:
        values = XSD_FINAL_ATTRIBUTE_VALUES

    items = value.split()
    if len(items) == 1 and items[0] == '#all':
        return ' '.join(values)
    elif not all([s in values for s in items]):
        raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute))
    return value


def get_xsd_form_attribute(elem, attribute):
    """
    Get an XSD form attribute, checking the value. If the attribute is missing returns `None`

    :param elem: the Element instance.
    :param attribute: the attribute name (maybe 'form', or 'elementFormDefault' or 'attributeFormDefault').
    :return: a string.
    """
    value = elem.get(attribute)
    if value is None:
        return
    elif value not in ('qualified', 'unqualified'):
        raise XMLSchemaValueError(
            "wrong value %r for attribute %r, it must be 'qualified' or 'unqualified'." % (value, attribute)
        )
    return value


class ParticleCounter(object):
    """
    An helper class for counting total min/max occurrences of XSD particles.
    """
    def __init__(self):
        self.min_occurs = self.max_occurs = 0

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.min_occurs, self.max_occurs)

    def __add__(self, other):
        self.min_occurs += other.min_occurs
        if self.max_occurs is not None:
            if other.max_occurs is None:
                self.max_occurs = None
            else:
                self.max_occurs += other.max_occurs
        return self

    def __mul__(self, other):
        self.min_occurs *= other.min_occurs
        if self.max_occurs is None:
            if other.max_occurs == 0:
                self.max_occurs = 0
        elif other.max_occurs is None:
            if self.max_occurs != 0:
                self.max_occurs = None
        else:
            self.max_occurs *= other.max_occurs
        return self

    def reset(self):
        self.min_occurs = self.max_occurs = 0
