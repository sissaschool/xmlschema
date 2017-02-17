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

from .core import (
    PY3, etree_fromstring, etree_get_namespaces, unicode_type,
    XSI_NAMESPACE_PATH, XSD_NAMESPACE_PATH
)
from .exceptions import (
    XMLSchemaValueError, XMLSchemaLookupError, XMLSchemaAttributeError,
    XMLSchemaURLError, XMLSchemaParseError, XMLSchemaComponentError,
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError
)
from .utils import camel_case_split, split_qname, get_qname, FrozenDict
from .resources import load_resource


_logger = _logging.getLogger(__name__)


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

# XSD 1.1 facets
XSD_ASSERTIONS_TAG = xsd_qname('assertions')
XSD_EXPLICIT_TIMEZONE_TAG = xsd_qname('explicitTimezone')


#
# XSI attributes
XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'noNamespaceSchemaLocation')


def get_xsi_schema_location(elem):
    """Retrieve the attribute xsi:schemaLocation from an XML document node."""
    try:
        return elem.find('.[@%s]' % XSI_SCHEMA_LOCATION).attrib.get(XSI_SCHEMA_LOCATION)
    except AttributeError:
        return None


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
    :param ref: An object or type that refer to the name.
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


def check_value(obj, name, ref, value, values, nullable=True):
    """
    Checks the value of 'value' argument to be in a tuple of values.

    :param obj: The schema object.
    :param name: The name of the attribute/key of the object.
    :param ref: An object or type that refer to the name.
    :param value: The value to be checked.
    :param values: A tuple with admitted values.
    :param nullable: None  admitted values.
    """
    if nullable:
        if value is not None and value not in values:
            message = "wrong value %s, it must be None or one of %r." % (type(value), values)
            raise XMLSchemaComponentError(obj, name, ref, message)
    elif value not in values:
        message = "wrong value %r, it must be one of %r." % (type(value), values)
        raise XMLSchemaComponentError(obj, name, ref, message)


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


def get_xsd_declaration(elem, required=True, strict=True):
    declarations_iterator = iter_xsd_declarations(elem)
    try:
        xsd_declaration = next(declarations_iterator)
    except StopIteration:
        if required:
            raise XMLSchemaParseError("missing declaration", elem)
        return None
    else:
        if not strict:
            return xsd_declaration
        try:
            next(declarations_iterator)
        except StopIteration:
            return xsd_declaration
        else:
            raise XMLSchemaParseError("too many declarations", elem)


def iter_xsd_declarations(elem):
    """
    Get the node's children are XSD declarations, excluding annotations.
    """
    counter = 0
    for child in elem:
        if child.tag == XSD_ANNOTATION_TAG:
            if counter > 0:
                raise XMLSchemaParseError("XSD annotation not allowed here!", elem=elem)
        else:
            yield child
            counter += 1


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


#
# Define an iterfind function for some XML Schema elements
def create_iterfind_by_tag(tag):
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

iterfind_xsd_imports = create_iterfind_by_tag(XSD_IMPORT_TAG)
iterfind_xsd_inclusions = create_iterfind_by_tag(XSD_INCLUDE_TAG)
iterfind_xsd_redefinitions = create_iterfind_by_tag(XSD_REDEFINE_TAG)
iterfind_xsd_simple_types = create_iterfind_by_tag(XSD_SIMPLE_TYPE_TAG)
iterfind_xsd_complex_types = create_iterfind_by_tag(XSD_COMPLEX_TYPE_TAG)
iterfind_xsd_attributes = create_iterfind_by_tag(XSD_ATTRIBUTE_TAG)
iterfind_xsd_attribute_groups = create_iterfind_by_tag(XSD_ATTRIBUTE_GROUP_TAG)
iterfind_xsd_elements = create_iterfind_by_tag(XSD_ELEMENT_TAG)
iterfind_xsd_groups = create_iterfind_by_tag(XSD_GROUP_TAG)


