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
This module contains functions for manipulating fully qualified names and XML Schema tags.
"""
from .core import XML_NAMESPACE_PATH, XSD_NAMESPACE_PATH, XSI_NAMESPACE_PATH
from .utils import get_namespace
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError


#
# Functions for handling fully qualified names
def get_qname(uri, name):
    """
    Returns a fully qualified Name from URI and local part. If the URI is empty
    or None, or if the name is already in QName format, returns the 'name' argument.

    :param uri: namespace URI
    :param name: local name/tag
    :return: string
    """
    if uri and name[0] not in ('{', '.', '/', '['):
        return u"{%s}%s" % (uri, name)
    else:
        return name


def local_name(qname):
    """
    Return the local part of a QName.

    :param qname: QName or universal name formatted string.
    """
    try:
        if qname[0] != '{':
            return qname
        return qname[qname.rindex('}') + 1:]
    except ValueError:
        raise XMLSchemaValueError("wrong format for a universal name! %r" % qname)
    except TypeError:
        if qname is None:
            return qname
        raise XMLSchemaTypeError("required a string-like object or None! %r" % qname)


def xsd_qname(name):
    """
    Builds a QName for XSD namespace from a local name.

    :param name: local name/tag
    :return: fully qualified name for XSD namespace
    """
    if name[0] != '{':
        return u"{%s}%s" % (XSD_NAMESPACE_PATH, name)
    elif not name.startswith('{%s}' % XSD_NAMESPACE_PATH):
        raise XMLSchemaValueError("%r is not a name of the XSD namespace" % name)
    else:
        return name


def reference_to_qname(ref, namespaces):
    """
    Transforms a reference into a fully qualified name using a namespace map.
    
    :param ref: a local name, a prefixed name or a fully qualified name.
    :param namespaces: Dictionary with the map from prefixes to namespace URIs.
    :return: String with a FQN or a local name.
    """
    if ref and ref[0] == '{':
        return ref  # the argument is already a QName

    try:
        prefix, name = ref.split(':')
    except ValueError:
        if ':' in ref:
            raise XMLSchemaValueError("wrong format for reference name %r" % ref)
        return ref
    else:
        try:
            return u'{%s}%s' % (namespaces[prefix], name)
        except KeyError:
            raise XMLSchemaValueError("prefix %r not found in namespace map" % prefix)


def qname_to_prefixed(qname, namespaces):
    """
    Transforms a fully qualified name into a prefixed reference using a namespace map.
    
    :param qname: a fully qualified name or a local name.
    :param namespaces: Dictionary with the map from prefixes to namespace URIs.
    :return: String with a prefixed or local reference.
    """
    qname_uri = get_namespace(qname)
    for prefix, uri in namespaces.items():
        if uri != qname_uri:
            continue
        if prefix:
            return qname.replace(u'{%s}' % uri, u'%s:' % prefix)
        else:
            return qname.replace(u'{%s}' % uri, '')
    return qname


def split_to_prefixed(qname, namespaces):
    """
    Transforms a fully qualified name into a prefixed reference using
    a namespace map. Returns also the qname's URI and matched prefix.

    :param qname: a fully qualified name or a local name.
    :param namespaces: Dictionary with the map from prefixes to namespace URIs.
    :return: A prefixed FQN or local reference, a prefix and an URI. Prefix and URI
    are None if the namespace isn't in the `namespaces` map.
    """
    qname_uri = get_namespace(qname)
    for prefix, uri in namespaces.items():
        if uri != qname_uri:
            continue
        if prefix:
            return qname.replace(u'{%s}' % uri, u'%s:' % prefix), prefix, uri
        else:
            return qname.replace(u'{%s}' % uri, ''), prefix, uri
    return qname, None, None


def split_qname(qname):
    """
    Splits a universal name format (QName) into namespace URI and local part.

    :param qname: QName or universal name formatted string.
    :return: A couple with namespace URI and the local part. Namespace URI is None \
    if there is only the local part.
    """
    if qname[0] == '{':
        try:
            return qname[1:].split('}')
        except ValueError:
            raise XMLSchemaValueError("wrong format for a universal name! %r" % qname)
    return None, qname


def split_reference(ref, namespaces):
    """
    Processes a reference name using namespaces information. A reference
    is a local name or a name with a namespace prefix (e.g. "xs:string").
    A couple with fully qualified name and namespace is returned.
    If no namespace association is possible returns a local name and None
    when the reference is only a local name or raise a ValueError otherwise.

    :param ref: Reference or fully qualified name (QName).
    :param namespaces: Dictionary that maps the namespace prefix into URI.
    :return: A couple with qname and namespace.
    """
    if ref and ref[0] == '{':
        return ref, ref[1:].split('}')[0] if ref[0] == '{' else ''

    try:
        prefix, name = ref.split(":")
    except ValueError:
        try:
            uri = namespaces['']
        except KeyError:
            return ref, ''
        else:
            return u"{%s}%s" % (uri, ref) if uri else ref, uri
    else:
        try:
            uri = namespaces[prefix]
        except KeyError as err:
            raise XMLSchemaValueError("unknown namespace prefix %s for reference %r" % (err, ref))
        else:
            return u"{%s}%s" % (uri, name) if uri else name, uri


#
# XML Schema fully qualified names
XSD_SCHEMA_TAG = xsd_qname('schema')

# Annotations
XSD_ANNOTATION_TAG = xsd_qname('annotation')
XSD_APPINFO_TAG = xsd_qname('appinfo')
XSD_DOCUMENTATION_TAG = xsd_qname('documentation')

# Composing schemas
XSD_INCLUDE_TAG = xsd_qname('include')
XSD_IMPORT_TAG = xsd_qname('import')
XSD_REDEFINE_TAG = xsd_qname('redefine')

# Structures
XSD_SIMPLE_TYPE_TAG = xsd_qname('simpleType')
XSD_COMPLEX_TYPE_TAG = xsd_qname('complexType')
XSD_ATTRIBUTE_TAG = xsd_qname('attribute')
XSD_ELEMENT_TAG = xsd_qname('element')
XSD_NOTATION_TAG = xsd_qname('notation')
XSD_NOTATION_TYPE = xsd_qname('NOTATION')

# Grouping
XSD_GROUP_TAG = xsd_qname('group')
XSD_ATTRIBUTE_GROUP_TAG = xsd_qname('attributeGroup')

# simpleType declaration elements
XSD_RESTRICTION_TAG = xsd_qname('restriction')
XSD_LIST_TAG = xsd_qname('list')
XSD_UNION_TAG = xsd_qname('union')

# complexType content
XSD_EXTENSION_TAG = xsd_qname('extension')
XSD_SEQUENCE_TAG = xsd_qname('sequence')
XSD_CHOICE_TAG = xsd_qname('choice')
XSD_ALL_TAG = xsd_qname('all')
XSD_ANY_TAG = xsd_qname('any')
XSD_SIMPLE_CONTENT_TAG = xsd_qname('simpleContent')
XSD_COMPLEX_CONTENT_TAG = xsd_qname('complexContent')
XSD_ANY_ATTRIBUTE_TAG = xsd_qname('anyAttribute')

#
#  Facets (lexical, pre-lexical and value-based facets)
XSD_ENUMERATION_TAG = xsd_qname('enumeration')
XSD_LENGTH_TAG = xsd_qname('length')
XSD_MIN_LENGTH_TAG = xsd_qname('minLength')
XSD_MAX_LENGTH_TAG = xsd_qname('maxLength')
XSD_PATTERN_TAG = xsd_qname('pattern')              # lexical facet
XSD_WHITE_SPACE_TAG = xsd_qname('whiteSpace')       # pre-lexical facet
XSD_WHITE_SPACE_ENUM = ('preserve', 'replace', 'collapse')
XSD_MAX_INCLUSIVE_TAG = xsd_qname('maxInclusive')
XSD_MAX_EXCLUSIVE_TAG = xsd_qname('maxExclusive')
XSD_MIN_INCLUSIVE_TAG = xsd_qname('minInclusive')
XSD_MIN_EXCLUSIVE_TAG = xsd_qname('minExclusive')
XSD_TOTAL_DIGITS_TAG = xsd_qname('totalDigits')
XSD_FRACTION_DIGITS_TAG = xsd_qname('fractionDigits')

# XSD 1.1 facets
XSD_ASSERTIONS_TAG = xsd_qname('assertions')
XSD_EXPLICIT_TIMEZONE_TAG = xsd_qname('explicitTimezone')


#
# Attributes of other namespaces
XML_LANG = get_qname(XML_NAMESPACE_PATH, 'lang')
XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'noNamespaceSchemaLocation')
