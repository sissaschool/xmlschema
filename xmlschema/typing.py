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

from typing import TYPE_CHECKING, Any, AnyStr, Dict, IO, List, Optional, Tuple, Type, Union

from .etree import ElementTree

if TYPE_CHECKING:
    from .resources import XMLResource
    from .converters import XMLSchemaConverter
    from .validators import XMLSchemaValidationError, XsdComponent


##
# Type aliases for ElementTree

ElementType = ElementTree.Element
ElementTreeType = ElementTree.ElementTree
XMLSourceType = Union[str, bytes, IO[AnyStr], ElementType, ElementTreeType]
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

SchemaSourceType = Union[str, IO, ElementTree.Element,
                         ElementTree.ElementTree, 'XMLResource']
ConverterType = Union[Type['XMLSchemaConverter'], 'XMLSchemaConverter']
ValidationSourceType = Union[XMLSourceType, 'XMLResource']
DecodeSourceType = ValidationSourceType


ComponentClassesType = Union[None, Type['XsdComponent'], Tuple[Type['XsdComponent'], ...]]
SourceType = Union[str, ElementType]
DecodeReturnType = Union[Any, List[Any],
                         Tuple[None, List['XMLSchemaValidationError']],
                         Tuple[Any, List['XMLSchemaValidationError']],
                         Tuple[List[Any], List['XMLSchemaValidationError']]]

EncodeReturnType = Union[None, ElementType, List[ElementType],
                         Tuple[None, List['XMLSchemaValidationError']],
                         Tuple[ElementType, List['XMLSchemaValidationError']],
                         Tuple[List[ElementType], List['XMLSchemaValidationError']]]

##
# Type aliases for XML documents API

XMLDocumentType = Union[XMLSourceType, 'XMLResource']
JsonDecodeReturnType = Union[str, None, Tuple['XMLSchemaValidationError', ...],
                             Tuple[Union[str, None], Tuple['XMLSchemaValidationError', ...]]]
