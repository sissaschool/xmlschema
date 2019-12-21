# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
from elementpath import iter_select, Selector, XPath1Parser

from .compat import (
    PY3, StringIO, BytesIO, string_base_type, urlopen, urlsplit, urljoin, urlunsplit,
    pathname2url, URLError, uses_relative
)
from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaURLError, XMLSchemaOSError
from .namespaces import get_namespace
from .etree import ElementTree, PyElementTree, SafeXMLParser, etree_tostring, etree_iter_location_hints


DEFUSE_MODES = ('always', 'remote', 'never')


XML_RESOURCE_XPATH_SYMBOLS = {
    'position', 'last', 'not', 'and', 'or', '!=', '<=', '>=', '(', ')', 'text',
    '[', ']', '.', ',', '/', '|', '*', '=', '<', '>', ':', '(end)', '(name)',
    '(string)', '(float)', '(decimal)', '(integer)'
}


class XmlResourceXPathParser(XPath1Parser):
    symbol_table = {k: v for k, v in XPath1Parser.symbol_table.items() if k in XML_RESOURCE_XPATH_SYMBOLS}
    SYMBOLS = XML_RESOURCE_XPATH_SYMBOLS


XmlResourceXPathParser.build_tokenizer()


def is_remote_url(url):
    return isinstance(url, string_base_type) and urlsplit(url).scheme not in ('', 'file')


def url_path_is_directory(url):
    return os.path.isdir(urlsplit(url).path)


def url_path_is_file(url):
    return os.path.isfile(urlsplit(url).path)


def normalize_url(url, base_url=None, keep_relative=False):
    """
    Returns a normalized URL doing a join with a base URL. URL scheme defaults to 'file' and
    backslashes are replaced with slashes. For file paths the os.path.join is used instead of
    urljoin.

    :param url: a relative or absolute URL.
    :param base_url: the reference base URL for construct the normalized URL from the argument. \
    For compatibility between "os.path.join" and "urljoin" a trailing '/' is added to not empty paths.
    :param keep_relative: if set to `True` keeps relative file paths, which would not strictly \
    conformant to URL format specification.
    :return: A normalized URL.
    """
    def add_trailing_slash(x):
        return urlunsplit((x[0], x[1], x[2] + '/' if x[2] and x[2][-1] != '/' else x[2], x[3], x[4]))

    def filter_url(x):
        x = x.strip().replace('\\', '/')
        while x.startswith('//'):
            x = x.replace('//', '/', 1)
        while x.startswith('file:////'):
            x = x.replace('file:////', 'file:///', 1)
        if urlsplit(x).scheme in {'', 'file'}:
            x = x.replace('#', '%23')
        return x

    url = filter_url(url)

    if base_url is not None:
        base_url = filter_url(base_url)
        base_url_parts = urlsplit(base_url)
        base_url = add_trailing_slash(base_url_parts)
        if base_url_parts.scheme not in uses_relative:
            base_url_parts = urlsplit('file:///{}'.format(base_url))
        else:
            base_url_parts = urlsplit(base_url)

        if base_url_parts.scheme not in ('', 'file'):
            url = urljoin(base_url, url)
        else:
            url_parts = urlsplit(url)
            if url_parts.scheme not in ('', 'file'):
                url = urljoin(base_url, url)
            elif not url_parts.netloc or base_url_parts.netloc == url_parts.netloc:
                # Join paths only if host parts (netloc) are equal, using the os.path.join
                # instead of urljoin for path normalization.
                url = urlunsplit((
                    '',
                    base_url_parts.netloc,
                    os.path.normpath(os.path.join(base_url_parts.path, url_parts.path)),
                    url_parts.query,
                    url_parts.fragment,
                ))

                # Add 'file' scheme if '//' prefix is added
                if base_url_parts.netloc and not url.startswith(base_url_parts.netloc) and url.startswith('//'):
                    url = 'file:' + url

    url_parts = urlsplit(url, scheme='file')
    if url_parts.scheme not in uses_relative:
        normalized_url = 'file:///{}'.format(url_parts.geturl())  # Eg. k:/Python/lib/....
    elif url_parts.scheme != 'file':
        normalized_url = urlunsplit((
            url_parts.scheme,
            url_parts.netloc,
            pathname2url(url_parts.path),
            url_parts.query,
            url_parts.fragment,
        ))
    elif os.path.isabs(url_parts.path):
        normalized_url = url_parts.geturl()
    elif keep_relative:
        # Can't use urlunsplit with a scheme because it converts relative paths to absolute ones.
        normalized_url = 'file:{}'.format(urlunsplit(('',) + url_parts[1:]))
    else:
        normalized_url = urlunsplit((
            url_parts.scheme,
            url_parts.netloc,
            os.path.abspath(url_parts.path),
            url_parts.query,
            url_parts.fragment,
        ))
    return filter_url(normalized_url)


