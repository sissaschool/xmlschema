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
This module contains XMLSchema class creator for xmlschema package.
"""
import os
from collections import namedtuple
import elementpath

from ..exceptions import (
    XMLSchemaTypeError, XMLSchemaURLError, XMLSchemaValueError
)
from ..namespaces import (
    XSD_NAMESPACE, XML_NAMESPACE, HFP_NAMESPACE, XSI_NAMESPACE, XLINK_NAMESPACE
)
from ..etree import etree_get_namespaces, etree_register_namespace, etree_iselement

from ..namespaces import NamespaceResourcesMap, NamespaceView
from ..qnames import XSD_SCHEMA_TAG
from ..resources import fetch_resource, load_xml_resource, iter_schema_location_hints
from ..converters import XSD_VALIDATION_MODES, XMLSchemaConverter
from ..xpath import ElementPathMixin
from .exceptions import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaNotBuiltError
)
from .parseutils import has_xsd_components, get_xsd_derivation_attribute
from .xsdbase import XsdBaseComponent, ValidatorMixin
from . import (
    XSD_FACETS, XsdNotation, XsdComplexType, XsdAttribute, XsdElement, XsdAttributeGroup, XsdGroup,
    XsdAtomicRestriction, XsdSimpleType, xsd_simple_type_factory, xsd_builtin_types_factory,
    xsd_build_any_content_group, xsd_build_any_attribute_group, XsdComponent
)
from .globals_ import (
    XsdGlobals, iterchildren_xsd_import, iterchildren_xsd_include, iterchildren_xsd_redefine
)

DEFAULT_BUILDERS = {
    'notation_class': XsdNotation,
    'simple_type_class': XsdSimpleType,
    'complex_type_class': XsdComplexType,
    'attribute_class': XsdAttribute,
    'attribute_group_class': XsdAttributeGroup,
    'group_class': XsdGroup,
    'element_class': XsdElement,
    'restriction_class': XsdAtomicRestriction,
    'simple_type_factory': xsd_simple_type_factory,
    'builtin_types_factory': xsd_builtin_types_factory,
    'build_any_content_group': xsd_build_any_content_group,
    'build_any_attribute_group': xsd_build_any_attribute_group
}
"""Default options for building XSD schema elements."""


# Schemas paths
SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')

XSD_1_0_META_SCHEMA_PATH = os.path.join(SCHEMAS_DIR, 'XSD_1.0/XMLSchema.xsd')
XSD_1_1_META_SCHEMA_PATH = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')

BASE_SCHEMAS = {
    XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xml_minimal.xsd'),
    HFP_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-hasFacetAndProperty_minimal.xsd'),
    XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-instance_minimal.xsd'),
    XLINK_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xlink.xsd')
}


class XMLSchemaMeta(type):

    def __new__(mcs, name, bases, dict_):
        base_schemas = dict_.pop('base_schemas')
        builders = dict_.pop('builders')
        meta_schema = dict_.pop('meta_schema')
        dict_['XSD_VERSION'] = dict_.pop('xsd_version')
        dict_['FACETS'] = dict_.pop('facets') or ()
        dict_['BUILDERS'] = namedtuple('Builders', builders)(**builders)

        # Build the meta-schema class
        meta_schema_class = super(XMLSchemaMeta, mcs).__new__(mcs, 'Meta' + name, bases, dict_)
        meta_schema = meta_schema_class(meta_schema, defuse='never', build=False)
        for uri, pathname in list(base_schemas.items()):
            meta_schema.import_schema(namespace=uri, location=pathname)
        meta_schema.maps.build()
        dict_['BASE_SCHEMAS'] = base_schemas
        dict_['meta_schema'] = meta_schema

        return super(XMLSchemaMeta, mcs).__new__(mcs, name, bases, dict_)

    def __init__(cls, name, bases, dict_):
        super(XMLSchemaMeta, cls).__init__(name, bases, dict_)


class XMLSchemaBase(XsdBaseComponent, ValidatorMixin, ElementPathMixin):
    """
    Base class for an XML Schema instance.

    :param source: An URI that reference to a resource or a file path or a file-like \
    object or a string containing the schema.
    :type source: str or file
    :param namespace: Is an optional argument that contains the URI of the namespace. \
    When specified it must be equal to the *targetNamespace* declared in the schema.
    :type namespace: str or None
    :param validation: Defines the XSD validation mode to use for build the schema, \
    it's value can be 'strict', 'lax' or 'skip'.
    :type validation: str
    :param global_maps: Is an optional argument containing an :class:`XsdGlobals` \
    instance, a mediator object for sharing declaration data between dependents \
    schema instances.
    :type global_maps: XsdGlobals or None
    :param converter: Is an optional argument that can be an :class:`XMLSchemaConverter` \
    subclass or instance, used for defining the default XML data converter for XML Schema instance.
    :type converter: XMLSchemaConverter or None
    :param locations: A map with schema location hints. Can be a dictionary or a sequence of \
    couples (namespace URI, resource URL). It can be useful for override schema's locations hints.
    :type locations: dict or None
    :param defuse: Defines when to defuse XML data. Can be 'always', 'remote' or 'never'. \
    For default defuse only remote XML data.
    :type defuse: str or None
    :param build: Defines whether build the schema maps.
    :type build: bool

    :cvar XSD_VERSION: Store the XSD version (1.0 or 1.1).
    :vartype XSD_VERSION: str
    :cvar meta_schema: The XSD meta-schema instance.
    :vartype meta_schema: XMLSchema
    :ivar root: schema ElementTree root element
    :vartype root: Element
    :ivar text: text source of the schema
    :vartype text: str
    :ivar url: The schema resource URL. It's `None` if the schema is built from a string.
    :vartype url: str
    :ivar target_namespace: It is the *targetNamespace* of the schema, the namespace to which \
    belong the declarations/definitions of the schema. If it's empty no namespace is associated \
    with the schema. In this case the schema declarations can be reused from other namespaces as \
    *chameleon* definitions.
    :vartype target_namespace: str
    :ivar validation: Validation mode, can be 'strict', 'lax' or 'skip'.
    :vartype validation: str
    :ivar defuse: When to defuse XML data, can be 'always', 'remote' or 'never'.
    :vartype defuse: str
    :ivar maps: XSD global declarations/definitions maps. This is an instance of :class:`XsdGlobal`, \
    that store the global_maps argument or a new object when this argument is not provided.
    :vartype maps: XsdGlobals
    :ivar converter: The default converter used for XML data decoding/encoding.
    :vartype converter: XMLSchemaConverter
    :ivar locations: Schema location hints.
    :vartype locations: dict
    :ivar namespaces: A dictionary that maps from the prefixes used by the schema into namespace URI.
    :vartype namespaces: dict

    :ivar notations: `xsd:notation` declarations
    :vartype notations: NamespaceView
    :ivar types: `xsd:simpleType` and `xsd:complexType` global declarations.
    :vartype types: NamespaceView
    :ivar attributes: `xsd:attribute` global declarations.
    :vartype attributes: NamespaceView
    :ivar attribute_groups: `xsd:attributeGroup` definitions.
    :vartype attribute_groups: NamespaceView
    :ivar groups: `xsd:group` global definitions.
    :vartype groups: NamespaceView
    :ivar elements: `xsd:element` global declarations.
    :vartype elements: NamespaceView
    """
    XSD_VERSION = None
    FACETS = None
    BUILDERS = ()
    BASE_SCHEMAS = None
    meta_schema = None
    _parent_map = None

    def __init__(self, source, namespace=None, validation='strict', global_maps=None,
                 converter=None, locations=None, defuse=None, build=True):
        self.defuse = defuse or 'remote'  # Will be changed to 'always' in the future
        self._base_elements = None

        # Load the XSD schema resource
        try:
            self.root, self.text, self.url = load_xml_resource(source, False, self.defuse)
        except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot create schema: %s' % err)
        super(XMLSchemaBase, self).__init__()

        # Set and check target namespace
        self.target_namespace = self.root.get('targetNamespace', '')
        if self.target_namespace == XSD_NAMESPACE and self.meta_schema is not None:
            raise XMLSchemaValueError("The %r cannot be used as target namespace!" % XSD_NAMESPACE)
        if namespace is not None and self.target_namespace != namespace:
            if self.target_namespace:
                raise XMLSchemaParseError(
                    "wrong namespace (%r instead of %r) for XSD resource %r." %
                    (self.target_namespace, namespace, self.url)
                )
            else:
                self.target_namespace = namespace  # Chameleon schema

        # Schema validity assessments
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("'validation' argument can be 'strict', 'lax' or 'skip'.")
        self.validation = validation

        self.locations = NamespaceResourcesMap()
        if locations:
            self.locations.update(locations)  # Insert locations argument first
        self.locations.update(iter_schema_location_hints(self.root))

        self.namespaces = {'xml': XML_NAMESPACE}  # the XML namespace is implicit
        # Extract namespaces from schema text
        self.namespaces.update(etree_get_namespaces(self.text))
        if '' not in self.namespaces:
            # For default local names are mapped to targetNamespace
            self.namespaces[''] = self.target_namespace

        self.converter = self.get_converter(converter)

        # Create or set the XSD global maps instance
        if global_maps is None:
            if self.meta_schema is None:
                self.maps = XsdGlobals(self.__class__)
            elif self.target_namespace in self.BASE_SCHEMAS:
                # Change the meta-schema instance
                meta_schema_class = self.meta_schema.__class__
                meta_schema = meta_schema_class(self.meta_schema.url, build=False)
                for uri, pathname in list(self.BASE_SCHEMAS.items()):
                    if uri == self.target_namespace:
                        meta_schema.import_schema(namespace=uri, location=self.url)
                    else:
                        meta_schema.import_schema(namespace=uri, location=pathname)
                self.meta_schema = meta_schema
                self.maps = self.meta_schema.maps
            else:
                self.maps = self.meta_schema.maps.copy()

        elif isinstance(global_maps, XsdGlobals):
            self.maps = global_maps
        else:
            raise XMLSchemaTypeError("'global_maps' argument must be a %r instance." % XsdGlobals)

        # Validate the schema document
        if self.meta_schema is None:
            # Base schemas use single file and don't have to be checked
            return
        elif validation == 'strict':
            self.check_schema(self.root)
        elif validation == 'lax':
            self.errors.extend([e for e in self.meta_schema.iter_errors(self.root)])

        # XSD 1.1 xpathDefaultNamespace attribute
        if self.XSD_VERSION > '1.0':
            self.xpath_default_namespace = self._parse_xpath_default_namespace_attribute(
                self.root, self.namespaces, self.target_namespace
            )

        # Includes
        for child in iterchildren_xsd_include(self.root):
            try:
                self.include_schema(child.attrib['schemaLocation'], self.base_url)
            except (KeyError, OSError, IOError):
                # Attribute missing error already found by validation against meta-schema.
                # It is not an error if the location fail to resolve:
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#compound-schema
                pass

        # Redefines
        for child in iterchildren_xsd_redefine(self.root):
            try:
                self.include_schema(child.attrib['schemaLocation'], self.base_url)
            except KeyError:
                pass  # Attribute missing error already found by validation against meta-schema
            except (OSError, IOError) as err:
                # If the redefine doesn't contain components (annotation excluded) the statement
                # is equivalent to an include, so no error is generated. Otherwise fails.
                if has_xsd_components(child):
                    if self.validation == 'lax':
                        self.errors.append(XMLSchemaParseError(str(err), self, child))
                    elif self.validation == 'strict':
                        raise XMLSchemaParseError(str(err), self, child)

        # Imports
        for namespace, schema_location in map(
                lambda x: (x.get('namespace', '').strip(), x.get('schemaLocation')),
                iterchildren_xsd_import(self.root)):
            if schema_location:
                try:
                    self.import_schema(namespace, schema_location, self.base_url)
                except (OSError, IOError):
                    # It is not an error if the location fail to resolve:
                    #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#composition-schemaImport
                    pass
                else:
                    continue

            # Try to resolve location with other schema location hints
            for url in self.get_locations(namespace):
                try:
                    self.import_schema(namespace, url, self.base_url)
                except (OSError, IOError):
                    pass
                else:
                    break
            else:
                if namespace:
                    # Last tentative with schema url
                    try:
                        self.import_schema(namespace, namespace)
                    except (OSError, IOError, ValueError):
                        pass

        if build:
            self.maps.build()

    def __repr__(self):
        if self.url:
            return u'%s(namespace=%r, url=%r)' % (self.__class__.__name__, self.target_namespace, self.url)
        else:
            return u'%s(namespace=%r)' % (self.__class__.__name__, self.target_namespace)

    def __setattr__(self, name, value):
        if name == 'root' and value.tag != XSD_SCHEMA_TAG:
            raise XMLSchemaValueError("schema root element must has %r tag." % XSD_SCHEMA_TAG)
        elif name == 'validation':
            assert value in ('strict', 'lax', 'skip'), "Wrong value %r for attribute 'validation'." % value
        elif name == 'maps':
            value.register(self)
            self.notations = NamespaceView(value.notations, self.target_namespace)
            self.types = NamespaceView(value.types, self.target_namespace)
            self.attributes = NamespaceView(value.attributes, self.target_namespace)
            self.attribute_groups = NamespaceView(value.attribute_groups, self.target_namespace)
            self.groups = NamespaceView(value.groups, self.target_namespace)
            self.elements = NamespaceView(value.elements, self.target_namespace)
            self.substitution_groups = NamespaceView(value.substitution_groups, self.target_namespace)
            self.constraints = NamespaceView(value.constraints, self.target_namespace)
            self.global_maps = (self.notations, self.types, self.attributes,
                                self.attribute_groups, self.groups, self.elements)
        super(XMLSchemaBase, self).__setattr__(name, value)

    # Schema element attributes
    @property
    def tag(self):
        return self.root.tag

    @property
    def id(self):
        """The schema's *id* attribute, defaults to ``None``."""
        return self.root.get('id')

    @property
    def version(self):
        """The schema's *version* attribute, defaults to ``None``."""
        return self.root.get('version')

    @property
    def attribute_form_default(self):
        """The schema's *attributeFormDefault* attribute, defaults to ``'unqualified'``"""
        return self.root.get('attributeFormDefault', 'unqualified')

    @property
    def element_form_default(self):
        """The schema's *elementFormDefault* attribute, defaults to ``'unqualified'``."""
        return self.root.get('elementFormDefault', 'unqualified')

    @property
    def block_default(self):
        """The schema's *blockDefault* attribute, defaults to ``None``."""
        return get_xsd_derivation_attribute(
            self.root, 'blockDefault', ('extension', 'restriction', 'substitution')
        )

    @property
    def final_default(self):
        """The schema's *finalDefault* attribute, defaults to ``None``."""
        return get_xsd_derivation_attribute(
            self.root, 'finalDefault', ('extension', 'restriction', 'list', 'union')
        )

    @property
    def schema_location(self):
        """A list of location hints extracted from the *xsi:schemaLocation* attribute of the schema."""
        return [(k, v) for k, v in iter_schema_location_hints(self.root) if k]

    @property
    def no_namespace_schema_location(self):
        """A location hint extracted from the *xsi:noNamespaceSchemaLocation* attribute of the schema."""
        for k, v in iter_schema_location_hints(self.root):
            if not k:
                return v

    @property
    def target_prefix(self):
        for prefix, namespace in self.namespaces.items():
            if namespace == self.target_namespace:
                return prefix
        return ''

    @property
    def base_url(self):
        return os.path.dirname(self.url) if self.url is not None else None

    @property
    def parent_map(self):
        if self._parent_map is None:
            self._parent_map = {
                e: p for p in self.iter()
                for e in p.iterchildren()
            }
        return self._parent_map

    @property
    def base_elements(self):
        """
        Lazy property that returns dictionary that contains the global elements plus
        the elements derived from global groups expansion. This lazy property could be
        resource costly to build when the schema has many nested global groups.
        """
        if self._base_elements is None:
            self._base_elements = self.elements.copy()
            for group in self.groups.values():
                self.base_elements.update({e.name: e for e in group.iter_elements()})
        return self._base_elements

    @classmethod
    def create_schema(cls, *args, **kwargs):
        """Creates a new schema instance of the same class of the caller."""
        return cls(*args, **kwargs)

    @classmethod
    def check_schema(cls, schema):
        """
        Validates the given schema against the XSD meta-schema (:attr:`meta_schema`).

        :raises: :exc:`XMLSchemaValidationError` if the schema is invalid.
        """
        for error in cls.meta_schema.iter_errors(schema):
            raise error

    def build(self):
        """Builds the schema XSD global maps."""
        self.maps.build()

    @property
    def built(self):
        xsd_global = None
        for xsd_global in self.iter_globals(schema=self):
            if not isinstance(xsd_global, XsdComponent):
                return False
            if not xsd_global.built:
                return False
        if xsd_global is not None:
            return True
        else:
            return False

    @property
    def validation_attempted(self):
        """
        Property that returns the XSD component validation status. It can be
        'full', 'partial' or 'none'.

        | https://www.w3.org/TR/xmlschema-1/#e-validation_attempted
        | https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validation_attempted
        """
        if self.built:
            return 'full'
        elif any([comp.validation_attempted == 'partial' for comp in self.iter_globals()]):
            return 'partial'
        else:
            return 'none'

    def iter_globals(self, schema=None):
        """
        Creates an iterator for XSD global definitions/declarations.

        :param schema: Optional schema instance.
        """
        if schema is None:
            for global_map in self.global_maps:
                for obj in global_map.values():
                    yield obj
        else:
            for global_map in self.global_maps:
                for obj in global_map.values():
                    if isinstance(obj, tuple):
                        if obj[1] == schema:
                            yield obj
                    elif obj.schema == schema:
                        yield obj

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.iter_globals():
            for obj in xsd_global.iter_components(xsd_classes):
                yield obj

    def get_locations(self, namespace):
        """
        Get a list of location hints.
        """
        try:
            return list(self.locations[namespace])
        except KeyError:
            return []

    def get_converter(self, converter=None, namespaces=None, **kwargs):
        if converter is None:
            converter = getattr(self, 'converter', XMLSchemaConverter)
        if namespaces is None:
            namespaces = self.namespaces

        for prefix, uri_ in namespaces.items():
            etree_register_namespace(prefix, uri_)

        if isinstance(converter, XMLSchemaConverter):
            return converter.copy(namespaces=namespaces, **kwargs)
        elif issubclass(converter, XMLSchemaConverter):
            return converter(namespaces, **kwargs)
        else:
            msg = "'converter' argument must be a %r subclass or instance: %r"
            raise XMLSchemaTypeError(msg % (XMLSchemaConverter, converter))

    def import_schema(self, namespace, location, base_url=None, force=False):
        """
        Imports a schema for an external namespace, from a specific URL.

        :param namespace: is the URI of the external namespace.
        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :param force: is set to `True` imports the schema also if the namespace is already imported.
        :return: the imported :class:`XMLSchema` instance.
        """
        if namespace in self.maps.namespaces and not force:
            return
        try:
            schema_url = fetch_resource(location, base_url)
        except XMLSchemaURLError as err:
            raise XMLSchemaURLError(
                reason="cannot import namespace %r: %s" % (namespace, err.reason)
            )
        else:
            if namespace in self.maps.namespaces:
                for schema in self.maps.namespaces[namespace]:
                    if schema_url == schema.url:
                        return schema

        try:
            return self.create_schema(
                schema_url, namespace or self.target_namespace, self.validation, self.maps,
                self.converter, None, self.defuse, False
            )
        except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot import namespace %r: %s' % (namespace, err))

    def include_schema(self, location, base_url=None):
        """
        Includes a schema for the same namespace, from a specific URL.

        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :return: the included :class:`XMLSchema` instance.
        """

        try:
            schema_url = fetch_resource(location, base_url)
        except XMLSchemaURLError as err:
            raise XMLSchemaURLError(reason="cannot include %r: %s." % (location, err.reason))
        else:
            for schema in self.maps.namespaces[self.target_namespace]:
                if schema_url == schema.url:
                    return schema
        try:
            return self.create_schema(
                schema_url, self.target_namespace, self.validation, self.maps,
                self.converter, None, self.defuse, False
            )
        except (XMLSchemaParseError, XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot include %r: %s' % (schema_url, err))

    def iter_decode(self, xml_document, path=None, validation='lax', process_namespaces=True,
                    namespaces=None, use_defaults=True, decimal_type=None, converter=None,
                    defuse=None, **kwargs):
        """
        Creates an iterator for decoding an XML document using the schema instance. Yields objects 
        that can be dictionaries or simple data values.

        :param xml_document: can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data.
        :param path: is an optional XPath expression that matches the parts of the document \
        that have to be decoded. The XPath expression considers the schema as the root \
        element with global elements as its children.
        :param validation: defines the XSD validation mode to use for decode, can be 'strict', \
        'lax' or 'skip'.
        :param process_namespaces: indicates whether to process namespaces, using the map \
        provided with the argument *namespaces* and the map extracted from the XML document.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param decimal_type: conversion type for `Decimal` objects (generated by XSD `decimal` \
        built-in and derived types), useful if you want to generate a JSON-compatible data structure.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the decoding.
        :param kwargs: Keyword arguments containing options for converters and decoding.
        """
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation mode argument can be 'strict', 'lax' or 'skip'.")

        if not self.built:
            raise XMLSchemaNotBuiltError("schema %r is not built." % self)

        if process_namespaces:
            namespaces = {} if namespaces is None else namespaces.copy()
            namespaces.update(etree_get_namespaces(xml_document))
            converter = self.get_converter(converter, namespaces, **kwargs)
        else:
            converter = self.get_converter(converter, namespaces={}, **kwargs)

        try:
            xml_root = xml_document.getroot()
        except (AttributeError, TypeError):
            if etree_iselement(xml_document):
                xml_root = xml_document
            else:
                xml_root = load_xml_resource(xml_document, defuse=defuse or self.defuse)
        else:
            if not etree_iselement(xml_root):
                raise XMLSchemaTypeError(
                    "wrong type %r for 'xml_document' argument." % type(xml_document)
                )

        if path is None:
            xsd_element = self.find(xml_root.tag, namespaces=namespaces)
            if not isinstance(xsd_element, XsdElement):
                msg = "%r is not a global element of the schema!" % xml_root.tag
                yield XMLSchemaValidationError(self, xml_root, reason=msg)
            else:
                for obj in xsd_element.iter_decode(
                        xml_root, validation,
                        process_namespaces=process_namespaces,
                        namespaces=namespaces,
                        use_defaults=use_defaults,
                        decimal_type=decimal_type,
                        converter=converter,
                        **kwargs):
                    yield obj
        else:
            xsd_element = self.find(path, namespaces=namespaces)
            if not isinstance(xsd_element, XsdElement):
                msg = "the path %r doesn't match any element of the schema!" % path
                obj = elementpath.select(xml_root, path, namespaces=namespaces) or xml_root
                yield XMLSchemaValidationError(self, obj, reason=msg)
            else:
                for elem in elementpath.select(xml_root, path, namespaces=namespaces):
                    for obj in xsd_element.iter_decode(
                            elem, validation,
                            process_namespaces=process_namespaces,
                            namespaces=namespaces,
                            use_defaults=use_defaults,
                            decimal_type=decimal_type,
                            converter=converter,
                            **kwargs):
                        yield obj

    def iter_encode(self, data, path=None, validation='lax', namespaces=None, indent=None,
                    converter=None, **kwargs):
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation mode argument can be 'strict', 'lax' or 'skip'.")

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
            for obj in xsd_element.iter_encode(data, validation, indent=indent,
                                               element_encode_hook=_converter.element_encode):
                yield obj

    def iter(self, name=None):
        """
        Creates a subtree iterator (depth-first) for the XSD/XML element. If *name* is not ``None``
        only XSD/XML elements whose name/tag equals *name* are returned from the iterator.
        """
        for xsd_element in self.elements.values():
            if name is None or xsd_element.name == name:
                yield xsd_element
            for e in xsd_element.iter(name):
                yield e

    def __iter__(self):
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name):
            yield xsd_element

    @property
    def name(self):
        return self.root.tag

    def iterchildren(self, name=None):
        """
        Creates an iterator for child XSD/XML elements, sorted by name. If *name* is not ``None``
        only XSD/XML elements whose name/tag equals *name* are returned from the iterator.
        """
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name):
            if name is None or xsd_element.name == name:
                yield xsd_element


def create_validator(xsd_version, meta_schema, base_schemas=None, facets=None, **options):
    builders = dict(DEFAULT_BUILDERS.items())
    builders.update(options)

    return XMLSchemaMeta(
        name='XMLSchema_v{}'.format(xsd_version.replace(".", "_")),
        bases=(XMLSchemaBase,),
        dict_=dict(
            xsd_version=xsd_version,
            meta_schema=meta_schema,
            base_schemas=base_schemas,
            facets=facets,
            builders=builders
        )
    )


XMLSchema_v1_0 = create_validator(
    xsd_version='1.0',
    meta_schema=XSD_1_0_META_SCHEMA_PATH,
    base_schemas=BASE_SCHEMAS,
    facets=XSD_FACETS
)
XMLSchema = XMLSchema_v1_0
"""The default class for schema instances."""
