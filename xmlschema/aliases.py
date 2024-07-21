#
# Copyright (c), 2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Type aliases for static typing analysis. In a type checking context the aliases
are defined from effective classes imported from package modules. In a runtime
context the aliases that can't be set from the same bases, due to circular
imports, are set with a common.
"""
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Counter, Dict, List, IO, Iterator, MutableMapping, \
    Optional, Sequence, Tuple, Type, TYPE_CHECKING, TypeVar, Union
from xml.etree.ElementTree import Element, ElementTree

from elementpath.datatypes import NormalizedString, QName, Float10, Integer, \
    Time, Base64Binary, HexBinary, AnyURI, Duration
from elementpath.datatypes.datetime import OrderedDateTime
from elementpath.protocols import ElementProtocol, DocumentProtocol
from elementpath import ElementNode, LazyElementNode, DocumentNode

from .utils.protocols import IOProtocol

__all__ = ['ElementType', 'ElementTreeType', 'XMLSourceType', 'NsmapType',
           'NormalizedLocationsType', 'LocationsType', 'NsmapType', 'XmlnsType',
           'ParentMapType', 'SchemaType', 'BaseXsdType', 'SchemaElementType',
           'SchemaAttributeType', 'SchemaGlobalType', 'GlobalMapType', 'ModelGroupType',
           'ModelParticleType', 'XPathElementType', 'AtomicValueType', 'NumericValueType',
           'DateTimeType', 'SchemaSourceType', 'ConverterType', 'ComponentClassType',
           'ExtraValidatorType', 'ValidationHookType', 'DecodeType', 'IterDecodeType',
           'JsonDecodeType', 'EncodeType', 'IterEncodeType', 'DecodedValueType',
           'FillerType', 'DepthFillerType', 'ValueHookType',
           'ElementHookType', 'OccursCounterType', 'LazyType', 'SourceType',
           'UriMapperType', 'IterparseType', 'EtreeType', 'IOType',
           'ResourceNodeType', 'NsmapsMapType', 'XmlnsMapType']

if TYPE_CHECKING:
    from .namespaces import NamespaceResourcesMap
    from .resources import XMLResource
    from .converters import ElementData, XMLSchemaConverter
    from .validators import XMLSchemaValidationError, XsdComponent, XMLSchemaBase, \
        XsdComplexType, XsdSimpleType, XsdElement, XsdAnyElement, XsdAttribute, \
        XsdAnyAttribute, XsdAssert, XsdGroup, XsdAttributeGroup, XsdNotation, \
        ParticleMixin

##
# Type aliases for ElementTree
ElementType = Element
ElementTreeType = ElementTree

##
# Type aliases for namespaces
NsmapType = MutableMapping[str, str]
NormalizedLocationsType = List[Tuple[str, str]]
LocationsType = Union[Tuple[Tuple[str, str], ...], Dict[str, str],
                      NormalizedLocationsType, 'NamespaceResourcesMap']
XmlnsType = Optional[List[Tuple[str, str]]]

##
# Type aliases for XML resources
IOType = Union[IOProtocol[str], IOProtocol[bytes]]
EtreeType = Union[Element, ElementTree, ElementProtocol, DocumentProtocol]
SourceType = Union[str, bytes, Path, IO[str], IO[bytes]]
XMLSourceType = Union[SourceType, EtreeType]

ResourceNodeType = Union[ElementNode, LazyElementNode, DocumentNode]
LazyType = Union[bool, int]
UriMapperType = Union[MutableMapping[str, str], Callable[[str], str]]
IterparseType = Callable[[IOType, Optional[Sequence[str]]], Iterator[Tuple[str, Any]]]
ParentMapType = Dict[ElementType, Optional[ElementType]]
NsmapsMapType = Dict[ElementType, Dict[str, str]]
XmlnsMapType = Dict[ElementType, List[Tuple[str, str]]]

##
# Type aliases for XSD components
SchemaSourceType = Union[
    str, bytes, Path, IO[str], IO[bytes], Element, ElementTree, 'XMLResource'
]
SchemaType = Union['XMLSchemaBase']
BaseXsdType = Union['XsdSimpleType', 'XsdComplexType']
SchemaElementType = Union['XsdElement', 'XsdAnyElement']
SchemaAttributeType = Union['XsdAttribute', 'XsdAnyAttribute']
SchemaGlobalType = Union['XsdNotation', 'BaseXsdType', 'XsdElement',
                         'XsdAttribute', 'XsdAttributeGroup', 'XsdGroup']

ModelGroupType = Union['XsdGroup']
ModelParticleType = Union['XsdElement', 'XsdAnyElement', 'XsdGroup']
OccursCounterType = Counter[
    Union['ParticleMixin', ModelParticleType, Tuple[ModelGroupType], None]
]
ComponentClassType = Union[None, Type['XsdComponent'], Tuple[Type['XsdComponent'], ...]]
XPathElementType = Union['XsdElement', 'XsdAnyElement', 'XsdAssert']

C = TypeVar('C')
GlobalMapType = Dict[str, Union[C, Tuple[Element, SchemaType]]]

##
# Type aliases for datatypes
AtomicValueType = Union[str, bytes, int, float, Decimal, bool, Integer,
                        Float10, NormalizedString, AnyURI, HexBinary,
                        Base64Binary, QName, Duration, OrderedDateTime, Time]
NumericValueType = Union[str, bytes, int, float, Decimal]
DateTimeType = Union[OrderedDateTime, Time]

##
# Type aliases for validation/decoding/encoding
ConverterType = Union[Type['XMLSchemaConverter'], 'XMLSchemaConverter']
ExtraValidatorType = Callable[[ElementType, 'XsdElement'],
                              Optional[Iterator['XMLSchemaValidationError']]]
ValidationHookType = Callable[[ElementType, 'XsdElement'], Union[bool, str]]

D = TypeVar('D')
DecodeType = Union[Optional[D], Tuple[Optional[D], List['XMLSchemaValidationError']]]
IterDecodeType = Iterator[Union[D, 'XMLSchemaValidationError']]

E = TypeVar('E')
EncodeType = Union[E, Tuple[E, List['XMLSchemaValidationError']]]
IterEncodeType = Iterator[Union[E, 'XMLSchemaValidationError']]

JsonDecodeType = Union[str, None, Tuple['XMLSchemaValidationError', ...],
                       Tuple[Union[str, None], Tuple['XMLSchemaValidationError', ...]]]

DecodedValueType = Union[None, AtomicValueType, List[Optional[AtomicValueType]]]

FillerType = Callable[[Union['XsdElement', 'XsdAttribute']], Any]
DepthFillerType = Callable[['XsdElement'], Any]
ValueHookType = Callable[[AtomicValueType, 'BaseXsdType'], Any]
ElementHookType = Callable[
    ['ElementData', Optional['XsdElement'], Optional['BaseXsdType']], 'ElementData'
]
