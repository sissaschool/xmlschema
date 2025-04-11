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
from collections import Counter
from collections.abc import Callable, Iterator, MutableMapping, Sequence
from typing import Any, AnyStr, IO, Optional, TYPE_CHECKING, TypeVar, Union
from xml.etree.ElementTree import Element, ElementTree

from elementpath.datatypes import NormalizedString, QName, Float10, Integer, \
    AnyURI, Duration, AbstractDateTime, AbstractBinary
from elementpath.protocols import ElementProtocol, DocumentProtocol
from elementpath import ElementNode, LazyElementNode, DocumentNode

from .utils.protocols import IOProtocol

__all__ = ['ElementType', 'ElementTreeType', 'XMLSourceType', 'NsmapType', 'LocationsMapType',
           'NormalizedLocationsType', 'LocationsType', 'NsmapType', 'XmlnsType',
           'ParentMapType', 'SchemaType', 'BaseXsdType', 'SchemaElementType',
           'SchemaAttributeType', 'SchemaGlobalType', 'ModelGroupType',
           'ModelParticleType', 'XPathElementType', 'AtomicValueType',
           'NumericValueType', 'SchemaSourceType', 'ComponentClassType',
           'LoadedItemType', 'StagedItemType', 'ExtraValidatorType',
           'ValidationHookType', 'DecodeType', 'IterDecodeType',
           'JsonDecodeType', 'EncodeType', 'IterEncodeType', 'DecodedValueType',
           'FillerType', 'DepthFillerType', 'ValueHookType', 'ElementHookType',
           'SerializerType', 'OccursCounterType', 'LazyType', 'SourceType',
           'UriMapperType', 'IterParseType', 'EtreeType', 'IOType', 'ClassInfoType',
           'ResourceNodeType', 'NsmapsMapType', 'XmlnsMapType', 'ErrorsType']

if TYPE_CHECKING:
    from xmlschema.resources import XMLResource
    from xmlschema.namespaces import NamespaceResourcesMap
    from xmlschema.converters import ElementData  # noqa: F401
    from xmlschema.validators import XMLSchemaValidationError, XsdComponent, \
        XsdComplexType, XsdSimpleType, XsdElement, XsdAnyElement, XsdAttribute, \
        XsdAnyAttribute, XsdAssert, XsdGroup, XsdAttributeGroup, XsdNotation, \
        ParticleMixin, XMLSchemaBase

##
# Type aliases for ElementTree
ElementType = Element
ElementTreeType = ElementTree

##
# Type aliases for namespaces
NsmapType = MutableMapping[str, str]
LocationsMapType = dict[str, Union[str, list[str]]]
NormalizedLocationsType = list[tuple[str, str]]
LocationsType = Union[tuple[tuple[str, str], ...], dict[str, str],
                      NormalizedLocationsType, 'NamespaceResourcesMap[str]']
XmlnsType = Optional[list[tuple[str, str]]]

##
# Type aliases for XML resources
IOType = Union[IOProtocol[str], IOProtocol[bytes]]
EtreeType = Union[Element, ElementTree, ElementProtocol, DocumentProtocol]
SourceType = Union[str, bytes, Path, IO[str], IO[bytes]]
XMLSourceType = Union[SourceType, EtreeType]

ResourceNodeType = Union[ElementNode, LazyElementNode, DocumentNode]
LazyType = Union[bool, int]
UriMapperType = Union[MutableMapping[str, str], Callable[[str], str]]
IterParseType = Callable[[IOType, Optional[Sequence[str]]], Iterator[tuple[str, Any]]]
ParentMapType = dict[ElementType, Optional[ElementType]]
NsmapsMapType = dict[ElementType, dict[str, str]]
XmlnsMapType = dict[ElementType, list[tuple[str, str]]]

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
    Union['ParticleMixin', ModelParticleType, tuple[ModelGroupType], None]
]
ComponentClassType = Union[None, type['XsdComponent'], tuple[type['XsdComponent'], ...]]
XPathElementType = Union['XsdElement', 'XsdAnyElement', 'XsdAssert']

C = TypeVar('C')
ClassInfoType = Union[type[C], tuple[type[C], ...]]

LoadedItemType = tuple[ElementType, SchemaType]
StagedItemType = Union[LoadedItemType, list[LoadedItemType], tuple[LoadedItemType]]

##
# Type aliases for datatypes
AtomicValueType = Union[str, bytes, int, float, Decimal, bool, Integer,
                        Float10, NormalizedString, AnyURI, QName, Duration,
                        AbstractDateTime, AbstractBinary]
NumericValueType = Union[str, bytes, int, float, Decimal]

##
# Type aliases for validation/decoding/encoding
ErrorsType = list['XMLSchemaValidationError']
ExtraValidatorType = Callable[[ElementType, 'XsdElement'],
                              Optional[Iterator['XMLSchemaValidationError']]]
ValidationHookType = Callable[[ElementType, 'XsdElement'], Union[bool, str]]

D = TypeVar('D')
DecodeType = Union[Optional[D], tuple[Optional[D], ErrorsType]]
IterDecodeType = Iterator[Union[D, 'XMLSchemaValidationError']]

E = TypeVar('E')
EncodeType = Union[E, tuple[E, ErrorsType]]
IterEncodeType = Iterator[Union[E, 'XMLSchemaValidationError']]

JsonDecodeType = Union[str, None, tuple['XMLSchemaValidationError', ...],
                       tuple[Union[str, None], tuple['XMLSchemaValidationError', ...]]]

DecodedValueType = Union[None, AtomicValueType, list[Optional[AtomicValueType]]]
FillerType = Callable[[Union['XsdElement', 'XsdAttribute']], DecodedValueType]
DepthFillerType = Callable[['XsdElement'], Any]
ValueHookType = Callable[[Optional[AtomicValueType], 'BaseXsdType'], DecodedValueType]
ElementHookType = Callable[
    ['ElementData', Optional['XsdElement'], Optional['BaseXsdType']], 'ElementData'
]
SerializerType = Callable[[Any], IO[AnyStr]]