#
# Define a lookup function for each structure of the XML Schema
def create_lookup_function(table_name):
    """
    Defines a lookup function for a specific map of the XMLSchema class.
    """
    def lookup_function(qname, namespace, imported_schemas):
        try:
            schema = imported_schemas[namespace]
        except KeyError as err:
            raise XMLSchemaLookupError("Namespace %r not imported!" % err)

        try:
            try:
                return getattr(schema, table_name)[qname]
            except AttributeError:
                # The schema is a string --> build the schema using the string
                if not isinstance(schema, (str, unicode_type)):
                    raise
                cls = imported_schemas[XSD_NAMESPACE_PATH].__class__
                schema = imported_schemas[namespace] = cls(schema)
                return getattr(schema, table_name)[qname]

        except KeyError as err:
            try:
                # Try the empty namespace for imported schemas without namespace attribute
                return getattr(imported_schemas[''], table_name)[qname]
            except KeyError:
                raise XMLSchemaLookupError("Missing XSD reference %s!" % err)

    return lookup_function

lookup_type = create_lookup_function("types")
lookup_attribute = create_lookup_function("attributes")
lookup_attribute_group = create_lookup_function("attribute_groups")
lookup_element = create_lookup_function("elements")
lookup_group = create_lookup_function("groups")
lookup_base_element = create_lookup_function("base_elements")


#
# Define an update function for each structure of the XML Schema
def create_update_function(factory_key, filter_function):

    def update_xsd_map(schema, target, elements, **kwargs):
        elements = filter_function(elements)
        _logger.debug(u"Update <%s at %#x> with filter_function %r",
                      target.__class__.__name__, id(target), filter_function.__name__)
        factory_function = kwargs.get(factory_key)
        errors_counter = 0
        while True:
            errors = []
            for elem in elements:
                try:
                    qname = get_qname(schema.target_namespace, elem.attrib['name'])
                except KeyError:
                    continue  # Skip local declarations

                try:
                    name_or_path, xsd_instance = factory_function(
                        elem, schema, instance=target.get(qname), **kwargs
                    )
                except XMLSchemaLookupError as err:
                    _logger.debug("XSD reference %s not yet defined: elem.attrib=%r", err, elem.attrib)
                    errors.append(XMLSchemaParseError(message=str(err), elem=elem))
                else:
                    _logger.debug("Update XSD reference: target[%r] = %r", name_or_path, xsd_instance)
                    target[name_or_path] = xsd_instance

            if not errors:
                break
            elif len(errors) == errors_counter:
                raise errors[0]

            errors_counter = len(errors)
            elements = [err.elem for err in errors]

    return update_xsd_map

update_xsd_simple_types = create_update_function('simple_type_factory', iterfind_xsd_simple_types)
update_xsd_attributes = create_update_function('attribute_factory', iterfind_xsd_attributes)
update_xsd_attribute_groups = create_update_function('attribute_group_factory', iterfind_xsd_attribute_groups)
update_xsd_complex_types = create_update_function('complex_type_factory', iterfind_xsd_complex_types)
update_xsd_elements = create_update_function('element_factory', iterfind_xsd_elements)
update_xsd_groups = create_update_function('group_factory', iterfind_xsd_groups)


