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
This module contains qualified names constants and helpers.
"""
from __future__ import unicode_literals
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError
from .namespaces import get_namespace

VC_TEMPLATE = '{http://www.w3.org/2007/XMLSchema-versioning}%s'
XML_TEMPLATE = '{http://www.w3.org/XML/1998/namespace}%s'
XSD_TEMPLATE = '{http://www.w3.org/2001/XMLSchema}%s'
XSI_TEMPLATE = '{http://www.w3.org/2001/XMLSchema-instance}%s'


#
# Version Control attributes (XSD 1.1)
VC_MIN_VERSION = VC_TEMPLATE % 'minVersion'
VC_MAX_VERSION = VC_TEMPLATE % 'maxVersion'
VC_TYPE_AVAILABLE = VC_TEMPLATE % 'typeAvailable'
VC_TYPE_UNAVAILABLE = VC_TEMPLATE % 'typeUnavailable'
VC_FACET_AVAILABLE = VC_TEMPLATE % 'facetAvailable'
VC_FACET_UNAVAILABLE = VC_TEMPLATE % 'facetUnavailable'


#
# XML attributes
XML_LANG = XML_TEMPLATE % 'lang'
XML_SPACE = XML_TEMPLATE % 'space'
XML_BASE = XML_TEMPLATE % 'base'
XML_ID = XML_TEMPLATE % 'id'
XML_SPECIAL_ATTRS = XML_TEMPLATE % 'specialAttrs'


#
# XML Schema Instance attributes
XSI_NIL = XSI_TEMPLATE % 'nil'
XSI_TYPE = XSI_TEMPLATE % 'type'
XSI_SCHEMA_LOCATION = XSI_TEMPLATE % 'schemaLocation'
XSI_NONS_SCHEMA_LOCATION = XSI_TEMPLATE % 'noNamespaceSchemaLocation'


#
# XML Schema fully qualified names
XSD_SCHEMA = XSD_TEMPLATE % 'schema'

# Annotations
XSD_ANNOTATION = XSD_TEMPLATE % 'annotation'
XSD_APPINFO = XSD_TEMPLATE % 'appinfo'
XSD_DOCUMENTATION = XSD_TEMPLATE % 'documentation'

# Composing schemas
XSD_INCLUDE = XSD_TEMPLATE % 'include'
XSD_IMPORT = XSD_TEMPLATE % 'import'
XSD_REDEFINE = XSD_TEMPLATE % 'redefine'
XSD_OVERRIDE = XSD_TEMPLATE % 'override'

# Structures
XSD_SIMPLE_TYPE = XSD_TEMPLATE % 'simpleType'
XSD_COMPLEX_TYPE = XSD_TEMPLATE % 'complexType'
XSD_ATTRIBUTE = XSD_TEMPLATE % 'attribute'
XSD_ELEMENT = XSD_TEMPLATE % 'element'
XSD_NOTATION = XSD_TEMPLATE % 'notation'

# Grouping
XSD_GROUP = XSD_TEMPLATE % 'group'
XSD_ATTRIBUTE_GROUP = XSD_TEMPLATE % 'attributeGroup'

# simpleType declaration elements
XSD_RESTRICTION = XSD_TEMPLATE % 'restriction'
XSD_LIST = XSD_TEMPLATE % 'list'
XSD_UNION = XSD_TEMPLATE % 'union'

# complexType content
XSD_EXTENSION = XSD_TEMPLATE % 'extension'
XSD_SEQUENCE = XSD_TEMPLATE % 'sequence'
XSD_CHOICE = XSD_TEMPLATE % 'choice'
XSD_ALL = XSD_TEMPLATE % 'all'
XSD_ANY = XSD_TEMPLATE % 'any'
XSD_SIMPLE_CONTENT = XSD_TEMPLATE % 'simpleContent'
XSD_COMPLEX_CONTENT = XSD_TEMPLATE % 'complexContent'
XSD_ANY_ATTRIBUTE = XSD_TEMPLATE % 'anyAttribute'

#
#  Facets (lexical, pre-lexical and value-based facets)
XSD_ENUMERATION = XSD_TEMPLATE % 'enumeration'
XSD_LENGTH = XSD_TEMPLATE % 'length'
XSD_MIN_LENGTH = XSD_TEMPLATE % 'minLength'
XSD_MAX_LENGTH = XSD_TEMPLATE % 'maxLength'
XSD_PATTERN = XSD_TEMPLATE % 'pattern'              # lexical facet
XSD_WHITE_SPACE = XSD_TEMPLATE % 'whiteSpace'       # pre-lexical facet
XSD_MAX_INCLUSIVE = XSD_TEMPLATE % 'maxInclusive'
XSD_MAX_EXCLUSIVE = XSD_TEMPLATE % 'maxExclusive'
XSD_MIN_INCLUSIVE = XSD_TEMPLATE % 'minInclusive'
XSD_MIN_EXCLUSIVE = XSD_TEMPLATE % 'minExclusive'
XSD_TOTAL_DIGITS = XSD_TEMPLATE % 'totalDigits'
XSD_FRACTION_DIGITS = XSD_TEMPLATE % 'fractionDigits'

# XSD 1.1 elements
XSD_OPEN_CONTENT = XSD_TEMPLATE % 'openContent'                 # open content model
XSD_DEFAULT_OPEN_CONTENT = XSD_TEMPLATE % 'defaultOpenContent'  # default open content model (schema level)
XSD_ALTERNATIVE = XSD_TEMPLATE % 'alternative'                  # conditional type assignment
XSD_ASSERT = XSD_TEMPLATE % 'assert'                            # complex type assertions
XSD_ASSERTION = XSD_TEMPLATE % 'assertion'                      # facets
XSD_EXPLICIT_TIMEZONE = XSD_TEMPLATE % 'explicitTimezone'

# Identity constraints
XSD_UNIQUE = XSD_TEMPLATE % 'unique'
XSD_KEY = XSD_TEMPLATE % 'key'
XSD_KEYREF = XSD_TEMPLATE % 'keyref'
XSD_SELECTOR = XSD_TEMPLATE % 'selector'
XSD_FIELD = XSD_TEMPLATE % 'field'

#
# XSD Builtin Types

# Special XSD built-in types.
XSD_ANY_TYPE = XSD_TEMPLATE % 'anyType'
XSD_ANY_SIMPLE_TYPE = XSD_TEMPLATE % 'anySimpleType'
XSD_ANY_ATOMIC_TYPE = XSD_TEMPLATE % 'anyAtomicType'

# Other XSD built-in types.
XSD_DECIMAL = XSD_TEMPLATE % 'decimal'
XSD_STRING = XSD_TEMPLATE % 'string'
XSD_DOUBLE = XSD_TEMPLATE % 'double'
XSD_FLOAT = XSD_TEMPLATE % 'float'

XSD_DATE = XSD_TEMPLATE % 'date'
XSD_DATETIME = XSD_TEMPLATE % 'dateTime'
XSD_GDAY = XSD_TEMPLATE % 'gDay'
XSD_GMONTH = XSD_TEMPLATE % 'gMonth'
XSD_GMONTH_DAY = XSD_TEMPLATE % 'gMonthDay'
XSD_GYEAR = XSD_TEMPLATE % 'gYear'
XSD_GYEAR_MONTH = XSD_TEMPLATE % 'gYearMonth'
XSD_TIME = XSD_TEMPLATE % 'time'
XSD_DURATION = XSD_TEMPLATE % 'duration'

XSD_QNAME = XSD_TEMPLATE % 'QName'
XSD_NOTATION_TYPE = XSD_TEMPLATE % 'NOTATION'
XSD_ANY_URI = XSD_TEMPLATE % 'anyURI'
XSD_BOOLEAN = XSD_TEMPLATE % 'boolean'
XSD_BASE64_BINARY = XSD_TEMPLATE % 'base64Binary'
XSD_HEX_BINARY = XSD_TEMPLATE % 'hexBinary'
XSD_NORMALIZED_STRING = XSD_TEMPLATE % 'normalizedString'
XSD_TOKEN = XSD_TEMPLATE % 'token'
XSD_LANGUAGE = XSD_TEMPLATE % 'language'
XSD_NAME = XSD_TEMPLATE % 'Name'
XSD_NCNAME = XSD_TEMPLATE % 'NCName'
XSD_ID = XSD_TEMPLATE % 'ID'
XSD_IDREF = XSD_TEMPLATE % 'IDREF'
XSD_ENTITY = XSD_TEMPLATE % 'ENTITY'
XSD_NMTOKEN = XSD_TEMPLATE % 'NMTOKEN'

XSD_INTEGER = XSD_TEMPLATE % 'integer'
XSD_LONG = XSD_TEMPLATE % 'long'
XSD_INT = XSD_TEMPLATE % 'int'
XSD_SHORT = XSD_TEMPLATE % 'short'
XSD_BYTE = XSD_TEMPLATE % 'byte'
XSD_NON_NEGATIVE_INTEGER = XSD_TEMPLATE % 'nonNegativeInteger'
XSD_POSITIVE_INTEGER = XSD_TEMPLATE % 'positiveInteger'
XSD_UNSIGNED_LONG = XSD_TEMPLATE % 'unsignedLong'
XSD_UNSIGNED_INT = XSD_TEMPLATE % 'unsignedInt'
XSD_UNSIGNED_SHORT = XSD_TEMPLATE % 'unsignedShort'
XSD_UNSIGNED_BYTE = XSD_TEMPLATE % 'unsignedByte'
XSD_NON_POSITIVE_INTEGER = XSD_TEMPLATE % 'nonPositiveInteger'
XSD_NEGATIVE_INTEGER = XSD_TEMPLATE % 'negativeInteger'

# Built-in list types
XSD_IDREFS = XSD_TEMPLATE % 'IDREFS'
XSD_ENTITIES = XSD_TEMPLATE % 'ENTITIES'
XSD_NMTOKENS = XSD_TEMPLATE % 'NMTOKENS'

# XSD 1.1 built-in types
XSD_DATE_TIME_STAMP = XSD_TEMPLATE % 'dateTimeStamp'
XSD_DAY_TIME_DURATION = XSD_TEMPLATE % 'dayTimeDuration'
XSD_YEAR_MONTH_DURATION = XSD_TEMPLATE % 'yearMonthDuration'
XSD_ERROR = XSD_TEMPLATE % 'error'


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
    Return the local part of an expanded QName or a prefixed name. If the name
    is `None` or empty returns the *name* argument.

    :param qname: an expanded QName or a prefixed name or a local name.
    """
    try:
        if qname[0] == '{':
            _, qname = qname.split('}')
        elif ':' in qname:
            _, qname = qname.split(':')
    except IndexError:
        return ''
    except ValueError:
        raise XMLSchemaValueError("the argument 'qname' has a wrong format: %r" % qname)
    except TypeError:
        if qname is None:
            return qname
        raise XMLSchemaTypeError("the argument 'qname' must be a string-like object or None")
    else:
        return qname


