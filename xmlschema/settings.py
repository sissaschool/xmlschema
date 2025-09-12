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
from dataclasses import dataclass
from typing import Optional, Union
from urllib.request import OpenerDirector

from xmlschema.aliases import SourceType, UriMapperType, LocationsType, \
    IterParseType, SelectorType
from xmlschema.utils.descriptors import Option
from xmlschema.options import BaseUrlOption, AllowOption, DefuseOption, \
    TimeoutOption, LazyOption, OpenerOption, UriMapperOption, SelectorOption, \
    IterParseOption, LogLevelOption, BooleanOption
from xmlschema.converters import ConverterType, ConverterOption
from xmlschema.locations import LocationsOption
from xmlschema.resources import XMLResource
from xmlschema.loaders import SchemaLoader, LoaderClassOption
from xmlschema.xpath import ElementSelector


@dataclass
class CommonSettings:
    """
    Settings for schemas and XML instances that uses a specific configuration.
    """
    locations: Option[Optional[LocationsType]] = LocationsOption(default=None)
    converter: Option[Optional[ConverterType]] = ConverterOption(default=None)

    base_url: Option[Optional[str]] = BaseUrlOption(default=None)
    """The effective base URL used for completing relative locations."""

    allow: Option[str] = AllowOption(default='all')
    """The security mode for accessing resource locations."""

    defuse: Option[str] = DefuseOption(default='remote')
    """When to defuse XML data."""

    timeout: Option[int] = TimeoutOption(default=300)
    """The timeout in seconds for accessing remote resources."""

    uri_mapper: Option[Optional[UriMapperType]] = UriMapperOption(default=None)
    opener: Option[Optional[OpenerDirector]] = OpenerOption(default=None)


@dataclass
class SchemaSettings(CommonSettings):
    """
    Settings for schemas and XML instances that uses a specific configuration.
    """
    loader_class: Option[type[SchemaLoader]] = LoaderClassOption(default=SchemaLoader)
    iterparse: Option[Optional[IterParseType]] = IterParseOption(default=None)
    use_fallback: Option[bool] = BooleanOption(default=True)
    use_xpath3: Option[bool] = BooleanOption(default=True)
    use_meta: Option[bool] = BooleanOption(default=True)
    loglevel: Option[Union[None, int, str]] = LogLevelOption(default=None)

    def create_xsd_resource(self, cls: type[XMLResource], source: SourceType) -> XMLResource:
        return cls(
            source=source,
            base_url=self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
        )


@dataclass
class DocumentSettings(CommonSettings):
    """
    Settings for XML instances that uses a specific configuration.
    """
    lazy: Option[Union[bool, int]] = LazyOption(default=False)
    thin_lazy: Option[bool] = BooleanOption(default=True)
    selector: Option[SelectorType] = SelectorOption(default=ElementSelector)


DEFAULT_SETTINGS = SchemaSettings()
_ACTIVE_SETTINGS = DEFAULT_SETTINGS


def install_settings(settings: SchemaSettings) -> SchemaSettings:
    return DEFAULT_SETTINGS
