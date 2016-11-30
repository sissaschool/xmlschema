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
This module contains XMLSchema class creator for xmlschema package
"""
import logging
from collections import MutableMapping

from .core import XMLSchemaValueError, XMLSchemaLookupError, XML_NAMESPACE_PATH, BASE_SCHEMAS, urlsplit
from .qnames import get_namespace, split_path, get_qualified_path, get_qname, uri_to_prefixes
from .resources import load_resource, load_xml
from .builtins import XSD_BUILTIN_TYPES
from .parse import (
    XSD_SCHEMA_TAG, XSI_SCHEMA_LOCATION, lookup_attribute, check_tag,
    update_xsd_simple_types, update_xsd_attributes, update_xsd_attribute_groups,
    update_xsd_complex_types, update_xsd_groups, update_xsd_elements, iterfind_xsd_imports
)
from .validators import XMLSchemaValidationError, XMLSchemaDecodeError
from .factories import (
    xsd_include_schemas, xsd_simple_type_factory, xsd_restriction_factory,
    xsd_attribute_factory, xsd_attribute_group_factory, xsd_complex_type_factory,
    xsd_element_factory,  xsd_group_factory
)
from .etree import etree_get_namespaces

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


class URIDict(MutableMapping):
    """
    Dictionary which uses normalized URIs as keys.
    """
    @staticmethod
    def normalize(uri):
        return urlsplit(uri).geturl()

    def __init__(self, *args, **kwargs):
        self._store = dict()
        self._store.update(*args, **kwargs)

    def __getitem__(self, uri):
        return self._store[self.normalize(uri)]

    def __setitem__(self, uri, value):
        self._store[self.normalize(uri)] = value

    def __delitem__(self, uri):
        del self._store[self.normalize(uri)]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return repr(self._store)


def create_validator(version=None, meta_schema=None, base_schemas=None, **options):

    validator_options = dict(DEFAULT_OPTIONS)
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
        OPTIONS = validator_options

        include_schemas = OPTIONS.pop('inclusion_method')

        def __init__(self, schema, builtin_types=None):
            """
            Initialize an XML schema instance.

            :param schema: This could be a string containing the schema, an URI
            that reference to a schema definition, a path to a file containing
            the schema or a file-like object containing the schema.
            """
            self.text, self._root, self.uri = load_xml(schema)

            # print(self.uri)

            check_tag(self._root, XSD_SCHEMA_TAG)
            self.target_namespace = self._root.attrib.get('targetNamespace', '')
            self.element_form = self._root.attrib.get('elementFormDefault', 'unqualified')
            self.attribute_form = self._root.attrib.get('attributeFormDefault', 'unqualified')
            self._schema_location = self._root.attrib.get(XSI_SCHEMA_LOCATION)

            if self.META_SCHEMA is not None:
                self.lookup_table = URIDict(self.BASE_SCHEMAS)
            else:
                self.lookup_table = self.BASE_SCHEMAS

            self.lookup_table[self.target_namespace] = self
            self._included_schemas = URIDict()
            self._redefined_schemas = URIDict()

            self.types = builtin_types or {}
            self.attributes = {}
            self.attribute_groups = {}
            self.groups = {}
            self.elements = {}

            # Extract namespaces from schema and import subschemas
            self.namespaces = {'xml': XML_NAMESPACE_PATH}  # The namespace 'xml 'is implicitly included
            namespaces = etree_get_namespaces(self.text)
            self.namespaces.update(namespaces)
            self.include_schemas(self._root)
            self.import_schemas(self._root)  # Imported schemas could override namespaces imports

            if '' not in self.namespaces:
                # Define lookup for local names when it's not explicitly declared (eg. xmlns="...")
                try:
                    self.namespaces[''] = self.lookup_table[''].target_namespace
                except KeyError:
                    self.namespaces[''] = self.target_namespace

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
            for error in cls(cls.META_SCHEMA).iter_errors(schema):
                raise error

        def import_namespace(self, uri, locations=None):
            locations = locations or uri
            if not locations:
                raise XMLSchemaValueError("No namespace or locations, cannot import!")
            try:
                if isinstance(self.lookup_table[uri], str):
                    # The value is a path of the BASE_SCHEMA dictionary
                    self.lookup_table[uri] = self.create_schema(self.lookup_table[uri])
            except KeyError:
                try:
                    schema, schema_uri = load_resource(locations, self.uri)
                except (OSError, IOError, ValueError) as err:
                    raise XMLSchemaValueError(
                        "%r: cannot import namespace %r from locations %r: %s" % (self, uri, locations, err)
                    )
                else:
                    self.lookup_table[uri] = self.create_schema(schema_uri)

        def import_schemas(self, elements):
            for elem in iterfind_xsd_imports(elements, namespaces=self.namespaces):
                uri = elem.attrib.get('namespace', '')
                locations = elem.attrib.get('schemaLocation')
                if locations is not None:
                    self.import_namespace(uri, locations)

        def update_schema(self, elements, path=None):
            kwargs = self.OPTIONS.copy()
            kwargs.update({'xsd_types': self.types})

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
                return lookup_attribute(name, namespace, self.lookup_table)
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
            from .components import XsdGroup

            def _iter_errors(elem, path, schema_elem):
                try:
                    xsd_element = schema.get_element(path)
                except XMLSchemaLookupError:
                    yield XMLSchemaValidationError(
                        validator=self,
                        value=elem.tag,
                        reason="element with path /%s not in schema!" % path,
                        elem=elem,
                        schema_elem=schema_elem
                    )
                else:
                    # Verify tag format
                    if xsd_element.qualified and not get_namespace(elem.tag):
                        yield XMLSchemaValidationError(
                            validator=self,
                            value=elem.tag,
                            reason="tag must be a fully qualified name!",
                            elem=elem,
                            schema_elem=schema_elem
                        )

                    # Verify element's attributes
                    try:
                        for error in xsd_element.type.attributes.validate(elem.attrib, elem):
                            yield error
                    except AttributeError:
                        # The element has simple content type.
                        pass

                    content_type = getattr(xsd_element.type, 'content_type', None)
                    if not isinstance(content_type, XsdGroup):
                        # Decode and validate
                        try:
                            xsd_element.decode(elem.text or '')
                        except (XMLSchemaValidationError, XMLSchemaDecodeError) as err:
                            value = getattr(err, 'value', None) or getattr(err, 'text', None)
                            yield XMLSchemaValidationError(
                                validator=xsd_element,
                                value=value,
                                reason=err.reason,
                                elem=elem,
                                schema_elem=xsd_element.elem
                            )

                        # simpleType or simpleContent: no subelements allowed!
                        for child in elem:
                            child_path = uri_to_prefixes('%s/%s' % (path, child.tag), self.namespaces)
                            yield XMLSchemaValidationError(
                                validator=xsd_element,
                                value=child.tag,
                                reason="element with path /%s not in schema!" % child_path,
                                elem=child,
                                schema_elem=xsd_element.elem
                            )
                    else:
                        # Verify the element content
                        for error in content_type.validate_content(elem):
                            yield error

                        # Validate each subtree
                        for child in elem:
                            for error in _iter_errors(child, '%s/%s' % (path, child.tag), xsd_element.elem):
                                yield error

            schema = schema or self
            xml_text, xml_root, xml_uri = load_xml(xml_document)
            root_path = get_qname(self.target_namespace, xml_root.tag)
            return _iter_errors(xml_root, root_path, schema._root)

        def to_dict(self, xml_document, schema=None):
            xml_text, xml_root, xml_uri = load_xml(xml_document)
            from .etree import element_to_dict
            return element_to_dict(xml_root, schema or self)

    # Create the meta schema
    if meta_schema is not None:
        meta_schema = XMLSchemaValidator(meta_schema, XSD_BUILTIN_TYPES)
        XMLSchemaValidator.META_SCHEMA = meta_schema

    if version is not None:
        XMLSchemaValidator.__name__ = 'XMLSchema_{}'.format(version.replace(".", "_"))

    return XMLSchemaValidator


# Define classes for generic XML schemas
XMLSchema_v1_0 = create_validator(
    version='1.0',
    meta_schema='schemas/XSD_1.0/XMLSchema.xsd',
    base_schemas=BASE_SCHEMAS
)

#
# TODO: Extending to XSD 1.1
#
# XMLSchema_v1_1 = create_validator(
#    version='1.1',
#    meta_schema='schemas/XSD_1.1/XMLSchema.xsd',
#    base_schemas=BASE_SCHEMAS
# )

XMLSchema = XMLSchema_v1_0


def validate(xml_document, schema, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    cls.check_schema(schema)
    cls(schema, *args, **kwargs).validate(xml_document)


def to_dict(xml_document, schema, cls=None, *args, **kwargs):
    if cls is None:
        cls = XMLSchema
    cls(schema, *args, **kwargs).validate(xml_document)
    return cls(schema, *args, **kwargs).to_dict(xml_document)