def fetch_resource(location, base_url=None, timeout=30):
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
        alt_url = normalize_url(location)
        try:
            resource = urlopen(alt_url, timeout=timeout)
        except URLError:
            raise XMLSchemaURLError("cannot access to resource %r: %s" % (url, err.reason))
        else:
            resource.close()
            return url
    else:
        resource.close()
        return url


def fetch_schema_locations(source, locations=None, base_url=None, defuse='remote', timeout=30):
    """
    Fetches schema location hints from an XML data source and a list of location hints.
    If an accessible schema location is not found raises a ValueError.

    :param source: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or an URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param locations: a dictionary or dictionary items with additional schema location hints.
    :param base_url: the same argument of the :class:`XMLResource`.
    :param defuse: the same argument of the :class:`XMLResource`.
    :param timeout: the same argument of the :class:`XMLResource` but with a reduced default.
    :return: A 2-tuple with the URL referring to the first reachable schema resource \
    and a list of dictionary items with normalized location hints.
    """
    if not isinstance(source, XMLResource):
        resource = XMLResource(source, base_url, defuse, timeout)
    else:
        resource = source

    base_url = resource.base_url
    namespace = resource.namespace
    locations = resource.get_locations(locations)
    if not locations:
        msg = "the XML data resource {!r} does not contain any schema location hint."
        raise XMLSchemaValueError(msg.format(source))

    for ns, url in sorted(locations, key=lambda x: x[0] != namespace):
        try:
            return fetch_resource(url, base_url, timeout), locations
        except XMLSchemaURLError:
            pass

    raise XMLSchemaValueError("not found a schema for XML data resource {!r}.".format(source))


def fetch_schema(source, locations=None, base_url=None, defuse='remote', timeout=30):
    """
    Like :meth:`fetch_schema_locations` but returns only a reachable
    location hint for a schema related to the source's namespace.
    """
    return fetch_schema_locations(source, locations, base_url, defuse, timeout)[0]


def fetch_namespaces(source, base_url=None, defuse='remote', timeout=30):
    """
    Fetches namespaces information from the XML data source. The argument *source*
    can be a string containing the XML document or file path or an url or a file-like
    object or an ElementTree instance or an Element instance. A dictionary with
    namespace mappings is returned.
    """
    resource = XMLResource(source, base_url, defuse, timeout)
    return resource.get_namespaces()


def load_xml_resource(source, element_only=True, **resource_options):
    """
    Load XML data source into an Element tree, returning the root Element, the XML text and an
    url, if available. Usable for XML data files of small or medium sizes, as XSD schemas.
    This helper function is deprecated from v1.0.17, use :class:`XMLResource` instead.

    :param source: an URL, a filename path or a file-like object.
    :param element_only: if True the function returns only the root Element of the tree.
    :param resource_options: keyword arguments for providing :class:`XMLResource` init options.
    :return: a tuple with three items (root Element, XML text and XML URL) or \
    only the root Element if 'element_only' argument is True.
    """
    import warnings
    warnings.warn("load_xml_resource() function will be removed in 1.1 version",
                  DeprecationWarning, stacklevel=2)

    lazy = resource_options.pop('lazy', False)
    source = XMLResource(source, lazy=lazy, **resource_options)
    if element_only:
        return source.root
    else:
        source.load()
        return source.root, source.text, source.url


