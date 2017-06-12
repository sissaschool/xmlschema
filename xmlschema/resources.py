# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os.path

try:
    # Python 3 specific imports
    from urllib.request import urlopen, urljoin, urlsplit, pathname2url
    from urllib.parse import uses_relative, urlparse
    from urllib.error import URLError
except ImportError:
    # Python 2 fallback
    from urllib import pathname2url
    from urllib2 import urlopen, URLError
    from urlparse import urlsplit, urljoin, uses_relative, urlparse

from .core import (
    PY3, etree_fromstring, etree_tostring, etree_parse_error, etree_iselement, unicode_type
)
from .exceptions import (
    XMLSchemaTypeError, XMLSchemaParseError, XMLSchemaValueError,
    XMLSchemaURLError, XMLSchemaOSError
)
from .utils import get_namespace
from .qnames import XSI_SCHEMA_LOCATION, XSI_NONS_SCHEMA_LOCATION


def get_xsi_schema_location(elem):
    """Retrieve the attribute xsi:schemaLocation from an XML document node."""
    try:
        return elem.find('.[@%s]' % XSI_SCHEMA_LOCATION).attrib.get(XSI_SCHEMA_LOCATION)
    except AttributeError:
        return None


def get_xsi_no_namespace_schema_location(elem):
    """Retrieve the attribute xsi:noNamespaceSchemaLocation from an XML document node."""
    try:
        return elem.find('.[@%s]' % XSI_NONS_SCHEMA_LOCATION).attrib.get(XSI_NONS_SCHEMA_LOCATION)
    except AttributeError:
        return None


def load_xml_resource(source, element_only=True):
    """
    Examines the source and returns the root Element, the XML text and an uri 
    if available. Returns only the root Element if the optional argument 
    "element_only" is True. This function is usable for XML data files of small 
    or medium sizes, as XSD schemas.

    :param source: An Element or an Element Tree with XML data or an URI or a 
    file-like object.
    :param element_only: If True the function returns only the root Element of the tree.
    :return: a tuple with three items (root Element, XML text and XML URI) or
    only the root Element if 'element_only' argument is True.
    """
    # source argument is an Element/ElementTree object.
    if etree_iselement(source):
        return source if element_only else (source, etree_tostring(source), None)
    else:
        try:
            xml_root = source.getroot()
        except AttributeError:
            pass
        else:
            if etree_iselement(xml_root):
                return xml_root if element_only else (xml_root, etree_tostring(xml_root), None)

    # source argument is a string
    if isinstance(source, (str, bytes, unicode_type)):
        try:
            xml_root = etree_fromstring(source)
        except (etree_parse_error, UnicodeEncodeError):
            if len(source.splitlines()) > 1:
                raise
        else:
            return xml_root if element_only else (xml_root, source, None)

        xml_data, xml_uri = load_resource(source)
    else:
        try:
            # source is a file-like object containing XML data
            xml_data = source.read()
        except AttributeError:
            raise XMLSchemaTypeError(
                "an Element tree, a string or a file-like object "
                "is required, not %r." % source.__class__.__name__
            )
        else:
            xml_uri = getattr(source, 'name', getattr(source, 'uri', None))
            source.close()

    try:
        xml_root = etree_fromstring(xml_data)
    except (etree_parse_error, UnicodeEncodeError) as err:
        raise XMLSchemaParseError(
            "error parsing XML data from %r: %s" % (xml_uri or type(xml_data), err)
        )
    else:
        return xml_root if element_only else (xml_root, xml_data, xml_uri)


def fetch_schema(source):
    """
    Fetch the schema URI from an XML resource. If no schema location is found
    raises a ValueError.

    :param source: An Element or an Element Tree with XML data or an URI or a
    file-like object.
    :return: An URI referring to the schema resource.
    """
    xml_root, xml_source, xml_uri = load_xml_resource(source, element_only=False)
    namespace = get_namespace(xml_root.tag)
    if namespace:
        uri_list = get_xsi_schema_location(xml_root).split()
        for ns, schema_location in zip(uri_list[0::2], uri_list[1::2]):
            if ns == namespace:
                return urljoin(xml_uri, schema_location)
    else:
        schema_location = get_xsi_no_namespace_schema_location(xml_root)
        if schema_location:
            return urljoin(xml_uri, schema_location)
    raise XMLSchemaValueError("schema not found for the XML resource %r." % source)


def load_resource(uri):
    """
    Load resource from an URI, decoding into a UTF-8 string.

    :param uri: Resource URIs.
    :return: Resource as unicode string ad the loaded URI.
    """
    msg = "cannot load resource from %r: %s"
    try:
        source, uri = open_resource(uri)
    except XMLSchemaURLError as err:
        raise XMLSchemaURLError(reason=msg % (uri, err))
    else:
        try:
            data = source.read()
        except (OSError, IOError) as err:
            raise XMLSchemaOSError(msg % (uri, err))
        finally:
            source.close()

    if PY3:
        try:
            return data.decode('utf-8'), uri
        except UnicodeDecodeError:
            return data.decode('iso-8859-1'), uri
    else:
        try:
            return data.encode('utf-8'), uri
        except UnicodeDecodeError:
            import codecs
            with codecs.open(urlsplit(uri).path, mode='rb', encoding='iso-8859-1') as text_file:
                return text_file.read().encode('iso-8859-1'), uri


def open_resource(locations, base_uri=None):
    """
    Open the first available resource from a space-separated list of locations.

    :param locations: Space-separated list of locations.
    :param base_uri: Reference path for completing local URIs.
    :return: A couple of opened file-like object and a normalized URI.
    """
    if locations is None or not locations.strip():
        raise XMLSchemaValueError("No locations")

    errors = []
    for location in locations.split():
        uri_parts = urlsplit(location)
        uri = uri_parts.geturl()
        if uri_parts.scheme and uri_parts.scheme in uses_relative:
            # The location is a well formed uri
            try:
                return urlopen(uri), uri
            except URLError as err:
                errors.append(err.reason)
                uri_parts = urlsplit(urljoin(base_uri, os.path.basename(uri_parts.path)))
        else:
            # The location is a file path
            absolute_uri = urljoin(u'file:', pathname2url(os.path.abspath(uri)))
            try:
                return urlopen(absolute_uri), absolute_uri
            except URLError as err:
                errors.append(err.reason)
                if base_uri is None:
                    uri_parts = urlsplit(urljoin(__file__, uri))
                else:
                    uri_parts = urlsplit(urljoin(base_uri, uri))

        # Fallback tentative using a specific base_uri
        uri = uri_parts.geturl()
        if not uri_parts.scheme:
            uri = urljoin(u'file:', os.path.abspath(uri))
        try:
            return urlopen(uri), uri
        except URLError:
            pass
    else:
        raise XMLSchemaURLError(
            reason="cannot access resource from %r: %s" % (locations, errors)
        )
