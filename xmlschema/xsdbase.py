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
import logging as _logging

from .core import PY3, etree_fromstring, etree_get_namespaces
from .exceptions import (
    XMLSchemaValueError, XMLSchemaLookupError, XMLSchemaParseError,
    XMLSchemaOSError, XMLSchemaComponentError
)
from .utils import camel_case_split, split_qname, xsd_qname
from .resources import load_uri_or_file, load_resource


_logger = _logging.getLogger(__name__)


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

# XSD 1.1 facets
XSD_ASSERTIONS_TAG = xsd_qname('assertions')
XSD_EXPLICIT_TIMEZONE_TAG = xsd_qname('explicitTimezone')


#
# Check functions for XSD schema factories and components.
def check_tag(elem, *args):
    if elem.tag not in args:
        tags = (split_qname(tag)[1] for tag in args)
        raise XMLSchemaParseError("({}) expected: {}".format('|'.join(tags), elem))


def check_type(obj, name, ref, value, types):
    """
    Checks the type of 'value' argument to be in a tuple of types.

    :param obj: The schema object.
    :param name: The name of the attribute/key of the object.
    :param ref: A reference to determine the type related to the name.
    :param value: The value to be checked.
    :param types: A tuple with admitted types.
    """
    if not isinstance(value, types):
        raise XMLSchemaComponentError(
            obj=obj,
            name=name,
            ref=ref,
            message="wrong type %s, it must be one of %r." % (type(value), types)
        )


def check_value(obj, name, ref, value, values):
    """
    Checks the value of 'value' argument to be in a tuple of values.

    :param obj: The schema object.
    :param name: The name of the attribute/key of the object.
    :param ref: A reference to determine the type related to the name.
    :param value: The value to be checked.
    :param values: A tuple with admitted values.
    """
    if value not in values:
        raise XMLSchemaComponentError(
            obj=obj,
            name=name,
            ref=ref,
            message="wrong value %s, it must be one of %r." % (type(value), values)
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


def get_xsd_attribute(elem, attribute, enumeration=None, **kwargs):
    """
    Get an element's attribute and throws a schema error if the attribute is absent
    and a default is not provided in keyword arguments. The value of the attribute
    can be checked with a list of admitted values.

    :param elem: The Element instance.
    :param attribute: The name of the XML attribute.
    :param enumeration: Container with the admitted values for the attribute.
    :param kwargs: Optional keyword arguments for a default value or for
    an enumeration with admitted values.
    :return: The attribute value in a string or the default value.
    """
    try:
        value = elem.attrib[attribute]
    except KeyError as err:
        try:
            return kwargs['default']
        except KeyError:
            raise XMLSchemaParseError("attribute {} expected".format(err), elem)
    else:
        if enumeration and value not in enumeration:
            raise XMLSchemaParseError("wrong value %r for %r attribute" % (value, attribute), elem)
        return value


def get_xsd_bool_attribute(elem, attribute, **kwargs):
    value = get_xsd_attribute(elem, attribute, **kwargs)
    if isinstance(value, bool):
        return value
    elif value in ('true', '1'):
        return True
    elif value in ('false', '0'):
        return False
    else:
        raise XMLSchemaParseError("an XML boolean value is required for attribute %r" % attribute, elem)


def get_xsd_int_attribute(elem, attribute, minimum=None, **kwargs):
    """
    Get an element's attribute converting it to an int(). Throws an
    error if the attribute is not found and the default is None.
    Checks the value when a minimum is provided.

    :param elem: The Element's instance.
    :param attribute: The attribute name.
    :param minimum: Optional minimum integer value for the attribute.
    :return: Integer containing the attribute value.
    """
    value = get_xsd_attribute(elem, attribute, **kwargs)
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


def create_lookup_function(lookup_table):
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

lookup_attribute = create_lookup_function("attributes")


def create_update_function(factory_key, filter_function):

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

update_xsd_simple_types = create_update_function('simple_type_factory', iterfind_xsd_simple_types)
update_xsd_attributes = create_update_function('attribute_factory', iterfind_xsd_attributes)
update_xsd_attribute_groups = create_update_function('attribute_group_factory', iterfind_xsd_attribute_groups)
update_xsd_complex_types = create_update_function('complex_type_factory', iterfind_xsd_complex_types)
update_xsd_elements = create_update_function('element_factory', iterfind_xsd_elements)
update_xsd_groups = create_update_function('group_factory', iterfind_xsd_groups)


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


class XsdBase(object):
    """
    Abstract base class for representing generic XML Schema Definition object,
    providing common API interface.

    :param name: Name associated with the definition
    :param elem: ElementTree's node containing the definition
    """
    EMPTY_DICT = {}
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    def __init__(self, name=None, elem=None, schema=None):
        self.name = name
        self.elem = elem
        self.schema = schema
        self._attrib = dict(elem.attrib) if elem is not None else self.EMPTY_DICT

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name, id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.name and self.name[0] == '{':
            return self.name
        else:
            return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def _get_namespace_attribute(self):
        """
        Get the namespace attribute value for anyAttribute and anyElement declaration,
        checking if the value is conforming to the specification.
        """
        value = get_xsd_attribute(self.elem, 'namespace', default='##all')
        items = value.strip().split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            return value
        elif not all([s not in ('##all', '##other') for s in items]):
            raise XMLSchemaValueError("wrong value %r for the 'namespace' attribute." % value, self)
        return value

    def _get_derivation_attribute(self, attribute, values):
        value = get_xsd_attribute(self.elem, attribute, default='#all')
        items = value.strip().split()
        if len(items) == 1 and items[0] == "#all":
            return
        elif not all([s not in values for s in items]):
            raise XMLSchemaValueError("wrong value %r for attribute %r" % (value, attribute), self)

    @property
    def id(self):
        return self._attrib.get('id')
