#
# Copyright (c), 2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import Callable, Iterator, Sequence
from functools import partial
from typing import Any, Optional
from xml.etree import ElementTree

from xmlschema.aliases import IOType, IterParseType, ElementType, NsmapType
from xmlschema.exceptions import XMLResourceParseError
from xmlschema.xpath import ElementPathSelector

SimpleFilterFunctionType = Callable[[ElementType, ElementType], bool]
FilterFunctionType = Callable[[ElementType, ElementType, list[ElementType]], bool]
CleanFunctionType = Callable[[ElementType, ElementType, list[ElementType]], bool]


def simple_iterparse(filter_fn: SimpleFilterFunctionType,
                     depth: int,
                     fp: IOType,
                     events: Optional[Sequence[str]] = None) -> Iterator[tuple[str, Any]]:
    """
    A simple event-base parser for filtering XML elements during parsing.
    """
    if events is None:
        events = 'start-ns', 'end-ns', 'start', 'end'
    elif 'start' not in events or 'end' not in events:
        events = tuple(events) + ('start', 'end')

    level = -1
    stop_node: Any = None
    root: Any = None
    node: Any

    try:
        for event, node in ElementTree.iterparse(fp, events):
            if event == 'end':
                if level == depth and stop_node is node:
                    stop_node = None
                    del node[:]
                level -= 1
            elif event == 'start':
                level += 1
                if stop_node is not None:
                    continue

                if not level:
                    root = node
                elif level == depth and not filter_fn(root, node):
                    stop_node = node
                    continue

                yield event, node
            else:
                yield event, node

    except SyntaxError as err:
        raise XMLResourceParseError("invalid XML syntax: {}".format(err)) from err


def advanced_iterparse(filter_fn: FilterFunctionType,
                       clean_fn: CleanFunctionType,
                       depth: int,
                       fp: IOType,
                       events: Optional[Sequence[str]] = None) -> Iterator[tuple[str, Any]]:
    """
    A filtered event-base XML parser with ancestors tracking.
    """
    if events is None:
        events = 'start-ns', 'end-ns', 'start', 'end'
    elif 'start' not in events or 'end' not in events:
        events = tuple(events) + ('start', 'end')

    level = -1
    ancestors: list[ElementType] = []
    stop_node: Any = None
    root: Any = None
    node: Any

    try:
        for event, node in ElementTree.iterparse(fp, events):
            if event == 'end':
                if level < depth:
                    ancestors.pop()
                elif level == depth and stop_node is node:
                    stop_node = None
                    clean_fn(root, node, ancestors)

                level -= 1
            elif event == 'start':
                level += 1
                if stop_node is not None:
                    continue

                if not level:
                    root = node

                if level < depth:
                    ancestors.append(node)
                elif level == depth:
                    if not filter_fn(root, node, ancestors):
                        stop_node = node
                        continue

                yield event, node
            else:
                yield event, node

    except SyntaxError as err:
        raise XMLResourceParseError("invalid XML syntax: {}".format(err)) from err


def iterfind_parser(path: str, namespaces: Optional[NsmapType] = None) -> IterParseType:
    selector = ElementPathSelector(path, namespaces)

    def filter_fn(root: ElementType, node: ElementType) -> bool:
        return selector.select_all or node in selector.iter_select(root)

    return partial(
        simple_iterparse,
        filter_fn=filter_fn,
        depth=selector.depth
    )
