#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
from ..helpers import get_namespace, get_qname

_REGEX_SPACES = re.compile(r'\s+')


def iter_nested_items(items, dict_class=dict, list_class=list):
    """Iterates a nested object composed by lists and dictionaries."""
    if isinstance(items, dict_class):
        for k, v in items.items():
            yield from iter_nested_items(v, dict_class, list_class)
    elif isinstance(items, list_class):
        for item in items:
            yield from iter_nested_items(item, dict_class, list_class)
    elif isinstance(items, dict):
        raise TypeError("%r: is a dict() instead of %r." % (items, dict_class))
    elif isinstance(items, list):
        raise TypeError("%r: is a list() instead of %r." % (items, list_class))
    else:
        yield items


def etree_elements_assert_equal(elem, other, strict=True, skip_comments=True, unordered=False):
    """
    Tests the equality of two XML Element trees.

    :param elem: the master Element tree, reference for namespace mapping.
    :param other: the other Element tree that has to be compared.
    :param strict: asserts strictly equality. `True` for default.
    :param skip_comments: skip comments from comparison.
    :param unordered: children may have different order.
    :raise: an AssertionError containing information about first difference encountered.
    """
    if unordered:
        children = sorted(elem, key=lambda x: '' if callable(x.tag) else x.tag)
        other_children = iter(sorted(
            other, key=lambda x: '' if callable(x.tag) else x.tag
        ))
    else:
        children = elem
        other_children = iter(other)

    namespace = ''
    for e1 in children:
        if skip_comments and callable(e1.tag):
            continue

        try:
            while True:
                e2 = next(other_children)
                if not skip_comments or not callable(e2.tag):
                    break
        except StopIteration:
            raise AssertionError("Node %r has more children than %r" % (elem, other))

        if strict or e1 is elem:
            if e1.tag != e2.tag:
                raise AssertionError("%r != %r: tags differ" % (e1, e2))
        else:
            namespace = get_namespace(e1.tag) or namespace
            if get_qname(namespace, e1.tag) != get_qname(namespace, e2.tag):
                raise AssertionError("%r != %r: tags differ." % (e1, e2))

        # Attributes
        if e1.attrib != e2.attrib:
            if strict:
                msg = "{!r} != {!r}: attributes differ: {!r} != {!r}"
                raise AssertionError(msg.format(e1, e2, e1.attrib, e2.attrib))
            else:
                msg = "%r != %r: attribute keys differ: %r != %r"
                if sorted(e1.attrib.keys()) != sorted(e2.attrib.keys()):
                    raise AssertionError(msg % (e1, e2, e1.attrib.keys(), e2.attrib.keys()))
                for k in e1.attrib:
                    a1, a2 = e1.attrib[k].strip(), e2.attrib[k].strip()
                    if a1 != a2:
                        try:
                            if float(a1) != float(a2):
                                raise ValueError()
                        except (ValueError, TypeError):
                            msg = "%r != %r: attribute %r values differ: %r != %r"
                            raise AssertionError(msg % (e1, e2, k, a1, a2)) from None

        # Number of children
        if skip_comments:
            nc1 = len([c for c in e1 if not callable(c.tag)])
            nc2 = len([c for c in e2 if not callable(c.tag)])
        else:
            nc1 = len(e1)
            nc2 = len(e2)
        if nc1 != nc2:
            msg = "%r != %r: children number differ: %r != %r"
            raise AssertionError(msg % (e1, e2, nc1, nc2))

        # Text
        if e1.text != e2.text:
            message = "%r != %r: texts differ: %r != %r" % (e1, e2, e1.text, e2.text)
            if strict:
                raise AssertionError(message)
            elif e1.text is None:
                if e2.text.strip():
                    raise AssertionError(message)
            elif e2.text is None:
                if e1.text.strip():
                    raise AssertionError(message)
            elif _REGEX_SPACES.sub('', e1.text.strip()) != _REGEX_SPACES.sub('', e2.text.strip()):
                text1 = e1.text.strip()
                text2 = e2.text.strip()
                if text1 == 'false':
                    if text2 != '0':
                        raise AssertionError(message)
                elif text1 == 'true':
                    if text2 != '1':
                        raise AssertionError(message)
                elif text2 == 'false':
                    if text1 != '0':
                        raise AssertionError(message)
                elif text2 == 'true':
                    if text1 != '1':
                        raise AssertionError(message)
                else:
                    try:
                        items1 = text1.split()
                        items2 = text2.split()
                        if len(items1) != len(items2):
                            raise ValueError()
                        if not all(float(x1) == float(x2) for x1, x2 in zip(items1, items2)):
                            raise ValueError()
                    except (AssertionError, ValueError, TypeError):
                        raise AssertionError(message) from None

        # Tail
        if e1.tail != e2.tail:
            message = "%r != %r: tails differ: %r != %r" % (e1, e2, e1.tail, e2.tail)
            if strict:
                raise AssertionError(message)
            elif e1.tail is None:
                if e2.tail.strip():
                    raise AssertionError(message)
            elif e2.tail is None:
                if e1.tail.strip():
                    raise AssertionError(message)
            elif e1.tail.strip() != e2.tail.strip():
                raise AssertionError(message)

        etree_elements_assert_equal(e1, e2, strict, skip_comments, unordered)

    try:
        next(other_children)
    except StopIteration:
        pass
    else:
        raise AssertionError("Node %r has lesser children than %r." % (elem, other))
