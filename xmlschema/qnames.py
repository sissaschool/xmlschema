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
XSD_SCHEMA = xsd_qname('schema')

# Annotations
XSD_ANNOTATION = xsd_qname('annotation')
XSD_APPINFO = xsd_qname('appinfo')
XSD_DOCUMENTATION = xsd_qname('documentation')

# Composing schemas
XSD_INCLUDE = xsd_qname('include')
XSD_IMPORT = xsd_qname('import')
XSD_REDEFINE = xsd_qname('redefine')

# Structures
XSD_SIMPLE_TYPE = xsd_qname('simpleType')
XSD_COMPLEX_TYPE = xsd_qname('complexType')
XSD_ATTRIBUTE = xsd_qname('attribute')
XSD_ELEMENT = xsd_qname('element')
XSD_NOTATION = xsd_qname('notation')

# Grouping
XSD_GROUP = xsd_qname('group')
XSD_ATTRIBUTE_GROUP = xsd_qname('attributeGroup')

# simpleType declaration elements
XSD_RESTRICTION = xsd_qname('restriction')
XSD_LIST = xsd_qname('list')
XSD_UNION = xsd_qname('union')

# complexType content
XSD_EXTENSION = xsd_qname('extension')
XSD_SEQUENCE = xsd_qname('sequence')
XSD_CHOICE = xsd_qname('choice')
XSD_ALL = xsd_qname('all')
XSD_ANY = xsd_qname('any')
XSD_SIMPLE_CONTENT = xsd_qname('simpleContent')
XSD_COMPLEX_CONTENT = xsd_qname('complexContent')
XSD_ANY_ATTRIBUTE = xsd_qname('anyAttribute')

#
#  Facets (lexical, pre-lexical and value-based facets)
XSD_ENUMERATION = xsd_qname('enumeration')
XSD_LENGTH = xsd_qname('length')
XSD_MIN_LENGTH = xsd_qname('minLength')
XSD_MAX_LENGTH = xsd_qname('maxLength')
XSD_PATTERN = xsd_qname('pattern')              # lexical facet
XSD_WHITE_SPACE = xsd_qname('whiteSpace')       # pre-lexical facet
XSD_MAX_INCLUSIVE = xsd_qname('maxInclusive')
XSD_MAX_EXCLUSIVE = xsd_qname('maxExclusive')
XSD_MIN_INCLUSIVE = xsd_qname('minInclusive')
XSD_MIN_EXCLUSIVE = xsd_qname('minExclusive')
XSD_TOTAL_DIGITS = xsd_qname('totalDigits')
XSD_FRACTION_DIGITS = xsd_qname('fractionDigits')

# XSD 1.1 elements
XSD_OPEN_CONTENT = xsd_qname('openContent')      # open content model
XSD_ALTERNATIVE = xsd_qname('alternative')      # conditional type assignment
XSD_ASSERT = xsd_qname('assert')            # complex type assertions
XSD_ASSERTION = xsd_qname('assertion')      # facets
XSD_EXPLICIT_TIMEZONE = xsd_qname('explicitTimezone')

# Identity constraints
XSD_UNIQUE = xsd_qname('unique')
XSD_KEY = xsd_qname('key')
XSD_KEYREF = xsd_qname('keyref')
XSD_SELECTOR = xsd_qname('selector')
XSD_FIELD = xsd_qname('field')


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


#
# XSD Builtin Types

# Special XSD built-in types.
XSD_ANY_TYPE = xsd_qname('anyType')
XSD_ANY_SIMPLE_TYPE = xsd_qname('anySimpleType')
XSD_ANY_ATOMIC_TYPE = xsd_qname('anyAtomicType')
XSD_SPECIAL_TYPES = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE}

# Other XSD built-in types.
XSD_DECIMAL = xsd_qname('decimal')
XSD_STRING = xsd_qname('string')
XSD_DOUBLE = xsd_qname('double')
XSD_FLOAT = xsd_qname('float')

XSD_DATE = xsd_qname('date')
XSD_DATETIME = xsd_qname('dateTime')
XSD_GDAY = xsd_qname('gDay')
XSD_GMONTH = xsd_qname('gMonth')
XSD_GMONTH_DAY = xsd_qname('gMonthDay')
XSD_GYEAR = xsd_qname('gYear')
XSD_GYEAR_MONTH = xsd_qname('gYearMonth')
XSD_TIME = xsd_qname('time')
XSD_DURATION = xsd_qname('duration')

XSD_QNAME = xsd_qname('QName')
XSD_NOTATION_TYPE = xsd_qname('NOTATION')
XSD_ANY_URI = xsd_qname('anyURI')
XSD_BOOLEAN = xsd_qname('boolean')

XSD_BASE64_BINARY = xsd_qname('base64Binary')
XSD_HEX_BINARY = xsd_qname('hexBinary')

XSD_NORMALIZED_STRING = xsd_qname('normalizedString')
XSD_TOKEN = xsd_qname('token')
XSD_LANGUAGE = xsd_qname('language')
XSD_NAME = xsd_qname('Name')
XSD_NCNAME = xsd_qname('NCName')
XSD_ID = xsd_qname('ID')
XSD_IDREF = xsd_qname('IDREF')
XSD_ENTITY = xsd_qname('ENTITY')
XSD_NMTOKEN = xsd_qname('NMTOKEN')

XSD_INTEGER = xsd_qname('integer')
XSD_LONG = xsd_qname('long')
XSD_INT = xsd_qname('int')
XSD_SHORT = xsd_qname('short')
XSD_BYTE = xsd_qname('byte')
XSD_NON_NEGATIVE_INTEGER = xsd_qname('nonNegativeInteger')
XSD_POSITIVE_INTEGER = xsd_qname('positiveInteger')
XSD_UNSIGNED_LONG = xsd_qname('unsignedLong')
XSD_UNSIGNED_INT = xsd_qname('unsignedInt')
XSD_UNSIGNED_SHORT = xsd_qname('unsignedShort')
XSD_UNSIGNED_BYTE = xsd_qname('unsignedByte')
XSD_NON_POSITIVE_INTEGER = xsd_qname('nonPositiveInteger')
XSD_NEGATIVE_INTEGER = xsd_qname('negativeInteger')