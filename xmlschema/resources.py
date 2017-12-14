# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os.path

from .compat import (
    PY3, StringIO, unicode_type, urlopen, urlsplit, urljoin, uses_relative, urlunsplit, pathname2url, URLError
)
from .etree import etree_iterparse, etree_fromstring, etree_parse_error, etree_iselement
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaURLError, XMLSchemaOSError
from .namespaces import get_namespace
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
    Examines the source and returns the root Element, the XML text and an url
    if available. Returns only the root Element if the optional argument 
    "element_only" is True. This function is usable for XML data files of small 
    or medium sizes, as XSD schemas.

    :param source: an URL, a filename path or a file-like object.
    :param element_only: If True the function returns only the root Element of the tree.
    :return: a tuple with three items (root Element, XML text and XML URL) or
    only the root Element if 'element_only' argument is True.
    """
    # source argument is a string
    if isinstance(source, (str, bytes, unicode_type)):
        try:
            xml_root = etree_fromstring(source)
        except (etree_parse_error, UnicodeEncodeError):
            if len(source.splitlines()) > 1:
                raise
        else:
            return xml_root if element_only else (xml_root, source, None)

        xml_data, xml_url = load_resource(source)
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
            xml_url = getattr(source, 'name', getattr(source, 'url', None))
            source.close()

    try:
        xml_root = etree_fromstring(xml_data)
    except (etree_parse_error, UnicodeEncodeError) as err:
        raise XMLSchemaValueError(
            "error parsing XML data from %r: %s" % (xml_url or type(xml_data), err)
        )
    else:
        return xml_root if element_only else (xml_root, xml_data, xml_url)


def load_resource(url):
    """
    Load resource from an URL, decoding into a UTF-8 string.

    :param url: Resource URLs.
    :return: Resource as unicode string ad the loaded URL.
    """
    msg = "cannot load resource from %r: %s"
    try:
        source = urlopen(normalize_url(url))
    except URLError as err:
        raise XMLSchemaURLError(reason=msg % (url, err.reason))
    else:
        try:
            data = source.read()
        except (OSError, IOError) as err:
            raise XMLSchemaOSError(msg % (url, err))
        finally:
            source.close()

    if PY3:
        try:
            return data.decode('utf-8'), url
        except UnicodeDecodeError:
            return data.decode('iso-8859-1'), url
    else:
        try:
            return data.encode('utf-8'), url
        except UnicodeDecodeError:
            import codecs
            with codecs.open(urlsplit(url).path, mode='rb', encoding='iso-8859-1') as text_file:
                return text_file.read().encode('iso-8859-1'), url


def normalize_url(url, base_url=None):
    """
    Returns a normalized url. If URL scheme is missing the 'file' scheme is set.

    :param url: An relative or absolute URL.
    :param base_url: A reference base URL to join.
    :return: A normalized URL.
    """
    url_parts = urlsplit(url)
    if url_parts.scheme and url_parts.scheme in uses_relative:
        return url_parts.geturl()
    elif base_url is None:
        pathname = os.path.abspath(url_parts.geturl())
        return urljoin(u'file:', pathname2url(pathname))
    else:
        base_url_parts = urlsplit(base_url)
        if base_url_parts.scheme and base_url_parts.scheme in uses_relative:
            return urlunsplit((
                base_url_parts.scheme,
                base_url_parts.netloc,
                os.path.join(base_url_parts.path, pathname2url(url)),
                base_url_parts.query,
                base_url_parts.fragment
            ))
        else:
            pathname = os.path.abspath(os.path.join(base_url, url))
            url_parts = urlsplit(pathname2url(pathname))
            if url_parts.scheme and url_parts.scheme in uses_relative:
                return url_parts.geturl()
            else:
                return urljoin(u'file:', url_parts.geturl())


def fetch_resource(location, base_url=None):
    """
    Fetch a resource trying to open it. If the resource is accessible
    returns the URL, otherwise raises an error (XMLSchemaURLError).

    :param location: An URL or a file path.
    :param base_url: Reference path for completing local URLs.
    :return: A normalized URL.
    """
    if not location:
        raise XMLSchemaValueError("'location' argument must contains a not empty string.")

    url = normalize_url(location, base_url)
    try:
        resource = urlopen(url)
    except URLError as err:
        # fallback joining the path without a base URL
        url = normalize_url(location)
        try:
            resource = urlopen(url)
        except URLError:
            raise XMLSchemaURLError(
                reason="cannot access resource from %r: %s" % (location, str(err))
            )
        else:
            resource.close()
            return url
    else:
        resource.close()
        return url


def get_xml_root(source):
    """
    Returns the root Element and an URL, if available.

    :param source: an ElementTree structure, a string containing XML data, \
    an URL or a file-like object.
    :return: A 2-tuple with root Element and the source URL or `None`.
    """
    if isinstance(source, (str, bytes, unicode_type)):
        # source argument is a string
        if '\n' not in source:
            try:
                for _, xml_root in etree_iterparse(StringIO(source), events=('start',)):
                    return xml_root, None
            except (etree_parse_error, UnicodeEncodeError):
                xml_url = normalize_url(source)
                resource = urlopen(xml_url)
                try:
                    for _, xml_root in etree_iterparse(resource, events=('start',)):
                        return xml_root, xml_url
                finally:
                    resource.close()
        else:
            for _, xml_root in etree_iterparse(StringIO(source), events=('start',)):
                return xml_root, None
    else:
        # source is a file-like object containing XML data
        try:
            xml_url = source.uri
        except AttributeError:
            try:
                xml_url = normalize_url(source.file)
            except AttributeError:
                raise XMLSchemaTypeError(
                    "an ElementTree structure, a string containing XML data, "
                    "an URL or a file-like object is required, not %r." % type(source)
                )

        for _, xml_root in etree_iterparse(urlopen(xml_url), events=('start',)):
            return xml_root, xml_url


def fetch_schema(xml_document):
    """
    Fetch the schema URL from an XML document. If no schema location is found
    raises a ValueError.

    :param xml_document: An Element or an Element Tree with XML data or an URL or a
    file-like object.
    :return: An URL referring to the schema resource.
    """
    try:
        xml_root, xml_url = xml_document.getroot(), None
    except (AttributeError, TypeError):
        if etree_iselement(xml_document):
            xml_root, xml_url = xml_document, None
        else:
            xml_root, xml_url = get_xml_root(xml_document)
    else:
        if not etree_iselement(xml_root):
            raise XMLSchemaTypeError(
                "wrong type %r for 'xml_document' argument." % type(xml_document)
            )

    namespace = get_namespace(xml_root.tag)
    base_url = None if xml_url is None else os.path.dirname(xml_url)
    if namespace:
        uri_list = get_xsi_schema_location(xml_root).split()
        for uri, url in zip(uri_list[0::2], uri_list[1::2]):
            if uri == namespace:
                try:
                    return fetch_resource(url, base_url)
                except XMLSchemaURLError:
                    pass
    else:
        schema_location = get_xsi_no_namespace_schema_location(xml_root)
        if schema_location:
            return fetch_resource(schema_location, base_url)
    raise XMLSchemaValueError("schema for XML document %r not found." % xml_document)
