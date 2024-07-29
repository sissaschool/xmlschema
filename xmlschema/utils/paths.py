#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os.path
import ntpath
import posixpath
import string
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit, urlunsplit, unquote, quote_from_bytes

from xmlschema.exceptions import XMLSchemaValueError

DRIVE_LETTERS = frozenset(string.ascii_letters)


class LocationPath(PurePath):
    """
    A version of pathlib.PurePath with an enhanced URI conversion and for
    the normalization of location paths.

    A system independent path normalization without resolution is essential for
    processing resource locations, so the use or base class internals can be
    necessary for using pathlib. Despite the URL path has to be considered
    case-sensitive (ref. https://www.w3.org/TR/WD-html40-970708/htmlweb.html)
    this not always happen. On the other hand the initial source is often a
    filepath, so the better choice is to maintain location paths still related
    to the operating system.
    """
    _path_module = os.path

    def __new__(cls, *args: str) -> 'LocationPath':
        if cls is LocationPath:
            cls = LocationWindowsPath if os.name == 'nt' else LocationPosixPath
        return super().__new__(cls, *args)

    @classmethod
    def from_uri(cls, uri: str) -> 'LocationPath':
        """
        Parse a URI and return a LocationPath. For non-local schemes like 'http',
        'https', etc. a LocationPosixPath is returned. For Windows related file
        paths, like a path with a drive, a UNC path or a path containing a backslash,
        a LocationWindowsPath is returned.
        """
        uri = uri.strip()
        if not uri:
            raise XMLSchemaValueError("Empty URI provided!")

        parts = urlsplit(uri)
        if not parts.scheme or parts.scheme == 'file':
            path = urlunsplit(('', parts.netloc, parts.path, '', ''))
        elif parts.scheme in DRIVE_LETTERS and len(parts.scheme) == 1:
            # uri is a Windows path with a drive, e.g. k:/Python/lib/file

            # urlsplit() converts the scheme to lowercase so use uri[0]
            path = urlunsplit((uri[0], parts.netloc, parts.path, '', ''))

            return LocationWindowsPath(unquote(path))
        else:
            return LocationPosixPath(unquote(parts.path))

        if parts.scheme == 'file':
            path_start = path[:4].replace('\\', '/')
            if path_start.startswith(('////', '///')):
                pass
            elif path_start.startswith('/') and ntpath.splitdrive(path[1:])[0]:
                return LocationWindowsPath(unquote(path[1:]))
            elif path_start.startswith('//') and ntpath.splitdrive(path[2:])[0]:
                raise XMLSchemaValueError(f"Invalid URI {uri!r}")

        if ntpath.splitdrive(path)[0] or '\\' in path:
            return LocationWindowsPath(unquote(path))
        return cls(unquote(path))

    def as_uri(self) -> str:
        # Implementation that maps relative paths to not RFC 8089 compliant relative
        # file URIs because urlopen() doesn't accept simple paths. For UNC paths uses
        # the format with four slashes to let urlopen() works.

        drive = self.drive
        if len(drive) == 2 and drive[1] == ':':
            # A Windows path with a drive: 'c:\dir\file' => 'file:///c:/dir/file'
            prefix = 'file:///' + drive
            path = self.as_posix()[2:]
        elif drive:
            # UNC format case: '\\host\dir\file' => 'file:////host/dir/file'
            prefix = 'file://'
            path = self.as_posix()
        else:
            path = self.as_posix()
            if path.startswith('/'):
                # A Windows relative path or an absolute posix path:
                #  ('\dir\file' | '/dir/file') => 'file://dir/file'
                prefix = 'file://'
            else:
                # A relative posix path: 'dir/file' => 'file:dir/file'
                prefix = 'file:'

        return prefix + quote_from_bytes(os.fsencode(path))

    def normalize(self) -> 'LocationPath':
        normalized_path = self._path_module.normpath(str(self))
        return self.__class__(normalized_path)


class LocationPosixPath(LocationPath, PurePosixPath):
    _path_module = posixpath
    __slots__ = ()


class LocationWindowsPath(LocationPath, PureWindowsPath):
    _path_module = ntpath
    __slots__ = ()
