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


def linked_flatten(obj):
    """
    Generate a sequence of 2-tuples from a nested structure of lists/tuples/sets.
    Each tuple is a couple with an item and the correspondent inner container.
    """
    if isinstance(obj, (list, tuple, set)):
        for item in obj:
            for _item, _container in linked_flatten(item):
                if _container is None:
                    yield _item, obj
                else:
                    yield _item, _container
    else:
        yield obj, None


def meta_next_gen(iterator, container=None):
    """
    Generate a 3-tuples of items from an iterator. The iterator's
    elements are expanded in case of list, tuple or set.

    :param iterator: the root iterator that generates the sequence.
    :param container: parent container of the iterator.
    :return: 3-tuple with: an object, a related iterator and the parent
    container. Returned iterator is None if the argument is not an iterable.
    """
    try:
        obj = next(iterator)
        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                for _obj, _iterator, _container in meta_next_gen(item, obj):
                    if _iterator is None:
                        yield _obj, iterator, _container
                    else:
                        yield _obj, _iterator, _container
        else:
            yield obj, iterator, container
    except TypeError:
        yield iterator, None, container
