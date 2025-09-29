#
# Copyright (c), 2016-2025, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Package settings for setup protection defaults."""
import dataclasses as dc
from functools import partial
from typing import cast, Optional, Any

from xmlschema.aliases import LocationsType, XMLSourceType, BaseUrlType
from xmlschema.arguments import FillerOption, DepthFillerOption, ExtraValidatorOption, \
    ValidationHookOption, ValueHookOption, ElementHookOption, ElementTypeOption, LogLevelOption
from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.translation import gettext as _
from xmlschema.arguments import Option, BooleanOption, BaseUrlOption, AllowOption, \
    DefuseOption, LazyOption, BlockOption, UriMapperOption, IterParseOption, \
    SelectorOption, OpenerOption, PositiveIntOption, validate_type, validate_subclass, \
    MaxDepthOption
from xmlschema.utils.misc import is_subclass

from xmlschema.locations import NamespaceResourcesMap
from xmlschema.resources import XMLResource
from xmlschema.loaders import SchemaLoader
from xmlschema.converters import ConverterType, XMLSchemaConverter
from xmlschema.xpath import ElementSelector

LOCATIONS_TYPES = (tuple, dict, list, NamespaceResourcesMap)


class ConverterOption(Option[Optional[ConverterType]]):
    def validated_value(self, value: Any) -> Optional[ConverterType]:
        if value is None or isinstance(value, XMLSchemaConverter) \
                or is_subclass(value, XMLSchemaConverter):
            return cast(ConverterType, value)
        msg = _("invalid type {!r} for {}, must be a {!r} instance/subclass or None")
        raise XMLSchemaTypeError(msg.format(type(value), self, XMLSchemaConverter))


class LocationsOption(Option[Optional[LocationsType]]):
    _validators = partial(validate_type, types=LOCATIONS_TYPES, none=True),


class LoaderClassOption(Option[type[SchemaLoader]]):
    _validators = partial(validate_subclass, cls=SchemaLoader, none=True),

    def validated_value(self, value: Any) -> type[SchemaLoader]:
        if value is None:
            return self._default
        return super().validated_value(value)

        return cast(type[SchemaLoader], value)


