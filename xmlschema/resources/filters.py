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

from xmlschema.aliases import AncestorsType, IOType, IterParseType, ElementType, NsmapType
from xmlschema.exceptions import XMLResourceParseError
from xmlschema.xpath import ElementPathSelector

FilterFunctionType = Callable[[ElementType, ElementType, AncestorsType], bool]
ClearFunctionType = Callable[[ElementType, ElementType, AncestorsType], None]


###
# Default filter and clear functions

def no_filter(r: ElementType, e: ElementType, a: AncestorsType) -> bool:
    return True


def no_cleanup(root: ElementType, elem: ElementType,  ancestors: AncestorsType) -> None:
    return


def clear_elem(root: ElementType, elem: ElementType,  ancestors: AncestorsType) -> None:
    elem.clear()


###
# Iterparse generator function

def filtered_iterparse(fp: IOType,
                       events: Optional[Sequence[str]] = None,
                       filter_fn: Optional[FilterFunctionType] = None,
                       clear_fn: Optional[ClearFunctionType] = None,
                       ancestors: Optional[list[ElementType]] = None,
                       depth: int = 1) -> Iterator[tuple[str, Any]]:
    """
    An event-based parser for filtering XML elements during parsing.
    """
    if events is None:
        events = 'start-ns', 'end-ns', 'start', 'end'
    elif 'start' not in events or 'end' not in events:
        events = tuple(events) + ('start', 'end')

    if filter_fn is None:
        filter_fn = no_filter
    if clear_fn is None:
        clear_fn = no_cleanup

    level = 0
    stop_node: Any = None
    root: Any = None
    node: Any

    try:
        for event, node in ElementTree.iterparse(fp, events):
            if event == 'end':
                level -= 1
                if level < depth:
                    if ancestors is not None:
                        ancestors.pop()
                elif level == depth and stop_node is node:
                    stop_node = None
                    clear_fn(root, node, ancestors)
            elif event == 'start':
                if level < depth:
                    if not level:
                        root = node
                    if ancestors is not None:
                        ancestors.append(node)
                elif level == depth and not filter_fn(root, node, ancestors):
                    stop_node = node
                    level += 1
                    continue

                level += 1
                if stop_node is None:
                    yield event, node
            else:
                yield event, node

    except SyntaxError as err:
        raise XMLResourceParseError("invalid XML syntax: {}".format(err)) from err


def iterfind_parser(path: str,
                    namespaces: Optional[NsmapType] = None,
                    ancestors: AncestorsType = None) -> IterParseType:
    selector = ElementPathSelector(path, namespaces)

    def filter_fn(root: ElementType, node: ElementType, ancestors: AncestorsType) -> bool:
        return selector.select_all or node in selector.iter_select(root)

    def clear_fn(root: ElementType, node: ElementType, ancestors: AncestorsType) -> None:
        node.clear()
        if ancestors is not None:
            if node in ancestors[-1]:
                ancestors[-1].remove(node)

    return partial(
        filtered_iterparse,
        filter_fn=filter_fn,
        clear_fn=clear_fn,
        ancestors=ancestors,
        depth=selector.depth
    )
