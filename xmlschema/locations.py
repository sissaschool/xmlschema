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
from collections.abc import Iterable, MutableMapping
from typing import Optional

from xmlschema.namespaces import NamespaceResourcesMap
from xmlschema.aliases import LocationsMapType, LocationsType, UriMapperType
from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.translation import gettext as _
from xmlschema.utils.urls import normalize_locations
import xmlschema.names as nm

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), 'schemas/')


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


def get_fallback_map(locations: LocationsMapType, fallbacks: LocationsMapType) -> dict[str, str]:
    fallback_map: dict[str, str] = {}

    for ns, urls in locations.items():
        if ns in fallbacks:
            fallback_urls = fallbacks[ns]
            if isinstance(urls, str) and isinstance(fallback_urls, str):
                fallback_map[urls] = fallback_urls
            elif isinstance(urls, list) and isinstance(fallback_urls, list):
                fallback_map.update(zip(urls, fallback_urls))

    return fallback_map


# Standard locations for well-known namespaces
LOCATIONS: LocationsMapType = {
    nm.XSD_NAMESPACE: [
        "https://www.w3.org/2001/XMLSchema.xsd",  # XSD 1.0
        "https://www.w3.org/2009/XMLSchema/XMLSchema.xsd",  # Mutable XSD 1.1
        "https://www.w3.org/2012/04/XMLSchema.xsd"
    ],
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

# Fallback locations for well-known namespaces
FALLBACK_LOCATIONS: LocationsMapType = {
    nm.XSD_NAMESPACE: [
        f'{SCHEMAS_DIR}XSD_1.0/XMLSchema.xsd',
        f'{SCHEMAS_DIR}XSD_1.1/XMLSchema.xsd',
        f'{SCHEMAS_DIR}XSD_1.1/XMLSchema.xsd',
    ],
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


class UrlResolver:
    """
    Returns a URL resolver callable objects that extends lookup to SSL protocol variants.
    An instance of this class is included in the schema configuration to resolve URLs
    for checking if a schema resource is already loaded.

    :param uri_mapper: optional URI mapper to wrap.
    :param use_fallback: whether to use fallback locations.
    """
    fallback_map = get_fallback_map(LOCATIONS, FALLBACK_LOCATIONS)

    def __init__(self, uri_mapper: Optional[UriMapperType] = None,
                 use_fallback: bool = True) -> None:
        self._uri_mapper = uri_mapper
        if not use_fallback:
            self.fallback_map = {}

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
