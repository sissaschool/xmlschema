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
from __future__ import unicode_literals
import json

from .compat import ordered_dict_class
from .resources import fetch_schema_locations
from .validators.schema import XMLSchema


def validate(xml_document, schema=None, cls=None, use_defaults=True, namespaces=None, locations=None, base_url=None):
    """
    Validates an XML document against a schema instance. This function builds an
    :class:`XMLSchema` object for validating the XML document. Raises an
    :exc:`XMLSchemaValidationError` if the XML document is not validated against
    the schema.

    :param xml_document: can be a file-like object or a string containing the XML data \
    or a file path or a URL of a resource or an ElementTree/Element instance.
    :param schema: can be a schema instance or a file-like object or a file path or a URL \
    of a resource or a string containing the schema.
    :param cls: schema class to use for building the instance (for default uses :class:`XMLSchema`).
    :param use_defaults: defines when to use elements and attribute defaults for filling \
    missing required values.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :param locations: additional schema location hints, in case a schema instance has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    """
    cls = XMLSchema if cls is None else XMLSchema
    if schema is None:
        schema, locations = fetch_schema_locations(xml_document, locations, base_url=base_url)
        schema = cls(schema, validation='strict', locations=locations)
    elif not isinstance(schema, XMLSchema):
        schema = cls(schema, validation='strict', locations=locations, base_url=base_url)
    schema.validate(xml_document, use_defaults, namespaces)


def to_dict(xml_document, schema=None, cls=None, path=None, process_namespaces=True,
            locations=None, base_url=None, **kwargs):
    """
    Decodes an XML document to a Python's nested dictionary. The decoding is based
    on an XML Schema class instance. For default the document is validated during
    the decoding phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

    :param xml_document: can be a file-like object or a string containing the XML data \
    or a file path or a URL of a resource or an ElementTree/Element instance.
    :param schema: can be a schema instance or a file-like object or a file path or a URL \
    of a resource or a string containing the schema.
    :param cls: schema class to use for building the instance (for default uses :class:`XMLSchema`).
    :param path: is an optional XPath expression that matches the subelement of the document \
    that have to be decoded. The XPath expression considers the schema as the root element \
    with global elements as its children.
    :param process_namespaces: indicates whether to use namespace information in the decoding process.
    :param locations: additional schema location hints, in case a schema instance has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    :param kwargs: optional arguments of :meth:`XMLSchema.iter_decode` as keyword arguments \
    to variate the decoding process.
    :return: an object containing the decoded data. If ``validation='lax'`` keyword argument \
    is provided the validation errors are collected and returned coupled in a tuple with the \
    decoded data.
    :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
    the XSD component, or also if it's invalid when ``validation='strict'`` is provided.

    """
    cls = XMLSchema if cls is None else XMLSchema
    if schema is None:
        schema, locations = fetch_schema_locations(xml_document, locations, base_url=base_url)
        schema = cls(schema, validation='strict', locations=locations)
    elif not isinstance(schema, XMLSchema):
        schema = cls(schema, validation='strict', locations=locations, base_url=base_url)
    return schema.to_dict(xml_document, path=path, process_namespaces=process_namespaces, **kwargs)


def to_json(xml_document, fp=None, schema=None, cls=None, path=None, converter=None,
            process_namespaces=True, locations=None, base_url=None, json_options=None, **kwargs):
    """
    Serialize an XML document to JSON. For default the XML data is validated during
    the decoding phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

    :param xml_document: can be a file-like object or a string containing the XML data \
    or a file path or an URI of a resource or an ElementTree/Element instance.
    :param fp: can be a :meth:`write()` supporting file-like object.
    :param schema: can be a schema instance or a file-like object or a file path or an URL \
    of a resource or a string containing the schema.
    :param cls: schema class to use for building the instance (for default uses :class:`XMLSchema`).
    :param path: is an optional XPath expression that matches the subelement of the document \
    that have to be decoded. The XPath expression considers the schema as the root element \
    with global elements as its children.
    :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the decoding.
    :param process_namespaces: indicates whether to use namespace information in the decoding process.
    :param locations: additional schema location hints, in case a schema instance has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    :param json_options: a dictionary with options for the JSON serializer.
    :param kwargs: optional arguments of :meth:`XMLSchema.iter_decode` as keyword arguments \
    to variate the decoding process.
    :return: a string containing the JSON data if *fp* is `None`, otherwise doesn't return anything. \
    If ``validation='lax'`` keyword argument is provided the validation errors are collected and \
    returned, eventually coupled in a tuple with the JSON data.
    :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
    the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
    """
    cls = XMLSchema if cls is None else XMLSchema
    if schema is None:
        schema, locations = fetch_schema_locations(xml_document, locations, base_url=base_url)
        schema = cls(schema, validation='strict', locations=locations)
    elif not isinstance(schema, XMLSchema):
        schema = cls(schema, validation='strict', locations=locations, base_url=base_url)
    if json_options is None:
        json_options = {}

    decimal_type = kwargs.pop('decimal_type', float)
    dict_class = kwargs.pop('dict_class', ordered_dict_class)
    obj = schema.to_dict(xml_document, path=path, decimal_type=decimal_type, dict_class=dict_class,
                         process_namespaces=process_namespaces, converter=converter, **kwargs)

    if isinstance(obj, tuple):
        if fp is not None:
            json.dump(obj[0], fp, **kwargs)
            return tuple(obj[1])
        else:
            return json.dumps(obj[0], **json_options), tuple(obj[1])
    elif fp is not None:
        json.dump(obj, fp, **json_options)
    else:
        return json.dumps(obj, **json_options)


def from_json(source, schema, path=None, converter=None, json_options=None, **kwargs):
    """
    Deserialize JSON data to an XML Element.

    :param source: can be a string or a :meth:`read()` supporting file-like object \
    containing the JSON document.
    :param schema: an :class:`XMLSchema` instance.
    :param path: is an optional XPath expression for selecting the element of the schema \
    that matches the data that has to be encoded. For default the first global element of \
    the schema is used.
    :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the encoding.
    :param json_options: a dictionary with options for the JSON deserializer.
    :param kwargs: Keyword arguments containing options for converter and encoding.
    :return: An element tree's Element instance. If ``validation='lax'`` keyword argument is \
    provided the validation errors are collected and returned coupled in a tuple with the \
    Element instance.
    :raises: :exc:`XMLSchemaValidationError` if the object is not encodable by the schema, \
    or also if it's invalid when ``validation='strict'`` is provided.
    """
    if not isinstance(schema, XMLSchema):
        raise TypeError("An XMLSchema instance required for 'schema' argument: %r" % schema)
    elif json_options is None:
        json_options = {}

    dict_class = kwargs.pop('dict_class', ordered_dict_class)
    object_hook = json_options.pop('object_hook', ordered_dict_class)
    object_pairs_hook = json_options.pop('object_pairs_hook', ordered_dict_class)
    if hasattr(source, 'read'):
        obj = json.load(source, object_hook=object_hook, object_pairs_hook=object_pairs_hook, **json_options)
    else:
        obj = json.loads(source, object_hook=object_hook, object_pairs_hook=object_pairs_hook, **json_options)

    return schema.encode(obj, path=path, converter=converter, dict_class=dict_class, **kwargs)
