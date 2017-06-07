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
import os.path

from .core import (
    XML_NAMESPACE_PATH, XSI_NAMESPACE_PATH, XLINK_NAMESPACE_PATH,
    HFP_NAMESPACE_PATH, etree_get_namespaces, etree_register_namespace
)
from .exceptions import (
    XMLSchemaTypeError, XMLSchemaParseError, XMLSchemaValidationError,
    XMLSchemaDecodeError, XMLSchemaURLError
)
from .qnames import XSD_SCHEMA_TAG
from .utils import URIDict, listify_update
from .resources import (
    open_resource, load_xml_resource, get_xsi_schema_location, get_xsi_no_namespace_schema_location
)
from . import xpath
from .builtins import XSD_BUILTIN_TYPES
from .components import check_tag, get_xsd_attribute, XsdElement, XSD_FACETS
from .converters import XMLSchemaConverter
from .factories import *
from .namespaces import (
    XsdGlobals, iterfind_xsd_import, iterfind_xsd_include, iterfind_xsd_redefine
)

DEFAULT_OPTIONS = {
    'simple_type_factory': xsd_simple_type_factory,
    'attribute_factory': xsd_attribute_factory,
    'attribute_group_factory': xsd_attribute_group_factory,
    'complex_type_factory': xsd_complex_type_factory,
    'group_factory': xsd_group_factory,
    'element_factory': xsd_element_factory,
    'notation_factory': xsd_notation_factory,
    'restriction_factory': xsd_restriction_factory
}
"""Default options for building XSD schema elements."""

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')