def qname_to_prefixed(qname, namespaces, use_empty=True):
    """
    Maps a QName in extended format to a QName in prefixed format.
    Do not change local names and QNames in prefixed format.

    :param qname: a QName or a local name.
    :param namespaces: a map from prefixes to namespace URIs.
    :param use_empty: if `True` use the empty prefix for mapping.
    :return: a QName in prefixed format or a local name.
    """
    if not qname or qname[0] != '{':
        return qname

    namespace = get_namespace(qname)
    prefixes = [x for x in namespaces if namespaces[x] == namespace]

    if not prefixes:
        return qname
    elif prefixes[0]:
        return '%s:%s' % (prefixes[0], qname.split('}', 1)[1])
    elif len(prefixes) > 1:
        return '%s:%s' % (prefixes[1], qname.split('}', 1)[1])
    elif use_empty:
        return qname.split('}', 1)[1]
    else:
        return qname


def qname_to_extended(qname, namespaces):
    """
    Maps a QName in prefixed format or a local name to the extended QName format.
    Local names are mapped if *namespaces* has a not empty default namespace.

    :param qname: a QName in prefixed format or a local name.
    :param namespaces: a map from prefixes to namespace URIs.
    :return: a QName in extended format or a local name.
    """
    try:
        if qname[0] == '{' or not namespaces:
            return qname
    except IndexError:
        return qname

    try:
        prefix, name = qname.split(':', 1)
    except ValueError:
        if not namespaces.get(''):
            return qname
        else:
            return '{%s}%s' % (namespaces[''], qname)
    else:
        try:
            uri = namespaces[prefix]
        except KeyError:
            return qname
        else:
            return u'{%s}%s' % (uri, name) if uri else name
