#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains mapping classes for managing namespaces.
"""
import os
import logging
import warnings
from collections import Counter
from collections.abc import Iterable, Iterator, MutableMapping, Sequence
from operator import attrgetter
from typing import Any, Optional, TypeVar, TYPE_CHECKING, Union
from xml.etree.ElementTree import ParseError

from xmlschema.aliases import ElementType, SchemaType, SchemaSourceType, LocationsType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError, \
    XMLResourceBlocked, XMLResourceForbidden
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import local_name
from xmlschema.utils.urls import is_url, normalize_url, normalize_locations
import xmlschema.names as nm

from xmlschema.validators import XMLSchemaParseError, \
    XMLSchemaIncludeWarning, XMLSchemaImportWarning

if TYPE_CHECKING:
    from xmlschema.validators.global_maps import GlobalMaps, XsdGlobals

logger = logging.getLogger('xmlschema')
base_url_attribute = attrgetter('name')

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')

##
# Resources maps
T = TypeVar('T', bound=object)


class NamespaceResourcesMap(MutableMapping[str, list[T]]):
    """
    Dictionary for storing information about namespace resources. Values are
    lists of objects. Setting an existing value appends the object to the value.
    Setting a value with a list sets/replaces the value.
    """
    __slots__ = ('_store',)

    def __init__(self, *args: Union[MutableMapping[str, T], Sequence[tuple[str, T]]],
                 **kwargs: T):
        self._store: dict[str, list[T]] = {}
        for item in args:
            self.update(item)
        self.update(kwargs)

    def __getitem__(self, uri: str) -> list[T]:
        return self._store[uri]

    def __setitem__(self, uri: str, value: Any) -> None:
        if isinstance(value, list):
            self._store[uri] = value[:]
        else:
            try:
                self._store[uri].append(value)
            except KeyError:
                self._store[uri] = [value]

    def __delitem__(self, uri: str) -> None:
        del self._store[uri]

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return repr(self._store)

    def clear(self) -> None:
        self._store.clear()

    def copy(self) -> 'NamespaceResourcesMap[T]':
        obj: NamespaceResourcesMap[T] = object.__new__(self.__class__)
        obj._store = {k: v.copy() for k, v in self.items()}
        return obj

    __copy__ = copy


def get_locations(locations: Optional[LocationsType], base_url: Optional[str] = None) \
        -> NamespaceResourcesMap[str]:
    """Returns a NamespaceResourcesMap with location hints provided at schema initialization."""
    if locations is None:
        return NamespaceResourcesMap()
    elif isinstance(locations, NamespaceResourcesMap):
        return locations
    elif isinstance(locations, tuple):
        return NamespaceResourcesMap(locations)
    elif not isinstance(locations, Iterable):
        msg = _('wrong type {!r} for locations argument')
        raise XMLSchemaTypeError(msg.format(type(locations)))
    else:
        return NamespaceResourcesMap(normalize_locations(locations, base_url))


class SchemaLoader:

    fallback_locations = {
        # Loaded for default with meta-schema
        nm.XML_NAMESPACE: f'{SCHEMAS_DIR}XML/xml_minimal.xsd',
        nm.XSI_NAMESPACE: f'{SCHEMAS_DIR}XSI/XMLSchema-instance_minimal.xsd',

        # Locally saved schemas
        nm.HFP_NAMESPACE: f'{SCHEMAS_DIR}HFP/XMLSchema-hasFacetAndProperty_minimal.xsd',
        nm.VC_NAMESPACE: f'{SCHEMAS_DIR}XSI/XMLSchema-versioning.xsd',
        nm.XLINK_NAMESPACE: f'{SCHEMAS_DIR}XLINK/xlink.xsd',
        nm.XHTML_NAMESPACE: f'{SCHEMAS_DIR}XHTML/xhtml1-strict.xsd',
        nm.WSDL_NAMESPACE: f'{SCHEMAS_DIR}WSDL/wsdl.xsd',
        nm.SOAP_NAMESPACE: f'{SCHEMAS_DIR}WSDL/wsdl-soap.xsd',
        nm.SOAP_ENVELOPE_NAMESPACE: f'{SCHEMAS_DIR}WSDL/soap-envelope.xsd',
        nm.SOAP_ENCODING_NAMESPACE: f'{SCHEMAS_DIR}WSDL/soap-encoding.xsd',
        nm.DSIG_NAMESPACE: f'{SCHEMAS_DIR}DSIG/xmldsig-core-schema.xsd',
        nm.DSIG11_NAMESPACE: f'{SCHEMAS_DIR}DSIG/xmldsig11-schema.xsd',
        nm.XENC_NAMESPACE: f'{SCHEMAS_DIR}XENC/xenc-schema.xsd',
        nm.XENC11_NAMESPACE: f'{SCHEMAS_DIR}XENC/xenc-schema-11.xsd',

        # Remote locations: contributors can propose additional official locations
        # for other namespaces for extending this list.
        nm.XSLT_NAMESPACE: 'http://www.w3.org/2007/schema-for-xslt20.xsd',
    }

    missing_locations: set[str]
    locations: NamespaceResourcesMap[str]

    def __init__(self, maps: 'XsdGlobals'):
        self.maps = maps
        self.missing_locations = set()  # Missing or failing resource locations

        # Set locations from validator init options
        validator = maps.validator
        self.schema_class = type(validator)
        self.base_url = validator.source.base_url
        self.locations = get_locations(validator.locations)
        if not validator.use_fallback:
            self.fallback_locations = {}

        # Save other validator init options, used for creating new schemas.
        self._init_options = {
            'validation': validator.validation,
            'converter': validator.converter,
            'allow': validator.source.allow,
            'defuse': validator.source.defuse,
            'timeout': validator.source.timeout,
            'uri_mapper': validator.source.uri_mapper,
            'opener': validator.source.opener,
            'use_xpath3': validator.use_xpath3,
        }

    def is_missing(self, namespace: str,
                   location: Optional[str] = None,
                   base_url: Optional[str] = None) -> bool:
        return namespace not in self.maps.namespaces \
            or not any(s.maps is self.maps for s in self.maps.namespaces[namespace])

    def get_locations(self, namespace: str, location: Optional[str] = None) -> list[str]:
        locations: list[str] = [location] if location else []

        if namespace in self.locations:
            locations.extend(x for x in self.locations[namespace])
        if namespace in self.fallback_locations:
            locations.append(self.fallback_locations[namespace])
        return locations

    def load_declared_schemas(self, schema) -> None:
        """
        Processes xs:include, xs:redefine, xs:override and xs:import statements,
        loading the schemas and/or the namespaced referred into declarations.
        """
        if schema not in self.maps.schemas:
            raise XMLSchemaValueError(f"{schema} is not registered in {self.maps}!")

        logger.debug("Processes inclusions and imports of schema %r", self)

        for child in schema.source.root:
            if child.tag in nm.XSD_ANNOTATION:
                continue
            elif child.tag not in (nm.XSD_IMPORT, nm.XSD_INCLUDE, nm.XSD_REDEFINE) \
                    and (child.tag != nm.XSD_OVERRIDE or schema.XSD_VERSION == '1.0'):
                break

            location = child.get('schemaLocation')
            if child.tag == nm.XSD_IMPORT:
                namespace = child.get('namespace', '').strip()
                if namespace == schema.target_namespace:
                    if namespace == '':
                        msg = _("if the 'namespace' attribute is not present on "
                                "the import statement then the imported schema "
                                "must have a 'targetNamespace'")
                    else:
                        msg = _("the attribute 'namespace' must be different "
                                "from schema's 'targetNamespace'")
                    schema.parse_error(msg)
                    continue

                schema.imported_namespaces.append(namespace)
                if not self.is_missing(namespace, location):
                    continue

                locations = self.get_locations(namespace, location)
                if not locations:
                    continue

                self.import_namespace(schema, namespace, locations)

            elif location is not None:
                # Process xs:include/xs:redefine/xs:override only if it has a
                # schemaLocation attribute. If not an error has been already
                # generated by the XSD validation with against the meta-schema.
                self._load_inclusions(child, schema, location)

        logger.debug("Inclusions and imports of schema %r processed", schema)

    def _load_inclusions(self, elem: ElementType,
                                     schema: SchemaType, location: str) -> None:
        """A valid xs:include/xs:redefine/xs:override element."""
        operation = elem.tag.split('}')[-1]
        logger.info("Process xs:%s schema from %s", operation, location)
        try:
            _schema = self.include_schema(schema, location, schema.base_url)
        except OSError as err:
            # It is not an error if the location fails to resolve:
            #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#compound-schema
            #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#src-include
            if elem.tag == nm.XSD_INCLUDE:
                msg = _("Include schema failed: {}").format(err)
            else:
                # If the xs:redefine/xs:override doesn't contain components (annotation
                # excluded) the statement is equivalent to an include, so no error is
                # generated, otherwise fails.
                if any(e.tag != nm.XSD_ANNOTATION and not callable(e.tag) for e in elem):
                    schema.parse_error(str(err), elem)

                if elem.tag == nm.XSD_REDEFINE:
                    msg = _("Redefine schema failed: {}").format(err)
                else:
                    msg = _("Override schema failed: {}").format(err)

            schema.warnings.append(msg)
            warnings.warn(msg, XMLSchemaIncludeWarning, stacklevel=3)

        except (XMLSchemaParseError, XMLSchemaTypeError, ParseError) as err:
            if elem.tag == nm.XSD_INCLUDE:
                msg = _("can't include schema {!r}: {}")
            elif elem.tag == nm.XSD_REDEFINE:
                msg = _("can't redefine schema {!r}: {}")
            else:
                msg = _("can't override schema {!r}: {}")

            if isinstance(err, (XMLSchemaParseError, ParseError)):
                schema.parse_error(msg.format(location, err), elem)
            else:
                raise type(err)(msg.format(location, err))
        else:
            if _schema is schema and operation != 'include':
                msg = _("can't {} the same schema {!r}").format(operation, schema)
                schema.parse_error(msg, elem)
            elif operation == 'redefine':
                _schema.redefine = schema
            elif operation == 'override':
                _schema.override = schema

    def import_namespace(self, schema: SchemaType,
                         namespace: str, location_hints: list[str]) -> None:
        import_error: Optional[Exception] = None
        for location in location_hints:
            try:
                logger.info("Import namespace %r from %r", namespace, location)
                self.import_schema(schema, namespace, location, schema.base_url)
            except (OSError, XMLResourceBlocked, XMLResourceForbidden) as err:
                # It's not an error if the location access fails (ref. section 4.2.6.2):
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#composition-schemaImport
                #
                # Also consider block or defuse of XML data as a location access fail.
                logger.debug('%s', err)
                if import_error is None:
                    import_error = err
            except (XMLSchemaParseError, XMLSchemaTypeError, ParseError) as err:
                if namespace:
                    msg = _("cannot import namespace {0!r}: {1}").format(namespace, err)
                else:
                    msg = _("cannot import chameleon schema: %s") % err
                if isinstance(err, (XMLSchemaParseError, ParseError)):
                    schema.parse_error(msg)
                else:
                    raise type(err)(msg)

            except XMLSchemaValueError as err:
                schema.parse_error(err)
            else:
                logger.info("Namespace %r imported from %r", namespace, location)
                break
        else:
            if import_error is not None:
                msg = _("Import of namespace {!r} from {!r} failed: {}.")
                schema.warnings.append(msg.format(namespace, location_hints, str(import_error)))
                warnings.warn(schema.warnings[-1], XMLSchemaImportWarning, stacklevel=4)

    def import_schema(self, target_schema: SchemaType,
                      namespace: str,
                      location: str,
                      base_url: Optional[str] = None,
                      build: bool = False) -> Optional[SchemaType]:
        """
        Imports a schema from a specific URL.

        :param target_schema: the importer schema.
        :param namespace: is the URI of the external namespace.
        :param location: is the URL of the schema.
        :param base_url: is an optional base URL for fetching the schema resource, \
        otherwise use the base url of the loader, if any.
        :param build: defines when to build the imported schema, the default is to not build.
        :return: the imported :class:`XMLSchema` instance.
        """
        if location in target_schema.imports:
            return target_schema.imports[location]

        logger.debug("Load schema from %r", location)
        schema = self.load_schema(location, base_url=base_url, build=build)
        if schema.target_namespace != namespace:
            msg = _('imported schema {!r} has an unmatched namespace {!r}')
            raise XMLSchemaValueError(msg.format(location, namespace))

        if target_schema is schema:
            return schema
        elif location not in target_schema.imports:
            target_schema.imports[location] = schema
        return schema

    def include_schema(self, target_schema: SchemaType,
                       location: str,
                       base_url: Optional[str] = None,
                       build: bool = False) -> SchemaType:
        if location in target_schema.includes:
            return target_schema.includes[location]

        schema = self.load_schema(location, target_schema.target_namespace, base_url, build)

        if target_schema is not schema:
            target_schema.includes[location] = schema
        return schema

    def load_schema(self, source: SchemaSourceType,
                    namespace: Optional[str] = None,
                    base_url: Optional[str] = None,
                    build: bool = False) -> SchemaType:
        """
        Loads a schema from a location.

        :param source: a URI that reference to a resource or a file path or a file-like \
        object or a string containing the schema or an Element or an ElementTree document.
        :param namespace: is the URI of the namespace that the schema belongs to.
        :param base_url: is an optional base URL for fetching the schema resource, \
        otherwise use the base url of the loader, if any.
        :param build: defines when to build the loaded schema, the default is to not build.
        :return: the loaded schema or the schema that matches the URL if it's already loaded.
        """
        schema = self.maps.match_source(source, base_url)
        if schema is not None:
            logger.info("Resource %r is already loaded", schema.source)
            return schema

        if is_url(source):
            logger.debug("Load schema from URL %r", source)
        else:
            logger.debug("Load schema from %r", type(source))

        return self.schema_class(
            source=source,
            namespace=namespace,
            base_url=base_url,
            global_maps=self.maps,
            build=build,
            **self._init_options,
        )

    def load_namespace(self, namespace: str) -> bool:
        if namespace in self.maps.namespaces:
            return True

        for location in self.get_locations(namespace):
            url = normalize_url(location, self.base_url)
            if not self.is_missing(namespace, url):
                break
            elif url in self.missing_locations:
                continue

            try:
                self.load_schema(url, namespace)
            except OSError:
                self.missing_locations.add(url)

        return namespace in self.maps.namespaces


class UrlSchemaLoader(SchemaLoader):
    urls: set[Optional[str]]

    def is_missing(self, namespace: str,
                   location: Optional[str] = None,
                   base_url: Optional[str] = None) -> bool:
        return namespace not in self.maps.namespaces or location is None \
            or normalize_url(location, base_url) not in self.urls


class SafeSchemaLoader(SchemaLoader):
    urls: set[Optional[str]]

    def load_schema(self, source: SchemaSourceType,
                    namespace: Optional[str] = None,
                    base_url: Optional[str] = None,
                    build: bool = False) -> SchemaType:
        schema = super().load_schema(source, namespace, base_url)

        other_schemas = self.maps.namespaces[schema.target_namespace]
        for child in schema.root:
            if (name := child.get('name')) is not None:
                pass
        return schema