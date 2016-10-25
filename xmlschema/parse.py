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
This module contains names and methods for parsing XSD schemas.
"""
import logging as _logging
from .core import (
    XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaLookupError, XMLSchemaException,
    PY3, XSD_NAMESPACE_PATH, XSI_NAMESPACE_PATH, etree_tostring
)
from .qnames import get_qname, split_qname, split_path

_logger = _logging.getLogger(__name__)


class XMLSchemaParseError(XMLSchemaException, ValueError):
    """Raised when an error is found when parsing an XML Schema."""
    def __init__(self, message, elem=None):
        self.message = message
        self.elem = elem

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join([
            self.message,
            u"\n\nSyntax error:\n\n  %s" % etree_tostring(self.elem) if self.elem is not None else ''
        ])

    if PY3:
        __str__ = __unicode__


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
XSD_PATTERN_TAG = xsd_qname('pattern')
XSD_WHITE_SPACE_TAG = xsd_qname('whiteSpace')
XSD_MAX_INCLUSIVE_TAG = xsd_qname('maxInclusive')
XSD_MAX_EXCLUSIVE_TAG = xsd_qname('maxExclusive')
XSD_MIN_INCLUSIVE_TAG = xsd_qname('minInclusive')
XSD_MIN_EXCLUSIVE_TAG = xsd_qname('minExclusive')
XSD_TOTAL_DIGITS_TAG = xsd_qname('totalDigits')
XSD_FRACTION_DIGITS_TAG = xsd_qname('fractionDigits')

# ----------------------------------
#  Useful names of other namespaces
# ----------------------------------
XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'noNamespaceSchemaLocation')


def camel_case_split(s):
    """
    Split words of a camel case string
    """
    from re import findall
    return findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', s)

#
# Check's functions for detecting inconsistencies
def check_tag(elem, *args):
    if elem.tag not in args:
        tags = (split_qname(tag)[1] for tag in args)
        raise XMLSchemaParseError("({}) expected: {}".format('|'.join(tags), elem))


def check_type(name, value, *types):
    """
    Check the type of an attribute with a list of admitted types.
    """
    if not isinstance(value, types):
        raise XMLSchemaTypeError(
            "wrong type {} for '{}' attribute, it must be one of {}.".format(type(value), name, types)
        )


def check_value(name, value, *values):
    """
    Check the value of an attribute with a list of admitted values.
    """
    if value not in values:
        raise XMLSchemaValueError(
            "wrong value {} for '{}' attribute, it must be one of {}.".format(type(value), name, values)
        )


#
# Functions for extracting declarations from schema's tree
def get_xsd_annotation(elem):
    """
    Return the annotation of a node child that is
    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation,
    None if there are no annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION_TAG else None
    except IndexError:
        return None


def get_xsd_declarations(elem, min_occurs=0, max_occurs=None):
    """
    Get the node's children are XSD declarations, excluding annotations.
    """
    declarations = [child for child in elem if child.tag != XSD_ANNOTATION_TAG]
    occurs = len(declarations)
    if occurs < min_occurs:
        raise XMLSchemaParseError("too few declarations (minOccurs={})".format(min_occurs), elem)
    elif max_occurs is not None and occurs > max_occurs:
        raise XMLSchemaParseError("too many declarations (maxOccurs={})".format(max_occurs), elem)
    return declarations


def get_xsd_declaration(elem, min_occurs=0):
    try:
        return get_xsd_declarations(elem, min_occurs=min_occurs, max_occurs=1)[0]
    except IndexError:
        return None


def get_xsd_attribute(elem, attribute, required=True):
    """
    Get an element's attribute and throws a schema error if
    the attribute is required or return None if it's optional.

    :param elem:
    :param attribute:
    :param required:
    :return: String containing the attribute value.
    """
    try:
        return elem.attrib[attribute]
    except KeyError as err:
        if required:
            raise XMLSchemaParseError("attribute {} expected".format(err), elem)
        else:
            return None


def _create_iterfind_by_tag(tag):
    """
    Defines a generator that produce all subelements that have a specific tag.
    """
    tag = str(tag)

    def iterfind_function(elements, path=None, namespaces=None):
        if isinstance(elements, list):
            for _elem in elements:
                for elem in _elem.iterfind(path or tag, namespaces or {}):
                    if elem.tag == tag:
                        yield _elem
        else:
            for elem in elements.iterfind(path or tag, namespaces or {}):
                if elem.tag == tag:
                    yield elem
    iterfind_function.__name__ = 'iterfind_xsd_%ss' % '_'.join(camel_case_split(split_qname(tag)[1])).lower()

    return iterfind_function

