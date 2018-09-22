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
from abc import ABCMeta
import warnings
import elementpath

from ..compat import add_metaclass
from ..exceptions import XMLSchemaTypeError, XMLSchemaURLError, XMLSchemaValueError, XMLSchemaOSError
from ..namespaces import XSD_NAMESPACE, XML_NAMESPACE, HFP_NAMESPACE, XSI_NAMESPACE, XLINK_NAMESPACE
from ..namespaces import NamespaceResourcesMap, NamespaceView, XHTML_NAMESPACE
from ..etree import etree_element, etree_tostring
from ..qnames import (
    XSD_SCHEMA_TAG, XSD_NOTATION_TAG, XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG,
    XSD_SIMPLE_TYPE_TAG, XSD_COMPLEX_TYPE_TAG, XSD_GROUP_TAG, XSD_ELEMENT_TAG,
    XSD_SEQUENCE_TAG, XSD_ANY_TAG, XSD_ANY_ATTRIBUTE_TAG
)
from ..resources import is_remote_url, url_path_is_file, fetch_resource, XMLResource
from ..converters import XMLSchemaConverter
from ..xpath import ElementPathMixin

from . import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaNotBuiltError,
    XMLSchemaIncludeWarning, XMLSchemaImportWarning, XsdValidator, ValidationMixin, XsdComponent,
    XsdNotation, XSD_10_FACETS, XSD_11_FACETS, UNION_FACETS, LIST_FACETS, XsdComplexType,
    XsdAttribute, XsdElement, XsdAttributeGroup, XsdGroup, XsdAtomicRestriction, XsdAnyElement,
    XsdAnyAttribute, xsd_simple_type_factory, Xsd11Attribute, Xsd11Element, Xsd11AnyElement,
    Xsd11AnyAttribute, Xsd11AtomicRestriction, Xsd11ComplexType, Xsd11Group, XsdGlobals
)
from .parseutils import has_xsd_components, get_xsd_derivation_attribute, get_xpath_default_namespace
from .globals_ import iterchildren_xsd_import, iterchildren_xsd_include, iterchildren_xsd_redefine


