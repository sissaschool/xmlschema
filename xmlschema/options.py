#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Descriptors for XML schema options and arguments."""

import io
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Optional, Any, Union, cast, TypeVar
from urllib.request import OpenerDirector

from xmlschema.aliases import XMLSourceType, UriMapperType, IterParseType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _
from xmlschema.utils.descriptors import Argument, Option
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.misc import is_subclass
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url
from xmlschema.xpath import ElementSelector

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))
LOG_LEVELS = ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL', 10, 20, 30, 40, 50)

T = TypeVar('T')


class SourceArgument(Argument[XMLSourceType]):
    """The XML data source."""
    def validated_value(self, value: Any) -> XMLSourceType:
        if isinstance(value, (str, bytes, Path, io.StringIO, io.BytesIO)):
            return value
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


class BooleanOption(Option[bool]):
    def validated_value(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r}")
        raise XMLSchemaTypeError(msg.format(type(value), self, bool))


class StringOption(Option[str]):
    def validated_value(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r}")
        raise XMLSchemaTypeError(msg.format(type(value), self, str))


class IntOption(Option[int]):
    def validated_value(self, value: Any) -> int:
        if isinstance(value, int):
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r}")
        raise XMLSchemaTypeError(msg.format(type(value), self, int))


class BaseUrlOption(Option[Optional[str]]):
    """The effective base URL used for completing relative locations."""
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


class AllowOption(StringOption):
    """The security mode for accessing resource locations."""
    def validated_value(self, value: Any) -> str:
        super().validated_value(value)
        self._validate_choice(value, SECURITY_MODES)
        return cast(str, value)


class DefuseOption(StringOption):
    """When to defuse XML data."""
    def validated_value(self, value: Any) -> str:
        super().validated_value(value)
        self._validate_choice(value, DEFUSE_MODES)
        return cast(str, value)


class TimeoutOption(IntOption):
    """The timeout in seconds for accessing remote resources."""
    def validated_value(self, value: Any) -> int:
        value = super().validated_value(value)
        self._validate_minimum(value, 1)
        return cast(int, value)


class LazyOption(Option[Union[bool, int]]):
    """Defines if the XML resource is lazy."""
    def validated_value(self, value: Any) -> int:
        if isinstance(value, (int, bool)):
            self._validate_minimum(value, 0)
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r}")
        raise XMLSchemaTypeError(msg.format(type(value), self, (int, bool)))


class ThinLazyOption(BooleanOption):
    """Defines if the resource is lazy and thin."""


class UriMapperOption(Option[Optional[UriMapperType]]):
    """The optional URI mapper argument for relocating addressed resources."""
    def validated_value(self, value: Any) -> Optional[UriMapperType]:
        if value is None or isinstance(value, MutableMapping) or callable(value):
            return cast(UriMapperType, value)
        msg = _("invalid type {!r} for {}, must be of dict or a callable object")
        raise XMLSchemaTypeError(msg.format(type(value), self, MutableMapping))


class OpenerOption(Option[Optional[OpenerDirector]]):
    def validated_value(self, value: Any) -> Optional[OpenerDirector]:
        if value is None or isinstance(value, OpenerDirector):
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r} or None")
        raise XMLSchemaTypeError(msg.format(type(value), self, OpenerDirector))


class IterParseOption(Option[Optional[IterParseType]]):
    def validated_value(self, value: Any) -> Optional[IterParseType]:
        if value is None:
            return self._default
        elif callable(value):
            return cast(Optional[IterParseType], value)
        else:
            msg = _("invalid type {!r} for {}, must be a callable object or None")
            raise XMLSchemaTypeError(msg.format(type(value), self))


class SelectorOption(Option[Optional[type[ElementSelector]]]):
    """Defines if the resource is loaded only for a specific path."""
    def validated_value(self, value: Any) -> Optional[type[ElementSelector]]:
        if value is None:
            return self._default
        elif is_subclass(value, ElementSelector):
            return cast(Optional[type[ElementSelector]], value)
        else:
            msg = _("invalid type {!r} for {}, must be a subclass of {!r}")
            raise XMLSchemaTypeError(msg.format(value, self, ElementSelector))


class LogLevelOption(Option[Union[None, str, int]]):
    def validated_value(self, value: Any) -> Union[None, str, int]:
        if value is None:
            return self._default
        elif isinstance(value, (int, str)):
            self._validate_choice(value, LOG_LEVELS)
            return value
        else:
            msg = _("invalid type {!r} for {}, must be of type {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self, (str, int)))
