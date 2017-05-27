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

from .core import PY3
from .qnames import *
from .exceptions import (
    XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaLookupError,
    XMLSchemaParseError, XMLSchemaAttributeError, XMLSchemaValidationError,
    XMLSchemaEncodeError, XMLSchemaDecodeError
)
from .utils import FrozenDict


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
def check_tag(elem, *tags):
    if elem.tag not in tags:
        tags = (split_qname(tag)[1] for tag in tags)
        raise XMLSchemaParseError("({}) expected: {}".format('|'.join(tags), elem))


def check_attrs(obj, *attrs):
    for attr in attrs:
        try:
            getattr(obj, attr)
        except AttributeError as err:
            raise XMLSchemaAttributeError(err.message)


def check_type(obj, *types):
    if not isinstance(obj, types):
        raise XMLSchemaTypeError(
            "wrong type %s, it must be one of %r." % (type(obj), types)
        )


def check_value(value, *values):
    if value not in values:
        raise XMLSchemaValueError(
            "wrong value %s, it must be None or one of %r." % (value, values)
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
    except (TypeError, IndexError):
        return None


def get_xsd_component(elem, required=True, strict=True):
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
                raise XMLSchemaParseError("XSD annotation not allowed here!", elem)
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
        raise XMLSchemaParseError(
            "an XML boolean value is required for attribute %r" % attribute, elem
        )


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
        raise XMLSchemaValueError("attribute %r error: %r" % (attribute, str(err)), elem)
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
        raise XMLSchemaLookupError("missing XSD reference %r!" % qname)
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


class XsdBase(object):
    """
    Base class for XML Schema Definition classes.

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
        elif not all([s in values for s in items]):
            raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute), self)
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


class XsdAnnotation(XsdBase):
    """
    Class for XSD 'annotation' definitions.
    
    <annotation
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (appinfo | documentation)*
    </annotation>
    
    <appinfo
      source = anyURI
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </appinfo>
    
    <documentation
      source = anyURI
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </documentation>

    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
    """
    def __init__(self, elem=None, schema=None):
        super(XsdAnnotation, self).__init__(elem, schema)

    def __setattr__(self, name, value):
        if name == 'elem':
            check_tag(value, XSD_ANNOTATION_TAG)
            self.appinfo = []
            self.documentation = []
            for child in value:
                if child.tag == XSD_APPINFO_TAG:
                    for key in child.attrib:
                        if key != 'source':
                            raise XMLSchemaParseError(
                                "wrong attribute %r for appinfo declaration." % key, self
                            )
                    self.appinfo.append(child)
                elif child.tag == XSD_DOCUMENTATION_TAG:
                    for key in child.attrib:
                        if key not in ['source', XML_LANG]:
                            raise XMLSchemaParseError(
                                "wrong attribute %r for documentation declaration." % key, self
                            )
                    self.documentation.append(child)
        super(XsdAnnotation, self).__setattr__(name, value)


class XsdComponent(XsdBase):
    """
    XML Schema component base class.

    :param name: A name associated with the component definition/declaration..
    :param elem: ElementTree's node containing the definition.
    :param schema: The XMLSchema object that owns the definition.
    """

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
                self.annotation = XsdAnnotation(annotation, self.schema)
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


class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t
    """
    def __setattr__(self, name, value):
        super(ParticleMixin, self).__setattr__(name, value)
        if name == 'elem':
            max_occurs = self.max_occurs
            if max_occurs is not None and self.min_occurs > max_occurs:
                raise XMLSchemaParseError(
                    "maxOccurs must be 'unbounded' or greater than minOccurs:", self
                )

    @property
    def min_occurs(self):
        return get_xsd_int_attribute(getattr(self, 'elem'), 'minOccurs', default=1, minimum=0)

    @property
    def max_occurs(self):
        try:
            return get_xsd_int_attribute(getattr(self, 'elem'), 'maxOccurs', default=1, minimum=0)
        except (TypeError, ValueError):
            if getattr(self, '_attrib')['maxOccurs'] == 'unbounded':
                return None
            raise

    def is_optional(self):
        return getattr(self, 'elem').get('minOccurs', '').strip() == "0"

    def is_emptiable(self):
        return self.min_occurs == 0
