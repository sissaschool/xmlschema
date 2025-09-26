#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import io
import os
from collections.abc import Callable, Iterable, MutableMapping
from functools import partial
from pathlib import Path
from typing import Any, cast, Generic, Optional, TypeVar, Union
from urllib.request import OpenerDirector

from xmlschema.aliases import XMLSourceType, UriMapperType, IterParseType, BlockType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaAttributeError
from xmlschema.translation import gettext as _
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.misc import is_subclass
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url
from xmlschema.xpath import ElementSelector

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))
BLOCK_TYPES = frozenset(('text', 'file', 'io', 'url', 'tree'))

T = TypeVar('T')


class Argument(Generic[T]):
    """
    A descriptor for positional and optional arguments. An argument can't be changed nor deleted.
    Arguments are validated with a sequence of validation functions tha are called by the base
    *validated_value* method.
    """
    __slots__ = ('_name', '_default')

    _default: T
    _validators: tuple[Callable[['Argument[T]', T], None], ...] = ()

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._name = f'_{name}'

    def __str__(self) -> str:
        if hasattr(self, '_default'):
            return _('optional argument {!r}').format(self._name[1:])
        return _('argument {!r}').format(self._name[1:])

    def __get__(self, instance: Optional[Any], owner: type[Any]) -> T:
        try:
            return cast(T, getattr(instance, self._name))
        except AttributeError:
            try:
                return self._default
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
        for validator in self._validators:
            validator(self, value)
        return cast(T, value)


class Option(Argument[T]):
    """
    A descriptor for handling optional arguments.

    :param default: The default value for the optional argument.
    """
    def __init__(self, *, default: T) -> None:
        self._default = default


###
# Validation helpers for arguments and options

def validate_type(attr: Argument[T], value: T,
                  types: Union[None, type[T], tuple[type[T]]] = None,
                  none: bool = False,
                  call: bool = False) -> None:
    """
    Base function for validating an argument type.

    :param attr: the argument to validate.
    :param value: the argument value to validate.
    :param types: the optional types to validate against.
    :param none: if `True` a None value is accepted.
    :param call: if `True` a callable value is accepted.
    """
    if none and value is None \
            or types is not None and isinstance(value, types) \
            or call and callable(value):
        return None

    if types is None:
        if none and call:
            msg = _("invalid type {!r} for {}, must be None o a callable")
        elif call:
            msg = _("invalid type {!r} for {}, must be a callable")
        elif none:
            msg = _("invalid type {!r} for {}, must be None")
        else:
            return None

        raise XMLSchemaTypeError(msg.format(type(value), attr))

    elif none and call:
        msg = _("invalid type {!r} for {}, must be None, a {!r} or a callable")
    elif call:
        msg = _("invalid type {!r} for {}, must be a {!r} or a callable")
    elif none:
        msg = _("invalid type {!r} for {}, must be None or a {!r}")
    else:
        msg = _("invalid type {!r} for {}, must be a {!r}")

    raise XMLSchemaTypeError(msg.format(type(value), attr, types))


def validate_subclass(attr: Argument[T], value: T, cls: type[T], none: bool = False) -> None:
    if none and value is None or is_subclass(value, cls):
        return None
    elif none:
        msg = _("invalid type {!r} for {}, must be None or a subclass of {!r}")
    else:
        msg = _("invalid type {!r} for {}, must be a subclass {!r}")

    raise XMLSchemaTypeError(msg.format(value, attr, cls))


def validate_choice(attr: Argument[T], value: T, choices: Iterable[T]) -> None:
    if value not in choices:
        msg = _("invalid value {!r} for {}: must be one of {}")
        raise XMLSchemaValueError(msg.format(value, attr, tuple(choices)))


def validate_minimum(attr: Argument[int], value: int, min_value: int) -> None:
    if value < min_value:
        msg = _("the value of {} must be greater or equal than {}")
        raise XMLSchemaValueError(msg.format(attr, min_value))


