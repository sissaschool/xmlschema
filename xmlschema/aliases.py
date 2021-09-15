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
Defining various aliases, mainly for type checking.
"""
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from typing import Dict, Tuple, List, IO, Union, Callable
    from .etree import ElementTree

    ElementType = ElementTree.Element
    NamespacesType = Optional[Dict[str, str]]

    # For XML resources
    XmlSourceType = Union[str, IO, ElementTree.Element, ElementTree.ElementTree]
    NormalizedLocationsType = List[Tuple[str, str]]
    LocationsType = Union[Dict[str, str], Tuple[Tuple[str, str]], NormalizedLocationsType]
    NsmapType = Optional[List[Tuple[str, str]], Dict[str, str]]
    AncestorsType = Optional[List[ElementType]]
    ParentMapType = Optional[Dict[ElementType, Optional[ElementType]]]
    LazyType = Union[bool, int]

else:
    # In runtime type aliases fallback to Any
    ElementType = Any
    NamespacesType = Any
    XmlSourceType = Any
    NormalizedLocationsType = Any
    LocationsType = Any
    NsmapType = Any
    AncestorsType = Any
    ParentMapType = Any
    LazyType = Any
