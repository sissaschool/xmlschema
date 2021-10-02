#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Type aliases for static typing analysis."""

from typing import TYPE_CHECKING, Any, BinaryIO, Callable, Dict, List, \
    Iterator, Optional, TextIO, Tuple, Type, Union

from .etree import ElementTree

if TYPE_CHECKING:
    from .resources import XMLResource
    from .converters import XMLSchemaConverter
    from .dataobjects import DataElement
    from .validators import XMLSchemaValidationError, XsdComponent, XMLSchemaBase
else:
    XMLResource = Any
    XMLSchemaConverter = Any
    DataElement = Any
    XMLSchemaValidationError = Any
    XsdComponent = Any
    XMLSchemaBase = Any

##
# Type aliases for ElementTree

ElementType = ElementTree.Element
ElementTreeType = ElementTree.ElementTree
XMLSourceType = Union[str, bytes, BinaryIO, TextIO, ElementType, ElementTreeType]
NamespacesType = Optional[Dict[str, str]]


##
# Type aliases for XML resources

NormalizedLocationsType = List[Tuple[str, str]]
LocationsType = Union[Tuple[Tuple[str, str], ...], Dict[str, str], NormalizedLocationsType]
NsmapType = Optional[Union[List[Tuple[str, str]], Dict[str, str]]]
AncestorsType = Optional[List[ElementType]]
ParentMapType = Optional[Dict[ElementType, Optional[ElementType]]]
LazyType = Union[bool, int]


##
# Type aliases for XSD validators

SchemaSourceType = Union[str, bytes, BinaryIO, TextIO, ElementTree.Element,
                         ElementTree.ElementTree, XMLResource]
ConverterType = Union[Type[XMLSchemaConverter], XMLSchemaConverter]
ComponentClassesType = Union[None, Type[XsdComponent], Tuple[Type[XsdComponent], ...]]

DecodeReturnType = Union[Any, List[Any],
                         Tuple[None, List[XMLSchemaValidationError]],
                         Tuple[Any, List[XMLSchemaValidationError]],
                         Tuple[List[Any], List[XMLSchemaValidationError]]]

EncodeReturnType = Union[None, ElementType, List[ElementType],
                         Tuple[None, List[XMLSchemaValidationError]],
                         Tuple[ElementType, List[XMLSchemaValidationError]],
                         Tuple[List[ElementType], List[XMLSchemaValidationError]]]

ToObjectsReturnType = Union[DataElement, List[DataElement],
                            Tuple[None, List[XMLSchemaValidationError]],
                            Tuple[DataElement, List[XMLSchemaValidationError]],
                            Tuple[List[DataElement], List[XMLSchemaValidationError]]]

ExtraValidatorType = Optional[Callable[[ElementType, XMLSchemaBase], Optional[Iterator[Any]]]]

##
# Type aliases for XML documents API

JsonDecodeReturnType = Union[str, None, Tuple[XMLSchemaValidationError, ...],
                             Tuple[Union[str, None], Tuple[XMLSchemaValidationError, ...]]]
