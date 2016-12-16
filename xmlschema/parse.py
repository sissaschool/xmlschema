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
This module contains functions for parsing XSD schemas loaded into ElementTree structures.
"""
import logging as _logging

from .utils import camel_case_split
from .core import etree_fromstring, etree_get_namespaces
from .exceptions import (
    XMLSchemaValueError, XMLSchemaLookupError, XMLSchemaParseError,
    XMLSchemaOSError,
)
from .qnames import (
    split_qname, XSD_SCHEMA_TAG, XSD_ANNOTATION_TAG, XSD_IMPORT_TAG, XSD_INCLUDE_TAG,
    XSD_REDEFINE_TAG, XSD_SIMPLE_TYPE_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ATTRIBUTE_TAG,
    XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG, XSD_GROUP_TAG
)
from .resources import load_uri_or_file, load_resource


_logger = _logging.getLogger(__name__)


def check_tag(elem, *args):
    if elem.tag not in args:
        tags = (split_qname(tag)[1] for tag in args)
        raise XMLSchemaParseError("({}) expected: {}".format('|'.join(tags), elem))


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


def get_xsd_attribute(elem, attribute, default=None, enumeration=None):
    """
    Get an element's attribute and throws a schema error if
    the attribute is required or return None if it's optional.

    :param elem: The Element instance.
    :param attribute: The name of the XML attribute.
    :param default: The default value. None means that the attribute is mandatory.
    :param enumeration: A container of admitted values for the attribute. Optional.
    :return: A string containing the attribute value.
    """
    try:
        value = elem.attrib[attribute]
    except KeyError as err:
        if default is not None:
            value = default
        else:
            raise XMLSchemaParseError("attribute {} expected".format(err), elem)
    if enumeration and value not in enumeration:
        raise XMLSchemaParseError("wrong value %r for %r attribute" % (value, attribute), elem)
    return value


def get_xsd_bool_attribute(elem, attribute, default=None):
    value = get_xsd_attribute(elem, attribute, default)
    if isinstance(value, bool):
        return value
    elif value in ('true', '1'):
        return True
    elif value in ('false', '0'):
        return False
    else:
        raise XMLSchemaParseError("an XML boolean value is required for attribute %r" % attribute, elem)


def get_xsd_int_attribute(elem, attribute, default=None, minimum=None):
    """
    Get an element's attribute converting it to an int(). Throws an
    error if the attribute is not found and the default is None.
    Checks the value when a minimum is provided.

    :param elem: The Element's instance.
    :param attribute: The attribute name.
    :param default: Optional default, if None raise a parse exception.
    :param minimum: Optional minimum integer value for the attribute.
    :return: Integer containing the attribute value.
    """
    value = get_xsd_attribute(elem, attribute, default)
    try:
        value = int(value)
    except (TypeError, ValueError) as err:
        raise XMLSchemaValueError("attribute {} error: {}".format(attribute, str(err)), elem)
    else:
        if minimum is None or value >= minimum:
            return value
        else:
            raise XMLSchemaParseError(
                "attribute %r value must be greater or equal to %r" % (attribute, minimum), elem
            )


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


def xsd_include_schemas(schema, elements):
    """
    Append elements of included schemas to element list itself.
    Ignore locations already loaded in the schema.

    :param schema: The schema instance.
    :param elements: XSD declarations as an Element Tree structure.
    """
    included_schemas = schema.included_schemas
    namespaces = schema.namespaces

    def _include_schemas(_elements, base_uri):
        for elem in iterfind_xsd_inclusions(_elements, namespaces=namespaces):
            locations = get_xsd_attribute(elem, 'schemaLocation')
            try:
                _schema, schema_uri = load_resource(locations, base_uri)
            except (OSError, IOError):
                raise XMLSchemaOSError("Not accessible schema locations '{}'".format(locations))

            if schema_uri not in included_schemas and schema_uri not in new_inclusions:
                schema_tree = etree_fromstring(_schema)
                check_tag(schema_tree, XSD_SCHEMA_TAG)
                new_inclusions[schema_uri] = schema_tree
                namespaces.update(etree_get_namespaces(_schema))
                _include_schemas(schema_tree, schema_uri)

        for elem in iterfind_xsd_redefinitions(_elements, namespaces=namespaces):
            for location in get_xsd_attribute(elem, 'schemaLocation').split():
                _schema, schema_uri = load_uri_or_file(location, base_uri)
                if schema_uri not in included_schemas and schema_uri not in new_inclusions:
                    namespaces.update(etree_get_namespaces(_schema))
                    schema_tree = etree_fromstring(_schema)
                    for child in elem:
                        schema_tree.append(child)
                    new_inclusions[schema_uri] = schema_tree

    new_inclusions = {}
    _include_schemas(elements, schema.uri)
    if new_inclusions:
        included_schemas.update(new_inclusions)
        for schema_element in new_inclusions.values():
            elements.extend(list(schema_element))
