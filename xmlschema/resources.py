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
import os.path
import re
import codecs

from .compat import (
    PY3, StringIO, unicode_type, urlopen, urlsplit, urljoin, uses_relative, urlunsplit, pathname2url, URLError
)
from .etree import (
    etree_iselement, etree_parse, etree_iterparse, etree_fromstring, etree_parse_error,
    safe_etree_parse, safe_etree_fromstring, safe_etree_iterparse, safe_etree_parse_error
)
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaURLError, XMLSchemaOSError
from .namespaces import get_namespace
from .qnames import XSI_SCHEMA_LOCATION, XSI_NONS_SCHEMA_LOCATION


DEFUSE_MODES = ('always', 'remote', 'never')


def is_remote_url(url):
    return url is not None and urlsplit(url).scheme not in ('', 'file')


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
            pathname = os.path.abspath(os.path.join(base_url_parts.path, pathname2url(url)))
            return urlunsplit((
                base_url_parts.scheme,
                base_url_parts.netloc,
                pathname,
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


def fetch_resource(location, base_url=None, timeout=300):
    """
    Fetch a resource trying to accessing it. If the resource is accessible
    returns the URL, otherwise raises an error (XMLSchemaURLError).

    :param location: an URL or a file path.
    :param base_url: reference base URL for normalizing local and relative URLs.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :return: a normalized URL.
    """
    if not location:
        raise XMLSchemaValueError("'location' argument must contains a not empty string.")

    url = normalize_url(location, base_url)
    try:
        resource = urlopen(url, timeout=timeout)
    except URLError as err:
        # fallback joining the path without a base URL
        url = normalize_url(location)
        try:
            resource = urlopen(url, timeout=timeout)
        except URLError:
            raise XMLSchemaURLError(reason=err.reason)
        else:
            resource.close()
            return url
    else:
        resource.close()
        return url


class XMLResource(object):

    def __init__(self, source, defuse='remote', timeout=300, lazy=True):
        if defuse not in DEFUSE_MODES:
            raise XMLSchemaValueError("'defuse' argument value has to be in {}: {}".format(DEFUSE_MODES, defuse))
        if not isinstance(timeout, int):
            raise XMLSchemaValueError("'timeout' argument value must be > 0: %d" % timeout)

        self._root = self._data = self._url = None
        self.defuse = defuse
        self.timeout = timeout
        self.source = source
        if not lazy:
            self.load()

    def __setattr__(self, name, value):
        super(XMLResource, self).__setattr__(name, value)
        if name == 'source':
            self._root, self._data, self._url = self.getroot(only_root=False)

    @property
    def root(self):
        return self._root

    @property
    def data(self):
        return self._data

    @property
    def url(self):
        return self._url

    @property
    def base_url(self):
        return os.path.dirname(self._url) if self._url is not None else None

    @property
    def namespace(self):
        return get_namespace(self._root.tag) if self._root is not None else None

    @property
    def parse(self):
        if self.defuse == 'always' or self.defuse == 'remote' and is_remote_url(self._url):
            return safe_etree_parse
        else:
            return etree_parse

    @property
    def iterparse(self):
        if self.defuse == 'always' or self.defuse == 'remote' and is_remote_url(self._url):
            return safe_etree_iterparse
        else:
            return etree_iterparse

    @property
    def fromstring(self):
        if self.defuse == 'always' or self.defuse == 'remote' and is_remote_url(self._url):
            return safe_etree_fromstring
        else:
            return etree_fromstring

    def is_loaded(self):
        return self._url is None or self._data is not None

    def getroot(self, only_root=True):
        if only_root and self._root is not None:
            return self._root

        source = self.source
        if etree_iselement(source):
            return source, None, None
        elif isinstance(source, (str, bytes, unicode_type)):
            try:
                # check if source is a string containing a valid XML root
                for _, root in self.iterparse(StringIO(source), events=('start',)):
                    return root if only_root else (root, source, None)
            except (etree_parse_error, safe_etree_parse_error, UnicodeEncodeError):
                pass
            url = normalize_url(source) if '\n' not in source else None
        elif hasattr(source, 'read'):
            # source should be a file-like object
            try:
                url = getattr(source, 'uri', normalize_url(source.file))
            except AttributeError:
                url = None
        else:
            try:
                root = source.getroot()
            except (AttributeError, TypeError):
                url = None
            else:
                if etree_iselement(root):
                    return root if only_root else (root, None, None)
                url = None

        if url is None:
            raise XMLSchemaTypeError(
                "an ElementTree structure, a string containing XML data, an URL or "
                "a file-like object is required, not %r." % type(source)
            )
        else:
            resource = urlopen(url, timeout=self.timeout)
            try:
                for _, root in self.iterparse(resource, events=('start',)):
                    return root if only_root else (root, None, url)
            finally:
                resource.close()

    def open(self):
        try:
            return urlopen(self._url, timeout=self.timeout)
        except URLError as err:
            raise XMLSchemaURLError(reason="cannot access to resource %r: %s" % (self._url, err.reason))

    def load(self):
        if self._url is None:
            return  # Created from Element or text source --> already loaded

        resource = self.open()
        try:
            data = resource.read()
        except (OSError, IOError) as err:
            raise XMLSchemaOSError("cannot load data from %r: %s" % (self._url, err))
        finally:
            resource.close()

        try:
            self._data = data.decode('utf-8') if PY3 else data.encode('utf-8')
        except UnicodeDecodeError:
            if PY3:
                self._data = data.decode('iso-8859-1')
            else:
                with codecs.open(urlsplit(self._url).path, mode='rb', encoding='iso-8859-1') as f:
                    self._data = f.read().encode('iso-8859-1')

        try:
            self._root = self.fromstring(self._data)
        except (etree_parse_error, safe_etree_parse_error, UnicodeEncodeError) as err:
            raise XMLSchemaValueError(
                "error parsing XML data from %r: %s" % (self._url or type(self._data), err)
            )

    def iter_location_hints(self):
        for elem in self._root.iter():
            try:
                locations = elem.attrib[XSI_SCHEMA_LOCATION]
            except KeyError:
                pass
            else:
                locations = locations.split()
                for ns, url in zip(locations[0::2], locations[1::2]):
                    yield ns, url

            try:
                locations = elem.attrib[XSI_NONS_SCHEMA_LOCATION]
            except KeyError:
                pass
            else:
                for url in locations.split():
                    yield '', url

    def get_namespaces(self):
        """
        Extracts namespaces with related prefixes from the XML resource. If a duplicate
        prefix declaration is encountered then adds the namespace using a different prefix,
        but only in the case if the namespace URI is not already mapped by another prefix.

        :return: A dictionary for mapping namespace prefixes to full URI.
        """
        def update_nsmap(prefix, uri):
            if prefix not in nsmap:
                nsmap[prefix] = uri
            elif not any(uri == ns for ns in nsmap.values()):
                if not prefix:
                    try:
                        prefix = re.search('(\w+)$', uri.strip()).group()
                    except AttributeError:
                        return

                while prefix in nsmap:
                    match = re.search('(\d+)$', prefix)
                    if match:
                        index = int(match.group()) + 1
                        prefix = prefix[:match.span()[0]] + str(index)
                    else:
                        prefix += '2'
                nsmap[prefix] = uri

        nsmap = {}
        if self._data is not None:
            try:
                for event, node in self.iterparse(StringIO(self._data), events=('start-ns',)):
                    update_nsmap(*node)
            except (etree_parse_error, safe_etree_parse_error):
                pass
        elif self._url is not None:
            resource = self.open()
            try:
                for event, node in self.iterparse(resource, events=('start-ns',)):
                    update_nsmap(*node)
            except (etree_parse_error, safe_etree_parse_error):
                pass
            finally:
                resource.close()
        else:
            # Warning: can extracts namespace information only from lxml etree structures
            try:
                for elem in self._root.iter():
                    for k, v in elem.nsmap.items():
                        update_nsmap(k if k is not None else '', v)
            except (AttributeError, TypeError):
                pass  # Not an lxml's tree or element

        return nsmap


def fetch_namespaces(source, defuse='remote', timeout=300):
    """
    Extracts namespaces with related prefixes from the XML data source. If the source is
    an lxml's ElementTree/Element returns the nsmap attribute of the root. If a duplicate
    prefix declaration is encountered then adds the namespace using a different prefix,
    but only in the case if the namespace URI is not already mapped by another prefix.

    :param source: An XMLResource instance of a string containing the XML document or a
    file path or a file like object or an ElementTree or Element.
    :param defuse: set the usage of defusedxml library for parsing XML data. Can be 'always', \
    'remote' or 'never'. Default is 'remote' that uses the defusedxml only when loading remote data.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :return: A dictionary for mapping namespace prefixes to full URI.
    """
    if not isinstance(source, XMLResource):
        source = XMLResource(source, defuse, timeout)
    return source.get_namespaces()


def load_xml_resource(source, element_only=True, defuse='remote', timeout=300):
    """
    Load XML data source into an Element tree, returning the root Element, the XML text and an
    url, if available. Usable for XML data files of small or medium sizes, as XSD schemas.

    :param source: an URL, a filename path or a file-like object.
    :param element_only: if True the function returns only the root Element of the tree.
    :param defuse: set the usage of defusedxml library for parsing XML data. Can be 'always', \
    'remote' or 'never'. Default is 'remote' that uses the defusedxml only when loading remote data.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :return: a tuple with three items (root Element, XML text and XML URL) or \
    only the root Element if 'element_only' argument is True.
    """
    if not isinstance(source, XMLResource):
        source = XMLResource(source, defuse, timeout)
    source.load()
    return source.root if element_only else (source.root, source.data, source.url)


def fetch_schema_locations(source, locations=None, base_url=None, defuse='remote', timeout=300):
    """
    Fetch the schema URL and other location hints from an XML data source. If no
    accessible schema location is found for source root's namespace raises a ValueError.

    :param source: An XMLResource instance or an Element or an Element Tree with XML data \
    or an URL or a file-like object.
    :param locations: A dictionary or dictionary items with Schema location hints.
    :param base_url: is an optional base URL for fetching the schema resource from relative locations.
    :param defuse: Set the usage of defusedxml library on data. Can be 'always', 'remote' \
    or 'never'. Default is 'remote' that uses the defusedxml only when loading remote data.
    :param timeout: the timeout in seconds for the connection attempts in case of remote data.
    :return: A tuple with the URL referring to the first reachable schema resource,a list \
    of dictionary items with normalized location hints.
    """
    if not isinstance(source, XMLResource):
        source = XMLResource(source, defuse, timeout)

    if base_url is None:
        base_url = source.base_url
    else:
        base_url = normalize_url(base_url, source.base_url)

    if locations is None:
        locations = []
    else:
        try:
            locations = [(ns, normalize_url(url, base_url)) for ns, url in locations.items()]
        except AttributeError:
            locations = [(ns, normalize_url(url, base_url)) for ns, url in locations]

    locations.extend([(ns, normalize_url(url, base_url)) for ns, url in source.iter_location_hints()])
    namespace = source.namespace
    for ns, url in filter(lambda x: x[0] == namespace, locations):
        try:
            return fetch_resource(url, base_url), locations, base_url
        except XMLSchemaURLError:
            pass
    raise XMLSchemaValueError("not found a schema for XML data resource %r (namespace=%r)." % (source, namespace))


def fetch_schema(source, locations=None):
    """
    Fetch the schema URL from an XML data source. If no accessible schema location
    is found raises a ValueError.

    :param source: An XMLResource instance or an Element or an ElementTree or a string \
    containing XML data or an URL or a file-like object.
    :param locations: A dictionary or dictionary items with Schema location hints.
    :return: An URL referring to a reachable schema resource.
    """
    return fetch_schema_locations(source, locations)[0]
