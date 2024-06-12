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
from typing import AnyStr, IO, List, Protocol, Union

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
XMLSourceType = Union[SourceType, ElementProtocol, DocumentProtocol]
ResourceType = Union[IOProtocol[str], IOProtocol[bytes]]
ResourceNodeType = Union[ElementNode, LazyElementNode, DocumentNode]
