#
# Copyright (c), 2016-2023, SISSA (International School for Advanced Studies).
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
import platform
import string
from collections.abc import MutableMapping
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Optional, Iterable
from urllib.parse import urlsplit, urlunsplit, unquote, quote_from_bytes

from .exceptions import XMLSchemaValueError
from .aliases import NormalizedLocationsType, LocationsType


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
        uri = uri.strip()
        if not uri:
            raise XMLSchemaValueError("Empty URI provided!")

        if uri.startswith(r'\\'):
            return LocationWindowsPath(uri)  # UNC path
        elif uri.startswith('/'):
            return cls(uri)

        parts = urlsplit(uri)
        if not parts.scheme:
            return cls(uri)
        elif parts.scheme in DRIVE_LETTERS and len(parts.scheme) == 1:
            return LocationWindowsPath(uri)  # Eg. k:/Python/lib/....
        elif parts.scheme != 'file':
            return LocationPosixPath(unquote(parts.path))

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
                return LocationWindowsPath(unquote(path[1:]))

            obj = LocationWindowsPath(unquote(path))
            if len(obj.drive) != 2 or obj.drive[1] != ':':
                raise XMLSchemaValueError("Invalid URI %r" % uri)
            return obj

        if '\\' in path:
            return LocationWindowsPath(unquote(path))
        return cls(unquote(path))

    def as_uri(self) -> str:
        if not self.is_absolute():
            # Converts relative paths to not RFC 8089 compliant relative
            # file URIs because urlopen() doesn't accept simple paths
            drive = self.drive
            if len(drive) == 2 and drive[1] == ':':
                prefix = 'file:' + drive
                path = self.as_posix()[2:]
            elif drive:
                prefix = 'file:'
                path = self.as_posix()
            else:
                prefix = 'file:'
                path = str(self)
            return prefix + quote_from_bytes(os.fsencode(path))

        uri = super().as_uri()
        if isinstance(self, LocationWindowsPath) and str(self).startswith(r'\\'):
            # UNC format case: use the format where the host part is included
            # in the path part, to let urlopen() works.
            if not uri.startswith('file:////'):
                return uri.replace('file://', 'file:////')
        return uri

    def normalize(self) -> 'LocationPath':
        normalized_path = self._path_module.normpath(str(self))
        return self.__class__(normalized_path)


class LocationPosixPath(LocationPath, PurePosixPath):
    _path_module = posixpath
    __slots__ = ()


class LocationWindowsPath(LocationPath, PureWindowsPath):
    _path_module = ntpath
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

    path = LocationPath.from_uri(url)
    if path.is_absolute():
        return path.normalize().as_uri()

    if base_url is not None:
        base_url_parts = urlsplit(base_url)
        base_path = LocationPath.from_uri(base_url)
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

    base_path = LocationPath(os.getcwd())
    return base_path.joinpath(path).normalize().as_uri()


def is_local_scheme(scheme: str) -> bool:
    return not scheme or scheme == 'file' or scheme in DRIVE_LETTERS


def is_url(obj: object) -> bool:
    """Returns `True` if the provided object is a URL, `False` otherwise."""
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
    else:
        return isinstance(obj, Path)

    try:
        urlsplit(obj.strip())  # type: ignore
    except ValueError:  # pragma: no cover
        return False
    else:
        return True


def is_remote_url(obj: object) -> bool:
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
        url = obj.strip()
    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
        url = obj.strip().decode('utf-8')
    else:
        return False

    try:
        return not is_local_scheme(urlsplit(url).scheme)
    except ValueError:  # pragma: no cover
        return False


def is_local_url(obj: object) -> bool:
    if isinstance(obj, str):
        if '\n' in obj or obj.lstrip().startswith('<'):
            return False
        url = obj.strip()
    elif isinstance(obj, bytes):
        if b'\n' in obj or obj.lstrip().startswith(b'<'):
            return False
        url = obj.strip().decode('utf-8')
    else:
        return isinstance(obj, Path)

    try:
        return is_local_scheme(urlsplit(url).scheme)
    except ValueError:  # pragma: no cover
        return False


def url_path_is_file(url: str) -> bool:
    if not is_local_url(url):
        return False
    if os.path.isfile(url):
        return True
    path = unquote(urlsplit(normalize_url(url)).path)
    if path.startswith('/') and platform.system() == 'Windows':
        path = path[1:]
    return os.path.isfile(path)


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
    if isinstance(locations, MutableMapping):
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


def match_location(url: str, locations: Iterable[str]) -> Optional[str]:
    """
    Match a URL against a group of locations. Give priority to exact matches,
    then to the match with the highest score after filtering out the locations
    that are not compatible with provided url. The score of a location path is
    determined by the number of path levels minus the number of parent steps.
    If no match is found returns `None`.
    """
    def is_compatible(loc: str) -> bool:
        parts = urlsplit(loc)
        return not parts.scheme or scheme == parts.scheme and netloc == parts.netloc

    if url in locations:
        return url

    scheme, netloc = urlsplit(url)[:2]
    path = LocationPath.from_uri(url).normalize()
    matching_url = None
    matching_score = None

    for other_url in filter(is_compatible, locations):
        other_path = LocationPath.from_uri(other_url).normalize()
        pattern = other_path.as_posix().replace('..', '*')

        if path.match(pattern):
            score = pattern.count('/') - pattern.count('*')
            if matching_score is None or matching_score < score:
                matching_score = score
                matching_url = other_url

    return matching_url
