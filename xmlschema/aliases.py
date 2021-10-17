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
Type aliases for static typing analysis. In a type checking context the aliases
are defined from effective classes imported from package modules. In a runtime
context the aliases are set to Any.
"""
from typing import TYPE_CHECKING, Optional, TypeVar

__all__ = ['ElementType', 'ElementTreeType', 'XMLSourceType', 'NamespacesType',
           'NormalizedLocationsType', 'LocationsType', 'NsmapType', 'ParentMapType',
           'LazyType', 'SchemaType', 'BaseXsdType', 'BaseElementType', 'BaseAttributeType',
           'GlobalComponentType', 'GlobalMapType', 'ModelGroupType', 'ModelParticleType',
           'XPathElementType', 'AtomicValueType', 'NumericValueType', 'DateTimeType',
           'SchemaSourceType', 'ConverterType', 'ComponentClassType', 'ExtraValidatorType',
           'DecodeType', 'IterDecodeType', 'JsonDecodeType', 'EncodeType', 'IterEncodeType',
           'DecodedValueType', 'EncodedValueType']

if TYPE_CHECKING:
    from decimal import Decimal
    from typing import BinaryIO, Callable, Dict, List, Iterator, MutableMapping, \
        TextIO, Tuple, Type, Union

    from elementpath.datatypes import NormalizedString, QName, Float10, Integer, \
        Time, Base64Binary, HexBinary, AnyURI, Duration
    from elementpath.datatypes.datetime import OrderedDateTime

    from .etree import ElementTree
    from .resources import XMLResource
    from .converters import XMLSchemaConverter
    from .validators import XMLSchemaValidationError, XsdComponent, XMLSchemaBase, \
        XsdComplexType, XsdSimpleType, XsdElement, XsdAnyElement, XsdAttribute, \
        XsdAnyAttribute, XsdAssert, XsdGroup, XsdAttributeGroup, XsdNotation

    ##
    # Type aliases for ElementTree
    ElementType = ElementTree.Element
    ElementTreeType = ElementTree.ElementTree
    XMLSourceType = Union[str, bytes, BinaryIO, TextIO, ElementType, ElementTreeType]
    NamespacesType = MutableMapping[str, str]

    ##
    # Type aliases for XML resources
    NormalizedLocationsType = List[Tuple[str, str]]
    LocationsType = Union[Tuple[Tuple[str, str], ...], Dict[str, str], NormalizedLocationsType]
    NsmapType = Union[List[Tuple[str, str]], MutableMapping[str, str]]
    ParentMapType = Dict[ElementType, Optional[ElementType]]
    LazyType = Union[bool, int]

    ##
    # Type aliases for XSD components
    SchemaType = XMLSchemaBase
    BaseXsdType = Union[XsdSimpleType, XsdComplexType]
    BaseElementType = Union[XsdElement, XsdAnyElement]
    BaseAttributeType = Union[XsdAttribute, XsdAnyAttribute]
    GlobalComponentType = Union[XsdNotation, BaseXsdType, XsdElement,
                                XsdAttribute, XsdAttributeGroup, XsdGroup]

    C = TypeVar('C')
    GlobalMapType = Dict[str, Union[C, Tuple[ElementType, SchemaType]]]

    ModelGroupType = XsdGroup
    ModelParticleType = Union[XsdElement, XsdAnyElement, XsdGroup]
    ExpectedChildrenType = Optional

    XPathElementType = Union[XsdElement, XsdAnyElement, XsdAssert]

    SchemaSourceType = Union[str, bytes, BinaryIO, TextIO, ElementTree.Element,
                             ElementTree.ElementTree, XMLResource]
    ConverterType = Union[Type[XMLSchemaConverter], XMLSchemaConverter]
    ComponentClassType = Union[None, Type[XsdComponent], Tuple[Type[XsdComponent], ...]]
    ExtraValidatorType = Callable[[ElementType, SchemaType],
                                  Optional[Iterator[XMLSchemaValidationError]]]

    ##
    # Type aliases for datatypes
    AtomicValueType = Union[str, int, float, Decimal, bool, Integer, Float10, NormalizedString,
                            AnyURI, HexBinary, Base64Binary, QName, Duration]
    NumericValueType = Union[str, bytes, int, float, Decimal]
    DateTimeType = Union[OrderedDateTime, Time]

    ##
    # Type aliases for decoding/encoding
    D = TypeVar('D')
    DecodeType = Union[Optional[D], Tuple[Optional[D], List[XMLSchemaValidationError]]]
    IterDecodeType = Iterator[Union[D, XMLSchemaValidationError]]

    E = TypeVar('E')
    EncodeType = Union[E, Tuple[E, List[XMLSchemaValidationError]]]
    IterEncodeType = Iterator[Union[E, XMLSchemaValidationError]]

    JsonDecodeType = Union[str, None, Tuple[XMLSchemaValidationError, ...],
                           Tuple[Union[str, None], Tuple[XMLSchemaValidationError, ...]]]

    DecodedValueType = Union[None, AtomicValueType, List[AtomicValueType]]
    EncodedValueType = Union[None, str, List[str]]

else:
    # In runtime use a dummy subscriptable type for compatibility
    T = TypeVar('T')
    DummyType = Optional[T]

    module_globals = globals()
    for name in __all__:
        module_globals[name] = DummyType
