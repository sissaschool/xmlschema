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
This module contains utility functions and classes.
"""
import re
from collections import Mapping, MutableMapping

try:
    from urllib.request import urlsplit
except ImportError:
    # noinspection PyCompatibility
    from urlparse import urlsplit

_RE_MATCH_NAMESPACE = re.compile(r'{([^}]*)}')
_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*})')


def split_path(path):
    return _RE_SPLIT_PATH.split(path)


def get_namespace(name):
    try:
        return _RE_MATCH_NAMESPACE.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


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
