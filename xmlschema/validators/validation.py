#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import copy
import decimal
import logging
from abc import abstractmethod
from collections import Counter
from collections.abc import Iterable, Iterator, MutableMapping
from typing import Any, cast, Generic, Optional, Type, TYPE_CHECKING, TypeVar, Union
from xml.etree.ElementTree import Element

from elementpath.datatypes import AnyAtomicType, AbstractDateTime, AbstractBinary, Duration

from xmlschema.exceptions import XMLSchemaValueError, XMLSchemaTypeError
from xmlschema.aliases import DecodeType, DepthFillerType, ElementType, \
    ElementHookType, EncodeType, ExtraValidatorType, FillerType, IterDecodeType, \
    IterEncodeType, ModelParticleType, NsmapType, SchemaElementType, \
    SchemaType, ValidationHookType, ValueHookType, ErrorsType, ClassInfoType, \
    DecodedValueType
from xmlschema.translation import gettext as _
from xmlschema.utils.decoding import EmptyType, raw_encode_value
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.logger import format_xmlschema_stack
from xmlschema.utils.qnames import get_prefixed_qname
from xmlschema.namespaces import NamespaceMapper
from xmlschema.converters import XMLSchemaConverter, ConverterType, get_converter
from xmlschema.resources import XMLResource

from .exceptions import XMLSchemaValidationError, \
    XMLSchemaChildrenValidationError, XMLSchemaDecodeError, XMLSchemaEncodeError

if TYPE_CHECKING:
    from .xsdbase import XsdValidator
    from .facets import XsdPatternFacets
    from .identities import XsdIdentity, IdentityCounter

logger = logging.getLogger('xmlschema')

XSD_VALIDATION_MODES = {'strict', 'lax', 'skip'}
"""
XML Schema validation modes
Ref.: https://www.w3.org/TR/xmlschema11-1/#key-va
"""


def check_validation_mode(validation: str) -> None:
    if not isinstance(validation, str):
        raise XMLSchemaTypeError(_("validation mode must be a string"))
    if validation not in XSD_VALIDATION_MODES:
        raise XMLSchemaValueError(_("validation mode can be 'strict', "
                                    "'lax' or 'skip': %r") % validation)


