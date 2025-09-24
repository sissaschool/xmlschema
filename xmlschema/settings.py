#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Package settings for setup protection defaults."""
import dataclasses as dc
import logging
from typing import cast, Optional, Any, Union

from xmlschema.aliases import LocationsType
from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.translation import gettext as _
from xmlschema.utils.descriptors import Option, BooleanOption
from xmlschema.utils.misc import is_subclass

from xmlschema.locations import NamespaceResourcesMap
from xmlschema.resources import ResourceSettings
from xmlschema.loaders import SchemaLoader
from xmlschema.converters import ConverterType, XMLSchemaConverter

LOG_LEVELS = ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL', 10, 20, 30, 40, 50)


class ConverterOption(Option[Optional[ConverterType]]):
    def validated_value(self, value: Any) -> Optional[ConverterType]:
        if value is None or isinstance(value, XMLSchemaConverter) \
                or is_subclass(value, XMLSchemaConverter):
            return cast(ConverterType, value)
        msg = _("invalid type {!r} for {}, must be a {!r} instance/subclass or None")
        raise XMLSchemaTypeError(msg.format(type(value), self, XMLSchemaConverter))


class LocationsOption(Option[Optional[LocationsType]]):
    def validated_value(self, value: Any) -> Optional[LocationsType]:
        if value is None or isinstance(value, (tuple, dict, list, NamespaceResourcesMap)):
            return value
        msg = _("invalid type {!r} for {}, must be of type {!r} or None")
        raise XMLSchemaTypeError(msg.format(
            type(value), self, (tuple, dict, list, NamespaceResourcesMap)
        ))


class LoaderClassOption(Option[type['SchemaLoader']]):
    def validated_value(self, value: Any) -> type[SchemaLoader]:
        if value is None:
            return self._default
        elif is_subclass(value, SchemaLoader):
            return cast(type[SchemaLoader], value)
        else:
            msg = _("invalid type {!r} for {}, must be a subclass of {!r}")
            raise XMLSchemaTypeError(msg.format(value, self, SchemaLoader))


class LogLevelOption(Option[Union[None, str, int]]):
    def validated_value(self, value: Any) -> Union[None, str, int]:
        if value is None:
            return self._default
        elif isinstance(value, (int, str)):
            self._validate_choice(value, LOG_LEVELS)
            if isinstance(value, str):
                return cast(int, getattr(logging, value.upper()))
            return value
        else:
            msg = _("invalid type {!r} for {}, must be of type {!r}")
            raise XMLSchemaTypeError(msg.format(type(value), self, (str, int)))


@dc.dataclass
class SchemaSettings(ResourceSettings):
    """Settings for schemas."""
    converter: Option[Optional[ConverterType]] = ConverterOption(default=None)
    """The converter to use for decoding/encoding XML data."""

    locations: Option[Optional[LocationsType]] = LocationsOption(default=None)
    """Optional schema extra location hints with additional namespaces to import."""

    loader_class: Option[type[SchemaLoader]] = LoaderClassOption(default=SchemaLoader)

    use_fallback: Option[bool] = BooleanOption(default=True)
    use_xpath3: Option[bool] = BooleanOption(default=True)
    use_meta: Option[bool] = BooleanOption(default=True)
    loglevel: Option[Union[None, int, str]] = LogLevelOption(default=None)

    @classmethod
    def get_settings(cls, **kwargs: Any) -> 'SchemaSettings':
        return cls(**kwargs)


@dc.dataclass
class DocumentSettings(ResourceSettings):
    """
    Settings for XML instances that uses a specific configuration.
    """
    use_location_hints: Option[bool] = BooleanOption(default=True)
    dummy_schema: Option[bool] = BooleanOption(default=False)


schema_settings = SchemaSettings()
document_settings = DocumentSettings()
