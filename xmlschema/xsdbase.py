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

from .core import PY3, XSI_NAMESPACE_PATH, XSD_NAMESPACE_PATH
from .exceptions import (
    XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaLookupError,
    XMLSchemaAttributeError, XMLSchemaParseError, XMLSchemaComponentError,
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError
)
from .utils import camel_case_split, split_qname, get_qname, FrozenDict


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


def get_xsi_no_namespace_schema_location(elem):
    """Retrieve the attribute xsi:noNamespaceSchemaLocation from an XML document node."""
    try:
        return elem.find('.[@%s]' % XSI_NONS_SCHEMA_LOCATION).attrib.get(XSI_NONS_SCHEMA_LOCATION)
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

iterfind_xsd_import = create_iterfind_by_tag(XSD_IMPORT_TAG)
iterfind_xsd_include = create_iterfind_by_tag(XSD_INCLUDE_TAG)
iterfind_xsd_redefine = create_iterfind_by_tag(XSD_REDEFINE_TAG)
iterfind_xsd_simple_types = create_iterfind_by_tag(XSD_SIMPLE_TYPE_TAG)
iterfind_xsd_complex_types = create_iterfind_by_tag(XSD_COMPLEX_TYPE_TAG)
iterfind_xsd_attributes = create_iterfind_by_tag(XSD_ATTRIBUTE_TAG)
iterfind_xsd_attribute_groups = create_iterfind_by_tag(XSD_ATTRIBUTE_GROUP_TAG)
iterfind_xsd_elements = create_iterfind_by_tag(XSD_ELEMENT_TAG)
iterfind_xsd_groups = create_iterfind_by_tag(XSD_GROUP_TAG)


#
# Lookups an XML schema global component.
def xsd_lookup(qname, xsd_globals):
    try:
        obj = xsd_globals[qname]
    except KeyError:
        raise XMLSchemaLookupError("Missing XSD reference %r!" % qname)
    else:
        if isinstance(obj, XsdBase):
            return obj
        elif isinstance(obj, list) and isinstance(obj[0], XsdBase):
            return obj[0]
        elif isinstance(obj, (tuple, list)):
            raise XMLSchemaTypeError("XSD reference %r not built!" % qname)
        else:
            raise XMLSchemaTypeError(
                "wrong type %r for XSD reference %r." % (type(obj), qname)
            )


#
# Define an update function for each structure of the XML Schema

def create_load_function(filter_function):

    def load_xsd_globals(xsd_globals, schemas):
        redefinitions = []
        for schema in schemas:
            if schema.built:
                continue

            target_namespace = schema.target_namespace
            for elem in iterfind_xsd_redefine(schema.root):
                for child in filter_function(elem):
                    qname = get_qname(target_namespace, get_xsd_attribute(child, 'name'))
                    redefinitions.append((qname, (child, schema)))

            for elem in filter_function(schema.root):
                qname = get_qname(target_namespace, get_xsd_attribute(elem, 'name'))
                try:
                    xsd_globals[qname].append((elem, schema))
                except KeyError:
                    xsd_globals[qname] = (elem, schema)
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], (elem, schema)]

        for qname, obj in redefinitions:
            if qname not in xsd_globals:
                raise XMLSchemaParseError("not a redefinition!", obj[0])
            try:
                xsd_globals[qname].append(obj)
            except KeyError:
                xsd_globals[qname] = obj
            except AttributeError:
                xsd_globals[qname] = [xsd_globals[qname], obj]

    return load_xsd_globals

load_xsd_simple_types = create_load_function(iterfind_xsd_simple_types)
load_xsd_attributes = create_load_function(iterfind_xsd_attributes)
load_xsd_attribute_groups = create_load_function(iterfind_xsd_attribute_groups)
load_xsd_complex_types = create_load_function(iterfind_xsd_complex_types)
load_xsd_elements = create_load_function(iterfind_xsd_elements)
load_xsd_groups = create_load_function(iterfind_xsd_groups)


