# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains functions for manipulating fully qualified names.
"""
import re
from .core import XMLSchemaValueError

_RE_MATCH_NAMESPACE = re.compile(r'\{([^}]*)\}')
_RE_STRIP_NAMESPACE = re.compile(r'\{[^}]*\}')
_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*\})')


def get_qname(uri, name):
    """
    Return a fully qualified Name from URI and local part. If the URI is empty
    or None, or if the name is already in QName format, returns the 'name' argument.

    :param uri: namespace URI
    :param name: local name/tag
    :return: string
    """
    if uri and name[0] not in ('{', '.', '/', '['):
        return u"{%s}%s" % (uri, name)
    else:
        return name


def split_qname(qname):
    """
    Split a universal name format (QName) into URI and local part

    :param qname: QName or universal name formatted string.
    :return: A couple with URI and local parts. URI is None if there
    is only the local part.
    """
    if qname[0] == '{':
        try:
            return qname[1:].split('}')
        except ValueError:
            raise XMLSchemaValueError("wrong format for a universal name! '%s'" % qname)
    return None, qname


def split_reference(ref, namespaces):
    """
    Processes a reference name using namespaces information. A reference
    is a local name or a name with a namespace prefix (e.g. "xs:string").
    A couple with fully qualified name and the namespace is returned.
    If no namespace association is possible returns a local name and None
    when the reference is only a local name or raise a ValueError otherwise.

    :param ref: Reference or fully qualified name (QName).
    :param namespaces: Dictionary that maps the namespace prefix into URI.
    :return: A couple with qname and namespace.
    """
    if ref[0] == '{':
        return ref, ref[1:].split('}')[0] if ref[0] == '{' else ''

    try:
        prefix, tag = ref.split(":")
    except ValueError:
        try:
            uri = namespaces['']
        except KeyError:
            return ref, ''
        else:
            return u"{%s}%s" % (uri, ref) if uri else ref, uri
    else:
        try:
            uri = namespaces[prefix]
        except KeyError as err:
            raise XMLSchemaValueError("unknown namespace prefix %s for reference %r" % (err, ref))
        else:
            return u"{%s}%s" % (uri, tag) if uri else tag, uri


def get_qualified_path(path, uri):
    return u'/'.join([get_qname(uri, name) for name in split_path(path)])


def get_namespace(name):
    try:
        return _RE_MATCH_NAMESPACE.match(name).group(1)
    except AttributeError:
        return None


def strip_namespace(path_or_name, prefix=''):
    return _RE_STRIP_NAMESPACE.sub(prefix, path_or_name)


def split_path(path):
    return _RE_SPLIT_PATH.split(path)


def uri_to_prefixes(text, namespaces):
    """Replace namespace "{uri}" with "prefix:". """
    print(namespaces)
    for prefix, uri in namespaces.items():
        if not uri or not prefix:
            continue
        uri = '{%s}' % uri
        if text.find(uri) >= 0:
            text = text.replace(uri, '%s:' % prefix)
    return text
