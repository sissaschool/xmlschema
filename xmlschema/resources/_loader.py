﻿#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from itertools import zip_longest
from typing import cast, Any, Dict, Optional, Iterator, List, Union, Tuple

from elementpath import ElementNode, LazyElementNode, DocumentNode, \
    build_lxml_node_tree, build_node_tree
from elementpath.protocols import LxmlElementProtocol

from xmlschema.aliases import ElementType, ElementTreeType, \
    EtreeType, IOType, IterparseType, ParentMapType
from xmlschema.utils.qnames import get_namespace

from .exceptions import XMLResourceError, XMLResourceParseError
from ._arguments import LazyArgument, ThinLazyArgument, IterparseArgument


class _ResourceLoader:
    """
    A proxy for XML data loading that can handle full or lazy loads of XML trees.
    """
    # Descriptor-based attributes for arguments
    lazy = LazyArgument()
    thin_lazy = ThinLazyArgument()
    iterparse = IterparseArgument()

    # Private attributes for arguments
    _lazy: Union[bool, int]
    _thin_lazy: bool
    _iterparse: IterparseType

    # Protected attributes for XML data
    _xpath_root: Union[None, ElementNode, DocumentNode]
    _nsmaps: Dict[ElementType, Dict[str, str]]
    _xmlns: Dict[ElementType, List[Tuple[str, str]]]
    _parent_map: Optional[ParentMapType]

    root: ElementType
    """The XML tree root Element."""

    __slots__ = ('root', '_nsmaps', '_xmlns', '_lazy', '_thin_lazy', '_iterparse',
                 '_xpath_root', '_parent_map', '__dict__')

    def __init__(self, source: Union[IOType, EtreeType],
                 lazy: Union[bool, int] = False,
                 thin_lazy: bool = True,
                 iterparse: Optional[IterparseType] = None) -> None:

        self.lazy = lazy
        self.thin_lazy = thin_lazy
        self.iterparse = iterparse
        self._nsmaps = {}
        self._xmlns = {}
        self._xpath_root = None
        self._parent_map = None

        if hasattr(source, 'read'):
            fp = cast(IOType, source)
            if self._lazy:
                for _ in self._lazy_iterparse(fp):
                    break
            else:
                self._parse(fp)
        else:
            if hasattr(source, 'tag'):
                self.root = cast(ElementType, source)
            else:
                self.root = cast(ElementTreeType, source).getroot()

            if self._lazy:
                msg = f"a {self.__class__.__name__} created from an ElementTree can't be lazy"
                raise XMLResourceError(msg)
            if hasattr(self.root, 'nsmap') and hasattr(self.root, 'xpath'):
                self._parse_namespace_declarations()

    def __repr__(self) -> str:
        if not hasattr(self, 'root'):
            return '<%s object at %#x>' % (self.__class__.__name__, id(self))
        return '%s(root=%r)' % (self.__class__.__name__, self.root)

    @property
    def namespace(self) -> str:
        """The namespace of the XML resource."""
        return get_namespace(self.root.tag)

    @property
    def parent_map(self) -> Dict[ElementType, Optional[ElementType]]:
        if self._lazy:
            raise XMLResourceError("can't create the parent map of a lazy XML resource")
        if self._parent_map is None:
            self._parent_map = {child: elem for elem in self.root.iter() for child in elem}
            self._parent_map[self.root] = None
        return self._parent_map

    @property
    def xpath_root(self) -> Union[ElementNode, DocumentNode]:
        """The XPath root node."""
        if self._xpath_root is None:
            if self._lazy:
                self._xpath_root = LazyElementNode(self.root, nsmap=self._nsmaps[self.root])
            elif hasattr(self.root, 'xpath'):
                self._xpath_root = build_lxml_node_tree(cast(LxmlElementProtocol, self.root))
            else:
                try:
                    _nsmap = self._nsmaps[self.root]
                except KeyError:
                    # A resource based on an ElementTree structure (no namespace maps)
                    self._xpath_root = build_node_tree(self.root)
                else:
                    node_tree = build_node_tree(self.root, _nsmap)

                    # Update namespace maps
                    for node in node_tree.iter_descendants(with_self=False):
                        if isinstance(node, ElementNode):
                            nsmap = self._nsmaps[cast(ElementType, node.elem)]
                            node.nsmap = {k or '': v for k, v in nsmap.items()}

                    self._xpath_root = node_tree

        return self._xpath_root

    def clear(self, elem: ElementType) -> None:
        if elem not in self._nsmaps:
            del elem[:]
        else:
            self._clear(elem)

    def get_nsmap(self, elem: ElementType) -> Optional[Dict[str, str]]:
        """
        Returns the namespace map (nsmap) of the element. Returns `None` if no nsmap is
        found for the element. Lazy resources have only the nsmap for the root element.
        """
        try:
            return self._nsmaps[elem]
        except KeyError:
            return getattr(elem, 'nsmap', None)  # an lxml element

    def get_xmlns(self, elem: ElementType) -> Optional[List[Tuple[str, str]]]:
        """
        Returns the list of namespaces declarations (xmlns and xmlns:<prefix> attributes)
        of the element. Returns `None` if the element doesn't have namespace declarations.
        Lazy resources have only the namespace declarations for the root element.
        """
        return self._xmlns.get(elem)

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

    def get_absolute_path(self, path: Optional[str] = None) -> str:
        if path is None:
            if self._lazy:
                return f"/{self.root.tag}/{'/'.join('*' * int(self._lazy))}"
            return f'/{self.root.tag}'
        elif path.startswith('/'):
            return path
        else:
            return f'/{self.root.tag}/{path}'

    ##
    # Protected parsing and clearing methods

    def _lazy_iterparse(self, fp: IOType) -> Iterator[Tuple[str, ElementType]]:
        events: Tuple[str, ...]
        events = 'start-ns', 'end-ns', 'start', 'end'

        root_started = False
        start_ns: List[Tuple[str, str]] = []
        end_ns = False
        nsmap_stack: List[Dict[str, str]] = [{}]

        self._nsmaps.clear()
        self._xmlns.clear()

        try:
            for event, node in self._iterparse(fp, events):
                if event == 'start':
                    if end_ns:
                        nsmap_stack.pop()
                        end_ns = False

                    if start_ns:
                        nsmap_stack.append(nsmap_stack[-1].copy())
                        nsmap_stack[-1].update(start_ns)
                        self._xmlns[node] = start_ns
                        start_ns = []

                    self._nsmaps[node] = nsmap_stack[-1]
                    if not root_started:
                        self.root = node
                        self._xpath_root = LazyElementNode(
                            self.root, nsmap=self._nsmaps[node]
                        )
                        root_started = True

                    yield event, node

                elif event == 'end':
                    if end_ns:
                        nsmap_stack.pop()
                        end_ns = False

                    yield event, node

                elif event == 'start-ns':
                    start_ns.append(node)
                else:
                    end_ns = True
        except SyntaxError as err:
            raise XMLResourceParseError(str(err)) from err

    def _parse(self, fp: IOType) -> None:
        root_started = False
        start_ns: List[Tuple[str, str]] = []
        end_ns = False
        nsmaps = self._nsmaps
        xmlns = self._xmlns
        events = 'start-ns', 'end-ns', 'start'
        nsmap_stack: List[Dict[str, str]] = [{}]

        try:
            for event, node in self._iterparse(fp, events):
                if event == 'start':
                    if not root_started:
                        self.root = node
                        root_started = True
                    if end_ns:
                        nsmap_stack.pop()
                        end_ns = False
                    if start_ns:
                        nsmap_stack.append(nsmap_stack[-1].copy())
                        nsmap_stack[-1].update(start_ns)
                        xmlns[node] = start_ns
                        start_ns = []
                    nsmaps[node] = nsmap_stack[-1]
                elif event == 'start-ns':
                    start_ns.append(node)
                else:
                    end_ns = True
        except SyntaxError as err:
            raise XMLResourceParseError(str(err)) from err

    def _clear(self, elem: ElementType,
               ancestors: Optional[List[ElementType]] = None) -> None:

        if ancestors and self._thin_lazy:
            # Delete preceding elements
            for parent, child in zip_longest(ancestors, ancestors[1:]):
                if child is None:
                    child = elem

                for k, e in enumerate(parent):
                    if child is not e:
                        if e in self._xmlns:
                            del self._xmlns[e]
                        del self._nsmaps[e]
                    else:
                        if k:
                            del parent[:k]
                        break

        for e in elem.iter():
            if elem is not e:
                if e in self._xmlns:
                    del self._xmlns[e]
                del self._nsmaps[e]

        del elem[:]  # delete children, keep attributes, text and tail.

        # reset the whole XPath tree to let it still usable if other
        # children are added to the root by ElementTree.iterparse().
        if self._xpath_root is not None:
            self._xpath_root.children.clear()

    def _parse_namespace_declarations(self) -> None:
        nsmap = {}
        lxml_nsmap = None
        for elem in cast(Any, self.root.iter()):
            if callable(elem.tag):
                self._nsmaps[elem] = {}
                continue

            if lxml_nsmap != elem.nsmap:
                nsmap = {k or '': v for k, v in elem.nsmap.items()}
                lxml_nsmap = elem.nsmap

            parent = elem.getparent()
            if parent is None:
                xmlns = [(k or '', v) for k, v in nsmap.items()]
            elif parent.nsmap != elem.nsmap:
                xmlns = [(k or '', v) for k, v in elem.nsmap.items()
                         if k not in parent.nsmap or v != parent.nsmap[k]]
            else:
                xmlns = None

            self._nsmaps[elem] = nsmap
            if xmlns:
                self._xmlns[elem] = xmlns
