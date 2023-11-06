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
from io import StringIO, BytesIO
from pathlib import Path
from typing import cast, Any, AnyStr, Dict, Optional, IO, Iterator, \
    List, MutableMapping, Union, Tuple
from urllib.request import urlopen as urlopen
from urllib.parse import urlsplit
from urllib.error import URLError

from elementpath import XPathToken, XPathContext, XPath2Parser, ElementNode, \
    LazyElementNode, DocumentNode, build_lxml_node_tree, build_node_tree
from elementpath.etree import ElementTree, PyElementTree, SafeXMLParser, etree_tostring
from elementpath.protocols import LxmlElementProtocol

from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLResourceError
from .names import XML_NAMESPACE, XSD_NAMESPACE
from .aliases import ElementType, NamespacesType, XMLSourceType, \
    NormalizedLocationsType, LocationsType, ParentMapType
from .helpers import get_namespace, update_namespaces, is_etree_document, \
    etree_iter_location_hints, etree_delete_preceding
from .locations import LocationPath, is_url, is_remote_url, is_local_url, \
    normalize_url, normalize_locations

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))

ResourceNodeType = Union[ElementNode, LazyElementNode, DocumentNode]


def fetch_resource(location: str, base_url: Optional[str] = None, timeout: int = 30) -> str:
    """
    Fetches a resource by trying to access it. If the resource is accessible
    returns its normalized URL, otherwise raises an `urllib.error.URLError`.

    :param location: a URL or a file path.
    :param base_url: reference base URL for normalizing local and relative URLs.
    :param timeout: the timeout in seconds for the connection attempt in case of remote data.
    :return: a normalized URL.
    """
    if not location:
        raise XMLSchemaValueError("the 'location' argument must contain a not empty string")

    url = normalize_url(location, base_url)
    try:
        with urlopen(url, timeout=timeout):
            return url
    except URLError:
        if url == normalize_url(location):
            raise
        else:
            # fallback using the location without a base URL
            alt_url = normalize_url(location)
            with urlopen(alt_url, timeout=timeout):
                return alt_url


def fetch_schema_locations(source: Union['XMLResource', XMLSourceType],
                           locations: Optional[LocationsType] = None,
                           base_url: Optional[str] = None,
                           allow: str = 'all',
                           defuse: str = 'remote',
                           timeout: int = 30,
                           root_only: bool = True) -> Tuple[str, NormalizedLocationsType]:
    """
    Fetches schema location hints from an XML data source and a list of location hints.
    If an accessible schema location is not found raises a ValueError.

    :param source: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or a URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param locations: a dictionary or dictionary items with additional schema location hints.
    :param base_url: the same argument of the :class:`XMLResource`.
    :param allow: the same argument of the :class:`XMLResource`, \
    applied to location hints only.
    :param defuse: the same argument of the :class:`XMLResource`.
    :param timeout: the same argument of the :class:`XMLResource` but with a reduced default.
    :param root_only: if `True` extracts from the XML source only the location hints \
    of the root element.
    :return: A 2-tuple with the URL referring to the first reachable schema resource \
    and a list of dictionary items with normalized location hints.
    """
    if not isinstance(source, XMLResource):
        resource = XMLResource(source, base_url, defuse=defuse, timeout=timeout, lazy=True)
    else:
        resource = source

    locations = resource.get_locations(locations, root_only=root_only)
    if not locations:
        raise XMLSchemaValueError("provided arguments don't contain any schema location hint")

    namespace = resource.namespace
    for ns, location in sorted(locations, key=lambda x: x[0] != namespace):
        try:
            resource = XMLResource(location, base_url, allow, defuse, timeout, lazy=True)
        except (XMLResourceError, URLError, ElementTree.ParseError):
            continue

        if resource.namespace == XSD_NAMESPACE and resource.url:
            return resource.url, locations
    else:
        raise XMLSchemaValueError("not found a schema for provided XML source")


