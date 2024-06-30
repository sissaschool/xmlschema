#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from types import TracebackType
from typing import AnyStr, IO, List, Optional, Protocol, Type


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
    def __enter__(self) -> 'IOProtocol[AnyStr]': ...
    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> None: ...


class FileWrapperProtocol(IOProtocol[AnyStr], Protocol[AnyStr]):
    file: IO[AnyStr]
    name: str
