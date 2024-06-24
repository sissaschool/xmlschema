#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections import Counter
from typing import Any, Callable, Iterator, Optional, Tuple

from xmlschema.names import XSI_SCHEMA_LOCATION, XSI_NONS_SCHEMA_LOCATION
from xmlschema.aliases import ElementType, NsmapType
from xmlschema.utils.qnames import get_namespace, get_prefixed_qname


def is_etree_element(obj: object) -> bool:
    """A validator for ElementTree elements that excludes XsdElement objects."""
    return hasattr(obj, 'append') and hasattr(obj, 'tag') and hasattr(obj, 'attrib')


def is_like_etree_element(obj: Any) -> bool:
    """A validator for ElementTree elements that includes XsdElement objects."""
    return hasattr(obj, 'tag') and hasattr(obj, 'attrib') and hasattr(obj, 'text')


def is_etree_document(obj: object) -> bool:
    """A validator for ElementTree objects."""
    return hasattr(obj, 'getroot') and hasattr(obj, 'parse') and hasattr(obj, 'iter')


def is_lxml_element(obj: object) -> bool:
    """A validator for lxml elements."""
    return hasattr(obj, 'append') and hasattr(obj, 'tag') and hasattr(obj, 'attrib') \
        and hasattr(obj, 'getparent') and hasattr(obj, 'nsmap') and hasattr(obj, 'xpath')


def is_lxml_document(obj: Any) -> bool:
    return is_etree_document(obj) and hasattr(obj, 'xpath') and hasattr(obj, 'xslt')


def etree_iterpath(elem: ElementType,
                   tag: Optional[str] = None,
                   path: str = '.',
                   namespaces: Optional[NsmapType] = None,
                   add_position: bool = False) -> Iterator[Tuple[ElementType, str]]:
    """
    Creates an iterator for the element and its subelements that yield elements and paths.
    If tag is not `None` or '*', only elements whose matches tag are returned from the iterator.

    :param elem: the element to iterate.
    :param tag: tag filtering.
    :param path: the current path, '.' for default.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :param add_position: add context position to child elements that appear multiple times.
    """
    if tag == "*":
        tag = None
    if not path:
        path = '../../tests'
    if tag is None or elem.tag == tag:
        yield elem, path

    if add_position:
        children_tags = Counter(e.tag for e in elem)
        positions = Counter(t for t in children_tags if children_tags[t] > 1)
    else:
        positions = Counter()

    for child in elem:
        if callable(child.tag):
            continue  # Skip comments and PIs

        child_name = child.tag if namespaces is None else get_prefixed_qname(child.tag, namespaces)
        if path == '/':
            child_path = f'/{child_name}'
        else:
            child_path = '/'.join((path, child_name))

        if child.tag in positions:
            child_path += '[%d]' % positions[child.tag]
            positions[child.tag] += 1

        yield from etree_iterpath(child, tag, child_path, namespaces, add_position)


def etree_getpath(elem: ElementType,
                  root: ElementType,
                  namespaces: Optional[NsmapType] = None,
                  relative: bool = True,
                  add_position: bool = False,
                  parent_path: bool = False) -> Optional[str]:
    """
    Returns the XPath path from *root* to descendant *elem* element.

    :param elem: the descendant element.
    :param root: the root element.
    :param namespaces: an optional mapping from namespace prefix to URI.
    :param relative: returns a relative path.
    :param add_position: add context position to child elements that appear multiple times.
    :param parent_path: if set to `True` returns the parent path. Default is `False`.
    :return: An XPath expression or `None` if *elem* is not a descendant of *root*.
    """
    if relative:
        path = '../../tests'
    elif namespaces:
        path = f'/{get_prefixed_qname(root.tag, namespaces)}'
    else:
        path = f'/{root.tag}'

    if not parent_path:
        for e, path in etree_iterpath(root, elem.tag, path, namespaces, add_position):
            if e is elem:
                return path
    else:
        for e, path in etree_iterpath(root, None, path, namespaces, add_position):
            if elem in e:
                return path
    return None


def etree_iter_location_hints(elem: ElementType) -> Iterator[Tuple[Any, Any]]:
    """Yields schema location hints contained in the attributes of an element."""
    if XSI_SCHEMA_LOCATION in elem.attrib:
        locations = elem.attrib[XSI_SCHEMA_LOCATION].split()
        for ns, url in zip(locations[0::2], locations[1::2]):
            yield ns, url

    if XSI_NONS_SCHEMA_LOCATION in elem.attrib:
        for url in elem.attrib[XSI_NONS_SCHEMA_LOCATION].split():
            yield '', url


def etree_iter_namespaces(root: ElementType,
                          elem: Optional[ElementType] = None) -> Iterator[str]:
    """
    Yields namespaces of an ElementTree structure. If an *elem* is
    provided stops when found if during the iteration.
    """
    if root.tag != '{' and root is not elem:
        yield ''

    for e in root.iter():
        if e is elem:
            return
        elif e.tag[0] == '{':
            yield get_namespace(e.tag)

        if e.attrib:
            for name in e.attrib:
                if name[0] == '{':
                    yield get_namespace(name)


def prune_etree(root: ElementType, selector: Callable[[ElementType], bool]) \
        -> Optional[bool]:
    """
    Removes from a tree structure the elements that verify the selector
    function. The checking and eventual removals are performed using a
    breadth-first visit method.

    :param root: the root element of the tree.
    :param selector: the single argument function to apply on each visited node.
    :return: `True` if the root node verify the selector function, `None` otherwise.
    """
    def _prune_subtree(elem: ElementType) -> None:
        for child in elem[:]:
            if selector(child):
                elem.remove(child)

        for child in elem:
            _prune_subtree(child)

    if selector(root):
        del root[:]
        return True
    _prune_subtree(root)
    return None
