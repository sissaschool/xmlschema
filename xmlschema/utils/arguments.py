#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import Callable, Iterable
from typing import Any, cast, Generic, Optional, overload, Type, TypeVar, Union

from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _

ClassInfoType = Union[Type[Any], tuple[Type[Any], ...]]

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
            raise XMLSchemaAttributeError(_("Can't set attribute {}").format(self._name))
        setattr(instance, self._private_name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        raise XMLSchemaAttributeError(_("Can't delete attribute {}").format(self._name))

    def validated_value(self, value: Any) -> AT:
        if value is None and self.nillable or \
                self.types and isinstance(value, self.types) or \
                any(func(value) for func in self.validators):
            return cast(AT, value)
        else:
            msg = _("invalid type {!r} for argument {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self._name))


class ChoiceArgument(Argument[AT]):
    """A string-type argument restricted by a set of choices."""

    def __init__(self, types: ClassInfoType, choices: Iterable[AT]) -> None:
        super().__init__(types, nillable=False)
        self.choices = choices

    def validated_value(self, value: Any) -> AT:
        value = super().validated_value(value)
        if value not in self.choices:
            msg = _("invalid value {!r} for argument {!r}: must be one of {}")
            raise XMLSchemaValueError(msg.format(value, self._name, tuple(self.choices)))
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
            raise XMLSchemaValueError(msg.format(self._name, self.min_value))
        elif self.max_value is not None and value > self.max_value:
            msg = _("the argument {!r} must be lesser or equal than {}")
            raise XMLSchemaValueError(msg.format(self._name, self.max_value))
        return cast(AT, value)
