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
from .exceptions import XMLSchemaValidationError, XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaKeyError
from .qnames import XSD_ANNOTATION_TAG

XSD_VALIDATION_MODES = {'strict', 'lax', 'skip'}
"""
XML Schema validation modes
Ref.: https://www.w3.org/TR/xmlschema11-1/#key-va
"""


#
# Functions for parsing XSD components and attributes from etree elements
def get_xsd_annotation(elem):
    """
    Returns the annotation of an XSD component.

    :param elem: ElementTree's node
    :return: The first child element containing an XSD annotation, `None` if \
    the XSD information item doesn't have an annotation.
    """
    try:
        return elem[0] if elem[0].tag == XSD_ANNOTATION_TAG else None
    except (TypeError, IndexError):
        return None


def get_xsd_component(elem, required=True, strict=True):
    """
    Returns the first XSD component child, excluding the annotation.
    """
    components_iterator = iter_xsd_components(elem)
    try:
        xsd_component = next(components_iterator)
    except StopIteration:
        if required:
            raise XMLSchemaValueError("missing XSD component")
        return None
    else:
        if not strict:
            return xsd_component
        try:
            next(components_iterator)
        except StopIteration:
            return xsd_component
        else:
            raise XMLSchemaValueError("too many XSD components")


def iter_xsd_components(elem):
    """
    Returns an iterator for XSD child components, excluding the annotation.
    """
    counter = 0
    for child in elem:
        if child.tag == XSD_ANNOTATION_TAG:
            if counter > 0:
                raise XMLSchemaValueError("XSD annotation not allowed after the first position.")
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
            raise XMLSchemaKeyError("attribute {} expected".format(err), elem)
    else:
        if enumeration and value not in enumeration:
            raise XMLSchemaValueError("wrong value %r for %r attribute." % (value, attribute))
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
        raise XMLSchemaTypeError("an XML boolean value is required for attribute %r" % attribute)


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
    except TypeError:
        raise XMLSchemaTypeError("wrong type for attribute %r: %r" % (attribute, value))
    except ValueError:
        raise XMLSchemaValueError("wrong value for attribute %r: %r" % (attribute, value))
    else:
        if minimum is None or value >= minimum:
            return value
        else:
            raise XMLSchemaValueError(
                "attribute %r value must be greater or equal to %r" % (attribute, minimum)
            )


def get_xsd_derivation_attribute(elem, attribute, values):
    """
    Get a derivation attribute (maybe 'block', 'blockDefault', 'final' or 'finalDefault')
    checking the items with the values arguments. Returns a string.

    :param elem: The Element's instance.
    :param attribute: The attribute name.
    :param values: Sequence of admitted values when the attribute value is not '#all'.
    :return: A string.
    """
    value = get_xsd_attribute(elem, attribute, default='')
    items = value.split()
    if len(items) == 1 and items[0] == "#all":
        return ' '.join(values)
    elif not all([s in values for s in items]):
        raise XMLSchemaValueError("wrong value %r for attribute %r." % (value, attribute))
    return value


def get_xsd_namespace_attribute(elem):
    """
    Get the namespace attribute value for anyAttribute and anyElement declaration,
    checking if the value is conforming to the specification.
    """
    value = get_xsd_attribute(elem, 'namespace', default='##any')
    items = value.split()
    if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
        return value
    elif not all([s not in ('##any', '##other') for s in items]):
        XMLSchemaValueError("wrong value %r for 'namespace' attribute." % value)
    return value


class XsdBaseComponent(object):
    """
    Common base class for representing XML Schema components. A concrete XSD component have
    to report its validity collecting building errors and implementing the properties.

    Ref: https://www.w3.org/TR/xmlschema-ref/
    """
    def __init__(self):
        self.errors = []  # component errors

    @property
    def built(self):
        raise NotImplementedError

    @property
    def validation_attempted(self):
        """
        Ref: https://www.w3.org/TR/xmlschema-1/#e-validation_attempted
        Ref: https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validation_attempted
        """
        raise NotImplementedError

    def iter_components(self, xsd_classes=None):
        """
        Returns an iterator for traversing all descendant XSD components.

        :param xsd_classes: Returns only a specific class/classes of components, \
        otherwise returns all components.
        """
        raise NotImplementedError

    @property
    def all_errors(self):
        """
        Returns a list with the errors of the component and of its descendants.
        """
        errors = []
        for comp in self.iter_components():
            if comp.errors:
                errors.extend(comp.errors)
        return errors

    @property
    def validity(self):
        """
        Ref: https://www.w3.org/TR/xmlschema-1/#e-validity
        Ref: https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validity
        """
        if self.errors or any([comp.errors for comp in self.iter_components()]):
            return 'invalid'
        elif self.built:
            return 'valid'
        else:
            return 'notKnown'


class ValidatorMixin(object):
    """
    Mixin for implementing XML Schema validators. A derived class must implement the
    methods `iter_decode` and `iter_encode`.
    """
    def validate(self, data, use_defaults=True):
        """
        Validates XML data using the XSD component.

        :param data: the data source containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param use_defaults: Use schema's default values for filling missing data.
        :raises: :exc:`XMLSchemaValidationError` if the object is not valid.
        """
        for error in self.iter_errors(data, use_defaults=use_defaults):
            raise error

    def iter_errors(self, data, path=None, use_defaults=True):
        """
        Creates an iterator for errors generated validating XML data with
        the XSD component.

        :param data: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param path:
        :param use_defaults: Use schema's default values for filling missing data.
        """
        for chunk in self.iter_decode(data, path, validation='lax', use_defaults=use_defaults):
            if isinstance(chunk, XMLSchemaValidationError):
                yield chunk

    def is_valid(self, data, use_defaults=True):
        error = next(self.iter_errors(data, use_defaults=use_defaults), None)
        return error is None

    def decode(self, data, *args, **kwargs):
        """
        Decodes XML data using the XSD component.

        :param data: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param args: arguments that maybe passed to :func:`XMLSchema.iter_decode`.
        :param kwargs: keyword arguments from the ones included in the optional \
        arguments of the :func:`XMLSchema.iter_decode`.
        :return: A dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
         a simple data type object otherwise.
        :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validate='strict'`` is provided.
        """
        validation = kwargs.pop('validation', 'strict')
        for chunk in self.iter_decode(data, validation=validation, *args, **kwargs):
            if isinstance(chunk, XMLSchemaValidationError) and validation == 'strict':
                raise chunk
            return chunk
    to_dict = decode

    def encode(self, data, *args, **kwargs):
        validation = kwargs.pop('validation', 'strict')
        for chunk in self.iter_encode(data, validation=validation, *args, **kwargs):
            if isinstance(chunk, XMLSchemaValidationError) and validation == 'strict':
                raise chunk
            return chunk
    to_etree = encode

    def iter_decode(self, data, path=None, validation='lax', process_namespaces=True,
                    namespaces=None, use_defaults=True, decimal_type=None, converter=None,
                    dict_class=None, list_class=None):
        """
        Generator method for decoding XML data using the XSD component. Returns a data
        structure after a sequence, possibly empty, of validation or decode errors.

        Like the method *decode* except that it does not raise any exception. Yields
        decoded values. Also :exc:`XMLSchemaValidationError` errors are yielded during
        decoding process if the *obj* is invalid.
        """
        raise NotImplementedError

    def iter_encode(self, data, path=None, validation='lax', namespaces=None, indent=None,
                    element_class=None, converter=None):
        raise NotImplementedError
