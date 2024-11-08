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
from collections.abc import Callable, Iterable, Iterator, MutableMapping, Sequence
from typing import Any, Optional, TypeVar, Union
from xml.etree.ElementTree import ParseError

from xmlschema.aliases import ElementType, LocationsType, SchemaType, SchemaSourceType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import get_qname, local_name
from xmlschema.utils.urls import normalize_url, normalize_locations
from xmlschema.resources import XMLResourceBlocked, XMLResourceForbidden
import xmlschema.names as nm

from xmlschema.validators import XMLSchemaParseError, XMLSchemaIncludeWarning, \
    XMLSchemaImportWarning

logger = logging.getLogger('xmlschema')

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')

##
# Resources maps
T = TypeVar('T', bound=Any)
ResourceMapArg = Union[MutableMapping[str, T], Sequence[tuple[str, T]]]


class NamespaceResourcesMap(MutableMapping[str, list[T]]):
    """
    Dictionary for storing information about namespace resources. Values are
    lists of objects. Setting an existing value appends the object to the value.
    Setting a value with a list sets/replaces the value.
    """
    __slots__ = ('_store',)

    def __init__(self, *args: ResourceMapArg[T], **kwargs: T):
        self._store: dict[str, list[T]] = {}
        for item in args:
            self.update(item)
        self.update(**kwargs)

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


class LocationHints(NamespaceResourcesMap[str]):

    @classmethod
    def from_args(cls, locations: Optional[LocationsType],
                  base_url: Optional[str] = None) -> 'LocationHints':
        if isinstance(locations, cls):
            return locations
        elif locations is None:
            return cls()
        elif isinstance(locations, tuple):
            return cls(locations)
        else:
            return cls(normalize_locations(locations, base_url=base_url))


#
# Defines the load functions for XML Schema structures
def create_load_function(tag: str) \
        -> Callable[[dict[str, Any], Iterable[SchemaType]], None]:

    def load_xsd_globals(xsd_globals: dict[str, Any],
                         schemas: Iterable[SchemaType]) -> None:
        redefinitions = []
        for schema in schemas:
            target_namespace = schema.target_namespace

            for elem in schema.root:
                if elem.tag not in {nm.XSD_REDEFINE, nm.XSD_OVERRIDE}:
                    continue

                location = elem.get('schemaLocation')
                if location is None:
                    continue
                for child in filter(lambda x: x.tag == tag and 'name' in x.attrib, elem):
                    qname = get_qname(target_namespace, child.attrib['name'])
                    redefinitions.append((qname, elem, child, schema, schema.includes[location]))

            for elem in filter(lambda x: x.tag == tag and 'name' in x.attrib, schema.root):
                qname = get_qname(target_namespace, elem.attrib['name'])
                if qname not in xsd_globals:
                    xsd_globals[qname] = (elem, schema)
                else:
                    try:
                        other_schema = xsd_globals[qname][1]
                    except (TypeError, IndexError):
                        pass
                    else:
                        # It's ignored or replaced in case of an override
                        if other_schema.override is schema:
                            continue
                        elif schema.override is other_schema:
                            xsd_globals[qname] = (elem, schema)
                            continue

                    msg = _("global {0} with name={1!r} is already defined")
                    schema.parse_error(
                        error=msg.format(local_name(tag), qname),
                        elem=elem
                    )

        redefined_names = Counter(x[0] for x in redefinitions)
        for qname, elem, child, schema, redefined_schema in reversed(redefinitions):

            # Checks multiple redefinitions
            if redefined_names[qname] > 1:
                redefined_names[qname] = 1

                redefined_schemas: Any
                redefined_schemas = [x[-1] for x in redefinitions if x[0] == qname]
                if any(redefined_schemas.count(x) > 1 for x in redefined_schemas):
                    msg = _("multiple redefinition for {0} {1!r}")
                    schema.parse_error(
                        error=msg.format(local_name(child.tag), qname),
                        elem=child
                    )
                else:
                    redefined_schemas = {x[-1]: x[-2] for x in redefinitions if x[0] == qname}
                    for rs, s in redefined_schemas.items():
                        while True:
                            try:
                                s = redefined_schemas[s]
                            except KeyError:
                                break

                            if s is rs:
                                msg = _("circular redefinition for {0} {1!r}")
                                schema.parse_error(
                                    error=msg.format(local_name(child.tag), qname),
                                    elem=child
                                )
                                break

            if elem.tag == nm.XSD_OVERRIDE:
                # Components which match nothing in the target schema are ignored. See the
                # period starting with "Source declarations not present in the target set"
                # of the paragraph https://www.w3.org/TR/xmlschema11-1/#override-schema.
                if qname in xsd_globals:
                    xsd_globals[qname] = (child, schema)
            else:
                # Append to a list if it's a redefinition
                try:
                    xsd_globals[qname].append((child, schema))
                except KeyError:
                    schema.parse_error(_("not a redefinition!"), child)
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], (child, schema)]

    return load_xsd_globals


