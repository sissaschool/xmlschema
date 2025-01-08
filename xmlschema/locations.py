#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os
from collections.abc import Iterable, Iterator, MutableMapping
from typing import Any, Optional, TypeVar

from xmlschema.aliases import LocationsType, UriMapperType
from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.translation import gettext as _
from xmlschema.utils.urls import normalize_locations
import xmlschema.names as nm

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

    def __init__(self, *args: Any, **kwargs: Any):
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


# Standard locations: contributors are invited to propose additional official
# locations for other well-known namespaces.
LOCATIONS = {
    nm.XSD_NAMESPACE: "https://www.w3.org/2001/XMLSchema.xsd",
    nm.XML_NAMESPACE: "https://www.w3.org/2001/xml.xsd",
    nm.XSI_NAMESPACE: "https://www.w3.org/2001/XMLSchema-instance",
    nm.XSLT_NAMESPACE: "https://www.w3.org/2007/schema-for-xslt20.xsd",
    nm.HFP_NAMESPACE: "https://www.w3.org/2001/XMLSchema-hasFacetAndProperty",
    nm.VC_NAMESPACE: "https://www.w3.org/2007/XMLSchema-versioning/XMLSchema-versioning.xsd",
    nm.XLINK_NAMESPACE: "https://www.w3.org/1999/xlink.xsd",
    nm.WSDL_NAMESPACE: "https://schemas.xmlsoap.org/wsdl/",
    nm.SOAP_NAMESPACE: "https://schemas.xmlsoap.org/wsdl/soap/",
    nm.SOAP_ENVELOPE_NAMESPACE: "https://schemas.xmlsoap.org/soap/envelope/",
    nm.SOAP_ENCODING_NAMESPACE: "https://schemas.xmlsoap.org/soap/encoding/",
    nm.DSIG_NAMESPACE: "https://www.w3.org/2000/09/xmldsig#",
    nm.DSIG11_NAMESPACE: "https://www.w3.org/2009/xmldsig11#",
    nm.XENC_NAMESPACE: "https://www.w3.org/TR/xmlenc-core/xenc-schema.xsd",
    nm.XENC11_NAMESPACE: "https://www.w3.org/TR/xmlenc-core1/xenc-schema-11.xsd",
}

# Fallback locations for well-known
FALLBACK_LOCATIONS = {
    nm.XML_NAMESPACE: f'{SCHEMAS_DIR}XML/xml.xsd',
    nm.XSI_NAMESPACE: f'{SCHEMAS_DIR}XSI/XMLSchema-instance.xsd',
    nm.HFP_NAMESPACE: f'{SCHEMAS_DIR}HFP/XMLSchema-hasFacetAndProperty.xsd',
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
}

FALLBACK_MAP = {
    LOCATIONS[k]: FALLBACK_LOCATIONS[k]
    for k, v in LOCATIONS.items() if k in FALLBACK_LOCATIONS
}


class UriMapper:
    """
    Returns a URI mapper callable objects that extends lookup to SSL protocol variants.

    :param uri_mapper: optional URI mapper to wrap.
    :param fallback_map: optional fallback map for standard namespaces.
    """
    def __init__(self, uri_mapper: Optional[UriMapperType] = None,
                 fallback_map: Optional[dict[str, str]] = None) -> None:
        self._uri_mapper = uri_mapper
        self.fallback_map = {} if fallback_map is None else fallback_map

    def map_uri(self, uri: str) -> str:
        if isinstance(self._uri_mapper, MutableMapping):
            uri = self._uri_mapper.get(uri, uri)
        elif callable(self._uri_mapper):
            uri = self._uri_mapper(uri)
        return self.fallback_map.get(uri, uri)

    def __call__(self, uri: str) -> str:
        if not uri.startswith(('http:', 'https:', 'ftp:', 'sftp:')):
            return self.map_uri(uri)
        elif (url := self.map_uri(uri)) != uri:
            return url
        elif uri.startswith('http:'):
            return self.map_uri(uri.replace('http:', 'https:', 1))
        elif uri.startswith('https:'):
            return self.map_uri(uri.replace('https:', 'http:', 1))
        elif uri.startswith('sftp:'):
            return self.map_uri(uri.replace('sftp:', 'ftp:', 1))
        else:
            return self.map_uri(uri.replace('ftp:', 'sftp:', 1))
