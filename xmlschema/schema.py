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
This module contains XMLSchema class creator for xmlschema package.
"""
import logging
import os.path

from .core import (
    XSD_NAMESPACE_PATH, XML_NAMESPACE_PATH, XSI_NAMESPACE_PATH, XLINK_NAMESPACE_PATH,
    XHTML_NAMESPACE_PATH, HFP_NAMESPACE_PATH, etree_get_namespaces
)
from .exceptions import (
    XMLSchemaValueError, XMLSchemaTypeError, XMLSchemaParseError,
    XMLSchemaValidationError, XMLSchemaDecodeError, XMLSchemaURLError
)
from .utils import URIDict
from .xsdbase import (
    check_tag, get_xsi_schema_location, XSD_SCHEMA_TAG, update_xsd_attributes,
    update_xsd_attribute_groups, update_xsd_simple_types, update_xsd_complex_types,
    update_xsd_groups, update_xsd_elements, xsd_include_schemas, iterfind_xsd_imports
)
from .resources import open_resource, load_xml_resource
from .facets import XSD_v1_0_FACETS
from .builtins import XSD_BUILTIN_TYPES
from .factories import (
    xsd_simple_type_factory, xsd_restriction_factory, xsd_attribute_factory,
    xsd_attribute_group_factory, xsd_complex_type_factory,
    xsd_element_factory, xsd_group_factory
)

logger = logging.getLogger(__name__)


DEFAULT_OPTIONS = {
    'inclusion_method': xsd_include_schemas,
    'simple_type_factory': xsd_simple_type_factory,
    'attribute_factory': xsd_attribute_factory,
    'attribute_group_factory': xsd_attribute_group_factory,
    'complex_type_factory': xsd_complex_type_factory,
    'group_factory': xsd_group_factory,
    'element_factory': xsd_element_factory,
    'restriction_factory': xsd_restriction_factory
}
"""Default options for building XSD schema elements."""

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')


def create_validator(version=None, meta_schema=None, base_schemas=None, facets=None,
                     builtin_types=None, **options):

    if base_schemas is None:
        base_schemas = {}
    else:
        base_schemas = {k: os.path.join(SCHEMAS_DIR, v) for k, v in base_schemas.items()}

    validator_options = dict(DEFAULT_OPTIONS.items())
    for opt in validator_options:
        if opt in options:
            validator_options[opt] = options[opt]

    class XMLSchemaValidator(object):
        """
        Class to wrap an XML Schema for components lookups and conversion.
        """
        VERSION = version
        META_SCHEMA = None
        BASE_SCHEMAS = URIDict(base_schemas or ())
        FACETS = facets or ()
        OPTIONS = validator_options

        include_schemas = OPTIONS.pop('inclusion_method')

        def __init__(self, schema, check_schema=False, imported_schemas=None):
            """
            Initialize an XML schema instance.

            :param schema: This could be a string containing the schema, an URI
            that reference to a schema definition, a path to a file containing
            the schema or a file-like object containing the schema.
            """
            try:
                self._root, self.text, self.uri = load_xml_resource(schema, element_only=False)
            except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                raise type(err)('cannot create schema: %s' % err)

            check_tag(self._root, XSD_SCHEMA_TAG)
            if check_schema and self.META_SCHEMA is not None:
                self.check_schema(self._root)

            self.target_namespace = self._root.attrib.get('targetNamespace', '')
            self.element_form = self._root.attrib.get('elementFormDefault', 'unqualified')
            self.attribute_form = self._root.attrib.get('attributeFormDefault', 'unqualified')
            self._schema_location = get_xsi_schema_location(self._root)

            if isinstance(imported_schemas, URIDict):
                self.imported_schemas = imported_schemas
            elif self.META_SCHEMA is not None:
                self.imported_schemas = URIDict(self.BASE_SCHEMAS)
            else:
                self.imported_schemas = self.BASE_SCHEMAS
            self.imported_schemas[self.target_namespace] = self
            self.included_schemas = URIDict()

            if self.target_namespace == XSD_NAMESPACE_PATH:
                self.types = builtin_types.copy()
            else:
                self.types = {}
            self.attributes = {}
            self.attribute_groups = {}
            self.groups = {}
            self.elements = {}  # Global elements
            self.base_elements = {}  # Global elements + global groups expansion

            # Extract namespaces from schema and include subschemas
            self.namespaces = {'xml': XML_NAMESPACE_PATH}  # the 'xml' namespace is implicit
            namespaces = etree_get_namespaces(self.text)
            self.namespaces.update(namespaces)
            self.include_schemas(self._root, check_schema)
            self.import_schemas(self._root, check_schema)
            if '' not in self.namespaces:
                try:
                    self.namespaces[''] = self.imported_schemas[''].target_namespace
                    # Local namespace is explicitly declared (eg. xmlns="...")
                except KeyError:
                    self.namespaces[''] = self.target_namespace
                    # Local namespace default is targetNamespace

            # Import all namespaces used by the schema
            for prefix, uri in namespaces:
                uri = self.namespaces[prefix]
                if uri != self.target_namespace:
                    self.import_namespace(uri, self._schema_location)

            self.update_schema(self._root)

        def __repr__(self):
            return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.target_namespace, id(self))

        @property
        def target_prefix(self):
            for prefix, namespace in self.namespaces.items():
                if namespace == self.target_namespace:
                    return prefix
            return ''

        @classmethod
        def create_schema(cls, *args, **kwargs):
            return cls(*args, **kwargs)

        @classmethod
        def check_schema(cls, schema):
            for error in cls.META_SCHEMA.iter_errors(schema):
                raise error

        def import_namespace(self, uri, locations=None, check_schema=False):
            locations = locations or uri
            try:
                if isinstance(self.imported_schemas[uri], self.__class__):
                    return
            except KeyError:
                if not locations:
                    raise XMLSchemaValueError("No namespace or locations, cannot import!")
            else:
                locations = self.imported_schemas[uri]

            try:
                schema_res, schema_uri = open_resource(locations, self.uri)
            except XMLSchemaURLError as err:
                raise XMLSchemaURLError(reason="cannot import namespace %r: %s" % (uri, err.reason))
            else:
                schema_res.close()

            try:
                schema = self.create_schema(schema_uri, check_schema, self.imported_schemas)
            except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                raise type(err)('cannot import namespace %r: %s' % (uri, err))
            except XMLSchemaURLError as err:
                raise XMLSchemaURLError(reason="cannot import namespace %r: %s" % (uri, err.reason))
            else:
                if schema.target_namespace != uri:
                    raise XMLSchemaParseError(
                        "wrong namespace %r for imported schema %r." % (uri, schema)
                    )

        def import_schemas(self, elements, check_schema=False):
            for elem in iterfind_xsd_imports(elements, namespaces=self.namespaces):
                uri = elem.attrib.get('namespace', '')
                locations = elem.attrib.get('schemaLocation')
                if locations is not None:
                    self.import_namespace(uri, locations, check_schema)

        def update_schema(self, elements):
            kwargs = self.OPTIONS.copy()

            # Parse global declarations
            update_xsd_simple_types(self, self.types, elements, **kwargs)
            update_xsd_attributes(self, self.attributes, elements, **kwargs)
            update_xsd_attribute_groups(self, self.attribute_groups, elements, **kwargs)
            update_xsd_complex_types(self, self.types, elements, **kwargs)
            update_xsd_elements(self, self.elements, elements, **kwargs)
            update_xsd_groups(self, self.groups, elements, **kwargs)

            # Parse other local declarations
            update_xsd_groups(self, self.groups, elements, parse_content_type=True, **kwargs)
            update_xsd_complex_types(self, self.types, elements, parse_content_type=True, **kwargs)
            update_xsd_elements(self, self.elements, elements, parse_content_type=True, **kwargs)

            # Update base_elements
            self.base_elements.update(self.elements)
            for v in self.groups.values():
                self.base_elements.update({e.name: e for e in v.iter_elements()})

        def validate(self, *args, **kwargs):
            for error in self.iter_errors(*args, **kwargs):
                raise error

        def is_valid(self, xml_document):
            error = next(self.iter_errors(xml_document), None)
            return error is None

        def iter_errors(self, xml_document):
            for chunk in self.iter_decode(xml_document):
                if isinstance(chunk, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    yield chunk

        def iter_decode(self, xml_document):
            xml_root = load_xml_resource(xml_document)
            try:
                xsd_element = self.elements[xml_root.tag]
            except KeyError:
                yield XMLSchemaValidationError(
                    self, xml_root.tag, "not a global element of the schema of the schema!", xml_root
                )
            else:
                for obj in xsd_element.iter_decode(xml_root):
                    yield obj

        def to_dict(self, xml_document):
            xml_root = load_xml_resource(xml_document)
            return self.elements[xml_root.tag].decode(xml_root)

    # Create the meta schema
    if meta_schema is not None:
        meta_schema = XMLSchemaValidator(os.path.join(SCHEMAS_DIR, meta_schema))
        for k, v in list(meta_schema.imported_schemas.items()):
            if not isinstance(v, XMLSchemaValidator):
                meta_schema.imported_schemas[k] = XMLSchemaValidator(v)

        XMLSchemaValidator.META_SCHEMA = meta_schema

    if version is not None:
        XMLSchemaValidator.__name__ = 'XMLSchema_{}'.format(version.replace(".", "_"))

    return XMLSchemaValidator


# Define classes for generic XML schemas
XMLSchema_v1_0 = create_validator(
    version='1.0',
    meta_schema='XSD_1.0/XMLSchema.xsd https://www.w3.org/2001/XMLSchema.xsd',
    base_schemas={
        XML_NAMESPACE_PATH: 'xml_minimal.xsd http://www.w3.org/2001/xml.xsd',
        HFP_NAMESPACE_PATH: 'XMLSchema-hasFacetAndProperty_minimal.xsd '
                            'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty',
        XHTML_NAMESPACE_PATH: 'xhtml1-strict.xsd '
                              'http://www.w3.org/2002/08/xhtml/xhtml1-strict.xsd',
        XSI_NAMESPACE_PATH: 'XMLSchema-instance_minimal.xsd '
                            'http://www.w3.org/2001/XMLSchema-instance',
        XLINK_NAMESPACE_PATH: 'xlink.xsd https://www.w3.org/1999/xlink.xsd',
    },
    facets=XSD_v1_0_FACETS,
    builtin_types=XSD_BUILTIN_TYPES
)
XMLSchema = XMLSchema_v1_0


def validate(xml_document, schema=None, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    xml_root, xml_text, xml_uri = load_xml_resource(xml_document, element_only=False)
    if schema is None:
        schema = open_resource(get_xsi_schema_location(xml_root), xml_uri)

    cls(schema, check_schema=True, *args, **kwargs).validate(xml_root)


def to_dict(xml_document, schema=None, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    xml_root, xml_text, xml_uri = load_xml_resource(xml_document, element_only=False)
    if schema is None:
        schema = open_resource(get_xsi_schema_location(xml_root), xml_uri)

    cls(schema, *args, **kwargs).validate(xml_root)
    return cls(schema, check_schema=True, *args, **kwargs).to_dict(xml_root)
