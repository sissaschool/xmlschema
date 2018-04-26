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
from .exceptions import XMLSchemaException, XMLSchemaRegexError, XMLSchemaURLError
from .etree import etree_get_namespaces
from .resources import fetch_resource, load_xml_resource, fetch_schema, fetch_schema_locations, normalize_url
from .converters import (
    XMLSchemaConverter, ParkerConverter, BadgerFishConverter, AbderaConverter, JsonMLConverter
)

from .validators.exceptions import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaDecodeError,
    XMLSchemaEncodeError, XMLSchemaNotBuiltError, XMLSchemaChildrenValidationError
)
from .validators.schema import XsdGlobals, XMLSchemaBase, XMLSchema, XMLSchema_v1_0, create_validator

__version__ = '0.9.27'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2018, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"


def validate(xml_document, schema=None, cls=XMLSchema, use_defaults=True, locations=None):
    """
    Validates an XML document against a schema instance. This function builds an
    :class:`XMLSchema` object for validating the XML document. Raises an
    :exc:`XMLSchemaValidationError` if the XML document is not validated against
    the schema.

    :param xml_document: can be a file-like object or a string containing the XML data \
    or a file path or an URI of a resource or an ElementTree/Element instance.
    :param schema: can be a file-like object or a file path or an URI of a resource or \
    a string containing the schema.
    :param cls: schema class to use for building the instance (default is :class:`XMLSchema`).
    :param use_defaults: defines when to use elements and attribute defaults for filling \
    missing required values.
    :param locations: Schema location hints.
    :return:
    """
    if schema is None:
        schema, locations = fetch_schema_locations(xml_document, locations)
    cls(schema, validation='strict', locations=locations).validate(xml_document, use_defaults)


def to_dict(xml_document, schema=None, cls=XMLSchema, path=None, process_namespaces=True, locations=None, **kwargs):
    """
    Decodes an XML document to a Python's nested dictionary. The decoding is based
    on an XML Schema class instance. For default the document is validated during
    the decode phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

    :param xml_document:can be a file-like object or a string containing the XML data \
    or a file path or an URI of a resource or an ElementTree/Element instance.
    :param schema: can be a file-like object or a file path or an URI of a resource or \
    a string containing the schema.
    :param cls: schema class to use for building the instance (default is :class:`XMLSchema`).
    :param path: is an optional XPath expression that matches the subelement of the document \
    that have to be decoded. The XPath expression considers the schema as the root element \
    with global elements as its children.
    :param process_namespaces: indicates whether to get the namespaces from the XML \
    document and use them in the decoding process.
    :param locations: Schema location hints.
    :param kwargs: optional arguments of :meth:`XMLSchema.iter_decode` as keyword arguments \
    to variate the decoding process.
    :return:
    """
    if schema is None:
        schema, locations = fetch_schema_locations(xml_document, locations)
    return cls(schema, validation='strict', locations=locations).to_dict(
        xml_document, path=path, process_namespaces=process_namespaces, **kwargs
    )
