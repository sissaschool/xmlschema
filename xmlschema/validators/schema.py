# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
import os
from collections import namedtuple, Counter
from abc import ABCMeta
import logging
import threading
import warnings
import re
import sys


from ..compat import add_metaclass
from ..exceptions import XMLSchemaTypeError, XMLSchemaURLError, XMLSchemaKeyError, \
    XMLSchemaValueError, XMLSchemaOSError, XMLSchemaNamespaceError
from ..qnames import VC_MIN_VERSION, VC_MAX_VERSION, VC_TYPE_AVAILABLE, \
    VC_TYPE_UNAVAILABLE, VC_FACET_AVAILABLE, VC_FACET_UNAVAILABLE, XSD_SCHEMA, \
    XSD_ANNOTATION, XSD_NOTATION, XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_GROUP, \
    XSD_SIMPLE_TYPE, XSD_COMPLEX_TYPE, XSD_ELEMENT, XSD_SEQUENCE, XSD_CHOICE, \
    XSD_ALL, XSD_ANY, XSD_ANY_ATTRIBUTE, XSD_INCLUDE, XSD_IMPORT, XSD_REDEFINE, \
    XSD_OVERRIDE, XSD_DEFAULT_OPEN_CONTENT, XSD_ANY_TYPE, XSI_TYPE
from ..helpers import get_xsd_derivation_attribute, get_xsd_form_attribute
from ..namespaces import XSD_NAMESPACE, XML_NAMESPACE, XSI_NAMESPACE, VC_NAMESPACE, \
    SCHEMAS_DIR, LOCATION_HINTS, NamespaceResourcesMap, NamespaceView, get_namespace
from ..etree import etree_element, etree_tostring, prune_etree, ParseError
from ..resources import is_remote_url, url_path_is_file, fetch_resource, XMLResource
from ..converters import XMLSchemaConverter
from ..xpath import XMLSchemaProxy, ElementPathMixin

from .exceptions import XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaEncodeError, \
    XMLSchemaNotBuiltError, XMLSchemaIncludeWarning, XMLSchemaImportWarning
from .xsdbase import XSD_VALIDATION_MODES, XsdValidator, ValidationMixin, XsdComponent
from .notations import XsdNotation
from .identities import XsdKey, XsdKeyref, XsdUnique, Xsd11Key, Xsd11Unique, Xsd11Keyref
from .facets import XSD_11_FACETS
from .simple_types import xsd_simple_type_factory, XsdUnion, XsdAtomicRestriction, \
    Xsd11AtomicRestriction, Xsd11Union
from .attributes import XsdAttribute, XsdAttributeGroup, Xsd11Attribute
from .complex_types import XsdComplexType, Xsd11ComplexType
from .groups import XsdGroup, Xsd11Group
from .elements import XsdElement, Xsd11Element
from .wildcards import XsdAnyElement, XsdAnyAttribute, Xsd11AnyElement, \
    Xsd11AnyAttribute, XsdDefaultOpenContent
from .globals_ import XsdGlobals

logger = logging.getLogger('xmlschema')
logging_formater = logging.Formatter('[%(levelname)s] %(message)s')
logging_handler = logging.StreamHandler(sys.stderr)
logging_handler.setFormatter(logging_formater)
logger.addHandler(logging_handler)

XSD_VERSION_PATTERN = re.compile(r'^\d+\.\d+$')

