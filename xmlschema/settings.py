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
from typing import cast, Optional, Any
from xml.etree.ElementTree import Element

from elementpath.datatypes import AnyAtomicType

from xmlschema.aliases import XMLSourceType, BaseUrlType, DecodedValueType, \
    GlobalMapsType, SourceArgType
from xmlschema.exceptions import XMLSchemaTypeError, XMLResourceError
from xmlschema.translation import gettext as _
from xmlschema.arguments import BooleanOption, BaseUrlOption, AllowOption, \
    DefuseOption, LazyOption, BlockOption, UriMapperOption, IterParseOption, \
    SelectorOption, OpenerOption, PositiveIntOption, MaxDepthOption, LocationsOption, \
    ValidationOption, FillerOption, DepthFillerOption, ExtraValidatorOption, \
    ValidationHookOption, ValueHookOption, ElementHookOption, ElementTypeOption, \
    LogLevelOption
from xmlschema.utils.decoding import raw_encode_value, raw_encode_attributes
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.resources import XMLResource
from xmlschema.converters import XMLSchemaConverter, ConverterOption, ConverterType
from xmlschema.loaders import SchemaLoader, LoaderClassOption
from xmlschema.xpath import ElementSelector


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

    def get_xml_resource(self, source: SourceArgType) -> XMLResource:
        """
        Returns a :class:`XMLResource` instance for the given XML source using schema settings.
        """
        if isinstance(source, XMLResource):
            return source

        return XMLResource(
            source=source,
            base_url=self.base_url,
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

    def get_resource_from_data(self, obj: Any, tag: Optional[str] = None) -> XMLResource:
        """
        Returns a :class:`XMLResource` instance from XML data. Build a dummy
        Element if the source is a dictionary or an atomic value. Do not load
        XML data from locations or local streams.

        :param obj: XML source data.
        :param tag: XML tag to use for building the dummy element, if necessary.
        """
        if isinstance(obj, XMLResource):
            if obj.is_lazy():
                msg = _("component validation/decoding doesn't support lazy mode")
                raise XMLResourceError(msg)
            return obj
        elif is_etree_element(obj) or is_etree_document(obj):
            return self.get_xml_resource(obj)
        elif isinstance(obj, dict):
            attrib = raw_encode_attributes(obj)
            root = Element(tag or 'root', attrib=attrib)
            return self.get_xml_resource(root)
        elif obj is None or isinstance(obj, (AnyAtomicType, bytes)):
            root = Element(tag or 'root')
            root.text = raw_encode_value(cast(DecodedValueType, obj))
            return self.get_xml_resource(root)
        else:
            msg = _("incompatible source type {!r}")
            raise TypeError(msg.format(type(obj)))

    def get_schema_resource(self, source: XMLSourceType,
                            base_url: Optional[BaseUrlType] = None) -> XMLResource:
        """
        Returns a :class:`XMLResource` instance suitable for building schemas.
        Use only ElementTree library and fully loaded resources. The `lxml.etree`
        library cannot be used because components definitions sometimes require
        the build of additional elements that share a child.
        """
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

    validation: ValidationOption = ValidationOption(default='strict')

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
        settings = kwargs.pop('settings', _DEFAULT_SCHEMA_SETTINGS)
        if not isinstance(settings, SchemaSettings):
            msg = _("expected a SchemaSettings instance for 'settings', got {!r}'")
            raise XMLSchemaTypeError(msg.format(settings))
        return dc.replace(settings, **kwargs)

    @classmethod
    def update_defaults(cls, **kwargs: Any) -> None:
        global _DEFAULT_SCHEMA_SETTINGS
        _DEFAULT_SCHEMA_SETTINGS = SchemaSettings.get_settings(**kwargs)

    @classmethod
    def reset_defaults(cls) -> None:
        global _DEFAULT_SCHEMA_SETTINGS
        _DEFAULT_SCHEMA_SETTINGS = SchemaSettings.get_settings()

    def get_converter(self, converter: Optional[ConverterType] = None,
                      **kwargs: Any) -> XMLSchemaConverter:
        """
        Returns a new converter instance, with a fallback to the optional converter
        saved with the settings.

        :param converter: can be a converter class or instance. If not provided the \
        converter option of the schema settings is used.
        :param kwargs: optional arguments to initialize the converter instance.
        :return: a converter instance.
        """
        if converter is None:
            converter = self.converter

        if converter is None:
            return XMLSchemaConverter(**kwargs)
        elif isinstance(converter, XMLSchemaConverter):
            return converter.replace(**kwargs)
        elif isinstance(converter, type) and issubclass(converter, XMLSchemaConverter):
            return converter(**kwargs)  # noqa
        else:
            msg = _("'converter' argument must be a {0!r} subclass or instance: {1!r}")
            raise XMLSchemaTypeError(msg.format(XMLSchemaConverter, converter))

    def get_loader(self, maps: GlobalMapsType) -> SchemaLoader:
        return self.loader_class(
            maps=maps,
            locations=self.locations,
            use_fallback=self.use_fallback
        )


@dc.dataclass
class ValidationSettings:
    """Settings for XML instances that uses a specific configuration."""
    path: Optional[str] = None
    schema_path: Optional[str] = None
    use_defaults: BooleanOption = BooleanOption(default=False)
    max_depth: MaxDepthOption = MaxDepthOption(default=None)
    extra_validator: ExtraValidatorOption = ExtraValidatorOption(default=None)
    validation_hook: ValidationHookOption = ValidationHookOption(default=None)
    allow_empty: BooleanOption = BooleanOption(default=True)
    use_location_hints: BooleanOption = BooleanOption(default=False)


@dc.dataclass
class DecodingSettings(ValidationSettings):
    """Settings for decoding XML data."""
    validation: str = 'lax'
    process_namespaces: bool = True
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
    # errors: Optional[list[XMLSchemaValidationError]] = None


@dc.dataclass
class EncodingSettings(ValidationSettings):
    """Settings for encoding XML data."""
    converter: ConverterOption = ConverterOption(default=None)
    unordered: BooleanOption = BooleanOption(default=False)
    process_skipped: BooleanOption = BooleanOption(default=False)
    max_depth: MaxDepthOption = MaxDepthOption(default=None)
    untyped_data: BooleanOption = BooleanOption(default=False)
    etree_element_class: ElementTypeOption = ElementTypeOption(default=None)


# Default package settings
_DEFAULT_SCHEMA_SETTINGS = SchemaSettings()
_DEFAULT_VALIDATION_SETTINGS = ValidationSettings()
