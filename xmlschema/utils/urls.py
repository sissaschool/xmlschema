#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from pathlib import Path
from string import ascii_letters
from urllib.parse import urlsplit, urlunsplit, quote, quote_plus, unquote, unquote_plus


def is_local_scheme(scheme: str) -> bool:
    return not scheme or scheme == 'file' or scheme in ascii_letters and len(scheme) == 1


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

    parts = urlsplit(url)
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
    parts = urlsplit(url)
    path_safe = ':/\\' if is_local_scheme(parts.scheme) else '/'

    return urlunsplit((
        parts.scheme,
        quote(parts.netloc, safe='@:'),
        quote(parts.path, safe=path_safe),
        query_quote(parts.query, safe=';/?:@=&'),
        query_quote(parts.fragment, safe=';/?:@=&'),
    ))


def decode_url(url: str, method: str = 'xml') -> str:
    """Decode the given url, if necessary."""
    if not is_encoded_url(url):
        return url

    query_unquote = unquote_plus if method == 'html' else unquote

    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        unquote(parts.netloc),
        unquote(parts.path),
        query_unquote(parts.query),
        query_unquote(parts.fragment),
    ))