def create_validator(version, meta_schema, base_schemas=None, facets=None,
                     builtin_types=None, **options):

    meta_schema = os.path.join(SCHEMAS_DIR, meta_schema)
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
        BUILTIN_TYPES = builtin_types
        FACETS = facets or ()
        OPTIONS = validator_options
        _parent_map = None

        def __init__(self, source, namespace=None, check_schema=False, global_maps=None, converter=None):
            """
            Initialize an XML schema instance.

            :param source: This could be a string containing the schema, an URI
            that reference to a schema definition, a path to a file containing
            the schema or a file-like object containing the schema.
            """
            try:
                self.root, self.text, self.uri = load_xml_resource(source, element_only=False)
            except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                raise type(err)('cannot create schema: %s' % err)

            check_tag(self.root, XSD_SCHEMA_TAG)
            self.element_form = self.root.attrib.get('elementFormDefault', 'unqualified')
            self.attribute_form = self.root.attrib.get('attributeFormDefault', 'unqualified')

            self.built = False  # True if the schema is built successfully
            self.errors = []    # Parsing errors

            # Determine the targetNamespace
            self.target_namespace = self.root.attrib.get('targetNamespace', '')
            if namespace is not None and self.target_namespace != namespace:
                if self.target_namespace:
                    raise XMLSchemaParseError(
                        "wrong namespace (%r instead of %r) for XSD resource %r." %
                        (self.target_namespace, namespace, self.uri)
                    )
                else:
                    self.target_namespace = namespace

            # Get schema location hints
            try:
                schema_location = get_xsi_schema_location(self.root).split()
            except AttributeError:
                self.schema_location = URIDict()
            else:
                self.schema_location = URIDict()
                listify_update(self.schema_location, zip(schema_location[0::2], schema_location[1::2]))
            self.no_namespace_schema_location = get_xsi_no_namespace_schema_location(self.root)

            # Create or set the XSD global maps instance
            if global_maps is None:
                try:
                    self.maps = self.META_SCHEMA.maps.copy()
                except AttributeError:
                    self.maps = XsdGlobals(XMLSchemaValidator)
                else:
                    if self.target_namespace in self.maps.namespaces:
                        self.maps.clear()
            elif isinstance(global_maps, XsdGlobals):
                self.maps = global_maps
            else:
                raise XMLSchemaTypeError("'global_maps' argument must be a %r instance." % XsdGlobals)
            self.maps.register(self)

            # Extract namespaces from schema and include subschemas
            self.namespaces = {'xml': XML_NAMESPACE_PATH}  # the XML namespace is implicit
            self.namespaces.update(etree_get_namespaces(self.text))
            if '' not in self.namespaces:
                # For default local names are mapped to targetNamespace
                self.namespaces[''] = self.target_namespace

            # Set the default converter class
            self.converter = self.get_converter(converter)

            if self.META_SCHEMA is not None:
                self.include_schemas(self.root, check_schema)
                self.import_schemas(self.root, check_schema)
                self.redefine_schemas(self.root, check_schema)

                if check_schema:
                    self.check_schema(self.root)

                # Builds the XSD objects only if the instance is
                # the creator of the XSD globals maps.
                if global_maps is None:
                    self.maps.build()
            else:
                # If the META_SCHEMA is not instantiated do not import
                # other namespaces and do not build maps.
                self.include_schemas(self.root)
                self.redefine_schemas(self.root, check_schema)

        def __repr__(self):
            return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.target_namespace, id(self))

        @property
        def target_prefix(self):
            for prefix, namespace in self.namespaces.items():
                if namespace == self.target_namespace:
                    return prefix
            return ''

        @property
        def notations(self):
            return self.maps.get_globals('notations', self.target_namespace, False)

        @property
        def types(self):
            return self.maps.get_globals('types', self.target_namespace, False)

        @property
        def attributes(self):
            return self.maps.get_globals('attributes', self.target_namespace, False)

        @property
        def attribute_groups(self):
            return self.maps.get_globals('attribute_groups', self.target_namespace, False)

        @property
        def groups(self):
            return self.maps.get_globals('groups', self.target_namespace, False)

        @property
        def elements(self):
            return self.maps.get_globals('elements', self.target_namespace, False)

        @property
        def base_elements(self):
            return self.maps.get_globals('base_elements', self.target_namespace, False)

        @property
        def parent_map(self):
            if self._parent_map is None:
                self._parent_map = {
                    e: p for p in self.iter()
                    for e in p.iterchildren()
                }
            return self._parent_map

        @classmethod
        def create_schema(cls, *args, **kwargs):
            return cls(*args, **kwargs)

        @classmethod
        def check_schema(cls, schema):
            for error in cls.META_SCHEMA.iter_errors(schema):
                raise error

        def get_locations(self, namespace):
            if not namespace:
                return self.no_namespace_schema_location

            try:
                locations = self.schema_location[namespace]
            except KeyError:
                return None
            else:
                if isinstance(locations, list):
                    return ' '.join(locations)
                else:
                    return locations

        def get_converter(self, converter=None, namespaces=None, dict_class=None,
                          list_class=None, element_class=None):
            if converter is None:
                converter = getattr(self, 'converter', XMLSchemaConverter)
            if namespaces:
                for prefix, uri in namespaces.items():
                    etree_register_namespace(prefix, uri)

            if isinstance(converter, XMLSchemaConverter):
                converter = converter.copy()
                if namespaces is not None:
                    converter.namespaces = namespaces
                if dict_class is not None:
                    converter.dict = dict_class
                if list_class is not None:
                    converter.list = list_class
                if element_class is not None:
                    converter.etree_element = element_class
                return converter
            elif issubclass(converter, XMLSchemaConverter):
                    return converter(namespaces, dict_class, list_class, element_class)
            else:
                msg = "'converter' argument must be a %r subclass or instance: %r"
                raise XMLSchemaTypeError(msg % (XMLSchemaConverter, converter))

        def import_schemas(self, elements, check_schema=False):
            for elem in iterfind_xsd_import(elements, namespaces=self.namespaces):
                namespace = elem.attrib.get('namespace', '').strip()
                if namespace in self.maps.namespaces:
                    continue

                locations = elem.attrib.get('schemaLocation', self.get_locations(namespace))
                if locations:
                    try:
                        schema_res, schema_uri = open_resource(locations, self.uri)
                        schema_res.close()
                    except XMLSchemaURLError as err:
                        raise XMLSchemaURLError(
                            reason="cannot import namespace %r: %s" % (namespace, err.reason)
                        )

                    try:
                        self.create_schema(
                            schema_uri, namespace or self.target_namespace, check_schema, self.maps
                        )
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot import namespace %r: %s' % (namespace, err))

        def include_schemas(self, elements, check_schema=False):
            for elem in iterfind_xsd_include(elements, namespaces=self.namespaces):
                location = get_xsd_attribute(elem, 'schemaLocation')
                try:
                    schema_res, schema_uri = open_resource(location, self.uri)
                    schema_res.close()
                except XMLSchemaURLError as err:
                    raise XMLSchemaURLError(
                        reason="cannot include %r: %s" % (location, err.reason)
                    )

                if schema_uri not in self.maps.resources:
                    try:
                        self.create_schema(schema_uri, self.target_namespace, check_schema, self.maps)
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot include %r: %s' % (schema_uri, err))

        def redefine_schemas(self, elements, check_schema=False):
            for elem in iterfind_xsd_redefine(elements, namespaces=self.namespaces):
                location = get_xsd_attribute(elem, 'schemaLocation')
                try:
                    schema_res, schema_uri = open_resource(location, self.uri)
                    schema_res.close()
                except XMLSchemaURLError as err:
                    raise XMLSchemaURLError(
                        reason="cannot redefine %r: %s" % (location, err.reason)
                    )

                if schema_uri not in self.maps.resources:
                    try:
                        self.create_schema(schema_uri, self.target_namespace, check_schema, self.maps)
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot redefine %r: %s' % (schema_uri, err))

        def validate(self, xml_document, use_defaults=True):
            for error in self.iter_errors(xml_document, use_defaults=use_defaults):
                raise error

        def is_valid(self, xml_document, use_defaults=True):
            error = next(self.iter_errors(xml_document, use_defaults=use_defaults), None)
            return error is None

        def iter_errors(self, xml_document, path=None, use_defaults=True):
            for chunk in self.iter_decode(
                    xml_document, path, use_defaults=use_defaults, skip_errors=True):
                if isinstance(chunk, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    yield chunk

        def iter_decode(self, xml_document, path=None, process_namespaces=True, validate=True,
                        namespaces=None, use_defaults=True, skip_errors=False, decimal_type=None,
                        converter=None, dict_class=None, list_class=None):
            if process_namespaces:
                _namespaces = etree_get_namespaces(xml_document, namespaces)
            else:
                _namespaces = {}

            _converter = self.get_converter(converter, _namespaces, dict_class, list_class)
            element_decode_hook = _converter.element_decode

            xml_root = load_xml_resource(xml_document)
            if path is None:
                xsd_element = self.find(xml_root.tag, namespaces=_namespaces)
                if not isinstance(xsd_element, XsdElement):
                    msg = "%r is not a global element of the schema!" % xml_root.tag
                    yield XMLSchemaValidationError(self, xml_root, reason=msg)
                for obj in xsd_element.iter_decode(
                        xml_root, validate, use_defaults=use_defaults, skip_errors=skip_errors,
                        decimal_type=decimal_type, element_decode_hook=element_decode_hook):
                    yield obj
            else:
                xsd_element = self.find(path, namespaces=_namespaces)
                if not isinstance(xsd_element, XsdElement):
                    msg = "the path %r doesn't match any element of the schema!" % path
                    obj = xml_root.findall(path, namespaces=_namespaces) or xml_root
                    yield XMLSchemaValidationError(self, obj, reason=msg)
                rel_path = xpath.relative_path(path, 1, _namespaces)
                for elem in xml_root.findall(rel_path, namespaces=_namespaces):
                    for obj in xsd_element.iter_decode(
                            elem, validate, use_defaults=use_defaults, skip_errors=skip_errors,
                            decimal_type=decimal_type, element_decode_hook=element_decode_hook):
                        yield obj

        def decode(self, *args, **kwargs):
            for obj in self.iter_decode(*args, **kwargs):
                if isinstance(obj, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    raise obj
                return obj
        to_dict = decode

        #
        # ElementTree APIs for extracting XSD elements and attributes.
        def iter(self, name=None):
            for xsd_element in self.elements.values():
                if name is None or xsd_element.name == name:
                    yield xsd_element
                for e in xsd_element.iter(name):
                    yield e

        def iterchildren(self, name=None):
            for xsd_element in sorted(self.elements.values(), key=lambda x: x.name):
                if name is None or xsd_element.name == name:
                    yield xsd_element

        def iterfind(self, path, namespaces=None):
            """
            Generate all matching XML Schema element declarations by path.

            :param path: a string having an XPath expression. 
            :param namespaces: an optional mapping from namespace prefix to full name.
            """
            return xpath.xsd_iterfind(self, path, namespaces or self.namespaces)

        def find(self, path, namespaces=None):
            """
            Find first matching XML Schema element declaration by path.

            :param path: a string having an XPath expression.
            :param namespaces: an optional mapping from namespace prefix to full name.
            :return: The first matching XML Schema element declaration or None if a 
            matching declaration is not found.
            """
            return next(xpath.xsd_iterfind(self, path, namespaces or self.namespaces), None)

        def findall(self, path, namespaces=None):
            """
            Find all matching XML Schema element declarations by path.

            :param path: a string having an XPath expression.
            :param namespaces: an optional mapping from namespace prefix to full name.
            :return: A list of matching XML Schema element declarations or None if a 
            matching declaration is not found.
            """
            return list(xpath.xsd_iterfind(self, path, namespaces or self.namespaces))

    # Create the meta schema
    if meta_schema is not None:
        meta_schema = XMLSchemaValidator(meta_schema)
        for k, v in list(base_schemas.items()):
            XMLSchemaValidator(v, global_maps=meta_schema.maps)

        XMLSchemaValidator.META_SCHEMA = meta_schema
        meta_schema.maps.build()

    if version is not None:
        XMLSchemaValidator.__name__ = 'XMLSchema_{}'.format(version.replace(".", "_"))

    return XMLSchemaValidator


# Define classes for generic XML schemas
XMLSchema_v1_0 = create_validator(
    version='1.0',
    meta_schema='XSD_1.0/XMLSchema.xsd',
    base_schemas={
        XML_NAMESPACE_PATH: 'xml_minimal.xsd',
        HFP_NAMESPACE_PATH: 'XMLSchema-hasFacetAndProperty_minimal.xsd',
        XSI_NAMESPACE_PATH: 'XMLSchema-instance_minimal.xsd',
        XLINK_NAMESPACE_PATH: 'xlink.xsd'
    },
    facets=XSD_FACETS,
    builtin_types=XSD_BUILTIN_TYPES
)
XMLSchema = XMLSchema_v1_0
