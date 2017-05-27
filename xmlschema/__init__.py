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
from .core import set_logger, etree_get_namespaces
from .exceptions import (
    XMLSchemaException, XMLSchemaParseError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaEncodeError, XMLSchemaXPathError,
    XMLSchemaRegexError
)
from .resources import open_resource, load_xml_resource
from .xsdbase import get_xsi_schema_location
from .schema import XsdGlobals, XMLSchema

__version__ = '0.9.8'
__author__ = "Davide Brunato"
__contact__ = "brunato@sissa.it"
__copyright__ = "Copyright 2016-2017, SISSA"
__license__ = "MIT"
__status__ = "Production/Stable"

set_logger(__name__)


def validate(xml_document, schema=None, cls=None, use_defaults=True):
    if cls is None:
        cls = XMLSchema
    xml_root, xml_text, xml_uri = load_xml_resource(xml_document, element_only=False)
    if schema is None:
        namespace, location = get_xsi_schema_location(xml_root).split()
        schema_resource, schema = open_resource(location, xml_uri)
        schema_resource.close()
    cls(schema, check_schema=True).validate(xml_root, use_defaults)


def to_dict(xml_document, schema=None, cls=None, path=None, process_namespaces=True, **kwargs):
    if cls is None:
        cls = XMLSchema
    xml_root, xml_text, xml_uri = load_xml_resource(xml_document, element_only=False)
    if schema is None:
        namespace, location = get_xsi_schema_location(xml_root).split()
        schema_resource, schema = open_resource(location, xml_uri)
        schema_resource.close()
    return cls(schema, check_schema=True).to_dict(xml_root, path, process_namespaces, **kwargs)