class ValidationContext:
    """
    A context class for handling validated decoding process. It stores together
    status-related fields, that are updated or set during the validation process,
    and parameters, as specific values or functions. Parameters can be provided
    as keyword-only arguments.
    """
    validation_only: bool = True

    # Common status: set once, updated by validators.
    errors: ErrorsType
    converter: Union[XMLSchemaConverter, NamespaceMapper]
    id_map: Counter[str]
    identities: dict['XsdIdentity', 'IdentityCounter']
    source: Union[XMLResource, Any]

    # Set and used by one or more XSD components.
    elem: Optional[ElementType]
    attribute: Optional[str]
    id_list: Optional[list[Any]]
    inherited: dict[str, str]
    patterns: Optional['XsdPatternFacets']
    level: int
    namespaces: MutableMapping[str, str]

    __slots__ = ('errors', 'converter', 'id_map', 'identities', 'elem', 'namespaces',
                 'attribute', 'id_list', 'inherited', 'level', 'max_depth', '__dict__')

    def __init__(self,
                 source: Any,
                 validation: str = 'strict',
                 converter: Optional[ConverterType] = None,
                 level: int = 0,
                 elem: Optional[ElementType] = None,
                 check_identities: bool = False,
                 use_defaults: bool = True,
                 process_skipped: bool = False,
                 max_depth: Optional[int] = None,
                 errors: Optional[ErrorsType] = None,
                 **kwargs: Any) -> None:

        check_validation_mode(validation)
        self.source = source
        self.validation = validation
        self.errors = [] if errors is None else errors
        self.id_map = Counter[str]()
        self.identities = {}
        self.inherited = {}
        self.level = level
        self.elem = elem
        self.attribute = None
        self.id_list = None
        self.patterns = None
        self.check_identities = check_identities
        self.use_defaults = use_defaults
        self.process_skipped = process_skipped
        self.max_depth = max_depth

        if self.validation_only:
            self.converter = NamespaceMapper(
                kwargs.get('namespaces'), source=self.source
            )
        else:
            self.converter = get_converter(converter, source=source, **kwargs)
        self.namespaces = self.converter.namespaces

    def __copy__(self) -> 'ValidationContext':
        context = object.__new__(self.__class__)
        context.__dict__.update(self.__dict__)

        context.errors = self.errors.copy()
        context.id_map = self.id_map.copy()
        context.identities = self.identities.copy()
        context.inherited = self.inherited.copy()
        context.id_list = self.id_list if self.id_list is None else self.id_list.copy()
        context.elem = self.elem
        context.attribute = self.attribute
        context.level = self.level
        context.max_depth = self.max_depth

        if self.converter.xmlns_processing == 'none':
            context.converter = self.converter
            context.namespaces = self.namespaces
        else:
            context.converter = copy.copy(self.converter)
            context.namespaces = context.converter.namespaces
        return context

    def clear(self) -> None:
        self.errors.clear()
        self.id_map.clear()
        self.identities.clear()
        self.inherited.clear()
        self.level = 0
        self.elem = None
        self.attribute = None
        self.id_list = None
        self.patterns = None

    @property
    def root_namespace(self) -> Optional[str]:
        if not isinstance(self.source, XMLResource):
            return None
        else:
            return self.source.namespace

    def raise_or_collect(self, validation: str, error: XMLSchemaValidationError) \
            -> XMLSchemaValidationError:
        if error.elem is None and self.elem is not None:
            error.elem = self.elem

        if self.attribute is not None and error.reason is not None \
                and not error.reason.startswith('attribute '):
            name = get_prefixed_qname(self.attribute, self.namespaces)
            value = raw_encode_value(error.obj)
            error.reason = _('attribute {0}={1!r}: {2}').format(name, value, error.reason)

        if validation == 'strict':
            raise error

        if error.stack_trace is None and logger.level == logging.DEBUG:
            error.stack_trace = format_xmlschema_stack('xmlschema/validators')
            logger.debug("Collect %r with traceback:\n%s", error, error.stack_trace)

        if validation == 'lax':
            self.errors.append(error)
        return error

    def validation_error(self,
                         validation: str,
                         validator: 'XsdValidator',
                         error: Union[str, Exception],
                         obj: Any = None) -> XMLSchemaValidationError:
        """
        Helper method for collecting or raising validation errors.

        :param validation:
        :param validator: the XSD validator related with the error.
        :param error: an error instance or the detailed reason of failed validation.
        :param obj: the instance related to the error.
        """
        if not isinstance(error, XMLSchemaValidationError):
            error = XMLSchemaValidationError(
                validator, obj, str(error), self.source, self.namespaces
            )
        else:
            if error.obj is None and obj is not None:
                error.obj = obj

            error.source = self.source
            error.namespaces = self.namespaces

        return self.raise_or_collect(validation, error)

    def children_validation_error(
            self, validation: str, validator: 'XsdValidator', elem: ElementType,
            index: int, particle: ModelParticleType, occurs: int = 0,
            expected: Optional[Iterable[SchemaElementType]] = None) \
            -> XMLSchemaValidationError:

        error = XMLSchemaChildrenValidationError(
            validator=validator,
            elem=elem,
            index=index,
            particle=particle,
            occurs=occurs,
            expected=expected,
            source=self.source,
            namespaces=self.namespaces,
        )
        return self.raise_or_collect(validation, error)


class DecodeContext(ValidationContext):
    """A context for handling validated decoding processes."""
    source: XMLResource

    def __init__(self,
                 source: Any,
                 validation: str = 'strict',
                 converter: Optional[ConverterType] = None,
                 level: int = 0,
                 elem: Optional[ElementType] = None,
                 *,
                 validation_only: bool = False,
                 check_identities: bool = False,
                 use_defaults: bool = True,
                 process_skipped: bool = False,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None,
                 validation_hook: Optional[ValidationHookType] = None,
                 use_location_hints: bool = False,
                 decimal_type: Optional[Union[Type[str], Type[float]]] = None,
                 datetime_types: bool = False,
                 binary_types: bool = False,
                 filler: Optional[FillerType] = None,
                 fill_missing: bool = False,
                 keep_empty: bool = False,
                 keep_unknown: bool = False,
                 depth_filler: Optional[DepthFillerType] = None,
                 value_hook: Optional[ValueHookType] = None,
                 element_hook: Optional[ElementHookType] = None,
                 errors: Optional[list[XMLSchemaValidationError]] = None,
                 **kwargs: Any) -> None:

        if not isinstance(source, XMLResource):
            # source is not a XMLResource, then create a new resource from
            # source element or a dummy document from data.
            if is_etree_element(source) or is_etree_document(source):
                source = XMLResource(source)
            elif elem is not None:
                source = XMLResource(elem)
            elif isinstance(source, dict):
                root = Element('root', attrib=source)
                source = XMLResource(root)
            elif source is None or isinstance(source, (AnyAtomicType, bytes)):
                root = Element('root')
                root.text = raw_encode_value(cast(DecodedValueType, source))
                source = XMLResource(root)
            else:
                raise XMLSchemaTypeError(
                    "incompatible type {!r} for source argument".format(type(source))
                )

        self.validation_only = validation_only
        self.extra_validator = extra_validator
        self.validation_hook = validation_hook
        self.use_location_hints = use_location_hints
        self.decimal_type = decimal_type
        self.filler = filler
        self.fill_missing = fill_missing
        self.keep_empty = keep_empty
        self.keep_unknown = keep_unknown
        self.depth_filler = depth_filler
        self.value_hook = value_hook
        self.element_hook = element_hook

        keep_datatypes: list[type[DecodedValueType]] = [int, float, list]
        if decimal_type is None:
            keep_datatypes.append(decimal.Decimal)
        if datetime_types:
            keep_datatypes.append(AbstractDateTime)
            keep_datatypes.append(Duration)
        if binary_types:
            keep_datatypes.append(AbstractBinary)
        self.keep_datatypes: ClassInfoType[DecodedValueType] = tuple(keep_datatypes)

        super().__init__(source, validation, converter, level, elem,
                         check_identities, use_defaults, process_skipped,
                         max_depth, errors, **kwargs)

    def decode_error(self,
                     validation: str,
                     validator: 'XsdValidator',
                     obj: Any,
                     decoder: Any,
                     error: Union[str, Exception]) -> XMLSchemaValidationError:
        error = XMLSchemaDecodeError(
            validator=validator,
            obj=obj,
            decoder=decoder,
            reason=str(error),
            source=self.source,
            namespaces=self.namespaces,
        )
        return self.raise_or_collect(validation, error)


