#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import sys
import logging
from dataclasses import dataclass
from typing import cast, Any, Dict, Generic, List, Iterable, Iterator, Optional, \
    Type, TYPE_CHECKING, TypeVar, Union

from xmlschema.exceptions import XMLSchemaValueError, XMLSchemaTypeError
from xmlschema.aliases import DecodeType, DepthFillerType, ElementType, \
    ElementHookType, EncodeType, FillerType, NsmapType, ExtraValidatorType, \
    IterDecodeType, IterEncodeType, ModelParticleType, SchemaElementType, \
    SchemaType, ValidationHookType, ValueHookType
from xmlschema.translation import gettext as _
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.logger import format_xmlschema_stack
from xmlschema.namespaces import NamespaceMapper
from xmlschema.converters import XMLSchemaConverter
from xmlschema.resources import XMLResource

from xmlschema.validators.exceptions import XMLSchemaValidationError, \
    XMLSchemaChildrenValidationError

if TYPE_CHECKING:
    from xmlschema.validators.xsdbase import XsdValidator
    from xmlschema.validators.facets import XsdPatternFacets
    from xmlschema.validators.identities import XsdIdentity, IdentityCounter

if sys.version_info >= (3, 9):
    from collections import Counter
else:
    from typing import Counter

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


Self = TypeVar('Self', bound='ValidationContext')
ST = TypeVar('ST')
DT = TypeVar('DT')


@dataclass
class ValidationContext:
    """A context dataclass for handling validated decoding process."""
    errors: List[XMLSchemaValidationError]
    converter: Union[XMLSchemaConverter, NamespaceMapper]
    id_map: Counter[str]
    identities: Dict['XsdIdentity', 'IdentityCounter']
    inherited: Optional[Dict[str, str]]
    source: Union[XMLResource, Any]

    validation: str = 'strict'
    use_defaults: bool = True
    unordered: bool = False
    process_skipped: bool = False
    max_depth: Optional[int] = None

    # Used by XSD components
    elem: Optional[ElementType] = None
    id_list: Optional[List[Any]] = None
    patterns: Optional['XsdPatternFacets'] = None

    @property
    def namespaces(self) -> NsmapType:
        return self.converter.namespaces

    @classmethod
    def get_context(cls: Type[Self],
                    validator: Union[SchemaType, 'ValidationMixin[ST, DT]'],
                    source: Any,
                    validation: str,
                    **kwargs: Any) -> Self:

        check_validation_mode(validation)
        kwargs['validation'] = validation

        schema: SchemaType
        if hasattr(validator, 'schema'):
            schema = validator.schema
        else:
            schema = cast(SchemaType, validator)

        if kwargs.get('errors') is None:
            kwargs['errors'] = []
        if 'id_map' not in kwargs:
            kwargs['id_map'] = Counter[str]()
        if 'identities' not in kwargs:
            kwargs['identities'] = {}
        if 'inherited' not in kwargs:
            kwargs['inherited'] = {}

        if isinstance(source, XMLResource):
            kwargs['source'] = source
            if source.is_lazy():
                kwargs['use_location_hints'] = False
        elif cls is EncodeContext:
            kwargs['source'] = source
        elif is_etree_element(source) or is_etree_document(source):
            kwargs['source'] = XMLResource(source)
        else:
            kwargs['source'] = source

        converter = kwargs.get('converter')
        if converter is NamespaceMapper:
            kwargs['converter'] = NamespaceMapper(
                namespaces=kwargs.get('namespaces'),
                source=kwargs['source']
            )
        else:
            kwargs['converter'] = schema.get_converter(**kwargs)

        return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})

    def validation_error(self: Self,
                         validator: 'XsdValidator',
                         error: Union[str, Exception],
                         obj: Any = None,
                         elem: Optional[ElementType] = None) -> XMLSchemaValidationError:
        """
        Helper method for collecting or raising validation errors.

        :param validator: the XSD validator related with the error.
        :param error: an error instance or the detailed reason of failed validation.
        :param obj: the instance related to the error.
        :param elem: the element related to the error, can be `obj` for elements.
        """
        if elem is None and is_etree_element(obj):
            elem = cast(ElementType, obj)

        if isinstance(error, XMLSchemaValidationError):
            if error.namespaces is None and self.namespaces is not None:
                error.namespaces = self.namespaces
            if error.source is None and self.source is not None:
                error.source = self.source
            if error.obj is None and obj is not None:
                error.obj = obj
            elif is_etree_element(error.obj) and elem is not None:
                if elem.tag == error.obj.tag and elem is not error.obj:
                    error.obj = elem
        else:
            error = XMLSchemaValidationError(
                validator, obj, str(error), self.source, self.namespaces
            )

        if error.elem is None and elem is not None:
            error.elem = elem

        if self.validation == 'strict':  # and error.elem is not None:
            raise error

        if error.stack_trace is None and logger.level == logging.DEBUG:
            error.stack_trace = format_xmlschema_stack()
            logger.debug("Collect %r with traceback:\n%s", error, error.stack_trace)

        if error not in self.errors:
            self.errors.append(error)

        return error

    def children_validation_error(self: Self,
                                  validator: 'XsdValidator',
                                  elem: ElementType,
                                  index: int,
                                  particle: ModelParticleType,
                                  occurs: int = 0,
                                  expected: Optional[Iterable[SchemaElementType]] = None) -> None:

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
        if self.validation == 'strict':
            raise error

        error.elem = None  # replace with the element of the encoded tree
        self.errors.append(error)


