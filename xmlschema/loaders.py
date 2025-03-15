#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import logging
import warnings
from operator import attrgetter
from typing import Any, Optional, TYPE_CHECKING
from xml.etree.ElementTree import ParseError

from xmlschema.aliases import ElementType, SchemaType, SchemaSourceType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError, \
    XMLResourceBlocked, XMLResourceForbidden, XMLResourceError
from xmlschema.locations import get_locations, FALLBACK_LOCATIONS, LOCATIONS
from xmlschema.namespaces import NamespaceResourcesMap
from xmlschema.translation import gettext as _
from xmlschema.resources import XMLResource
from xmlschema.utils.urls import get_url, is_local_url, normalize_url
import xmlschema.names as nm

from xmlschema.validators import XMLSchemaParseError, \
    XMLSchemaIncludeWarning, XMLSchemaImportWarning

if TYPE_CHECKING:
    from xmlschema.validators.global_maps import XsdGlobals

logger = logging.getLogger('xmlschema')
base_url_attribute = attrgetter('name')


class SchemaResource(XMLResource):
    """
    A naive XSD schema resource used by SafeSchemaLoader for checking XSD globals declarations.
    """
    includes: dict[str, str]
    override = None
    meta_schema = None

    def parse_error(self, error: str, *args: Any, **kwargs: Any) -> None:
        raise XMLSchemaValueError(error)

    @property
    def target_namespace(self) -> str:
        return self.root.get('targetNamespace', '')

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.includes = {}
        for elem in self.root:
            if elem.tag in (nm.XSD_REDEFINE, nm.XSD_OVERRIDE):
                location = elem.get('schemaLocation')
                if location is not None:
                    self.includes[location] = self.get_url(location)


class SchemaLoader:

    fallback_locations = {**LOCATIONS, **FALLBACK_LOCATIONS}

    locations: NamespaceResourcesMap[str]
    missing_locations: set[str]  # Missing or failing resource locations

    __slots__ = ('maps', 'namespaces', 'config', 'locations', 'missing_locations', '__dict__')

    def __init__(self, maps: 'XsdGlobals'):
        self.maps = maps
        self.namespaces = maps.namespaces
        self.config = maps.config
        self.locations = get_locations(self.config.locations, self.config.base_url)
        self.missing_locations = set()

        if not maps.config.use_fallback:
            self.fallback_locations = {}

    def get_locations(self, namespace: str, location: Optional[str] = None) -> list[str]:
        locations: list[str] = [location] if location else []

        if namespace in self.locations:
            locations.extend(x for x in self.locations[namespace])
        if namespace in self.fallback_locations:
            values = self.fallback_locations[namespace]

            if isinstance(values, str):
                locations.append(values)
            else:
                locations.extend(values)

        return locations

    def load_declared_schemas(self, schema: SchemaType) -> None:
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

    def _load_inclusions(self, elem: ElementType, schema: SchemaType, location: str) -> None:
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

        local_hints = [url for url in location_hints if is_local_url(url)]
        if local_hints:
            location_hints = local_hints + [x for x in location_hints if x not in local_hints]

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
                    msg = _("import of namespace {!r} failed: {}").format(namespace, err)
                else:
                    msg = _("import of chameleon schema failed: {}").format(err)

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
            schema = target_schema.imports[location]
            if schema is not None and schema.target_namespace != namespace:
                msg = _('imported schema {!r} has an unmatched namespace {!r}')
                raise XMLSchemaValueError(msg.format(location, namespace))

        if namespace in self.namespaces:
            logger.debug("Import schema in namespace %r from %r", namespace, location)
        else:
            logger.debug("Import namespace %r from %r", namespace, location)

        schema = self.load_schema(location, namespace, base_url, build)
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

        namespace = target_schema.target_namespace
        logger.debug("Include schema in namespace %r from %r", namespace, location)
        schema = self.load_schema(location, namespace, base_url, build)

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
        schema = self.get_schema(namespace, source, base_url)
        if schema is not None:
            logger.info("Resource %r is already loaded", schema.source)
            return schema

        return self.config.create_schema(
            source=source,
            namespace=namespace,
            base_url=base_url,
            build=build,
            global_maps=self.maps
        )

    def load_namespace(self, namespace: str) -> bool:
        if namespace in self.namespaces:
            return True

        for location in self.get_locations(namespace):
            url = normalize_url(location, self.config.base_url)
            if not self.is_missing(namespace, url):
                break
            elif url in self.missing_locations:
                continue

            try:
                self.load_schema(url, namespace)
            except OSError:
                self.missing_locations.add(url)

        return namespace in self.namespaces

    def get_schema(self, namespace: Optional[str] = None,
                   source: Optional[SchemaSourceType] = None,
                   base_url: Optional[str] = None) -> Optional[SchemaType]:
        schemas: Optional[list[SchemaType]]

        if namespace is not None:
            schemas = self.namespaces.get(namespace)
        elif isinstance(source, XMLResource):
            namespace = source.root.get('targetNamespace', '')
            schemas = self.namespaces.get(namespace)
        elif source is None:
            return None
        else:
            schemas = list(self.maps.schemas)

        if schemas is not None:
            if source is None:
                return schemas[0]
            elif (url := get_url(source)) is not None:
                url = self.config.url_resolver(url)
                url = normalize_url(url, base_url)
                for schema in schemas:
                    if url == schema.url:
                        return schema

            elif isinstance(source, XMLResource):
                for schema in schemas:
                    if schema.source.source is source.source:
                        return schema
            else:
                for schema in schemas:
                    if schema.source.source is source:
                        return schema

        return None

    def is_missing(self, namespace: str,
                   location: Optional[str] = None,
                   base_url: Optional[str] = None) -> bool:
        return namespace not in self.namespaces or \
            not any(s.maps is self.maps for s in self.namespaces[namespace])


class LocationSchemaLoader(SchemaLoader):

    def is_missing(self, namespace: str,
                   location: Optional[str] = None,
                   base_url: Optional[str] = None) -> bool:
        if namespace not in self.namespaces or \
                not any(s.maps is self.maps for s in self.namespaces[namespace]):
            return True

        schema = self.get_schema(namespace, location, base_url)
        return schema is None or schema.maps is not self.maps


class SafeSchemaLoader(SchemaLoader):

    def __init__(self, maps: 'XsdGlobals'):
        super().__init__(maps)
        self.global_maps = maps.global_maps.__class__.empty_maps(maps.validator.builders)

    def is_missing(self, namespace: str,
                   location: Optional[str] = None,
                   base_url: Optional[str] = None) -> bool:
        if namespace not in self.namespaces or \
                not any(s.maps is self.maps for s in self.namespaces[namespace]):
            return True

        schema = self.get_schema(namespace, location, base_url)
        if schema is not None and schema.maps is self.maps:
            return False
        if location is None:
            return True

        try:
            xml_resource = self.config.create_resource(
                location, cls=SchemaResource, base_url=base_url
            )
        except XMLResourceError:
            return False  # The resource is not accessible

        other_schemas: list[Any] = self.namespaces[namespace].copy()
        self.global_maps.clear()
        self.global_maps.load_globals(other_schemas + [xml_resource])
        return True
