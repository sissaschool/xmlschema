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
from threading import Lock
from typing import Any, cast, Generic, Optional, overload, TypeVar, TYPE_CHECKING, Union

from xmlschema.aliases import ClassInfoType
from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _

if TYPE_CHECKING:
    from xmlschema.validators.xsdbase import XsdValidator

__all__ = ['validator_property', 'Argument', 'ChoiceArgument', 'ValueArgument']


VT = TypeVar('VT', bound='XsdValidator')
RT = TypeVar('RT')


# noinspection PyPep8Naming
class validator_property(Generic[VT, RT]):
    """A property that caches the value only if the XSD validator is built."""

    __slots__ = ('func', 'lock', '_name', '__dict__')

    def __init__(self, func: Callable[[VT], RT]) -> None:
        self.func = func
        self.lock = Lock()
        self.__doc__ = func.__doc__
        if hasattr(func, '__module__'):
            self.__module__ = func.__module__

    def __set_name__(self, owner: type[VT], name: str) -> None:
        if not hasattr(owner, 'built'):
            raise XMLSchemaTypeError("{!r} is not an XSD validator".format(owner))
        if name == 'built':
            raise XMLSchemaAttributeError("can't apply to 'built' property")
        self._name = name

    @overload
    def __get__(self, instance: None, owner: type[VT]) -> 'validator_property[VT, RT]': ...

    @overload
    def __get__(self, instance: VT, owner: type[VT]) -> RT: ...

    def __get__(self, instance: Optional[VT], owner: type[VT]) \
            -> Union['validator_property[VT, RT]', RT]:
        if instance is None:
            return self

        if self._name not in instance.__dict__:
            value = self.func(instance)
            if not instance.built:
                # Can't cache the property if the validator is not built
                return value

            with self.lock:
                if self._name not in instance.__dict__:
                    instance.__dict__[self._name] = value

        return cast(RT, instance.__dict__[self._name])


T = TypeVar('T')


class Argument(Generic[T]):
    """
    A validated initialization argument, with a private attribute that
    can set only if it's not defined yet.

    :param types: a type or a tuple of types for explicit type check. \
    For default no type checking is done.
    :param validators: an optional sequence of validator functions that accepts \
    a single argument and returns True if the argument is valid.
    :param nillable: defines when a `None` value is accepted.
    """

    def __init__(self, types: Optional[ClassInfoType[Any]] = None,
                 validators: Iterable[Callable[[Any], bool]] = (),
                 nillable: bool = True) -> None:
        self.types = types
        self.validators = validators
        self.nillable = nillable

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._name = name
        self._private_name = f'_{name}'

    @overload
    def __get__(self, instance: None, owner: type[Any]) -> 'Argument[T]': ...

    @overload
    def __get__(self, instance: Any, owner: type[Any]) -> T: ...

    def __get__(self, instance: Optional[Any], owner: type[Any]) \
            -> Union['Argument[T]', T]:
        if instance is None:
            return self
        return self.validated_value(getattr(instance, self._private_name))

    def __set__(self, instance: Any, value: Any) -> None:
        if hasattr(instance, self._private_name):
            raise XMLSchemaAttributeError(_("Can't set attribute {}").format(self._name))
        setattr(instance, self._private_name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        raise XMLSchemaAttributeError(_("Can't delete attribute {}").format(self._name))

    def validated_value(self, value: Any) -> T:
        if value is None and self.nillable or \
                self.types and isinstance(value, self.types) or \
                any(func(value) for func in self.validators):
            return cast(T, value)
        else:
            msg = _("invalid type {!r} for argument {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self._name))


class ChoiceArgument(Argument[T]):
    """A string-type argument restricted by a set of choices."""

    def __init__(self, types: ClassInfoType[Any], choices: Iterable[T]) -> None:
        super().__init__(types, nillable=False)
        self.choices = choices

    def validated_value(self, value: Any) -> T:
        value = super().validated_value(value)
        if value not in self.choices:
            msg = _("invalid value {!r} for argument {!r}: must be one of {}")
            raise XMLSchemaValueError(msg.format(value, self._name, tuple(self.choices)))
        return cast(T, value)


class ValueArgument(Argument[T]):
    """A typed argument with optional min and max values."""

    def __init__(self, types: ClassInfoType[Any],
                 min_value: Optional[T] = None,
                 max_value: Optional[T] = None) -> None:
        super().__init__(types, nillable=False)
        self.min_value = min_value
        self.max_value = max_value

    def validated_value(self, value: Any) -> T:
        value = super().validated_value(value)
        if self.min_value is not None and value < self.min_value:
            msg = _("the argument {!r} must be greater or equal than {}")
            raise XMLSchemaValueError(msg.format(self._name, self.min_value))
        elif self.max_value is not None and value > self.max_value:
            msg = _("the argument {!r} must be lesser or equal than {}")
            raise XMLSchemaValueError(msg.format(self._name, self.max_value))
        return cast(T, value)
