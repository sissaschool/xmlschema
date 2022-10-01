#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains declarations and classes for XML Schema constraint facets.
"""
import re
import math
import operator
from abc import abstractmethod
from typing import TYPE_CHECKING, cast, Any, List, Optional, Pattern, Union, \
    MutableSequence, overload, Tuple
from xml.etree.ElementTree import Element

from elementpath import XPath2Parser, XPathContext, ElementPathError, \
    translate_pattern, RegexError, ElementNode

from ..names import XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_ENUMERATION, \
    XSD_INTEGER, XSD_WHITE_SPACE, XSD_PATTERN, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, \
    XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_TOTAL_DIGITS, XSD_FRACTION_DIGITS, \
    XSD_ASSERTION, XSD_DECIMAL, XSD_EXPLICIT_TIMEZONE, XSD_NOTATION_TYPE, XSD_QNAME, \
    XSD_ANNOTATION
from ..aliases import ElementType, SchemaType, AtomicValueType, BaseXsdType
from ..translation import gettext as _
from ..helpers import count_digits, local_name
from .exceptions import XMLSchemaValidationError, XMLSchemaDecodeError
from .xsdbase import XsdComponent, XsdAnnotation

if TYPE_CHECKING:
    from .simple_types import XsdList, XsdAtomicRestriction

LaxDecodeType = Tuple[Any, List[XMLSchemaValidationError]]


class XsdFacet(XsdComponent):
    """
    XML Schema constraining facets base class.
    """
    value: Optional[AtomicValueType]
    base_type: Optional[BaseXsdType]
    base_value: Optional[AtomicValueType]
    fixed = False

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Union['XsdList', 'XsdAtomicRestriction'],
                 base_type: Optional[BaseXsdType]) -> None:
        self.base_type = base_type
        super(XsdFacet, self).__init__(elem, schema, parent)

    def __repr__(self) -> str:
        return '%s(value=%r, fixed=%r)' % (self.__class__.__name__, self.value, self.fixed)

    def __call__(self, value: Any) -> None:
        try:
            self._validator(value)
        except TypeError:
            reason = _("invalid type {!r} provided").format(type(value))
            raise XMLSchemaValidationError(self, value, reason) from None

    @staticmethod
    def _validator(_: Any) -> None:
        return

    def _parse(self) -> None:
        if 'fixed' in self.elem.attrib and self.elem.attrib['fixed'] in ('true', '1'):
            self.fixed = True
        base_facet = self.base_facet
        self.base_value = None if base_facet is None else base_facet.value

        try:
            self._parse_value(self.elem)
        except (KeyError, ValueError, XMLSchemaDecodeError) as err:
            self.value = None
            self.parse_error(err)
        else:
            if base_facet is not None and base_facet.fixed and \
                    base_facet.value is not None and self.value != base_facet.value:
                msg = _("{0!r} facet value is fixed to {1!r}")
                self.parse_error(msg.format(local_name(self.elem.tag), base_facet.value))

    def _parse_value(self, elem: ElementType) -> Union[None, AtomicValueType, Pattern[str]]:
        self.value = elem.attrib['value']  # pragma: no cover
        return None

    @property
    def built(self) -> bool:
        return True  # pragma: no cover

    @property
    def base_facet(self) -> Optional['XsdFacet']:
        """
        An object of the same type if the instance has a base facet, `None` otherwise.
        """
        base_type: Optional[BaseXsdType] = self.base_type
        tag = self.elem.tag
        while True:
            if base_type is None:
                return None
            try:
                base_facet = base_type.facets[tag]  # type: ignore[union-attr]
            except (AttributeError, KeyError):
                base_type = base_type.base_type
            else:
                assert isinstance(base_facet, self.__class__)
                return base_facet


class XsdWhiteSpaceFacet(XsdFacet):
    """
    XSD *whiteSpace* facet.

    ..  <whiteSpace
          fixed = boolean : false
          id = ID
          value = (collapse | preserve | replace)
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </whiteSpace>
    """
    value: str
    _ADMITTED_TAGS = XSD_WHITE_SPACE,

    def _parse_value(self, elem: ElementType) -> None:
        self.value = elem.attrib['value']
        if self.value == 'collapse':
            self._validator = self.collapse_white_space_validator  # type: ignore[assignment]
        elif self.value == 'replace':
            if self.base_value == 'collapse':
                self.parse_error(_("facet value can be only 'collapse'"))
            self._validator = self.replace_white_space_validator  # type: ignore[assignment]
        elif self.base_value == 'collapse':
            self.parse_error(_("facet value can be only 'collapse'"))
        elif self.base_value == 'replace':
            self.parse_error(_("facet value can be only 'replace' or 'collapse'"))

    def replace_white_space_validator(self, value: str) -> None:
        if '\t' in value or '\n' in value:
            raise XMLSchemaValidationError(
                self, value, _("value contains tabs or newlines")
            )

    def collapse_white_space_validator(self, value: str) -> None:
        if '\t' in value or '\n' in value or '  ' in value:
            raise XMLSchemaValidationError(
                self, value, _("value contains non collapsed white spaces")
            )


class XsdLengthFacet(XsdFacet):
    """
    XSD *length* facet.

    ..  <length
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </length>
    """
    value: int
    base_type: BaseXsdType
    base_value: Optional[int]
    _ADMITTED_TAGS = XSD_LENGTH,

    def _parse_value(self, elem: ElementType) -> None:
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value != self.base_value:
            msg = _("base facet has a different length ({})")
            self.parse_error(msg.format(self.base_value))

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None or primitive_type.name not in {XSD_QNAME, XSD_NOTATION_TYPE}:
            # See: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
            self._validator = self._length_validator  # type: ignore[assignment]

    def _length_validator(self, value: Any) -> None:
        if len(value) != self.value:
            reason = _("length has to be {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdMinLengthFacet(XsdFacet):
    """
    XSD *minLength* facet.

    ..  <minLength
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minLength>
    """
    value: int
    base_type: BaseXsdType
    base_value: Optional[int]
    _ADMITTED_TAGS = XSD_MIN_LENGTH,

    def _parse_value(self, elem: ElementType) -> None:
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value < self.base_value:
            msg = _("base facet has a greater min length ({})")
            self.parse_error(msg.format(self.base_value))

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None or primitive_type.name not in {XSD_QNAME, XSD_NOTATION_TYPE}:
            # See: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
            self._validator = self._min_length_validator  # type: ignore[assignment]

    def _min_length_validator(self, value: Any) -> None:
        if len(value) < self.value:
            reason = _("value length cannot be lesser than {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdMaxLengthFacet(XsdFacet):
    """
    XSD *maxLength* facet.

    ..  <maxLength
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxLength>
    """
    value: int
    base_type: BaseXsdType
    base_value: Optional[int]
    _ADMITTED_TAGS = XSD_MAX_LENGTH,

    def _parse_value(self, elem: ElementType) -> None:
        self.value = int(elem.attrib['value'])
        if self.base_value is not None and self.value > self.base_value:
            msg = _("base type has a lesser max length ({})")
            self.parse_error(msg.format(self.base_value))

        primitive_type = getattr(self.base_type, 'primitive_type', None)
        if primitive_type is None or primitive_type.name not in {XSD_QNAME, XSD_NOTATION_TYPE}:
            # See: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4009
            self._validator = self._max_length_validator  # type: ignore[assignment]

    def _max_length_validator(self, value: Any) -> None:
        if len(value) > self.value:
            reason = _("value length cannot be greater than {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdMinInclusiveFacet(XsdFacet):
    """
    XSD *minInclusive* facet.

    ..  <minInclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minInclusive>
    """
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_MIN_INCLUSIVE,

    def _parse_value(self, elem: ElementType) -> None:
        value = elem.attrib['value']
        self.value, errors = cast(LaxDecodeType, self.base_type.decode(value, 'lax'))
        for e in errors:
            self.parse_error(_("invalid restriction: {}").format(e.reason))

    def __call__(self, value: Any) -> None:
        try:
            if value < self.value:
                reason = _("value has to be greater or equal than {!r}").format(self.value)
                raise XMLSchemaValidationError(self, value, reason)
        except TypeError as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None


class XsdMinExclusiveFacet(XsdFacet):
    """
    XSD *minExclusive* facet.

    ..  <minExclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </minExclusive>
    """
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_MIN_EXCLUSIVE,

    def _parse_value(self, elem: ElementType) -> None:
        value = elem.attrib['value']
        self.value, errors = cast(LaxDecodeType, self.base_type.decode(value, 'lax'))
        for e in errors:
            if not isinstance(e.validator, self.__class__) or e.validator.value != self.value:
                self.parse_error(_("invalid restriction: {}").format(e.reason))

        facet: Any = self.base_type.get_facet(XSD_MAX_INCLUSIVE)
        if facet is not None and facet.value == self.value:
            msg = _("invalid restriction: {} is also the maximum")
            self.parse_error(msg.format(self.value))

    def __call__(self, value: Any) -> None:
        try:
            if value <= self.value:
                reason = _("value has to be greater than {!r}").format(self.value)
                raise XMLSchemaValidationError(self, value, reason)
        except TypeError as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None


class XsdMaxInclusiveFacet(XsdFacet):
    """
    XSD *maxInclusive* facet.

    ..  <maxInclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxInclusive>
    """
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_MAX_INCLUSIVE,

    def _parse_value(self, elem: ElementType) -> None:
        value = elem.attrib['value']
        self.value, errors = cast(LaxDecodeType, self.base_type.decode(value, 'lax'))
        for e in errors:
            self.parse_error(_("invalid restriction: {}").format(e.reason))

    def __call__(self, value: Any) -> None:
        try:
            if value > self.value:
                reason = _("value has to be less than or equal than {!r}").format(self.value)
                raise XMLSchemaValidationError(self, value, reason)
        except TypeError as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None


class XsdMaxExclusiveFacet(XsdFacet):
    """
    XSD *maxExclusive* facet.

    ..  <maxExclusive
          fixed = boolean : false
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </maxExclusive>
    """
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_MAX_EXCLUSIVE,

    def _parse_value(self, elem: ElementType) -> None:
        value = elem.attrib['value']
        self.value, errors = cast(LaxDecodeType, self.base_type.decode(value, 'lax'))
        for e in errors:
            if not isinstance(e.validator, self.__class__) or e.validator.value != self.value:
                self.parse_error(_("invalid restriction: {}").format(e.reason))

        facet: Any = self.base_type.get_facet(XSD_MIN_INCLUSIVE)
        if facet is not None and facet.value == self.value:
            msg = _("invalid restriction: {} is also the minimum")
            self.parse_error(msg.format(self.value))

    def __call__(self, value: Any) -> None:
        try:
            if value >= self.value:
                reason = _("value has to be lesser than {!r}").format(self.value)
                raise XMLSchemaValidationError(self, value, reason)
        except TypeError as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None


class XsdTotalDigitsFacet(XsdFacet):
    """
    XSD *totalDigits* facet.

    ..  <totalDigits
          fixed = boolean : false
          id = ID
          value = positiveInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </totalDigits>
    """
    value: int
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_TOTAL_DIGITS,

    def _parse_value(self, elem: ElementType) -> None:
        # Errors are detected by meta-schema validation. For schemas with
        # 'lax' validation mode use 9999 in case of an invalid value.
        try:
            self.value = int(elem.attrib['value'])
        except (ValueError, KeyError):
            self.value = 9999
        else:
            if self.value < 1:
                self.value = 9999

            facet: Any = self.base_type.get_facet(XSD_TOTAL_DIGITS)
            if facet is not None and facet.value < self.value:
                msg = _("invalid restriction: base value is lower ({})")
                self.parse_error(msg.format(facet.value))

    def __call__(self, value: Any) -> None:
        try:
            if operator.add(*count_digits(value)) <= self.value:
                return
        except (TypeError, ValueError, ArithmeticError) as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None
        else:
            reason = _("the number of digits has to be lesser or equal "
                       "than {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdFractionDigitsFacet(XsdFacet):
    """
    XSD *fractionDigits* facet.

    ..  <fractionDigits
          fixed = boolean : false
          id = ID
          value = nonNegativeInteger
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </fractionDigits>
    """
    value: int
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_FRACTION_DIGITS,

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: 'XsdAtomicRestriction',
                 base_type: BaseXsdType) -> None:

        super(XsdFractionDigitsFacet, self).__init__(elem, schema, parent, base_type)
        if not base_type.is_derived(self.maps.types[XSD_DECIMAL]):
            msg = _("fractionDigits facet can be applied only to types derived from xs:decimal")
            self.parse_error(msg)

    def _parse_value(self, elem: ElementType) -> None:
        # Errors are detected by meta-schema validation. For schemas with
        # 'lax' validation mode use 9999 in case of an invalid value.
        try:
            self.value = int(elem.attrib['value'])
        except (ValueError, KeyError):
            self.value = 9999
        else:
            if self.value < 0:
                self.value = 9999
            elif self.value > 0 and self.base_type.is_derived(self.maps.types[XSD_INTEGER]):
                msg = _("fractionDigits facet value must be 0 for types derived from xs:integer")
                raise ValueError(msg)

            facet: Any = self.base_type.get_facet(XSD_FRACTION_DIGITS)
            if facet is not None and facet.value < self.value:
                msg = _("invalid restriction: base value is lower ({})")
                self.parse_error(msg.format(facet.value))

    def __call__(self, value: Any) -> None:
        try:
            if count_digits(value)[1] <= self.value:
                return
        except (TypeError, ValueError, ArithmeticError) as err:
            raise XMLSchemaValidationError(self, value, str(err)) from None
        else:
            reason = _("the number of fraction digits has to be lesser "
                       "or equal than {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdExplicitTimezoneFacet(XsdFacet):
    """
    XSD 1.1 *explicitTimezone* facet.

    ..  <explicitTimezone
          fixed = boolean : false
          id = ID
          value = NCName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </explicitTimezone>
    """
    value: str
    base_type: BaseXsdType
    _ADMITTED_TAGS = XSD_EXPLICIT_TIMEZONE,

    def _parse_value(self, elem: ElementType) -> None:
        self.value = elem.attrib['value']
        if self.value == 'prohibited':
            self._validator = self._prohibited_timezone_validator  # type: ignore[assignment]
        elif self.value == 'required':
            self._validator = self._required_timezone_validator  # type: ignore[assignment]
        elif self.value != 'optional':
            self.value = 'optional'  # Error already detected by meta-schema validation

        facet: Any = self.base_type.get_facet(XSD_EXPLICIT_TIMEZONE)
        if facet is not None and facet.value != self.value and facet.value != 'optional':
            msg = _("invalid restriction from {!r}")
            self.parse_error(msg.format(facet.value))

    def _required_timezone_validator(self, value: Any) -> None:
        if value.tzinfo is None:
            reason = _("time zone required for value {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)

    def _prohibited_timezone_validator(self, value: Any) -> None:
        if value.tzinfo is not None:
            reason = _("time zone prohibited for value {!r}").format(self.value)
            raise XMLSchemaValidationError(self, value, reason)


class XsdEnumerationFacets(MutableSequence[ElementType], XsdFacet):
    """
    Sequence of XSD *enumeration* facets. Values are validates if match any of enumeration values.

    ..  <enumeration
          id = ID
          value = anySimpleType
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </enumeration>
    """
    base_type: BaseXsdType
    _ADMITTED_TAGS = {XSD_ENUMERATION}

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: 'XsdAtomicRestriction',
                 base_type: BaseXsdType) -> None:
        XsdFacet.__init__(self, elem, schema, parent, base_type)

    def _parse(self) -> None:
        self._elements = [self.elem]
        self.enumeration = [self._parse_value(self.elem)]

    def _parse_value(self, elem: ElementType) -> Optional[AtomicValueType]:
        try:
            value = self.base_type.decode(elem.attrib['value'], namespaces=self.schema.namespaces)
        except KeyError:
            pass  # pragma: no cover (already detected by meta-schema validation)
        except XMLSchemaValidationError as err:
            self.parse_error(err, elem)
        else:
            if self.base_type.name == XSD_NOTATION_TYPE:
                assert isinstance(value, str)
                try:
                    notation_qname = self.schema.resolve_qname(value)
                except (KeyError, ValueError, RuntimeError) as err:
                    self.parse_error(err, elem)
                else:
                    if notation_qname not in self.maps.notations:
                        msg = _("value {!r} must match a notation declaration")
                        self.parse_error(msg.format(value), elem)
            return cast(AtomicValueType, value)
        return None

    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> ElementType: ...

    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> MutableSequence[ElementType]: ...

    def __getitem__(self, i: Union[int, slice]) \
            -> Union[ElementType, MutableSequence[ElementType]]:
        return self._elements[i]

    def __setitem__(self, i: Union[int, slice], o: Any) -> None:
        self._elements[i] = o
        if isinstance(i, int):
            self.enumeration[i] = self._parse_value(o)
        else:
            self.enumeration[i] = [self._parse_value(e) for e in o]

    def __delitem__(self, i: Union[int, slice]) -> None:
        del self._elements[i]
        del self.enumeration[i]

    def __len__(self) -> int:
        return len(self._elements)

    def insert(self, i: int, elem: ElementType) -> None:
        self._elements.insert(i, elem)
        self.enumeration.insert(i, self._parse_value(elem))

    def __repr__(self) -> str:
        if len(self.enumeration) > 5:
            return '%s(%s)' % (
                self.__class__.__name__, '[%s, ...]' % ', '.join(map(repr, self.enumeration[:5]))
            )
        else:
            return '%s(%r)' % (self.__class__.__name__, self.enumeration)

    def __call__(self, value: Any) -> None:
        if value in self.enumeration:
            return

        try:
            if math.isnan(value):
                if any(math.isnan(x) for x in self.enumeration):  # type: ignore[arg-type]
                    return
            elif math.isinf(value):
                if any(math.isinf(x) and str(value) == str(x)  # type: ignore[arg-type]
                       for x in self.enumeration):  # pragma: no cover
                    return
        except TypeError:
            pass

        reason = _("value must be one of {!r}").format(self.enumeration)
        raise XMLSchemaValidationError(self, value, reason)

    def get_annotation(self, i: int) -> Optional[XsdAnnotation]:
        """
        Get the XSD annotation of the i-th enumeration facet.

        :param i: an integer index.
        :returns: an XsdAnnotation object or `None`.
        """
        for child in self._elements[i]:
            if child.tag == XSD_ANNOTATION:
                return XsdAnnotation(child, self.schema, self)
        return None


class XsdPatternFacets(MutableSequence[ElementType], XsdFacet):
    """
    Sequence of XSD *pattern* facets. Values are validates if match any of patterns.

    ..  <pattern
          id = ID
          value = string
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </pattern>
    """
    _ADMITTED_TAGS = {XSD_PATTERN}
    patterns: List[Pattern[str]]

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: 'XsdAtomicRestriction',
                 base_type: Optional[BaseXsdType]) -> None:
        XsdFacet.__init__(self, elem, schema, parent, base_type)

    def _parse(self) -> None:
        self._elements = [self.elem]
        self.patterns = [self._parse_value(self.elem)]

    def _parse_value(self, elem: ElementType) -> Pattern[str]:
        try:
            python_pattern = translate_pattern(
                pattern=elem.attrib['value'],
                xsd_version=self.xsd_version,
                back_references=False,
                lazy_quantifiers=False,
                anchors=False
            )
            return re.compile(python_pattern)
        except KeyError:
            return re.compile(r'^.*$')
        except (RegexError, re.error, XMLSchemaDecodeError) as err:
            self.parse_error(str(err), elem)
            return re.compile(r'^.*$')

    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> ElementType: ...

    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> MutableSequence[ElementType]: ...

    def __getitem__(self, i: Union[int, slice]) \
            -> Union[ElementType, MutableSequence[ElementType]]:
        return self._elements[i]

    def __setitem__(self, i: Union[int, slice], o: Any) -> None:
        self._elements[i] = o
        if isinstance(i, int):
            self.patterns[i] = self._parse_value(o)
        else:
            self.patterns[i] = [self._parse_value(e) for e in o]

    def __delitem__(self, i: Union[int, slice]) -> None:
        del self._elements[i]
        del self.patterns[i]

    def __len__(self) -> int:
        return len(self._elements)

    def insert(self, i: int, elem: ElementType) -> None:
        self._elements.insert(i, elem)
        self.patterns.insert(i, self._parse_value(elem))

    def __repr__(self) -> str:
        s = repr(self.regexps)
        if len(s) < 70:
            return '%s(%s)' % (self.__class__.__name__, s)
        else:
            return '%s(%s...\'])' % (self.__class__.__name__, s[:70])

    def __call__(self, text: str) -> None:
        try:
            if all(pattern.match(text) is None for pattern in self.patterns):
                reason = _("value doesn't match any pattern of {!r}").format(self.regexps)
                raise XMLSchemaValidationError(self, text, reason)
        except TypeError as err:
            raise XMLSchemaValidationError(self, text, str(err)) from None

    @property
    def regexps(self) -> List[str]:
        return [e.attrib.get('value', '') for e in self._elements]

    def get_annotation(self, i: int) -> Optional[XsdAnnotation]:
        """
        Get the XSD annotation of the i-th pattern facet.

        :param i: an integer index.
        :returns: an XsdAnnotation object or `None`.
        """
        for child in self._elements[i]:
            if child.tag == XSD_ANNOTATION:
                return XsdAnnotation(child, self.schema, self)
        return None


class XsdAssertionXPathParser(XPath2Parser):
    """Parser for XSD 1.1 assertion facets."""


XsdAssertionXPathParser.unregister('last')
XsdAssertionXPathParser.unregister('position')


# noinspection PyUnusedLocal
@XsdAssertionXPathParser.method(  # type: ignore[no-untyped-def]
    XsdAssertionXPathParser.function('last', nargs=0))
def evaluate_last(self, context=None):
    raise self.missing_context("context item size is undefined")


# noinspection PyUnusedLocal
@XsdAssertionXPathParser.method(  # type: ignore[no-untyped-def]
    XsdAssertionXPathParser.function('position', nargs=0))
def evaluate_position(self, context=None):
    raise self.missing_context("context item position is undefined")


class XsdAssertionFacet(XsdFacet):
    """
    XSD 1.1 *assertion* facet for simpleType definitions.

    ..  <assertion
          id = ID
          test = an XPath expression
          xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </assertion>
    """
    _ADMITTED_TAGS = {XSD_ASSERTION}
    _root = ElementNode(elem=Element('root'))

    def __repr__(self) -> str:
        return '%s(test=%r)' % (self.__class__.__name__, self.path)

    def _parse(self) -> None:
        try:
            self.path = self.elem.attrib['test']
        except KeyError:
            self.parse_error(_("missing attribute 'test'"))
            self.path = 'true()'

        try:
            value = self.base_type.primitive_type.prefixed_name  # type: ignore[union-attr]
        except AttributeError:
            value = self.any_simple_type.prefixed_name

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace

        self.parser = XsdAssertionXPathParser(
            namespaces=self.namespaces,
            strict=False,
            variable_types={'value': value},
            default_namespace=self.xpath_default_namespace
        )

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.parse_error(err)
            self.token = self.parser.parse('true()')

    def __call__(self, value: AtomicValueType) -> None:
        context = XPathContext(self._root, variables={'value': value})
        try:
            if not self.token.evaluate(context):
                reason = _("value is not true with test path {!r}").format(self.path)
                raise XMLSchemaValidationError(self, value, reason)
        except ElementPathError as err:
            raise XMLSchemaValidationError(self, value, reason=str(err)) from None


XSD_10_FACETS_BUILDERS = {
    XSD_WHITE_SPACE: XsdWhiteSpaceFacet,
    XSD_LENGTH: XsdLengthFacet,
    XSD_MIN_LENGTH: XsdMinLengthFacet,
    XSD_MAX_LENGTH: XsdMaxLengthFacet,
    XSD_MIN_INCLUSIVE: XsdMinInclusiveFacet,
    XSD_MIN_EXCLUSIVE: XsdMinExclusiveFacet,
    XSD_MAX_INCLUSIVE: XsdMaxInclusiveFacet,
    XSD_MAX_EXCLUSIVE: XsdMaxExclusiveFacet,
    XSD_TOTAL_DIGITS: XsdTotalDigitsFacet,
    XSD_FRACTION_DIGITS: XsdFractionDigitsFacet,
    XSD_ENUMERATION: XsdEnumerationFacets,
    XSD_PATTERN: XsdPatternFacets
}

XSD_11_FACETS_BUILDERS = XSD_10_FACETS_BUILDERS.copy()
XSD_11_FACETS_BUILDERS.update({
    XSD_ASSERTION: XsdAssertionFacet,
    XSD_EXPLICIT_TIMEZONE: XsdExplicitTimezoneFacet
})

XSD_10_FACETS = set(XSD_10_FACETS_BUILDERS)
XSD_11_FACETS = set(XSD_11_FACETS_BUILDERS)

XSD_10_LIST_FACETS = {XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_PATTERN,
                      XSD_ENUMERATION, XSD_WHITE_SPACE}
XSD_11_LIST_FACETS = XSD_10_LIST_FACETS | {XSD_ASSERTION}

XSD_10_UNION_FACETS = {XSD_PATTERN, XSD_ENUMERATION}
XSD_11_UNION_FACETS = MULTIPLE_FACETS = {XSD_PATTERN, XSD_ENUMERATION, XSD_ASSERTION}


XsdFacetType = Union[XsdLengthFacet, XsdMinLengthFacet, XsdMaxLengthFacet,
                     XsdMinInclusiveFacet, XsdMinExclusiveFacet, XsdMaxInclusiveFacet,
                     XsdMaxExclusiveFacet, XsdTotalDigitsFacet, XsdFractionDigitsFacet,
                     XsdEnumerationFacets, XsdPatternFacets]
