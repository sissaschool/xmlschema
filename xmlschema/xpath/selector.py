#
# Copyright (c), 2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import Iterator
from typing import Any, cast, Optional, TYPE_CHECKING
from xml.etree.ElementTree import Element

from elementpath import XPath2Parser, XPathToken, ElementNode, XPathContext

from xmlschema.aliases import ElementType, NsmapType
from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.utils.etree import etree_get_element_path

if TYPE_CHECKING:
    from xmlschema.resources import XMLResource

CacheKeyType = tuple[Any]

_selectors_cache: dict[CacheKeyType, 'ElementSelector'] = {}
_dummy_element = Element('dummy')


def get_element_selector(path: str, namespaces: Optional[NsmapType] = None) \
        -> 'ElementSelector':
    """Get an ElementSelector instance using a cache."""
    key: CacheKeyType = (path,)
    if namespaces is not None:
        key += (path,) + tuple(namespaces.items())

    try:
        return _selectors_cache[key]
    except KeyError:
        if len(_selectors_cache) > 100:
            _selectors_cache.clear()
        selector = ElementSelector(path, namespaces)
        _selectors_cache[key] = selector
        return selector


class ElementSelector:
    """
    A selector class that parse a path using the xml.etree.ElementPath interface.
    If the path parse fails fallback to elementpath.select().
    """
    select_all: bool
    _token: Optional[XPathToken]

    def __init__(self, path: str, namespaces: Optional[NsmapType] = None) -> None:
        path = path.replace(' ', '').replace('./', '')
        self.select_all = '*' in path and set(path).issubset(('*', '/'))

        if path == '.':
            self.path_depth = 0
        elif path.startswith('/'):
            self.path_depth = path.count('/') - 1
        else:
            self.path_depth = path.count('/') + 1

        self.path = path
        self.namespaces = None if namespaces is None else {k: v for k, v in namespaces.items()}

        self._path = etree_get_element_path(path)
        if self._path is None:
            parser = XPath2Parser(namespaces, strict=False)
            self._token = parser.parse(path)
        else:
            try:
                _dummy_element.find(self._path, cast(dict[str, str], namespaces))
            except SyntaxError:
                parser = XPath2Parser(namespaces, strict=False)
                self._token = parser.parse(path)
            else:
                self._token = None

    def iter_select(self, resource: 'XMLResource') -> Iterator[Element]:
        if self._token is not None:
            context = XPathContext(resource.xpath_root)
            for item in self._token.select(context):
                if not isinstance(item, ElementNode):  # pragma: no cover
                    msg = "XPath expressions on XML resources can select only elements"
                    raise XMLSchemaTypeError(msg)
                yield cast(ElementType, item.obj)
        elif self._path is not None:
            for elem in resource.root.iterfind(self._path, self.namespaces):
                if not hasattr(elem, 'tag'):  # pragma: no cover
                    msg = "XPath expressions on XML resources can select only elements"
                    raise XMLSchemaTypeError(msg)
                yield elem
