#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from pathlib import Path
from typing import Any, AnyStr, Callable, Dict, IO, Iterator, List, MutableMapping, \
    Optional, Protocol, Sequence, Union, Tuple
from xml.etree.ElementTree import Element, ElementTree

from elementpath.protocols import ElementProtocol, DocumentProtocol
from elementpath import ElementNode, LazyElementNode, DocumentNode


class IOProtocol(Protocol[AnyStr]):
    @property
    def closed(self) -> bool: ...
    def close(self) -> None: ...
    def flush(self) -> None: ...
    def isatty(self) -> bool: ...
    def read(self, n: int = ...) -> AnyStr: ...
    def readable(self) -> bool: ...
    def readline(self, limit: int = ...) -> AnyStr: ...
    def readlines(self, hint: int = ...) -> List[AnyStr]: ...
    def seek(self, offset: int, whence: int = ...) -> int: ...
    def seekable(self) -> bool: ...
    def tell(self) -> int: ...


class FileWrapperProtocol(IOProtocol[AnyStr], Protocol[AnyStr]):
    file: IO[AnyStr]
    name: str


SourceType = Union[str, bytes, Path, IO[str], IO[bytes]]
XMLSourceType = Union[SourceType, Element, ElementTree, ElementProtocol, DocumentProtocol]
ResourceType = Union[IOProtocol[str], IOProtocol[bytes]]
ResourceNodeType = Union[ElementNode, LazyElementNode, DocumentNode]
LazyType = Union[bool, int]
UriMapperType = Union[MutableMapping[str, str], Callable[[str], str]]
IterparseType = Callable[[ResourceType, Optional[Sequence[str]]], Iterator[tuple[str, Any]]]
NsmapType = MutableMapping[str, str]
XmlnsType = Optional[List[Tuple[str, str]]]
ParentMapType = Dict[Element, Optional[Element]]


__all__ = ['IOProtocol', 'FileWrapperProtocol', 'SourceType', 'XMLSourceType',
           'ResourceType', 'ResourceNodeType',  'LazyType', 'UriMapperType',
           'IterparseType', 'NsmapType', 'XmlnsType', 'ParentMapType']
