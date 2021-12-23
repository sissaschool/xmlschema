#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import copy
import os.path
import platform
import re
import string
from io import StringIO, BytesIO
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import cast, Any, AnyStr, Dict, Optional, IO, Iterator, List, \
    MutableMapping, Union, Tuple
from urllib.request import urlopen
from urllib.parse import urlsplit, urlunsplit, unquote, quote_from_bytes
from urllib.error import URLError

from elementpath import iter_select, XPathContext, XPath2Parser
from elementpath.protocols import ElementProtocol

from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLResourceError
from .names import XML_NAMESPACE
from .etree import ElementTree, PyElementTree, SafeXMLParser, etree_tostring
from .aliases import ElementType, ElementTreeType, NamespacesType, XMLSourceType, \
    NormalizedLocationsType, LocationsType, NsmapType, ParentMapType
from .helpers import get_namespace, is_etree_element, is_etree_document, \
    etree_iter_location_hints

DEFUSE_MODES = frozenset(('never', 'remote', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox'))

###
# Restricted XPath parser for XML resources
LAZY_XML_XPATH_SYMBOLS = frozenset((
    'position', 'last', 'not', 'and', 'or', '!=', '<=', '>=', '(', ')', 'text',
    '[', ']', '.', ',', '/', '|', '*', '=', '<', '>', ':', '@', '(end)',
    '(unknown)', '(invalid)', '(name)', '(string)', '(float)', '(decimal)',
    '(integer)'
))

DRIVE_LETTERS = frozenset(string.ascii_letters)


class LazyXPath2Parser(XPath2Parser):
    symbol_table = {
        k: v for k, v in XPath2Parser.symbol_table.items()  # type: ignore[misc]
        if k in LAZY_XML_XPATH_SYMBOLS
    }
    SYMBOLS = LAZY_XML_XPATH_SYMBOLS


class LazySelector:
    """A limited XPath selector class for lazy XML resources."""

    def __init__(self, path: str, namespaces: Optional[NamespacesType] = None) -> None:
        self.parser = LazyXPath2Parser(namespaces, strict=False)
        self.path = path
        self.root_token = self.parser.parse(path)

    def __repr__(self) -> str:
        return '%s(path=%r)' % (self.__class__.__name__, self.path)

    def select(self, root: ElementProtocol, **kwargs: Any) -> List[ElementProtocol]:
        context = XPathContext(root, **kwargs)
        results = self.root_token.get_results(context)
        if not isinstance(results, list) or any(not is_etree_element(x) for x in results):
            msg = "XPath expressions on lazy resources can select only elements"
            raise XMLResourceError(msg)
        return results

    def iter_select(self, root: ElementProtocol, **kwargs: Any) -> Iterator[ElementProtocol]:
        context = XPathContext(root, **kwargs)
        for elem in self.root_token.select_results(context):
            if not is_etree_element(elem):
                msg = "XPath expressions on lazy resources can select only elements"
                raise XMLResourceError(msg)
            yield cast(ElementProtocol, elem)


###
# URL normalization (that fixes many headaches :)
class _PurePath(PurePath):
    """
    A version of pathlib.PurePath adapted for managing the creation
    from URIs and the simple normalization of paths.
    """
    _from_parts: Any
    _flavour: Any

    def __new__(cls, *args: str) -> '_PurePath':
        if cls is _PurePath:
            cls = _PureWindowsPath if os.name == 'nt' else _PurePosixPath
        return cast('_PurePath', cls._from_parts(args))

    @classmethod
    def from_uri(cls, uri: str) -> '_PurePath':
        uri = uri.strip()
        if not uri:
            raise XMLSchemaValueError("Empty URI provided!")

        if uri.startswith(r'\\'):
            return _PureWindowsPath(uri)  # UNC path
        elif uri.startswith('/'):
            return cls(uri)

        parts = urlsplit(uri)
        if not parts.scheme:
            return cls(uri)
        elif parts.scheme in DRIVE_LETTERS and len(parts.scheme) == 1:
            return _PureWindowsPath(uri)  # Eg. k:/Python/lib/....
        elif parts.scheme != 'file':
            return _PurePosixPath(unquote(parts.path))

        # Get file URI path because urlsplit does not parse it well
        start = 7 if uri.startswith('file:///') else 5
        if parts.query:
            path = uri[start:uri.index('?')]
        elif parts.fragment:
            path = uri[start:uri.index('#')]
        else:
            path = uri[start:]

        if ':' in path:
            # Windows path with a drive
            pos = path.index(':')
            if pos == 2 and path[0] == '/' and path[1] in DRIVE_LETTERS:
                return _PureWindowsPath(unquote(path[1:]))

            obj = _PureWindowsPath(unquote(path))
            if len(obj.drive) != 2 or obj.drive[1] != ':':
                raise XMLSchemaValueError("Invalid URI {!r}".format(uri))
            return obj

        if '\\' in path:
            return _PureWindowsPath(unquote(path))
        return cls(unquote(path))

    def as_uri(self) -> str:
        if not self.is_absolute():
            uri: str = self._flavour.make_uri(self)
            while uri.startswith('file:/'):
                uri = uri.replace('file:/', 'file:', 1)
            return uri

        uri = cast(str, self._flavour.make_uri(self))
        if isinstance(self, _PureWindowsPath) and str(self).startswith(r'\\'):
            # UNC format case: use the format where the host part is included
            # in the path part, to let urlopen() works.
            if not uri.startswith('file:////'):
                return uri.replace('file://', 'file:////')
        return uri

    def normalize(self) -> '_PurePath':
        normalized_path = self._flavour.pathmod.normpath(str(self))
        return cast('_PurePath', self._from_parts((normalized_path,)))


class _PurePosixPath(_PurePath, PurePosixPath):
    __slots__ = ()


class _PureWindowsPath(_PurePath, PureWindowsPath):
    __slots__ = ()


def normalize_url(url: str, base_url: Optional[str] = None,
                  keep_relative: bool = False) -> str:
    """
    Returns a normalized URL eventually joining it to a base URL if it's a relative path.
    Path names are converted to 'file' scheme URLs.

    :param url: a relative or absolute URL.
    :param base_url: a reference base URL.
    :param keep_relative: if set to `True` keeps relative file paths, which would \
    not strictly conformant to specification (RFC 8089), because *urlopen()* doesn't \
    accept a simple pathname.
    :return: a normalized URL string.
    """
    url_parts = urlsplit(url)
    if not is_local_scheme(url_parts.scheme):
        return url_parts.geturl()

    path = _PurePath.from_uri(url)
    if path.is_absolute():
        return path.normalize().as_uri()

    if base_url is not None:
        base_url_parts = urlsplit(base_url)
        base_path = _PurePath.from_uri(base_url)
        if is_local_scheme(base_url_parts.scheme):
            path = base_path.joinpath(path)
        elif not url_parts.scheme:
            path = base_path.joinpath(path).normalize()
            return urlunsplit((
                base_url_parts.scheme,
                base_url_parts.netloc,
                quote_from_bytes(bytes(path)),
                url_parts.query,
                url_parts.fragment
            ))

    if path.is_absolute() or keep_relative:
        return path.normalize().as_uri()

    base_path = _PurePath(os.getcwd())
    return base_path.joinpath(path).normalize().as_uri()


###
# Internal helper functions

def is_local_scheme(scheme: str) -> bool:
    return not scheme or scheme == 'file' or scheme in DRIVE_LETTERS


def is_url(obj: object) -> bool:
    """Returns `True` if the provided object is an URL, `False` otherwise."""
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
        try:
            urlsplit(obj.strip())
        except ValueError:
            return False
    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
        try:
            urlsplit(obj.strip())
        except ValueError:
            return False
    else:
        return isinstance(obj, Path)

    return True


def is_remote_url(obj: object) -> bool:
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
        try:
            return not is_local_scheme(urlsplit(obj.strip()).scheme)
        except ValueError:
            return False

    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
        try:
            return not is_local_scheme(urlsplit(obj.strip().decode('utf-8')).scheme)
        except ValueError:
            return False
    else:
        return False


def is_local_url(obj: object) -> bool:
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
        try:
            return is_local_scheme(urlsplit(obj.strip()).scheme)
        except ValueError:
            return False

    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
        try:
            return is_local_scheme(urlsplit(obj.strip().decode('utf-8')).scheme)
        except ValueError:
            return False
    else:
        return isinstance(obj, Path)


def url_path_is_file(url: str) -> bool:
    if not is_local_url(url):
        return False
    if os.path.isfile(url):
        return True
    path = unquote(urlsplit(normalize_url(url)).path)
    if path.startswith('/') and platform.system() == 'Windows':
        path = path[1:]
    return os.path.isfile(path)


###
# API for XML resources

def normalize_locations(locations: LocationsType,
                        base_url: Optional[str] = None,
                        keep_relative: bool = False) -> NormalizedLocationsType:
    """
    Returns a list of normalized locations. The locations are normalized using
    the base URL of the instance.

    :param locations: a dictionary or a list of couples containing namespace location hints.
    :param base_url: the reference base URL for construct the normalized URL from the argument.
    :param keep_relative: if set to `True` keeps relative file paths, which would not strictly \
    conformant to URL format specification.
    :return: a list of couples containing normalized namespace location hints.
    """
    normalized_locations = []
    if isinstance(locations, dict):
        for ns, value in locations.items():
            if isinstance(value, list):
                normalized_locations.extend(
                    [(ns, normalize_url(url, base_url, keep_relative)) for url in value]
                )
            else:
                normalized_locations.append((ns, normalize_url(value, base_url, keep_relative)))
    else:
        normalized_locations.extend(
            [(ns, normalize_url(url, base_url, keep_relative)) for ns, url in locations]
        )
    return normalized_locations


def fetch_resource(location: str, base_url: Optional[str] = None, timeout: int = 30) -> str:
    """
    Fetch a resource by trying to access it. If the resource is accessible
    returns its URL, otherwise raises an :class:`XMLResourceError`.

    :param location: an URL or a file path.
    :param base_url: reference base URL for normalizing local and relative URLs.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :return: a normalized URL.
    """
    if not location:
        raise XMLSchemaValueError("'location' argument must contain a not empty string")

    url = normalize_url(location, base_url)
    try:
        with urlopen(url, timeout=timeout):
            return url
    except URLError as err:
        # fallback joining the path without a base URL
        alt_url = normalize_url(location)
        if url == alt_url:
            raise XMLResourceError("cannot access to resource %r: %s" % (url, err.reason))

        try:
            with urlopen(alt_url, timeout=timeout):
                return alt_url
        except URLError:
            raise XMLResourceError("cannot access to resource %r: %s" % (url, err.reason))


def fetch_schema_locations(source: Union['XMLResource', XMLSourceType],
                           locations: Optional[LocationsType] = None,
                           base_url: Optional[str] = None,
                           allow: str = 'all',
                           defuse: str = 'remote',
                           timeout: int = 30) -> Tuple[str, NormalizedLocationsType]:
    """
    Fetches schema location hints from an XML data source and a list of location hints.
    If an accessible schema location is not found raises a ValueError.

    :param source: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or an URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param locations: a dictionary or dictionary items with additional schema location hints.
    :param base_url: the same argument of the :class:`XMLResource`.
    :param allow: the same argument of the :class:`XMLResource`.
    :param defuse: the same argument of the :class:`XMLResource`.
    :param timeout: the same argument of the :class:`XMLResource` but with a reduced default.
    :return: A 2-tuple with the URL referring to the first reachable schema resource \
    and a list of dictionary items with normalized location hints.
    """
    if not isinstance(source, XMLResource):
        resource = XMLResource(source, base_url, allow, defuse, timeout, lazy=True)
    else:
        resource = source

    base_url = resource.base_url
    namespace = resource.namespace
    locations = resource.get_locations(locations, root_only=False)
    if not locations:
        msg = "{!r} does not contain any schema location hint"
        raise XMLSchemaValueError(msg.format(source))

    for ns, url in sorted(locations, key=lambda x: x[0] != namespace):
        try:
            return fetch_resource(url, base_url, timeout), locations
        except XMLResourceError:
            pass

    raise XMLSchemaValueError("not found a schema for XML data resource {!r}.".format(source))


def fetch_schema(source: Union['XMLResource', XMLSourceType],
                 locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 30) -> str:
    """
    Like :meth:`fetch_schema_locations` but returns only a reachable
    location hint for a schema related to the source's namespace.
    """
    return fetch_schema_locations(source, locations, base_url, allow, defuse, timeout)[0]


def fetch_namespaces(source: XMLSourceType,
                     base_url: Optional[str] = None,
                     allow: str = 'all',
                     defuse: str = 'remote',
                     timeout: int = 30) -> NamespacesType:
    """
    Fetches namespaces information from the XML data source. The argument *source*
    can be a string containing the XML document or file path or an url or a file-like
    object or an ElementTree instance or an Element instance. A dictionary with
    namespace mappings is returned.
    """
    resource = XMLResource(source, base_url, allow, defuse, timeout, lazy=True)
    return resource.get_namespaces(root_only=False)


class XMLResource:
    """
    XML resource reader based on ElementTree and urllib.

    :param source: a string containing the XML document or file path or an URL or a \
    file like object or an ElementTree or an Element.
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the resource can't be obtained from the source argument. For security \
    access to a local file resource is always denied if the *base_url* is a remote URL.
    :param allow: defines the security mode for accessing resource locations. Can be \
    'all', 'remote', 'local' or 'sandbox'. Default is 'all' that means all types of \
    URLs are allowed. With 'remote' only remote resource URLs are allowed. With 'local' \
    only file paths and URLs are allowed. With 'sandbox' only file paths and URLs that \
    are under the directory path identified by the *base_url* argument are allowed.
    :param defuse: defines when to defuse XML data using a `SafeXMLParser`. Can be \
    'always', 'remote' or 'never'. For default defuses only remote XML data.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :param lazy: if a value `False` or 0 is provided the XML data is fully loaded into and \
    processed from memory. For default only the root element of the source is loaded, \
    except in case the *source* argument is an Element or an ElementTree instance. A \
    positive integer also defines the depth at which the lazy resource can be better \
    iterated (`True` means 1).
    """
    # Protected attributes for data and resource location
    _source: XMLSourceType
    _root: ElementType
    _nsmap: Dict[ElementType, List[Tuple[str, str]]]
    _text: Optional[str] = None
    _url: Optional[str] = None
    _base_url: Optional[str] = None
    _parent_map: Optional[ParentMapType] = None
    _lazy: Union[bool, int] = False

    def __init__(self, source: XMLSourceType,
                 base_url: Union[None, str, Path, bytes] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 300,
                 lazy: Union[bool, int] = False) -> None:

        if isinstance(base_url, str):
            if not is_url(base_url):
                raise XMLSchemaValueError("'base_url' argument is not an URL")
            self._base_url = base_url
        elif isinstance(base_url, Path):
            self._base_url = str(base_url)
        elif isinstance(base_url, bytes):
            if not is_url(base_url):
                raise XMLSchemaValueError("'base_url' argument is not an URL")
            self._base_url = base_url.decode()
        elif base_url is not None:
            msg = "invalid type {!r} for argument 'base_url'"
            raise XMLSchemaTypeError(msg.format(type(base_url)))

        if not isinstance(allow, str):
            msg = "invalid type {!r} for argument 'allow'"
            raise XMLSchemaTypeError(msg.format(type(allow)))
        elif allow not in SECURITY_MODES:
            msg = "'allow' argument: {!r} is not a security mode"
            raise XMLSchemaValueError(msg.format(allow))
        elif allow == 'sandbox' and self._base_url is None:
            msg = "block access to files out of sandbox requires 'base_url' to be set"
            raise XMLResourceError(msg)
        self._allow = allow

        if not isinstance(defuse, str):
            msg = "invalid type {!r} for argument 'defuse'"
            raise XMLSchemaTypeError(msg.format(type(defuse)))
        elif defuse not in DEFUSE_MODES:
            msg = "'defuse' argument: {!r} is not a defuse mode"
            raise XMLSchemaValueError(msg.format(defuse))
        self._defuse = defuse

        if not isinstance(timeout, int):
            msg = "invalid type {!r} for argument 'timeout'"
            raise XMLSchemaTypeError(msg.format(type(timeout)))
        elif timeout <= 0:
            msg = "the argument 'timeout' must be a positive integer"
            raise XMLSchemaValueError(msg)
        self._timeout = timeout

        self.parse(source, lazy)

    def __repr__(self) -> str:
        return '%s(root=%r)' % (self.__class__.__name__, self._root)

    @property
    def source(self) -> XMLSourceType:
        """The XML data source."""
        return self._source

    @property
    def root(self) -> ElementType:
        """The XML tree root Element."""
        return self._root

    @property
    def text(self) -> Optional[str]:
        """The XML text source, `None` if it's not available."""
        return self._text

    @property
    def name(self) -> Optional[str]:
        """
        The source name, is `None` if the instance is created from an Element or a string.
        """
        return None if self._url is None else os.path.basename(self._url)

    @property
    def url(self) -> Optional[str]:
        """
        The source URL, `None` if the instance is created from an Element or a string.
        """
        return self._url

    @property
    def base_url(self) -> Optional[str]:
        """The effective base URL used for completing relative locations."""
        return os.path.dirname(self._url) if self._url else self._base_url

    @property
    def filepath(self) -> Optional[str]:
        """
        The resource filepath if the instance is created from a local file, `None` otherwise.
        """
        if self._url:
            url_parts = urlsplit(self._url)
            if url_parts.scheme in ('', 'file'):
                return url_parts.path
        return None

    @property
    def allow(self) -> str:
        """The security mode for accessing resource locations."""
        return self._allow

    @property
    def defuse(self) -> str:
        """When to defuse XML data."""
        return self._defuse

    @property
    def timeout(self) -> int:
        """The timeout in seconds for accessing remote resources."""
        return self._timeout

    def _access_control(self, url: str) -> None:
        if self._allow == 'all':
            return
        elif self._allow == 'remote':
            if is_local_url(url):
                raise XMLResourceError("block access to local resource {}".format(url))
        elif is_remote_url(url):
            raise XMLResourceError("block access to remote resource {}".format(url))
        elif self._allow == 'sandbox' and self._base_url is not None:
            if not url.startswith(normalize_url(self._base_url)):
                raise XMLResourceError("block access to out of sandbox file {}".format(url))

    def _update_nsmap(self, nsmap: MutableMapping[str, str], prefix: str, uri: str) -> None:
        if not prefix:
            if not uri:
                return
            elif '' not in nsmap:
                if self.namespace:
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

    def _lazy_iterparse(self, resource: IO[AnyStr], nsmap: Optional[NsmapType] = None) \
            -> Iterator[Tuple[str, ElementType]]:
        events: Tuple[str, ...]
        _nsmap: List[Tuple[str, str]]

        if nsmap is None:
            events = 'start', 'end'
            _nsmap = []
        else:
            events = 'start-ns', 'end-ns', 'start', 'end'
            if isinstance(nsmap, list):
                _nsmap = nsmap
                _nsmap.clear()
            else:
                _nsmap = []

        if self._defuse == 'remote' and is_remote_url(self.base_url) \
                or self._defuse == 'always':
            safe_parser = SafeXMLParser(target=PyElementTree.TreeBuilder())
            tree_iterator = PyElementTree.iterparse(resource, events, safe_parser)
        else:
            tree_iterator = ElementTree.iterparse(resource, events)

        root_started = False
        nsmap_update = False

        _root = cast(Optional[ElementType], getattr(self, '_root', None))

        try:
            for event, node in tree_iterator:
                if event == 'start':
                    if not root_started:
                        self._root = node
                        root_started = True
                    if nsmap_update and isinstance(nsmap, dict):
                        for prefix, uri in _nsmap:
                            self._update_nsmap(nsmap, prefix, uri)
                        nsmap_update = False
                    yield event, node

                elif event == 'end':
                    yield event, node
                elif nsmap is not None:
                    if event == 'start-ns':
                        _nsmap.append(node)
                    else:
                        _nsmap.pop()
                    nsmap_update = isinstance(nsmap, dict)

        except Exception as err:
            if _root is not None:
                self._root = _root
            if isinstance(err, PyElementTree.ParseError):
                raise ElementTree.ParseError(str(err)) from None
            raise

    def _parse(self, resource: IO[AnyStr]) -> None:
        if self._defuse == 'remote' and is_remote_url(self.base_url) \
                or self._defuse == 'always':

            if not hasattr(resource, 'seekable') or not resource.seekable():
                text = resource.read()
                if isinstance(text, str):
                    resource = StringIO(text)
                else:
                    resource = BytesIO(text)

            safe_parser = SafeXMLParser(target=PyElementTree.TreeBuilder())
            try:
                for _ in PyElementTree.iterparse(resource, ('start',), safe_parser):
                    break
            except PyElementTree.ParseError as err:
                raise ElementTree.ParseError(str(err))
            else:
                resource.seek(0)

        elem: Optional[ElementType] = None
        nsmap: List[Tuple[str, str]] = []
        nsmap_changed = False
        namespaces = {}
        events = 'start-ns', 'end-ns', 'end'

        for event, node in ElementTree.iterparse(resource, events):
            if event == 'end':
                if nsmap_changed or elem is None:
                    namespaces[node] = nsmap[:]
                    nsmap_changed = False
                else:
                    namespaces[node] = namespaces[elem]
                elem = node
            elif event == 'start-ns':
                nsmap.append(node)
                nsmap_changed = True
            else:
                nsmap.pop()
                nsmap_changed = True

        assert elem is not None
        self._root = elem
        self._nsmap = namespaces

    def _parse_resource(self, resource: IO[AnyStr],
                        url: Optional[str],
                        lazy: Union[bool, int]) -> None:
        _url, self._url = self._url, url
        try:
            if not lazy:
                self._parse(resource)
            else:
                nsmap: List[Tuple[str, str]] = []
                for _, root in self._lazy_iterparse(resource, nsmap):  # pragma: no cover
                    self._nsmap = {root: nsmap}
                    break
        except Exception:
            self._url = _url
            raise

    def parse(self, source: XMLSourceType, lazy: Union[bool, int] = False) -> None:
        if isinstance(lazy, bool):
            pass
        elif not isinstance(lazy, int):
            msg = "invalid type {!r} for the attribute 'lazy'"
            raise XMLSchemaTypeError(msg.format(type(lazy)))
        elif lazy < 0:
            msg = "invalid value {!r} for the attribute 'lazy'"
            raise XMLSchemaValueError(msg.format(lazy))

        url: Optional[str]
        if isinstance(source, str):
            if is_url(source):
                # source is a string containing an URL or a file path
                url = normalize_url(source, self._base_url)
                self._access_control(url)

                with urlopen(url, timeout=self._timeout) as resource:
                    self._parse_resource(resource, url, lazy)

                self._text = None
                self._lazy = lazy
            else:
                # source is a string containing an XML document
                resource = StringIO(source)
                self._parse_resource(resource, None, lazy)
                self._text = source
                self._lazy = False

        elif isinstance(source, bytes):
            if is_url(source):
                url = normalize_url(source.decode(), self._base_url)
                self._access_control(url)

                with urlopen(url, timeout=self._timeout) as resource:
                    self._parse_resource(resource, url, lazy)

                self._text = None
                self._lazy = lazy

            else:
                resource = BytesIO(source)
                self._parse_resource(resource, None, lazy)
                self._text = source.decode()
                self._lazy = False

        elif isinstance(source, Path):
            url = normalize_url(str(source), self._base_url)
            self._access_control(url)

            with urlopen(url, timeout=self._timeout) as resource:
                self._parse_resource(resource, url, lazy)

            self._text = None
            self._lazy = lazy

        elif isinstance(source, StringIO):
            self._parse_resource(source, None, lazy)
            self._text = source.getvalue()
            self._lazy = lazy

        elif hasattr(source, 'read'):
            # source is a readable resource (remote or local file)
            url = getattr(source, 'url', None)
            if url is not None:
                # Save remote urls for open new resources (non seekable)
                if is_remote_url(url):
                    self._access_control(url)
                else:
                    url = None

            self._parse_resource(cast(IO[str], source), url, lazy)
            self._text = None
            self._lazy = lazy

        else:
            # Source is already an Element or an ElementTree.
            if hasattr(source, 'tag') and hasattr(source, 'attrib'):
                # Source is already an Element --> nothing to parse
                self._root = cast(ElementType, source)
            elif is_etree_document(source):
                # Could be only an ElementTree object at last
                self._root = cast(ElementTreeType, source).getroot()
            else:
                raise XMLSchemaTypeError(
                    "wrong type %r for 'source' attribute: an ElementTree object or "
                    "an Element instance or a string containing XML data or an URL "
                    "or a file-like object is required." % type(source)
                )

            self._text = self._url = None
            self._lazy = False
            self._nsmap = {}

            # TODO for Python 3.8+: need a Protocol for checking this with isinstance()
            if hasattr(self._root, 'nsmap'):
                nsmap = []
                lxml_nsmap = None
                for elem in cast(Any, self._root.iter()):
                    if lxml_nsmap != elem.nsmap:
                        lxml_nsmap = elem.nsmap
                        nsmap = [(k or '', v) for k, v in elem.nsmap.items()]
                    self._nsmap[elem] = nsmap

        self._parent_map = None
        self._source = source

    @property
    def namespace(self) -> str:
        """The namespace of the XML resource."""
        return '' if self._root is None else get_namespace(self._root.tag)

    @property
    def parent_map(self) -> Dict[ElementType, Optional[ElementType]]:
        if self._lazy:
            raise XMLResourceError("cannot create the parent map of a lazy resource")
        if self._parent_map is None:
            assert self._root is not None
            self._parent_map = {child: elem for elem in self._root.iter() for child in elem}
            self._parent_map[self._root] = None
        return self._parent_map

    def get_nsmap(self, elem: ElementType) -> List[Tuple[str, str]]:
        """
        Returns a list of couples with the namespace (nsmap) map of the element.
        Lazy resources have only a nsmap for the root element. If no nsmap is
        found for the element returns an empty list.
        """
        try:
            return self._nsmap[elem]
        except KeyError:
            return []

    def get_absolute_path(self, path: Optional[str] = None) -> str:
        if path is None:
            if self._lazy:
                return '/%s/%s' % (self._root.tag, '/'.join('*' * int(self._lazy)))
            return '/%s' % self._root.tag
        elif path.startswith('/'):
            return path
        else:
            return '/%s/%s' % (self._root.tag, path)

    def get_text(self) -> str:
        """
        Gets the source text of the XML document. If the source text is not
        available creates an encoded string representation of the XML tree.
        Il the resource is lazy raises a resource error.
        """
        if self._text is not None:
            return self._text
        elif self._url is not None:
            self.load()
            if self._text is not None:
                return self._text

        return self.tostring(xml_declaration=True)

    def tostring(self, indent: str = '', max_lines: Optional[int] = None,
                 spaces_for_tab: int = 4, xml_declaration: bool = False) -> str:
        """Generates a string representation of the XML resource."""
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy resource")

        elem = self._root
        namespaces = self.get_namespaces(root_only=False)
        _string = etree_tostring(elem, namespaces, indent, max_lines,
                                 spaces_for_tab, xml_declaration)

        return _string.decode('utf-8') if isinstance(_string, bytes) else _string

    def subresource(self, elem: ElementType) -> 'XMLResource':
        """Create an XMLResource instance from a subelement of a non-lazy XML tree."""
        if self._lazy:
            raise XMLResourceError("cannot create a subresource from a lazy resource")

        for e in self._root.iter():  # pragma: no cover
            if e is elem:
                break
        else:
            msg = "{!r} is not an element or the XML resource tree"
            raise XMLResourceError(msg.format(elem))

        resource = XMLResource(elem, self.base_url, self._allow, self._defuse, self._timeout)
        if not hasattr(elem, 'nsmap') and self._nsmap is not None:
            namespaces = {}
            _nsmap = self._nsmap[elem]
            _nsmap_initial_len = len(_nsmap)
            nsmap = list(dict(_nsmap).items())

            for e in elem.iter():
                if _nsmap is not self._nsmap[e]:
                    _nsmap = self._nsmap[e]
                    nsmap = nsmap[:]
                    nsmap.extend(_nsmap[_nsmap_initial_len:])
                namespaces[e] = nsmap

            resource._nsmap = namespaces

        return resource

    def open(self) -> IO[AnyStr]:
        """
        Returns a opened resource reader object for the instance URL. If the
        source attribute is a seekable file-like object rewind the source and
        return it.
        """
        if self.seek(0) == 0:
            return cast(IO[AnyStr], self._source)
        elif self._url is None:
            raise XMLResourceError("can't open, the resource has no URL associated.")

        try:
            return cast(IO[AnyStr], urlopen(self._url, timeout=self._timeout))
        except URLError as err:
            raise XMLResourceError(
                "cannot access to resource %r: %s" % (self._url, err.reason)
            )

    def seek(self, position: int) -> Optional[int]:
        """
        Change stream position if the XML resource was created with a seekable
        file-like object. In the other cases this method has no effect.
        """
        if not hasattr(self._source, 'read'):
            return None

        try:
            if not self._source.seekable():  # type: ignore[union-attr]
                return None
        except AttributeError:
            return None  # pragma: no cover
        except ValueError as err:
            raise XMLResourceError(str(err)) from None
        else:
            return self._source.seek(position)  # type: ignore[union-attr]

    def close(self) -> None:
        """
        Close the XML resource if it's created with a file-like object.
        In other cases this method has no effect.
        """
        try:
            self._source.close()  # type: ignore[union-attr]
        except (AttributeError, TypeError):
            pass

    def load(self) -> None:
        """
        Loads the XML text from the data source. If the data source is an Element
        the source XML text can't be retrieved.
        """
        if self._url is None and not hasattr(self._source, 'read'):
            return  # Created from Element or text source --> already loaded
        elif self._lazy:
            raise XMLResourceError("cannot load a lazy resource")

        resource = self.open()
        try:
            data = resource.read()
        finally:
            # We don't want to close the file obj if it wasn't originally
            # opened by `XMLResource`. That is the concern of the code
            # where the file obj came from.
            if resource is not self._source:
                resource.close()

        if isinstance(data, bytes):
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                text = data.decode('iso-8859-1')
        else:
            text = data

        self._text = text

    def is_lazy(self) -> bool:
        """Returns `True` if the XML resource is lazy."""
        return bool(self._lazy)

    def is_remote(self) -> bool:
        """Returns `True` if the resource is related with remote XML data."""
        return is_remote_url(self._url)

    def is_local(self) -> bool:
        """Returns `True` if the resource is related with local XML data."""
        return is_local_url(self._url)

    @property
    def lazy_depth(self) -> int:
        """
        The optimal depth for validate this resource. Is a positive
        integer for lazy resources and 0 for fully loaded XML trees.
        """
        return int(self._lazy)

    def is_loaded(self) -> bool:
        """Returns `True` if the XML text of the data source is loaded."""
        return self._text is not None

    def iter(self, tag: Optional[str] = None, nsmap: Optional[NsmapType] = None) \
            -> Iterator[ElementType]:
        """
        XML resource tree iterator. The iteration of a lazy resource
        is in reverse order (top level element is the last). If tag
        is not None or '*', only elements whose tag equals tag are
        returned from the iterator. Provide a *nsmap* list for
        tracking the namespaces of yielded elements. If *nsmap* is
        a dictionary the tracking of namespaces is cumulative on
        the whole tree, renaming prefixes in case of conflicts.
        """
        if self._lazy:
            resource = self.open()
            tag = '*' if tag is None else tag.strip()
            try:
                for event, node in self._lazy_iterparse(resource, nsmap):
                    if event == 'end':
                        if tag == '*' or node.tag == tag:
                            yield node
                        node.clear()
            finally:
                # Close the resource only if it was originally opened by XMLResource
                if resource is not self._source:
                    resource.close()

        elif not self._nsmap or nsmap is None:
            yield from self._root.iter(tag)
        else:
            _nsmap = None
            for elem in self._root.iter(tag):
                try:
                    if _nsmap is not self._nsmap[elem]:
                        _nsmap = self._nsmap[elem]
                        if isinstance(nsmap, list):
                            nsmap.clear()
                            nsmap.extend(_nsmap)
                        else:
                            for prefix, uri in _nsmap:
                                self._update_nsmap(nsmap, prefix, uri)
                except KeyError:
                    pass

                yield elem

    def iter_location_hints(self, tag: Optional[str] = None) -> Iterator[Tuple[str, str]]:
        """
        Yields all schema location hints of the XML resource. If tag
        is not None or '*', only location hints of elements whose tag
        equals tag are returned from the iterator.
        """
        for elem in self.iter(tag):
            yield from etree_iter_location_hints(elem)

    def iter_depth(self, mode: int = 1, nsmap: Optional[NsmapType] = None,
                   ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        """
        Iterates XML subtrees. For fully loaded resources yields the root element.
        On lazy resources the argument *mode* can change the sequence and the
        completeness of yielded elements. There are four possible modes, that
        generate different sequences of elements:\n
          1. Only the elements at *depth_level* level of the tree\n
          2. Only a root element pruned at *depth_level*\n
          3. The elements at *depth_level* and then a pruned root\n
          4. An incomplete root at start, the elements at *depth_level* and a pruned root

        :param mode: an integer in range [1..4] that defines the iteration mode.
        :param nsmap: provide a list/dict for tracking the namespaces of yielded \
        elements. If a list is passed the tracking is done at element level, otherwise \
        the tracking is on the whole tree, renaming prefixes in case of conflicts.
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        """
        if ancestors is not None:
            ancestors.clear()

        if not self._lazy:
            if nsmap is not None and self._nsmap:
                if isinstance(nsmap, list):
                    nsmap.clear()
                    nsmap.extend(self._nsmap[self._root])
                else:
                    for elem in self._root.iter():
                        for prefix, uri in self._nsmap[elem]:
                            self._update_nsmap(nsmap, prefix, uri)

            yield self._root
            return

        if mode not in (1, 2, 3, 4):
            raise XMLSchemaValueError("invalid argument mode={!r}".format(mode))

        resource = self.open()
        level = 0
        subtree_level = int(self._lazy)

        try:
            for event, node in self._lazy_iterparse(resource, nsmap):
                if event == "start":
                    if not level:
                        if mode == 4:
                            yield node
                    if ancestors is not None and level < subtree_level:
                        ancestors.append(node)
                    level += 1
                else:
                    level -= 1
                    if not level:
                        if mode != 1:
                            yield node
                    elif level != subtree_level:
                        if ancestors is not None and level < subtree_level:
                            ancestors.pop()
                        continue  # pragma: no cover
                    elif mode != 2:
                        yield node

                    del node[:]  # delete children, keep attributes, text and tail.
        finally:
            if self._source is not resource:
                resource.close()

    def iterfind(self, path: str,
                 namespaces: Optional[NamespacesType] = None,
                 nsmap: Optional[NsmapType] = None,
                 ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        """
        Apply XPath selection to XML resource that yields full subtrees.

        :param path: an XPath expression to select element nodes.
        :param namespaces: an optional mapping from namespace prefixes to URIs \
        used for parsing the XPath expression.
        :param nsmap: provide a list/dict for tracking the namespaces of yielded \
        elements. If a list is passed the tracking is done at element level, otherwise \
        the tracking is on the whole tree, renaming prefixes in case of conflicts.
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        """
        selector: Any

        if self._lazy:
            selector = LazySelector(path, namespaces)
            path = path.replace(' ', '').replace('./', '')
            resource = self.open()
            level = 0
            select_all = '*' in path and set(path).issubset({'*', '/'})
            if path == '.':
                subtree_level = 0
            elif path.startswith('/'):
                subtree_level = path.count('/') - 1
            else:
                subtree_level = path.count('/') + 1

            try:
                for event, node in self._lazy_iterparse(resource, nsmap):
                    if event == "start":
                        if ancestors is not None and level < subtree_level:
                            ancestors.append(node)
                        level += 1
                    else:
                        level -= 1
                        if not level:
                            if subtree_level:
                                pass
                            elif select_all or node in selector.select(self._root):
                                yield node
                        elif not subtree_level:
                            continue
                        elif level != subtree_level:
                            if ancestors is not None and level < subtree_level:
                                ancestors.pop()
                            continue  # pragma: no cover
                        elif select_all or node in selector.select(self._root):
                            yield node

                        del node[:]  # delete children, keep attributes, text and tail.

            finally:
                if self._source is not resource:
                    resource.close()

        else:
            if ancestors is None:
                selector = iter_select
            else:
                parent_map = self.parent_map
                ancestors.clear()

                def selector(*args: Any, **kwargs: Any) -> Iterator[Any]:
                    assert ancestors is not None
                    for e in iter_select(*args, **kwargs):
                        if e is self._root:
                            ancestors.clear()
                        else:
                            _ancestors = []
                            parent = e
                            try:
                                while True:
                                    parent = parent_map[parent]
                                    if parent is not None:
                                        _ancestors.append(parent)
                            except KeyError:
                                pass

                            if _ancestors:
                                ancestors.clear()
                                ancestors.extend(reversed(_ancestors))

                        yield e

            if not self._nsmap or nsmap is None:
                yield from selector(self._root, path, namespaces, strict=False)
            else:
                _nsmap = None
                for elem in selector(self._root, path, namespaces, strict=False):
                    try:
                        if _nsmap is not self._nsmap[elem]:
                            _nsmap = self._nsmap[elem]
                            if isinstance(nsmap, list):
                                nsmap.clear()
                                nsmap.extend(_nsmap)
                            else:
                                for prefix, uri in _nsmap:
                                    self._update_nsmap(nsmap, prefix, uri)
                    except KeyError:
                        pass

                    yield elem

    def find(self, path: str,
             namespaces: Optional[NamespacesType] = None,
             nsmap: Optional[NsmapType] = None,
             ancestors: Optional[List[ElementType]] = None) -> Optional[ElementType]:
        return next(self.iterfind(path, namespaces, nsmap, ancestors), None)

    def findall(self, path: str, namespaces: Optional[NamespacesType] = None) \
            -> List[ElementType]:
        return list(self.iterfind(path, namespaces))

    def get_namespaces(self, namespaces: Optional[NamespacesType] = None,
                       root_only: Optional[bool] = None) -> NamespacesType:
        """
        Extracts namespaces with related prefixes from the XML resource. If a duplicate
        prefix declaration is encountered and the prefix maps a different namespace,
        adds the namespace using a different generated prefix. The empty prefix '' is
        used only if it's declared at root level to avoid erroneous mapping of local
        names. In other cases uses 'default' prefix as substitute.

        :param namespaces: builds the namespace map starting over the dictionary provided.
        :param root_only: if `True`, or `None` and the resource is lazy, extracts \
        only the namespaces declared in the root element.
        :return: a dictionary for mapping namespace prefixes to full URI.
        """
        if namespaces is None:
            namespaces = {}
        elif namespaces.get('xml', XML_NAMESPACE) != XML_NAMESPACE:
            msg = "reserved prefix (xml) must not be bound to another namespace name"
            raise XMLSchemaValueError(msg)
        else:
            namespaces = copy.copy(namespaces)

        try:
            if root_only or root_only is None and self._lazy:
                for _ in self.iter(nsmap=namespaces):
                    break
            else:
                for _ in self.iter(nsmap=namespaces):
                    pass
        except (ElementTree.ParseError, PyElementTree.ParseError, UnicodeEncodeError):
            pass

        return namespaces

    def get_locations(self, locations: Optional[LocationsType] = None,
                      root_only: Optional[bool] = None) -> NormalizedLocationsType:
        """
        Extracts a list of schema location hints from the XML resource.
        The locations are normalized using the base URL of the instance.

        :param locations: a sequence of schema location hints inserted \
        before the ones extracted from the XML resource. Locations passed \
        within a tuple container are not normalized.
        :param root_only: if `True`, or if `None` and the resource is lazy, \
        extracts the location hints of the root element only.
        :returns: a list of couples containing normalized location hints.
        """
        if root_only is None:
            root_only = bool(self._lazy)

        if not locations:
            location_hints = []
        elif isinstance(locations, tuple):
            location_hints = [x for x in locations]
        else:
            location_hints = normalize_locations(locations, self.base_url)

        if root_only:
            location_hints.extend([
                (ns, normalize_url(url, self.base_url))
                for ns, url in etree_iter_location_hints(self._root)
            ])
        else:
            location_hints.extend([
                (ns, normalize_url(url, self.base_url))
                for ns, url in self.iter_location_hints()
            ])
        return location_hints
