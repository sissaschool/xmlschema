#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
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

from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _

if TYPE_CHECKING:
    from xmlschema.validators.xsdbase import XsdValidator  # noqa

__all__ = ['validator_property', 'Attribute', 'Option', 'Argument']


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

        if not instance.built:
            # Can't cache the property if the validator is not built
            if self._name in instance.__dict__:
                instance.__dict__.pop(self._name)
            return self.func(instance)
        elif self._name not in instance.__dict__:
            with self.lock:
                if self._name not in instance.__dict__:
                    instance.__dict__[self._name] = self.func(instance)

        return cast(RT, instance.__dict__[self._name])


T = TypeVar('T')


class Attribute(Generic[T]):
    """
    A validated descriptor for handling protected attributes
    """
    __slots__ = ('_name', '_owner')

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._name = f'_{name}'
        self._owner = owner

    def __str__(self) -> str:
        return _('attribute {!r}').format(self._name[1:])

    def __get__(self, instance: Optional[Any], owner: type[Any]) -> T:
        try:
            return cast(T, getattr(instance, self._name))
        except AttributeError:
            if instance is None:
                msg = _("{} can't be accessed from {!r}").format(self, owner)
            else:
                msg = _("{} of {!r} object has not been set").format(self, instance)
            raise XMLSchemaAttributeError(msg) from None

    def __set__(self, instance: Any, value: Any) -> None:
        if hasattr(instance, self._name):
            raise XMLSchemaAttributeError(_("can't change {}").format(self))
        setattr(instance, self._name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        raise XMLSchemaAttributeError(_("can't delete {}").format(self))

    def validated_value(self, value: Any) -> T:
        return cast(T, value)

    def _validate_choice(self, value: T, choices: Iterable[T]) -> None:
        if value not in choices:
            msg = _("invalid value {!r} for {}: must be one of {}")
            raise XMLSchemaValueError(msg.format(value, self, tuple(choices)))

    def _validate_minimum(self, value: T, min_value: Any) -> None:
        if value < min_value:
            msg = _("the value of {} must be greater or equal than {}")
            raise XMLSchemaValueError(msg.format(self, min_value))


class Argument(Attribute[T]):
    """Descriptor for an XML schema positional arguments."""
    def __str__(self) -> str:
        return _('argument {!r}').format(self._name[1:])


class Option(Argument[T]):
    """
    Descriptor for handling XML schema optional arguments and settings options.
    """
    __slots__ = ('_default',)

    def __init__(self, *, default: T) -> None:
        self._default = default

    def __str__(self) -> str:
        if 'Settings' in self._owner.__name__:
            return _('settings option {!r}').format(self._name[1:])
        return _('optional argument {!r}').format(self._name[1:])

    def __get__(self, instance: Any, owner: type[Any]) -> T:
        try:
            return cast(T, getattr(instance, self._name))
        except AttributeError:
            return self._default
