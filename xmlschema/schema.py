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

from .core import (
    XSD_NAMESPACE_PATH, XML_NAMESPACE_PATH, XSI_NAMESPACE_PATH, BASE_SCHEMAS, etree_get_namespaces, URIDict
)
from .exceptions import XMLSchemaValueError, XMLSchemaLookupError
from .utils import get_namespace, split_path, get_qualified_path, get_qname
from .xsdbase import (
    check_tag, XSD_SCHEMA_TAG, xsd_include_schemas, iterfind_xsd_imports, lookup_attribute,
    update_xsd_attributes, update_xsd_attribute_groups, update_xsd_simple_types,
    update_xsd_complex_types, update_xsd_groups, update_xsd_elements
)
from .resources import load_resource, load_xml
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


XSI_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'schemaLocation')
XSI_NONS_SCHEMA_LOCATION = get_qname(XSI_NAMESPACE_PATH, 'noNamespaceSchemaLocation')


def create_validator(version=None, meta_schema=None, base_schemas=None, facets=None,
                     builtin_types=None, **options):

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

        def __init__(self, schema, check_schema=False):
            """
            Initialize an XML schema instance.

            :param schema: This could be a string containing the schema, an URI
            that reference to a schema definition, a path to a file containing
            the schema or a file-like object containing the schema.
            """
            self._root, self.text, self.uri = load_xml(schema)
            check_tag(self._root, XSD_SCHEMA_TAG)
            if check_schema and self.META_SCHEMA is not None:
                self.check_schema(self._root)

            self.target_namespace = self._root.attrib.get('targetNamespace', '')
            self.element_form = self._root.attrib.get('elementFormDefault', 'unqualified')
            self.attribute_form = self._root.attrib.get('attributeFormDefault', 'unqualified')
            self._schema_location = self._root.attrib.get(XSI_SCHEMA_LOCATION)

            if self.META_SCHEMA is not None:
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
            self.elements = {}

            # Extract namespaces from schema and include subschemas
            self.namespaces = {'xml': XML_NAMESPACE_PATH}  # the 'xml' namespace is required by XSD
            namespaces = etree_get_namespaces(self.text)
            self.namespaces.update(namespaces)
            self.include_schemas(self._root)
            self.import_schemas(self._root)

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
        def create_schema(cls, schema):
            return cls(schema)

        @classmethod
        def check_schema(cls, schema):
            for error in cls.META_SCHEMA.iter_errors(schema):
                raise error

        def import_namespace(self, uri, locations=None):
            locations = locations or uri
            if not locations:
                raise XMLSchemaValueError("No namespace or locations, cannot import!")
            try:
                if isinstance(self.imported_schemas[uri], str):
                    # The value is a path of the BASE_SCHEMA dictionary
                    self.imported_schemas[uri] = self.create_schema(self.imported_schemas[uri])
            except KeyError:
                try:
                    schema, schema_uri = load_resource(locations, self.uri)
                except (OSError, IOError, ValueError) as err:
                    raise XMLSchemaValueError(
                        "%r: cannot import namespace %r: %s" % (self, uri, err)
                    )
                else:
                    self.imported_schemas[uri] = self.create_schema(schema_uri)

        def import_schemas(self, elements):
            for elem in iterfind_xsd_imports(elements, namespaces=self.namespaces):
                uri = elem.attrib.get('namespace', '')
                locations = elem.attrib.get('schemaLocation')
                if locations is not None:
                    self.import_namespace(uri, locations)

        def update_schema(self, elements, path=None):
            kwargs = self.OPTIONS.copy()

            # Parse global declarations
            update_xsd_simple_types(self, self.types, elements, path=path, **kwargs)
            update_xsd_attributes(self, self.attributes, elements, path=path, **kwargs)
            update_xsd_attribute_groups(self, self.attribute_groups, elements, **kwargs)
            update_xsd_complex_types(self, self.types, elements, path=path, **kwargs)
            update_xsd_elements(self, self.elements, elements, path=path, **kwargs)
            update_xsd_groups(self, self.groups, elements, path=path, **kwargs)

            # Parse other local declarations
            update_xsd_groups(self, self.groups, elements, path=path, parse_content_type=True, **kwargs)
            update_xsd_groups(self, self.groups, elements, path=path, parse_content_type=True, **kwargs)
            update_xsd_complex_types(self, self.types, elements, path=path, parse_content_type=True, **kwargs)
            update_xsd_elements(self, self.elements, elements, path=path, parse_content_type=True, **kwargs)

        def get_element(self, path):
            qualified_path = get_qualified_path(path, self.target_namespace)
            elements = split_path(qualified_path)
            if not elements:
                raise XMLSchemaValueError("empty path!")
            try:
                target_element = self.elements[elements[0]]
            except KeyError:
                import pdb
                pdb.set_trace()
                raise XMLSchemaLookupError(path)

            for name in elements[1:]:
                try:
                    for xsd_element in target_element.type.content_type.iter_elements():
                        if xsd_element.name == name:
                            if xsd_element.ref:
                                target_element = self.elements[name]
                            else:
                                target_element = xsd_element
                            break
                    else:
                        raise XMLSchemaLookupError(path)
                except AttributeError:
                    raise XMLSchemaLookupError(path)
            return target_element

        def get_attribute(self, name, path):
            if name[0] != '{':
                return self.get_element(path).get_attribute(get_qname(self.target_namespace, name))

            namespace = get_namespace(name)
            if namespace != self.target_namespace:
                return lookup_attribute(name, namespace, self.imported_schemas)
            else:
                return self.get_element(path).get_attribute(name)

        def get_attributes(self, path):
            element = self.get_element(path)
            try:
                return element.xsd_type.attributes.keys()
            except AttributeError:
                return tuple()

        def validate(self, *args, **kwargs):
            for error in self.iter_errors(*args, **kwargs):
                raise error

        def is_valid(self, xml_document, schema=None):
            error = next(self.iter_errors(xml_document, schema), None)
            return error is None

        def iter_errors(self, xml_document, schema=None):
            xml_root = load_xml(xml_document)[0]
            schema = schema or self
            root_path = get_qname(schema.target_namespace, xml_root.tag)
            xsd_element = schema.get_element(root_path)
            for error in xsd_element.iter_errors(xml_root):
                yield error

        def iter_decode(self, xml_document, schema=None):
            xml_root = load_xml(xml_document)[0]
            schema = schema or self
            root_path = get_qname(schema.target_namespace, xml_root.tag)
            xsd_element = schema.get_element(root_path)
            for obj in xsd_element.iter_decode(xml_root):
                yield obj

        def to_dict(self, xml_document, schema=None):
            xml_root = load_xml(xml_document)[0]
            schema = schema or self
            root_path = get_qname(schema.target_namespace, xml_root.tag)
            xsd_element = schema.get_element(root_path)
            return xsd_element.decode(xml_root)

    # Create the meta schema
    if meta_schema is not None:
        meta_schema = XMLSchemaValidator(meta_schema)
        for k, v in meta_schema.imported_schemas.items():
            if not isinstance(v, XMLSchemaValidator):
                meta_schema.imported_schemas[k] = XMLSchemaValidator(v)
        XMLSchemaValidator.META_SCHEMA = meta_schema

    if version is not None:
        XMLSchemaValidator.__name__ = 'XMLSchema_{}'.format(version.replace(".", "_"))

    return XMLSchemaValidator


# Define classes for generic XML schemas
XMLSchema_v1_0 = create_validator(
    version='1.0',
    meta_schema='schemas/XSD_1.0/XMLSchema.xsd',
    base_schemas=BASE_SCHEMAS,
    facets=XSD_v1_0_FACETS,
    builtin_types=XSD_BUILTIN_TYPES
)

#
# TODO: Extending to XSD 1.1
#
# XMLSchema_v1_1 = create_validator(
#    version='1.1',
#    meta_schema='schemas/XSD_1.1/XMLSchema.xsd',
#    base_schemas=BASE_SCHEMAS,
#    facets=XSD_v1_1_FACETS
# )

XMLSchema = XMLSchema_v1_0


def validate(xml_document, schema, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    cls(schema, *args, **kwargs).validate(xml_document)


def to_dict(xml_document, schema, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    cls(schema, *args, **kwargs).validate(xml_document)
    return cls(schema, *args, **kwargs).to_dict(xml_document)