bool_validator = partial(validate_type, types=bool)
bool_int_validator = partial(validate_type, types=(bool, int))
str_validator = partial(validate_type, types=str)
none_str_validator = partial(validate_type, types=str, none=True)
pos_int_validator = partial(validate_minimum, min_value=1)
non_neg_int_validator = partial(validate_minimum, min_value=0)
callable_validator = partial(validate_type, call=True)
opt_callable_validator = partial(validate_type, none=True, call=True)


class BooleanOption(Option[bool]):
    _validators = (bool_validator,)


class StringOption(Option[str]):
    _validators = (str_validator,)

###
# XMLResource arguments

class SourceArgument(Argument[XMLSourceType]):
    def validated_value(self, value: Any) -> XMLSourceType:
        if isinstance(value, (str, bytes, Path, io.StringIO, io.BytesIO)):
            return cast(XMLSourceType, value)
        elif is_file_object(value) or is_etree_element(value):
            return cast(XMLSourceType, value)
        elif is_etree_document(value):
            if value.getroot() is None:
                raise XMLSchemaValueError(_("source XML document is empty"))
            return cast(XMLSourceType, value)
        else:
            msg = _("invalid type {!r} for {}, must be a string containing the "
                    "XML document or file path or a URL or a file like object or "
                    "an ElementTree or an Element")
            raise XMLSchemaTypeError(msg.format(type(value), self))


class BaseUrlOption(Option[Optional[str]]):
    def __get__(self, instance: Any, owner: type[Any]) -> Optional[str]:
        if instance is None:
            return self._default
        if isinstance(url := getattr(instance, 'url', None), str):
            return os.path.dirname(url)
        return cast(Optional[str], getattr(instance, self._name, self._default))

    def validated_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        elif not isinstance(value, (str, bytes, Path)):
            msg = _("invalid type {!r} for {}, must be of type {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self, (str, bytes, Path)))
        elif not is_url(value):
            msg = _("invalid value {!r} for {}")
            raise XMLSchemaValueError(msg.format(value, self))
        elif isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode()
        else:
            return str(value)


class AllowOption(Option[str]):
    _validators = str_validator, partial(validate_choice, choices=SECURITY_MODES)


class DefuseOption(Option[str]):
    _validators = str_validator, partial(validate_choice, choices=DEFUSE_MODES)


class TimeOutOption(Option[int]):
    _validators = pos_int_validator,


class LazyOption(Option[Union[bool, int]]):
    _validators = bool_int_validator, non_neg_int_validator


class BlockOption(Option[Optional[BlockType]]):
    def validator(self, value: Any) -> Optional[BlockType]:
        if value is None:
            return value
        elif isinstance(value, str):
            value = value.split()

        if isinstance(value, (list, tuple)) and value:
            for v in value:
                if not isinstance(v, str):
                    break
                validate_choice(self, v, BLOCK_TYPES)
            else:
                return tuple(value)

        msg = _("invalid type {!r} for {}, must be None or a tuple/list of strings")
        raise XMLSchemaTypeError(msg.format(type(value), self, (str, tuple)))


class UriMapperOption(Option[Optional[UriMapperType]]):
    _validators = partial(validate_type, types=MutableMapping, none=True, call=True),


class OpenerOption(Option[Optional[OpenerDirector]]):
    _validators = partial(validate_type, types=OpenerDirector, none=True),


class IterParseOption(Option[Optional[IterParseType]]):
    def validated_value(self, value: Any) -> Optional[IterParseType]:
        if value is None:
            return self._default
        validate_type(self, value, none=True, call=True)
        return cast(IterParseType, value)


class SelectorOption(Option[Optional[type[ElementSelector]]]):
    def validated_value(self, value: Any) -> Optional[type[ElementSelector]]:
        if value is None:
            return self._default
        validate_subclass(self, value, cls=ElementSelector, none=True)
        return cast(type[ElementSelector], value)