@dataclass
class DecodeContext(ValidationContext):
    """A context dataclass for handling validated decoding process."""
    extra_validator: Optional[ExtraValidatorType] = None
    validation_hook: Optional[ValidationHookType] = None
    use_location_hints: bool = False

    # Other optional attributes used only for decoding
    decimal_type: Optional[Type[Any]] = None
    datetime_types: bool = False
    binary_types: bool = False
    filler: Optional[FillerType] = None
    fill_missing: bool = False
    keep_empty: bool = False
    keep_unknown: bool = False
    depth_filler: Optional[DepthFillerType] = None
    value_hook: Optional[ValueHookType] = None
    element_hook: Optional[ElementHookType] = None


@dataclass
class EncodeContext(ValidationContext):
    """A context dataclass for handling validated encoding process."""
    converter: XMLSchemaConverter


class ValidationMixin(Generic[ST, DT]):
    """
    Mixin for implementing XML data validators/decoders on XSD components.
    A derived class must implement the methods `raw_decode` and `raw_encode`.
    """
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
                                      max_depth, extra_validator):
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
        context = DecodeContext.get_context(
            validator=self,
            source=obj,
            validation='lax',
            converter=NamespaceMapper,
            use_defaults=use_defaults,
            namespaces=namespaces,
            max_depth=max_depth,
            extra_validator=extra_validator,
            validation_hook=validation_hook,
        )
        self.raw_decode(obj, context)
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
        context = DecodeContext.get_context(self, obj, validation, **kwargs)
        result = self.raw_decode(obj, context)
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
        context = EncodeContext.get_context(self, obj, validation, **kwargs)
        result = self.raw_encode(obj, context)
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
        context = DecodeContext.get_context(self, obj, validation, **kwargs)
        result = self.raw_decode(obj, context)
        yield from context.errors
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
        context = EncodeContext.get_context(self, obj, validation, **kwargs)
        result = self.raw_encode(obj, context)
        yield from context.errors
        yield result

    def raw_decode(self, obj: ST, context: DecodeContext, level: int = 0) -> DecodeType[DT]:
        """
        Internal decode method. Takes the same arguments as *decode*. Returns the \
        decoded data structure, usually a nested dict and/or list.
        """
        raise NotImplementedError()

    def raw_encode(self, obj: Any, context: EncodeContext, level: int = 0) -> Any:
        """
        Internal encode method. Takes the same arguments as *encode*. Returns a \
        tree of Elements or a fragment of it (e.g. an attribute value).
        """
        raise NotImplementedError()
