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
from collections import Mapping, MutableMapping

try:
    from urllib.request import urlsplit
except ImportError:
    # noinspection PyCompatibility
    from urlparse import urlsplit

from .exceptions import XMLSchemaValueError

_RE_MATCH_NAMESPACE = re.compile(r'{([^}]*)}')
_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*})')


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


def reference_to_qname(ref, namespaces):
    if ref and ref[0] == '{':
        return ref

    try:
        prefix, name = ref.split(':')
    except ValueError:
        if ':' in ref:
            raise XMLSchemaValueError("wrong format for reference name %r" % ref)
        return ref
    else:
        try:
            return "{%s}%s" % (namespaces[prefix], name)
        except KeyError:
            raise XMLSchemaValueError("prefix %r not found in namespace map" % prefix)


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


def strip_uri(qname):
    """
    Return the local part of a QName.
    
    :param qname: QName or universal name formatted string.
    """
    if qname[0] != '{':
        return qname
    try:
        return qname[qname.rindex('}') + 1:]
    except ValueError:
        raise XMLSchemaValueError("wrong format for a universal name! '%s'" % qname)


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
    if ref and ref[0] == '{':
        return ref, ref[1:].split('}')[0] if ref[0] == '{' else ''

    try:
        prefix, name = ref.split(":")
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
            return u"{%s}%s" % (uri, name) if uri else name, uri


def get_qualified_path(path, uri):
    return u'/'.join([get_qname(uri, name) for name in split_path(path)])


def get_namespace(name):
    try:
        return _RE_MATCH_NAMESPACE.match(name).group(1)
    except AttributeError:
        return ''


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


def listify_update(obj, pairs, force_list=False):
    """
    Update a dictionary forcing a list of values when the key already exists.
    Force the list also for a single value if the argument force_list is True.

    :param obj: the dictionary-like instance.
    :param pairs: sequence of (key, value) couples.
    :param force_list: Force a list at the key first insertion.
    """
    for k, v in pairs:
        if k not in obj:
            obj[k] = [v] if force_list else v
        elif not isinstance(obj[k], list):
            obj[k] = [obj[k], v]
        else:
            obj[k].append(v)


class URIDict(MutableMapping):
    """
    Dictionary which uses normalized URIs as keys.
    """
    @staticmethod
    def normalize(uri):
        return urlsplit(uri).geturl()

    def __init__(self, *args, **kwargs):
        self._store = dict()
        self._store.update(*args, **kwargs)

    def __getitem__(self, uri):
        return self._store[self.normalize(uri)]

    def __setitem__(self, uri, value):
        self._store[self.normalize(uri)] = value

    def __delitem__(self, uri):
        del self._store[self.normalize(uri)]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return repr(self._store)


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