def create_build_function(factory_key):

    def build_xsd_map(xsd_globals, tag, **kwargs):
        global_names = set(xsd_globals.keys())
        factory_function = kwargs.get(factory_key)
        errors_counter = 0
        i = 0
        while True:
            i += 1
            missing = []
            errors = []
            for qname in global_names:
                obj = xsd_globals[qname]
                try:
                    if isinstance(obj, XsdBase):
                        elem, schema = obj.elem, obj.schema
                        if elem is None or elem.tag != tag or schema.built:
                            continue
                        res_qname, xsd_instance = factory_function(
                            elem, schema, obj, is_global=True, **kwargs
                        )
                    elif isinstance(obj, tuple):
                        elem, schema = obj
                        if elem.tag != tag:
                            continue
                        res_qname, xsd_instance = factory_function(
                            elem, schema, is_global=True, **kwargs
                        )
                    elif isinstance(obj, list):
                        start = int(isinstance(obj[0], XsdBase))
                        xsd_instance = obj[0] if start else None
                        for k in range(start, len(obj)):
                            elem, schema = obj[k]
                            if elem.tag != tag:
                                break
                            res_qname, xsd_instance = factory_function(
                                elem, schema, xsd_instance, is_global=True, **kwargs
                            )
                            obj[0] = xsd_instance
                    else:
                        raise XMLSchemaTypeError("unexpected type %r for XSD global %r" % (type(obj), qname))

                except (XMLSchemaTypeError, XMLSchemaLookupError) as err:
                    _logger.debug("XSD reference %s not yet defined: elem.attrib=%r", err, elem.attrib)
                    missing.append(qname)
                    if isinstance(err, XMLSchemaLookupError):
                        errors.append(err)
                    if len(missing) == errors_counter:
                        raise errors[0] if errors else XMLSchemaParseError(message=str(err), elem=elem)
                else:
                    if elem.tag != tag:
                        continue
                    if res_qname != qname:
                        raise XMLSchemaParseError("wrong result name: %r != %r" % (res_qname, qname))
                    _logger.debug("Update XSD reference: target[%r] = %r", res_qname, xsd_instance)
                    xsd_globals[qname] = xsd_instance

            if not missing:
                break
            errors_counter = len(missing)
            global_names = missing

    return build_xsd_map

build_xsd_simple_types = create_build_function('simple_type_factory')
build_xsd_attributes = create_build_function('attribute_factory')
build_xsd_attribute_groups = create_build_function('attribute_group_factory')
build_xsd_complex_types = create_build_function('complex_type_factory')
build_xsd_elements = create_build_function('element_factory')
build_xsd_groups = create_build_function('group_factory')


class XsdBase(object):
    """
    Base class for XML Schema Definition classes.

    :param name: A name associated with the definition.
    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
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
                self.target_namespace = value.target_namespace
                self.namespaces = value.namespaces
            else:
                self.target_namespace = ''
                self.namespaces = self._DUMMY_DICT
        super(XsdBase, self).__setattr__(name, value)

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name, id(self))

    def __str__(self):
        # noinspection PyCompatibility
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
        items = value.split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            return value
        elif not all([s not in ('##any', '##other') for s in items]):
            raise XMLSchemaValueError("wrong value %r for the 'namespace' attribute." % value, self)
        return value

    def _get_derivation_attribute(self, attribute, values):
        value = get_xsd_attribute(self.elem, attribute, default='')
        items = value.split()
        if len(items) == 1 and items[0] == "#all":
            return ' '.join(values)
        elif not all([s not in values for s in items]):
            raise XMLSchemaValueError("wrong value %r for attribute %r" % (value, attribute), self)
        return value

    def _is_namespace_allowed(self, namespace, any_namespace):
        if any_namespace == '##any' or namespace == XSI_NAMESPACE_PATH:
            return True
        elif any_namespace == '##other':
            return namespace != self.target_namespace
        else:
            any_namespaces = any_namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces

    @property
    def id(self):
        """The ``'id'`` attribute of declaration tag, ``None`` if missing."""
        return self._attrib.get('id')

    def update_attrs(self, **kwargs):
        """Updates a set of existing instance attributes."""
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise XMLSchemaAttributeError("%r object has no attribute %r" % (self, k))

    def validate(self, obj):
        """
        Validates XML data using the XSD component.
        
        :param obj: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :raises: :exc:`XMLSchemaValidationError` if the object is not valid.
        """
        for error in self.iter_errors(obj):
            raise error

    def iter_errors(self, obj):
        """
        Creates an iterator for errors generated validating XML data with 
        the XSD component.

        :param obj: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        """
        for chunk in self.iter_decode(obj):
            if isinstance(chunk, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                yield chunk

    def decode(self, obj, validate=True, **kwargs):
        """
        Decodes the object using the XSD component.
        
        :param obj: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param validate: if ``True`` validates the object against the XSD \
        component during the decoding process.
        :param kwargs: keyword arguments from the ones included in the optional \
        arguments of the :func:`XMLSchema.iter_decode`.
        :return: A dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
         a simple data type object otherwise.
        :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validate=True`` is provided.
        """
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
        Creates an iterator for decoding an object using the XSD component. Likes
        method *decode* except that does not raise any exception. Yields decoded values.
        Also :exc:`XMLSchemaValidationError` errors are yielded during decoding process
        if the *obj* is invalid.
        """
        raise NotImplementedError

    def iter_encode(self, obj, validate=True, **kwargs):
        raise NotImplementedError
