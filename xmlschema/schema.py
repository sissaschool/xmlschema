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
    XMLSchemaURLError, XMLSchemaEncodeError, XMLSchemaNotBuiltError, XMLSchemaValueError
)
from .utils import URIDict, listify_update
from .resources import (
    open_resource, load_xml_resource, get_xsi_schema_location, get_xsi_no_namespace_schema_location
)
from . import xpath
from .builtins import XSD_BUILTIN_TYPES
from .validator import XMLSchemaValidator
from .components import (
    check_tag, get_xsd_attribute, XSD_FACETS, get_xsd_derivation_attribute,
    iterchildren_xsd_import, iterchildren_xsd_include, iterchildren_xsd_redefine,
    XsdNotation, XsdComplexType, XsdAttribute, XsdElement, XsdAttributeGroup, XsdGroup,
    xsd_simple_type_factory, XsdAtomicRestriction, XsdSimpleType
)
from . import qnames
from .utils import check_value
from .converters import XMLSchemaConverter
from .namespaces import XsdGlobals, NamespaceView

DEFAULT_OPTIONS = {
    'simple_type_factory': xsd_simple_type_factory,
    qnames.XSD_NOTATION_TAG: XsdNotation,
    qnames.XSD_SIMPLE_TYPE_TAG: XsdSimpleType,
    qnames.XSD_COMPLEX_TYPE_TAG: XsdComplexType,
    qnames.XSD_ANNOTATION_TAG: XsdAttribute,
    qnames.XSD_ATTRIBUTE_GROUP_TAG: XsdAttributeGroup,
    qnames.XSD_GROUP_TAG: XsdGroup,
    qnames.XSD_ELEMENT_TAG: XsdElement,
    qnames.XSD_RESTRICTION_TAG: XsdAtomicRestriction
}
"""Default options for building XSD schema elements."""

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')


