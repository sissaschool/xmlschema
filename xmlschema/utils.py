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
import datetime
import re


RE_ISO_TIMEZONE = re.compile(r"(Z|[+-](?:[0-1][0-9]|2[0-3]):[0-5][0-9])$")


def is_datetime_iso8601(date_string, date_format='%Y-%m-%d'):
    """
    Check if the string represents a valid datetime ISO 8601 like, according to the
    specified formatting, plus optional timezone specification as suffix.

    :param date_string: The string containing the datetime
    :param date_format: The reference formatting for datetime
    :return: True if the string is a valid datetime, False if not.
    """
    try:
        date_string, time_zone, _ = RE_ISO_TIMEZONE.split(date_string)
    except ValueError:
        pass

    try:
        datetime.datetime.strptime(date_string, date_format)
    except ValueError:
        return False
    else:
        return True


def dump_args(func):
    arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]

    def dump_func(*args, **kwargs):
        print("{}: {}".format(
            func.__name__,
            ', '.join('%s=%r' % entry for entry in list(zip(arg_names, args)) + list(kwargs.items()))
        ))
        return func(*args, **kwargs)
    return dump_func


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


def nested_next(iterator, container=None):
    """
    Produce 3-tuples of items from a structure of nested iterators.
    """
    try:
        obj = next(iterator)
        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                for o, i, c in nested_next(item, container):
                    if i is None:
                        yield o, iterator, c
                    else:
                        yield o, i, c
        else:
            yield obj, iterator, container
    except TypeError:
        yield iterator, None, container