@dc.dataclass
class ResourceSettings:
    """Settings for accessing XML resources."""

    base_url: BaseUrlOption = BaseUrlOption(default=None)
    """The effective base URL used for completing relative locations."""

    allow: AllowOption = AllowOption(default='all')
    """
    The security mode for accessing resource locations. Can be 'all', 'remote',
    'local' or 'sandbox'. Default is 'all' that means all types of URLs are allowed.
    With 'remote' only remote resource URLs are allowed. With 'local' only file paths
    and URLs are allowed. With 'sandbox' only file paths and URLs that are under the
    directory path identified by source or by the *base_url* argument are allowed.
    """

    defuse: DefuseOption = DefuseOption(default='remote')
    """
    Defines when to defuse XML data using a `SafeXMLParser`. Can be 'always',
    'remote' or 'never'. For default defuses only remote XML data.
    """

    timeout: PositiveIntOption = PositiveIntOption(default=300)
    """The timeout in seconds for accessing remote resources. Default is `300` seconds."""

    lazy: LazyOption = LazyOption(default=False)
    """
    Defines if the XML data is fully loaded and processed in memory, that is for default.
    Setting `True` or a positive integer only the root element of the source is loaded
    when the XMLResource instance is created. The root and the other parts are reloaded
    at each iteration, pruning the processed subtrees at the depth defined by this option
    (`True` means 1).
    """

    thin_lazy: BooleanOption = BooleanOption(default=True)
    """
    For default, in order to reduce the memory usage, during the iteration of a lazy
    resource deletes also the preceding elements after the use. Setting `False` only
    descendant elements are deleted at the depth defined by *lazy* option.
    """

    block: BlockOption = BlockOption(default=None)
    """
    Defines which types of sources are blocked for security reasons. For default none
    of possible types are blocked. Set with a space separated string of words, choosing
    between 'text', 'file', 'io', 'url' and 'tree' or a tuple/list of them to select
    which types are blocked.
    """

    uri_mapper: UriMapperOption = UriMapperOption(default=None)
    """
    Optional URI mapper for using relocated or URN-addressed resources. Can be a
    dictionary or a function that takes the URI string and returns a URL, or the
    argument if there is no mapping for it.
    """

    opener: OpenerOption = OpenerOption(default=None)
    """
    Optional :class:`OpenerDirector` to use for open XML resources.
    For default the opener installed globally for *urlopen* is used.
    """

    iterparse: IterParseOption = IterParseOption(default=None)
    """
    Optional callable that returns an iterator parser used for building the
    XML trees. For default *ElementTree.iterparse* is used. XSD schemas are
    built using only *ElementTree.iterparse*, because *lxml* is unsuitable
    for multitree structures and for pruning.
    """

    selector: SelectorOption = SelectorOption(default=ElementSelector)
    """The selector class to use for XPath element selectors."""

    @classmethod
    def get_settings(cls, **kwargs: Any) -> 'ResourceSettings':
        if 'settings' not in kwargs:
            return dc.replace(_DEFAULT_SCHEMA_SETTINGS, **kwargs)

        settings = kwargs.pop('settings')
        if not isinstance(settings, cls):
            raise XMLSchemaTypeError('settings is not an instance of SchemaSettings')
        return dc.replace(settings, **kwargs)

    @classmethod
    def update_defaults(cls, **kwargs: Any) -> None:
        global _DEFAULT_DOCUMENT_SETTINGS
        _DEFAULT_DOCUMENT_SETTINGS = cls.get_settings(**kwargs)

    @classmethod
    def reset_defaults(cls) -> None:
        global _DEFAULT_DOCUMENT_SETTINGS
        _DEFAULT_DOCUMENT_SETTINGS = cls.get_settings()

    def get_xml_resource(self, source: XMLSourceType,
                         base_url: Optional[BaseUrlType] = None) -> XMLResource:
        return XMLResource(
            source=source,
            base_url=base_url or self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            lazy=self.lazy,
            thin_lazy=self.thin_lazy,
            block=self.block,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
            iterparse=self.iterparse,
            selector=self.selector,
        )

    def get_xsd_resource(self, source: XMLSourceType,
                         base_url: Optional[BaseUrlType] = None) -> XMLResource:
        return XMLResource(
            source=source,
            base_url=base_url or self.base_url,
            allow=self.allow,
            defuse=self.defuse,
            timeout=self.timeout,
            block=self.block,
            uri_mapper=self.uri_mapper,
            opener=self.opener,
        )


@dc.dataclass
class SchemaSettings(ResourceSettings):
    """Settings for schemas."""
    converter: ConverterOption = ConverterOption(default=None)
    """The converter to use for decoding/encoding XML data."""

    locations: LocationsOption = LocationsOption(default=None)
    """Optional schema extra location hints with additional namespaces to import."""

    use_location_hints: BooleanOption = BooleanOption(default=False)
    """
    Schema locations hints provided within XML data for dynamic schema loading.
    For default these hints are ignored by schemas in order to avoid the change of
    schema instance. Set this option to `True` to activate dynamic schema loading.
    """

    loader_class: LoaderClassOption = LoaderClassOption(default=SchemaLoader)

    use_fallback: BooleanOption = BooleanOption(default=True)
    use_xpath3: BooleanOption = BooleanOption(default=True)
    use_meta: BooleanOption = BooleanOption(default=True)
    loglevel: LogLevelOption = LogLevelOption(default=None)

    @classmethod
    def get_settings(cls, **kwargs: Any) -> 'SchemaSettings':
        if 'settings' not in kwargs:
            return dc.replace(_DEFAULT_SCHEMA_SETTINGS, **kwargs)

        settings = kwargs.pop('settings')
        if not isinstance(settings, cls):
            raise XMLSchemaTypeError('settings is not an instance of SchemaSettings')
        return dc.replace(settings, **kwargs)

    @classmethod
    def update_defaults(cls, **kwargs: Any) -> None:
        global _DEFAULT_SCHEMA_SETTINGS
        _DEFAULT_SCHEMA_SETTINGS = SchemaSettings.get_settings(**kwargs)

    @classmethod
    def reset_defaults(cls) -> None:
        global _DEFAULT_SCHEMA_SETTINGS
        _DEFAULT_SCHEMA_SETTINGS = SchemaSettings.get_settings()


