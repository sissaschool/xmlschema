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
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, MutableMapping, Sequence
from typing import Any, Optional, TypeVar, Union

from xmlschema.aliases import LocationsType, SchemaType
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import get_qname, local_name
from xmlschema.utils.urls import normalize_locations
import xmlschema.names as nm

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

    def __init__(self, locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 use_fallback: bool = False):
        self.schemas = set()
        self.namespaces = NamespaceResourcesMap()
        self.locations = LocationHints.from_args(locations, base_url)

        if not use_fallback:
            self.fallback_locations = {}

        self.missing_locations = set()  # Missing or failing resource locations

    def get_locations(self, namespace: str) -> list[str]:
        locations: list[str]

        if namespace not in self.locations:
            locations = []
        else:
            locations = [x for x in self.locations[namespace]]

        if namespace in self.fallback_locations:
            locations.append(self.fallback_locations[namespace])
        return locations

    def __copy__(self) -> 'SchemaLoader':
        loader: SchemaLoader = object.__new__(self.__class__)
        loader.__dict__.update(self.__dict__)
        loader.schemas = {s for s in self.schemas}
        loader.namespaces = self.namespaces.copy()
        loader.locations = self.locations.copy()
        return loader

    def copy(self) -> 'SchemaLoader':
        return self.__copy__()
