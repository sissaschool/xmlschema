﻿#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import io
import sys
import os.path
from collections import deque
from io import StringIO, BytesIO
from pathlib import Path
from typing import cast, Any, Optional, IO, Iterator, \
    List, MutableMapping, Union, Tuple
from urllib.request import urlopen, OpenerDirector
from urllib.parse import urlsplit, unquote
from urllib.error import URLError
from xml.etree import ElementTree

from elementpath import XPathToken, XPathContext, XPath2Parser, ElementNode

from xmlschema.aliases import ElementType, NsmapType, \
    NormalizedLocationsType, LocationsType, XMLSourceType, IOType, \
    ResourceNodeType, IterparseType, UriMapperType, EtreeType
from xmlschema.utils.paths import LocationPath
from xmlschema.utils.etree import etree_tostring, etree_iter_location_hints
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.qnames import update_namespaces, get_namespace_map
from xmlschema.utils.urls import is_url, is_remote_url, is_local_url
from xmlschema.locations import normalize_url, normalize_locations

from .exceptions import XMLResourceError, XMLResourceOSError, XMLResourceTypeError, \
    XMLResourceValueError, XMLResourceBlocked
from .sax import defuse_xml
from ._arguments import SourceArgument, BaseUrlArgument, AllowArgument, \
    DefuseArgument, TimeoutArgument, UriMapperArgument, OpenerArgument
from ._loader import _ResourceLoader

if sys.version_info < (3, 9):
    from typing import Deque
else:
    Deque = deque


