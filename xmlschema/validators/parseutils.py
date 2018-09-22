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
This module contains utility functions and classes.
"""
from __future__ import unicode_literals
from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaKeyError
from ..qnames import XSD_ANNOTATION_TAG


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


def iter_xsd_components(elem, start=0):
    """
    Returns an iterator for XSD child components, excluding the annotation.
    """
    counter = 0
    for child in elem:
        if child.tag == XSD_ANNOTATION_TAG:
            if counter > 0:
                raise XMLSchemaValueError("XSD annotation not allowed after the first position.")
        else:
            if start > 0:
                start -= 1
            else:
                yield child
            counter += 1


def has_xsd_components(elem, start=0):
    try:
        next(iter_xsd_components(elem, start))
    except StopIteration:
        return False
    else:
        return True


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


def get_xpath_default_namespace(elem, default_namespace, target_namespace, default=None):
    """
    Get the xpathDefaultNamespace attribute value for alternative, assert, assertion, selector
    and field XSD 1.1 declarations, checking if the value is conforming to the specification.
    """
    try:
        value = get_xsd_attribute(elem, 'xpathDefaultNamespace').strip()
    except KeyError:
        return

    if value == '##local':
        return ''
    elif value == '##defaultNamespace':
        return default_namespace
    elif value == '##targetNamespace':
        return target_namespace
    elif value is None:
        return default
    elif len(value.split()) == 1:
        return value.strip()
    else:
        admitted_values = ('##defaultNamespace', '##targetNamespace', '##local')
        msg = "wrong value %r for 'xpathDefaultNamespace' attribute, can be (anyURI | %r)."
        raise XMLSchemaValueError(msg % (value, '|'.join(admitted_values)))
