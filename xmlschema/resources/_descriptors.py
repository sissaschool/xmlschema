#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import os
from collections.abc import Iterable
from pathlib import Path
from typing import cast, overload, Any, Generic, Optional, Protocol, Tuple, Type, \
    TYPE_CHECKING, TypeVar, Union

if TYPE_CHECKING:
    from ._resource import XMLResource

from xmlschema.locations import is_url, is_local_url

ClassInfoType = Union[Type[Any], Tuple[Type[Any], ...]]


class HasResource(Protocol):
    resource: 'XMLResource'


AT = TypeVar('AT')


class ResourceAttribute(Generic[AT]):
    """
    Link to the same attribute of the resource attribute of the instance.
    Useful for composition of resource attributes in other classes.
    """

    def __set_name__(self, owner: Type[HasResource], name: str) -> None:
        self._name = name

    @overload
    def __get__(self, instance: None, owner: Type[HasResource]) \
        -> 'ResourceAttribute[AT]': ...

    @overload
    def __get__(self, instance: HasResource, owner: Type[HasResource]) -> AT: ...

    def __get__(self, instance: Optional[HasResource], owner: Type[HasResource]) \
            -> Union['ResourceAttribute[AT]', AT]:
        if instance is None:
            return self
        return cast(AT, getattr(instance.resource, self._name))

    def __set__(self, instance: HasResource, value: AT) -> None:
        raise AttributeError(f'Cannot set attribute link {self._name}')

    def __delete__(self, instance: HasResource) -> None:
        raise AttributeError(f'Cannot delete attribute link {self._name}')


class Argument(Generic[AT]):
    """
    A validated initialization argument, with a private attribute that
    can set only if it's not defined yet.
    """
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
            raise AttributeError(f"Can't set attribute {self._name}")
        setattr(instance, self._private_name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        raise AttributeError(f"Can't delete attribute {self._name}")

    def validated_value(self, value: Any) -> AT:
        return cast(AT, value)


class TypedArgument(Argument[AT]):

    def __init__(self, types: Optional[ClassInfoType] = None,
                 none: bool = True,
                 call: bool = False) -> None:
        self.types = types
        self.none = none
        self.call = call

    def validated_value(self, value: Any) -> AT:
        if value is None and self.none \
                or callable(value) and self.call \
                or self.types and isinstance(value, self.types):
            return cast(AT, value)
        else:
            raise TypeError(f"invalid type {type(value)!r} for argument {self._name!r}")


class ChoiceArgument(TypedArgument[AT]):
    """A string-type argument restricted by a set of choices."""

    def __init__(self, types: ClassInfoType, choices: Iterable[AT]) -> None:
        super().__init__(types, none=False)
        self.choices = choices

    def validated_value(self, value: Any) -> AT:
        value = super().validated_value(value)
        if value not in self.choices:
            raise ValueError(f"invalid value {value!r} for argument {self._name!r}: "
                             f"must be one of {tuple(self.choices)}")
        return cast(AT, value)


class ValueArgument(TypedArgument[AT]):
    """An typed argument with optional min and max values."""

    def __init__(self, types: ClassInfoType,
                 min_value: Optional[AT] = None,
                 max_value: Optional[AT] = None) -> None:
        super().__init__(types, none=False)
        self.min_value = min_value
        self.max_value = max_value

    def validated_value(self, value: Any) -> AT:
        value = super().validated_value(value)
        if self.min_value is not None and value < self.min_value:
            raise ValueError(f"the argument {self._name!r} must "
                             f"be greater or equal than {self.min_value}")
        elif self.max_value is not None and value > self.max_value:
            raise ValueError(f"the argument {self._name!r} must "
                             f"be lesser or equal than {self.max_value}")
        return cast(AT, value)


class UrlArgument(TypedArgument[Optional[str]]):

    @overload
    def __get__(self, instance: None, owner: Type[Any]) -> 'UrlArgument': ...

    @overload
    def __get__(self, instance: Any, owner: Type[Any]) -> Optional[str]: ...

    def __get__(self, instance: Optional[Any], owner: Type[Any]) \
            -> Union['UrlArgument', Optional[str]]:
        if instance is None:
            return self
        elif self._name == 'base_url':
            url = getattr(instance, 'url', None)
            if isinstance(url, str):
                return os.path.dirname(url)

        return self.validated_value(getattr(instance, self._private_name))

    def validated_value(self, value: Any) -> Optional[str]:
        value = super().validated_value(value)
        if value is None:
            return None
        elif not is_url(value):
            raise ValueError(f"invalid value {value!r} for argument {self._name!r}")
        elif isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode()
        else:
            return str(value)