load_xsd_simple_types = create_load_function(nm.XSD_SIMPLE_TYPE)
load_xsd_attributes = create_load_function(nm.XSD_ATTRIBUTE)
load_xsd_attribute_groups = create_load_function(nm.XSD_ATTRIBUTE_GROUP)
load_xsd_complex_types = create_load_function(nm.XSD_COMPLEX_TYPE)
load_xsd_elements = create_load_function(nm.XSD_ELEMENT)
load_xsd_groups = create_load_function(nm.XSD_GROUP)
load_xsd_notations = create_load_function(nm.XSD_NOTATION)


class SchemaLoader:

    fallback_locations = {
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

    schemas: set[SchemaType]
    namespaces: NamespaceResourcesMap[SchemaType]
    locations: LocationHints
    missing_locations: set[str]

    def __init__(self, validator: SchemaType,
                 locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 use_fallback: bool = False):
        self.validator = validator
        self.schemas = set()
        self.namespaces = NamespaceResourcesMap()
        self.locations = LocationHints.from_args(locations, base_url)
        self.base_url = base_url

        if not use_fallback:
            self.fallback_locations = {}

        self.missing_locations = set()  # Missing or failing resource locations

        self.schema_class = type(validator)
        self.options = {
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
        return namespace not in self.namespaces

    def get_locations(self, namespace: str, location: Optional[str] = None) -> list[str]:
        locations: list[str] = [location] if location else []

        if namespace in self.locations:
            locations.extend(x for x in self.locations[namespace])
        if namespace in self.fallback_locations:
            locations.append(self.fallback_locations[namespace])
        return locations

    def copy(self) -> 'SchemaLoader':
        loader: SchemaLoader = object.__new__(self.__class__)
        loader.__dict__.update(self.__dict__)
        loader.schemas = {s for s in self.schemas}
        loader.namespaces = self.namespaces.copy()
        loader.locations = self.locations.copy()
        return loader

    __copy__ = copy

    def load_components(self, schema) -> None:
        """Add schema documents from imports, inclusions and redefinitions/overrides."""
        if schema not in self.schemas:
            raise XMLSchemaValueError(f"{schema} is not loaded!")

        logger.debug("Processing inclusions and imports of schema %r", self)

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

                schema._import_statements.add(namespace)
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
                self._process_inclusion_statement(child, schema, location)

        logger.debug("Inclusions and imports of schema %r processed", schema)

    def _process_inclusion_statement(self, elem: ElementType,
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
            if _schema is schema:
                pass  # FIXME??
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
            schema.imports[namespace] = None

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
        if base_url is None:
            base_url = self.base_url

        url = normalize_url(location, base_url)
        if location in target_schema.imports:
            return target_schema.imports[location]
        elif url in target_schema.imports:
            return target_schema.imports[url]

        schema = self.load_schema(url, build=build)
        if schema.target_namespace != namespace:
            msg = _('imported schema {!r} has an unmatched namespace {!r}')
            raise XMLSchemaValueError(msg.format(location, namespace))

        if target_schema is schema:
            return schema
        elif location not in target_schema.imports:
            target_schema.imports[location] = schema
        elif target_schema.imports[location] is not schema:
            target_schema.imports[url] = schema
        return schema

    def include_schema(self, target_schema: SchemaType,
                       location: str,
                       base_url: Optional[str] = None,
                       build: bool = False) -> SchemaType:
        url = normalize_url(location, base_url)
        if location in target_schema.includes:
            return target_schema.includes[location]
        elif url in target_schema.includes:
            return target_schema.includes[url]

        schema = self.load_schema(url, target_schema.target_namespace, build)

        if target_schema is schema:
            return schema
        elif location not in target_schema.includes:
            target_schema.includes[location] = schema
        elif target_schema.includes[location] is not schema:
            target_schema.includes[url] = schema
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
        for schema in self.schemas:
            if schema.url == source or schema.source is source or schema.source.source is source:
                logger.info("Resource %r is already loaded", source)
                return schema

        logger.debug("Load schema from %r", source)
        return self.schema_class(
            source=source,
            namespace=namespace,
            base_url=base_url or self.base_url,
            global_maps=self.validator.maps,
            build=build,
            **self.options,
        )