class EncodeContext(ValidationContext):
    """A context for handling validated encoding processes."""
    source: Any
    converter: XMLSchemaConverter
    validation_only = False

    def __init__(self,
                 source: Any,
                 validation: str = 'strict',
                 converter: Optional[ConverterType] = None,
                 level: int = 0,
                 elem: Optional[ElementType] = None,
                 *,
                 check_identities: bool = False,
                 use_defaults: bool = True,
                 unordered: bool = False,
                 process_skipped: bool = False,
                 max_depth: Optional[int] = None,
                 untyped_data: bool = False,
                 errors: Optional[list[XMLSchemaValidationError]] = None,
                 **kwargs: Any) -> None:

        self.unordered = unordered
        self.untyped_data = untyped_data
        super().__init__(source, validation, converter, level, elem,
                         check_identities, use_defaults, process_skipped,
                         max_depth, errors, **kwargs)

    def encode_error(self,
                     validation: str,
                     validator: 'XsdValidator',
                     obj: Any,
                     encoder: Any,
                     error: Union[str, Exception]) -> XMLSchemaValidationError:
        error = XMLSchemaEncodeError(
            validator=validator,
            obj=obj,
            encoder=encoder,
            reason=str(error),
            source=self.source,
            namespaces=self.namespaces,
        )
        return self.raise_or_collect(validation, error)

    @property
    def padding(self) -> str:
        return '\n' + ' ' * self.converter.indent * self.level

    def create_element(self, tag: str) -> Element:
        self.elem = self.converter.etree_element(tag, level=self.level)
        return self.elem

    def set_element_content(self, elem: Element, text: Optional[str],
                            children: list[Element]) -> None:
        if children:
            if children[-1].tail is None:
                children[-1].tail = self.padding
            else:
                children[-1].tail = children[-1].tail.strip() + self.padding

            elem.text = text or self.padding
            elem.extend(children)
        else:
            elem.text = text


ST = TypeVar('ST')
DT = TypeVar('DT')