class XMLResource(_ResourceLoader):
    """
    XML resource manager based on ElementTree and urllib.

    :param source: a string containing the XML document or file path or a URL or a \
    file like object or an ElementTree or an Element.
    :param base_url: is an optional base URL, used for the normalization of relative paths \
    when the URL of the resource can't be obtained from the source argument. For security \
    the access to a local file resource is always denied if the *base_url* is a remote URL.
    :param allow: defines the security mode for accessing resource locations. Can be \
    'all', 'remote', 'local', 'sandbox' or 'none'. Default is 'all', which means all types \
    of URLs are allowed. With 'remote' only remote resource URLs are allowed. With 'local' \
    only file paths and URLs are allowed. With 'sandbox' only file paths and URLs that \
    are under the directory path identified by the *base_url* argument are allowed. \
    If you provide 'none', no resources will be allowed from any location.
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
    :param thin_lazy: for default, in order to reduce the memory usage, during the \
    iteration of a lazy resource at *lazy_depth* level, deletes also the preceding \
    elements after the use.
    :param uri_mapper: an optional URI mapper for using relocated or URN-addressed \
    resources. Can be a dictionary or a function that takes the URI string and returns \
    a URL, or the argument if there is no mapping for it.
    """
    # Descriptor-based attributes for arguments
    source = SourceArgument()
    base_url = BaseUrlArgument()
    allow = AllowArgument()
    defuse = DefuseArgument()
    timeout = TimeoutArgument()
    uri_mapper = UriMapperArgument()
    opener = OpenerArgument()

    # Private attributes for arguments
    _source: XMLSourceType
    _base_url: Optional[str]
    _defuse: str
    _allow: str
    _timeout: int
    _uri_mapper: Optional[UriMapperType]
    _opener: Optional[OpenerDirector]

    text: Optional[str] = None
    """The XML text source, `None` if it's not loaded or available."""

    url: Optional[str] = None
    """An URL if the source is an URL or a file-like object with a remote url."""

    fp: Optional[IOType] = None
    """An file-like object if the source is a file-like object."""

    _context_fp: Optional[IOType] = None

    def __init__(self, source: XMLSourceType,
                 base_url: Union[None, str, Path, bytes] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 300,
                 lazy: Union[bool, int] = False,
                 thin_lazy: bool = True,
                 uri_mapper: Optional[UriMapperType] = None,
                 opener: Optional[OpenerDirector] = None,
                 iterparse: Optional[IterparseType] = None) -> None:

        if allow == 'sandbox' and base_url is None:
            msg = "block access to files out of sandbox requires 'base_url' to be set"
            raise XMLResourceValueError(msg)

        # Set and validate arguments
        self.base_url = base_url
        self.allow = allow
        self.defuse = defuse
        self.timeout = timeout
        self.uri_mapper = uri_mapper
        self.opener = opener
        self.source = source

        if is_url(source):
            assert isinstance(source, (str, bytes, Path))
            self.url = self.get_url(source)
            self.access_control(self.url)

        elif isinstance(source, str):
            self.text = source
        elif isinstance(source, bytes):
            self.text = source.decode()
        elif isinstance(source, StringIO):
            self.fp = cast(IO[str], source)
            self.text = source.getvalue()
        elif isinstance(source, BytesIO):
            self.fp = cast(IO[bytes], source)
        elif is_file_object(source):
            # source is a file-like object (remote resource or local file)
            self.fp = cast(IOType, source)
            self.access_control(getattr(source, 'url', None))
        else:
            super().__init__(cast(EtreeType, source), lazy, thin_lazy, iterparse)
            return

        with self as fp:
            super().__init__(fp, lazy, thin_lazy, iterparse)

    def __enter__(self) -> IOType:
        if self._context_fp is not None:
            raise XMLResourceError(f"resource {self!r} is already used in a context")

        self._context_fp = self.open()
        return self._context_fp

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._context_fp is not None:
            # Don't close a seekable file-like obj if it's the source of the instance.
            if self._context_fp is not self.fp or not self._context_fp.seekable():
                self._context_fp.close()
            self._context_fp = None

    @property
    def name(self) -> Optional[str]:
        """
        The source name, is `None` if the instance is created from an Element or a string.
        """
        return None if self.url is None else os.path.basename(unquote(self.url))

    @property
    def filepath(self) -> Optional[str]:
        """
        The resource filepath if the instance is created from a local file, `None` otherwise.
        """
        if self.url:
            url_parts = urlsplit(self.url)
            if url_parts.scheme in ('', 'file'):
                return str(LocationPath.from_uri(self.url))
        return None

    @property
    def lazy_depth(self) -> int:
        """
        The depth at which the XML tree of the resource is fully loaded during iterations
        methods. Is a positive integer for lazy resources and 0 for fully loaded XML trees.
        """
        return int(self._lazy)

    def is_lazy(self) -> bool:
        """Returns `True` if the XML resource is lazy."""
        return bool(self._lazy)

    def is_thin(self) -> bool:
        """Returns `True` if the XML resource is lazy and thin."""
        return bool(self._lazy) and self._thin_lazy

    def is_remote(self) -> bool:
        """Returns `True` if the resource is related with remote XML data."""
        return is_remote_url(self.url)

    def is_local(self) -> bool:
        """Returns `True` if the resource is related with local XML data."""
        return is_local_url(self.url)

    def is_data(self) -> bool:
        """Returns `True` if the instance source argument is a data object."""
        return not isinstance(self._source, (str, bytes, Path)) \
            and not hasattr(self._source, 'read')

    def is_loaded(self) -> bool:
        """Returns `True` if the XML text of the data source is loaded."""
        return self.text is not None

    def is_defused(self) -> bool:
        """Returns `True` if the XML data is defused before parsing."""
        return self._defuse == 'remote' and is_remote_url(self.base_url) \
            or self._defuse == 'nonlocal' and not is_local_url(self.base_url) \
            or self._defuse == 'always'

    def get_url(self, uri_or_path: Union[str, bytes, Path]) -> str:
        if isinstance(uri_or_path, str):
            uri = uri_or_path.strip()
        elif isinstance(uri_or_path, bytes):
            uri = uri_or_path.decode().strip()
        else:
            uri = str(uri_or_path)

        if isinstance(self._uri_mapper, MutableMapping):
            if uri in self._uri_mapper:
                uri = self._uri_mapper[uri]
        elif callable(self._uri_mapper):
            uri = self._uri_mapper(uri)

        return normalize_url(uri, self._base_url)

    def access_control(self, url: Optional[str]) -> None:
        if self._allow == 'all' or url is None:
            return
        elif self._allow == 'none':
            raise XMLResourceBlocked(f"block access to resource {url}")
        elif self._allow == 'remote':
            if is_local_url(url):
                raise XMLResourceBlocked(f"block access to local resource {url}")
        elif is_remote_url(url):
            raise XMLResourceBlocked(f"block access to remote resource {url}")
        elif self._allow == 'sandbox' and self._base_url is not None:
            if not url.startswith(normalize_url(self._base_url)):
                raise XMLResourceBlocked(f"block access to out of sandbox file {url}")

    def parse(self, source: XMLSourceType, lazy: Union[bool, int] = False) -> None:
        other = XMLResource(
            source,
            base_url=self._base_url,
            allow=self._allow,
            defuse=self._defuse,
            timeout=self._timeout,
            lazy=lazy,
            thin_lazy=self._thin_lazy,
            uri_mapper=self._uri_mapper,
        )
        self.__dict__ = other.__dict__
        del other

    def get_text(self) -> str:
        """
        Gets the source text of the XML document. If the source text is not
        available creates an encoded string representation of the XML tree.
        Il the resource is lazy raises a resource error.
        """
        if self.text is not None:
            return self.text
        elif self.url is not None:
            self.load()
            if self.text is not None:
                return self.text

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
        :param indent: the baseline indentation.
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
            raise XMLResourceError("can't serialize a lazy XML resource")

        if not hasattr(self.root, 'nsmap'):
            namespaces = self.get_namespaces(namespaces, root_only=False)

        _string = etree_tostring(
            elem=self.root,
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
            raise XMLResourceError("can't create a subresource from a lazy XML resource")

        for e in self.root.iter():  # pragma: no cover
            if e is elem:
                break
        else:
            msg = "{!r} is not an element or the XML resource tree"
            raise XMLResourceValueError(msg.format(elem))

        resource = XMLResource(elem, self.base_url, self._allow, self._defuse, self._timeout)
        if not hasattr(elem, 'nsmap'):
            for e in elem.iter():
                resource._nsmaps[e] = self._nsmaps[e]

                if e is elem:
                    ns_declarations = [(k, v) for k, v in self._nsmaps[e].items()]
                    if ns_declarations:
                        resource._xmlns[e] = ns_declarations
                elif e in self._xmlns:
                    resource._xmlns[e] = self._xmlns[e]

        return resource

    def open(self) -> IOType:
        """
        Returns an opened resource reader object for the instance URL. If the
        source attribute is a seekable file-like object rewind the source and
        return it. If required by configuration the XML resource is defused
        before returning if to the caller.
        """
        def open_url(url: str) -> IOType:
            try:
                if self._opener is not None:
                    return cast(IOType, self._opener.open(url, timeout=self._timeout))
                return cast(IOType, urlopen(url, timeout=self._timeout))
            except URLError as err:
                raise XMLResourceOSError(f"can't access to resource {url!r}: {err.reason}")

        if self.fp is not None:
            if self.fp.closed:
                msg = f"can't open {self!r}: its file-like object has been closed"
                raise XMLResourceOSError(msg)
            elif self.fp.seekable() and self.fp.seek(0) != 0:
                msg = f"can't open {self!r}: its file-like object can't be rewound"
                raise XMLResourceOSError(msg)
            else:
                fp = self.fp

        elif self.url is not None:
            fp = open_url(self.url)
        elif isinstance(self._source, str):
            fp = StringIO(self._source)
        elif isinstance(self._source, bytes):
            fp = BytesIO(self._source)
        else:
            msg = f"can't open {self!r}: its source is an ElementTree structure"
            raise XMLResourceError(msg)

        if self.is_defused():
            if fp.seekable() or isinstance(fp, (io.RawIOBase, io.BufferedIOBase)):
                return defuse_xml(fp)
            elif self.url is not None:
                # If the file-like object is created from a URL, create a new
                # file-like object for defusing XML data. This may not be as
                # safe as defusing a resource using buffered data.
                with open_url(self.url) as _fp:
                    defuse_xml(_fp, rewind=False)
            else:
                msg = f"can't defuse {self!r}: its file-like object is not seekable"
                raise XMLResourceOSError(msg)

        return fp

    def seek(self, position: int) -> Optional[int]:
        """
        Change stream position if the XML resource was created with a seekable
        file-like object. In the other cases this method has no effect.
        """
        return self.fp.seek(position) if self.fp is not None and self.fp.seekable() else None

    def close(self) -> None:
        """
        Close the XML resource if it's created with a file-like object.
        In other cases this method has no effect.
        """
        if self.fp is not None:
            self.fp.close()

    def load(self) -> None:
        """
        Loads the XML text from the data source. If the data source is an Element
        the source XML text can't be retrieved.
        """
        if self.url is None and not hasattr(self._source, 'read'):
            return  # Created from Element or text source --> already loaded
        elif self._lazy:
            raise XMLResourceError("can't load a lazy XML resource")

        with self as fp:
            data = fp.read()

        if isinstance(data, bytes):
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                text = data.decode('iso-8859-1')
        else:
            text = data

        self.text = text

    def iter(self, tag: Optional[str] = None) -> Iterator[ElementType]:
        """
        XML resource tree iterator. If tag is not None or '*', only elements whose
        tag equals tag are returned from the iterator. In a lazy resource the yielded
        elements are full over or at *lazy_depth* level, otherwise are incomplete and
        thin for default.
        """
        if not self._lazy:
            yield from self.root.iter(tag)
            return

        tag = '*' if tag is None else tag.strip()
        lazy_depth = int(self._lazy)
        subtree_elements: Deque[ElementType] = deque()
        ancestors = []
        level = 0

        with self as fp:
            for event, node in self._lazy_iterparse(fp):
                if event == "start":
                    if level < lazy_depth:
                        if level:
                            ancestors.append(node)
                        if tag == '*' or node.tag == tag:
                            yield node  # an incomplete element
                    level += 1
                else:
                    level -= 1
                    if level < lazy_depth:
                        if level:
                            ancestors.pop()
                        continue  # pragma: no cover
                    elif level > lazy_depth:
                        if tag == '*' or node.tag == tag:
                            subtree_elements.appendleft(node)
                        continue  # pragma: no cover

                    if tag == '*' or node.tag == tag:
                        yield node  # a full element

                    yield from subtree_elements
                    subtree_elements.clear()

                    self._clear(node, ancestors)

    def iter_location_hints(self, tag: Optional[str] = None) -> Iterator[Tuple[str, str]]:
        """
        Yields all schema location hints of the XML resource. If tag
        is not None or '*', only location hints of elements whose tag
        equals tag are returned from the iterator.
        """
        for elem in self.iter(tag):
            yield from etree_iter_location_hints(elem)

    def iter_depth(self, mode: int = 1, ancestors: Optional[List[ElementType]] = None) \
            -> Iterator[ElementType]:
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
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        """
        if mode not in (1, 2, 3, 4, 5):
            raise XMLResourceValueError(f"invalid argument mode={mode!r}")

        if ancestors is not None:
            ancestors.clear()
        elif mode <= 2:
            ancestors = []

        if not self._lazy:
            yield self.root
            return

        level = 0
        lazy_depth = int(self._lazy)

        # boolean flags
        incomplete_root = mode == 5
        pruned_root = mode > 2
        depth_level_elements = mode != 3
        thin_lazy = mode <= 2

        with self as fp:
            for event, elem in self._lazy_iterparse(fp):
                if event == "start":
                    if not level:
                        if incomplete_root:
                            yield elem
                    if ancestors is not None and level < lazy_depth:
                        ancestors.append(elem)
                    level += 1
                else:
                    level -= 1
                    if not level:
                        if pruned_root:
                            yield elem
                        continue
                    elif level != lazy_depth:
                        if ancestors is not None and level < lazy_depth:
                            ancestors.pop()
                        continue  # pragma: no cover
                    elif depth_level_elements:
                        yield elem

                    if thin_lazy:
                        self._clear(elem, ancestors)
                    else:
                        self._clear(elem)

                    if self._xpath_root is not None:
                        self.xpath_root.children.clear()

    def _select_elements(self, token: XPathToken,
                         node: ResourceNodeType,
                         ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        context = XPathContext(node)
        for item in token.select(context):
            if not isinstance(item, ElementNode):  # pragma: no cover
                msg = "XPath expressions on XML resources can select only elements"
                raise XMLResourceTypeError(msg)
            elif ancestors is not None:
                if item.elem is self.root:
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
                 namespaces: Optional[NsmapType] = None,
                 ancestors: Optional[List[ElementType]] = None) -> Iterator[ElementType]:
        """
        Apply XPath selection to XML resource that yields full subtrees.

        :param path: an XPath 2.0 expression that selects element nodes. \
        Selecting other values or nodes raise an error.
        :param namespaces: an optional mapping from namespace prefixes to URIs \
        used for parsing the XPath expression.
        :param ancestors: provide a list for tracking the ancestors of yielded elements.
        """
        parser = XPath2Parser(namespaces, strict=False)
        token = parser.parse(path)

        if not self._lazy:
            yield from self._select_elements(token, self.xpath_root, ancestors)
            return

        lazy_depth = int(self._lazy)
        level = 0

        path = path.replace(' ', '').replace('./', '')
        select_all = '*' in path and set(path).issubset(('*', '/'))
        if path == '.':
            path_depth = 0
        elif path.startswith('/'):
            path_depth = path.count('/') - 1
        else:
            path_depth = path.count('/') + 1

        if not path_depth:
            raise XMLResourceValueError(f"can't use path {path!r} on a lazy resource")
        elif path_depth < lazy_depth:
            raise XMLResourceValueError(f"can't use path {path!r} on a lazy resource "
                                        f"with lazy_depth=={lazy_depth}")

        if ancestors is not None:
            ancestors.clear()
        elif self._thin_lazy:
            ancestors = []

        with self as fp:
            for event, node in self._lazy_iterparse(fp):
                if event == "start":
                    if ancestors is not None and level < path_depth:
                        ancestors.append(node)
                    level += 1
                else:
                    level -= 1
                    if level < path_depth:
                        if ancestors is not None:
                            ancestors.pop()
                        continue
                    elif level == path_depth:
                        if select_all or \
                             node in self._select_elements(token, self.xpath_root):
                            yield node
                    if level == lazy_depth:
                        self._clear(node, ancestors)

    def find(self, path: str,
             namespaces: Optional[NsmapType] = None,
             ancestors: Optional[List[ElementType]] = None) -> Optional[ElementType]:
        return next(self.iterfind(path, namespaces, ancestors), None)

    def findall(self, path: str, namespaces: Optional[NsmapType] = None) \
            -> List[ElementType]:
        return list(self.iterfind(path, namespaces))

    def get_namespaces(self, namespaces: Optional[NsmapType] = None,
                       root_only: bool = True) -> NsmapType:
        """
        Extracts namespaces with related prefixes from the XML resource.
        If a duplicate prefix is encountered in a xmlns declaration, and
        this is mapped to a different namespace, adds the namespace using
        a different generated prefix. The empty prefix '' is used only if
        it's declared at root level to avoid erroneous mapping of local
        names. In other cases it uses the prefix 'default' as substitute.

        :param namespaces: is an optional mapping from namespace prefix to URI that \
        integrate/override the namespace declarations of the root element.
        :param root_only: if `True` extracts only the namespaces declared in the root \
        element, otherwise scan the whole tree for further namespace declarations. \
        A full namespace map can be useful for cases where the element context is \
        not available.

        :return: a dictionary for mapping namespace prefixes to full URI.
        """
        namespaces = get_namespace_map(namespaces)

        try:
            for elem in self.iter():
                if elem in self._xmlns:
                    update_namespaces(namespaces, self._xmlns[elem], elem is self.root)
                if root_only:
                    break
        except (ElementTree.ParseError, UnicodeEncodeError):
            return namespaces  # a lazy resource with malformed XML data
        else:
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
                for ns, url in etree_iter_location_hints(self.root)
            ])
        else:
            try:
                location_hints.extend([
                    (ns, normalize_url(url, self.base_url))
                    for ns, url in self.iter_location_hints()
                ])
            except (ElementTree.ParseError, UnicodeEncodeError):
                pass  # a lazy resource containing malformed XML data after the first tag

        return location_hints