def create_validator(xsd_version, meta_schema, base_schemas=None, facets=None,
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

    class _XMLSchema(XMLSchemaValidator, xpath.XPathMixin):
        """
        Class to wrap an XML Schema for components lookups and conversion.
        """
        XSD_VERSION = xsd_version
        META_SCHEMA = None
        BUILTIN_TYPES = builtin_types  # TODO: implement __deepcopy__
        FACETS = facets or ()
        OPTIONS = validator_options
        _parent_map = None

        def __init__(self, source, namespace=None, validation='strict', global_maps=None, converter=None):
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
            else:
                super(_XMLSchema, self).__init__()

            # Schema validity assessments
            self.validation = validation
            self.errors = []        # Parsing errors
            self.parent = self

            # Determine the targetNamespace
            self.target_namespace = self.root.get('targetNamespace', '')
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
                    self.maps = XsdGlobals(_XMLSchema, self.validation)
                else:
                    self.maps.validation = self.validation
            elif isinstance(global_maps, XsdGlobals):
                self.maps = global_maps
            else:
                raise XMLSchemaTypeError("'global_maps' argument must be a %r instance." % XsdGlobals)

            # Extract namespaces from schema and include subschemas
            self.namespaces = {'xml': XML_NAMESPACE_PATH}  # the XML namespace is implicit
            self.namespaces.update(etree_get_namespaces(self.text))
            if '' not in self.namespaces:
                # For default local names are mapped to targetNamespace
                self.namespaces[''] = self.target_namespace

            # Set the default converter class
            self.converter = self.get_converter(converter)

            if self.META_SCHEMA is not None:
                self.include_schemas(self.root, validation)
                self.import_schemas(self.root, validation)
                self.redefine_schemas(self.root, validation)

                if validation == 'strict':
                    self.check_schema(self.root)

                # Builds the XSD objects only if the instance is
                # the creator of the XSD globals maps.
                if global_maps is None:
                    self.maps.build()
            else:
                # If the META_SCHEMA is not instantiated do not import
                # other namespaces and do not build maps.
                self.include_schemas(self.root)
                self.redefine_schemas(self.root, validation)

        def __repr__(self):
            return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.target_namespace, id(self))

        def __setattr__(self, name, value):
            if name == 'root':
                check_tag(value, qnames.XSD_SCHEMA_TAG)
            elif name == 'validation':
                check_value(value, 'strict', 'lax', 'skip')
            elif name == 'maps':
                value.register(self)
                self.notations = NamespaceView(value.notations, self.target_namespace)
                self.types = NamespaceView(value.types, self.target_namespace)
                self.attributes = NamespaceView(value.attributes, self.target_namespace)
                self.attribute_groups = NamespaceView(value.attribute_groups, self.target_namespace)
                self.groups = NamespaceView(value.groups, self.target_namespace)
                self.elements = NamespaceView(value.elements, self.target_namespace)
                self.base_elements = NamespaceView(value.base_elements, self.target_namespace)
                self.substitution_groups = NamespaceView(value.substitution_groups, self.target_namespace)
                self.global_maps = (self.notations, self.types, self.attributes,
                                    self.attribute_groups, self.groups, self.elements)
            super(_XMLSchema, self).__setattr__(name, value)

        # Schema element attributes
        @property
        def attribute_form_default(self):
            return self.root.get('attributeFormDefault', 'unqualified')

        @property
        def block_default(self):
            return get_xsd_derivation_attribute(
                self.root, 'blockDefault', ('extension', 'restriction', 'substitution')
            )

        @property
        def element_form_default(self):
            return self.root.get('elementFormDefault', 'unqualified')

        @property
        def final_default(self):
            return get_xsd_derivation_attribute(
                self.root, 'finalDefault', ('extension', 'restriction', 'list', 'union')
            )

        @property
        def id(self):
            return self.root.get('id')

        @property
        def version(self):
            return self.root.get('version')

        @property
        def target_prefix(self):
            for prefix, namespace in self.namespaces.items():
                if namespace == self.target_namespace:
                    return prefix
            return ''

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

        @property
        def check_token(self):
            return self.maps.check_token

        @property
        def built(self):
            xsd_global = None
            for xsd_global in self.iter_globals():
                if xsd_global is False:
                    return False
            return xsd_global is not None  # An empty schema is not built

        def check(self):
            if not self.checked:

                if self.errors:
                    self._valid = False

                for xsd_global in self.iter_globals():
                    xsd_global.check()
                    if xsd_global.valid is False:
                        self._valid = False
                        break
                    elif xsd_global.valid is None:
                        self._valid = None
                super(_XMLSchema, self).check()

            if self.valid is not True and self.validation == 'strict':
                if not self.built:
                    raise XMLSchemaNotBuiltError(
                        "%r: 'strict' validation requires a built schema."
                    )
                elif self.valid is False:
                    try:
                        if len(self.errors) == 2:
                            raise self.errors[0]
                        else:
                            err = self.errors[0]
                            msg = "found %d errors parsing the schema: %s"
                            raise XMLSchemaParseError(
                                msg % (len(self.errors), err.message),
                                obj=self.errors[0].obj
                            )
                    except IndexError:
                        raise XMLSchemaValueError("%r: at least an error expected." % self)
                else:
                    raise XMLSchemaValueError('%r: schema built but validity unknown.' % self)

        def iter_globals(self):
            for global_map in self.global_maps:
                for obj in global_map.values():
                    yield obj

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

        def get_converter(self, converter=None, namespaces=None, dict_class=None, list_class=None):
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
                return converter
            elif issubclass(converter, XMLSchemaConverter):
                    return converter(namespaces, dict_class, list_class)
            else:
                msg = "'converter' argument must be a %r subclass or instance: %r"
                raise XMLSchemaTypeError(msg % (XMLSchemaConverter, converter))

        def import_schemas(self, elem, validation='strict'):
            for child in iterchildren_xsd_import(elem):
                namespace = child.get('namespace', '').strip()
                if namespace in self.maps.namespaces:
                    continue

                locations = child.get('schemaLocation', self.get_locations(namespace))
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
                            schema_uri, namespace or self.target_namespace, validation, self.maps
                        )
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot import namespace %r: %s' % (namespace, err))

        def include_schemas(self, elem, validation='strict'):
            for child in iterchildren_xsd_include(elem):
                location = get_xsd_attribute(child, 'schemaLocation')
                try:
                    schema_res, schema_uri = open_resource(location, self.uri)
                    schema_res.close()
                except XMLSchemaURLError as err:
                    raise XMLSchemaURLError(
                        reason="cannot include %r: %s" % (location, err.reason)
                    )

                if schema_uri not in self.maps.resources:
                    try:
                        self.create_schema(schema_uri, self.target_namespace, validation, self.maps)
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot include %r: %s' % (schema_uri, err))

        def redefine_schemas(self, elem, validation='strict'):
            for child in iterchildren_xsd_redefine(elem):
                location = get_xsd_attribute(child, 'schemaLocation')
                try:
                    schema_res, schema_uri = open_resource(location, self.uri)
                    schema_res.close()
                except XMLSchemaURLError as err:
                    raise XMLSchemaURLError(
                        reason="cannot redefine %r: %s" % (location, err.reason)
                    )

                if schema_uri not in self.maps.resources:
                    try:
                        self.create_schema(schema_uri, self.target_namespace, validation, self.maps)
                    except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
                        raise type(err)('cannot redefine %r: %s' % (schema_uri, err))

        def iter_decode(self, xml_document, path=None, process_namespaces=True, validate=True,
                        namespaces=None, use_defaults=True, skip_errors=False, decimal_type=None,
                        converter=None, dict_class=None, list_class=None):
            if process_namespaces:
                # Considers namespaces extracted from the XML document first,
                # then from the argument and at last from the schema.
                _namespaces = {k: v for k, v in self.namespaces.items() if k != ''}
                if namespaces:
                    _namespaces.update(namespaces)
                _namespaces.update(etree_get_namespaces(xml_document))
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

        def iter_encode(self, data, path=None, validate=True, namespaces=None, skip_errors=False,
                        indent=None, element_class=None, converter=None):
            if indent is not None and indent < 0:
                indent = 0
            _namespaces = self.namespaces.copy()
            if namespaces:
                _namespaces.update(namespaces)

            xsd_element = self.find(path, namespaces=_namespaces)
            if not isinstance(xsd_element, XsdElement):
                msg = "the path %r doesn't match any element of the schema!" % path
                yield XMLSchemaEncodeError(self, data, self.elements, reason=msg)
            else:
                _converter = self.get_converter(converter, _namespaces)
                kwargs = {
                    'skip_errors': skip_errors,
                    'indent': indent,
                    'element_encode_hook': _converter.element_encode
                }
                for obj in xsd_element.iter_encode(data, validate, **kwargs):
                    yield obj

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

    # Create the meta schema
    if meta_schema is not None:
        meta_schema = _XMLSchema(meta_schema)
        for k, v in list(base_schemas.items()):
            _XMLSchema(v, global_maps=meta_schema.maps)
        _XMLSchema.META_SCHEMA = meta_schema
        meta_schema.maps.build()

    if xsd_version is not None:
        _XMLSchema.__name__ = 'XMLSchema_{}'.format(xsd_version.replace(".", "_"))

    return _XMLSchema


# Define classes for generic XML schemas
XMLSchema_v1_0 = create_validator(
    xsd_version='1.0',
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