# Elements for building dummy groups
ATTRIBUTE_GROUP_ELEMENT = etree_element(XSD_ATTRIBUTE_GROUP)
ANY_ATTRIBUTE_ELEMENT = etree_element(
    XSD_ANY_ATTRIBUTE, attrib={'namespace': '##any', 'processContents': 'lax'}
)
SEQUENCE_ELEMENT = etree_element(XSD_SEQUENCE)
ANY_ELEMENT = etree_element(
    XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


class XMLSchemaMeta(ABCMeta):

    def __new__(mcs, name, bases, dict_):

        def get_attribute(attr, *args):
            for obj in args:
                if hasattr(obj, attr):
                    return getattr(obj, attr)

        meta_schema = dict_.get('meta_schema') or get_attribute('meta_schema', *bases)
        if meta_schema is None:
            # Defining a subclass without a meta-schema (eg. XMLSchemaBase)
            return super(XMLSchemaMeta, mcs).__new__(mcs, name, bases, dict_)
        dict_['meta_schema'] = None
        dict_['lock'] = threading.Lock()  # Lock instance for shared meta-schemas

        xsd_version = dict_.get('XSD_VERSION') or get_attribute('XSD_VERSION', *bases)
        if xsd_version not in ('1.0', '1.1'):
            raise XMLSchemaValueError("Validator class XSD version must be '1.0' or '1.1', not %r." % xsd_version)

        builders = dict_.get('BUILDERS') or get_attribute('BUILDERS', *bases)
        if isinstance(builders, dict):
            dict_['BUILDERS'] = namedtuple('Builders', builders)(**builders)
            dict_['BUILDERS_MAP'] = {
                XSD_NOTATION: builders['notation_class'],
                XSD_SIMPLE_TYPE: builders['simple_type_factory'],
                XSD_COMPLEX_TYPE: builders['complex_type_class'],
                XSD_ATTRIBUTE: builders['attribute_class'],
                XSD_ATTRIBUTE_GROUP: builders['attribute_group_class'],
                XSD_GROUP: builders['group_class'],
                XSD_ELEMENT: builders['element_class'],
            }
        elif builders is None:
            raise XMLSchemaValueError("Validator class doesn't have defined XSD builders.")
        elif get_attribute('BUILDERS_MAP', *bases) is None:
            raise XMLSchemaValueError("Validator class doesn't have a builder map for XSD globals.")

        # Build the new meta-schema class
        meta_schema_class_name = 'Meta' + name
        meta_schema_class = super(XMLSchemaMeta, mcs).__new__(mcs, meta_schema_class_name, bases, dict_)
        meta_schema_class.__qualname__ = meta_schema_class_name
        globals()[meta_schema_class_name] = meta_schema_class

        # Build the shared meta-schema instance
        schema_location = meta_schema.url if isinstance(meta_schema, XMLSchemaBase) else meta_schema
        meta_schema = meta_schema_class.create_meta_schema(schema_location)
        dict_['meta_schema'] = meta_schema
        dict_.pop('lock')

        return super(XMLSchemaMeta, mcs).__new__(mcs, name, bases, dict_)

    def __init__(cls, name, bases, dict_):
        super(XMLSchemaMeta, cls).__init__(name, bases, dict_)


@add_metaclass(XMLSchemaMeta)
class XMLSchemaBase(XsdValidator, ValidationMixin, ElementPathMixin):
    """
    Base class for an XML Schema instance.

    :param source: an URI that reference to a resource or a file path or a file-like \
    object or a string containing the schema or an Element or an ElementTree document.
    :type source: Element or ElementTree or str or file-like object
    :param namespace: is an optional argument that contains the URI of the namespace. \
    When specified it must be equal to the *targetNamespace* declared in the schema.
    :type namespace: str or None
    :param validation: defines the XSD validation mode to use for build the schema, \
    it's value can be 'strict', 'lax' or 'skip'.
    :type validation: str
    :param global_maps: is an optional argument containing an :class:`XsdGlobals` \
    instance, a mediator object for sharing declaration data between dependents \
    schema instances.
    :type global_maps: XsdGlobals or None
    :param converter: is an optional argument that can be an :class:`XMLSchemaConverter` \
    subclass or instance, used for defining the default XML data converter for XML Schema instance.
    :type converter: XMLSchemaConverter or None
    :param locations: schema location hints, that can include additional namespaces to \
    import after processing schema's import statements. Usually filled with the couples \
    (namespace, url) extracted from xsi:schemaLocations. Can be a dictionary or a sequence \
    of couples (namespace URI, resource URL).
    :type locations: dict or list or None
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the schema resource can't be obtained from the source argument.
    :type base_url: str or None
    :param defuse: defines when to defuse XML data. Can be 'always', 'remote' or 'never'. \
    For default defuse only remote XML data.
    :type defuse: str or None
    :param timeout: the timeout in seconds for fetching resources. Default is `300`.
    :type timeout: int
    :param build: defines whether build the schema maps. Default is `True`.
    :type build: bool
    :param use_meta: if `True` the schema processor uses the package meta-schema, \
    otherwise a new meta-schema is added at the end. In the latter case the meta-schema \
    is rebuilt if any base namespace has been overridden by an import. Ignored if the \
    argument *global_maps* is provided.
    :type use_meta: bool
    :param loglevel: for setting a different logging level for schema initialization \
    and building. For default is WARNING (30). For INFO level set it with 20, for \
    DEBUG level with 10. The default loglevel is restored after schema building, \
    when exiting the initialization method.
    :type loglevel: int

    :cvar XSD_VERSION: store the XSD version (1.0 or 1.1).
    :vartype XSD_VERSION: str
    :cvar BUILDERS: a namedtuple with attributes related to schema components classes. \
    Used for build local components within parsing methods.
    :vartype BUILDERS: namedtuple
    :cvar BUILDERS_MAP: a dictionary that maps from tag to class for XSD global components. \
    Used for build global components within lookup functions.
    :vartype BUILDERS_MAP: dict
    :cvar BASE_SCHEMAS: a dictionary from namespace to schema resource for meta-schema bases.
    :vartype BASE_SCHEMAS: dict
    :cvar FALLBACK_LOCATIONS: fallback schema location hints for other standard namespaces.
    :vartype FALLBACK_LOCATIONS: dict
    :cvar meta_schema: the XSD meta-schema instance.
    :vartype meta_schema: XMLSchema
    :cvar attribute_form_default: the schema's *attributeFormDefault* attribute, defaults to 'unqualified'.
    :vartype attribute_form_default: str
    :cvar element_form_default: the schema's *elementFormDefault* attribute, defaults to 'unqualified'
    :vartype element_form_default: str
    :cvar block_default: the schema's *blockDefault* attribute, defaults to ''.
    :vartype block_default: str
    :cvar final_default: the schema's *finalDefault* attribute, defaults to ''.
    :vartype final_default: str
    :cvar default_attributes: the XSD 1.1 schema's *defaultAttributes* attribute, defaults to ``None``.
    :vartype default_attributes: XsdAttributeGroup
    :cvar xpath_tokens: symbol table for schema bound XPath 2.0 parsers. Initially set to \
    ``None`` it's redefined at instance level with a dictionary at first use of the XPath \
    selector. The parser symbol table is extended with schema types constructors.
    :vartype xpath_tokens: dict

    :ivar target_namespace: is the *targetNamespace* of the schema, the namespace to which \
    belong the declarations/definitions of the schema. If it's empty no namespace is associated \
    with the schema. In this case the schema declarations can be reused from other namespaces as \
    *chameleon* definitions.
    :vartype target_namespace: str
    :ivar validation: validation mode, can be 'strict', 'lax' or 'skip'.
    :vartype validation: str
    :ivar maps: XSD global declarations/definitions maps. This is an instance of :class:`XsdGlobal`, \
    that store the global_maps argument or a new object when this argument is not provided.
    :vartype maps: XsdGlobals
    :ivar converter: the default converter used for XML data decoding/encoding.
    :vartype converter: XMLSchemaConverter
    :ivar locations: schemas location hints.
    :vartype locations: NamespaceResourcesMap
    :ivar namespaces: a dictionary that maps from the prefixes used by the schema into namespace URI.
    :vartype namespaces: dict
    :ivar imports: a dictionary of namespace imports of the schema, that maps namespace URI to imported schema \
    object, or `None` in case of unsuccessful import.
    :vartype imports: dict
    :ivar includes: a dictionary of included schemas, that maps a schema location to an included schema. \
    It also comprehend schemas included by "xs:redefine" or "xs:override" statements.
    :vartype warnings: dict
    :ivar warnings: warning messages about failure of import and include elements.
    :vartype warnings: list

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
    XSD_VERSION = None
    BUILDERS = None
    BUILDERS_MAP = None
    BASE_SCHEMAS = None
    FALLBACK_LOCATIONS = None
    meta_schema = None

    # Schema defaults
    target_namespace = ''
    attribute_form_default = 'unqualified'
    element_form_default = 'unqualified'
    block_default = ''
    final_default = ''
    redefine = None

    # Additional defaults for XSD 1.1
    default_attributes = None
    default_open_content = None
    override = None
    xpath_tokens = None

    def __init__(self, source, namespace=None, validation='strict', global_maps=None,
                 converter=None, locations=None, base_url=None, defuse='remote',
                 timeout=300, build=True, use_meta=True, loglevel=None):
        super(XMLSchemaBase, self).__init__(validation)
        ElementPathMixin.__init__(self)

        if loglevel is not None:
            logger.setLevel(loglevel)
        elif build and global_maps is None:
            logger.setLevel(logging.WARNING)

        self.source = XMLResource(source, base_url, defuse, timeout, lazy=False)
        logger.debug("Read schema from %r", self.source)

        self.imports = {}
        self.includes = {}
        self.warnings = []
        self._root_elements = None
        root = self.source.root

        # Parse namespaces and targetNamespace
        self.namespaces = self.source.get_namespaces(
            namespaces={'xml': XML_NAMESPACE}  # the XML namespace is implicitly declared
        )
        try:
            self.target_namespace = root.attrib['targetNamespace']
        except KeyError:
            pass
        else:
            if self.target_namespace == '':
                # Ref: https://www.w3.org/TR/2004/REC-xmlschema-1-20041028/structures.html#element-schema
                self.parse_error("The attribute 'targetNamespace' cannot be an empty string.", root)

        if namespace is not None and self.target_namespace != namespace:
            if self.target_namespace:
                msg = u"wrong namespace (%r instead of %r) for XSD resource %r."
                self.parse_error(msg % (self.target_namespace, namespace, self.url), root)

            # Chameleon schema case: set the target namespace and the default namespace
            self.target_namespace = namespace
            if '' not in self.namespaces:
                self.namespaces[''] = namespace

        logger.debug("Schema targetNamespace is %r", self.target_namespace)
        logger.debug("Declared namespaces: %r", self.namespaces)

        # Parses the schema defaults
        if 'attributeFormDefault' in root.attrib:
            try:
                self.attribute_form_default = get_xsd_form_attribute(root, 'attributeFormDefault')
            except ValueError as err:
                self.parse_error(err, root)

        if 'elementFormDefault' in root.attrib:
            try:
                self.element_form_default = get_xsd_form_attribute(root, 'elementFormDefault')
            except ValueError as err:
                self.parse_error(err, root)

        if 'blockDefault' in root.attrib:
            if self.meta_schema is None:
                pass  # Skip XSD 1.0 meta-schema that has blockDefault="#all"
            else:
                try:
                    self.block_default = get_xsd_derivation_attribute(
                        root, 'blockDefault', {'extension', 'restriction', 'substitution'}
                    )
                except ValueError as err:
                    self.parse_error(err, root)

        if 'finalDefault' in root.attrib:
            try:
                self.final_default = get_xsd_derivation_attribute(root, 'finalDefault')
            except ValueError as err:
                self.parse_error(err, root)

        self.locations = NamespaceResourcesMap(self.source.get_locations(locations))
        self.converter = self.get_converter(converter)

        if self.meta_schema is None:
            # Meta-schema creation phase (MetaXMLSchema class)
            self.maps = global_maps or XsdGlobals(self)
            for child in filter(lambda x: x.tag == XSD_OVERRIDE, self.root):
                self.include_schema(child.attrib['schemaLocation'], self.base_url)
            return  # Meta-schemas don't need to be checked and don't process imports

        with self.meta_schema.lock:
            if not self.meta_schema.maps.types:
                self.meta_schema.maps.build()

        # Create or set the XSD global maps instance
        if global_maps is None:
            if use_meta and self.target_namespace not in self.meta_schema.maps.namespaces:
                self.maps = self.meta_schema.maps.copy(self, validation=validation)
            else:
                self.maps = XsdGlobals(self, validation)

        elif isinstance(global_maps, XsdGlobals):
            self.maps = global_maps
        else:
            raise XMLSchemaTypeError("'global_maps' argument must be an %r instance." % XsdGlobals)

        if self.XSD_VERSION > '1.0' and any(ns == VC_NAMESPACE for ns in self.namespaces.values()):
            # For XSD 1.1+ apply versioning filter to schema tree. See the paragraph
            # 4.2.2 of XSD 1.1 (Part 1: Structures) definition for details.
            # Ref: https://www.w3.org/TR/xmlschema11-1/#cip
            if prune_etree(root, selector=lambda x: not self.version_check(x)):
                for k in list(root.attrib):
                    if k not in {'targetNamespace', VC_MIN_VERSION, VC_MAX_VERSION}:
                        del root.attrib[k]

        # Validate the schema document (transforming validation errors to parse errors)
        if validation != 'skip':
            for e in self.meta_schema.iter_errors(root, namespaces=self.namespaces):
                self.parse_error(e.reason, elem=e.elem)

        self._parse_inclusions()
        self._parse_imports()

        # Imports by argument (usually from xsi:schemaLocation attribute).
        for ns in self.locations:
            if ns not in self.maps.namespaces:
                self._import_namespace(ns, self.locations[ns])

        if '' not in self.namespaces:
            self.namespaces[''] = ''  # For default local names are mapped to no namespace

        # XSD 1.1 default declarations (defaultAttributes, defaultOpenContent, xpathDefaultNamespace)
        if self.XSD_VERSION > '1.0':
            self.xpath_default_namespace = self._parse_xpath_default_namespace(root)
            if 'defaultAttributes' in root.attrib:
                try:
                    self.default_attributes = self.resolve_qname(root.attrib['defaultAttributes'])
                except (ValueError, KeyError, RuntimeError) as err:
                    self.parse_error(str(err), root)

            for child in filter(lambda x: x.tag == XSD_DEFAULT_OPEN_CONTENT, root):
                self.default_open_content = XsdDefaultOpenContent(child, self)
                break

        try:
            if build:
                self.maps.build()
        finally:
            if loglevel is not None:
                logger.setLevel(logging.WARNING)  # Restore default logging

    def __repr__(self):
        if self.url:
            basename = os.path.basename(self.url)
            return u'%s(basename=%r, namespace=%r)' % (self.__class__.__name__, basename, self.target_namespace)
        else:
            return u'%s(namespace=%r)' % (self.__class__.__name__, self.target_namespace)

    def __setattr__(self, name, value):
        if name == 'root' and value.tag not in (XSD_SCHEMA, 'schema'):
            raise XMLSchemaValueError("schema root element must has %r tag." % XSD_SCHEMA)
        elif name == 'maps':
            if self.meta_schema is None and hasattr(self, 'maps'):
                raise XMLSchemaValueError("cannot change the global maps instance of a meta-schema")
            super(XMLSchemaBase, self).__setattr__(name, value)
            self.notations = NamespaceView(value.notations, self.target_namespace)
            self.types = NamespaceView(value.types, self.target_namespace)
            self.attributes = NamespaceView(value.attributes, self.target_namespace)
            self.attribute_groups = NamespaceView(value.attribute_groups, self.target_namespace)
            self.groups = NamespaceView(value.groups, self.target_namespace)
            self.elements = NamespaceView(value.elements, self.target_namespace)
            self.substitution_groups = NamespaceView(value.substitution_groups, self.target_namespace)
            self.identities = NamespaceView(value.identities, self.target_namespace)
            self.global_maps = (self.notations, self.types, self.attributes,
                                self.attribute_groups, self.groups, self.elements)
            value.register(self)
        elif name == 'validation' and value not in ('strict', 'lax', 'skip'):
            raise XMLSchemaValueError("Wrong value %r for attribute 'validation'." % value)
        else:
            super(XMLSchemaBase, self).__setattr__(name, value)

    def __iter__(self):
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name):
            yield xsd_element

    def __reversed__(self):
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name, reverse=True):
            yield xsd_element

    def __len__(self):
        return len(self.elements)

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self)

    @property
    def xsd_version(self):
        """Property that returns the class attribute XSD_VERSION."""
        return self.XSD_VERSION

    # XML resource attributes access
    @property
    def root(self):
        """Root element of the schema."""
        return self.source.root

    def get_text(self):
        """
        Gets the XSD text of the schema. If the source text is not available creates
        an encoded string representation of the XSD tree.
        """
        if self.source.text is None:
            if self.source.url is None:
                return etree_tostring(self.source.root, self.namespaces, xml_declaration=True)
            else:
                try:
                    self.source.load()
                except XMLSchemaOSError:
                    return etree_tostring(self.source.root, self.namespaces, xml_declaration=True)
        return self.source.text

    @property
    def url(self):
        """Schema resource URL, is `None` if the schema is built from a string."""
        return self.source.url

    @property
    def base_url(self):
        """The base URL of the source of the schema."""
        return self.source.base_url

    @property
    def defuse(self):
        """Defines when to defuse XML data, can be 'always', 'remote' or 'never'."""
        return self.source.defuse

    @property
    def timeout(self):
        """Timeout in seconds for fetching resources."""
        return self.source.timeout

    @property
    def use_meta(self):
        """Returns `True` if the meta-schema is imported."""
        return self.meta_schema is not None and XSD_NAMESPACE in self.maps.namespaces

    # Schema root attributes
    @property
    def tag(self):
        """Schema root tag. For compatibility with the ElementTree API."""
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
    def schema_location(self):
        """A list of location hints extracted from the *xsi:schemaLocation* attribute of the schema."""
        return [(k, v) for k, v in self.source.iter_location_hints() if k]

    @property
    def no_namespace_schema_location(self):
        """A location hint extracted from the *xsi:noNamespaceSchemaLocation* attribute of the schema."""
        for k, v in self.source.iter_location_hints():
            if not k:
                return v

    @property
    def default_namespace(self):
        """The namespace associated to the empty prefix ''."""
        return self.namespaces.get('')

    @property
    def target_prefix(self):
        """The prefix associated to the *targetNamespace*."""
        for prefix, namespace in self.namespaces.items():
            if namespace == self.target_namespace:
                return prefix
        return ''

    @classmethod
    def builtin_types(cls):
        """Accessor for XSD built-in types."""
        try:
            builtin_types = cls.meta_schema.maps.namespaces[XSD_NAMESPACE][0].types
        except KeyError:
            raise XMLSchemaNotBuiltError(cls.meta_schema, "missing XSD namespace in meta-schema")
        except AttributeError:
            raise XMLSchemaNotBuiltError(cls.meta_schema, "meta-schema unavailable for %r" % cls)
        else:
            if not builtin_types:
                cls.meta_schema.build()
            return builtin_types

    @property
    def root_elements(self):
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
            names = set(e.name for e in self.elements.values())
            for xsd_element in self.elements.values():
                for e in xsd_element.iter():
                    if e is xsd_element or isinstance(e, XsdAnyElement):
                        continue
                    elif e.ref or e.parent is None:
                        if e.name in names:
                            names.discard(e.name)
                            if not names:
                                break
            self._root_elements = list(names)

        return [e for e in self.elements.values() if e.name in self._root_elements]

    @property
    def constraints(self):
        """
        Old reference to identity constraints, for backward compatibility. Will be removed in v1.1.0.
        """
        warnings.warn("'constraints' property has been replaced by 'identities' "
                      "and will be removed in 1.1 version.", DeprecationWarning)
        return self.identities

    @classmethod
    def create_meta_schema(cls, source=None, base_schemas=None, global_maps=None):
        """
        Creates a new meta-schema instance.

        :param source: an optional argument referencing to or containing the XSD meta-schema \
        resource. Required if the schema class doesn't already have a meta-schema.
        :param base_schemas: an optional dictionary that contains namespace URIs and \
        schema locations. If provided it's used as substitute for class 's BASE_SCHEMAS. \
        Also a sequence of (namespace, location) items can be provided if there are more \
        schema documents for one or more namespaces.
        :param global_maps: is an optional argument containing an :class:`XsdGlobals` \
        instance for the new meta schema. If not provided a new map is created.
        """
        if source is None:
            try:
                source = cls.meta_schema.url
            except AttributeError:
                raise XMLSchemaValueError(
                    "The argument 'source' is required when the class doesn't already have a meta-schema"
                )

        if base_schemas is None:
            base_schemas = cls.BASE_SCHEMAS.items()
        elif isinstance(base_schemas, dict):
            base_schemas = base_schemas.items()
        else:
            try:
                base_schemas = [(n, l) for n, l in base_schemas]
            except ValueError:
                raise ValueError("The argument 'base_schemas' is not a dictionary nor a sequence of items")

        meta_schema_class = cls if cls.meta_schema is None else cls.meta_schema.__class__
        meta_schema = meta_schema_class(source, XSD_NAMESPACE, global_maps=global_maps, defuse='never', build=False)
        for ns, location in base_schemas:
            if ns == XSD_NAMESPACE:
                meta_schema.include_schema(location=location)
            else:
                meta_schema.import_schema(namespace=ns, location=location)
        return meta_schema

    @classmethod
    def create_schema(cls, *args, **kwargs):
        """Creates a new schema instance of the same class of the caller."""
        warnings.warn("'create_schema()' method will be removed in 1.1 version.", DeprecationWarning)
        return cls(*args, **kwargs)

    def create_any_content_group(self, parent, any_element=None):
        """
        Creates a model group related to schema instance that accepts any content.

        :param parent: the parent component to set for the any content group.
        :param any_element: an optional any element to use for the content group. \
        When provided it's copied, linked to the group and the minOccurs/maxOccurs \
        are set to 0 and 'unbounded'.
        """
        group = self.BUILDERS.group_class(SEQUENCE_ELEMENT, self, parent)

        if any_element is not None:
            any_element = any_element.copy()
            any_element.min_occurs = 0
            any_element.max_occurs = None
            any_element.parent = group
            group.append(any_element)
        else:
            group.append(self.BUILDERS.any_element_class(ANY_ELEMENT, self, group))

        return group

    def create_empty_content_group(self, parent, model='sequence'):
        if model == 'sequence':
            group_elem = etree_element(XSD_SEQUENCE)
        elif model == 'choice':
            group_elem = etree_element(XSD_CHOICE)
        elif model == 'all':
            group_elem = etree_element(XSD_ALL)
        else:
            raise XMLSchemaValueError("'model' argument must be (sequence | choice | all)")

        group_elem.text = '\n    '
        return self.BUILDERS.group_class(group_elem, self, parent)

    def create_any_attribute_group(self, parent):
        """
        Creates an attribute group related to schema instance that accepts any attribute.

        :param parent: the parent component to set for the any attribute group.
        """
        attribute_group = self.BUILDERS.attribute_group_class(
            ATTRIBUTE_GROUP_ELEMENT, self, parent
        )
        attribute_group[None] = self.BUILDERS.any_attribute_class(
            ANY_ATTRIBUTE_ELEMENT, self, attribute_group
        )
        return attribute_group

    def create_empty_attribute_group(self, parent):
        """
        Creates an empty attribute group related to schema instance.

        :param parent: the parent component to set for the any attribute group.
        """
        return self.BUILDERS.attribute_group_class(ATTRIBUTE_GROUP_ELEMENT, self, parent)

    def create_any_type(self):
        """
        Creates an xs:anyType instance related to schema instance.
        """
        any_type = self.BUILDERS.complex_type_class(
            elem=etree_element(XSD_COMPLEX_TYPE, name=XSD_ANY_TYPE),
            schema=self,
            parent=None,
            mixed=True
        )
        any_type.content_type = self.create_any_content_group(any_type)
        any_type.attributes = self.create_any_attribute_group(any_type)
        return any_type

    def create_element(self, name):
        """
        Creates an xs:element instance related to schema instance.
        """
        return self.BUILDERS.element_class(
            elem=etree_element(XSD_ELEMENT, name=name),
            schema=self,
            parent=None,
        )

    def copy(self):
        """
        Makes a copy of the schema instance. The new instance has independent maps
        of shared XSD components.
        """
        schema = object.__new__(self.__class__)
        schema.__dict__.update(self.__dict__)
        schema.source = self.source.copy()
        schema.errors = self.errors[:]
        schema.warnings = self.warnings[:]
        schema.namespaces = self.namespaces.copy()
        schema.locations = NamespaceResourcesMap(self.locations)
        schema.imports = dict(self.imports)
        schema.includes = dict(self.includes)
        schema.maps = self.maps.copy(validator=schema)
        return schema

    __copy__ = copy

    @classmethod
    def check_schema(cls, schema, namespaces=None):
        """
        Validates the given schema against the XSD meta-schema (:attr:`meta_schema`).

        :param schema: the schema instance that has to be validated.
        :param namespaces: is an optional mapping from namespace prefix to URI.

        :raises: :exc:`XMLSchemaValidationError` if the schema is invalid.
        """
        if not cls.meta_schema.maps.types:
            cls.meta_schema.maps.build()

        for error in cls.meta_schema.iter_errors(schema, namespaces=namespaces):
            raise error

    def build(self):
        """Builds the schema's XSD global maps."""
        self.maps.build()

    def clear(self):
        """Clears the schema's XSD global maps."""
        self.maps.clear()

    @property
    def built(self):
        if any(not isinstance(g, XsdComponent) or not g.built for g in self.iter_globals()):
            return False
        for _ in self.iter_globals():
            return True
        if self.meta_schema is None:
            return False

        # No XSD globals: check with a lookup of schema child elements.
        prefix = '{%s}' % self.target_namespace if self.target_namespace else ''
        for child in filter(lambda x: x.tag != XSD_ANNOTATION, self.root):
            if child.tag in {XSD_REDEFINE, XSD_OVERRIDE}:
                for e in filter(lambda x: x.tag in self.BUILDERS_MAP, child):
                    name = e.get('name')
                    if name is not None:
                        try:
                            if not self.maps.lookup(e.tag, prefix + name if prefix else name).built:
                                return False
                        except KeyError:
                            return False
            elif child.tag in self.BUILDERS_MAP:
                name = child.get('name')
                if name is not None:
                    try:
                        if not self.maps.lookup(child.tag, prefix + name if prefix else name).built:
                            return False
                    except KeyError:
                        return False
        return True

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any(comp.validation_attempted == 'partial' for comp in self.iter_globals()):
            return 'partial'
        else:
            return 'none'

    def iter_globals(self, schema=None):
        """
        Creates an iterator for XSD global definitions/declarations related to schema namespace.

        :param schema: Optional argument for filtering only globals related to a schema instance.
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
        for xsd_global in self.iter_globals(self):
            for obj in xsd_global.iter_components(xsd_classes):
                yield obj

    def get_converter(self, converter=None, namespaces=None, **kwargs):
        """
        Returns a new converter instance.

        :param converter: can be a converter class or instance. If it's an instance \
        the new instance is copied from it and configured with the provided arguments.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param kwargs: optional arguments for initialize the converter instance.
        :return: a converter instance.
        """
        if converter is None:
            converter = getattr(self, 'converter', XMLSchemaConverter)

        if isinstance(converter, XMLSchemaConverter):
            return converter.copy(namespaces=namespaces, **kwargs)
        elif issubclass(converter, XMLSchemaConverter):
            return converter(namespaces, **kwargs)
        else:
            msg = "'converter' argument must be a %r subclass or instance: %r"
            raise XMLSchemaTypeError(msg % (XMLSchemaConverter, converter))

    def get_locations(self, namespace):
        """
        Get a list of location hints for a namespace.
        """
        try:
            return list(self.locations[namespace])
        except KeyError:
            return []

    def get_element(self, tag, path=None, namespaces=None):
        if not path:
            return self.find(tag)
        elif path[-1] == '*':
            return self.find(path[:-1] + tag, namespaces)
        else:
            return self.find(path, namespaces)

    def _parse_inclusions(self):
        """Processes schema document inclusions and redefinitions."""
        for child in filter(lambda x: x.tag == XSD_INCLUDE, self.root):
            try:
                location = child.attrib['schemaLocation'].strip()
                logger.info("Include schema from %r", location)
                self.include_schema(location, self.base_url)
            except KeyError:
                pass
            except (OSError, IOError) as err:
                # Attribute missing error already found by validation against meta-schema.
                # It is not an error if the location fail to resolve:
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#compound-schema
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#src-include
                self.warnings.append("Include schema failed: %s." % str(err))
                warnings.warn(self.warnings[-1], XMLSchemaIncludeWarning, stacklevel=3)
            except (XMLSchemaURLError, XMLSchemaParseError, XMLSchemaTypeError, ParseError) as err:
                msg = 'cannot include schema %r: %s' % (child.attrib['schemaLocation'], err)
                if isinstance(err, (XMLSchemaParseError, ParseError)):
                    self.parse_error(msg)
                elif self.validation == 'strict':
                    raise type(err)(msg)
                else:
                    self.errors.append(type(err)(msg))

        for child in filter(lambda x: x.tag == XSD_REDEFINE, self.root):
            try:
                location = child.attrib['schemaLocation'].strip()
                logger.info("Redefine schema %r", location)
                schema = self.include_schema(location, self.base_url)
            except KeyError:
                pass  # Attribute missing error already found by validation against meta-schema
            except (OSError, IOError) as err:
                # If the redefine doesn't contain components (annotation excluded) the statement
                # is equivalent to an include, so no error is generated. Otherwise fails.
                self.warnings.append("Redefine schema failed: %s." % str(err))
                warnings.warn(self.warnings[-1], XMLSchemaIncludeWarning, stacklevel=3)
                if any(e.tag != XSD_ANNOTATION for e in child):
                    self.parse_error(str(err), child)
            except (XMLSchemaURLError, XMLSchemaParseError, XMLSchemaTypeError, ParseError) as err:
                msg = 'cannot redefine schema %r: %s' % (child.attrib['schemaLocation'], err)
                if isinstance(err, (XMLSchemaParseError, ParseError)):
                    self.parse_error(msg)
                elif self.validation == 'strict':
                    raise type(err)(msg)
                else:
                    self.errors.append(type(err)(msg))
            else:
                schema.redefine = self

    def include_schema(self, location, base_url=None):
        """
        Includes a schema for the same namespace, from a specific URL.

        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :return: the included :class:`XMLSchema` instance.
        """
        schema_url = fetch_resource(location, base_url)
        for schema in self.maps.namespaces[self.target_namespace]:
            if schema_url == schema.url:
                break
        else:
            schema = type(self)(
                source=schema_url,
                namespace=self.target_namespace,
                validation=self.validation,
                global_maps=self.maps,
                converter=self.converter,
                base_url=self.base_url,
                defuse=self.defuse,
                timeout=self.timeout,
                build=False,
            )

        if schema is self:
            return self
        elif location not in self.includes:
            self.includes[location] = schema
        elif self.includes[location] is not schema:
            self.includes[schema_url] = schema
        return schema

    def _parse_imports(self):
        """
        Parse namespace import elements. Imports are done on namespace basis, not on
        single resource. A warning is generated for a failure of a namespace import.
        """
        namespace_imports = NamespaceResourcesMap(map(
            lambda x: (x.get('namespace'), x.get('schemaLocation')),
            filter(lambda x: x.tag == XSD_IMPORT, self.root)
        ))

        for namespace, locations in namespace_imports.items():

            # Checks the namespace against the targetNamespace of the schema
            if namespace is None:
                namespace = ''
                if namespace == self.target_namespace:
                    self.parse_error("if the 'namespace' attribute is not present on the import statement "
                                     "then the importing schema must has a 'targetNamespace'")
                    continue
            elif namespace == self.target_namespace:
                self.parse_error("the attribute 'namespace' must be different from schema's 'targetNamespace'")
                continue

            # Skip import of already imported namespaces
            if self.imports.get(namespace) is not None:
                continue
            elif namespace in self.maps.namespaces:
                self.imports[namespace] = self.maps.namespaces[namespace][0]
                continue

            locations = [url for url in locations if url]
            if not namespace:
                pass
            elif not locations:
                locations = self.get_locations(namespace)
            elif all(is_remote_url(url) for url in locations):
                # If all import schema locations are remote URLs and there are local hints
                # that match a local file path, try the local hints before schema locations.
                # This is not the standard processing for XSD imports, but resolve the problem
                # of local processing of schemas tested to work from a http server, providing
                # explicit local hints.
                local_hints = [url for url in self.get_locations(namespace) if url and url_path_is_file(url)]
                if local_hints:
                    locations = local_hints + locations

            if namespace in self.FALLBACK_LOCATIONS:
                locations.append(self.FALLBACK_LOCATIONS[namespace])

            self._import_namespace(namespace, locations)

    def _import_namespace(self, namespace, locations):
        import_error = None
        for url in locations:
            try:
                logger.debug("Import namespace %r from %r", namespace, url)
                self.import_schema(namespace, url, self.base_url)
            except (OSError, IOError) as err:
                # It's not an error if the location access fails (ref. section 4.2.6.2):
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#composition-schemaImport
                logger.debug('%s', err)
                if import_error is None:
                    import_error = err
            except (XMLSchemaURLError, XMLSchemaParseError, XMLSchemaTypeError, ParseError) as err:
                if namespace:
                    msg = "cannot import namespace %r: %s." % (namespace, err)
                else:
                    msg = "cannot import chameleon schema: %s." % err
                if isinstance(err, (XMLSchemaParseError, ParseError)):
                    self.parse_error(msg)
                elif self.validation == 'strict':
                    raise type(err)(msg)
                else:
                    self.errors.append(type(err)(msg))
            except XMLSchemaValueError as err:
                self.parse_error(err)
            else:
                logger.info("Namespace %r imported from %r", namespace, url)
                break
        else:
            if import_error is not None:
                msg = "Import of namespace {!r} from {!r} failed: {}."
                self.warnings.append(msg.format(namespace, locations, str(import_error)))
                warnings.warn(self.warnings[-1], XMLSchemaImportWarning, stacklevel=4)
            self.imports[namespace] = None

    def import_schema(self, namespace, location, base_url=None, force=False, build=False):
        """
        Imports a schema for an external namespace, from a specific URL.

        :param namespace: is the URI of the external namespace.
        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource.
        :param force: if set to `True` imports the schema also if the namespace is already imported.
        :param build: defines when to build the imported schema, the default is to not build.
        :return: the imported :class:`XMLSchema` instance.
        """
        if not force:
            if self.imports.get(namespace) is not None:
                return self.imports[namespace]
            elif namespace in self.maps.namespaces:
                self.imports[namespace] = self.maps.namespaces[namespace][0]
                return self.imports[namespace]

        schema_url = fetch_resource(location, base_url)
        if self.imports.get(namespace) is not None and self.imports[namespace].url == schema_url:
            return self.imports[namespace]
        elif namespace in self.maps.namespaces:
            for schema in self.maps.namespaces[namespace]:
                if schema_url == schema.url:
                    self.imports[namespace] = schema
                    return schema

        schema = type(self)(
            source=schema_url,
            validation=self.validation,
            global_maps=self.maps,
            converter=self.converter,
            base_url=self.base_url,
            defuse=self.defuse,
            timeout=self.timeout,
            build=build,
        )
        if schema.target_namespace != namespace:
            raise XMLSchemaValueError('imported schema %r has an unmatched namespace %r' % (location, namespace))
        self.imports[namespace] = schema
        return schema

    def version_check(self, elem):
        """
        Checks if the element is compatible with the version of the validator and XSD
        types/facets availability.

        :param elem: an Element of the schema.
        :return: `True` if the schema element is compatible with the validator, \
        `False` otherwise.
        """
        if VC_MIN_VERSION in elem.attrib:
            vc_min_version = elem.attrib[VC_MIN_VERSION]
            if not XSD_VERSION_PATTERN.match(vc_min_version):
                self.parse_error("invalid attribute vc:minVersion value", elem)
            elif vc_min_version > '1.1':
                return False

        if VC_MAX_VERSION in elem.attrib:
            vc_max_version = elem.attrib[VC_MAX_VERSION]
            if not XSD_VERSION_PATTERN.match(vc_max_version):
                self.parse_error("invalid attribute vc:maxVersion value", elem)
            elif vc_max_version <= '1.1':
                return False

        if VC_TYPE_AVAILABLE in elem.attrib:
            for qname in elem.attrib[VC_TYPE_AVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in self.maps.types:
                        return False
                except XMLSchemaNamespaceError:
                    return False
                except (KeyError, ValueError) as err:
                    self.parse_error(str(err), elem)

        if VC_TYPE_UNAVAILABLE in elem.attrib:
            for qname in elem.attrib[VC_TYPE_UNAVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in self.maps.types:
                        break
                except XMLSchemaNamespaceError:
                    break
                except (KeyError, ValueError) as err:
                    self.parse_error(err, elem)
            else:
                return False

        if VC_FACET_AVAILABLE in elem.attrib:
            for qname in elem.attrib[VC_FACET_AVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in XSD_11_FACETS:
                        return False
                except XMLSchemaNamespaceError:
                    pass
                except (KeyError, ValueError) as err:
                    self.parse_error(str(err), elem)

        if VC_FACET_UNAVAILABLE in elem.attrib:
            for qname in elem.attrib[VC_FACET_UNAVAILABLE].split():
                try:
                    if self.resolve_qname(qname) not in XSD_11_FACETS:
                        break
                except XMLSchemaNamespaceError:
                    break
                except (KeyError, ValueError) as err:
                    self.parse_error(err, elem)
            else:
                return False

        return True

    def resolve_qname(self, qname, namespace_imported=True):
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
            raise XMLSchemaValueError("{!r} is not a valid value for xs:QName".format(qname))

        if qname[0] == '{':
            try:
                namespace, local_name = qname[1:].split('}')
            except ValueError:
                raise XMLSchemaValueError("{!r} is not a valid value for xs:QName".format(qname))
        elif ':' in qname:
            try:
                prefix, local_name = qname.split(':')
            except ValueError:
                raise XMLSchemaValueError("{!r} is not a valid value for xs:QName".format(qname))
            else:
                try:
                    namespace = self.namespaces[prefix]
                except KeyError:
                    raise XMLSchemaKeyError("prefix %r not found in namespace map" % prefix)
        else:
            namespace, local_name = self.namespaces.get('', ''), qname

        if not namespace:
            return local_name
        elif namespace_imported and self.meta_schema is not None and \
                namespace != self.target_namespace and \
                namespace not in {XSD_NAMESPACE, XSI_NAMESPACE} and \
                namespace not in self.imports:
            raise XMLSchemaNamespaceError(
                "the QName {!r} is mapped to the namespace {!r}, but this namespace has "
                "not an xs:import statement in the schema.".format(qname, namespace)
            )
        return '{%s}%s' % (namespace, local_name)

    def validate(self, source, path=None, schema_path=None, use_defaults=True, namespaces=None):
        """
        Validates an XML data against the XSD schema/component instance.

        :raises: :exc:`XMLSchemaValidationError` if XML *data* instance is not a valid.
        """
        for error in self.iter_errors(source, path, schema_path, use_defaults, namespaces):
            raise error

    def is_valid(self, source, path=None, schema_path=None, use_defaults=True, namespaces=None):
        """
        Like :meth:`validate` except that do not raises an exception but returns ``True`` if
        the XML data is valid, ``False`` if it's invalid.
        """
        error = next(self.iter_errors(source, path, schema_path, use_defaults, namespaces), None)
        return error is None

    def iter_errors(self, source, path=None, schema_path=None, use_defaults=True, namespaces=None):
        """
        Creates an iterator for the errors generated by the validation of an XML data
        against the XSD schema/component instance.

        :param source: the source of XML data. Can be an :class:`XMLResource` instance, a \
        path to a file or an URI of a resource or an opened file-like object or an Element \
        instance or an ElementTree instance or a string containing the XML data.
        :param path: is an optional XPath expression that matches the elements of the XML \
        data that have to be decoded. If not provided the XML root element is selected.
        :param schema_path: an alternative XPath expression to select the XSD element to use for \
        decoding. Useful if the root of the XML data doesn't match an XSD global element of the schema.
        :param use_defaults: Use schema's default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        """
        if not self.built:
            if self.meta_schema is not None:
                raise XMLSchemaNotBuiltError(self, "schema %r is not built" % self)
            self.build()

        if not isinstance(source, XMLResource):
            source = XMLResource(source, defuse=self.defuse, timeout=self.timeout, lazy=False)
        if not schema_path and path:
            schema_path = path if path.startswith('/') else '/%s/%s' % (source.root.tag, path)

        id_map = Counter()
        root_only = source.is_lazy() and not namespaces
        namespaces = source.get_namespaces(namespaces, root_only)
        namespace = source.namespace or namespaces.get('', '')

        try:
            schema = self.maps.namespaces[namespace][0]
        except (KeyError, IndexError):
            reason = 'the namespace {!r} is not loaded'.format(namespace)
            yield self.validation_error('lax', reason, source.root, source, namespaces)
            return

        kwargs = {
            'source': source,
            'namespaces': namespaces,
            'converter': None,
            'use_defaults': use_defaults,
            'id_map': id_map,
            'inherited': {},
        }

        if source.is_lazy() and path is None:
            kwargs['locations'] = {}  # Lazy schema load

            xsd_element = schema.get_element(source.root.tag, schema_path, namespaces)
            if xsd_element is None:
                if XSI_TYPE in source.root.attrib:
                    xsd_element = self.create_element(name=source.root.tag)
                else:
                    reason = "{!r} is not an element of the schema".format(source.root)
                    yield schema.validation_error('lax', reason, source.root, source, namespaces)
                    return

            for result in xsd_element.iter_decode(source.root, max_depth=1, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    del result

            path = '*'
            if not schema_path:
                schema_path = '/%s/*' % source.root.tag
            kwargs['inherited'].clear()

            if root_only:
                # Tell to iterfind to catch namespace events and update map
                namespaces.clear()

        for elem in source.iterfind(path, namespaces):
            xsd_element = schema.get_element(elem.tag, schema_path, namespaces)
            if xsd_element is None:
                if XSI_TYPE in elem.attrib:
                    xsd_element = self.create_element(name=elem.tag)
                else:
                    reason = "{!r} is not an element of the schema".format(elem)
                    yield schema.validation_error('lax', reason, elem, source, namespaces)
                    return

            for result in xsd_element.iter_decode(elem, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    del result

        # Check unresolved IDREF values
        for k, v in id_map.items():
            if isinstance(v, XMLSchemaValidationError):
                yield v
            elif v == 0:
                yield self.validation_error('lax', "IDREF %r not found in XML document" % k, source.root)

    def iter_decode(self, source, path=None, schema_path=None, validation='lax', process_namespaces=True,
                    namespaces=None, use_defaults=True, decimal_type=None, datetime_types=False,
                    converter=None, filler=None, fill_missing=False, max_depth=None, **kwargs):
        """
        Creates an iterator for decoding an XML source to a data structure.

        :param source: the source of XML data. Can be an :class:`XMLResource` instance, a \
        path to a file or an URI of a resource or an opened file-like object or an Element \
        instance or an ElementTree instance or a string containing the XML data.
        :param path: is an optional XPath expression that matches the elements of the XML \
        data that have to be decoded. If not provided the XML root element is selected.
        :param schema_path: an alternative XPath expression to select the XSD element to use for \
        decoding. Useful if the root of the XML data doesn't match an XSD global element of the schema.
        :param validation: defines the XSD validation mode to use for decode, can be 'strict', \
        'lax' or 'skip'.
        :param process_namespaces: indicates whether to use namespace information in the decoding \
        process, using the map provided with the argument *namespaces* and the map extracted from \
        the XML document.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param decimal_type: conversion type for `Decimal` objects (generated by XSD `decimal` \
        built-in and derived types), useful if you want to generate a JSON-compatible data structure.
        :param datetime_types: if set to `True` the datetime and duration XSD types are decoded, \
        otherwise their origin XML string is returned.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the decoding.
        :param filler: an optional callback function to fill undecodable data with a typed value. \
        The callback function must accepts one positional argument, that can be an XSD Element or \
        an attribute declaration. If not provided undecodable data is replaced by `None`.
        :param fill_missing: if set to `True` the decoder fills also missing attributes. \
        The filling value is `None` or a typed value if the *filler* callback is provided.
        :param max_depth: maximum level of decoding, for default there is no limit.
        :param kwargs: keyword arguments with other options for converter and decoder.
        :return: yields a decoded data object, eventually preceded by a sequence of validation \
        or decoding errors.
        """
        if not self.built:
            if self.meta_schema is not None:
                raise XMLSchemaNotBuiltError(self, "schema %r is not built" % self)
            self.build()

        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)
        elif not isinstance(source, XMLResource):
            source = XMLResource(source, defuse=self.defuse, timeout=self.timeout, lazy=False)

        if not schema_path and path:
            schema_path = path if path.startswith('/') else '/%s/%s' % (source.root.tag, path)

        if process_namespaces:
            root_only = source.is_lazy() and not namespaces
            namespaces = source.get_namespaces(namespaces, root_only)
            namespace = source.namespace or namespaces.get('', '')
        else:
            root_only = namespaces = None
            namespace = source.namespace

        try:
            schema = self.maps.namespaces[namespace][0]
        except (KeyError, IndexError):
            reason = 'the namespace {!r} is not loaded'.format(namespace)
            yield self.validation_error('lax', reason, source.root, source, namespaces)
            return

        id_map = Counter()
        converter = self.get_converter(converter, namespaces, **kwargs)
        kwargs.update(
            converter=converter,
            namespaces=converter.namespaces,
            source=source,
            use_defaults=use_defaults,
            datetime_types=datetime_types,
            fill_missing=fill_missing,
            id_map=id_map,
            inherited={},
        )
        if decimal_type is not None:
            kwargs['decimal_type'] = decimal_type
        if filler is not None:
            kwargs['filler'] = filler
        if max_depth is not None:
            kwargs['max_depth'] = max_depth

        if root_only:
            converter.namespaces.clear()

        for elem in source.iterfind(path, converter.namespaces):
            xsd_element = schema.get_element(elem.tag, schema_path, namespaces)
            if xsd_element is None:
                if XSI_TYPE in elem.attrib:
                    xsd_element = self.create_element(name=elem.tag)
                else:
                    reason = "{!r} is not an element of the schema".format(elem)
                    yield schema.validation_error('lax', reason, elem, source, namespaces)
                    return

            for obj in xsd_element.iter_decode(elem, validation, **kwargs):
                yield obj

        for k, v in id_map.items():
            if isinstance(v, XMLSchemaValidationError):
                yield v
            elif v == 0:
                yield self.validation_error('lax', "IDREF %r not found in XML document" % k, source.root)

    def decode(self, source, path=None, schema_path=None, validation='strict', *args, **kwargs):
        """
        Decodes XML data. Takes the same arguments of the method :func:`XMLSchema.iter_decode`.

        """
        data, errors = [], []
        for result in self.iter_decode(source, path, schema_path, validation, *args, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                data.append(result)
            elif validation == 'lax':
                errors.append(result)
            else:
                raise result

        if not data:
            return (None, errors) if validation == 'lax' else None
        elif len(data) == 1:
            return (data[0], errors) if validation == 'lax' else data[0]
        else:
            return (data, errors) if validation == 'lax' else data

    to_dict = decode

    def iter_encode(self, obj, path=None, validation='lax', namespaces=None, converter=None,
                    unordered=False, **kwargs):
        """
        Creates an iterator for encoding a data structure to an ElementTree's Element.

        :param obj: the data that has to be encoded to XML data.
        :param path: is an optional XPath expression for selecting the element of the schema \
        that matches the data that has to be encoded. For default the first global element of \
        the schema is used.
        :param validation: the XSD validation mode. Can be 'strict', 'lax' or 'skip'.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the encoding.
        :param unordered: a flag for explicitly activating unordered encoding mode for content model \
        data. This mode uses content models for a reordered-by-model iteration of the child elements.
        :param kwargs: Keyword arguments containing options for converter and encoding.
        :return: yields an Element instance/s or validation/encoding errors.
        """
        if not self.built:
            if self.meta_schema is not None:
                raise XMLSchemaNotBuiltError(self, "schema %r is not built" % self)
            self.build()

        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)
        elif not self.elements:
            yield XMLSchemaValueError("encoding needs at least one XSD element declaration!")

        namespaces = {} if namespaces is None else namespaces.copy()
        converter = self.get_converter(converter, namespaces, **kwargs)

        namespace = get_namespace(path) or namespaces.get('', '')
        if namespace:
            try:
                schema = self.maps.namespaces[namespace][0]
            except (KeyError, IndexError):
                reason = 'the namespace {!r} is not loaded'.format(namespace)
                raise XMLSchemaEncodeError(self, obj, self, reason, namespaces=namespaces)
            else:
                xsd_element = schema.find(path, namespaces=namespaces)
        elif path is not None:
            xsd_element = self.find(path, namespaces=namespaces)
        elif isinstance(obj, dict) and len(obj) == 1:
            xsd_element = self.elements.get(list(obj.keys())[0])
        elif len(self.elements) == 1:
            xsd_element = list(self.elements.values())[0]
        else:
            root_elements = self.root_elements
            xsd_element = root_elements[0] if len(root_elements) == 1 else None

        if not isinstance(xsd_element, XsdElement):
            if path is not None:
                reason = "the path %r doesn't match any element of the schema!" % path
            else:
                reason = "unable to select an element for decoding data, provide a valid 'path' argument."
            raise XMLSchemaEncodeError(self, obj, self.elements, reason, namespaces=namespaces)
        else:
            for result in xsd_element.iter_encode(obj, validation, converter=converter,
                                                  unordered=unordered, **kwargs):
                yield result

    def encode(self, obj, path=None, validation='strict', *args, **kwargs):
        """
        Encodes to XML data. Takes the same arguments of the method :func:`XMLSchema.iter_encode`.

        :return: An ElementTree's Element or a list containing a sequence of ElementTree's \
        elements if the argument *path* matches multiple XML data chunks. If *validation* \
        argument is 'lax' a 2-items tuple is returned, where the first item is the encoded \
        object and the second item is a list containing the errors.
        """
        data, errors = [], []
        for result in self.iter_encode(obj, path, validation, *args, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                data.append(result)
            elif validation == 'lax':
                errors.append(result)
            else:
                raise result

        if not data:
            return (None, errors) if validation == 'lax' else None
        elif len(data) == 1:
            return (data[0], errors) if validation == 'lax' else data[0]
        else:
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
    XSD_VERSION = '1.0'
    BUILDERS = {
        'notation_class': XsdNotation,
        'complex_type_class': XsdComplexType,
        'attribute_class': XsdAttribute,
        'any_attribute_class': XsdAnyAttribute,
        'attribute_group_class': XsdAttributeGroup,
        'group_class': XsdGroup,
        'element_class': XsdElement,
        'any_element_class': XsdAnyElement,
        'restriction_class': XsdAtomicRestriction,
        'union_class': XsdUnion,
        'key_class': XsdKey,
        'keyref_class': XsdKeyref,
        'unique_class': XsdUnique,
        'simple_type_factory': xsd_simple_type_factory
    }
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.0/XMLSchema.xsd')
    BASE_SCHEMAS = {
        XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xml_minimal.xsd'),
        XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-instance_minimal.xsd'),
    }
    FALLBACK_LOCATIONS = LOCATION_HINTS


# ++++ UNDER DEVELOPMENT, DO NOT USE!!! ++++
class XMLSchema11(XMLSchemaBase):
    """
    XSD 1.1 schema class.

    <schema
      attributeFormDefault = (qualified | unqualified) : unqualified
      blockDefault = (#all | List of (extension | restriction | substitution))  : ''
      defaultAttributes = QName
      xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))  : ##local
      elementFormDefault = (qualified | unqualified) : unqualified
      finalDefault = (#all | List of (extension | restriction | list | union))  : ''
      id = ID
      targetNamespace = anyURI
      version = token
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ((include | import | redefine | override | annotation)*, (defaultOpenContent, annotation*)?,
      ((simpleType | complexType | group | attributeGroup | element | attribute | notation), annotation*)*)
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
    XSD_VERSION = '1.1'
    BUILDERS = {
        'notation_class': XsdNotation,
        'complex_type_class': Xsd11ComplexType,
        'attribute_class': Xsd11Attribute,
        'any_attribute_class': Xsd11AnyAttribute,
        'attribute_group_class': XsdAttributeGroup,
        'group_class': Xsd11Group,
        'element_class': Xsd11Element,
        'any_element_class': Xsd11AnyElement,
        'restriction_class': Xsd11AtomicRestriction,
        'union_class': Xsd11Union,
        'key_class': Xsd11Key,
        'keyref_class': Xsd11Keyref,
        'unique_class': Xsd11Unique,
        'simple_type_factory': xsd_simple_type_factory,
    }
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')
    BASE_SCHEMAS = {
        XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xml_minimal.xsd'),
        XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-instance_minimal.xsd'),
        XSD_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XSD_1.1/xsd11-extra.xsd'),
        VC_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-versioning_minimal.xsd'),
    }
    FALLBACK_LOCATIONS = LOCATION_HINTS

    def _parse_inclusions(self):
        super(XMLSchema11, self)._parse_inclusions()

        for child in filter(lambda x: x.tag == XSD_OVERRIDE, self.root):
            try:
                location = child.attrib['schemaLocation'].strip()
                logger.info("Override schema %r", location)
                schema = self.include_schema(location, self.base_url)
            except KeyError:
                pass  # Attribute missing error already found by validation against meta-schema
            except (OSError, IOError) as err:
                # If the override doesn't contain components (annotation excluded) the statement
                # is equivalent to an include, so no error is generated. Otherwise fails.
                self.warnings.append("Override schema failed: %s." % str(err))
                warnings.warn(self.warnings[-1], XMLSchemaIncludeWarning, stacklevel=3)
                if any(e.tag != XSD_ANNOTATION for e in child):
                    self.parse_error(str(err), child)
            else:
                schema.override = self


XMLSchema = XMLSchema10
"""The default class for schema instances."""