def fetch_schema(source: Union['XMLResource', XMLSourceType],
                 locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 30,
                 root_only: bool = True) -> str:
    """
    Like :meth:`fetch_schema_locations` but returns only the URL of a loadable XSD
    schema from location hints fetched from the source or provided by argument.
    """
    return fetch_schema_locations(source, locations, base_url, allow,
                                  defuse, timeout, root_only)[0]


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

    :param source: a string containing the XML document or file path or a URL or a \
    file like object or an ElementTree or an Element.
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the resource can't be obtained from the source argument. For security \
    access to a local file resource is always denied if the *base_url* is a remote URL.
    :param allow: defines the security mode for accessing resource locations. Can be \
    'all', 'remote', 'local', 'sandbox' or 'none'. Default is 'all' that means all types of \
    URLs are allowed. With 'remote' only remote resource URLs are allowed. With 'local' \
    only file paths and URLs are allowed. With 'sandbox' only file paths and URLs that \
    are under the directory path identified by the *base_url* argument are allowed. \
    If you provide 'none' no located resource is allowed.
    :param defuse: defines when to defuse XML data using a `SafeXMLParser`. Can be \
    'always', 'remote', 'nonlocal' or 'never'. For default defuses only remote XML data. \
    With 'always' all the XML data that is not already parsed is defused. With 'nonlocal' \
    it defuses unparsed data except local files. With 'never' no XML data source is defused.
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
    _xpath_root: Union[None, ElementNode, DocumentNode] = None
    _nsmaps: Dict[ElementType, Dict[str, str]]
    _ns_declarations: Dict[ElementType, List[Tuple[str, str]]]
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

        if isinstance(base_url, (str, bytes)):
            if not is_url(base_url):
                raise XMLSchemaValueError("'base_url' argument is not an URL")
            self._base_url = base_url if isinstance(base_url, str) else base_url.decode()
        elif isinstance(base_url, Path):
            self._base_url = str(base_url)
        elif base_url is not None:
            msg = "invalid type %r for argument 'base_url'"
            raise XMLSchemaTypeError(msg % type(base_url))

        if not isinstance(allow, str):
            msg = "invalid type %r for argument 'allow'"
            raise XMLSchemaTypeError(msg % type(allow))
        elif allow not in SECURITY_MODES:
            msg = "'allow' argument: %r is not a security mode"
            raise XMLSchemaValueError(msg % allow)
        elif allow == 'sandbox' and self._base_url is None:
            msg = "block access to files out of sandbox requires 'base_url' to be set"
            raise XMLResourceError(msg)
        self._allow = allow

        if not isinstance(defuse, str):
            msg = "invalid type %r for argument 'defuse'"
            raise XMLSchemaTypeError(msg % type(defuse))
        elif defuse not in DEFUSE_MODES:
            msg = "'defuse' argument: %r is not a defuse mode"
            raise XMLSchemaValueError(msg % defuse)
        self._defuse = defuse

        if not isinstance(timeout, int):
            msg = "invalid type %r for argument 'timeout'"
            raise XMLSchemaTypeError(msg % type(timeout))
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
                return str(LocationPath.from_uri(self._url))
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
        elif self._allow == 'none':
            raise XMLResourceError(f"block access to resource {url}")
        elif self._allow == 'remote':
            if is_local_url(url):
                raise XMLResourceError(f"block access to local resource {url}")
        elif is_remote_url(url):
            raise XMLResourceError(f"block access to remote resource {url}")
        elif self._allow == 'sandbox' and self._base_url is not None:
            if not url.startswith(normalize_url(self._base_url)):
                raise XMLResourceError(f"block access to out of sandbox file {url}")

    def _track_nsmap(self, elements: Iterator[ElementType],
                     nsmap: NamespacesType) -> Iterator[ElementType]:
        initial_nsmap = {k: v for k, v in nsmap.items()}
        elem_nsmap = None
        root_namespace = self.namespace

        for elem in elements:
            try:
                if elem_nsmap is not self._nsmaps[elem]:
                    elem_nsmap = self._nsmaps[elem]
                    nsmap.clear()
                    nsmap.update(initial_nsmap)
                    update_namespaces(nsmap, elem_nsmap.items(), root_namespace)
            except KeyError:
                pass

            yield elem

    def _lazy_iterparse(self, resource: IO[AnyStr], nsmap: Optional[NamespacesType] = None) \
            -> Iterator[Tuple[str, ElementType]]:
        events: Tuple[str, ...]

        events = 'start-ns', 'end-ns', 'start', 'end'
        if self._defuse == 'remote' and is_remote_url(self.base_url) \
                or self._defuse == 'nonlocal' and not is_local_url(self.base_url) \
                or self._defuse == 'always':
            safe_parser = SafeXMLParser(target=PyElementTree.TreeBuilder())
            tree_iterator = PyElementTree.iterparse(resource, events, safe_parser)
        else:
            tree_iterator = ElementTree.iterparse(resource, events)

        root_started = False
        start_ns: List[Tuple[str, str]] = []
        end_ns = False
        nsmap_stack: List[Dict[str, str]] = [{}]

        # Save previous status (if any)
        _root: Optional[ElementType]
        _nsmaps: Optional[Dict[ElementType, Dict[str, str]]]
        _ns_declarations: Optional[Dict[ElementType, List[Tuple[str, str]]]]
        if hasattr(self, '_root'):
            _root = self._root
            _nsmaps = self._nsmaps
            _ns_declarations = self._ns_declarations
            _xpath_root = self._xpath_root
        else:
            _root = _nsmaps = _ns_declarations = _xpath_root = None

        self._nsmaps = {}
        self._ns_declarations = {}

        try:
            for event, node in tree_iterator:
                if event == 'start':
                    if not root_started:
                        self._root = node
                        self._nsmaps[node] = {k: v for k, v in start_ns}
                        self._xpath_root = LazyElementNode(
                            self._root, nsmap=self._nsmaps[node]
                        )
                        root_started = True

                    if end_ns:
                        nsmap_stack.pop()
                        end_ns = False
                        if nsmap is not None:
                            nsmap.clear()
                            nsmap.update(nsmap_stack[-1])

                    if start_ns:
                        nsmap_stack.append(nsmap_stack[-1].copy())
                        nsmap_stack[-1].update(start_ns)
                        self._ns_declarations[node] = start_ns
                        start_ns = []
                        if nsmap is not None:
                            nsmap.clear()
                            nsmap.update(nsmap_stack[-1])

                    yield event, node

                elif event == 'end':
                    if end_ns:
                        nsmap_stack.pop()
                        end_ns = False
                        if nsmap is not None:
                            nsmap.clear()
                            nsmap.update(nsmap_stack[-1])

                    yield event, node

                elif event == 'start-ns':
                    start_ns.append(node)
                else:
                    end_ns = True

        except Exception as err:
            if _root is not None \
                    and _nsmaps is not None \
                    and _ns_declarations is not None:
                self._root = _root
                self._nsmaps = _nsmaps
                self._ns_declarations = _ns_declarations
                self._xpath_root = _xpath_root
            if isinstance(err, PyElementTree.ParseError):
                raise ElementTree.ParseError(str(err)) from None
            raise

    def _parse(self, resource: IO[AnyStr]) -> None:
        if self._defuse == 'remote' and is_remote_url(self.base_url) \
                or self._defuse == 'nonlocal' and not is_local_url(self.base_url) \
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

        root: Optional[ElementType] = None
        start_ns: List[Tuple[str, str]] = []
        end_ns = False
        nsmaps: Dict[ElementType, Dict[str, str]] = {}
        ns_declarations: Dict[ElementType, List[Tuple[str, str]]] = {}
        events = 'start-ns', 'end-ns', 'start'
        nsmap_stack: List[Dict[str, str]] = [{}]

        for event, node in ElementTree.iterparse(resource, events):
            if event == 'start':
                if root is None:
                    root = node
                if end_ns:
                    nsmap_stack.pop()
                    end_ns = False
                if start_ns:
                    nsmap_stack.append(nsmap_stack[-1].copy())
                    nsmap_stack[-1].update(start_ns)
                    ns_declarations[node] = start_ns
                    start_ns = []
                nsmaps[node] = nsmap_stack[-1]
            elif event == 'start-ns':
                start_ns.append(node)
            else:
                end_ns = True

        assert root is not None
        self._root = root
        self._xpath_root = None
        self._nsmaps = nsmaps
        self._ns_declarations = ns_declarations

    def _parse_resource(self, resource: IO[AnyStr],
                        url: Optional[str],
                        lazy: Union[bool, int]) -> None:
        _url, self._url = self._url, url
        try:
            if not lazy:
                self._parse(resource)
            else:
                for _, root in self._lazy_iterparse(resource):  # pragma: no cover
                    break
        except Exception:
            self._url = _url
            raise

    def parse(self, source: XMLSourceType, lazy: Union[bool, int] = False) -> None:
        if isinstance(lazy, bool):
            pass
        elif not isinstance(lazy, int):
            msg = "invalid type %r for the attribute 'lazy'"
            raise XMLSchemaTypeError(msg % type(lazy))
        elif lazy < 0:
            msg = "invalid value %r for the attribute 'lazy'"
            raise XMLSchemaValueError(msg % lazy)

        url: Optional[str]
        if isinstance(source, str):
            if is_url(source):
                # source is a string containing a URL or a file path
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
                self._access_control(url)

                # Save remote urls for open new resources (non seekable)
                if not is_remote_url(url):
                    url = None

            self._parse_resource(cast(IO[str], source), url, lazy)
            self._text = None
            self._lazy = lazy

        else:
            # source is an Element or an ElementTree
            if hasattr(source, 'tag') and hasattr(source, 'attrib'):
                # Source is already an Element --> nothing to parse
                self._root = cast(ElementType, source)
            elif is_etree_document(source):
                # Could be only an ElementTree object at last
                self._root = source.getroot()
            else:
                raise XMLSchemaTypeError(
                    "wrong type %r for 'source' attribute: an ElementTree object or "
                    "an Element instance or a string containing XML data or an URL "
                    "or a file-like object is required." % type(source)
                )

            self._xpath_root = None
            self._text = self._url = None
            self._lazy = False
            self._nsmaps = {}
            self._ns_declarations = {}

            # TODO for Python 3.8+: need a Protocol for checking this with isinstance()
            if hasattr(self._root, 'xpath'):
                nsmap = {}
                lxml_nsmap = None
                for elem in cast(Any, self._root.iter()):
                    if lxml_nsmap != elem.nsmap:
                        nsmap = {k or '': v for k, v in elem.nsmap.items()}

                        if lxml_nsmap is None:
                            ns_declarations = [(k, v) for k, v in nsmap.items()]
                        else:
                            ns_declarations = [(k or '', v) for k, v in elem.nsmap.items()
                                               if k not in lxml_nsmap or v != lxml_nsmap[k]]
                        if ns_declarations:
                            self._ns_declarations[elem] = ns_declarations

                        lxml_nsmap = elem.nsmap

                    self._nsmaps[elem] = nsmap

        self._parent_map = None
        self._source = source

    @property
    def namespace(self) -> str:
        """The namespace of the XML resource."""
        return get_namespace(self._root.tag)

    @property
    def parent_map(self) -> Dict[ElementType, Optional[ElementType]]:
        if self._lazy:
            raise XMLResourceError("cannot create the parent map of a lazy XML resource")
        if self._parent_map is None:
            self._parent_map = {child: elem for elem in self._root.iter() for child in elem}
            self._parent_map[self._root] = None
        return self._parent_map

    @property
    def xpath_root(self) -> Union[ElementNode, DocumentNode]:
        """The XPath root node."""
        if self._xpath_root is None:
            if hasattr(self._root, 'xpath'):
                self._xpath_root = build_lxml_node_tree(cast(LxmlElementProtocol, self._root))
            else:
                try:
                    _nsmap = self._nsmaps[self._root]
                except KeyError:
                    # A resource based on an ElementTree structure (no namespace maps)
                    self._xpath_root = build_node_tree(self._root)
                else:
                    node_tree = build_node_tree(self._root, _nsmap)

                    # Update namespace maps
                    for node in node_tree.iter_descendants(with_self=False):
                        if isinstance(node, ElementNode):
                            nsmap = self._nsmaps[cast(ElementType, node.elem)]
                            node.nsmap = {k or '': v for k, v in nsmap.items()}

                    self._xpath_root = node_tree

        return self._xpath_root

    def get_xpath_node(self, elem: ElementType) -> ElementNode:
        """
        Returns an XPath node for the element, fetching it from the XPath root node.
        Returns a new lazy element node if the matching element node is not found.
        """
        xpath_node = self.xpath_root.get_element_node(elem)
        if xpath_node is not None:
            return xpath_node

        try:
            return LazyElementNode(elem, nsmap=self._nsmaps[elem])
        except KeyError:
            return LazyElementNode(elem)

    def get_nsmap(self, elem: ElementType) -> Optional[Dict[str, str]]:
        """
        Returns the namespace map (nsmap) of the element. Returns `None` if no nsmap is
        found for the element. Lazy resources have only the nsmap for the root element.
        """
        return self._nsmaps.get(elem)

    def get_ns_declarations(self, elem: ElementType) -> Optional[List[Tuple[str, str]]]:
        """
        Returns the list of namespaces declarations (xmlns and xmlns:<prefix> attributes)
        of the element. Returns `None` if the element doesn't have namespace declarations.
        Lazy resources have only the namespace declarations for the root element.
        """
        return self._ns_declarations.get(elem)

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

    def tostring(self, namespaces: Optional[MutableMapping[str, str]] = None,
                 indent: str = '', max_lines: Optional[int] = None,
                 spaces_for_tab: int = 4, xml_declaration: bool = False,
                 encoding: str = 'unicode', method: str = 'xml') -> str:
        """
        Serialize an XML resource to a string.

        :param namespaces: is an optional mapping from namespace prefix to URI. \
        Provided namespaces are registered before serialization. Ignored if the \
        provided *elem* argument is a lxml Element instance.
        :param indent: the base line indentation.
        :param max_lines: if truncate serialization after a number of lines \
        (default: do not truncate).
        :param spaces_for_tab: number of spaces for replacing tab characters. For \
        default tabs are replaced with 4 spaces, provide `None` to keep tab characters.
        :param xml_declaration: if set to `True` inserts the XML declaration at the head.
        :param encoding: if "unicode" (the default) the output is a string, \
        otherwise it’s binary.
        :param method: is either "xml" (the default), "html" or "text".
        :return: a Unicode string.
        """
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy XML resource")

        if not hasattr(self._root, 'nsmap'):
            namespaces = self.get_namespaces(namespaces, root_only=False)

        _string = etree_tostring(
            elem=self._root,
            namespaces=namespaces,
            indent=indent,
            max_lines=max_lines,
            spaces_for_tab=spaces_for_tab,
            xml_declaration=xml_declaration,
            encoding=encoding,
            method=method
        )
        if isinstance(_string, bytes):  # pragma: no cover
            return _string.decode('utf-8')
        return _string

    def subresource(self, elem: ElementType) -> 'XMLResource':
        """Create an XMLResource instance from a subelement of a non-lazy XML tree."""
        if self._lazy:
            raise XMLResourceError("cannot create a subresource from a lazy XML resource")

        for e in self._root.iter():  # pragma: no cover
            if e is elem:
                break
        else:
            msg = "{!r} is not an element or the XML resource tree"
            raise XMLResourceError(msg.format(elem))

        resource = XMLResource(elem, self.base_url, self._allow, self._defuse, self._timeout)
        if not hasattr(elem, 'nsmap'):
            for e in elem.iter():
                resource._nsmaps[e] = self._nsmaps[e]

                if e is elem:
                    ns_declarations = [(k, v) for k, v in self._nsmaps[e].items()]
                    if ns_declarations:
                        resource._ns_declarations[e] = ns_declarations
                elif e in self._ns_declarations:
                    resource._ns_declarations[e] = self._ns_declarations[e]

        return resource

    def open(self) -> IO[AnyStr]:
        """
        Returns an opened resource reader object for the instance URL. If the
        source attribute is a seekable file-like object rewind the source and
        return it.
        """
        if self.seek(0) == 0:
            return cast(IO[AnyStr], self._source)
        elif self._url is None:
            raise XMLResourceError(f"can't open, {self!r} has no URL associated")

        try:
            return cast(IO[AnyStr], urlopen(self._url, timeout=self._timeout))
        except URLError as err:
            msg = "cannot access to resource %(url)r: %(reason)s"
            raise XMLResourceError(msg % {'url': self._url, 'reason': err.reason})

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
            raise XMLResourceError("cannot load a lazy XML resource")

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

    def iter(self, tag: Optional[str] = None, nsmap: Optional[NamespacesType] = None,
             reversed_lazy: bool = True, thin_lazy: bool = False) -> Iterator[ElementType]:
        """
        XML resource tree iterator. If tag is not None or '*', only elements whose
        tag equals tag are returned from the iterator. Provide a *nsmap* dict for
        tracking the namespaces of yielded elements. For default the iteration of
        lazy resources is in reverse order (top level element is the last) for having
        fully build elements. Provide *reversed_lazy* as `False` for iterating lazy
        resources in forward order. In this case the returned elements are incomplete.
        Provide *thin_lazy* as `True` for iterating the lazy resource in forward order
        and removing the preceding elements during iteration. This option has the
        precedence over *reversed_lazy* option.
        """
        if self._lazy:
            resource = self.open()
            tag = '*' if tag is None else tag.strip()
            try:
                if thin_lazy:
                    ancestors = []
                    for event, node in self._lazy_iterparse(resource, nsmap):
                        if event == 'start':
                            if tag == '*' or node.tag == tag:
                                yield node
                            ancestors.append(node)
                        else:
                            ancestors.pop()
                            etree_delete_preceding(node, ancestors)
                            node.clear()

                elif reversed_lazy:
                    for event, node in self._lazy_iterparse(resource, nsmap):
                        if event == 'end':
                            if tag == '*' or node.tag == tag:
                                yield node
                            node.clear()
                else:
                    for event, node in self._lazy_iterparse(resource, nsmap):
                        if event == 'start':
                            if tag == '*' or node.tag == tag:
                                yield node
                        else:
                            node.clear()
            finally:
                # Close the resource only if it was originally opened by XMLResource
                if resource is not self._source:
                    resource.close()

        elif not self._nsmaps or nsmap is None:
            yield from self._root.iter(tag)
        else:
            yield from self._track_nsmap(self._root.iter(tag), nsmap)

    def iter_location_hints(self, tag: Optional[str] = None) -> Iterator[Tuple[str, str]]:
        """
        Yields all schema location hints of the XML resource. If tag
        is not None or '*', only location hints of elements whose tag
        equals tag are returned from the iterator.
        """
        for elem in self.iter(tag):
            yield from etree_iter_location_hints(elem)

    def iter_depth(self, mode: int = 1, nsmap: Optional[NamespacesType] = None,
                   ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        """
        Iterates XML subtrees. For fully loaded resources yields the root element.
        On lazy resources the argument *mode* can change the sequence and the
        completeness of yielded elements. There are four possible modes, that
        generate different sequences of elements:\n
          1. Only the elements at *depth_level* level of the tree\n
          2. Only the elements at *depth_level* level of the tree removing\n
             the preceding elements of ancestors (thin lazy tree)
          3. Only a root element pruned at *depth_level*\n
          4. The elements at *depth_level* and then a pruned root\n
          5. An incomplete root at start, the elements at *depth_level* and a pruned root\n

        :param mode: an integer in range [1..5] that defines the iteration mode.
        :param nsmap: provide a dict for tracking the namespaces of yielded elements.
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        """
        if ancestors is not None:
            ancestors.clear()
        elif mode <= 2:
            ancestors = []

        if not self._lazy:
            if nsmap is not None and self._nsmaps:
                root_namespace = self.namespace
                for elem in self._root.iter():
                    update_namespaces(nsmap, self._nsmaps[elem].items(), root_namespace)

            yield self._root
            return

        if mode not in (1, 2, 3, 4, 5):
            raise XMLSchemaValueError("invalid argument mode={!r}".format(mode))

        resource = self.open()
        level = 0
        subtree_level = int(self._lazy)

        # boolean flags
        incomplete_root = mode == 5
        pruned_root = mode > 2
        depth_level_elements = mode != 3
        thin_lazy = mode <= 2

        try:
            for event, node in self._lazy_iterparse(resource, nsmap):
                if event == "start":
                    if not level:
                        if incomplete_root:
                            yield node
                    if ancestors is not None and level < subtree_level:
                        ancestors.append(node)
                    level += 1
                else:
                    level -= 1
                    if not level:
                        if pruned_root:
                            yield node
                    elif level != subtree_level:
                        if ancestors is not None and level < subtree_level:
                            ancestors.pop()
                        continue  # pragma: no cover
                    elif depth_level_elements:
                        yield node

                        if thin_lazy and ancestors:
                            etree_delete_preceding(node, ancestors)

                    del node[:]  # delete children, keep attributes, text and tail.

                    # reset the whole XPath tree to let it still usable if other
                    # children are added to the root by ElementTree.iterparse().
                    self.xpath_root.children.clear()
        finally:
            if self._source is not resource:
                resource.close()

    def _select_elements(self, token: XPathToken,
                         node: ResourceNodeType,
                         ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        context = XPathContext(node)
        for item in token.select(context):
            if not isinstance(item, ElementNode):  # pragma: no cover
                msg = "XPath expressions on XML resources can select only elements"
                raise XMLResourceError(msg)
            elif ancestors is not None:
                if item.elem is self._root:
                    ancestors.clear()
                else:
                    _ancestors: Any = []
                    parent = item.parent
                    while parent is not None:
                        _ancestors.append(parent.value)
                        parent = parent.parent

                    if _ancestors:
                        ancestors.clear()
                        ancestors.extend(reversed(_ancestors))

            yield cast(ElementType, item.elem)

    def iterfind(self, path: str,
                 namespaces: Optional[NamespacesType] = None,
                 nsmap: Optional[NamespacesType] = None,
                 ancestors: Optional[List[ElementType]] = None,
                 thin_lazy: bool = False) -> Iterator[ElementType]:
        """
        Apply XPath selection to XML resource that yields full subtrees.

        :param path: an XPath 2.0 expression that selects element nodes. \
        Selecting other values or nodes raise an error.
        :param namespaces: an optional mapping from namespace prefixes to URIs \
        used for parsing the XPath expression.
        :param nsmap: provide a dict for tracking the namespaces of yielded elements.
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        :param thin_lazy: provide *thin_lazy* as `True` for removing the preceding \
        elements after each yielded one.
        """
        parser = XPath2Parser(namespaces, strict=False)
        token = parser.parse(path)
        selector: Any

        if self._lazy:
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

            if ancestors is not None:
                ancestors.clear()
            elif thin_lazy:
                ancestors = []

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
                            elif select_all or \
                                    node in self._select_elements(token, self.xpath_root):
                                yield node
                        elif not subtree_level:
                            continue
                        elif level != subtree_level:
                            if ancestors and level < subtree_level:
                                ancestors.pop()
                            continue  # pragma: no cover
                        elif select_all or \
                                node in self._select_elements(token, self.xpath_root):
                            yield node

                        if thin_lazy and ancestors:
                            etree_delete_preceding(node, ancestors)

                        del node[:]  # delete children, keep attributes, text and tail.
                        self.xpath_root.children.clear()  # reset XPath tree

            finally:
                if self._source is not resource:
                    resource.close()

        else:
            selector = self._select_elements(token, self.xpath_root, ancestors)

            if not self._nsmaps or nsmap is None:
                yield from selector
            else:
                yield from self._track_nsmap(selector, nsmap)

    def find(self, path: str,
             namespaces: Optional[NamespacesType] = None,
             nsmap: Optional[NamespacesType] = None,
             ancestors: Optional[List[ElementType]] = None,
             thin_lazy: bool = False) -> Optional[ElementType]:
        return next(self.iterfind(path, namespaces, nsmap, ancestors, thin_lazy), None)

    def findall(self, path: str, namespaces: Optional[NamespacesType] = None) \
            -> List[ElementType]:
        return list(self.iterfind(path, namespaces))

    def get_namespaces(self, namespaces: Optional[NamespacesType] = None,
                       root_only: bool = True) -> NamespacesType:
        """
        Extracts namespaces with related prefixes from the XML resource.

        :param namespaces: builds the namespace map starting over the dictionary provided.
        :param root_only: if `True` extracts only the namespaces declared in the root \
        element, otherwise if a duplicate prefix declaration is encountered and the \
        prefix maps to a different namespace, adds the namespace using a different \
        generated prefix. The empty prefix '' is used only if it's declared at root \
        level to avoid erroneous mapping of local names. In other cases it uses the \
        prefix 'default' as substitute. A full namespace map can be useful for cases \
        where the element context is not available.
        :return: a dictionary for mapping namespace prefixes to full URI.
        """
        if namespaces is None:
            namespaces = {}
        elif namespaces.get('xml', XML_NAMESPACE) != XML_NAMESPACE:
            msg = "reserved prefix 'xml' can't be used for another namespace name"
            raise XMLSchemaValueError(msg)
        else:
            namespaces = copy.copy(namespaces)

        root_namespace = self.namespace
        try:
            for elem in self.iter(reversed_lazy=False):
                if elem in self._ns_declarations:
                    update_namespaces(namespaces, self._ns_declarations[elem], root_namespace)
                if root_only:
                    break
        except (ElementTree.ParseError, PyElementTree.ParseError, UnicodeEncodeError):
            pass

        return namespaces

    def get_locations(self, locations: Optional[LocationsType] = None,
                      root_only: bool = True) -> NormalizedLocationsType:
        """
        Extracts a list of schema location hints from the XML resource.
        The locations are normalized using the base URL of the instance.

        :param locations: a sequence of schema location hints inserted \
        before the ones extracted from the XML resource. Locations passed \
        within a tuple container are not normalized.
        :param root_only: if `True` extracts only the location hints of the \
        root element.
        :returns: a list of couples containing normalized location hints.
        """
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
