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
This module contains functions for manipulating fully qualified names and XML Schema tags.
"""
from __future__ import unicode_literals
from .namespaces import get_namespace, XML_NAMESPACE, XSD_NAMESPACE, XSI_NAMESPACE
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError


#
# Functions for handling fully qualified names
def xsd_qname(name):
    """Builds the XSD namespace's QName from a local name."""
    return '{%s}%s' % (XSD_NAMESPACE, name)


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

# XSD 1.1 elements
XSD_OPEN_CONTENT_TAG = xsd_qname('openContent')      # open content model
XSD_ALTERNATIVE_TAG = xsd_qname('alternative')      # conditional type assignment
XSD_ASSERT_TAG = xsd_qname('assert')            # complex type assertions
XSD_ASSERTION_TAG = xsd_qname('assertion')      # facets
XSD_EXPLICIT_TIMEZONE_TAG = xsd_qname('explicitTimezone')

# Identity constraints
XSD_UNIQUE_TAG = xsd_qname('unique')
XSD_KEY_TAG = xsd_qname('key')
XSD_KEYREF_TAG = xsd_qname('keyref')
XSD_SELECTOR_TAG = xsd_qname('selector')
XSD_FIELD_TAG = xsd_qname('field')

# Special XSD built-in types.
XSD_ANY_TYPE = xsd_qname('anyType')
XSD_ANY_SIMPLE_TYPE = xsd_qname('anySimpleType')
XSD_ANY_ATOMIC_TYPE = xsd_qname('anyAtomicType')
XSD_SPECIAL_TYPES = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE}

# Other XSD built-in types.
XSD_DECIMAL_TYPE = xsd_qname('decimal')
XSD_INTEGER_TYPE = xsd_qname('integer')


#
# XML attributes
XML_LANG = get_qname(XML_NAMESPACE, 'lang')
XML_SPACE = get_qname(XML_NAMESPACE, 'space')
XML_BASE = get_qname(XML_NAMESPACE, 'base')
XML_ID = get_qname(XML_NAMESPACE, 'id')
XML_SPECIAL_ATTRS = get_qname(XML_NAMESPACE, 'specialAttrs')

#
# XML Schema Instance attributes
XSI_NIL = get_qname(XSI_NAMESPACE, 'nil')
XSI_TYPE = get_qname(XSI_NAMESPACE, 'type')
XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE, 'noNamespaceSchemaLocation')
