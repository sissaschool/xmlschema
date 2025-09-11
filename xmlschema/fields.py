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
from collections.abc import Callable, Iterable, MutableMapping
from functools import partial
from pathlib import Path
from typing import cast, Any, Generic, Optional, TypeVar, Union
from urllib.request import OpenerDirector
from xml.etree import ElementTree

from xmlschema.aliases import XMLSourceType, UriMapperType, IterParseType, \
    ClassInfoType
from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, \
    XMLSchemaValueError
from xmlschema.translation import gettext as _
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.misc import is_subclass
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url
from xmlschema.xpath import ElementSelector

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))

T = TypeVar('T')


class ValidatedField(Generic[T]):
    """
    A validated field, with a private attribute that
    can set only if it's not defined yet.

    :param types: a type or a tuple of types for explicit type check. \
    For default no type checking is done.
    :param validators: an optional sequence of validator functions that accepts \
    a single argument and returns True if the argument is valid.
    :param nillable: defines when a default value is accepted.

    """

    def __init__(self,
                 types: Optional[ClassInfoType[Any]] = None,
                 validators: Iterable[Callable[[Any], bool]] = (),
                 *,
                 default: Optional[T] = None,
                 nillable: bool = True,
                 changeable: bool = False,
                 deletable: bool = False) -> None:

        self._types = types
        self._validators = validators
        self._default = default
        self._nillable = nillable
        self._changeable = changeable
        self._deletable = deletable

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self._name = name
        self._private_name = f'_{name}'

    def __get__(self, instance: Optional[Any], owner: type[Any]) -> Union[T]:
        try:
            return cast(T, getattr(instance, self._private_name))
        except AttributeError:
            if self._nillable or self._default is not None:
                return cast(T, self._default)

        raise XMLSchemaAttributeError(_("can't get attribute {}").format(self._name))

    def __set__(self, instance: Any, value: Any) -> None:
        if not self._changeable and hasattr(instance, self._private_name):
            raise XMLSchemaAttributeError(_("Can't change attribute {}").format(self._name))
        setattr(instance, self._private_name, self.validated_value(value))

    def __delete__(self, instance: Any) -> None:
        if not self._deletable and hasattr(instance, self._private_name):
            raise XMLSchemaAttributeError(_("Can't delete attribute {}").format(self._name))
        delattr(instance, self._private_name)

    def validated_value(self, value: Any) -> T:
        if value is None and self._nillable or \
                self._types and isinstance(value, self._types) or \
                any(func(value) for func in self._validators):
            return cast(T, value)
        else:
            msg = _("invalid type {!r} for argument {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self._name))


class BooleanField(ValidatedField[bool]):
    def __init__(self, *, default: Optional[bool]) -> None:
        super().__init__(bool, default=default)


class ChoiceField(ValidatedField[str]):
    """A string-type field restricted by a set of choices."""

    def __init__(self, types: ClassInfoType[Any], choices: Iterable[str], **kwargs: Any) -> None:
        super().__init__(types, nillable=False, **kwargs)
        self._choices = choices

    def validated_value(self, value: Any) -> str:
        value = super().validated_value(value)
        if value not in self._choices:
            msg = _("invalid value {!r} for argument {!r}: must be one of {}")
            raise XMLSchemaValueError(msg.format(value, self._name, tuple(self._choices)))
        return cast(str, value)


class OrderedField(ValidatedField[T]):
    """A typed field with optional min and max values."""

    def __init__(self, types: ClassInfoType[Any],
                 min_value: Optional[T] = None,
                 max_value: Optional[T] = None,
                 **kwargs: Any) -> None:
        super().__init__(types, nillable=False, **kwargs)
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


class SourceField(ValidatedField[XMLSourceType]):
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
                raise XMLSchemaValueError(_("source XML document is empty"))
        return cast(XMLSourceType, value)


class BaseUrlField(ValidatedField[Optional[str]]):
    """The effective base URL used for completing relative locations."""

    def __init__(self) -> None:
        super().__init__((str, bytes, Path))

    def __get__(self, instance: Optional[object], owner: type[object]) \
            -> Union[Optional[str]]:
        if instance is None:
            return None

        if isinstance(url := getattr(instance, 'url', None), str):
            return os.path.dirname(url)
        return getattr(instance, self._private_name, None)

    def validated_value(self, value: Any) -> Optional[str]:
        value = super().validated_value(value)
        if value is None:
            return None
        elif not is_url(value):
            msg = _("invalid value {!r} for argument {!r}")
            raise XMLSchemaValueError(msg.format(value, self._name))
        elif isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode()
        else:
            return str(value)


class AllowField(ChoiceField):
    """The security mode for accessing resource locations."""

    def __init__(self) -> None:
        super().__init__(str, SECURITY_MODES, default='all')


class DefuseField(ChoiceField):
    """When to defuse XML data."""
    def __init__(self) -> None:
        super().__init__(str, DEFUSE_MODES, default='remote')


class TimeoutField(OrderedField[int]):
    """The timeout in seconds for accessing remote resources."""
    def __init__(self) -> None:
        super().__init__(int, min_value=1, default=300)


class LazyField(OrderedField[Union[bool, int]]):
    """Defines if the XML resource is lazy."""
    def __init__(self) -> None:
        super().__init__((bool, int), 0, default=False)


class UriMapperField(ValidatedField[Optional[UriMapperType]]):
    """The optional URI mapper argument for relocating addressed resources."""
    def __init__(self) -> None:
        super().__init__(MutableMapping, (callable,))


class OpenerField(ValidatedField[Optional[OpenerDirector]]):
    def __init__(self) -> None:
        super().__init__(OpenerDirector)


class IterParseField(ValidatedField[Optional[IterParseType]]):
    def __init__(self) -> None:
        super().__init__(validators=(callable,))

    def validated_value(self, value: Any) -> IterParseType:
        value = super().validated_value(value)
        if value is not None:
            return cast(IterParseType, value)
        return ElementTree.iterparse


is_selector_subclass = partial[bool](is_subclass, cls=ElementSelector)


class SelectorField(ValidatedField[Optional[type[ElementSelector]]]):
    """Defines if the resource is loaded only for a specific path."""
    def __init__(self) -> None:
        super().__init__(validators=(is_selector_subclass,))

    def validated_value(self, value: Any) -> type[ElementSelector]:
        value = super().validated_value(value)
        if value is not None:
            return cast(type[ElementSelector], value)
        return ElementSelector