class XMLResource(object):
    """
    XML resource reader based on ElementTree and urllib.

    :param source: a string containing the XML document or file path or an URL or a \
    file like object or an ElementTree or an Element.
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the resource can't be obtained from the source argument.
    :param defuse: set the usage of SafeXMLParser for XML data. Can be 'always', 'remote' \
    or 'never'. Default is 'remote' that uses the defusedxml only when loading remote data.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :param lazy: if a value `False` is provided the XML data is fully loaded into and \
    processed from memory. For default only the root element of the source is loaded, \
    except in case the *source* argument is an Element or an ElementTree instance.
    """
    _root = _text = _url = None

    def __init__(self, source, base_url=None, defuse='remote', timeout=300, lazy=True):
        self._base_url = base_url
        self.defuse = defuse
        self.timeout = timeout
        self._lazy = lazy
        self.source = source

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def __repr__(self):
        if self._root is None:
            return u'%s()' % self.__class__.__name__
        elif self._url is None:
            return u'%s(tag=%r)' % (self.__class__.__name__, self._root.tag)
        else:
            return u'%s(tag=%r, basename=%r)' % (
                self.__class__.__name__, self._root.tag, os.path.basename(self._url)
            )

    def __setattr__(self, name, value):
        if name == 'source':
            self._root, self._text, self._url = self._fromsource(value)
        elif name == '_base_url':
            if value is not None and not isinstance(value, string_base_type):
                msg = "invalid type {!r} for the attribute 'base_url'"
                raise XMLSchemaTypeError(msg.format(type(value)))
        elif name == 'defuse':
            if value is not None and not isinstance(value, string_base_type):
                msg = "invalid type {!r} for the attribute 'defuse'"
                raise XMLSchemaTypeError(msg.format(type(value)))
            elif value not in DEFUSE_MODES:
                msg = "'defuse' attribute: {!r} is not a defuse mode"
                raise XMLSchemaValueError(msg.format(value))
        elif name == 'timeout':
            if not isinstance(value, int):
                msg = "invalid type {!r} for the attribute 'timeout'"
                raise XMLSchemaTypeError(msg.format(type(value)))
            elif value <= 0:
                raise XMLSchemaValueError("the attribute 'timeout' must be a positive integer")
        elif name == '_lazy':
            if not isinstance(value, bool):
                msg = "invalid type {!r} for the attribute 'lazy'"
                raise XMLSchemaValueError(msg.format(type(value)))
        super(XMLResource, self).__setattr__(name, value)

    def _fromsource(self, source):
        url = None
        if hasattr(source, 'tag') and hasattr(source, 'attrib'):
            self._lazy = False
            return source, None, None  # Source is already an Element --> nothing to load

        elif isinstance(source, string_base_type):
            _url, self._url = self._url, None
            try:
                if self._lazy:
                    # check if source is a string containing a valid XML root
                    for _, root in self.iterparse(StringIO(source), events=('start',)):
                        return root, source, None
                else:
                    return self.fromstring(source), source, None
            except (ElementTree.ParseError, PyElementTree.ParseError, UnicodeEncodeError):
                if '\n' in source:
                    raise
            finally:
                self._url = _url

            url = normalize_url(source) if '\n' not in source else None

        elif isinstance(source, StringIO):
            _url, self._url = self._url, None
            try:
                if self._lazy:
                    for _, root in self.iterparse(source, events=('start',)):
                        return root, source.getvalue(), None
                else:
                    return self.parse(source).getroot(), source.getvalue(), None
            finally:
                self._url = _url

        elif hasattr(source, 'read'):
            try:
                # Save remote urls for open new resources (non seekable)
                if is_remote_url(source.url):
                    url = source.url
            except AttributeError:
                pass

            _url, self._url = self._url, url
            try:
                if self._lazy:
                    for _, root in self.iterparse(source, events=('start',)):
                        return root, None, url
                else:
                    return self.parse(source).getroot(), None, url
            finally:
                self._url = _url

        else:
            # Try ElementTree object at last
            try:
                root = source.getroot()
            except (AttributeError, TypeError):
                pass
            else:
                if hasattr(root, 'tag'):
                    self._lazy = False
                    return root, None, None

        if url is None:
            raise XMLSchemaTypeError(
                "wrong type %r for 'source' attribute: an ElementTree object or an Element instance or a "
                "string containing XML data or an URL or a file-like object is required." % type(source)
            )
        else:
            resource = urlopen(url, timeout=self.timeout)
            _url, self._url = self._url, url
            try:
                if self._lazy:
                    for _, root in self.iterparse(resource, events=('start',)):
                        return root, None, url
                else:
                    return self.parse(resource).getroot(), None, url
            finally:
                self._url = _url
                resource.close()

    @property
    def root(self):
        """The XML tree root Element."""
        return self._root

    @property
    def text(self):
        """The XML text source, `None` if it's not available."""
        return self._text

    @property
    def url(self):
        """The source URL, `None` if the instance is created from an Element tree or from a string."""
        return self._url

    @property
    def base_url(self):
        """The effective base URL used for completing relative locations."""
        return os.path.dirname(self._url) if self._url else self._base_url

    @property
    def document(self):
        """
        The resource as ElementTree XML document. It's `None` if the instance
        is lazy or if it's an lxml Element.
        """
        if isinstance(self.source, ElementTree.ElementTree):
            return self.source
        elif hasattr(self.source, 'getroot') and hasattr(self.source, 'parse'):
            return self.source  # lxml's _ElementTree
        elif not self._lazy and not hasattr(self.root, 'nsmap'):
            return ElementTree.ElementTree(self.root)

    @property
    def namespace(self):
        """The namespace of the XML resource."""
        return get_namespace(self._root.tag)

    @staticmethod
    def defusing(source):
        """
        Defuse an XML source, raising an `ElementTree.ParseError` if the source contains entity
        definitions or remote entity loading.

        :param source: a filename or file object containing XML data.
        """
        parser = SafeXMLParser(target=PyElementTree.TreeBuilder())
        try:
            for _, _ in PyElementTree.iterparse(source, ('start',), parser):
                break
        except PyElementTree.ParseError as err:
            raise ElementTree.ParseError(str(err))

    def parse(self, source):
        """
        An equivalent of *ElementTree.parse()* that can protect from XML entities attacks.
        When protection is applied XML data are loaded and defused before building the
        ElementTree instance. The protection applied is based on value of *defuse*
        attribute and *base_url* property.

        :param source: a filename or file object containing XML data.
        :returns: an ElementTree instance.
        """
        if self.defuse == 'always' or self.defuse == 'remote' and \
                hasattr(source, 'read') and is_remote_url(self.base_url):

            if hasattr(source, 'read'):
                text = source.read()
            else:
                with open(source) as f:
                    text = f.read()

            if isinstance(text, bytes):
                self.defusing(BytesIO(text))
                return ElementTree.parse(BytesIO(text))
            else:
                self.defusing(StringIO(text))
                return ElementTree.parse(StringIO(text))
        else:
            return ElementTree.parse(source)

    def iterparse(self, source, events=None):
        """
        An equivalent of *ElementTree.iterparse()* that can protect from XML entities attacks.
        When protection is applied the iterator yields pure-Python Element instances.
        The protection applied is based on resource *defuse* attribute and *base_url* property.

        :param source: a filename or file object containing XML data.
        :param events: a list of events to report back. If omitted, only “end” events are reported.
        """
        if self.defuse == 'always' or self.defuse == 'remote' and \
                hasattr(source, 'read') and is_remote_url(self.base_url):

            parser = SafeXMLParser(target=PyElementTree.TreeBuilder())
            try:
                return PyElementTree.iterparse(source, events, parser)
            except PyElementTree.ParseError as err:
                raise ElementTree.ParseError(str(err))
        else:
            return ElementTree.iterparse(source, events)

    def fromstring(self, text):
        """
        An equivalent of *ElementTree.fromstring()* that can protect from XML entities attacks.
        The protection applied is based on resource *defuse* attribute and *base_url* property.

        :param text: a string containing XML data.
        :returns: the root Element instance.
        """
        if self.defuse == 'always' or self.defuse == 'remote' and is_remote_url(self.base_url):
            self.defusing(StringIO(text))
        return ElementTree.fromstring(text)

    def tostring(self, indent='', max_lines=None, spaces_for_tab=4, xml_declaration=False):
        """Generates a string representation of the XML resource."""
        elem = self._root
        namespaces = self.get_namespaces()
        return etree_tostring(elem, namespaces, indent, max_lines, spaces_for_tab, xml_declaration)

    def copy(self, **kwargs):
        """Resource copy method. Change init parameters with keyword arguments."""
        obj = type(self)(
            source=self.source,
            base_url=kwargs.get('base_url', self.base_url),
            defuse=kwargs.get('defuse', self.defuse),
            timeout=kwargs.get('timeout', self.timeout),
            lazy=kwargs.get('lazy', self._lazy)
        )
        if obj._text is None and self._text is not None:
            obj._text = self._text
        return obj

    def open(self):
        """
        Returns a opened resource reader object for the instance URL. If the
        source attribute is a seekable file-like object rewind the source and
        return it.
        """
        if self.seek(0) == 0:
            return self.source
        elif self._url is None:
            raise XMLSchemaValueError("can't open, the resource has no URL associated.")

        try:
            return urlopen(self._url, timeout=self.timeout)
        except URLError as err:
            raise XMLSchemaURLError("cannot access to resource %r: %s" % (self._url, err.reason))

    def seek(self, position):
        """
        Change stream position if the XML resource was created with a seekable
        file-like object. In the other cases this method has no effect.
        """
        if not hasattr(self.source, 'read'):
            return

        try:
            if not self.source.seekable():
                return
        except AttributeError:
            pass
        else:
            return self.source.seek(position)

        try:
            value = self.source.seek(position)
        except AttributeError:
            pass
        else:
            return value if PY3 else position

        try:
            value = self.source.fp.seek(position)
        except AttributeError:
            pass
        else:
            return value if PY3 else position

    def close(self):
        """
        Close the XML resource if it's created with a file-like object.
        In other cases this method has no effect.
        """
        try:
            self.source.close()
        except (AttributeError, TypeError):
            pass

    def load(self):
        """
        Loads the XML text from the data source. If the data source is an Element
        the source XML text can't be retrieved.
        """
        if self._url is None and not hasattr(self.source, 'read'):
            return  # Created from Element or text source --> already loaded

        resource = self.open()
        try:
            data = resource.read()
        except (OSError, IOError) as err:
            raise XMLSchemaOSError("cannot load data from %r: %s" % (self._url, err))
        finally:
            # We don't want to close the file obj if it wasn't originally
            # opened by `XMLResource`. That is the concern of the code
            # where the file obj came from.
            if resource is not self.source:
                resource.close()

        if isinstance(data, bytes):
            try:
                text = data.decode('utf-8') if PY3 else data.encode('utf-8')
            except UnicodeDecodeError:
                if PY3:
                    text = data.decode('iso-8859-1')
                else:
                    with codecs.open(urlsplit(self._url).path, mode='rb', encoding='iso-8859-1') as f:
                        text = f.read().encode('iso-8859-1')
        else:
            text = data

        self._text = text

    def is_lazy(self):
        """Returns `True` if the XML resource is lazy."""
        return self._lazy

    def is_loaded(self):
        """Returns `True` if the XML text of the data source is loaded."""
        return self._text is not None

    def iter(self, tag=None):
        """XML resource tree iterator."""
        if not self._lazy:
            for elem in self._root.iter(tag):
                yield elem
            return
        elif self.seek(0) == 0:
            resource = self.source
        elif self._url is not None:
            resource = urlopen(self._url, timeout=self.timeout)
        else:
            resource = StringIO(self._text)

        # Note: lazy iteration change the order (top level element is the last)
        try:
            for event, elem in self.iterparse(resource, events=('end',)):
                if tag is None or elem.tag == tag:
                    yield elem
                elem.clear()
        finally:
            if resource is not self.source:
                resource.close()

    def iterfind(self, path=None, namespaces=None):
        """
        XML resource tree iterfind selector.

        :param path: an XPath expression to select nodes. If not provided the \
        iteration returns only the root node.
        :param namespaces: optional mapping from namespace prefixes to URIs. If the \
        resource is lazy and an empty dictionary is provided, the namespace map is \
        updated during the iteration.
        """
        if not self._lazy:
            if path is None:
                yield self._root
            else:
                for e in iter_select(self._root, path, namespaces, strict=False):
                    yield e
            return
        elif self.seek(0) == 0:
            resource = self.source
        elif self._url is not None:
            resource = urlopen(self._url, timeout=self.timeout)
        else:
            self.load()
            resource = StringIO(self._text)

        if namespaces or namespaces is None:
            events = ('start', 'end')
            nsmap = None
        else:
            # Track ad update namespaces
            events = ('start-ns', 'end-ns', 'start', 'end')
            nsmap = []

        try:
            if path is None:
                level = 0
                for event, node in self.iterparse(resource, events):
                    if event == "start":
                        if level == 0:
                            self._root.clear()
                            self._root = node
                        level += 1
                    elif event == 'end':
                        level -= 1
                        if level == 0:
                            yield node
                            node.clear()
                    elif event == 'start-ns':
                        nsmap.append(node)
                        namespaces[node[0]] = node[1]
                    else:
                        try:
                            del namespaces[nsmap.pop()[0]]
                        except KeyError:
                            pass
                        namespaces.update(nsmap)

            else:
                selector = Selector(path, namespaces, strict=False, parser=XmlResourceXPathParser)
                path = path.replace(' ', '').replace('./', '')
                path_level = path.count('/') + 1 if path != '.' else 0
                select_all = '*' in path and set(path).issubset({'*', '/'})

                level = 0
                for event, node in self.iterparse(resource, events):
                    if event == "start":
                        if level == 0:
                            self._root.clear()
                            self._root = node
                        level += 1
                    elif event == 'end':
                        level -= 1
                        if level == path_level and \
                                (select_all or node in selector.select(self._root)):
                            yield node
                            node.clear()
                        elif level == 0:
                            node.clear()
                    elif event == 'start-ns':
                        nsmap.append(node)
                        namespaces[node[0]] = node[1]
                    else:
                        try:
                            del namespaces[nsmap.pop()[0]]
                        except KeyError:
                            pass
                        namespaces.update(nsmap)

        finally:
            if self.source is not resource:
                resource.close()

    def iter_location_hints(self, root_only=False):
        """
        Yields schema location hints from the XML resource.

        :param root_only: if `True` yields only the location hints declared in \
        the root element.
        """
        if root_only:
            for ns_url in etree_iter_location_hints(self._root):
                yield ns_url
            return

        if self._url is not None or hasattr(self.source, 'read'):
            resource = self.open()
        elif isinstance(self._text, string_base_type):
            resource = StringIO(self._text)
        else:
            for elem in self._root.iter():
                for ns_url in etree_iter_location_hints(elem):
                    yield ns_url
            return

        try:
            for event, node in self.iterparse(resource, events=('start', 'end')):
                if event == 'end':
                    node.clear()
                else:
                    for ns_url in etree_iter_location_hints(node):
                        yield ns_url
        except (ElementTree.ParseError, PyElementTree.ParseError, UnicodeEncodeError):
            pass
        finally:
            if self.source is not resource:
                resource.close()

    def get_namespaces(self, namespaces=None, root_only=False):
        """
        Extracts namespaces with related prefixes from the XML resource. If a duplicate
        prefix declaration is encountered and the prefix maps a different namespace,
        adds the namespace using a different generated prefix. The empty prefix '' is
        used only if it's declared at root level to avoid erroneous mapping of local
        names. In other cases uses 'default' prefix as substitute.

        :param namespaces: builds the namespace map starting over the dictionary provided.
        :param root_only: if `True` extracts only the namespaces declared in the root element.
        :return: a dictionary for mapping namespace prefixes to full URI.
        """
        def update_nsmap(prefix, uri):
            if not prefix:
                if '' not in nsmap:
                    nsmap[prefix] = uri
                    return
                elif nsmap[''] == uri:
                    return
                prefix = 'default'

            while prefix in nsmap:
                if nsmap[prefix] == uri:
                    return
                match = re.search(r'(\d+)$', prefix)
                if match:
                    index = int(match.group()) + 1
                    prefix = prefix[:match.span()[0]] + str(index)
                else:
                    prefix += '0'
            nsmap[prefix] = uri

        nsmap = {}
        if not self.namespace:
            nsmap[''] = ''
        if namespaces:
            nsmap.update(namespaces)

        if self._url is not None or hasattr(self.source, 'read'):
            resource = self.open()
        elif isinstance(self._text, string_base_type):
            resource = StringIO(self._text)
        else:
            if hasattr(self._root, 'nsmap'):
                # Can extract namespace mapping information only from lxml etree structures
                if root_only:
                    for k, v in self._root.nsmap.items():
                        update_nsmap(k if k is not None else '', v)
                else:
                    for elem in self._root.iter():
                        for k, v in elem.nsmap.items():
                            update_nsmap(k if k is not None else '', v)

            if nsmap.get('') == '':
                del nsmap['']
            return nsmap

        events = ('start-ns', 'start') if root_only else ('start-ns', 'end')
        try:
            for event, node in self.iterparse(resource, events):
                if event == 'start-ns':
                    update_nsmap(*node)
                elif event == 'end':
                    node.clear()
                else:
                    break
        except (ElementTree.ParseError, PyElementTree.ParseError, UnicodeEncodeError):
            pass
        finally:
            # We don't want to close the file obj if it wasn't
            # originally opened by `XMLResource`. That is the concern
            # of the code where the file obj came from.
            if self.source is not resource:
                resource.close()

        if nsmap.get('') == '':
            del nsmap['']
        return nsmap

    def get_locations(self, locations=None, root_only=False):
        """
        Extracts a list of normalized schema location hints from the XML resource.
        The locations are normalized using the base URL of the instance.

        :param locations: a dictionary or a list of namespace resources that is \
        inserted before the schema location hints extracted from the XML resource.
        :param root_only: if `True` extracts only the location hints declared in \
        the root element.
        :returns: a list of couples containing namespace location hints.
        """
        base_url = self.base_url
        location_hints = []
        if locations is not None:
            try:
                for ns, value in locations.items():
                    if isinstance(value, list):
                        location_hints.extend([(ns, normalize_url(url, base_url)) for url in value])
                    else:
                        location_hints.append((ns, normalize_url(value, base_url)))
            except AttributeError:
                location_hints.extend([(ns, normalize_url(url, base_url)) for ns, url in locations])

        location_hints.extend([
            (ns, normalize_url(url, base_url)) for ns, url in self.iter_location_hints(root_only)
        ])
        return location_hints
