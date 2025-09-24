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
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any, Union, cast, TYPE_CHECKING, TypeVar
from urllib.request import OpenerDirector

from xmlschema.aliases import XMLSourceType, UriMapperType, IterParseType, \
    SelectorType, BaseUrlType, BlockType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _
from xmlschema.utils.descriptors import Argument, Option, StringOption, \
    BooleanOption, IntOption
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.misc import is_subclass
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url
from xmlschema.xpath import ElementSelector

if TYPE_CHECKING:
    from xmlschema.resources import XMLResource  # noqa: F401

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))
BLOCK_TYPES = frozenset(('text', 'file', 'io', 'url', 'tree'))

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


class TimeOutOption(IntOption):
    """The timeout in seconds for the connection attempt in case of remote data."""
    def __init__(self, *, default: int):
        super().__init__(default=default, min_value=1)


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


class BlockOption(Option[Optional[BlockType]]):
    """The types blocked for XML source argument."""

    def validated_value(self, value: Any) -> Optional[BlockType]:
        if value is None:
            return value
        elif isinstance(value, str):
            value = value.split()

        if isinstance(value, (list, tuple)) and value:
            for v in value:
                if not isinstance(v, str):
                    break
                self._validate_choice(v, BLOCK_TYPES)
            else:
                return tuple(value)

        msg = _("invalid type {!r} for {}, must be None or a tuple/list of strings")
        raise XMLSchemaTypeError(msg.format(type(value), self, (str, tuple)))


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


@dataclass
class ResourceSettings:
    """Settings for accessing XML resources."""

    base_url: Option[Optional[str]] = BaseUrlOption(default=None)
    """The effective base URL used for completing relative locations."""

    allow: Option[str] = AllowOption(default='all')
    """
    The security mode for accessing resource locations.  Can be 'all', 'remote',
    'local' or 'sandbox'. Default is 'all' that means all types of URLs are allowed.
    With 'remote' only remote resource URLs are allowed. With 'local' only file paths
    and URLs are allowed. With 'sandbox' only file paths and URLs that are under the
    directory path identified by source or by the *base_url* argument are allowed.
    """

    defuse: Option[str] = DefuseOption(default='remote')
    """When to defuse XML data."""

    timeout: Option[int] = IntOption(default=300, min_value=1)
    """The timeout in seconds for accessing remote resources."""

    lazy: Option[Union[bool, int]] = LazyOption(default=False)
    """
    Defines if the XML data is fully loaded and processed in memory, that is for default.
    Setting `True` or a positive integer only the root element of the source is loaded
    when the XMLResource instance is created. The root and the other parts are reloaded
    at each iteration, pruning the processed subtrees at the depth defined by this option
    (`True` means 1).
    """

    thin_lazy: Option[bool] = BooleanOption(default=True)
    """
    For default, in order to reduce the memory usage, during the iteration of a lazy
    resource deletes also the preceding elements after the use. Setting `False` only
    descendant elements are deleted at the depth defined by *lazy* option.
    """

    block: Option[Optional[BlockType]] = BlockOption(default=None)
    """
    Defines which types of sources are blocked for security reasons. For default none
    of possible types are blocked. Set with a space separated string of words, choosing
    between 'text', 'file', 'io', 'url' and 'tree' or a tuple/list of them to select 
    which types are blocked.
    """

    uri_mapper: Option[Optional[UriMapperType]] = UriMapperOption(default=None)
    """Optional URI mapper for using relocated or URN-addressed resources."""

    opener: Option[Optional[OpenerDirector]] = OpenerOption(default=None)
    """Optional :class:`OpenerDirector` to use for open XML resources."""

    iterparse: Option[Optional[IterParseType]] = IterParseOption(default=None)
    """Optional callable that returns an iterator parser used for building the XML tree."""

    selector: Option[SelectorType] = SelectorOption(default=ElementSelector)

    def get_resource(self, cls: type['XMLResource'],
                     source: XMLSourceType,
                     base_url: Optional[BaseUrlType] = None) -> 'XMLResource':
        kwargs = asdict(self)
        if base_url is not None:
            kwargs['base_url'] = base_url
        return cls(source, **kwargs)

    def get_schema_resource(self, cls: type['XMLResource'],
                            source: XMLSourceType,
                            base_url: Optional[BaseUrlType] = None) -> 'XMLResource':
        return cls(
            source=source,
            base_url=base_url or self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
        )

    @classmethod
    def get_settings(cls, **kwargs: Any) -> 'ResourceSettings':
        return cls(**kwargs)

    def set_options(self, **kwargs: Any) -> None:
        """Set options for settings object."""
        type(self)(**kwargs)
        for name, value in kwargs.items():
            setattr(self, f'_{name}', value)

    def reset(self) -> None:
        """Reset settings to default values."""
        self.set_options(**asdict(type(self)()))


resource_settings = ResourceSettings()  # Active settings for XMLResource
