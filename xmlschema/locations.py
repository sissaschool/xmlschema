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
import platform
import string
from collections.abc import MutableMapping
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Optional, Iterable
from urllib.parse import urlsplit, urlunsplit, unquote, quote_from_bytes

from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.aliases import NormalizedLocationsType, LocationsType
from xmlschema.utils.urls import is_local_url, is_local_scheme, encode_url
from xmlschema.utils.paths import LocationPath


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
    url_parts = urlsplit(url)
    if not is_local_scheme(url_parts.scheme):
        return encode_url(url_parts.geturl(), method)

    path = LocationPath.from_uri(url)
    if path.is_absolute():
        return path.normalize().as_uri()

    if base_url is not None:
        base_url_parts = urlsplit(base_url)
        base_path = LocationPath.from_uri(base_url)

        if is_local_scheme(base_url_parts.scheme):
            path = base_path.joinpath(path)
        elif not url_parts.scheme:
            url = urlunsplit((
                base_url_parts.scheme,
                base_url_parts.netloc,
                base_path.joinpath(path).normalize().as_posix(),
                url_parts.query,
                url_parts.fragment
            ))
            return encode_url(url, method)

    if path.is_absolute() or keep_relative:
        return path.normalize().as_uri()

    base_path = LocationPath(os.getcwd())
    return base_path.joinpath(path).normalize().as_uri()


def location_is_file(url: str) -> bool:
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