# Elements for building dummy groups
ATTRIBUTE_GROUP_ELEMENT = etree_element(XSD_ATTRIBUTE_GROUP_TAG)
ANY_ATTRIBUTE_ELEMENT = etree_element(
    XSD_ANY_ATTRIBUTE_TAG, attrib={'namespace': '##any', 'processContents': 'lax'}
)
SEQUENCE_ELEMENT = etree_element(XSD_SEQUENCE_TAG)
ANY_ELEMENT = etree_element(
    XSD_ANY_TAG,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')


class XMLSchemaMeta(ABCMeta):

    def __new__(mcs, name, bases, dict_):

        def get_attribute(attr, *args):
            for obj in args:
                if hasattr(obj, attr):
                    return getattr(obj, attr)

        meta_schema = dict_.get('meta_schema') or get_attribute('meta_schema', *bases)
        if meta_schema is None:
            return super(XMLSchemaMeta, mcs).__new__(mcs, name, bases, dict_)

        xsd_version = dict_.get('XSD_VERSION') or get_attribute('XSD_VERSION', *bases)
        if xsd_version not in ('1.0', '1.1'):
            raise XMLSchemaValueError("Validator class XSD version must be '1.0' or '1.1', not %r." % xsd_version)

        facets = dict_.get('FACETS') or get_attribute('FACETS', *bases)
        if not isinstance(facets, set):
            raise XMLSchemaValueError("Validator class FACETS must be a set(), not %r." % type(facets))
        dict_['LIST_FACETS'] = facets.intersection(LIST_FACETS)
        dict_['UNION_FACETS'] = facets.intersection(UNION_FACETS)

        builders = dict_.get('BUILDERS') or get_attribute('BUILDERS', *bases)
        if isinstance(builders, dict):
            dict_['BUILDERS'] = namedtuple('Builders', builders)(**builders)
            dict_['TAG_MAP'] = {
                XSD_NOTATION_TAG: builders['notation_class'],
                XSD_SIMPLE_TYPE_TAG: builders['simple_type_factory'],
                XSD_COMPLEX_TYPE_TAG: builders['complex_type_class'],
                XSD_ATTRIBUTE_TAG: builders['attribute_class'],
                XSD_ATTRIBUTE_GROUP_TAG: builders['attribute_group_class'],
                XSD_GROUP_TAG: builders['group_class'],
                XSD_ELEMENT_TAG: builders['element_class'],
            }
        elif builders is None:
            raise XMLSchemaValueError("Validator class doesn't have defined builders.")
        elif get_attribute('TAG_MAP', *bases) is None:
            raise XMLSchemaValueError("Validator class doesn't have a defined tag map.")

        dict_['meta_schema'] = None
        if isinstance(meta_schema, XMLSchemaBase):
            meta_schema = meta_schema.url

        # Build the meta-schema class
        meta_schema_class_name = 'Meta' + name
        meta_schema_class = super(XMLSchemaMeta, mcs).__new__(mcs, meta_schema_class_name, bases, dict_)
        meta_schema_class.__qualname__ = meta_schema_class_name
        meta_schema = meta_schema_class(meta_schema, defuse='never', build=False)
        globals()[meta_schema_class_name] = meta_schema_class

        base_schemas = dict_.get('BASE_SCHEMAS') or get_attribute('BASE_SCHEMAS', *bases)
        for uri, pathname in list(base_schemas.items()):
            meta_schema.import_schema(namespace=uri, location=pathname)
        meta_schema.maps.build()
        dict_['meta_schema'] = meta_schema

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
    :param locations: schema location hints for namespace imports. Can be a dictionary or \
    a sequence of couples (namespace URI, resource URL).
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

    :cvar XSD_VERSION: store the XSD version (1.0 or 1.1).
    :vartype XSD_VERSION: str
    :cvar meta_schema: the XSD meta-schema instance.
    :vartype meta_schema: XMLSchema
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
    :ivar locations: schema location hints.
    :vartype locations: NamespaceResourcesMap
    :ivar namespaces: a dictionary that maps from the prefixes used by the schema into namespace URI.
    :vartype namespaces: dict
    :ivar warnings: warning messages about failure of import and include elements.
    :vartype namespaces: list

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

    FACETS = None
    LIST_FACETS = None
    UNION_FACETS = None
    BUILDERS = None
    TAG_MAP = None

    meta_schema = None
    BASE_SCHEMAS = {
        XML_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xml_minimal.xsd'),
        HFP_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-hasFacetAndProperty_minimal.xsd'),
        XSI_NAMESPACE: os.path.join(SCHEMAS_DIR, 'XMLSchema-instance_minimal.xsd'),
        XLINK_NAMESPACE: os.path.join(SCHEMAS_DIR, 'xlink.xsd')
    }
    _parent_map = None

    def __init__(self, source, namespace=None, validation='strict', global_maps=None, converter=None,
                 locations=None, base_url=None, defuse='remote', timeout=300, build=True):
        super(XMLSchemaBase, self).__init__(validation)
        try:
            self.source = XMLResource(source, base_url, defuse, timeout, lazy=False)
        except (XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot create schema: %s' % err)

        self.warnings = []
        self._root_elements = None
        root = self.source.root

        # Set and check target namespace
        self.target_namespace = root.get('targetNamespace', '')
        if self.target_namespace == XSD_NAMESPACE and self.meta_schema is not None:
            raise XMLSchemaValueError("The %r cannot be used as target namespace!" % XSD_NAMESPACE)
        if namespace is not None and self.target_namespace != namespace:
            if self.target_namespace:
                msg = u"wrong namespace (%r instead of %r) for XSD resource %r."
                self.parse_error(msg % (self.target_namespace, namespace, self.url), root)
            else:
                self.target_namespace = namespace  # Chameleon schema

        self.locations = NamespaceResourcesMap(self.source.get_locations(locations))
        if self.meta_schema is not None:
            # Add fallback schema location hint for XHTML
            self.locations[XHTML_NAMESPACE] = os.path.join(SCHEMAS_DIR, 'xhtml1-strict.xsd')

        self.namespaces = {'xml': XML_NAMESPACE}  # the XML namespace is implicit
        self.namespaces.update(self.source.get_namespaces())
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
                self.maps = self.meta_schema.maps.copy(validation)

        elif isinstance(global_maps, XsdGlobals):
            self.maps = global_maps
        else:
            raise XMLSchemaTypeError("'global_maps' argument must be a %r instance." % XsdGlobals)

        # Validate the schema document
        if self.meta_schema is None:
            # Base schemas use single file and don't have to be checked
            return
        elif validation == 'strict':
            self.check_schema(root, self.namespaces)
        elif validation == 'lax':
            self.errors.extend([e for e in self.meta_schema.iter_errors(root, namespaces=self.namespaces)])

        # XSD 1.1 xpathDefaultNamespace attribute
        if self.XSD_VERSION > '1.0':
            try:
                self.xpath_default_namespace = get_xpath_default_namespace(
                    root, self.namespaces[''], self.target_namespace, default=''
                )
            except XMLSchemaValueError as error:
                self.parse_error(str(error), root)
                self.xpath_default_namespace = self.namespaces['']

        self.warnings.extend(self._include_schemas())
        self.warnings.extend(self._import_namespaces())

        if build:
            self.maps.build()

    def __repr__(self):
        if self.url:
            return u'%s(namespace=%r, url=%r)' % (self.__class__.__name__, self.target_namespace, self.url)
        else:
            return u'%s(namespace=%r)' % (self.__class__.__name__, self.target_namespace)

    def __setattr__(self, name, value):
        if name == 'root' and value.tag not in (XSD_SCHEMA_TAG, 'schema'):
            raise XMLSchemaValueError("schema root element must has %r tag." % XSD_SCHEMA_TAG)
        elif name == 'validation':
            if value not in ('strict', 'lax', 'skip'):
                raise XMLSchemaValueError("Wrong value %r for attribute 'validation'." % value)
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

    def __iter__(self):
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name):
            yield xsd_element

    def __reversed__(self):
        for xsd_element in sorted(self.elements.values(), key=lambda x: x.name, reverse=True):
            yield xsd_element

    def __len__(self):
        return len(self.elements)

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

    @property
    def parent_map(self):
        warnings.warn(
            "This property will be removed in future versions. "
            "Use the 'parent' attribute of the element instead.",
            DeprecationWarning, stacklevel=2
        )
        if self._parent_map is None:
            self._parent_map = {e: p for p in self.iter() for e in p.iterchildren()}
        return self._parent_map

    @classmethod
    def builtin_types(cls):
        """An accessor for XSD built-in types."""
        try:
            return cls.meta_schema.maps.namespaces[XSD_NAMESPACE][0].types
        except KeyError:
            raise XMLSchemaNotBuiltError(cls.meta_schema, "missing XSD namespace in meta-schema.")

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
                    if e is xsd_element:
                        continue
                    elif e.ref or e.is_global:
                        if e.name in names:
                            names.discard(e.name)
                            if not names:
                                break
            self._root_elements = list(names)

        return [e for e in self.elements.values() if e.name in self._root_elements]

    @classmethod
    def create_schema(cls, *args, **kwargs):
        """Creates a new schema instance of the same class of the caller."""
        return cls(*args, **kwargs)

    def create_any_content_group(self, parent, name=None):
        """Creates a model group related to schema instance that accepts any content."""
        group = self.BUILDERS.group_class(SEQUENCE_ELEMENT, self, parent, name)
        group.append(XsdAnyElement(ANY_ELEMENT, self, group))
        return group

    def create_any_attribute_group(self, parent, name=None):
        """Creates an attribute group related to schema instance that accepts any attribute."""
        attribute_group = self.BUILDERS.attribute_group_class(ATTRIBUTE_GROUP_ELEMENT, self, parent, name)
        attribute_group[None] = XsdAnyAttribute(ANY_ATTRIBUTE_ELEMENT, self, attribute_group)
        return attribute_group

    @classmethod
    def check_schema(cls, schema, namespaces=None):
        """
        Validates the given schema against the XSD meta-schema (:attr:`meta_schema`).

        :param schema: the schema instance that has to be validated.
        :param namespaces: is an optional mapping from namespace prefix to URI.

        :raises: :exc:`XMLSchemaValidationError` if the schema is invalid.
        """
        for error in cls.meta_schema.iter_errors(schema, namespaces=namespaces):
            raise error

    def build(self):
        """Builds the schema XSD global maps."""
        self.maps.build()

    @property
    def built(self):
        xsd_global = None
        for xsd_global in self.iter_globals():
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
        Get a list of location hints for a namespace.
        """
        try:
            return list(self.locations[namespace])
        except KeyError:
            return []

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

    def _include_schemas(self):
        """Processes schema document inclusions and redefinitions."""
        include_warnings = []

        for child in iterchildren_xsd_include(self.root):
            try:
                self.include_schema(child.attrib['schemaLocation'], self.base_url)
            except KeyError:
                pass
            except (OSError, IOError) as err:
                # Attribute missing error already found by validation against meta-schema.
                # It is not an error if the location fail to resolve:
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#compound-schema
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#src-include
                include_warnings.append("Include schema failed: %s." % str(err))
                warnings.warn(include_warnings[-1], XMLSchemaIncludeWarning, stacklevel=3)

        for child in iterchildren_xsd_redefine(self.root):
            try:
                self.include_schema(child.attrib['schemaLocation'], self.base_url)
            except KeyError:
                pass  # Attribute missing error already found by validation against meta-schema
            except (OSError, IOError) as err:
                # If the redefine doesn't contain components (annotation excluded) the statement
                # is equivalent to an include, so no error is generated. Otherwise fails.
                include_warnings.append("Redefine schema failed: %s." % str(err))
                warnings.warn(include_warnings[-1], XMLSchemaIncludeWarning, stacklevel=3)
                if has_xsd_components(child):
                    self.parse_error(str(err), child)

        return include_warnings

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
            raise XMLSchemaOSError("cannot include schema from %r: %s." % (location, err))
        else:
            for schema in self.maps.namespaces[self.target_namespace]:
                if schema_url == schema.url:
                    return schema
        try:
            return self.create_schema(
                schema_url, self.target_namespace, self.validation, self.maps, self.converter,
                self.locations, self.base_url, self.defuse, self.timeout, False
            )
        except XMLSchemaParseError as err:
            err.message = 'cannot include %r: %s' % (schema_url, err.message)
            raise err
        except (XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot include %r: %s' % (schema_url, err))

    def _import_namespaces(self):
        """Processes namespace imports. Return a list of exceptions."""
        import_warnings = []
        namespace_imports = NamespaceResourcesMap(map(
            lambda x: (x.get('namespace', '').strip(), x.get('schemaLocation')),
            iterchildren_xsd_import(self.root)
        ))

        for namespace, locations in namespace_imports.items():
            if namespace in self.maps.namespaces:
                # Imports are done on namespace basis not on resource: this is the standard
                # and also avoids import loops that sometimes are hard to detect.
                continue

            locations = [url for url in locations if url]
            if not locations:
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

            import_error = None
            for url in locations:
                try:
                    self.import_schema(namespace, url, self.base_url)
                except (OSError, IOError) as err:
                    # It's not an error if the location access fails (ref. section 4.2.6.2):
                    #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#composition-schemaImport
                    if import_error is None:
                        import_error = err
                else:
                    break
            else:
                if import_error is None:
                    import_warnings.append("Namespace import failed: no schema location provided.")
                else:
                    import_warnings.append("Namespace import failed: %s." % str(import_error))
                warnings.warn(import_warnings[-1], XMLSchemaImportWarning, stacklevel=3)

        return import_warnings

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
            if namespace:
                raise XMLSchemaOSError("cannot import namespace %r from %r: %s." % (namespace, location, err))
            else:
                raise XMLSchemaOSError("cannot import chameleon schema from %r: %s." % (location, err))
        else:
            if namespace in self.maps.namespaces:
                for schema in self.maps.namespaces[namespace]:
                    if schema_url == schema.url:
                        return schema

        try:
            namespace = namespace or self.target_namespace
            return self.create_schema(
                schema_url, namespace, self.validation, self.maps, self.converter,
                self.locations, self.base_url, self.defuse, self.timeout, False
            )
        except XMLSchemaParseError as err:
            err.message = 'cannot import namespace %r: %s' % (namespace, err.message)
            raise err
        except (XMLSchemaTypeError, OSError, IOError) as err:
            raise type(err)('cannot import namespace %r: %s' % (namespace, err))

    def iter_decode(self, source, path=None, validation='lax', process_namespaces=True,
                    namespaces=None, use_defaults=True, decimal_type=None, converter=None,
                    defuse=None, timeout=None, **kwargs):
        """
        Creates an iterator for decoding an XML source to a data structure.

        :param source: the XML data source. Can be a path to a file or an URI of a resource or \
        an opened file-like object or an Element Tree instance or a string containing XML data.
        :param path: is an optional XPath expression that matches the parts of the document \
        that have to be decoded. The XPath expression considers the schema as the root \
        element with global elements as its children.
        :param validation: defines the XSD validation mode to use for decode, can be 'strict', \
        'lax' or 'skip'.
        :param process_namespaces: indicates whether to use namespace information in the decoding \
        process, using the map provided with the argument *namespaces* and the map extracted from \
        the XML document.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param decimal_type: conversion type for `Decimal` objects (generated by XSD `decimal` \
        built-in and derived types), useful if you want to generate a JSON-compatible data structure.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the decoding.
        :param defuse: Overrides when to defuse XML data. Can be 'always', 'remote' or 'never'.
        :param timeout: Overrides the timeout setted for the schema.
        :param kwargs: Keyword arguments containing options for converter and decoding.
        :return: Yields a decoded data object, eventually preceded by a sequence of validation \
        or decoding errors.
        """
        if not self.built:
            raise XMLSchemaNotBuiltError(self, "schema %r is not built." % self)
        elif not self.elements:
            raise XMLSchemaValueError("decoding needs at least one XSD element declaration!")

        if not isinstance(source, XMLResource):
            defuse = defuse or self.defuse
            timeout = timeout or self.timeout
            source = XMLResource(source=source, defuse=defuse, timeout=timeout, lazy=False)
        elif defuse and source.defuse != defuse or timeout and source.timeout != timeout:
            source = source.copy(defuse=defuse, timeout=timeout, lazy=False)

        if process_namespaces:
            namespaces = {} if namespaces is None else namespaces.copy()
            namespaces.update(source.get_namespaces())
        else:
            namespaces = {}

        converter = self.get_converter(converter, namespaces, **kwargs)

        if path is None:
            xsd_element = self.find(source.root.tag, namespaces=namespaces)
            if not isinstance(xsd_element, XsdElement):
                reason = "%r is not a global element of the schema!" % source.root.tag
                yield XMLSchemaValidationError(self, source.root, reason, source, namespaces)
            else:
                for obj in xsd_element.iter_decode(
                        source.root, validation, converter, source=source, namespaces=namespaces,
                        use_defaults=use_defaults, decimal_type=decimal_type, **kwargs):
                    yield obj
        else:
            xsd_element = self.find(path, namespaces=namespaces)
            if not isinstance(xsd_element, XsdElement):
                reason = "the path %r doesn't match any element of the schema!" % path
                obj = elementpath.select(source.root, path, namespaces=namespaces) or source.root
                yield XMLSchemaValidationError(self, obj, reason, source, namespaces)
            else:
                for elem in elementpath.select(source.root, path, namespaces=namespaces):
                    for obj in xsd_element.iter_decode(
                            elem, validation, converter, source=source, namespaces=namespaces,
                            use_defaults=use_defaults, decimal_type=decimal_type, **kwargs):
                        yield obj

    def iter_encode(self, obj, path=None, validation='lax', namespaces=None, converter=None, **kwargs):
        """
        Creates an iterator for encoding a data structure to an ElementTree's Element.

        :param obj: the data that has to be encoded.
        :param path: is an optional XPath expression for selecting the element of the schema \
        that matches the data that has to be encoded. For default the first global element of \
        the schema is used.
        :param validation: the XSD validation mode. Can be 'strict', 'lax' or 'skip'.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance to use for the encoding.
        :param kwargs: Keyword arguments containing options for converter and encoding.
        :return: Yields an Element instance, eventually preceded by a sequence of validation \
        or encoding errors.
        """
        if not self.built:
            raise XMLSchemaNotBuiltError(self, "schema %r is not built." % self)
        elif not self.elements:
            yield XMLSchemaValueError("encoding needs at least one XSD element declaration!")

        namespaces = {} if namespaces is None else namespaces.copy()
        converter = self.get_converter(converter, namespaces, **kwargs)

        if path is not None:
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
                msg = "the path %r doesn't match any element of the schema!" % path
            else:
                msg = "unable to select an element for decoding data, provide a valid 'path' argument."
            yield XMLSchemaEncodeError(self, obj, self.elements, reason=msg)
        else:
            for result in xsd_element.iter_encode(obj, validation, converter, **kwargs):
                yield result


class XMLSchema10(XMLSchemaBase):
    """XSD 1.0 Schema class"""
    XSD_VERSION = '1.0'
    FACETS = XSD_10_FACETS
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
        'simple_type_factory': xsd_simple_type_factory
    }
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.0/XMLSchema.xsd')


# ++++ UNDER DEVELOPMENT, DO NOT USE!!! ++++
class XMLSchema11(XMLSchemaBase):
    """XSD 1.1 Schema class"""
    XSD_VERSION = '1.1'
    FACETS = XSD_11_FACETS
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
        'simple_type_factory': xsd_simple_type_factory
    }
    meta_schema = os.path.join(SCHEMAS_DIR, 'XSD_1.1/XMLSchema.xsd')


XMLSchema = XMLSchema10
"""The default class for schema instances."""
