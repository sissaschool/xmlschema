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
This module contains functions for manipulating fully qualified names and XSD qname constants.
"""
import re
from .core import XSD_NAMESPACE_PATH, XSI_NAMESPACE_PATH
from .exceptions import XMLSchemaValueError

_RE_MATCH_NAMESPACE = re.compile(r'\{([^}]*)\}')
_RE_STRIP_NAMESPACE = re.compile(r'\{[^}]*\}')
_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*\})')


def get_qname(uri, name):
    """
    Return a fully qualified Name from URI and local part. If the URI is empty
    or None, or if the name is already in QName format, returns the 'name' argument.

    :param uri: namespace URI
    :param name: local name/tag
    :return: string
    """
    if uri and name[0] not in ('{', '.', '/', '['):
        return u"{%s}%s" % (uri, name)
    else:
        return name


def split_qname(qname):
    """
    Split a universal name format (QName) into URI and local part

    :param qname: QName or universal name formatted string.
    :return: A couple with URI and local parts. URI is None if there
    is only the local part.
    """
    if qname[0] == '{':
        try:
            return qname[1:].split('}')
        except ValueError:
            raise XMLSchemaValueError("wrong format for a universal name! '%s'" % qname)
    return None, qname


def split_reference(ref, namespaces):
    """
    Processes a reference name using namespaces information. A reference
    is a local name or a name with a namespace prefix (e.g. "xs:string").
    A couple with fully qualified name and the namespace is returned.
    If no namespace association is possible returns a local name and None
    when the reference is only a local name or raise a ValueError otherwise.

    :param ref: Reference or fully qualified name (QName).
    :param namespaces: Dictionary that maps the namespace prefix into URI.
    :return: A couple with qname and namespace.
    """
    if ref[0] == '{':
        return ref, ref[1:].split('}')[0] if ref[0] == '{' else ''

    try:
        prefix, tag = ref.split(":")
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
            return u"{%s}%s" % (uri, tag) if uri else tag, uri


def get_qualified_path(path, uri):
    return u'/'.join([get_qname(uri, name) for name in split_path(path)])


def get_namespace(name):
    try:
        return _RE_MATCH_NAMESPACE.match(name).group(1)
    except AttributeError:
        return None


def strip_namespace(path_or_name, prefix=''):
    return _RE_STRIP_NAMESPACE.sub(prefix, path_or_name)


def split_path(path):
    return _RE_SPLIT_PATH.split(path)


def uri_to_prefixes(text, namespaces):
    """Replace namespace "{uri}" with "prefix:". """
    for prefix, uri in namespaces.items():
        if not uri or not prefix:
            continue
        uri = '{%s}' % uri
        if text.find(uri) >= 0:
            text = text.replace(uri, '%s:' % prefix)
    return text


def xsd_qname(name):
    """
    Build a QName for XSD namespace from a local name.

    :param name: local name/tag
    :return: fully qualified name for XSD namespace
    """
    if name[0] != '{':
        return u"{%s}%s" % (XSD_NAMESPACE_PATH, name)
    elif not name.startswith('{%s}' % XSD_NAMESPACE_PATH):
        raise XMLSchemaValueError("'%s' is not a name of the XSD namespace" % name)
    else:
        return name


# ------------------------
#  XSD/XS Qualified Names
# ------------------------
XSD_SCHEMA_TAG = xsd_qname('schema')

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
XSD_ANNOTATION_TAG = xsd_qname('annotation')

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

# Facets
XSD_ENUMERATION_TAG = xsd_qname('enumeration')
XSD_LENGTH_TAG = xsd_qname('length')
XSD_MIN_LENGTH_TAG = xsd_qname('minLength')
XSD_MAX_LENGTH_TAG = xsd_qname('maxLength')
XSD_PATTERN_TAG = xsd_qname('pattern')              # lexical facet
XSD_WHITE_SPACE_TAG = xsd_qname('whiteSpace')       # pre-lexical facet
XSD_MAX_INCLUSIVE_TAG = xsd_qname('maxInclusive')
XSD_MAX_EXCLUSIVE_TAG = xsd_qname('maxExclusive')
XSD_MIN_INCLUSIVE_TAG = xsd_qname('minInclusive')
XSD_MIN_EXCLUSIVE_TAG = xsd_qname('minExclusive')
XSD_TOTAL_DIGITS_TAG = xsd_qname('totalDigits')
XSD_FRACTION_DIGITS_TAG = xsd_qname('fractionDigits')

XSD_VALUE_BASED_FACETS = (
    XSD_LENGTH_TAG,
    XSD_MIN_LENGTH_TAG,
    XSD_MAX_LENGTH_TAG,
    XSD_ENUMERATION_TAG,
    XSD_WHITE_SPACE_TAG,
    XSD_PATTERN_TAG,
    XSD_MAX_INCLUSIVE_TAG,
    XSD_MAX_EXCLUSIVE_TAG,
    XSD_MIN_INCLUSIVE_TAG,
    XSD_MIN_EXCLUSIVE_TAG,
    XSD_TOTAL_DIGITS_TAG,
    XSD_FRACTION_DIGITS_TAG
)

# ----------------------------------
#  Useful names of other namespaces
# ----------------------------------
XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'noNamespaceSchemaLocation')

__all__ = (
    'get_qname', 'xsd_qname', 'split_qname', 'split_path',
    'split_reference', 'get_namespace', 'get_qualified_path',
    'uri_to_prefixes', 'strip_namespace', 'XSD_SCHEMA_TAG',
    'XSD_INCLUDE_TAG', 'XSD_IMPORT_TAG', 'XSD_REDEFINE_TAG',
    'XSD_SIMPLE_TYPE_TAG', 'XSD_COMPLEX_TYPE_TAG',
    'XSD_ATTRIBUTE_TAG', 'XSD_ELEMENT_TAG',
    'XSD_NOTATION_TAG', 'XSD_ANNOTATION_TAG',
    'XSD_GROUP_TAG', 'XSD_ATTRIBUTE_GROUP_TAG',
    'XSD_RESTRICTION_TAG', 'XSD_EXTENSION_TAG',
    'XSD_LIST_TAG', 'XSD_UNION_TAG', 'XSD_SEQUENCE_TAG',
    'XSD_CHOICE_TAG', 'XSD_ALL_TAG', 'XSD_ANY_TAG',
    'XSD_SIMPLE_CONTENT_TAG', 'XSD_COMPLEX_CONTENT_TAG',
    'XSD_ANY_ATTRIBUTE_TAG', 'XSD_VALUE_BASED_FACETS',
    'XSD_ENUMERATION_TAG', 'XSD_LENGTH_TAG',
    'XSD_MIN_LENGTH_TAG', 'XSD_MAX_LENGTH_TAG',
    'XSD_PATTERN_TAG', 'XSD_WHITE_SPACE_TAG',
    'XSD_MAX_INCLUSIVE_TAG', 'XSD_MAX_EXCLUSIVE_TAG',
    'XSD_MIN_INCLUSIVE_TAG', 'XSD_MIN_EXCLUSIVE_TAG',
    'XSD_TOTAL_DIGITS_TAG', 'XSD_FRACTION_DIGITS_TAG'
)
