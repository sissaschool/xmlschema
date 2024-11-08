#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains XMLSchema classes creator for xmlschema package.

Two schema classes are created at the end of this module, XMLSchema10 for XSD 1.0 and
XMLSchema11 for XSD 1.1. The latter class parses also XSD 1.0 schemas, as prescribed by
the standard.
"""
from abc import ABCMeta
import os
import logging
import threading
import warnings
import re
import sys
from collections.abc import Callable, ItemsView, Iterator
from copy import copy as _copy, deepcopy
from operator import attrgetter
from pathlib import Path
from typing import Any, cast, Optional, Union, Type
from urllib.request import OpenerDirector
from xml.etree.ElementTree import Element, ParseError

from elementpath import XPathToken, SchemaElementNode, build_schema_node_tree

from xmlschema.aliases import XMLSourceType, NsmapType, LocationsType, UriMapperType, \
    SchemaType, SchemaSourceType, ComponentClassType, DecodeType, EncodeType, \
    BaseXsdType, ExtraValidatorType, ValidationHookType, SchemaGlobalType, \
    FillerType, DepthFillerType, ValueHookType, ElementHookType, ElementType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaKeyError, \
    XMLSchemaRuntimeError, XMLSchemaValueError, XMLSchemaNamespaceError
from xmlschema.translation import gettext as _
from xmlschema.utils.decoding import Empty
from xmlschema.utils.logger import set_logging_level
from xmlschema.utils.etree import prune_etree, is_etree_element
from xmlschema.utils.qnames import get_namespace, get_qname
from xmlschema.utils.urls import is_local_url, normalize_url
from xmlschema.resources import XMLResource, XMLResourceBlocked, XMLResourceForbidden
from xmlschema.converters import XMLSchemaConverter, ConverterType, \
    check_converter_argument, get_converter
from xmlschema.xpath import XMLSchemaProxy, ElementPathMixin
from xmlschema.loaders import SCHEMAS_DIR, SchemaLoader, LocationHints
from xmlschema.exports import export_schema
from xmlschema import dataobjects
import xmlschema.names as nm

from .exceptions import XMLSchemaParseError, XMLSchemaValidationError, \
    XMLSchemaEncodeError, XMLSchemaNotBuiltError, XMLSchemaStopValidation, \
    XMLSchemaIncludeWarning, XMLSchemaImportWarning
from .validation import check_validation_mode, DecodeContext, EncodeContext
from .helpers import get_xsd_derivation_attribute, get_xsd_annotation_child
from .xsdbase import XSD_ELEMENT_DERIVATIONS, XsdValidator, XsdComponent, XsdAnnotation
from .notations import XsdNotation
from .identities import XsdIdentity, XsdKey, XsdKeyref, XsdUnique, \
    Xsd11Key, Xsd11Unique, Xsd11Keyref, KeyrefCounter
from .facets import XSD_10_FACETS, XSD_11_FACETS
from .simple_types import XsdSimpleType, XsdList, XsdUnion, XsdAtomicRestriction, \
    Xsd11AtomicRestriction, Xsd11Union
from .attributes import XsdAttribute, XsdAttributeGroup, Xsd11Attribute
from .complex_types import XsdComplexType, Xsd11ComplexType
from .groups import XsdGroup, Xsd11Group
from .elements import XsdElement, Xsd11Element
from .wildcards import XsdAnyElement, XsdAnyAttribute, Xsd11AnyElement, \
    Xsd11AnyAttribute, XsdDefaultOpenContent
from .global_maps import NamespaceView, XsdGlobals

logger = logging.getLogger('xmlschema')

name_attribute = attrgetter('name')

XSD_VERSION_PATTERN = re.compile(r'^\d+\.\d+$')

# Elements for building dummy groups
ATTRIBUTE_GROUP_ELEMENT = Element(nm.XSD_ATTRIBUTE_GROUP)
ANY_ATTRIBUTE_ELEMENT = Element(
    nm.XSD_ANY_ATTRIBUTE, attrib={'namespace': '##any', 'processContents': 'lax'}
)
SEQUENCE_ELEMENT = Element(nm.XSD_SEQUENCE)
ANY_ELEMENT = Element(
    nm.XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })

GLOBAL_TAGS = frozenset((
    nm.XSD_NOTATION, nm.XSD_SIMPLE_TYPE, nm.XSD_COMPLEX_TYPE,
    nm.XSD_ATTRIBUTE, nm.XSD_ATTRIBUTE_GROUP, nm.XSD_GROUP, nm.XSD_ELEMENT
))


class XMLSchemaMeta(ABCMeta):
    XSD_VERSION: str
    create_meta_schema: Callable[['XMLSchemaBase', Optional[str]], SchemaType]

    def __new__(mcs, name: str, bases: tuple[Type[Any]], dict_: dict[str, Any]) \
            -> 'XMLSchemaMeta':
        assert bases, "a base class is mandatory"
        base_class = bases[0]

        if isinstance(dict_.get('meta_schema'), str):
            # Build a new meta-schema class and register it into module's globals
            meta_schema_file: str = dict_.pop('meta_schema')
            meta_schema_class_name = 'Meta' + name

            meta_schema: Optional[SchemaType]
            meta_schema = getattr(base_class, 'meta_schema', None)
            if meta_schema is None:
                meta_bases = bases
            else:
                # Use base's meta_schema class as base for the new meta-schema
                meta_bases = (meta_schema.__class__,)
                if len(bases) > 1:
                    meta_bases += bases[1:]

            meta_schema_class = cast(
                'XMLSchemaBase',
                super().__new__(mcs, meta_schema_class_name, meta_bases, dict_)
            )
            meta_schema_class.__qualname__ = meta_schema_class_name
            module = sys.modules[dict_['__module__']]
            setattr(module, meta_schema_class_name, meta_schema_class)

            meta_schema = meta_schema_class.create_meta_schema(meta_schema_file)
            dict_['meta_schema'] = meta_schema

        # Create the class and check some basic attributes
        cls = super().__new__(mcs, name, bases, dict_)
        if cls.XSD_VERSION not in ('1.0', '1.1'):
            raise XMLSchemaValueError(_("XSD_VERSION must be '1.0' or '1.1'"))
        return cls


class XMLSchemaBase(XsdValidator, ElementPathMixin[Union[SchemaType, XsdElement]],
                    metaclass=XMLSchemaMeta):
    """
    Base class for an XML Schema instance.

    :param source: a URI that reference to a resource or a file path or a file-like \
    object or a string containing the schema or an Element or an ElementTree document \
    or an :class:`XMLResource` instance. A multi source initialization is supported \
    providing a not empty list of XSD sources.
    :param namespace: is an optional argument that contains the URI of the namespace \
    that has to used in case the schema has no namespace (chameleon schema). For other \
    cases, when specified, it must be equal to the *targetNamespace* of the schema.
    :param validation: the XSD validation mode to use for build the schema, \
    that can be 'strict' (default), 'lax' or 'skip'.
    :param global_maps: is an optional argument containing an :class:`XsdGlobals` \
    instance, a mediator object for sharing declaration data between dependents \
    schema instances.
    :param converter: is an optional argument that can be an :class:`XMLSchemaConverter` \
    subclass or instance, used for defining the default XML data converter for XML Schema instance.
    :param locations: schema extra location hints, that can include custom resource locations \
    (e.g. local XSD file instead of remote resource) or additional namespaces to import after \
    processing schema's import statements. Can be a dictionary or a sequence of couples \
    (namespace URI, resource URL). Extra locations passed using a tuple container are not \
    normalized.
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the schema resource can't be obtained from the source argument.
    :param allow: the security mode for accessing resource locations. Can be \
    'all', 'remote', 'local' or 'sandbox'. Default is 'all' that means all types of \
    URLs are allowed. With 'remote' only remote resource URLs are allowed. With 'local' \
    only file paths and URLs are allowed. With 'sandbox' only file paths and URLs that \
    are under the directory path identified by source or by the *base_url* argument \
    are allowed.
    :param defuse: defines when to defuse XML data using a `SafeXMLParser`. Can be \
    'always', 'remote' or 'never'. For default defuses only remote XML data.
    :param timeout: the timeout in seconds for fetching resources. Default is `300`.
    :param uri_mapper: an optional URI mapper for using relocated or URN-addressed \
    resources. Can be a dictionary or a function that takes the URI string and returns \
    a URL, or the argument if there is no mapping for it.
    :param opener: an optional :class:`OpenerDirector` to use for open the resource. \
    For default use the opener installed globally for *urlopen*.
    :param build: defines whether build the schema maps. Default is `True`.
    :param use_meta: if `True` the schema processor uses the validator meta-schema, \
    otherwise a new meta-schema is added at the end. In the latter case the meta-schema \
    is rebuilt if any base namespace has been overridden by an import. Ignored if the \
    argument *global_maps* is provided.
    :param use_fallback: if `True` the schema processor uses the validator fallback \
    location hints to load well-known namespaces (e.g. xhtml).
    :param use_xpath3: if `True` an XSD 1.1 schema instance uses the XPath 3 processor \
    for assertions. For default a full XPath 2.0 processor is used.
    :param loglevel: for setting a different logging level for schema initialization \
    and building. For default is WARNING (30). For INFO level set it with 20, for \
    DEBUG level with 10. The default loglevel is restored after schema building, \
    when exiting the initialization method.

    :cvar XSD_VERSION: store the XSD version (1.0 or 1.1).
    :cvar BASE_SCHEMAS: a dictionary from namespace to schema resource for meta-schema bases.
    :cvar meta_schema: the XSD meta-schema instance.
    :cvar attribute_form_default: the schema's *attributeFormDefault* attribute. \
    Default is 'unqualified'.
    :cvar element_form_default: the schema's *elementFormDefault* attribute. \
    Default is 'unqualified'.
    :cvar block_default: the schema's *blockDefault* attribute. Default is ''.
    :cvar final_default: the schema's *finalDefault* attribute. Default is ''.
    :cvar default_attributes: the XSD 1.1 schema's *defaultAttributes* attribute. \
    Default is ``None``.
    :cvar xpath_tokens: symbol table for schema bound XPath 2.0 parsers. Initially set to \
    ``None`` it's redefined at instance level with a dictionary at first use of the XPath \
    selector. The parser symbol table is extended with schema types constructors.

    :ivar target_namespace: is the *targetNamespace* of the schema, the namespace to which \
    belong the declarations/definitions of the schema. If it's empty no namespace is associated \
    with the schema. In this case the schema declarations can be reused from other namespaces as \
    *chameleon* definitions.
    :ivar maps: XSD global declarations/definitions maps. This is an instance of \
    :class:`XsdGlobals`, that stores the *global_maps* argument or a new object \
    when this argument is not provided.
    :ivar converter: the default converter used for XML data decoding/encoding.
    :ivar namespaces: a dictionary that maps from the prefixes used by the schema \
    into namespace URI.
    :ivar imports: a dictionary of namespace imports of the schema, that maps namespace \
    URI to imported schema object, or `None` in case of unsuccessful import.
    :ivar includes: a dictionary of included schemas, that maps a schema location to an \
    included schema. It also comprehends schemas included by "xs:redefine" or \
    "xs:override" statements.
    :ivar warnings: warning messages about failure of import and include elements.

    :ivar notations: `xsd:notation` declarations.
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
    # Instance attributes type annotations
    source: XMLResource
    namespaces: NsmapType
    converter: ConverterType
    maps: XsdGlobals
    imports: dict[str, Optional[SchemaType]]
    _import_statements: set[str]
    includes: dict[str, SchemaType]
    warnings: list[str]

    notations: NamespaceView[XsdNotation]
    types: NamespaceView[BaseXsdType]
    attributes: NamespaceView[XsdAttribute]
    attribute_groups: NamespaceView[XsdAttributeGroup]
    groups: NamespaceView[XsdGroup]
    elements: NamespaceView[XsdElement]
    substitution_groups: NamespaceView[list[XsdElement]]
    identities: NamespaceView[XsdIdentity]

    XSD_VERSION: str = '1.0'
    BASE_SCHEMAS: dict[str, str] = {}
    meta_schema: Optional['XMLSchemaBase'] = None
    _annotations: Optional[list[XsdAnnotation]] = None
    _components: Optional[dict[ElementType, XsdComponent]] = None
    _root_elements: Optional[set[str]] = None
    _xpath_node: Optional[SchemaElementNode]
    _validation_context: Optional[DecodeContext] = None

    # XSD components classes
    xsd_notation_class = XsdNotation
    xsd_complex_type_class = XsdComplexType
    xsd_attribute_class = XsdAttribute
    xsd_any_attribute_class = XsdAnyAttribute
    xsd_attribute_group_class = XsdAttributeGroup
    xsd_group_class = XsdGroup
    xsd_element_class = XsdElement
    xsd_any_class = XsdAnyElement
    xsd_atomic_restriction_class = XsdAtomicRestriction
    xsd_list_class = XsdList
    xsd_union_class = XsdUnion
    xsd_key_class = XsdKey
    xsd_keyref_class = XsdKeyref
    xsd_unique_class = XsdUnique

    # Schema defaults
    target_namespace = ''
    attribute_form_default = 'unqualified'
    element_form_default = 'unqualified'
    block_default = ''
    final_default = ''
    redefine: Optional['XMLSchemaBase'] = None

    # Additional defaults for XSD 1.1
    default_attributes: Optional[Union[str, XsdAttributeGroup]] = None
    default_open_content: Optional[XsdDefaultOpenContent] = None
    override: Optional['XMLSchemaBase'] = None
    use_xpath3: bool = False

    # Store XPath constructors tokens (for schema and its assertions)
    xpath_tokens: Optional[dict[str, Type[XPathToken]]] = None

    def __init__(self, source: Union[SchemaSourceType, list[SchemaSourceType]],
                 namespace: Optional[str] = None,
                 validation: str = 'strict',
                 global_maps: Optional[XsdGlobals] = None,
                 converter: Optional[ConverterType] = None,
                 locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 300,
                 uri_mapper: Optional[UriMapperType] = None,
                 opener: Optional[OpenerDirector] = None,
                 loader: Optional[Type[SchemaLoader]] = None,
                 build: bool = True,
                 use_meta: bool = True,
                 use_fallback: bool = True,
                 use_xpath3: bool = False,
                 loglevel: Optional[Union[str, int]] = None) -> None:

        super().__init__(validation)
        self.lock = threading.Lock()  # Lock for build operations

        if loglevel is not None:
            set_logging_level(loglevel)
        elif build and global_maps is None:
            logger.setLevel(logging.WARNING)

        if allow == 'sandbox' and base_url is None and is_local_url(source):
            # Allow sandbox mode without a base_url using the initial schema URL as base
            assert isinstance(source, str)
            base_url = os.path.dirname(normalize_url(source))

        other_sources: list[SchemaSourceType]
        if isinstance(source, list):
            if not source:
                raise XMLSchemaValueError(_("no XSD source provided!"))
            other_sources = source[1:]
            source = source[0]
        else:
            other_sources = []

        if isinstance(source, XMLResource):
            self.source = source
        else:
            self.source = XMLResource(
                source, base_url, allow, defuse, timeout, uri_mapper=uri_mapper, opener=opener
            )

        logger.debug("Load schema from %r", self.source.url or self.source.source)

        if converter is None:
            self.converter = XMLSchemaConverter
        else:
            check_converter_argument(converter)
            self.converter = converter

        self.imports = {}
        self._import_statements = set()
        self.includes = {}
        self.warnings = []

        self.name = self.source.name
        root = self.source.root

        # Initialize schema's namespaces, the XML namespace is implicitly declared.
        self.namespaces = self.source.get_namespaces({'xml': nm.XML_NAMESPACE})

        if 'targetNamespace' in root.attrib:
            self.target_namespace = root.attrib['targetNamespace'].strip()
            if not self.target_namespace:
                # https://www.w3.org/TR/2004/REC-xmlschema-1-20041028/structures.html#element-schema
                msg = _("the attribute 'targetNamespace' cannot be an empty string")
                self.parse_error(msg, root)
            elif namespace is not None and self.target_namespace != namespace:
                msg = _("wrong namespace ({0!r} instead of {1!r}) for XSD resource {2}")
                self.parse_error(msg.format(self.target_namespace, namespace, self.url), root)

        if not self.target_namespace and namespace is not None:
            # Chameleon schema case
            self.target_namespace = namespace
            if '' not in self.namespaces:
                self.namespaces[''] = namespace

        elif '' not in self.namespaces:
            # If not declared map the default namespace to no namespace
            self.namespaces[''] = ''

        if self.target_namespace == nm.XMLNS_NAMESPACE:
            # https://www.w3.org/TR/xmlschema11-1/#sec-nss-special
            msg = _(f"The namespace {nm.XMLNS_NAMESPACE} cannot be used as 'targetNamespace'")
            raise XMLSchemaValueError(msg)

        logger.debug("Schema targetNamespace is %r", self.target_namespace)
        logger.debug("Schema namespaces: %r", self.namespaces)

        # Parses the schema defaults
        if 'attributeFormDefault' in root.attrib:
            self.attribute_form_default = root.attrib['attributeFormDefault']

        if 'elementFormDefault' in root.attrib:
            self.element_form_default = root.attrib['elementFormDefault']

        if 'blockDefault' in root.attrib:
            if self.meta_schema is None:
                pass  # Skip for XSD 1.0 meta-schema that has blockDefault="#all"
            else:
                try:
                    self.block_default = get_xsd_derivation_attribute(
                        root, 'blockDefault', XSD_ELEMENT_DERIVATIONS
                    )
                except ValueError as err:
                    self.parse_error(err, root)

        if 'finalDefault' in root.attrib:
            try:
                self.final_default = get_xsd_derivation_attribute(root, 'finalDefault')
            except ValueError as err:
                self.parse_error(err, root)

        if self.meta_schema is None:
            # Meta-schema maps creation (MetaXMLSchema10/11 classes)
            self.maps = global_maps or XsdGlobals(self)
            for child in self.source.root:
                if child.tag == nm.XSD_OVERRIDE:
                    self.include_schema(child.attrib['schemaLocation'], self.base_url)
            return  # Meta-schemas don't need to be checked and don't process imports

        # Complete the namespace map with internal declarations, remapping
        # identical prefixes that refer to different namespaces.
        self.namespaces = self.source.get_namespaces(self.namespaces, root_only=False)

        with self.meta_schema.lock:
            if not self.meta_schema.maps.types:
                self.meta_schema.maps.build()

        # Create or set the XSD global maps instance
        if global_maps is None:
            loader_class = SchemaLoader if loader is None else loader
            _loader = loader_class(self, locations, base_url, use_fallback)

            if use_meta and self.target_namespace not in self.meta_schema.maps.namespaces:
                self.maps = self.meta_schema.maps.copy(self, _loader)
            else:
                self.maps = XsdGlobals(self, _loader)

        elif isinstance(global_maps, XsdGlobals):
            self.maps = global_maps
        else:
            raise XMLSchemaTypeError(
                _("'global_maps' argument must be an %r instance") % XsdGlobals
            )

        if use_xpath3 and self.XSD_VERSION > '1.0':
            self.use_xpath3 = True

        if any(ns == nm.VC_NAMESPACE for ns in self.namespaces.values()):
            # For XSD 1.1+ apply versioning filter to schema tree. See the paragraph
            # 4.2.2 of XSD 1.1 (Part 1: Structures) definition for details.
            # Ref: https://www.w3.org/TR/xmlschema11-1/#cip
            if prune_etree(root, selector=lambda x: not self.version_check(x)):
                for k in list(root.attrib):
                    if k not in ('targetNamespace', nm.VC_MIN_VERSION, nm.VC_MAX_VERSION):
                        del root.attrib[k]

        # Validate the schema document (transforming validation errors to parse errors)
        if validation != 'skip':
            for e in self.meta_schema.iter_errors(root, namespaces=self.namespaces):
                self.parse_error(e.reason or e, elem=e.elem)

        self.maps.loader.load_components(self)

        # Import namespaces by argument (usually from xsi:schemaLocation attribute).
        if global_maps is None:
            for ns in self.locations:
                if ns not in self.maps.namespaces:
                    self.maps.loader.import_namespace(self, ns, self.locations[ns])

        # XSD 1.1 default declarations (defaultAttributes, defaultOpenContent,
        # xpathDefaultNamespace)
        if self.XSD_VERSION > '1.0':
            self.xpath_default_namespace = self._parse_xpath_default_namespace(root)
            if 'defaultAttributes' in root.attrib:
                try:
                    self.default_attributes = self.resolve_qname(root.attrib['defaultAttributes'])
                except (ValueError, KeyError, RuntimeError) as err:
                    self.parse_error(err, root)

            for child in root:
                if child.tag == nm.XSD_DEFAULT_OPEN_CONTENT:
                    self.default_open_content = XsdDefaultOpenContent(child, self)
                    break

        _source: Union[SchemaSourceType, XMLResource]
        for _source in other_sources:
            if isinstance(_source, XMLResource):
                resource: XMLResource = _source
            else:
                resource = XMLResource(_source, base_url, allow, defuse, timeout)

            if not resource.root.get('targetNamespace') and self.target_namespace:
                # Adding a chameleon schema: set the namespace with targetNamespace
                self.add_schema(resource, namespace=self.target_namespace)
            else:
                self.add_schema(resource)

        try:
            if build:
                self.maps.build()
        finally:
            if loglevel is not None:
                logger.setLevel(logging.WARNING)  # Restore default logging

    def __repr__(self) -> str:
        if self.url:
            return '%s(name=%r, namespace=%r)' % (
                self.__class__.__name__, self.name, self.target_namespace
            )
        return '%s(namespace=%r)' % (self.__class__.__name__, self.target_namespace)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'maps':
            if self.meta_schema is None and hasattr(self, 'maps'):
                msg = _("cannot change the global maps instance of a meta-schema")
                raise XMLSchemaValueError(msg)

            super().__setattr__(name, value)
            self.notations = NamespaceView(value.notations, self.target_namespace)
            self.types = NamespaceView(value.types, self.target_namespace)
            self.attributes = NamespaceView(value.attributes, self.target_namespace)
            self.attribute_groups = NamespaceView(value.attribute_groups,
                                                  self.target_namespace)
            self.groups = NamespaceView(value.groups, self.target_namespace)
            self.elements = NamespaceView(value.elements, self.target_namespace)
            self.substitution_groups = NamespaceView(value.substitution_groups,
                                                     self.target_namespace)
            self.identities = NamespaceView(value.identities, self.target_namespace)
            value.register(self)
        else:
            if name == 'validation':
                check_validation_mode(value)
            super().__setattr__(name, value)

    def __iter__(self) -> Iterator[XsdElement]:
        yield from sorted(self.elements.values(), key=name_attribute)

    def __reversed__(self) -> Iterator[XsdElement]:
        yield from sorted(self.elements.values(), key=name_attribute, reverse=True)

    def __len__(self) -> int:
        return len(self.elements)

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state.pop('lock', None)
        state.pop('xpath_tokens', None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self.lock = threading.Lock()

    def copy(self) -> 'XMLSchemaBase':
        """
        Makes a copy of the schema instance. The new instance has independent maps
        but shares the already built XSD components.
        """
        schema: SchemaType = object.__new__(self.__class__)
        schema.__dict__.update(self.__dict__)
        schema.source = _copy(self.source)
        schema.errors = self.errors[:]
        schema.warnings = self.warnings[:]
        schema.namespaces = dict(self.namespaces)
        schema.imports = self.imports.copy()
        schema.includes = self.includes.copy()
        schema.maps = self.maps.copy(validator=schema)
        return schema

    __copy__ = copy

    @property
    def xpath_proxy(self) -> XMLSchemaProxy:
        return XMLSchemaProxy(self)

    @property
    def xpath_node(self) -> SchemaElementNode:
        """Returns an XPath node for processing an XPath expression on the schema instance."""
        if self._xpath_node is None:
            self._xpath_node = build_schema_node_tree(root=self, uri=self.url)
        return self._xpath_node

    @property
    def xsd_version(self) -> str:
        """Compatibility property that returns the class attribute XSD_VERSION."""
        return self.XSD_VERSION

    # XML resource attributes access
    @property
    def root(self) -> Element:
        """Root element of the schema."""
        return self.source.root

    def get_text(self) -> str:
        """Returns the source text of the XSD schema."""
        return self.source.get_text()

    @property
    def url(self) -> Optional[str]:
        """Schema resource URL, is `None` if the schema is built from an Element or a string."""
        return self.source.url

    @property
    def base_url(self) -> Optional[str]:
        """The base URL of the source of the schema."""
        return self.source.base_url

    @property
    def filepath(self) -> Optional[str]:
        """The filepath if the schema is loaded from a local XSD file, `None` otherwise."""
        return self.source.filepath

    @property
    def allow(self) -> str:
        """
        The resource access security mode: can be 'all', 'remote', 'local' or 'sandbox'.
        """
        return self.source.allow

    @property
    def defuse(self) -> str:
        """Defines when to defuse XML data: can be 'always', 'remote' or 'never'."""
        return self.source.defuse

    @property
    def timeout(self) -> int:
        """Timeout in seconds for fetching resources."""
        return self.source.timeout

    @property
    def uri_mapper(self) -> Optional[UriMapperType]:
        """The optional URI mapper argument for relocating addressed resources."""
        return self.source.uri_mapper

    @property
    def opener(self) -> Optional[OpenerDirector]:
        """The optional OpenerDirector argument opening addressed resources."""
        return self.source.opener

    @property
    def use_meta(self) -> bool:
        """Returns `True` if the class meta-schema is used."""
        return self.meta_schema is self.__class__.meta_schema

    # Schema root attributes
    @property
    def tag(self) -> str:
        """Schema root tag. For compatibility with the ElementTree API."""
        return self.source.root.tag

    @property
    def id(self) -> Optional[str]:
        """The schema's *id* attribute, defaults to ``None``."""
        return self.source.root.get('id')

    @property
    def version(self) -> Optional[str]:
        """The schema's *version* attribute, defaults to ``None``."""
        return self.source.root.get('version')

    @property
    def locations(self) -> LocationHints:
        return self.maps.loader.locations

    @property
    def schema_location(self) -> list[tuple[str, str]]:
        """
        A list of location hints extracted from the *xsi:schemaLocation* attribute of the schema.
        """
        return [(k, v) for k, v in self.source.iter_location_hints() if k]

    @property
    def no_namespace_schema_location(self) -> Optional[str]:
        """
        A location hint extracted from the *xsi:noNamespaceSchemaLocation* attribute of the schema.
        """
        for k, v in self.source.iter_location_hints():
            if not k:
                return v
        return None

    @property
    def default_namespace(self) -> Optional[str]:
        """The namespace associated to the empty prefix ''."""
        return self.namespaces.get('')

    @property
    def target_prefix(self) -> str:
        """The prefix associated to the *targetNamespace*."""
        for prefix, namespace in self.namespaces.items():
            if namespace == self.target_namespace:
                return prefix
        return ''

    @classmethod
    def builtin_types(cls) -> NamespaceView[BaseXsdType]:
        """Returns the XSD built-in types of the meta-schema."""
        if cls.meta_schema is None:
            raise XMLSchemaRuntimeError(_("meta-schema unavailable for %r") % cls)

        try:
            meta_schema: SchemaType = cls.meta_schema.maps.namespaces[nm.XSD_NAMESPACE][0]
            builtin_types = meta_schema.types
        except KeyError:
            raise XMLSchemaNotBuiltError(
                cls.meta_schema, _("missing XSD namespace in meta-schema")
            )
        else:
            if not builtin_types:
                cls.meta_schema.build()
            return builtin_types

    @property
    def annotations(self) -> list[XsdAnnotation]:
        """
        Annotations related to schema object. This list includes the annotations
        of xs:include, xs:import, xs:redefine and xs:override elements.
        """
        if self._annotations is None:
            self._annotations = []
            for elem in self.source.root:
                if elem.tag == nm.XSD_ANNOTATION:
                    self._annotations.append(XsdAnnotation(elem, self))
                elif elem.tag in (nm.XSD_IMPORT, nm.XSD_INCLUDE, nm.XSD_DEFAULT_OPEN_CONTENT):
                    child = get_xsd_annotation_child(elem)
                    if child is not None:
                        annotation = XsdAnnotation(child, self, parent_elem=elem)
                        self._annotations.append(annotation)
                elif elem.tag in (nm.XSD_REDEFINE, nm.XSD_OVERRIDE):
                    for child in elem:
                        if child.tag == nm.XSD_ANNOTATION:
                            annotation = XsdAnnotation(child, self, parent_elem=elem)
                            self._annotations.append(annotation)

        return self._annotations

    @property
    def components(self) -> dict[ElementType, XsdComponent]:
        """A map from XSD ElementTree elements to their schema components."""
        if self._components is None:
            self.check_validator(self.validation)
            self._components = {
                c.elem: c for c in self.iter_components() if isinstance(c, XsdComponent)
            }
        return self._components

    @property
    def root_elements(self) -> list[XsdElement]:
        """
        The list of global elements that are not used by reference in any model of the schema.
        This is implemented as lazy property because it's computationally expensive to build
        when the schema model is complex.
        """
        if not self.elements:
            return []
        elif len(self.elements) == 1:
            return list(self.elements.values())
        elif self._root_elements is None:
            names = {e.name for e in self.elements.values()}
            for xsd_element in self.elements.values():
                for e in xsd_element.iter():
                    if e is xsd_element or isinstance(e, XsdAnyElement):
                        continue
                    elif e.ref or e.parent is None:
                        if e.name in names:
                            names.discard(e.name)
                            if not names:
                                break
            self._root_elements = set(names)

        assert self._root_elements is not None
        return [e for e in self.elements.values() if e.name in self._root_elements]

    @property
    def validation_context(self) -> DecodeContext:
        """
        A validation context instance used internally for decoding schema simple values.
        """
        if self._validation_context is None:
            self._validation_context = DecodeContext(
                source=self.source,
                validation=self.validation,
                validation_only=True,
                namespaces=self.namespaces,
                xmlns_processing='none'
            )
        return self._validation_context

    @property
    def simple_types(self) -> list[XsdSimpleType]:
        """Returns a list containing the global simple types."""
        return [x for x in self.types.values() if isinstance(x, XsdSimpleType)]

    @property
    def complex_types(self) -> list[XsdComplexType]:
        """Returns a list containing the global complex types."""
        return [x for x in self.types.values() if isinstance(x, XsdComplexType)]

    @classmethod
    def create_meta_schema(cls, source: Optional[str] = None,
                           base_schemas: Union[None, dict[str, str],
                                               list[tuple[str, str]]] = None,
                           global_maps: Optional[XsdGlobals] = None) -> SchemaType:
        """
        Creates a new meta-schema instance.

        :param source: an optional argument referencing to or containing the XSD meta-schema \
        resource. Required if the schema class doesn't already have a meta-schema.
        :param base_schemas: an optional dictionary that contains namespace URIs and \
        schema locations. If provided is used as substitute for class BASE_SCHEMAS. \
        Also a sequence of (namespace, location) items can be provided if there are more \
        schema documents for one or more namespaces.
        :param global_maps: is an optional argument containing an :class:`XsdGlobals` \
        instance for the new meta schema. If not provided a new map is created.
        """
        if source is None:
            if cls.meta_schema is None or not cls.meta_schema.url:
                raise XMLSchemaValueError(_("Missing meta-schema source URL"))
            source = cls.meta_schema.url

        _base_schemas: Union[ItemsView[str, str], list[tuple[str, str]]]
        if base_schemas is None:
            _base_schemas = cls.BASE_SCHEMAS.items()
        elif isinstance(base_schemas, dict):
            _base_schemas = base_schemas.items()
        else:
            try:
                _base_schemas = [(n, l) for n, l in base_schemas]
            except ValueError:
                msg = _("The argument 'base_schemas' must be a "
                        "dictionary or a sequence of couples")
                raise XMLSchemaValueError(msg) from None

        meta_schema: SchemaType
        meta_schema_class = cls if cls.meta_schema is None else cls.meta_schema.__class__

        if global_maps is None:
            meta_schema = meta_schema_class(source, nm.XSD_NAMESPACE, defuse='never', build=False)
            global_maps = meta_schema.maps
        elif nm.XSD_NAMESPACE not in global_maps.namespaces:
            meta_schema = meta_schema_class(source, nm.XSD_NAMESPACE, global_maps=global_maps,
                                            defuse='never', build=False)
        else:
            meta_schema = global_maps.namespaces[nm.XSD_NAMESPACE][0]

        for ns, location in _base_schemas:
            if ns == nm.XSD_NAMESPACE:
                meta_schema.include_schema(location=location)
            elif ns not in global_maps.namespaces:
                meta_schema.import_schema(namespace=ns, location=location)

        return meta_schema

    def simple_type_factory(self, elem: Element,
                            schema: Optional[SchemaType] = None,
                            parent: Optional[XsdComponent] = None) -> XsdSimpleType:
        """
        Factory function for XSD simple types. Parses the xs:simpleType element and its
        child component, that can be a restriction, a list or a union. Annotations are
        linked to simple type instance, omitting the inner annotation if both are given.
        """
        if schema is None:
            schema = self

        annotation = None
        try:
            child = elem[0]
        except IndexError:
            return cast(XsdSimpleType, self.maps.types[nm.XSD_ANY_SIMPLE_TYPE])
        else:
            if child.tag == nm.XSD_ANNOTATION:
                annotation = XsdAnnotation(child, schema, parent)
                try:
                    child = elem[1]
                except IndexError:
                    msg = _("(restriction | list | union) expected")
                    schema.parse_error(msg, elem)
                    return cast(XsdSimpleType, self.maps.types[nm.XSD_ANY_SIMPLE_TYPE])

        xsd_type: XsdSimpleType
        if child.tag == nm.XSD_RESTRICTION:
            xsd_type = self.xsd_atomic_restriction_class(child, schema, parent)
        elif child.tag == nm.XSD_LIST:
            xsd_type = self.xsd_list_class(child, schema, parent)
        elif child.tag == nm.XSD_UNION:
            xsd_type = self.xsd_union_class(child, schema, parent)
        else:
            msg = _("(restriction | list | union) expected")
            schema.parse_error(msg, elem)
            return cast(XsdSimpleType, self.maps.types[nm.XSD_ANY_SIMPLE_TYPE])

        if annotation is not None:
            xsd_type._annotation = annotation

        try:
            xsd_type.name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            if parent is None:
                msg = _("missing attribute 'name' in a global simpleType")
                schema.parse_error(msg, elem)
                xsd_type.name = 'nameless_%s' % str(id(xsd_type))
        else:
            if parent is not None:
                msg = _("attribute 'name' not allowed for a local simpleType")
                schema.parse_error(msg, elem)
                xsd_type.name = None

        if 'final' in elem.attrib:
            try:
                xsd_type._final = get_xsd_derivation_attribute(elem, 'final')
            except ValueError as err:
                xsd_type.parse_error(err, elem)

        return xsd_type

    def create_any_content_group(self, parent: Union[XsdComplexType, XsdGroup],
                                 any_element: Optional[XsdAnyElement] = None) -> XsdGroup:
        """
        Creates a model group related to schema instance that accepts any content.

        :param parent: the parent component to set for the content group.
        :param any_element: an optional any element to use for the content group. \
        When provided it's copied, linked to the group and the minOccurs/maxOccurs \
        are set to 0 and 'unbounded'.
        """
        group: XsdGroup = self.xsd_group_class(SEQUENCE_ELEMENT, self, parent)

        if isinstance(any_element, XsdAnyElement):
            particle = _copy(any_element)
            particle.min_occurs = 0
            particle.max_occurs = None
            particle.parent = group
            group.append(particle)
        else:
            group.append(self.xsd_any_class(ANY_ELEMENT, self, group))

        return group

    def create_empty_content_group(self, parent: Union[XsdComplexType, XsdGroup],
                                   model: str = 'sequence', **attrib: Any) -> XsdGroup:
        if model == 'sequence':
            group_elem = Element(nm.XSD_SEQUENCE, **attrib)
        elif model == 'choice':
            group_elem = Element(nm.XSD_CHOICE, **attrib)
        elif model == 'all':
            group_elem = Element(nm.XSD_ALL, **attrib)
        else:
            msg = _("'model' argument must be (sequence | choice | all)")
            raise XMLSchemaValueError(msg)

        group_elem.text = '\n    '
        return self.xsd_group_class(group_elem, self, parent)

    def create_any_attribute_group(self, parent: Union[XsdComplexType, XsdElement]) \
            -> XsdAttributeGroup:
        """
        Creates an attribute group related to schema instance that accepts any attribute.

        :param parent: the parent component to set for the attribute group.
        """
        attribute_group = self.xsd_attribute_group_class(
            ATTRIBUTE_GROUP_ELEMENT, self, parent
        )
        attribute_group[None] = self.xsd_any_attribute_class(
            ANY_ATTRIBUTE_ELEMENT, self, attribute_group
        )
        return attribute_group

    def create_empty_attribute_group(self, parent: Union[XsdComplexType, XsdElement]) \
            -> XsdAttributeGroup:
        """
        Creates an empty attribute group related to schema instance.

        :param parent: the parent component to set for the attribute group.
        """
        return self.xsd_attribute_group_class(ATTRIBUTE_GROUP_ELEMENT, self, parent)

    def create_any_type(self) -> XsdComplexType:
        """
        Creates a xs:anyType equivalent type related with the wildcards
        connected to global maps of the schema instance in order to do a
        correct namespace lookup during wildcards validation.
        """
        schema = self.meta_schema or self
        any_type = self.xsd_complex_type_class(
            elem=Element(nm.XSD_COMPLEX_TYPE, name=nm.XSD_ANY_TYPE),
            schema=schema, parent=None, mixed=True, block='', final=''
        )
        assert isinstance(any_type.content, XsdGroup)
        any_type.content.append(self.xsd_any_class(
            ANY_ELEMENT, schema, any_type.content
        ))
        any_type.attributes[None] = self.xsd_any_attribute_class(
            ANY_ATTRIBUTE_ELEMENT, schema, any_type.attributes
        )
        any_type.maps = any_type.content.maps = any_type.content[0].maps = \
            any_type.attributes[None].maps = self.maps
        return any_type

    def create_element(self, name: str, parent: Optional[XsdComponent] = None,
                       text: Optional[str] = None, **attrib: Any) -> XsdElement:
        """
        Creates a xs:element instance related to schema component.
        Used as dummy element for validation/decoding/encoding
        operations of wildcards and complex types.
        """
        elem = Element(nm.XSD_ELEMENT, name=name, **attrib)
        if text is not None:
            elem.text = text
        return self.xsd_element_class(elem=elem, schema=self, parent=parent)

    def check_validator(self, validation: str = 'strict') -> None:
        """Checks the status of a schema validator against a validation mode."""
        check_validation_mode(validation)

        if self.built:
            pass
        elif self.meta_schema is None:
            self.build()  # Meta-schema lazy build
        elif validation == 'skip' and self.validation == 'skip' and \
                any(isinstance(comp, tuple) or comp.validation_attempted == 'partial'
                    for comp in self.iter_globals()):
            pass
        else:
            raise XMLSchemaNotBuiltError(self, _("schema %r is not built") % self)

    def build(self) -> None:
        """Builds the schema's XSD global maps."""
        self.maps.build()

    def clear(self) -> None:
        """Clears the schema's XSD global maps."""
        self.maps.clear()
        self._xpath_node = None
        self._annotations = None
        self._components = None
        self._root_elements = None

    @property
    def built(self) -> bool:
        if any(not isinstance(g, XsdComponent) or not g.built for g in self.iter_globals()):
            return False
        for _xsd_global in self.iter_globals():
            return True
        if self.meta_schema is None:
            return False

        # No XSD globals: check with a lookup of schema child elements.
        prefix = f'{{{self.target_namespace}}}' if self.target_namespace else ''
        for child in self.source.root:
            if child.tag in (nm.XSD_REDEFINE, nm.XSD_OVERRIDE):
                for e in filter(lambda x: x.tag in GLOBAL_TAGS, child):
                    name = e.get('name')
                    if name is not None:
                        try:
                            if not self.maps.lookup(e.tag, prefix + name if prefix else name).built:
                                return False
                        except KeyError:
                            return False
            elif child.tag in GLOBAL_TAGS:
                name = child.get('name')
                if name is not None:
                    try:
                        if not self.maps.lookup(child.tag, prefix + name if prefix else name).built:
                            return False
                    except KeyError:
                        return False
        return True

    @property
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif any(isinstance(comp, tuple) or comp.validation_attempted == 'partial'
                 for comp in self.iter_globals()):
            return 'partial'
        else:
            return 'none'

    def iter_globals(self, schema: Optional[SchemaType] = None) \
            -> Iterator[Union[SchemaGlobalType, tuple[Any, ...]]]:
        """
        Creates an iterator for XSD global definitions/declarations related to schema namespace.

        :param schema: Optional argument for filtering only globals related to a schema instance.
        """
        if schema is None:
            yield from self.notations.values()
            yield from self.types.values()
            yield from self.attributes.values()
            yield from self.attribute_groups.values()
            yield from self.groups.values()
            yield from self.elements.values()
        else:
            def schema_filter(x: Union[XsdComponent, tuple[Element, SchemaType]]) -> bool:
                if isinstance(x, tuple):
                    return x[1] is schema
                return x.schema is schema

            yield from filter(schema_filter, self.notations.values())
            yield from filter(schema_filter, self.types.values())
            yield from filter(schema_filter, self.attributes.values())
            yield from filter(schema_filter, self.attribute_groups.values())
            yield from filter(schema_filter, self.groups.values())
            yield from filter(schema_filter, self.elements.values())

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[Union[XsdComponent, SchemaType]]:
        """
        Iterates yielding the schema and its components. For default
        includes all the relevant components of the schema, excluding
        only facets and empty attribute groups. The first returned
        component is the schema itself.

        :param xsd_classes: provide a class or a tuple of classes to \
        restrict the range of component types yielded.
        """
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.iter_globals(self):
            if not isinstance(xsd_global, tuple):
                yield from xsd_global.iter_components(xsd_classes)

    def get_converter(self, converter: Optional[ConverterType] = None,
                      **kwargs: Any) -> XMLSchemaConverter:
        """
        Returns a new converter instance.

        :param converter: can be a converter class or instance. If not provided the \
        converter attribute of the schema instance is used.
        :param kwargs: optional arguments for initialize the converter instance.
        :return: a converter instance.
        """
        if converter is None:
            converter = self.converter
        return get_converter(converter, **kwargs)

    def get_locations(self, namespace: str) -> list[str]:
        """Get a list of location hints for a namespace."""
        return self.maps.loader.get_locations(namespace)

    def get_schema(self, namespace: str) -> SchemaType:
        """
        Returns the first schema loaded for a namespace. Raises a
        `KeyError` if the requested namespace is not loaded.
        """
        try:
            return cast(SchemaType, self.maps.namespaces[namespace][0])
        except KeyError:
            if not namespace:
                return self
            msg = _('the namespace {!r} is not loaded')
            raise XMLSchemaKeyError(msg.format(namespace)) from None

    def get_element(self, tag: str, path: Optional[str] = None,
                    namespaces: Optional[NsmapType] = None) -> Optional[XsdElement]:
        if not path:
            xsd_element = self.find(tag)
            return xsd_element if isinstance(xsd_element, XsdElement) else None
        elif path[-1] == '*':
            xsd_element = self.find(path[:-1] + tag, namespaces)
            if isinstance(xsd_element, XsdElement):
                return xsd_element

            obj = self.maps.elements.get(tag)
            return obj if isinstance(obj, XsdElement) else None
        else:
            xsd_element = self.find(path, namespaces)
            return xsd_element if isinstance(xsd_element, XsdElement) else None

    def create_bindings(self, *bases: type, **attrs: Any) -> None:
        """
        Creates data object bindings for XSD elements of the schema.

        :param bases: base classes to use for creating the binding classes.
        :param attrs: attribute and method definitions for the binding classes body.
        """
        for xsd_component in self.iter_components():
            if isinstance(xsd_component, XsdElement):
                xsd_component.get_binding(*bases, replace_existing=True, **attrs)

    def include_schema(self, location: str, base_url: Optional[str] = None,
                       build: bool = False) -> SchemaType:
        """
        Includes a schema for the same namespace, from a specific URL.

        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :param build: defines when to build the imported schema, the default is to not build.
        :return: the included :class:`XMLSchema` instance.
        """
        return self.maps.loader.include_schema(self, location, base_url, build)

    def import_schema(self, namespace: str, location: str, base_url: Optional[str] = None,
                      force: bool = False, build: bool = False) -> Optional[SchemaType]:
        """
        Imports a schema for an external namespace from a specific location.

        :param namespace: is the URI of the external namespace.
        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :param force: if set to `True` imports the schema also if the namespace is already imported.
        :param build: defines when to build the imported schema, the default is to not build.
        :return: the imported :class:`XMLSchema` instance, or `None` if the schema is already imported.
        """
        if not force:
            if self.imports.get(namespace) is not None:
                return self.imports[namespace]
            elif namespace in self.maps.namespaces:
                self.imports[namespace] = self.maps.namespaces[namespace][0]
                return self.imports[namespace]

        schema: SchemaType
        url = normalize_url(location, base_url)
        imported_ns = self.imports.get(namespace)
        if imported_ns is not None and imported_ns.url == url:
            return imported_ns
        elif namespace in self.maps.namespaces:
            for schema in self.maps.namespaces[namespace]:
                if url == schema.url:
                    self.imports[namespace] = schema
                    return schema

        locations = deepcopy(self.locations)
        if namespace in locations:
            locations.pop(namespace)

        schema = type(self)(
            source=url,
            validation=self.validation,
            global_maps=self.maps,
            converter=self.converter,
            base_url=self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
            build=build,
            use_xpath3=self.use_xpath3,
        )
        if schema.target_namespace != namespace:
            msg = _('imported schema {0!r} has an unmatched namespace {1!r}')
            raise XMLSchemaValueError(msg.format(location, namespace))

        self.imports[namespace] = schema
        return schema

    def add_schema(self, source: SchemaSourceType,
                   namespace: Optional[str] = None, build: bool = False) -> SchemaType:
        """
        Add another schema source to the maps of the instance.

        :param source: a URI that reference to a resource or a file path or a file-like \
        object or a string containing the schema or an Element or an ElementTree document.
        :param namespace: is an optional argument that contains the URI of the namespace \
        that has to used in case the schema has no namespace (chameleon schema). For other \
        cases, when specified, it must be equal to the *targetNamespace* of the schema.
        :param build: defines when to build the imported schema, the default is to not build.
        :return: the added :class:`XMLSchema` instance.
        """
        locations = deepcopy(self.locations)
        if namespace is None:
            if '' in locations:
                locations.pop('')
        elif namespace in locations:
            locations.pop(namespace)

        return type(self)(
            source=source,
            namespace=namespace,
            validation=self.validation,
            global_maps=self.maps,
            converter=self.converter,
            base_url=self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
            build=build,
            use_xpath3=self.use_xpath3,
        )

    def export(self, target: Union[str, Path],
               save_remote: bool = False,
               remove_residuals: bool = True,
               exclude_locations: Optional[list[str]] = None,
               loglevel: Optional[Union[str, int]] = None) -> dict[str, str]:
        """
        Exports a schema instance. The schema instance is exported to a
        directory with also the hierarchy of imported/included schemas.

        :param target: a path to a local empty directory.
        :param save_remote: if `True` is provided saves also remote schemas.
        :param remove_residuals: for default removes residual remote schema \
        locations from redundant import statements.
        :param exclude_locations: explicitly exclude schema locations from \
        substitution or removal.
        :param loglevel: for setting a different logging level for schema export.
        :return: a dictionary containing the map of modified locations.
        """
        return export_schema(
            schema=self,
            target=target,
            save_remote=save_remote,
            remove_residuals=remove_residuals,
            exclude_locations=exclude_locations,
            loglevel=loglevel
        )

    def version_check(self, elem: Element) -> bool:
        """
        Checks if the element is compatible with the version of the validator and XSD
        types/facets availability. Invalid vc attributes are not detected in XSD 1.0.

        :param elem: an Element of the schema.
        :return: `True` if the schema element is compatible with the validator, \
        `False` otherwise.
        """
        if nm.VC_MIN_VERSION in elem.attrib:
            vc_min_version = elem.attrib[nm.VC_MIN_VERSION]
            if not XSD_VERSION_PATTERN.match(vc_min_version):
                if self.XSD_VERSION > '1.0':
                    msg = _("invalid attribute vc:minVersion value")
                    self.parse_error(msg, elem)
            elif vc_min_version > self.XSD_VERSION:
                return False

        if nm.VC_MAX_VERSION in elem.attrib:
            vc_max_version = elem.attrib[nm.VC_MAX_VERSION]
            if not XSD_VERSION_PATTERN.match(vc_max_version):
                if self.XSD_VERSION > '1.0':
                    msg = _("invalid attribute vc:maxVersion value")
                    self.parse_error(msg, elem)
            elif vc_max_version <= self.XSD_VERSION:
                return False

        if nm.VC_TYPE_AVAILABLE in elem.attrib:
            for qname in elem.attrib[nm.VC_TYPE_AVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in self.maps.types:
                        return False
                except XMLSchemaNamespaceError:
                    return False
                except (KeyError, ValueError) as err:
                    self.parse_error(str(err), elem)

        if nm.VC_TYPE_UNAVAILABLE in elem.attrib:
            for qname in elem.attrib[nm.VC_TYPE_UNAVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in self.maps.types:
                        break
                except XMLSchemaNamespaceError:
                    break
                except (KeyError, ValueError) as err:
                    self.parse_error(err, elem)
            else:
                return False

        if nm.VC_FACET_AVAILABLE in elem.attrib:
            for qname in elem.attrib[nm.VC_FACET_AVAILABLE].split():
                try:
                    facet_name = self.resolve_qname(qname)
                except XMLSchemaNamespaceError:
                    pass
                except (KeyError, ValueError) as err:
                    self.parse_error(str(err), elem)
                else:
                    if self.XSD_VERSION == '1.0':
                        if facet_name not in XSD_10_FACETS:
                            return False
                    elif facet_name not in XSD_11_FACETS:
                        return False

        if nm.VC_FACET_UNAVAILABLE in elem.attrib:
            for qname in elem.attrib[nm.VC_FACET_UNAVAILABLE].split():
                try:
                    facet_name = self.resolve_qname(qname)
                except XMLSchemaNamespaceError:
                    break
                except (KeyError, ValueError) as err:
                    self.parse_error(err, elem)
                else:
                    if self.XSD_VERSION == '1.0':
                        if facet_name not in XSD_10_FACETS:
                            break
                    elif facet_name not in XSD_11_FACETS:
                        break
            else:
                return False

        return True

    def resolve_qname(self, qname: str, namespace_imported: bool = True) -> str:
        """
        QName resolution for a schema instance.

        :param qname: a string in xs:QName format.
        :param namespace_imported: if this argument is `True` raises an \
        `XMLSchemaNamespaceError` if the namespace of the QName is not the \
        *targetNamespace* and the namespace is not imported by the schema.
        :returns: an expanded QName in the format "{*namespace-URI*}*local-name*".
        :raises: `XMLSchemaValueError` for an invalid xs:QName is found, \
        `XMLSchemaKeyError` if the namespace prefix is not declared in the \
        schema instance.
        """
        qname = qname.strip()
        if not qname or ' ' in qname or '\t' in qname or '\n' in qname:
            msg = _("{!r} is not a valid value for xs:QName")
            raise XMLSchemaValueError(msg.format(qname))

        if qname[0] == '{':
            try:
                namespace, local_name = qname[1:].split('}')
            except ValueError:
                msg = _("{!r} is not a valid value for xs:QName")
                raise XMLSchemaValueError(msg.format(qname))
        elif ':' in qname:
            try:
                prefix, local_name = qname.split(':')
            except ValueError:
                msg = _("{!r} is not a valid value for xs:QName")
                raise XMLSchemaValueError(msg.format(qname))
            else:
                try:
                    namespace = self.namespaces[prefix]
                except KeyError:
                    msg = _("prefix {!r} not found in namespace map")
                    raise XMLSchemaKeyError(msg.format(prefix))
        else:
            namespace, local_name = self.namespaces.get('', ''), qname

        if not namespace:
            if namespace_imported and self.target_namespace \
                    and '' not in self._import_statements:
                msg = _("the QName {!r} is mapped to no namespace, but this requires "
                        "that there is an xs:import statement in the schema without "
                        "the 'namespace' attribute.")
                raise XMLSchemaNamespaceError(msg.format(qname))
            return local_name
        elif namespace_imported and self.meta_schema is not None and \
                namespace != self.target_namespace and \
                namespace not in (nm.XSD_NAMESPACE, nm.XSI_NAMESPACE) and \
                namespace not in self._import_statements:
            msg = _("the QName {0!r} is mapped to the namespace {1!r}, but this "
                    "namespace has not an xs:import statement in the schema.")
            raise XMLSchemaNamespaceError(msg.format(qname, namespace))

        return f'{{{namespace}}}{local_name}'

    def validate(self, source: Union[XMLSourceType, XMLResource],
                 path: Optional[str] = None,
                 schema_path: Optional[str] = None,
                 use_defaults: bool = True,
                 namespaces: Optional[NsmapType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None,
                 validation_hook: Optional[ValidationHookType] = None,
                 allow_empty: bool = True,
                 use_location_hints: bool = False) -> None:
        """
        Validates an XML data against the XSD schema/component instance.

        :param source: the source of XML data. Can be an :class:`XMLResource` instance, a \
        path to a file or a URI of a resource or an opened file-like object or an Element \
        instance or an ElementTree instance or a string containing the XML data.
        :param path: is an optional XPath expression that matches the elements of the XML \
        data that have to be decoded. If not provided the XML root element is selected.
        :param schema_path: an alternative XPath expression to select the XSD element \
        to use for decoding. Useful if the root of the XML data doesn't match an XSD \
        global element of the schema.
        :param use_defaults: Use schema's default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param max_depth: maximum level of validation, for default there is no limit. \
        With lazy resources is set to `source.lazy_depth` for managing lazy validation.
        :param extra_validator: an optional function for performing non-standard \
        validations on XML data. The provided function is called for each traversed \
        element, with the XML element as 1st argument and the corresponding XSD \
        element as 2nd argument. It can be also a generator function and has to \
        raise/yield :exc:`XMLSchemaValidationError` exceptions.
        :param validation_hook: an optional function for stopping or changing \
        validation at element level. The provided function must accept two arguments, \
        the XML element and the matching XSD element. If the value returned by this \
        function is evaluated to false then the validation process continues without \
        changes, otherwise the validation process is stopped or changed. If the value \
        returned is a validation mode the validation process continues changing the \
        current validation mode to the returned value, otherwise the element and its \
        content are not processed. The function can also stop validation suddenly \
        raising a `XmlSchemaStopValidation` exception.
        :param allow_empty: for default providing a path argument empty selections \
        of XML data are allowed. Provide `False` to generate a validation error.
        :param use_location_hints: for default schema locations hints provided within \
        XML data are ignored in order to avoid the change of schema instance. Set this \
        option to `True` to activate dynamic schema loading using schema location hints.
        :raises: :exc:`XMLSchemaValidationError` if the XML data instance is invalid.
        """
        for error in self.iter_errors(source, path, schema_path, use_defaults,
                                      namespaces, max_depth, extra_validator,
                                      validation_hook, allow_empty, use_location_hints,
                                      validation='strict'):
            raise error

    def is_valid(self, source: Union[XMLSourceType, XMLResource],
                 path: Optional[str] = None,
                 schema_path: Optional[str] = None,
                 use_defaults: bool = True,
                 namespaces: Optional[NsmapType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None,
                 validation_hook: Optional[ValidationHookType] = None,
                 allow_empty: bool = True,
                 use_location_hints: bool = False) -> bool:
        """
        Like :meth:`validate` except that does not raise an exception but returns
        ``True`` if the XML data instance is valid, ``False`` if it is invalid.
        """
        error = next(self.iter_errors(source, path, schema_path, use_defaults,
                                      namespaces, max_depth, extra_validator,
                                      validation_hook, allow_empty, use_location_hints), None)
        return error is None

    def iter_errors(self, source: Union[XMLSourceType, XMLResource],
                    path: Optional[str] = None,
                    schema_path: Optional[str] = None,
                    use_defaults: bool = True,
                    namespaces: Optional[NsmapType] = None,
                    max_depth: Optional[int] = None,
                    extra_validator: Optional[ExtraValidatorType] = None,
                    validation_hook: Optional[ValidationHookType] = None,
                    allow_empty: bool = True,
                    use_location_hints: bool = False, validation: str = 'lax') \
            -> Iterator[XMLSchemaValidationError]:
        """
        Creates an iterator for the errors generated by the validation of an XML data against
        the XSD schema/component instance. Accepts the same arguments of :meth:`validate`.
        """
        self.check_validator(validation='lax')
        if isinstance(source, XMLResource):
            resource: XMLResource = source
        else:
            resource = XMLResource(source, defuse=self.defuse, timeout=self.timeout)

        ancestors: list[Element] = []
        prev_ancestors: list[Element] = []
        kwargs: dict[Any, Any] = {
            'level': resource.lazy_depth or bool(path),
            'namespaces': namespaces,
            'validation_only': True,
            'check_identities': True,
            'use_defaults': use_defaults,
            'use_location_hints': use_location_hints,
            'max_depth': max_depth,
            'extra_validator': extra_validator,
            'validation_hook': validation_hook,
        }
        context = DecodeContext(resource, validation, **kwargs)
        namespaces = context.namespaces
        identities = context.identities

        namespace = resource.namespace or namespaces.get('', '')
        try:
            schema = self.get_schema(namespace)
        except KeyError:
            schema = self

        if not schema_path:
            schema_path = resource.get_absolute_path(path)

        if path:
            selector = resource.iterfind(path, namespaces, ancestors=ancestors)
        else:
            selector = resource.iter_depth(mode=4, ancestors=ancestors)

        elem: Optional[Element] = None
        for elem in selector:
            if elem is resource.root:
                if resource.lazy_depth:
                    context.level = 0
                    context.identities = {}
                    context.max_depth = resource.lazy_depth
            else:
                if prev_ancestors != ancestors:
                    k = 0
                    for k in range(min(len(ancestors), len(prev_ancestors))):
                        if ancestors[k] is not prev_ancestors[k]:
                            break

                    path_ = f"{'/'.join(e.tag for e in ancestors)}/ancestor-or-self::node()"
                    xsd_ancestors = cast(list[XsdElement],
                                         schema.findall(path_, namespaces)[1:])

                    # Clear identity constraints counters
                    for k, e in enumerate(xsd_ancestors[k:], start=k):
                        for identity in e.identities:
                            if identity in identities:
                                identities[identity].reset(ancestors[k])
                            else:
                                identities[identity] = identity.get_counter(ancestors[k])

                    prev_ancestors = ancestors[:]

            xsd_element = schema.get_element(elem.tag, schema_path, namespaces)
            if xsd_element is None:
                if nm.XSI_TYPE in elem.attrib:
                    xsd_element = self.create_element(name=elem.tag)
                elif elem is not resource.root and ancestors:
                    continue
                else:
                    reason = _("{!r} is not an element of the schema").format(elem)
                    yield context.validation_error(validation, self, reason, elem)
                    return

            try:
                xsd_element.raw_decode(elem, validation, context)
            except XMLSchemaStopValidation:
                pass

            yield from context.errors
            context.errors.clear()
        else:
            if elem is None and not allow_empty:
                assert path is not None
                reason = _("the provided path selects nothing to validate")
                yield context.validation_error(validation, self, reason)
                return

        if context.identities is not identities:
            for identity, counter in context.identities.items():
                identities[identity].counter.update(counter.counter)
            context.identities = identities

        yield from self._validate_references(validation, context)

    def _validate_references(self, validation: str, context: DecodeContext) \
            -> Iterator[XMLSchemaValidationError]:
        # Check unresolved IDREF values
        for k, v in context.id_map.items():
            if v == 0:
                msg = _("IDREF %r not found in XML document") % k
                yield context.validation_error(validation, self, msg, context.source.root)

        # Check still enabled key references (lazy validation cases)
        for identity, counter in context.identities.items():
            if counter.enabled and isinstance(identity, XsdKeyref):
                for error in cast(KeyrefCounter, counter).iter_errors(context.identities):
                    yield context.validation_error(validation, self, error, context.source.root)

    def raw_decoder(self, source: Union[XMLSourceType, XMLResource],
                    path: Optional[str] = None,
                    schema_path: Optional[str] = None,
                    validation: str = 'lax',
                    **kwargs: Any) -> Iterator[Union[Any, XMLSchemaValidationError]]:
        """Returns a generator for decoding a resource."""
        context = DecodeContext(source, validation, **kwargs)
        if path:
            selector = context.source.iterfind(path, context.namespaces)
        else:
            selector = context.source.iter_depth(mode=2)

        for elem in selector:
            xsd_element = self.get_element(elem.tag, schema_path, context.namespaces)
            if xsd_element is None:
                if nm.XSI_TYPE in elem.attrib:
                    xsd_element = self.create_element(name=elem.tag)
                else:
                    reason = _("{!r} is not an element of the schema").format(elem)
                    yield context.validation_error(validation, self, reason, elem)
                    continue

            result = xsd_element.raw_decode(elem, validation, context)
            if context.errors:
                yield from context.errors
                context.errors.clear()
            if result is not Empty:
                yield result

        if context.max_depth is None:
            yield from self._validate_references(validation, context)

    def iter_decode(self, source: Union[XMLSourceType, XMLResource],
                    path: Optional[str] = None,
                    schema_path: Optional[str] = None,
                    validation: str = 'lax',
                    process_namespaces: bool = True,
                    namespaces: Optional[NsmapType] = None,
                    use_defaults: bool = True,
                    use_location_hints: bool = False,
                    decimal_type: Optional[Type[Any]] = None,
                    datetime_types: bool = False,
                    binary_types: bool = False,
                    converter: Optional[ConverterType] = None,
                    filler: Optional[FillerType] = None,
                    fill_missing: bool = False,
                    keep_empty: bool = False,
                    keep_unknown: bool = False,
                    process_skipped: bool = False,
                    max_depth: Optional[int] = None,
                    depth_filler: Optional[DepthFillerType] = None,
                    extra_validator: Optional[ExtraValidatorType] = None,
                    validation_hook: Optional[ValidationHookType] = None,
                    value_hook: Optional[ValueHookType] = None,
                    element_hook: Optional[ElementHookType] = None,
                    errors: Optional[list[XMLSchemaValidationError]] = None,
                    **kwargs: Any) -> Iterator[Union[Any, XMLSchemaValidationError]]:
        """
        Creates an iterator for decoding an XML source to a data structure.

        :param source: the source of XML data. Can be an :class:`XMLResource` instance, a \
        path to a file or a URI of a resource or an opened file-like object or an Element \
        instance or an ElementTree instance or a string containing the XML data.
        :param path: is an optional XPath expression that matches the elements of the XML \
        data that have to be decoded. If not provided the XML root element is selected.
        :param schema_path: an alternative XPath expression to select the XSD element \
        to use for decoding. Useful if the root of the XML data doesn't match an XSD \
        global element of the schema.
        :param validation: defines the XSD validation mode to use for decode, can be \
        'strict', 'lax' or 'skip'.
        :param process_namespaces: whether to use namespace information in the \
        decoding process, using the map provided with the argument *namespaces* \
        and the namespace declarations extracted from the XML document.
        :param namespaces: is an optional mapping from namespace prefix to URI that \
        integrate/override the root namespace declarations of the XML source. \
        In case of prefix collision an alternate prefix is used for the root \
        XML namespace declaration.
        :param use_defaults: whether to use default values for filling missing data.
        :param use_location_hints: for default schema locations hints provided within \
        XML data are ignored in order to avoid the change of schema instance. Set this \
        option to `True` to activate dynamic schema loading using schema location hints.
        :param decimal_type: conversion type for `Decimal` objects (generated by \
        `xs:decimal` built-in and derived types), useful if you want to generate a \
        JSON-compatible data structure.
        :param datetime_types: if set to `True` the datetime and duration XSD types \
        are kept decoded, otherwise their origin XML string is returned.
        :param binary_types: if set to `True` xs:hexBinary and xs:base64Binary types \
        are kept decoded, otherwise their origin XML string is returned.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use \
        for decoding.
        :param filler: an optional callback function to fill undecodable data with a \
        typed value. The callback function must accept one positional argument, that \
        can be an XSD Element or an attribute declaration. If not provided undecodable \
        data is replaced by `None`.
        :param fill_missing: if set to `True` the decoder fills also missing attributes. \
        The filling value is `None` or a typed value if the *filler* callback is provided.
        :param keep_empty: if set to `True` empty elements that are valid are decoded with \
        an empty string value instead of a `None`.
        :param keep_unknown: if set to `True` unknown tags are kept and are decoded with \
        *xs:anyType*. For default unknown tags not decoded by a wildcard are discarded.
        :param process_skipped: process XML data that match a wildcard with \
        `processContents='skip'`.
        :param max_depth: maximum level of decoding, for default there is no limit. \
        With lazy resources is set to `source.lazy_depth` for managing lazy decoding.
        :param depth_filler: an optional callback function to replace data over the \
        *max_depth* level. The callback function must accept one positional argument, that \
        can be an XSD Element. If not provided deeper data are replaced with `None` values.
        :param extra_validator: an optional function for performing non-standard \
        validations on XML data. The provided function is called for each traversed \
        element, with the XML element as 1st argument and the corresponding XSD \
        element as 2nd argument. It can be also a generator function and has to \
        raise/yield :exc:`XMLSchemaValidationError` exceptions.
        :param validation_hook: an optional function for stopping or changing \
        validated decoding at element level. The provided function must accept two \
        arguments, the XML element and the matching XSD element. If the value returned \
        by this function is evaluated to false then the decoding process continues \
        without changes, otherwise the decoding process is stopped or changed. If the \
        value returned is a validation mode the decoding process continues changing the \
        current validation mode to the returned value, otherwise the element and its \
        content are not decoded.
        :param value_hook: an optional function that will be called with any decoded \
        atomic value and the XSD type used for decoding. The return value will be used \
        instead of the original value.
        :param element_hook: an optional function that is called with decoded element \
        data before calling the converter decode method. Takes an `ElementData` \
        instance plus optionally the XSD element and the XSD type, and returns a \
        new `ElementData` instance.
        :param errors: optional internal collector for validation errors.
        :param kwargs: keyword arguments with other options for building XMLResource \
        and converter instances.
        :return: yields a decoded data object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        self.check_validator(validation)
        if isinstance(source, XMLResource):
            resource: XMLResource = source
        else:
            resource = XMLResource(source, defuse=self.defuse, timeout=self.timeout)

        if converter is None:
            converter = self.converter

        kwargs.update(
            process_namespaces=process_namespaces,
            namespaces=namespaces,
            check_identities=True,
            use_defaults=use_defaults,
            use_location_hints=use_location_hints,
            decimal_type=decimal_type,
            datetime_types=datetime_types,
            binary_types=binary_types,
            converter=converter,
            filler=filler,
            fill_missing=fill_missing,
            keep_empty=keep_empty,
            keep_unknown=keep_unknown,
            process_skipped=process_skipped,
            max_depth=max_depth,
            depth_filler=depth_filler,
            extra_validator=extra_validator,
            validation_hook=validation_hook,
            value_hook=value_hook,
            element_hook=element_hook,
            errors=errors
        )
        context = DecodeContext(resource, validation, **kwargs)
        namespaces = context.namespaces

        namespace = resource.namespace or namespaces.get('', '')
        schema = self.get_schema(namespace)

        if path:
            selector = resource.iterfind(path, namespaces)
            if not schema_path:
                schema_path = resource.get_absolute_path(path)

        elif not resource.is_lazy():
            selector = iter((resource.root,))
        else:
            decoder = self.raw_decoder(
                source=resource,
                schema_path=resource.get_absolute_path(),
                validation=validation,
                **kwargs
            )
            context.depth_filler = lambda x: decoder
            context.max_depth = resource.lazy_depth
            selector = resource.iter_depth(mode=3)

        yielded_errors = 0

        for elem in selector:
            xsd_element = schema.get_element(elem.tag, schema_path, namespaces)
            if xsd_element is None:
                if nm.XSI_TYPE in elem.attrib:
                    xsd_element = self.create_element(name=elem.tag)
                else:
                    reason = _("{!r} is not an element of the schema").format(elem)
                    yield context.validation_error(validation, self, reason, elem)
                    return

            result = xsd_element.raw_decode(elem, validation, context)

            if errors is not context.errors:
                yield from context.errors
                context.errors.clear()
            elif len(context.errors) > yielded_errors:
                yield from context.errors[yielded_errors:]
                yielded_errors = len(context.errors)

            if result is not Empty:
                yield result

        if context.max_depth is not None:
            yield from self._validate_references(validation, context)

    def decode(self, source: Union[XMLSourceType, XMLResource],
               path: Optional[str] = None,
               schema_path: Optional[str] = None,
               validation: str = 'strict',
               *args: Any, **kwargs: Any) -> DecodeType[Any]:
        """
        Decodes XML data. Takes the same arguments of the method :meth:`iter_decode`.
        """
        data, errors = [], []
        for result in self.iter_decode(source, path, schema_path, validation, *args, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                data.append(result)
            elif validation == 'lax':
                errors.append(result)
            elif validation == 'strict':
                raise result

        if not data:
            return (None, errors) if validation == 'lax' else None
        elif len(data) == 1:
            return (data[0], errors) if validation == 'lax' else data[0]
        else:
            return (data, errors) if validation == 'lax' else data

    to_dict = decode

    def to_objects(self, source: Union[XMLSourceType, XMLResource], with_bindings: bool = False,
                   **kwargs: Any) -> DecodeType['dataobjects.DataElement']:
        """
        Decodes XML data to Python data objects.

        :param source: the XML data. Can be a string for an attribute or for a simple \
        type components or a dictionary for an attribute group or an ElementTree's \
        Element for other components.
        :param with_bindings: if `True` is provided the decoding is done using \
        :class:`DataBindingConverter` that used XML data binding classes. For \
        default the objects are instances of :class:`DataElement` and uses the \
        :class:`DataElementConverter`.
        :param kwargs: other optional keyword arguments for the method \
        :func:`iter_decode`, except the argument *converter*.
        """
        if with_bindings:
            return self.decode(source, converter=dataobjects.DataBindingConverter, **kwargs)
        return self.decode(source, converter=dataobjects.DataElementConverter, **kwargs)

    def iter_encode(self, obj: Any,
                    path: Optional[str] = None,
                    validation: str = 'lax',
                    namespaces: Optional[NsmapType] = None,
                    use_defaults: bool = True,
                    converter: Optional[ConverterType] = None,
                    unordered: bool = False,
                    process_skipped: bool = False,
                    max_depth: Optional[int] = None,
                    **kwargs: Any) -> Iterator[Union[Element, XMLSchemaValidationError]]:
        """
        Creates an iterator for encoding a data structure to an ElementTree's Element.

        :param obj: the data that has to be encoded to XML data.
        :param path: is an optional XPath expression for selecting the element of \
        the schema that matches the data that has to be encoded. For default the first \
        global element of the schema is used.
        :param validation: the XSD validation mode. Can be 'strict', 'lax' or 'skip'.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param use_defaults: whether to use default values for filling missing data.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for \
        the encoding.
        :param unordered: a flag for explicitly activating unordered encoding mode for \
        content model data. This mode uses content models for a reordered-by-model \
        iteration of the child elements.
        :param process_skipped: process XML decoded data that match a wildcard with \
        `processContents='skip'`.
        :param max_depth: maximum level of encoding, for default there is no limit.
        :param kwargs: keyword arguments with other options for building the \
        converter instance.
        :return: yields an Element instance/s or validation/encoding errors.
        """
        self.check_validator(validation)
        if not self.elements:
            msg = _("encoding needs at least one XSD element declaration")
            raise XMLSchemaValueError(msg)

        if converter is None:
            converter = self.converter

        kwargs.update(
            namespaces=namespaces,
            check_identities=True,
            use_defaults=use_defaults,
            converter=converter,
            unordered=unordered,
            process_skipped=process_skipped,
            max_depth=max_depth
        )
        context = EncodeContext(obj, validation, **kwargs)

        xsd_element = None
        if path is not None:
            match = re.search(r'[{\w]', path)
            if match:
                namespace = get_namespace(path[match.start():], context.namespaces)
                schema = self.get_schema(namespace)
                xsd_element = schema.find(path, context.namespaces)

        elif len(self.elements) == 1:
            xsd_element = list(self.elements.values())[0]
        else:
            root_elements = self.root_elements
            if len(root_elements) == 1:
                xsd_element = root_elements[0]
            elif isinstance(obj, (context.converter.dict, dict)) and len(obj) == 1:
                for key in obj:
                    match = re.search(r'[{\w]', key)
                    if match:
                        namespace = get_namespace(key[match.start():], context.namespaces)
                        schema = self.get_schema(namespace)
                        xsd_element = schema.find(key, context.namespaces)

        if not isinstance(xsd_element, XsdElement):
            if path is not None:
                reason = _("the path %r doesn't match any element of the schema!") % path
            else:
                reason = _("unable to select an element for encoding data, "
                           "provide a valid 'path' argument.")
            raise XMLSchemaEncodeError(self, obj, self.elements, reason, namespaces=namespaces)
        else:
            result = xsd_element.raw_encode(obj, validation, context)
            yield from context.errors
            context.errors.clear()
            if result is not None:
                yield result

    def encode(self, obj: Any, path: Optional[str] = None, validation: str = 'strict',
               *args: Any, **kwargs: Any) -> EncodeType[Any]:
        """
        Encodes to XML data. Takes the same arguments of the method :meth:`iter_encode`.

        :return: An ElementTree's Element or a list containing a sequence of ElementTree's \
        elements if the argument *path* matches multiple XML data chunks. If *validation* \
        argument is 'lax' a 2-items tuple is returned, where the first item is the encoded \
        object and the second item is a list containing the errors.
        """
        data, errors = [], []
        result: Union[Element, XMLSchemaValidationError]
        for result in self.iter_encode(obj, path, validation, *args, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                data.append(result)
            elif validation == 'lax':
                errors.append(result)
            elif validation == 'strict':
                raise result

        if not data:
            return (None, errors) if validation == 'lax' else None
        elif len(data) == 1:
            if errors and is_etree_element(data[0]):
                # Replace decoded data source with an XML resource
                resource = XMLResource(data[0])
                for e in errors:
                    e.source = resource

            return (data[0], errors) if validation == 'lax' else data[0]
        else:
            print(data)
            return (data, errors) if validation == 'lax' else data

    to_etree = encode


class XMLSchema10(XMLSchemaBase):
    """
    XSD 1.0 schema class.

    <schema
      attributeFormDefault = (qualified | unqualified) : unqualified
      blockDefault = (#all | List of (extension | restriction | substitution))  : ''
      elementFormDefault = (qualified | unqualified) : unqualified
      finalDefault = (#all | List of (extension | restriction | list | union))  : ''
      id = ID
      targetNamespace = anyURI
      version = token
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ((include | import | redefine | annotation)*, (((simpleType | complexType | group |
      attributeGroup) | element | attribute | notation), annotation*)*)
    </schema>
    """
    meta_schema: XMLSchemaBase
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.0/XMLSchema.xsd')  # type: ignore
    BASE_SCHEMAS = {
        nm.XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XML/xml_minimal.xsd'),
        nm.XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XSI/XMLSchema-instance_minimal.xsd'),
    }


class XMLSchema11(XMLSchemaBase):
    """
    XSD 1.1 schema class.

    <schema
      attributeFormDefault = (qualified | unqualified) : unqualified
      blockDefault = (#all | List of (extension | restriction | substitution)) : ''
      defaultAttributes = QName
      xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace| ##local)) : ##local
      elementFormDefault = (qualified | unqualified) : unqualified
      finalDefault = (#all | List of (extension | restriction | list | union))  : ''
      id = ID
      targetNamespace = anyURI
      version = token
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ((include | import | redefine | override | annotation)*,
      (defaultOpenContent, annotation*)?, ((simpleType | complexType |
      group | attributeGroup | element | attribute | notation), annotation*)*)
    </schema>

    <schema
      attributeFormDefault = (qualified | unqualified) : unqualified
      blockDefault = (#all | List of (extension | restriction | substitution))  : ''
      elementFormDefault = (qualified | unqualified) : unqualified
      finalDefault = (#all | List of (extension | restriction | list | union))  : ''
      id = ID
      targetNamespace = anyURI
      version = token
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ((include | import | redefine | annotation)*, (((simpleType | complexType | group |
      attributeGroup) | element | attribute | notation), annotation*)*)
    </schema>
    """
    meta_schema: XMLSchemaBase
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')  # type: ignore
    XSD_VERSION = '1.1'

    BASE_SCHEMAS = {
        nm.XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XML/xml_minimal.xsd'),
        nm.XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XSI/XMLSchema-instance_minimal.xsd'),
        nm.XSD_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XSD_1.1/xsd11-extra.xsd'),
        nm.VC_NAMESPACE: os.path.join(SCHEMAS_DIR, 'VC/XMLSchema-versioning.xsd'),
    }

    xsd_complex_type_class = Xsd11ComplexType
    xsd_attribute_class = Xsd11Attribute
    xsd_any_attribute_class = Xsd11AnyAttribute
    xsd_group_class = Xsd11Group
    xsd_element_class = Xsd11Element
    xsd_any_class = Xsd11AnyElement
    xsd_atomic_restriction_class = Xsd11AtomicRestriction
    xsd_union_class = Xsd11Union
    xsd_key_class = Xsd11Key
    xsd_keyref_class = Xsd11Keyref
    xsd_unique_class = Xsd11Unique


XMLSchema = XMLSchema10
"""The default class for schema instances."""