iterfind_xsd_imports = _create_iterfind_by_tag(XSD_IMPORT_TAG)
iterfind_xsd_inclusions = _create_iterfind_by_tag(XSD_INCLUDE_TAG)
iterfind_xsd_redefinitions = _create_iterfind_by_tag(XSD_REDEFINE_TAG)
iterfind_xsd_simple_types = _create_iterfind_by_tag(XSD_SIMPLE_TYPE_TAG)
iterfind_xsd_complex_types = _create_iterfind_by_tag(XSD_COMPLEX_TYPE_TAG)
iterfind_xsd_attributes = _create_iterfind_by_tag(XSD_ATTRIBUTE_TAG)
iterfind_xsd_attribute_groups = _create_iterfind_by_tag(XSD_ATTRIBUTE_GROUP_TAG)
iterfind_xsd_elements = _create_iterfind_by_tag(XSD_ELEMENT_TAG)
iterfind_xsd_groups = _create_iterfind_by_tag(XSD_GROUP_TAG)


def _create_lookup_function(lookup_table):
    """
    Defines a lookup function for a specific map on multiple schema's instances.
    """
    def lookup_function(qname_or_path, namespace, lookup_schemas):
        try:
            schema = lookup_schemas[namespace]
        except KeyError as err:
            raise XMLSchemaLookupError("Namespace not mapped {}!".format(err))

        try:
            return getattr(schema, lookup_table)[qname_or_path]
        except KeyError as err:
            try:
                # Try the empty namespace for imported schemas without namespace attribute
                return getattr(lookup_schemas[''], lookup_table)[qname_or_path]
            except KeyError:
                raise XMLSchemaLookupError("Missing XSD reference %s!" % err)

    return lookup_function

lookup_type = _create_lookup_function("types")
lookup_attribute = _create_lookup_function("attributes")
lookup_element = _create_lookup_function("elements")
lookup_group = _create_lookup_function("groups")
lookup_attribute_group = _create_lookup_function("attribute_groups")


def _create_update_function(factory_key, filter_function):

    def update_xsd_map(schema, target, elements, **kwargs):
        elements = filter_function(elements)
        _logger.debug(u"Update <%s at %#x> with filter_function %r",
                     target.__class__.__name__, id(target), filter_function.__name__)
        factory_function = kwargs.get(factory_key)
        missing_counter = 0
        while True:
            missing = list()
            for elem in elements:
                try:
                    name_or_path, xsd_instance = factory_function(elem, schema, **kwargs)
                except XMLSchemaLookupError as err:
                    _logger.debug("XSD reference %s not yet defined: elem.attrib=%r", err, elem.attrib)
                    missing.append(elem)
                else:
                    _logger.debug("Update XSD reference: target[%r] = %r", name_or_path, xsd_instance)
                    target[name_or_path] = xsd_instance

            if not missing:
                break
            elif len(missing) == missing_counter:
                raise XMLSchemaParseError("missing n.{} global '{}' declarations in XML schema: {}".format(
                    missing_counter,
                    missing[0].tag,
                    [elem.attrib for elem in missing]
                ))
            missing_counter = len(missing)
            elements = missing

    return update_xsd_map

update_xsd_simple_types = _create_update_function('simple_type_factory', iterfind_xsd_simple_types)
update_xsd_attributes = _create_update_function('attribute_factory', iterfind_xsd_attributes)
update_xsd_attribute_groups = _create_update_function('attribute_group_factory', iterfind_xsd_attribute_groups)
update_xsd_complex_types = _create_update_function('complex_type_factory', iterfind_xsd_complex_types)
update_xsd_elements = _create_update_function('element_factory', iterfind_xsd_elements)
update_xsd_groups = _create_update_function('group_factory', iterfind_xsd_groups)


def get_chain(target, path):
    names = split_path(path)
    parts = []
    j = 0
    for k in range(1, len(names)):
        if names[k] in target:
            parts.append(slice(j, k + 1))
            j = k
    if all(['/'.join(names[_slice]) in target for _slice in parts]):
        return target['/'.join(names[j:])]
    raise XMLSchemaLookupError
