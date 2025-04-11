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
import platform
import posixpath
import string
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit, unquote, quote_from_bytes

from xmlschema.exceptions import XMLSchemaValueError

DRIVE_LETTERS = frozenset(string.ascii_letters)


def get_uri_path(scheme: str = '', authority: str = '', path: str = '',
                 query: str = '', fragment: str = '') -> str:
    """
    Get the URI path from components, according to https://datatracker.ietf.org/doc/html/rfc3986.
    The returned path includes the authority.
    """
    if scheme == 'urn':
        if not path or authority or query or fragment:
            raise XMLSchemaValueError("An URN can have only scheme and path components")
        elif path.startswith(':') or path.endswith(':'):
            raise XMLSchemaValueError(f"Invalid URN path {path!r}")
        return path
    elif authority:
        if path and path[:1] != '/':
            return f'//{authority}/{path}'
        else:
            return f'//{authority}{path}'
    elif path[:2] == '//':
        return f'//{path}'  # UNC path
    elif scheme and scheme not in DRIVE_LETTERS and (not path or path[0] == '/'):
        return f'//{path}'
    else:
        return path


def get_uri(scheme: str = '', authority: str = '', path: str = '',
            query: str = '', fragment: str = '') -> str:
    """
    Get the URI from components, according to https://datatracker.ietf.org/doc/html/rfc3986.
    """
    if scheme == 'urn':
        return f'urn:{get_uri_path(scheme, authority, path, query, fragment)}'

    url = get_uri_path(scheme, authority, path, query, fragment)
    if scheme:
        url = scheme + ':' + url
    if query:
        url = url + '?' + query
    if fragment:
        url = url + '#' + fragment

    return url


def is_unc_path(path: str) -> bool:
    """
    Returns `True` if the provided path is a UNC path, `False` otherwise.
    Based on the capabilities of `PureWindowsPath` of the Python release.
    """
    return PureWindowsPath(path).drive.startswith('\\\\')


def is_drive_path(path: str) -> bool:
    """Returns `True` if the provided path starts with a drive (e.g. 'C:'), `False` otherwise."""
    drive = ntpath.splitdrive(path)[0]
    return len(drive) == 2 and drive[1] == ':' and drive[0] in DRIVE_LETTERS


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
        return super().__new__(cls, *args)  # type: ignore[arg-type, unused-ignore]

    @classmethod
    def from_uri(cls, uri: str) -> 'LocationPath':
        """
        Parse a URI and return a LocationPath. For non-local schemes like 'http',
        'https', etc. a LocationPosixPath is returned. For Windows related file
        paths, like a path with a drive, a UNC path or a path containing a backslash,
        a LocationWindowsPath is returned.
        """
        parts = urlsplit(uri.strip())
        if not parts.scheme or parts.scheme == 'file':
            path = get_uri_path(authority=parts.netloc, path=parts.path)

            # Detect invalid Windows paths (rooted or UNC path followed by a drive)
            for k in range(len(path)):
                if path[k] not in '/\\':
                    if not k or not is_drive_path(path[k:]):
                        break
                    elif k == 1 and parts.scheme == 'file':
                        # Valid case for a URL with a file scheme
                        return LocationWindowsPath(unquote(path[1:]))
                    else:
                        raise XMLSchemaValueError(f"Invalid URI {uri!r}")

            if '\\' in path or platform.system() == 'Windows':
                return LocationWindowsPath(unquote(path))
            elif ntpath.splitdrive(path)[0]:
                location_path = LocationWindowsPath(unquote(path))
                if location_path.drive:
                    # PureWindowsPath not detects a drive in Python 3.11.x also
                    # if it's detected by ntpath.splitdrive().
                    return location_path

            return LocationPosixPath(unquote(path))

        elif parts.scheme in DRIVE_LETTERS:
            # uri is a Windows path with a drive, e.g. k:/Python/lib/file

            # urlsplit() converts the scheme to lowercase so use uri[0]
            path = f'{uri[0]}:{get_uri_path(authority=parts.netloc, path=parts.path)}'
            return LocationWindowsPath(unquote(path))

        elif parts.scheme == 'urn':
            raise XMLSchemaValueError(f"Can't create a {cls!r} from an URN!")
        else:
            return LocationPosixPath(unquote(parts.path))

    def as_uri(self) -> str:
        # Implementation that maps relative paths to not RFC 8089 compliant relative
        # file URIs because urlopen() doesn't accept simple paths. For UNC paths uses
        # the format with four slashes to let urlopen() works.

        drive = self.drive
        if len(drive) == 2 and drive[1] == ':' and drive[0] in DRIVE_LETTERS:
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
