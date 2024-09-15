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
from urllib.parse import urlsplit, quote, quote_plus, unquote, unquote_plus, quote_from_bytes

from .exceptions import XMLSchemaValueError
from .aliases import NormalizedLocationsType, LocationsType


DRIVE_LETTERS = frozenset(string.ascii_letters)

URL_SCHEMES = frozenset(('file', 'http', 'https', 'ftp', 'sftp', 'rsync',
                         'svn', 'svn+ssh', 'nfs', 'git', 'git+ssh', 'ws', 'wss'))


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
        uri = uri.strip()
        if not uri:
            raise XMLSchemaValueError("Empty URI provided!")

        parts = urlsplit(uri)
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


def normalize_url(url: str, base_url: Optional[str] = None,
                  keep_relative: bool = False, method: str = 'xml') -> str:
    """
    Returns a normalized URL eventually joining it to a base URL if it's a relative path.
    Path names are converted to 'file' scheme URLs and unsafe characters are encoded.
    Query and fragments parts are kept only for non-local URLs

    :param url: a relative or absolute URL.
    :param base_url: a reference base URL.
    :param keep_relative: if set to `True` keeps relative file paths, which would \
    not strictly conformant to specification (RFC 8089), because *urlopen()* doesn't \
    accept a simple pathname.
    :param method: method used to encode query and fragment parts. If set to `html` \
    the whitespaces are replaced with `+` characters.
    :return: a normalized URL string.
    """
    url_parts = urlsplit(url.lstrip())
    if not is_local_scheme(url_parts.scheme):
        return encode_url(get_uri(*url_parts), method)

    path = LocationPath.from_uri(url)
    if path.is_absolute():
        return path.normalize().as_uri()

    if base_url is not None:
        base_url_parts = urlsplit(base_url.lstrip())
        base_path = LocationPath.from_uri(base_url)

        if is_local_scheme(base_url_parts.scheme):
            path = base_path.joinpath(path)
        elif not url_parts.scheme:
            url = get_uri(
                base_url_parts.scheme,
                base_url_parts.netloc,
                base_path.joinpath(path).normalize().as_posix(),
                url_parts.query,
                url_parts.fragment
            )
            return encode_url(url, method)

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


def is_encoded_url(url: str) -> bool:
    """
    Determines whether the given URL is encoded. The case with '+' and without
    spaces is not univocal and the plus signs are ignored for the result.
    """
    return unquote(url) != url or \
        '+' in url and ' ' not in url and \
        unquote(url.replace('+', '$')) != url.replace('+', '$')


def is_safe_url(url: str, method: str = 'xml') -> bool:
    """Determines whether the given URL is safe."""
    query_quote = quote_plus if method == 'html' else quote
    query_unquote = unquote_plus if method == 'html' else unquote

    parts = urlsplit(url.lstrip())
    path_safe = ':/\\' if is_local_scheme(parts.scheme) else '/'

    return parts.netloc == quote(unquote(parts.netloc), safe='@:') and \
        parts.path == quote(unquote(parts.path), safe=path_safe) and \
        parts.query == query_quote(query_unquote(parts.query), safe=';/?:@=&') and \
        parts.fragment == query_quote(query_unquote(parts.fragment), safe=';/?:@=&')


def encode_url(url: str, method: str = 'xml') -> str:
    """Encode the given url, if necessary."""
    if is_safe_url(url, method):
        return url
    elif is_encoded_url(url):
        url = decode_url(url, method)

    query_quote = quote_plus if method == 'html' else quote
    parts = urlsplit(url.lstrip())
    path_safe = ':/\\' if is_local_scheme(parts.scheme) else '/'

    return get_uri(
        parts.scheme,
        quote(parts.netloc, safe='@:'),
        quote(parts.path, safe=path_safe),
        query_quote(parts.query, safe=';/?:@=&'),
        query_quote(parts.fragment, safe=';/?:@=&'),
    )


def decode_url(url: str, method: str = 'xml') -> str:
    """Decode the given url, if necessary."""
    if not is_encoded_url(url):
        return url

    query_unquote = unquote_plus if method == 'html' else unquote

    parts = urlsplit(url)
    return get_uri(
        parts.scheme,
        unquote(parts.netloc),
        unquote(parts.path),
        query_unquote(parts.query),
        query_unquote(parts.fragment),
    )


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
