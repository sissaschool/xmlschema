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
This module contains general-purpose utility functions.
"""
import re
from collections import Mapping

from .core import XSD_NAMESPACE_PATH
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError

_RE_MATCH_NAMESPACE = re.compile(r'\{([^}]*)\}')
_RE_STRIP_NAMESPACE = re.compile(r'\{[^}]*\}')
_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*\})')


#
# Functions for handling fully qualified names
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
    for prefix, uri in namespaces.items():
        if not uri or not prefix:
            continue
        uri = '{%s}' % uri
        if text.find(uri) >= 0:
            text = text.replace(uri, '%s:' % prefix)
    return text


def xsd_qname(name):
    """
    Build a QName for XSD namespace from a local name.

    :param name: local name/tag
    :return: fully qualified name for XSD namespace
    """
    if name[0] != '{':
        return u"{%s}%s" % (XSD_NAMESPACE_PATH, name)
    elif not name.startswith('{%s}' % XSD_NAMESPACE_PATH):
        raise XMLSchemaValueError("'%s' is not a name of the XSD namespace" % name)
    else:
        return name


#
# Other utility functions
def dump_args(func):
    arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]

    def dump_func(*args, **kwargs):
        print("{}: {}".format(
            func.__name__,
            ', '.join('%s=%r' % entry for entry in list(zip(arg_names, args)) + list(kwargs.items()))
        ))
        return func(*args, **kwargs)
    return dump_func


def camel_case_split(s):
    """
    Split words of a camel case string
    """
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', s)


def listify_update(obj, *args, **kwargs):
    """
    Update a dictionary forcing a list of values when the key already exists.

    :param obj: the dictionary-like instance.
    :param args: couple (key, value) or dictionary.
    :param kwargs: keyword arguments dictionary.
    :return:
    """
    def _update(k, v):
        if k not in obj:
            obj[k] = v
        elif not isinstance(obj[k], list):
            obj[k] = [obj[k], v]
        elif all(not isinstance(i, list) for i in obj[k]):
            if isinstance(v, list):
                obj[k] = [obj[k], v]
            else:
                obj[k] = [obj[k], [v]]
        elif isinstance(v, list):
            obj[k].append(v)
        else:
            obj[k].append([v])

    if len(args) > 1:
        raise XMLSchemaTypeError('listify_update expected at most 1 arguments, got %d' % len(args))

    if args:
        other = args[0]
        if hasattr(other, 'items'):
            for key, value in other.items():
                _update(key, value)
        elif isinstance(other, (list, tuple)) and len(other) == 2:
                _update(other[0], other[1])
        else:
            XMLSchemaTypeError('listify_update expected at a couple of values, got %r' % other)

    for key, value in kwargs.items():
        _update(key, value)


class FrozenDict(Mapping):
    """A read-only dictionary for shared maps."""

    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)
        self._hash = None

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return '<%s %r at %#x>' % (self.__class__.__name__, self._data, id(self))

    def __contains__(self, key):
        return key in self._data

    def __eq__(self, other):
        return dict(self._data.items()) == dict(other.items())

    def __hash__(self):
        if self._hash is None:
            h = 0
            for key, value in self._data.items():
                h ^= hash((key, value))
            self._hash = h
        return self._hash

    def copy(self, **kwargs):
        return self.__class__(self, **kwargs)
