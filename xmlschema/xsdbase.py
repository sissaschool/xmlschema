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

from .core import PY3
from .qnames import *
from .exceptions import (
    XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaLookupError,
    XMLSchemaAttributeError, XMLSchemaParseError, XMLSchemaComponentError,
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError
)
from .utils import FrozenDict


_logger = _logging.getLogger(__name__)


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
    except (TypeError, IndexError):
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
    except (KeyError, AttributeError) as err:
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


def xsd_factory(*args):
    """
    Check Element instance passed to a factory and log arguments.

    :param args: Values admitted for Element's tag (base argument of the factory)
    """
    def make_factory_wrapper(factory_function):
        def xsd_factory_wrapper(elem, schema, instance=None, **kwargs):
            if _logger.getEffectiveLevel() == _logging.DEBUG:
                _logger.debug(
                    "%s: elem.tag='%s', elem.attrib=%r, kwargs.keys()=%r",
                    factory_function.__name__, elem.tag, elem.attrib, kwargs.keys()
                )
                check_tag(elem, *args)
                factory_result = factory_function(elem, schema, instance, **kwargs)
                _logger.debug("%s: return %r", factory_function.__name__, factory_result)
                return factory_result
            check_tag(elem, *args)
            try:
                result = factory_function(elem, schema, instance, **kwargs)
            except XMLSchemaValidationError as err:
                raise XMLSchemaParseError(err.message, elem)
            else:
                if instance is not None:
                    if isinstance(result, tuple):
                        if instance.name is not None and instance.name != result[0]:
                            raise XMLSchemaParseError(
                                "name mismatch wih instance %r: %r." % (instance, result[0]), elem
                            )
                    if instance.elem is None:
                        instance.elem = elem
                    if instance.schema is None:
                        instance.schema = schema
                return result

        return xsd_factory_wrapper
    return make_factory_wrapper


@xsd_factory(XSD_ANNOTATION_TAG)
def xsd_annotation_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'annotation' declarations.

    <annotation
        id = ID
        {any attributes with non-schema Namespace}...>
    Content: (appinfo | documentation)*
    </annotation>
    """
    appinfo = []
    documentation = []
    for child in elem:
        if child.tag == XSD_APPINFO_TAG:
            for key in child.attrib:
                if key != 'source':
                    raise XMLSchemaParseError(
                        "wrong attribute %r for appinfo declaration." % key, child
                    )
            appinfo.append(child)
        elif child.tag == XSD_DOCUMENTATION_TAG:
            for key in child.attrib:
                if key not in ['source', XML_LANG]:
                    raise XMLSchemaParseError(
                        "wrong attribute %r for documentation declaration." % key, child
                    )
            documentation.append(child)
    return XsdAnnotation(elem, schema, appinfo, documentation)


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

    def __init__(self, elem=None, schema=None):
        self.schema = schema
        self.elem = elem

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
        return u"<%s at %#x>" % (self.__class__.__name__, id(self))

    def __str__(self):
        # noinspection PyCompatibility
        return unicode(self).encode("utf-8")

    def __unicode__(self):
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


class XsdAnnotation(XsdBase):
    """
    Class for XML Schema annotation definitions.
    """

    def __init__(self, elem=None, schema=None, appinfo=None, documentation=None):
        super(XsdAnnotation, self).__init__(elem, schema)
        self.appinfo = appinfo if appinfo is not None else []
        self.documentation = documentation if documentation is not None else []


class XsdComponent(XsdBase):

    def __init__(self, name=None, elem=None, schema=None):
        self.name = name
        super(XsdComponent, self).__init__(elem, schema)

    def __repr__(self):
        return u"<%s %r at %#x>" % (self.__class__.__name__, self.name, id(self))

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


    def __setattr__(self, name, value):
        if name == "elem":
            annotation = get_xsd_annotation(value)
            if annotation is not None:
                self.annotation = xsd_annotation_factory(annotation, self.schema)
            else:
                self.annotation = None

        super(XsdComponent, self).__setattr__(name, value)

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
