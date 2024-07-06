#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import io
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast, overload, Any, Callable, Generic, Iterable, \
    Optional, Tuple, Type, TYPE_CHECKING, TypeVar, Union
from urllib.request import OpenerDirector
from xml.etree import ElementTree

if TYPE_CHECKING:
    from .xml_resource import XMLResource

from xmlschema.aliases import XMLSourceType, UriMapperType, IterparseType
from xmlschema.translation import gettext as _
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url

from .exceptions import XMLResourceAttributeError, XMLResourceTypeError, XMLResourceValueError

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))

ClassInfoType = Union[Type[Any], Tuple[Type[Any], ...]]

AT = TypeVar('AT')


class Argument(Generic[AT]):
    """
    A validated initialization argument, with a private attribute that
    can set only if it's not defined yet.

    :param types: a type or a tuple of types for explicit type check. \
    For default no type checking is done.
    :param validators: an optional sequence of validator functions that accepts \
    a single argument and returns True if the argument is valid.
    :param nillable: defines when a `None` value is accepted.
    """
    _attribute_error = XMLResourceAttributeError
    _type_error = XMLResourceTypeError
    _value_error = XMLResourceValueError

    def __init__(self, types: Optional[ClassInfoType] = None,
                 validators: Iterable[Callable[[Any], bool]] = (),
                 nillable: bool = True) -> None:
        self.types = types
        self.validators = validators
        self.nillable = nillable

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        self._name = name
        self._private_name = f'_{name}'

    @overload
    def __get__(self, instance: None, owner: Type[Any]) -> 'Argument[AT]': ...

    @overload
    def __get__(self, instance: Any, owner: Type[Any]) -> AT: ...

    def __get__(self, instance: Optional[Any], owner: Type[Any]) \
            -> Union['Argument[AT]', AT]:
        if instance is None:
            return self
        return self.validated_value(getattr(instance, self._private_name))

    def __set__(self, instance: Any, value: Any) -> None:
        if hasattr(instance, self._private_name):
            raise self._attribute_error(_("Can't set attribute {}").format(self._name))
        setattr(instance, self._private_name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        raise self._attribute_error(_("Can't delete attribute {}").format(self._name))

    def validated_value(self, value: Any) -> AT:
        if value is None and self.nillable or \
                self.types and isinstance(value, self.types) or \
                any(func(value) for func in self.validators):
            return cast(AT, value)
        else:
            msg = _("invalid type {!r} for argument {!r}")
            raise self._type_error(msg.format(type(value), self._name))


class ChoiceArgument(Argument[AT]):
    """A string-type argument restricted by a set of choices."""

    def __init__(self, types: ClassInfoType, choices: Iterable[AT]) -> None:
        super().__init__(types, nillable=False)
        self.choices = choices

    def validated_value(self, value: Any) -> AT:
        value = super().validated_value(value)
        if value not in self.choices:
            msg = _("invalid value {!r} for argument {!r}: must be one of {}")
            raise self._value_error(msg.format(value, self._name, tuple(self.choices)))
        return cast(AT, value)


class ValueArgument(Argument[AT]):
    """A typed argument with optional min and max values."""

    def __init__(self, types: ClassInfoType,
                 min_value: Optional[AT] = None,
                 max_value: Optional[AT] = None) -> None:
        super().__init__(types, nillable=False)
        self.min_value = min_value
        self.max_value = max_value

    def validated_value(self, value: Any) -> AT:
        value = super().validated_value(value)
        if self.min_value is not None and value < self.min_value:
            msg = _("the argument {!r} must be greater or equal than {}")
            raise self._value_error(msg.format(self._name, self.min_value))
        elif self.max_value is not None and value > self.max_value:
            msg = _("the argument {!r} must be lesser or equal than {}")
            raise self._value_error(msg.format(self._name, self.max_value))
        return cast(AT, value)


class SourceArgument(Argument[XMLSourceType]):
    """The XML data source."""

    def __init__(self) -> None:
        super().__init__(
            types=(str, bytes, Path, io.StringIO, io.BytesIO),
            validators=(is_file_object, is_etree_element, is_etree_document)
        )

    def validated_value(self, value: Any) -> XMLSourceType:
        value = super().validated_value(value)
        if is_etree_document(value):
            if value.getroot() is None:
                raise self._value_error(_("source XML document is empty"))
        return cast(XMLSourceType, value)


class BaseUrlArgument(Argument[Optional[str]]):
    """The effective base URL used for completing relative locations."""

    def __init__(self) -> None:
        super().__init__((str, bytes, Path))

    @overload
    def __get__(self, instance: None, owner: Type['XMLResource']) \
        -> 'BaseUrlArgument': ...

    @overload
    def __get__(self, instance: 'XMLResource', owner: Type['XMLResource']) \
        -> Optional[str]: ...

    def __get__(self, instance: Optional['XMLResource'], owner: Type['XMLResource']) \
            -> Union['BaseUrlArgument', Optional[str]]:
        if instance is None:
            return self

        if instance.url is not None:
            return os.path.dirname(instance.url)
        return self.validated_value(getattr(instance, self._private_name))

    def validated_value(self, value: Any) -> Optional[str]:
        value = super().validated_value(value)
        if value is None:
            return None
        elif not is_url(value):
            msg = _("invalid value {!r} for argument {!r}")
            raise self._value_error(msg.format(value, self._name))
        elif isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode()
        else:
            return str(value)


class AllowArgument(ChoiceArgument[str]):
    """The security mode for accessing resource locations."""

    def __init__(self) -> None:
        super().__init__(str, SECURITY_MODES)


class DefuseArgument(ChoiceArgument[str]):
    """When to defuse XML data."""
    def __init__(self) -> None:
        super().__init__(str, DEFUSE_MODES)


class TimeoutArgument(ValueArgument[int]):
    """The timeout in seconds for accessing remote resources."""
    def __init__(self) -> None:
        super().__init__(int, min_value=1)


class LazyArgument(ValueArgument[Union[bool, int]]):
    """Defines if the XML resource is lazy."""
    def __init__(self) -> None:
        super().__init__((bool, int), 0)


class ThinLazyArgument(ValueArgument[bool]):
    """Defines if the resource is lazy and thin."""
    def __init__(self) -> None:
        super().__init__(bool)


class UriMapperArgument(Argument[Optional[UriMapperType]]):
    """The optional URI mapper argument for relocating addressed resources."""
    def __init__(self) -> None:
        super().__init__(MutableMapping, (callable,))


class OpenerArgument(Argument[Optional[OpenerDirector]]):
    def __init__(self) -> None:
        super().__init__(OpenerDirector)


class IterparseArgument(Argument[Optional[IterparseType]]):
    def __init__(self) -> None:
        super().__init__(validators=(callable,))

    def validated_value(self, value: Any) -> IterparseType:
        value = super().validated_value(value)
        if value is not None:
            return cast(IterparseType, value)
        return ElementTree.iterparse
