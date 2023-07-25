#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains classes for XML Schema simple data types.
"""
from decimal import DecimalException
from typing import cast, Any, Callable, Dict, Iterator, List, \
    Optional, Set, Union, Tuple, Type
from xml.etree import ElementTree

from ..aliases import ElementType, AtomicValueType, ComponentClassType, \
    IterDecodeType, IterEncodeType, BaseXsdType, SchemaType, DecodedValueType, \
    EncodedValueType
from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..names import XSD_NAMESPACE, XSD_ANY_TYPE, XSD_SIMPLE_TYPE, XSD_PATTERN, \
    XSD_ANY_ATOMIC_TYPE, XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE, \
    XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, \
    XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_WHITE_SPACE, XSD_ENUMERATION,\
    XSD_LIST, XSD_ANY_SIMPLE_TYPE, XSD_UNION, XSD_RESTRICTION, XSD_ANNOTATION, \
    XSD_ASSERTION, XSD_ID, XSD_IDREF, XSD_FRACTION_DIGITS, XSD_TOTAL_DIGITS, \
    XSD_EXPLICIT_TIMEZONE, XSD_ERROR, XSD_ASSERT, XSD_QNAME
from ..translation import gettext as _
from ..helpers import local_name

from .exceptions import XMLSchemaValidationError, XMLSchemaEncodeError, \
    XMLSchemaDecodeError, XMLSchemaParseError
from .xsdbase import XsdComponent, XsdType, ValidationMixin
from .facets import XsdFacet, XsdWhiteSpaceFacet, XsdPatternFacets, \
    XsdEnumerationFacets, XsdAssertionFacet, XSD_10_FACETS_BUILDERS, \
    XSD_11_FACETS_BUILDERS, XSD_10_FACETS, XSD_11_FACETS, XSD_10_LIST_FACETS, \
    XSD_11_LIST_FACETS, XSD_10_UNION_FACETS, XSD_11_UNION_FACETS, MULTIPLE_FACETS

FacetsValueType = Union[XsdFacet, Callable[[Any], None], List[XsdAssertionFacet]]
PythonTypeClasses = Type[Any]


class XsdSimpleType(XsdType, ValidationMixin[Union[str, bytes], DecodedValueType]):
    """
    Base class for simpleTypes definitions. Generally used only for
    instances of xs:anySimpleType.

    ..  <simpleType
          final = (#all | List of (list | union | restriction | extension))
          id = ID
          name = NCName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (restriction | list | union))
        </simpleType>
    """
    _special_types = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE}
    _ADMITTED_TAGS = {XSD_SIMPLE_TYPE}
    copy: Callable[['XsdSimpleType'], 'XsdSimpleType']

    block: str = ''
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    white_space: Optional[str] = None
    patterns = None
    validators: Union[Tuple[()], List[Union[XsdFacet, Callable[[Any], None]]]] = ()
    allow_empty = True
    facets: Dict[Optional[str], FacetsValueType]

    python_type: PythonTypeClasses
    instance_types: Union[PythonTypeClasses, Tuple[PythonTypeClasses]]

    # Unicode string as default datatype for XSD simple types
    python_type = instance_types = to_python = from_python = str

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent] = None,
                 name: Optional[str] = None,
                 facets: Optional[Dict[Optional[str], FacetsValueType]] = None) -> None:

        super(XsdSimpleType, self).__init__(elem, schema, parent, name)
        if not hasattr(self, 'facets'):
            self.facets = facets if facets is not None else {}

    def __setattr__(self, name: str, value: Any) -> None:
        super(XsdSimpleType, self).__setattr__(name, value)
        if name == 'facets':
            if not isinstance(self, XsdAtomicBuiltin):
                self._parse_facets(value)

            if self.min_length:
                self.allow_empty = False

            white_space = getattr(self.get_facet(XSD_WHITE_SPACE), 'value', None)
            if white_space is not None:
                self.white_space = white_space

            patterns = self.get_facet(XSD_PATTERN)
            if isinstance(patterns, XsdPatternFacets):
                self.patterns = patterns
                if all(p.match('') is None for p in patterns.patterns):
                    self.allow_empty = False

            enumeration = self.get_facet(XSD_ENUMERATION)
            if isinstance(enumeration, XsdEnumerationFacets) \
                    and '' not in enumeration.enumeration:
                self.allow_empty = False

            if value:
                validators: List[Union[XsdFacet, Callable[[Any], None]]]
                if None in value:
                    validators = [value[None]]  # Use only the validator function!
                else:
                    validators = [v for k, v in value.items()
                                  if k not in {XSD_WHITE_SPACE, XSD_PATTERN, XSD_ASSERTION}]
                if XSD_ASSERTION in value:
                    assertions: Union[XsdAssertionFacet, List[XsdAssertionFacet]]
                    assertions = value[XSD_ASSERTION]
                    if isinstance(assertions, list):
                        validators.extend(assertions)
                    else:
                        validators.append(assertions)
                if validators:
                    self.validators = validators

    def _parse_facets(self, facets: Any) -> None:
        base_type: Any

        if facets and self.base_type is not None:
            if isinstance(self.base_type, XsdSimpleType):
                if self.base_type.name == XSD_ANY_SIMPLE_TYPE:
                    msg = _("facets not allowed for a direct derivation of xs:anySimpleType")
                    self.parse_error(msg)
            elif self.base_type.has_simple_content():
                if self.base_type.content.name == XSD_ANY_SIMPLE_TYPE:
                    msg = _("facets not allowed for a direct content "
                            "derivation of xs:anySimpleType")
                    self.parse_error(msg)

        # Checks the applicability of the facets
        if any(k not in self.admitted_facets for k in facets if k is not None):
            msg = _("one or more facets are not applicable, admitted set is {!r}")
            self.parse_error(msg.format({local_name(e) for e in self.admitted_facets if e}))

        # Check group base_type
        base_type = {t.base_type for t in facets.values() if isinstance(t, XsdFacet)}
        if len(base_type) > 1:
            msg = _("facet group must have the same base type: %r")
            self.parse_error(msg % base_type)
        base_type = base_type.pop() if base_type else None

        # Checks length based facets
        length = getattr(facets.get(XSD_LENGTH), 'value', None)
        min_length = getattr(facets.get(XSD_MIN_LENGTH), 'value', None)
        max_length = getattr(facets.get(XSD_MAX_LENGTH), 'value', None)
        if length is not None:
            if length < 0:
                self.parse_error(_("'length' value must be non a negative integer"))

            if min_length is not None:
                if min_length > length:
                    msg = _("'minLength' value must be less than or equal to 'length'")
                    self.parse_error(msg)
                min_length_facet = base_type.get_facet(XSD_MIN_LENGTH)
                length_facet = base_type.get_facet(XSD_LENGTH)
                if (min_length_facet is None
                        or (length_facet is not None
                            and length_facet.base_type == min_length_facet.base_type)):
                    msg = _("cannot specify both 'length' and 'minLength'")
                    self.parse_error(msg)

            if max_length is not None:
                if max_length < length:
                    msg = _("'maxLength' value must be greater or equal to 'length'")
                    self.parse_error(msg)

                max_length_facet = base_type.get_facet(XSD_MAX_LENGTH)
                length_facet = base_type.get_facet(XSD_LENGTH)
                if max_length_facet is None \
                        or (length_facet is not None
                            and length_facet.base_type == max_length_facet.base_type):
                    msg = _("cannot specify both 'length' and 'maxLength'")
                    self.parse_error(msg)

            min_length = max_length = length
        elif min_length is not None or max_length is not None:
            min_length_facet = base_type.get_facet(XSD_MIN_LENGTH)
            max_length_facet = base_type.get_facet(XSD_MAX_LENGTH)
            if min_length is not None:
                if min_length < 0:
                    msg = _("'minLength' value must be a non negative integer")
                    self.parse_error(msg)
                if max_length is not None and max_length < min_length:
                    msg = _("'maxLength' value is less than 'minLength'")
                    self.parse_error(msg)
                if min_length_facet is not None and min_length_facet.value > min_length:
                    msg = _("'minLength' has a lesser value than parent")
                    self.parse_error(msg)
                if max_length_facet is not None and min_length > max_length_facet.value:
                    msg = _("'minLength' has a greater value than parent 'maxLength'")
                    self.parse_error(msg)

            if max_length is not None:
                if max_length < 0:
                    msg = _("'maxLength' value must be a non negative integer")
                    self.parse_error(msg)
                if min_length_facet is not None and min_length_facet.value > max_length:
                    msg = _("'maxLength' has a lesser value than parent 'minLength'")
                    self.parse_error(msg)
                if max_length_facet is not None and max_length > max_length_facet.value:
                    msg = _("'maxLength' has a greater value than parent")
                    self.parse_error(msg)

        # Checks min/max values
        min_inclusive = getattr(facets.get(XSD_MIN_INCLUSIVE), 'value', None)
        min_exclusive = getattr(facets.get(XSD_MIN_EXCLUSIVE), 'value', None)
        max_inclusive = getattr(facets.get(XSD_MAX_INCLUSIVE), 'value', None)
        max_exclusive = getattr(facets.get(XSD_MAX_EXCLUSIVE), 'value', None)

        if min_inclusive is not None:
            if min_exclusive is not None:
                msg = _("cannot specify both 'minInclusive' and 'minExclusive'")
                self.parse_error(msg)
            if max_inclusive is not None and min_inclusive > max_inclusive:
                msg = _("'minInclusive' must be less or equal to 'maxInclusive'")
                self.parse_error(msg)
            elif max_exclusive is not None and min_inclusive >= max_exclusive:
                msg = _("'minInclusive' must be lesser than 'maxExclusive'")
                self.parse_error(msg)

        elif min_exclusive is not None:
            if max_inclusive is not None and min_exclusive >= max_inclusive:
                msg = _("'minExclusive' must be lesser than 'maxInclusive'")
                self.parse_error(msg)
            elif max_exclusive is not None and min_exclusive > max_exclusive:
                msg = _("'minExclusive' must be less or equal to 'maxExclusive'")
                self.parse_error(msg)

        if max_inclusive is not None and max_exclusive is not None:
            self.parse_error(_("cannot specify both 'maxInclusive' and 'maxExclusive'"))

        # Checks fraction digits
        if XSD_TOTAL_DIGITS in facets:
            if XSD_FRACTION_DIGITS in facets and \
                    facets[XSD_TOTAL_DIGITS].value < facets[XSD_FRACTION_DIGITS].value:
                msg = _("fractionDigits facet value cannot be lesser "
                        "than the value of totalDigits facet")
                self.parse_error(msg)

            total_digits = base_type.get_facet(XSD_TOTAL_DIGITS)
            if total_digits is not None and total_digits.value < facets[XSD_TOTAL_DIGITS].value:
                msg = _("totalDigits facet value cannot be greater than "
                        "the value of the same facet in the base type")
                self.parse_error(msg)

        # Checks XSD 1.1 facets
        if XSD_EXPLICIT_TIMEZONE in facets:
            explicit_tz_facet = base_type.get_facet(XSD_EXPLICIT_TIMEZONE)
            if explicit_tz_facet and explicit_tz_facet.value in ('prohibited', 'required') \
                    and facets[XSD_EXPLICIT_TIMEZONE].value != explicit_tz_facet.value:
                msg = _("the explicitTimezone facet value cannot be changed "
                        "if the base type has the same facet with value %r")
                self.parse_error(msg % explicit_tz_facet.value)

        self.min_length = min_length
        self.max_length = max_length

    @property
    def variety(self) -> Optional[str]:
        return None

    @property
    def simple_type(self) -> 'XsdSimpleType':
        return self

    @property
    def min_value(self) -> Optional[AtomicValueType]:
        min_exclusive: Optional['AtomicValueType']
        min_inclusive: Optional['AtomicValueType']
        min_exclusive = cast(
            Optional['AtomicValueType'],
            getattr(self.get_facet(XSD_MIN_EXCLUSIVE), 'value', None)
        )
        min_inclusive = cast(
            Optional['AtomicValueType'],
            getattr(self.get_facet(XSD_MIN_INCLUSIVE), 'value', None)
        )

        if min_exclusive is None:
            return min_inclusive
        elif min_inclusive is None:
            return min_exclusive
        elif min_inclusive <= min_exclusive:  # type: ignore[operator]
            return min_exclusive
        else:
            return min_inclusive

    @property
    def max_value(self) -> Optional[AtomicValueType]:
        max_exclusive: Optional['AtomicValueType']
        max_inclusive: Optional['AtomicValueType']
        max_exclusive = cast(
            Optional['AtomicValueType'],
            getattr(self.get_facet(XSD_MAX_EXCLUSIVE), 'value', None)
        )
        max_inclusive = cast(
            Optional['AtomicValueType'],
            getattr(self.get_facet(XSD_MAX_INCLUSIVE), 'value', None)
        )

        if max_exclusive is None:
            return max_inclusive
        elif max_inclusive is None:
            return max_exclusive
        elif max_inclusive >= max_exclusive:  # type: ignore[operator]
            return max_exclusive
        else:
            return max_inclusive

    @property
    def enumeration(self) -> Optional[List[Optional[AtomicValueType]]]:
        enumeration = self.get_facet(XSD_ENUMERATION)
        if isinstance(enumeration, XsdEnumerationFacets):
            return enumeration.enumeration
        return None

    @property
    def admitted_facets(self) -> Set[str]:
        return XSD_10_FACETS if self.xsd_version == '1.0' else XSD_11_FACETS

    @property
    def built(self) -> bool:
        return True

    @staticmethod
    def is_simple() -> bool:
        return True

    @staticmethod
    def is_complex() -> bool:
        return False

    @property
    def content_type_label(self) -> str:
        return 'empty' if self.max_length == 0 else 'simple'

    @property
    def sequence_type(self) -> str:
        if self.is_empty():
            return 'empty-sequence()'

        root_type = self.root_type
        if root_type.name is not None:
            sequence_type = f'xs:{root_type.local_name}'
        else:
            sequence_type = 'xs:untypedAtomic'

        if not self.is_list():
            return sequence_type
        elif self.is_emptiable():
            return f'{sequence_type}*'
        else:
            return f'{sequence_type}+'

    def is_empty(self) -> bool:
        return self.max_length == 0 or \
            self.enumeration is not None and all(v == '' for v in self.enumeration)

    def is_emptiable(self) -> bool:
        return self.allow_empty

    def has_simple_content(self) -> bool:
        return self.max_length != 0

    def has_complex_content(self) -> bool:
        return False

    def has_mixed_content(self) -> bool:
        return False

    def is_element_only(self) -> bool:
        return False

    def is_derived(self, other: Union[BaseXsdType, Tuple[ElementType, SchemaType]],
                   derivation: Optional[str] = None) -> bool:
        if self is other:
            return True
        elif isinstance(other, tuple):
            other[1].parse_error(f"global type {other[0].tag!r} is not built")
            return False
        elif derivation and self.derivation and derivation != self.derivation:
            return False
        elif other.name in self._special_types:
            return derivation != 'extension'
        elif self.base_type is other:
            return True
        elif self.base_type is None:
            if isinstance(other, XsdUnion):
                return any(self.is_derived(m, derivation) for m in other.member_types)
            return False
        elif self.base_type.is_complex():
            if not self.base_type.has_simple_content():
                return False
            return self.base_type.content.is_derived(other, derivation)  # type: ignore
        elif isinstance(other, XsdUnion):
            return any(self.is_derived(m, derivation) for m in other.member_types)
        else:
            return self.base_type.is_derived(other, derivation)

    def is_dynamic_consistent(self, other: BaseXsdType) -> bool:
        return other.name in {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE} or self.is_derived(other) or \
            isinstance(other, XsdUnion) and any(self.is_derived(mt) for mt in other.member_types)

    def normalize(self, text: Union[str, bytes]) -> str:
        """
        Normalize and restrict value-space with pre-lexical and lexical facets.

        :param text: text string encoded value.
        :return: a normalized string.
        """
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        elif not isinstance(text, str):
            raise XMLSchemaValueError('argument is not a string: %r' % text)

        if self.white_space == 'replace':
            return self._REGEX_SPACE.sub(' ', text)
        elif self.white_space == 'collapse':
            return self._REGEX_SPACES.sub(' ', text).strip()
        else:
            return text

    def text_decode(self, text: str) -> AtomicValueType:
        return cast(AtomicValueType, self.decode(text, validation='skip'))

    def iter_decode(self, obj: Union[str, bytes], validation: str = 'lax',
                    **kwargs: Any) -> IterDecodeType[DecodedValueType]:
        text = self.normalize(obj)
        if self.patterns is not None:
            try:
                self.patterns(text)
            except XMLSchemaValidationError as err:
                yield err

        for validator in self.validators:
            try:
                validator(text)
            except XMLSchemaValidationError as err:
                yield err

        yield text

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[EncodedValueType]:
        if isinstance(obj, (str, bytes)):
            text = self.normalize(obj)
        elif obj is None:
            text = ''
        elif isinstance(obj, list):
            text = ' '.join(str(x) for x in obj)
        else:
            text = str(obj)

        if self.patterns is not None:
            try:
                self.patterns(text)
            except XMLSchemaValidationError as err:
                yield err

        for validator in self.validators:
            try:
                validator(text)
            except XMLSchemaValidationError as err:
                yield err

        yield text

    def get_facet(self, tag: str) -> Optional[FacetsValueType]:
        return self.facets.get(tag)


#
# simpleType's derived classes:
class XsdAtomic(XsdSimpleType):
    """
    Class for atomic simpleType definitions. An atomic definition has
    a base_type attribute that refers to primitive or derived atomic
    built-in type or another derived simpleType.
    """
    _special_types = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE}
    _ADMITTED_TAGS = {XSD_RESTRICTION, XSD_SIMPLE_TYPE}

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent] = None,
                 name: Optional[str] = None,
                 facets: Optional[Dict[Optional[str], FacetsValueType]] = None,
                 base_type: Optional[BaseXsdType] = None) -> None:

        if base_type is None:
            self.primitive_type = self
        else:
            self.base_type = base_type
        super(XsdAtomic, self).__init__(elem, schema, parent, name, facets)

    def __repr__(self) -> str:
        if self.name is None:
            return '%s(primitive_type=%r)' % (
                self.__class__.__name__, self.primitive_type.local_name
            )
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name: str, value: Any) -> None:
        super(XsdAtomic, self).__setattr__(name, value)
        if name == 'base_type':
            if not hasattr(self, 'white_space'):
                try:
                    self.white_space = value.white_space
                except AttributeError:
                    pass
            try:
                if value.is_simple():
                    self.primitive_type = value.primitive_type
                else:
                    self.primitive_type = value.content.primitive_type
            except AttributeError:
                self.primitive_type = value

    @property
    def variety(self) -> Optional[str]:
        return 'atomic'

    @property
    def admitted_facets(self) -> Set[str]:
        if self.primitive_type.is_complex():
            return XSD_10_FACETS if self.xsd_version == '1.0' else XSD_11_FACETS
        return self.primitive_type.admitted_facets

    def is_datetime(self) -> bool:
        return self.primitive_type.to_python.__name__ == 'fromstring'

    def get_facet(self, tag: str) -> Optional[FacetsValueType]:
        facet = self.facets.get(tag)
        if facet is not None:
            return facet
        elif self.base_type is not None:
            return self.base_type.get_facet(tag)
        else:
            return None

    def is_atomic(self) -> bool:
        return True


class XsdAtomicBuiltin(XsdAtomic):
    """
    Class for defining XML Schema built-in simpleType atomic datatypes. An instance
    contains a Python's type transformation and a list of validator functions. The
    'base_type' is not used for validation, but only for reference to the XML Schema
    restriction hierarchy.

    Type conversion methods:
      - to_python(value): Decoding from XML
      - from_python(value): Encoding to XML
    """
    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 name: str,
                 python_type: Type[Any],
                 base_type: Optional['XsdAtomicBuiltin'] = None,
                 admitted_facets: Optional[Set[str]] = None,
                 facets: Optional[Dict[Optional[str], FacetsValueType]] = None,
                 to_python: Any = None,
                 from_python: Any = None) -> None:
        """
        :param name: the XSD type's qualified name.
        :param python_type: the correspondent Python's type. If a tuple of types \
        is provided uses the first and consider the others as compatible types.
        :param base_type: the reference base type, None if it's a primitive type.
        :param admitted_facets: admitted facets tags for type (required for primitive types).
        :param facets: optional facets validators.
        :param to_python: optional decode function.
        :param from_python: optional encode function.
        """
        if isinstance(python_type, tuple):
            self.instance_types, python_type = python_type, python_type[0]
        else:
            self.instance_types = python_type
        if not callable(python_type):
            raise XMLSchemaTypeError("%r object is not callable" % python_type.__class__)

        if base_type is None and not admitted_facets and name != XSD_ERROR:
            raise XMLSchemaValueError("argument 'admitted_facets' must be "
                                      "a not empty set of a primitive type")
        self._admitted_facets = admitted_facets

        super(XsdAtomicBuiltin, self).__init__(elem, schema, None, name, facets, base_type)
        self.python_type = python_type
        self.to_python = to_python if to_python is not None else python_type
        self.from_python = from_python if from_python is not None else str

    def __repr__(self) -> str:
        return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    @property
    def admitted_facets(self) -> Set[str]:
        return self._admitted_facets or self.primitive_type.admitted_facets

    def iter_decode(self, obj: Union[str, bytes], validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[DecodedValueType]:
        if isinstance(obj, (str, bytes)):
            obj = self.normalize(obj)
        elif obj is not None and not isinstance(obj, self.instance_types):
            reason = _("value is not an instance of {!r}").format(self.instance_types)
            yield XMLSchemaDecodeError(self, obj, self.to_python, reason)

        if validation == 'skip':
            try:
                yield self.to_python(obj)
            except (ValueError, DecimalException):
                yield str(obj)
            return

        if self.patterns is not None:
            try:
                self.patterns(obj)
            except XMLSchemaValidationError as err:
                yield err

        try:
            result = self.to_python(obj)
        except (ValueError, DecimalException) as err:
            yield XMLSchemaDecodeError(self, obj, self.to_python, reason=str(err))
            yield None
            return
        except TypeError:
            # xs:error type (e.g. an XSD 1.1 type alternative used to catch invalid values)
            reason = _("invalid value {!r}").format(obj)
            yield self.validation_error(validation, error=reason, obj=obj)
            yield None
            return

        for validator in self.validators:
            try:
                validator(result)
            except XMLSchemaValidationError as err:
                yield err

        if self.name not in {XSD_QNAME, XSD_IDREF, XSD_ID}:
            pass
        elif self.name == XSD_QNAME:
            if ':' in obj:
                try:
                    prefix, name = obj.split(':')
                except ValueError:
                    pass
                else:
                    try:
                        result = f"{{{kwargs['namespaces'][prefix]}}}{name}"
                    except (TypeError, KeyError):
                        try:
                            if kwargs['source'].namespace != XSD_NAMESPACE:
                                reason = _("unmapped prefix %r in a QName") % prefix
                                yield self.validation_error(validation, error=reason, obj=obj)
                        except KeyError:
                            pass
            else:
                try:
                    default_namespace = kwargs['namespaces']['']
                except (TypeError, KeyError):
                    pass
                else:
                    if default_namespace:
                        result = f'{{{default_namespace}}}{obj}'

        elif self.name == XSD_IDREF:
            try:
                id_map = kwargs['id_map']
            except KeyError:
                pass
            else:
                if obj not in id_map:
                    id_map[obj] = 0

        elif kwargs.get('level') != 0:
            try:
                id_map = kwargs['id_map']
            except KeyError:
                pass
            else:
                try:
                    id_list = kwargs['id_list']
                except KeyError:
                    if not id_map[obj]:
                        id_map[obj] = 1
                    else:
                        reason = _("duplicated xs:ID value {!r}").format(obj)
                        yield self.validation_error(validation, error=reason, obj=obj)
                else:
                    if not id_map[obj]:
                        id_map[obj] = 1
                        id_list.append(obj)
                        if len(id_list) > 1 and self.xsd_version == '1.0':
                            reason = _("no more than one attribute of type ID should "
                                       "be present in an element")
                            yield self.validation_error(validation, reason, obj, **kwargs)

                    elif obj not in id_list or self.xsd_version == '1.0':
                        reason = _("duplicated xs:ID value {!r}").format(obj)
                        yield self.validation_error(validation, error=reason, obj=obj)

        yield result

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[EncodedValueType]:
        if isinstance(obj, (str, bytes)):
            obj = self.normalize(obj)

        if validation == 'skip':
            try:
                yield self.from_python(obj)
            except ValueError:
                yield str(obj)
            return

        elif isinstance(obj, bool):
            types_: Any = self.instance_types
            if types_ is not bool or (isinstance(types_, tuple) and bool in types_):
                reason = _("boolean value {0!r} requires a {1!r} decoder").format(obj, bool)
                yield XMLSchemaEncodeError(self, obj, self.from_python, reason)
                obj = self.python_type(obj)

        elif not isinstance(obj, self.instance_types):
            reason = _("{0!r} is not an instance of {1!r}").format(obj, self.instance_types)
            yield XMLSchemaEncodeError(self, obj, self.from_python, reason)

            try:
                value = self.python_type(obj)
                if value != obj and not isinstance(value, str) \
                        and not isinstance(obj, (str, bytes)):
                    raise ValueError()
                obj = value
            except (ValueError, TypeError) as err:
                yield XMLSchemaEncodeError(self, obj, self.from_python, reason=str(err))
                yield None
                return
            else:
                if value == obj or str(value) == str(obj):
                    obj = value
                else:
                    reason = _("invalid value {!r}").format(obj)
                    yield XMLSchemaEncodeError(self, obj, self.from_python, reason)
                    yield None
                    return

        for validator in self.validators:
            try:
                validator(obj)
            except XMLSchemaValidationError as err:
                yield err

        try:
            text = self.from_python(obj)
        except ValueError as err:
            yield XMLSchemaEncodeError(self, obj, self.from_python, reason=str(err))
            yield None
        else:
            if self.patterns is not None:
                try:
                    self.patterns(text)
                except XMLSchemaValidationError as err:
                    yield err
            yield text


class XsdList(XsdSimpleType):
    """
    Class for 'list' definitions. A list definition has an item_type attribute
    that refers to an atomic or union simpleType definition.

    ..  <list
          id = ID
          itemType = QName
          {any attributes with non-schema namespace ...}>
          Content: (annotation?, simpleType?)
        </list>
    """
    base_type: XsdSimpleType
    _ADMITTED_TAGS = {XSD_LIST}
    _white_space_elem = ElementTree.Element(
        XSD_WHITE_SPACE, attrib={'value': 'collapse', 'fixed': 'true'}
    )

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent],
                 name: Optional[str] = None) -> None:
        facets: Optional[Dict[Optional[str], FacetsValueType]] = {
            XSD_WHITE_SPACE: XsdWhiteSpaceFacet(self._white_space_elem, schema, self, self)
        }
        super(XsdList, self).__init__(elem, schema, parent, name, facets)

    def __repr__(self) -> str:
        if self.name is None:
            return '%s(item_type=%r)' % (self.__class__.__name__, self.base_type)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'elem' and value is not None and value.tag != XSD_LIST:
            if value.tag == XSD_SIMPLE_TYPE:
                for child in value:
                    if child.tag == XSD_LIST:
                        super(XsdList, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError(
                "a {0!r} definition required for {1!r}".format(XSD_LIST, self)
            )
        elif name == 'base_type':
            if not value.is_atomic():
                raise XMLSchemaValueError(
                    _("%r: a list must be based on atomic data types") % self
                )
        elif name == 'white_space' and value is None:
            value = 'collapse'
        super(XsdList, self).__setattr__(name, value)

    def _parse(self) -> None:
        base_type: Any

        child = self._parse_child_component(self.elem)
        if child is not None:
            # Case of a local simpleType declaration inside the list tag
            try:
                base_type = self.schema.simple_type_factory(child, parent=self)
            except XMLSchemaParseError as err:
                self.parse_error(err)
                base_type = self.any_atomic_type

            if 'itemType' in self.elem.attrib:
                self.parse_error(_("ambiguous list type declaration"))

        else:
            # List tag with itemType attribute that refers to a global type
            try:
                item_qname = self.schema.resolve_qname(self.elem.attrib['itemType'])
            except (KeyError, ValueError, RuntimeError) as err:
                if 'itemType' not in self.elem.attrib:
                    self.parse_error(_("missing list type declaration"))
                else:
                    self.parse_error(err)
                base_type = self.any_atomic_type
            else:
                try:
                    base_type = self.maps.lookup_type(item_qname)
                except KeyError:
                    msg = _("unknown type {!r}")
                    self.parse_error(msg.format(self.elem.attrib['itemType']))
                    base_type = self.any_atomic_type
                else:
                    if isinstance(base_type, tuple):
                        msg = _("circular definition found for type {!r}")
                        self.parse_error(msg.format(item_qname))
                        base_type = self.any_atomic_type

        if base_type.final == '#all' or 'list' in base_type.final:
            msg = _("'final' value of the itemType %r forbids derivation by list")
            self.parse_error(msg % base_type)

        if base_type.name == XSD_ANY_ATOMIC_TYPE:
            msg = _("cannot use xs:anyAtomicType as base type of a user-defined type")
            self.parse_error(msg)

        try:
            self.base_type = base_type
        except XMLSchemaValueError as err:
            self.parse_error(err)
            self.base_type = self.any_atomic_type
        else:
            if not base_type.allow_empty and self.min_length != 0:
                self.allow_empty = False

    @property
    def variety(self) -> Optional[str]:
        return 'list'

    @property
    def admitted_facets(self) -> Set[str]:
        return XSD_10_LIST_FACETS if self.xsd_version == '1.0' else XSD_11_LIST_FACETS

    @property
    def item_type(self) -> BaseXsdType:
        return self.base_type

    def is_atomic(self) -> bool:
        return False

    def is_list(self) -> bool:
        return True

    def is_derived(self, other: Union[BaseXsdType, Tuple[ElementType, SchemaType]],
                   derivation: Optional[str] = None) -> bool:
        if self is other:
            return True
        elif isinstance(other, tuple):
            other[1].parse_error(f"global type {other[0].tag!r} is not built")
            return False
        elif derivation and self.derivation and derivation != self.derivation:
            return False
        elif other.name in self._special_types:
            return derivation != 'extension'
        elif self.base_type is other:
            return True
        else:
            return False

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[XsdComponent]:
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.base_type.parent is not None:
            yield from self.base_type.iter_components(xsd_classes)

    def iter_decode(self, obj: Union[str, bytes],
                    validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[Union[XMLSchemaValidationError,
                              List[Optional[AtomicValueType]]]]:
        items = []
        for chunk in self.normalize(obj).split():
            for result in self.base_type.iter_decode(chunk, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    assert not isinstance(result, list)
                    items.append(result)
        else:
            yield items

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[EncodedValueType]:
        if not hasattr(obj, '__iter__') or isinstance(obj, (str, bytes)):
            obj = [obj]

        encoded_items: List[Any] = []
        for item in obj:
            for result in self.base_type.iter_encode(item, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    encoded_items.append(result)

        yield ' '.join(item for item in encoded_items if item is not None)


class XsdUnion(XsdSimpleType):
    """
    Class for 'union' definitions. A union definition has a member_types
    attribute that refers to a 'simpleType' definition.

    ..  <union
          id = ID
          memberTypes = List of QName
          {any attributes with non-schema namespace ...}>
          Content: (annotation?, simpleType*)
        </union>
    """
    member_types: Any = ()
    _ADMITTED_TYPES: Any = XsdSimpleType
    _ADMITTED_TAGS = {XSD_UNION}

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent],
                 name: Optional[str] = None) -> None:
        super(XsdUnion, self).__init__(elem, schema, parent, name, facets=None)

    def __repr__(self) -> str:
        if self.name is None:
            return '%s(member_types=%r)' % (self.__class__.__name__, self.member_types)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'elem' and value is not None and value.tag != XSD_UNION:
            if value.tag == XSD_SIMPLE_TYPE:
                for child in value:
                    if child.tag == XSD_UNION:
                        super(XsdUnion, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError(
                "a {0!r} definition required for {1!r}".format(XSD_UNION, self)
            )

        elif name == 'white_space':
            if not (value is None or value == 'collapse'):
                msg = _("wrong value %r for attribute 'white_space'")
                raise XMLSchemaValueError(msg % value)
            value = 'collapse'
        super(XsdUnion, self).__setattr__(name, value)

    def _parse(self) -> None:
        mt: Any
        member_types = []

        for child in self.elem:
            if child.tag != XSD_ANNOTATION and not callable(child.tag):
                mt = self.schema.simple_type_factory(child, parent=self)
                if isinstance(mt, XMLSchemaParseError):
                    self.parse_error(mt)
                else:
                    member_types.append(mt)

        if 'memberTypes' in self.elem.attrib:
            for name in self.elem.attrib['memberTypes'].split():
                try:
                    type_qname = self.schema.resolve_qname(name)
                except (KeyError, ValueError, RuntimeError) as err:
                    self.parse_error(err)
                    continue

                try:
                    mt = self.maps.lookup_type(type_qname)
                except KeyError:
                    self.parse_error(_("unknown type {!r}").format(type_qname))
                    mt = self.any_atomic_type
                except XMLSchemaParseError as err:
                    self.parse_error(err)
                    mt = self.any_atomic_type

                if isinstance(mt, tuple):
                    msg = _("circular definition found on xs:union type {!r}")
                    self.parse_error(msg.format(self.name))
                    continue
                elif not isinstance(mt, self._ADMITTED_TYPES):
                    msg = _("a {0!r} required, not {1!r}")
                    self.parse_error(msg.format(self._ADMITTED_TYPES, mt))
                    continue
                elif mt.final == '#all' or 'union' in mt.final:
                    msg = _("'final' value of the memberTypes %r forbids derivation by union")
                    self.parse_error(msg % member_types)

                member_types.append(mt)

        if not member_types:
            self.parse_error(_("missing xs:union type declarations"))
            self.member_types = [self.any_atomic_type]
        elif any(mt.name == XSD_ANY_ATOMIC_TYPE for mt in member_types):
            msg = _("cannot use xs:anyAtomicType as base type of a user-defined type")
            self.parse_error(msg)
        else:
            self.member_types = member_types
            if all(not mt.allow_empty for mt in member_types):
                self.allow_empty = False

    @property
    def variety(self) -> Optional[str]:
        return 'union'

    @property
    def admitted_facets(self) -> Set[str]:
        return XSD_10_UNION_FACETS if self.xsd_version == '1.0' else XSD_11_UNION_FACETS

    def is_atomic(self) -> bool:
        return all(mt.is_atomic() for mt in self.member_types)

    def is_list(self) -> bool:
        return all(mt.is_list() for mt in self.member_types)

    def is_key(self) -> bool:
        return any(mt.is_key() for mt in self.member_types)

    def is_union(self) -> bool:
        return True

    def is_dynamic_consistent(self, other: Any) -> bool:
        return other.name in {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE} or \
            other.is_derived(self) or isinstance(other, self.__class__) and \
            any(mt1.is_derived(mt2) for mt1 in other.member_types for mt2 in self.member_types)

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[XsdComponent]:
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for mt in filter(lambda x: x.parent is not None, self.member_types):
            yield from mt.iter_components(xsd_classes)

    def iter_decode(self, obj: AtomicValueType, validation: str = 'lax',
                    patterns: Optional[XsdPatternFacets] = None,
                    **kwargs: Any) -> IterDecodeType[DecodedValueType]:

        # Try decoding the whole text (or validate the decoded atomic value)
        for member_type in self.member_types:
            for result in member_type.iter_decode(obj, validation='lax', **kwargs):
                if not isinstance(result, XMLSchemaValidationError):
                    if patterns and isinstance(obj, (str, bytes)):
                        try:
                            patterns(member_type.normalize(obj))
                        except XMLSchemaValidationError as err:
                            yield err

                    yield result
                    return
                break

        if isinstance(obj, bytes):
            obj = obj.decode('utf-8')

        if not isinstance(obj, str) or ' ' not in obj.strip():
            reason = _("invalid value {!r}").format(obj)
            yield XMLSchemaDecodeError(self, obj, self.member_types, reason)
            return

        items = []
        not_decodable = []
        for chunk in obj.split():
            for member_type in self.member_types:
                for result in member_type.iter_decode(chunk, validation='lax', **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        break
                    else:
                        items.append(result)
                else:
                    break
            else:
                if validation != 'skip':
                    not_decodable.append(chunk)
                else:
                    items.append(str(chunk))

        if not_decodable:
            reason = _("no type suitable for decoding the values %r") % not_decodable
            yield XMLSchemaDecodeError(self, obj, self.member_types, reason)

        yield items if len(items) > 1 else items[0] if items else None

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[EncodedValueType]:

        for member_type in self.member_types:
            for result in member_type.iter_encode(obj, validation='lax', **kwargs):
                if result is not None and not isinstance(result, XMLSchemaValidationError):
                    yield result
                    return
                elif validation == 'strict':
                    # In 'strict' mode avoid lax encoding by similar types
                    # (e.g. float encoded by int)
                    break

        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            for member_type in self.member_types:
                results = []
                for item in obj:
                    for result in member_type.iter_encode(item, validation='lax', **kwargs):
                        if result is not None and not isinstance(result, XMLSchemaValidationError):
                            results.append(result)
                            break
                        elif validation == 'strict':
                            break

                if len(results) == len(obj):
                    yield results
                    break

        if validation != 'skip':
            reason = _("no type suitable for encoding the object")
            yield XMLSchemaEncodeError(self, obj, self.member_types, reason)
            yield None
        else:
            yield str(obj)


class Xsd11Union(XsdUnion):
    _ADMITTED_TYPES = XsdAtomic, XsdList, XsdUnion


class XsdAtomicRestriction(XsdAtomic):
    """
    Class for XSD 1.0 atomic simpleType and complexType's simpleContent restrictions.

    ..  <restriction
          base = QName
          id = ID
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive |
          maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength |
          enumeration | whiteSpace | pattern)*))
        </restriction>
    """
    parent: 'XsdSimpleType'
    base_type: BaseXsdType
    derivation = 'restriction'
    _FACETS_BUILDERS = XSD_10_FACETS_BUILDERS
    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE}

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'elem' and value is not None:
            if self.name != XSD_ANY_ATOMIC_TYPE and value.tag != XSD_RESTRICTION:
                if not (value.tag == XSD_SIMPLE_TYPE and value.get('name') is not None):
                    raise XMLSchemaValueError(
                        "an xs:restriction definition required for %r." % self
                    )
        super(XsdAtomicRestriction, self).__setattr__(name, value)

    def _parse(self) -> None:
        elem = self.elem
        if elem.get('name') == XSD_ANY_ATOMIC_TYPE:
            return  # skip special type xs:anyAtomicType
        elif elem.tag == XSD_SIMPLE_TYPE and elem.get('name') is not None:
            # Global simpleType with internal restriction
            elem = cast(ElementType, self._parse_child_component(elem))

        if self.name is not None and self.parent is not None:
            msg = _("'name' attribute in a local simpleType definition")
            self.parse_error(msg)

        base_type: Any = None
        facets: Any = {}
        has_attributes = False
        has_simple_type_child = False

        if 'base' in elem.attrib:
            try:
                base_qname = self.schema.resolve_qname(elem.attrib['base'])
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err)
                base_type = self.any_atomic_type
            else:
                if base_qname == self.name:
                    if self.redefine is None:
                        msg = _("wrong definition with self-reference")
                        self.parse_error(msg)
                        base_type = self.any_atomic_type
                    else:
                        base_type = self.base_type
                else:
                    if self.redefine is not None:
                        msg = _("wrong redefinition without self-reference")
                        self.parse_error(msg)

                    try:
                        base_type = self.maps.lookup_type(base_qname)
                    except KeyError:
                        self.parse_error(_("unknown type {!r}").format(elem.attrib['base']))
                        base_type = self.any_atomic_type
                    except XMLSchemaParseError as err:
                        self.parse_error(err)
                        base_type = self.any_atomic_type
                    else:
                        if isinstance(base_type, tuple):
                            msg = _("circular definition found between {0!r} and {1!r}")
                            self.parse_error(msg.format(self, base_qname))
                            base_type = self.any_atomic_type

            if base_type.is_simple() and base_type.name == XSD_ANY_SIMPLE_TYPE:
                msg = _("wrong base type %r, an atomic type required")
                self.parse_error(msg % XSD_ANY_SIMPLE_TYPE)
            elif base_type.is_complex():
                if base_type.mixed and base_type.is_emptiable():
                    child = self._parse_child_component(elem, strict=False)
                    if child is None:
                        msg = _("an xs:simpleType definition expected")
                        self.parse_error(msg)
                    elif child.tag != XSD_SIMPLE_TYPE:
                        # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                        self.parse_error(_(
                            "when a complexType with simpleContent restricts a complexType "
                            "with mixed and with emptiable content then a simpleType child "
                            "declaration is required"
                        ))
                elif self.parent is None or self.parent.is_simple():
                    msg = _("simpleType restriction of %r is not allowed")
                    self.parse_error(msg % base_type)

        for child in elem:
            if child.tag == XSD_ANNOTATION or callable(child.tag):
                continue
            elif child.tag in self._CONTENT_TAIL_TAGS:
                has_attributes = True  # only if it's a complexType restriction
            elif has_attributes:
                msg = _("unexpected tag after attribute declarations")
                self.parse_error(msg)
            elif child.tag == XSD_SIMPLE_TYPE:
                # Case of simpleType declaration inside a restriction
                if has_simple_type_child:
                    msg = _("duplicated simpleType declaration")
                    self.parse_error(msg)

                if base_type is None:
                    try:
                        base_type = self.schema.simple_type_factory(child, parent=self)
                    except XMLSchemaParseError as err:
                        self.parse_error(err, child)
                        base_type = self.any_simple_type
                elif base_type.is_complex():
                    if base_type.admit_simple_restriction():
                        base_type = self.schema.xsd_complex_type_class(
                            elem=elem,
                            schema=self.schema,
                            parent=self,
                            content=self.schema.simple_type_factory(child, parent=self),
                            attributes=base_type.attributes,
                            mixed=base_type.mixed,
                            block=base_type.block,
                            final=base_type.final,
                        )
                elif 'base' in elem.attrib:
                    msg = _("restriction with 'base' attribute and simpleType declaration")
                    self.parse_error(msg)

                has_simple_type_child = True
            else:
                try:
                    facet_class = self._FACETS_BUILDERS[child.tag]
                except KeyError:
                    self.parse_error(_("unexpected tag %r in restriction") % child.tag)
                    continue

                if child.tag not in facets:
                    facets[child.tag] = facet_class(child, self.schema, self, base_type)
                elif child.tag not in MULTIPLE_FACETS:
                    msg = _("multiple %r constraint facet")
                    self.parse_error(msg % local_name(child.tag))
                elif child.tag != XSD_ASSERTION:
                    facets[child.tag].append(child)
                else:
                    assertion = facet_class(child, self.schema, self, base_type)
                    try:
                        facets[child.tag].append(assertion)
                    except AttributeError:
                        facets[child.tag] = [facets[child.tag], assertion]

        if base_type is None:
            self.parse_error(_("missing base type in restriction"))
        elif base_type.final == '#all' or 'restriction' in base_type.final:
            msg = _("'final' value of the baseType %r forbids derivation by restriction")
            self.parse_error(msg % base_type)
        if base_type is self.any_atomic_type:
            msg = _("cannot use xs:anyAtomicType as base type of a user-defined type")
            self.parse_error(msg)

        self.base_type = base_type
        self.facets = facets

    @property
    def variety(self) -> Optional[str]:
        return cast(Optional[str], getattr(self.base_type, 'variety', None))

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[XsdComponent]:
        if xsd_classes is None:
            yield self
            for facet in self.facets.values():
                if isinstance(facet, list):
                    yield from facet  # XSD 1.1 assertions can be more than one
                elif isinstance(facet, XsdFacet):
                    yield facet  # only XSD facets, skip callables
        else:
            if isinstance(self, xsd_classes):
                yield self
            if issubclass(XsdFacet, xsd_classes):
                for facet in self.facets.values():
                    if isinstance(facet, list):
                        yield from facet
                    elif isinstance(facet, XsdFacet):
                        yield facet

        if self.base_type.parent is not None:
            yield from self.base_type.iter_components(xsd_classes)

    def iter_decode(self, obj: AtomicValueType, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[DecodedValueType]:
        if isinstance(obj, (str, bytes)):
            obj = self.normalize(obj)

            if self.patterns:
                if not isinstance(self.primitive_type, XsdUnion):
                    try:
                        self.patterns(obj)
                    except XMLSchemaValidationError as err:
                        yield err
                elif 'patterns' not in kwargs:
                    kwargs['patterns'] = self.patterns

        base_type: Any
        if isinstance(self.base_type, XsdSimpleType):
            base_type = self.base_type
        elif self.base_type.has_simple_content():
            base_type = self.base_type.content
        elif self.base_type.mixed:
            yield obj
            return
        else:  # pragma: no cover
            msg = _("wrong base type %r: a simpleType or a complexType "
                    "with simple or mixed content required")
            raise XMLSchemaValueError(msg % self.base_type)

        for result in base_type.iter_decode(obj, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                if result is not None:
                    for validator in self.validators:
                        try:
                            validator(result)
                        except XMLSchemaValidationError as err:
                            yield err

                yield result
                return

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[EncodedValueType]:

        base_type: Any
        if self.is_list():
            if not hasattr(obj, '__iter__') or isinstance(obj, (str, bytes)):
                obj = [] if obj is None or obj == '' else [obj]
            base_type = self.base_type
        else:
            if isinstance(obj, (str, bytes)):
                obj = self.normalize(obj)

            if isinstance(self.base_type, XsdSimpleType):
                base_type = self.base_type
            elif self.base_type.has_simple_content():
                base_type = self.base_type.content
            elif self.base_type.mixed:
                yield str(obj)
                return
            else:  # pragma: no cover
                msg = _("wrong base type %r: a simpleType or a complexType "
                        "with simple or mixed content required")
                raise XMLSchemaValueError(msg % self.base_type)

        result: Any
        for result in base_type.iter_encode(obj, validation):
            if isinstance(result, XMLSchemaValidationError):
                yield result
                if isinstance(result, XMLSchemaEncodeError):
                    yield str(obj) if validation == 'skip' else None
                    return
            else:
                if self.validators and obj is not None:
                    if isinstance(obj, (str, bytes)) and \
                            self.primitive_type.to_python is not str and \
                            isinstance(obj, self.primitive_type.instance_types):
                        try:
                            obj = self.primitive_type.to_python(obj)
                        except (ValueError, DecimalException, TypeError):
                            pass

                    for validator in self.validators:
                        try:
                            validator(obj)
                        except XMLSchemaValidationError as err:
                            yield err

                if self.patterns:
                    if not isinstance(self.primitive_type, XsdUnion):
                        try:
                            self.patterns(result)
                        except XMLSchemaValidationError as err:
                            yield err
                    elif 'patterns' not in kwargs:
                        kwargs['patterns'] = self.patterns

                yield result
                return

    def is_list(self) -> bool:
        return self.primitive_type.is_list()

    def is_union(self) -> bool:
        return self.primitive_type.is_union()


class Xsd11AtomicRestriction(XsdAtomicRestriction):
    """
    Class for XSD 1.1 atomic simpleType and complexType's simpleContent restrictions.

    ..  <restriction
          base = QName
          id = ID
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive |
          maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength |
          enumeration | whiteSpace | pattern | assertion | explicitTimezone |
          {any with namespace: ##other})*))
        </restriction>
    """
    _FACETS_BUILDERS = XSD_11_FACETS_BUILDERS
    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE, XSD_ASSERT}