@dc.dataclass
class DecodingSettings:
    """Settings for decoding XML data."""
    use_defaults: BooleanOption = BooleanOption(default=True)
    use_location_hints: BooleanOption = BooleanOption(default=False)

    decimal_type: Optional[type[Any]] = None
    datetime_types: BooleanOption = BooleanOption(default=False)
    binary_types: BooleanOption = BooleanOption(default=False)
    converter: ConverterOption = ConverterOption(default=None)
    filler: FillerOption = FillerOption(default=None)
    fill_missing: BooleanOption = BooleanOption(default=False)
    keep_empty: BooleanOption = BooleanOption(default=False)
    keep_unknown: BooleanOption = BooleanOption(default=False)
    process_skipped: BooleanOption = BooleanOption(default=False)
    max_depth: MaxDepthOption = MaxDepthOption(default=None)
    depth_filler: DepthFillerOption = DepthFillerOption(default=None)
    extra_validator: ExtraValidatorOption = ExtraValidatorOption(default=None)
    validation_hook: ValidationHookOption = ValidationHookOption(default=None)
    value_hook: ValueHookOption = ValueHookOption(default=None)
    element_hook: ElementHookOption = ElementHookOption(default=None)


@dc.dataclass
class EncodingSettings:
    """Settings for encoding XML data."""
    use_defaults: BooleanOption = BooleanOption(default=False)
    converter: ConverterOption = ConverterOption(default=None)
    unordered: BooleanOption = BooleanOption(default=False)
    process_skipped: BooleanOption = BooleanOption(default=False)
    max_depth: MaxDepthOption = MaxDepthOption(default=None)
    untyped_data: BooleanOption = BooleanOption(default=False)
    etree_element_class: ElementTypeOption = ElementTypeOption(default=None)


@dc.dataclass
class DocumentSettings(SchemaSettings):
    """Settings for XML instances that uses a specific configuration."""

    use_location_hints: BooleanOption = BooleanOption(default=True)
    """
    Schema locations hints provided within XML data for dynamic schema loading.
    Disabled at schema level, for default these hints are enabled at document level.
    """

    dummy_schema: BooleanOption = BooleanOption(default=False)
    max_depth: MaxDepthOption = MaxDepthOption(default=None)
    extra_validator: ExtraValidatorOption = ExtraValidatorOption(default=None)
    validation_hook: ValidationHookOption = ValidationHookOption(default=None)
    allow_empty: BooleanOption = BooleanOption(default=True)

    @classmethod
    def get_settings(cls, **kwargs: Any) -> 'DocumentSettings':
        if 'settings' not in kwargs:
            return cast(DocumentSettings, dc.replace(_DEFAULT_DOCUMENT_SETTINGS, **kwargs))

        settings = kwargs.pop('settings')
        if not isinstance(settings, cls):
            raise XMLSchemaTypeError('settings is not an instance of SchemaSettings')
        return dc.replace(settings, **kwargs)

    @classmethod
    def update_defaults(cls, **kwargs: Any) -> None:
        global _DEFAULT_DOCUMENT_SETTINGS
        _DEFAULT_DOCUMENT_SETTINGS = cls.get_settings(**kwargs)

    @classmethod
    def reset_defaults(cls) -> None:
        global _DEFAULT_DOCUMENT_SETTINGS
        _DEFAULT_DOCUMENT_SETTINGS = cls.get_settings()


# Default package settings
_DEFAULT_RESOURCE_SETTINGS = ResourceSettings()
_DEFAULT_SCHEMA_SETTINGS = SchemaSettings()
_DEFAULT_DOCUMENT_SETTINGS = DocumentSettings()
