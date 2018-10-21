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
This module contains qualified names constants.
"""
from __future__ import unicode_literals


def xsd_qname(name):
    return '{http://www.w3.org/2001/XMLSchema}%s' % name


def xml_qname(name):
    return '{http://www.w3.org/XML/1998/namespace}%s' % name


def xsi_qname(name):
    return '{http://www.w3.org/2001/XMLSchema-instance}%s' % name


#
# XML attributes
XML_LANG = xml_qname('lang')
XML_SPACE = xml_qname('space')
XML_BASE = xml_qname('base')
XML_ID = xml_qname('id')
XML_SPECIAL_ATTRS = xml_qname('specialAttrs')

#
# XML Schema Instance attributes
XSI_NIL = xsi_qname('nil')
XSI_TYPE = xsi_qname('type')
XSI_SCHEMA_LOCATION = xsi_qname('schemaLocation')
XSI_NONS_SCHEMA_LOCATION = xsi_qname('noNamespaceSchemaLocation')


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
XSD_OPEN_CONTENT = xsd_qname('openContent')            # open content model
XSD_ALTERNATIVE = xsd_qname('alternative')             # conditional type assignment
XSD_ASSERT = xsd_qname('assert')                       # complex type assertions
XSD_ASSERTION = xsd_qname('assertion')                 # facets
XSD_EXPLICIT_TIMEZONE = xsd_qname('explicitTimezone')

# Identity constraints
XSD_UNIQUE = xsd_qname('unique')
XSD_KEY = xsd_qname('key')
XSD_KEYREF = xsd_qname('keyref')
XSD_SELECTOR = xsd_qname('selector')
XSD_FIELD = xsd_qname('field')

#
# XSD Builtin Types

# Special XSD built-in types.
XSD_ANY_TYPE = xsd_qname('anyType')
XSD_ANY_SIMPLE_TYPE = xsd_qname('anySimpleType')
XSD_ANY_ATOMIC_TYPE = xsd_qname('anyAtomicType')

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

# XSD 1.1 built-in types
XSD_DATE_TIME_STAMP = xsd_qname('dateTimeStamp')
XSD_DAY_TIME_DURATION = xsd_qname('dayTimeDuration')
XSD_YEAR_MONTH_DURATION = xsd_qname('yearMonthDuration')

__all__ = [
    'XML_LANG', 'XML_ID', 'XML_BASE', 'XML_SPACE', 'XML_SPECIAL_ATTRS', 'XSI_TYPE', 'XSI_NIL',
    'XSI_SCHEMA_LOCATION', 'XSI_NONS_SCHEMA_LOCATION', 'XSD_SCHEMA', 'XSD_ANNOTATION', 'XSD_APPINFO',
    'XSD_DOCUMENTATION', 'XSD_INCLUDE', 'XSD_IMPORT', 'XSD_REDEFINE', 'XSD_SIMPLE_TYPE', 'XSD_COMPLEX_TYPE',
    'XSD_ATTRIBUTE', 'XSD_ELEMENT', 'XSD_NOTATION', 'XSD_GROUP', 'XSD_ATTRIBUTE_GROUP', 'XSD_RESTRICTION',
    'XSD_LIST', 'XSD_UNION', 'XSD_EXTENSION', 'XSD_SEQUENCE', 'XSD_CHOICE', 'XSD_ALL', 'XSD_ANY',
    'XSD_SIMPLE_CONTENT', 'XSD_COMPLEX_CONTENT', 'XSD_ANY_ATTRIBUTE', 'XSD_ENUMERATION', 'XSD_LENGTH',
    'XSD_MIN_LENGTH', 'XSD_MAX_LENGTH', 'XSD_PATTERN', 'XSD_WHITE_SPACE', 'XSD_MAX_INCLUSIVE',
    'XSD_MAX_EXCLUSIVE', 'XSD_MIN_INCLUSIVE', 'XSD_MIN_EXCLUSIVE', 'XSD_TOTAL_DIGITS', 'XSD_FRACTION_DIGITS',
    'XSD_OPEN_CONTENT', 'XSD_ALTERNATIVE', 'XSD_ASSERT', 'XSD_ASSERTION', 'XSD_EXPLICIT_TIMEZONE',
    'XSD_UNIQUE', 'XSD_KEY', 'XSD_KEYREF', 'XSD_SELECTOR', 'XSD_FIELD', 'XSD_ANY_TYPE', 'XSD_ANY_SIMPLE_TYPE',
    'XSD_ANY_ATOMIC_TYPE', 'XSD_DECIMAL', 'XSD_STRING', 'XSD_DOUBLE', 'XSD_FLOAT', 'XSD_DATE', 'XSD_DATETIME',
    'XSD_GDAY', 'XSD_GMONTH', 'XSD_GMONTH_DAY', 'XSD_GYEAR', 'XSD_GYEAR_MONTH', 'XSD_TIME', 'XSD_DURATION',
    'XSD_QNAME', 'XSD_NOTATION_TYPE', 'XSD_ANY_URI', 'XSD_BOOLEAN', 'XSD_BASE64_BINARY', 'XSD_HEX_BINARY',
    'XSD_NORMALIZED_STRING', 'XSD_TOKEN', 'XSD_LANGUAGE', 'XSD_NAME', 'XSD_NCNAME', 'XSD_ID', 'XSD_IDREF',
    'XSD_ENTITY', 'XSD_NMTOKEN', 'XSD_INTEGER', 'XSD_LONG', 'XSD_INT', 'XSD_SHORT', 'XSD_BYTE',
    'XSD_NON_NEGATIVE_INTEGER', 'XSD_POSITIVE_INTEGER', 'XSD_UNSIGNED_LONG', 'XSD_UNSIGNED_INT',
    'XSD_UNSIGNED_SHORT', 'XSD_UNSIGNED_BYTE', 'XSD_NON_POSITIVE_INTEGER', 'XSD_NEGATIVE_INTEGER',
    'XSD_DATE_TIME_STAMP', 'XSD_DAY_TIME_DURATION', 'XSD_YEAR_MONTH_DURATION',
]