def xsd_include_schemas(schema, elements, check_schema=False):
    """
    Append elements of included schemas to element list itself.
    Ignore locations already loaded in the schema. Parse also
    xs:include and xs:redefine.

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
            except XMLSchemaURLError as err:
                raise XMLSchemaURLError(reason="cannot get the subschema: %r" % err)

            if schema_uri not in included_schemas and schema_uri not in new_inclusions:
                schema_root = etree_fromstring(_schema)
                check_tag(schema_root, XSD_SCHEMA_TAG)
                new_inclusions[schema_uri] = schema_root
                namespaces.update(etree_get_namespaces(_schema))
                _include_schemas(schema_root, schema_uri)

        for elem in iterfind_xsd_redefinitions(_elements, namespaces=namespaces):
            for location in get_xsd_attribute(elem, 'schemaLocation').split():
                _schema, schema_uri = load_resource(location, base_uri)
                if schema_uri not in included_schemas and schema_uri not in new_inclusions:
                    namespaces.update(etree_get_namespaces(_schema))
                    schema_root = etree_fromstring(_schema)
                    xsd_redefine_schema(schema_root, elem)
                    new_inclusions[schema_uri] = schema_root

    new_inclusions = {}
    _include_schemas(elements, schema.uri)
    if new_inclusions:
        included_schemas.update(new_inclusions)
        for schema_element in new_inclusions.values():
            elements.extend(list(schema_element))


def xsd_redefine_schema(schema_root, elem):
    """
    Extend a schema with global model groups, attribute groups, simple
    and complex types redefinitions.

    :param schema_root: The root element of a schema.
    :param elem: The XSD redefine element containing the redefinitions.
    """
    check_tag(schema_root, XSD_SCHEMA_TAG)
    check_tag(elem, XSD_REDEFINE_TAG)
    for child in elem:
        check_tag(
            child, XSD_ATTRIBUTE_GROUP_TAG, XSD_GROUP_TAG, XSD_ANNOTATION_TAG,
            XSD_SIMPLE_TYPE_TAG, XSD_COMPLEX_TYPE_TAG
        )
        if child.tag == XSD_ANNOTATION_TAG:
            continue

        if not any([is_xsd_equivalent(child, c) for c in schema_root]):
            raise XMLSchemaParseError("not a redefinition!", child)

    schema_root.extend(list(elem))


def is_xsd_equivalent(e1, e2):
    """
    Check if two Elements are the same XSD declaration (same tag an name).
    """
    if e1.tag != e2.tag:
        return False
    try:
        return e1.attrib['name'] == e2.attrib['name']
    except KeyError:
        return False


class XsdBase(object):
    """
    Abstract base class for representing generic XML Schema Definition object,
    providing common API interface.

    :param name: Name associated with the definition
    :param elem: ElementTree's node containing the definition
    """
    _DUMMY_DICT = FrozenDict()
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    def __init__(self, name=None, elem=None, schema=None):
        self.name = name
        self.elem = elem
        self.schema = schema

    def __setattr__(self, name, value):
        if name == "elem":
            self._attrib = value.attrib if value is not None else self._DUMMY_DICT
        elif name == "schema":
            if value is not None:
                self._target_namespace = value.target_namespace
                self._namespaces = value.namespaces
                self._imported_schemas = value.imported_schemas
            else:
                self._target_namespace = ''
                self._namespaces = self._DUMMY_DICT
                self._imported_schemas = self._DUMMY_DICT
        super(XsdBase, self).__setattr__(name, value)

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
        value = get_xsd_attribute(self.elem, 'namespace', default='##any')
        items = value.strip().split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            return value
        elif not all([s not in ('##any', '##other') for s in items]):
            raise XMLSchemaValueError("wrong value %r for the 'namespace' attribute." % value, self)
        return value

    def _get_derivation_attribute(self, attribute, values):
        value = get_xsd_attribute(self.elem, attribute, default='#all')
        items = value.strip().split()
        if len(items) == 1 and items[0] == "#all":
            return
        elif not all([s not in values for s in items]):
            raise XMLSchemaValueError("wrong value %r for attribute %r" % (value, attribute), self)

    def _is_namespace_allowed(self, namespace, any_namespace):
        if any_namespace == '##any' or namespace == XSI_NAMESPACE_PATH:
            return True
        elif any_namespace == '##other':
            return namespace != self._target_namespace
        else:
            any_namespaces = any_namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self._target_namespace:
                return True
            else:
                return namespace in any_namespaces

    @property
    def id(self):
        return self._attrib.get('id')

    def update_attrs(self, **kwargs):
        """For simplify the schema building when an instance update is needed."""
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise XMLSchemaAttributeError("%r object has no attribute %r" % (self, k))

    def validate(self, obj):
        for error in self.iter_errors(obj):
            raise error

    def iter_errors(self, obj):
        for chunk in self.iter_decode(obj):
            if isinstance(chunk, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                yield chunk

    def decode(self, obj, validate=True, **kwargs):
        for obj in self.iter_decode(obj, validate, **kwargs):
            if isinstance(obj, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                raise obj
            return obj

    def encode(self, obj, validate=True, **kwargs):
        for obj in self.iter_encode(obj, validate, **kwargs):
            if isinstance(obj, (XMLSchemaEncodeError, XMLSchemaValidationError)):
                raise obj
            return obj

    def iter_decode(self, obj, validate=True, **kwargs):
        """
        Decode generator method. It generates the object that represents the
        decoded value or, if there are decoding or validation errors, a sequence
        of exceptions XMLSchemaValidationError followed by the decoded value. If
        there is a decoding error the last generated value is the original value
        or a partial decoded object (eg. in case of a list).
        """
        raise NotImplementedError

    def iter_encode(self, obj, validate=True, **kwargs):
        raise NotImplementedError