class ValidationMixin(Generic[ST, DT]):
    """
    Mixin for implementing XML data validators/decoders on XSD components.
    A derived class must implement the methods `raw_decode` and `raw_encode`.
    """
    schema: SchemaType

    def validate(self, obj: ST,
                 use_defaults: bool = True,
                 namespaces: Optional[NsmapType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None,
                 validation_hook: Optional[ValidationHookType] = None) -> None:
        """
        Validates XML data against the XSD schema/component instance.

        :param obj: the XML data. Can be a string for an attribute or a simple type \
        validators, or an ElementTree's Element otherwise.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param max_depth: maximum level of validation, for default there is no limit.
        :param extra_validator: an optional function for performing non-standard \
        validations on XML data. The provided function is called for each traversed \
        element, with the XML element as 1st argument and the corresponding XSD \
        element as 2nd argument. It can be also a generator function and has to \
        raise/yield :exc:`xmlschema.XMLSchemaValidationError` exceptions.
        :param validation_hook: an optional function for stopping or changing \
        validation at element level. The provided function must accept two arguments, \
        the XML element and the matching XSD element. If the value returned by this \
        function is evaluated to false then the validation process continues without \
        changes, otherwise the validation process is stopped or changed. If the value \
        returned is a validation mode the validation process continues changing the \
        current validation mode to the returned value, otherwise the element and its \
        content are not processed. The function can also stop validation suddenly \
        raising a `XmlSchemaStopValidation` exception.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the XML data instance is invalid.
        """
        for error in self.iter_errors(obj, use_defaults, namespaces,
                                      max_depth, extra_validator, validation_hook):
            raise error

    def is_valid(self, obj: ST,
                 use_defaults: bool = True,
                 namespaces: Optional[NsmapType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None,
                 validation_hook: Optional[ValidationHookType] = None) -> bool:
        """
        Like :meth:`validate` except that does not raise an exception but returns
        ``True`` if the XML data instance is valid, ``False`` if it is invalid.
        """
        error = next(self.iter_errors(obj, use_defaults, namespaces, max_depth,
                                      extra_validator, validation_hook), None)
        return error is None

    def iter_errors(self, obj: ST,
                    use_defaults: bool = True,
                    namespaces: Optional[NsmapType] = None,
                    max_depth: Optional[int] = None,
                    extra_validator: Optional[ExtraValidatorType] = None,
                    validation_hook: Optional[ValidationHookType] = None) \
            -> Iterator[XMLSchemaValidationError]:
        """
        Creates an iterator for the errors generated by the validation of an XML data against
        the XSD schema/component instance. Accepts the same arguments of :meth:`validate`.
        """
        context = DecodeContext(
            source=obj,
            namespaces=namespaces,
            validation_only=True,
            use_defaults=use_defaults,
            max_depth=max_depth,
            extra_validator=extra_validator,
            validation_hook=validation_hook,
        )
        self.raw_decode(obj, 'lax', context)
        yield from context.errors

    def decode(self, obj: ST, validation: str = 'strict', **kwargs: Any) -> DecodeType[DT]:
        """
        Decodes XML data.

        :param obj: the XML data. Can be a string for an attribute or for simple type \
        components or a dictionary for an attribute group or an ElementTree's \
        Element for other components.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_decode`.
        :return: a dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
        a simple data type object otherwise. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the decoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        converter = kwargs.pop('converter', None)
        if converter is None:
            converter = self.schema.converter

        context = DecodeContext(obj, validation, converter, **kwargs)
        result = self.raw_decode(obj, validation, context)
        if isinstance(result, EmptyType):
            return (None, context.errors) if validation == 'lax' else None
        return (result, context.errors) if validation == 'lax' else result

    def encode(self, obj: Any, validation: str = 'strict', **kwargs: Any) -> EncodeType[Any]:
        """
        Encodes data to XML.

        :param obj: the data to be encoded to XML.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_encode`.
        :return: An element tree's Element if the original data is a structured data or \
        a string if it's simple type datum. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the encoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the object is not encodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        converter = kwargs.pop('converter', None)
        if converter is None:
            converter = self.schema.converter

        context = EncodeContext(obj, validation, converter, **kwargs)
        result = self.raw_encode(obj, validation, context)
        if isinstance(result, EmptyType):
            return (None, context.errors) if validation == 'lax' else None
        return (result, context.errors) if validation == 'lax' else result

    def iter_decode(self, obj: ST, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[DT]:
        """
        Creates an iterator for decoding an XML source to a Python object.

        :param obj: the XML data.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoder API.
        :return: Yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        converter = kwargs.pop('converter', None)
        if converter is None:
            converter = self.schema.converter

        context = DecodeContext(obj, validation, converter, **kwargs)
        result = self.raw_decode(obj, validation, context)
        yield from context.errors
        context.errors.clear()
        if not isinstance(result, EmptyType):
            yield result

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[Any]:
        """
        Creates an iterator for encoding data to an Element tree.

        :param obj: The data that has to be encoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoder API.
        :return: Yields an Element, eventually preceded by a sequence of validation \
        or encoding errors.
        """
        converter = kwargs.pop('converter', None)
        if converter is None:
            converter = self.schema.converter

        context = EncodeContext(obj, validation, converter, **kwargs)
        result = self.raw_encode(obj, validation, context)
        yield from context.errors
        context.errors.clear()
        if not isinstance(result, EmptyType):
            yield result

    @abstractmethod
    def raw_decode(self, obj: ST, validation: str, context: DecodeContext) \
            -> Union[DT, EmptyType]:
        """
        Internal decode method. Takes the same arguments as *decode*, but keyword arguments
        are replaced with a decode context. Returns a decoded data structure, usually a
        nested dict and/or list.
        """
        raise NotImplementedError()

    @abstractmethod
    def raw_encode(self, obj: Any, validation: str, context: EncodeContext) -> Any:
        """
        Internal encode method. Takes the same arguments as *encode*, but keyword arguments
        are replaced with a decode context. Returns a tree of Elements or a fragment of it
        (e.g. an attribute value).
        """
        raise NotImplementedError()
