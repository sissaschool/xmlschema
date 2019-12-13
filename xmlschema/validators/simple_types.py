# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
from __future__ import unicode_literals
from decimal import DecimalException

from ..compat import string_base_type, unicode_type
from ..etree import etree_element
from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..qnames import XSD_ANY_TYPE, XSD_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE, \
    XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE, XSD_PATTERN, \
    XSD_MIN_INCLUSIVE, XSD_MIN_EXCLUSIVE, XSD_MAX_INCLUSIVE, XSD_MAX_EXCLUSIVE, \
    XSD_LENGTH, XSD_MIN_LENGTH, XSD_MAX_LENGTH, XSD_WHITE_SPACE, XSD_ENUMERATION,\
    XSD_LIST, XSD_ANY_SIMPLE_TYPE, XSD_UNION, XSD_RESTRICTION, XSD_ANNOTATION, \
    XSD_ASSERTION, XSD_ID, XSD_IDREF, XSD_FRACTION_DIGITS, XSD_TOTAL_DIGITS, \
    XSD_EXPLICIT_TIMEZONE, XSD_ERROR, XSD_ASSERT, get_qname, local_name
from ..helpers import get_xsd_derivation_attribute

from .exceptions import XMLSchemaValidationError, XMLSchemaEncodeError, \
    XMLSchemaDecodeError, XMLSchemaParseError
from .xsdbase import XsdAnnotation, XsdType, ValidationMixin
from .facets import XsdFacet, XsdWhiteSpaceFacet, XSD_10_FACETS_BUILDERS, \
    XSD_11_FACETS_BUILDERS, XSD_10_FACETS, XSD_11_FACETS, XSD_10_LIST_FACETS, \
    XSD_11_LIST_FACETS, XSD_10_UNION_FACETS, XSD_11_UNION_FACETS, MULTIPLE_FACETS


def xsd_simple_type_factory(elem, schema, parent):
    """
    Factory function for XSD simple types. Parses the xs:simpleType element and its
    child component, that can be a restriction, a list or an union. Annotations are
    linked to simple type instance, omitting the inner annotation if both are given.
    """
    annotation = None
    try:
        child = elem[0]
    except IndexError:
        return schema.maps.types[XSD_ANY_SIMPLE_TYPE]
    else:
        if child.tag == XSD_ANNOTATION:
            annotation = XsdAnnotation(elem[0], schema, child)
            try:
                child = elem[1]
            except IndexError:
                schema.parse_error("(restriction | list | union) expected", elem)
                return schema.maps.types[XSD_ANY_SIMPLE_TYPE]

    if child.tag == XSD_RESTRICTION:
        xsd_type = schema.BUILDERS.restriction_class(child, schema, parent)
    elif child.tag == XSD_LIST:
        xsd_type = XsdList(child, schema, parent)
    elif child.tag == XSD_UNION:
        xsd_type = schema.BUILDERS.union_class(child, schema, parent)
    else:
        schema.parse_error("(restriction | list | union) expected", elem)
        return schema.maps.types[XSD_ANY_SIMPLE_TYPE]

    if annotation is not None:
        xsd_type.annotation = annotation

    try:
        xsd_type.name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        if parent is None:
            schema.parse_error("missing attribute 'name' in a global simpleType", elem)
            xsd_type.name = 'nameless_%s' % str(id(xsd_type))
    else:
        if parent is not None:
            schema.parse_error("attribute 'name' not allowed for a local simpleType", elem)
            xsd_type.name = None

    if 'final' in elem.attrib:
        try:
            xsd_type._final = get_xsd_derivation_attribute(elem, 'final')
        except ValueError as err:
            xsd_type.parse_error(err, elem)

    return xsd_type


class XsdSimpleType(XsdType, ValidationMixin):
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

    min_length = None
    max_length = None
    white_space = None
    patterns = None
    validators = ()
    allow_empty = True

    def __init__(self, elem, schema, parent, name=None, facets=None):
        super(XsdSimpleType, self).__init__(elem, schema, parent, name)
        if not hasattr(self, 'facets'):
            self.facets = facets or {}

    def __setattr__(self, name, value):
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
            if patterns is not None:
                self.patterns = patterns
                if all(p.match('') is None for p in patterns.patterns):
                    self.allow_empty = False

            enumeration = self.get_facet(XSD_ENUMERATION)
            if enumeration is not None and '' not in enumeration:
                self.allow_empty = False

            if value:
                if None in value:
                    validators = [value[None]]  # Use only the validator function!
                else:
                    validators = [v for k, v in value.items()
                                  if k not in {XSD_WHITE_SPACE, XSD_PATTERN, XSD_ASSERTION}]
                if XSD_ASSERTION in value:
                    assertions = value[XSD_ASSERTION]
                    if isinstance(assertions, list):
                        validators.extend(assertions)
                    else:
                        validators.append(assertions)
                if validators:
                    self.validators = validators

    def _parse_facets(self, facets):
        if facets and self.base_type is not None:
            if self.base_type.is_simple():
                if self.base_type.name == XSD_ANY_SIMPLE_TYPE:
                    self.parse_error("facets not allowed for a direct derivation of xs:anySimpleType")
            elif self.base_type.has_simple_content():
                if self.base_type.content_type.name == XSD_ANY_SIMPLE_TYPE:
                    self.parse_error("facets not allowed for a direct content derivation of xs:anySimpleType")

        # Checks the applicability of the facets
        if any(k not in self.admitted_facets for k in facets if k is not None):
            reason = "one or more facets are not applicable, admitted set is %r:"
            self.parse_error(reason % {local_name(e) for e in self.admitted_facets if e})

        # Check group base_type
        base_type = {t.base_type for t in facets.values() if isinstance(t, XsdFacet)}
        if len(base_type) > 1:
            self.parse_error("facet group must have the same base_type: %r" % base_type)
        base_type = base_type.pop() if base_type else None

        # Checks length based facets
        length = getattr(facets.get(XSD_LENGTH), 'value', None)
        min_length = getattr(facets.get(XSD_MIN_LENGTH), 'value', None)
        max_length = getattr(facets.get(XSD_MAX_LENGTH), 'value', None)
        if length is not None:
            if length < 0:
                self.parse_error("'length' value must be non negative integer")
            if min_length is not None:
                if min_length > length:
                    self.parse_error("'minLength' value must be less or equal to 'length'")
                min_length_facet = base_type.get_facet(XSD_MIN_LENGTH)
                length_facet = base_type.get_facet(XSD_LENGTH)
                if min_length_facet is None or \
                        (length_facet is not None and length_facet.base_type == min_length_facet.base_type):
                    self.parse_error("cannot specify both 'length' and 'minLength'")
            if max_length is not None:
                if max_length < length:
                    self.parse_error("'maxLength' value must be greater or equal to 'length'")
                max_length_facet = base_type.get_facet(XSD_MAX_LENGTH)
                length_facet = base_type.get_facet(XSD_LENGTH)
                if max_length_facet is None or \
                        (length_facet is not None and length_facet.base_type == max_length_facet.base_type):
                    self.parse_error("cannot specify both 'length' and 'maxLength'")
            min_length = max_length = length
        elif min_length is not None or max_length is not None:
            min_length_facet = base_type.get_facet(XSD_MIN_LENGTH)
            max_length_facet = base_type.get_facet(XSD_MAX_LENGTH)
            if min_length is not None:
                if min_length < 0:
                    self.parse_error("'minLength' value must be non negative integer")
                if max_length is not None and max_length < min_length:
                    self.parse_error("'maxLength' value is lesser than 'minLength'")
                if min_length_facet is not None and min_length_facet.value > min_length:
                    self.parse_error("'minLength' has a lesser value than parent")
                if max_length_facet is not None and min_length > max_length_facet.value:
                    self.parse_error("'minLength' has a greater value than parent 'maxLength'")

            if max_length is not None:
                if max_length < 0:
                    self.parse_error("'maxLength' value mu  st be non negative integer")
                if min_length_facet is not None and min_length_facet.value > max_length:
                    self.parse_error("'maxLength' has a lesser value than parent 'minLength'")
                if max_length_facet is not None and max_length > max_length_facet.value:
                    self.parse_error("'maxLength' has a greater value than parent")

        # Checks min/max values
        min_inclusive = getattr(facets.get(XSD_MIN_INCLUSIVE), 'value', None)
        min_exclusive = getattr(facets.get(XSD_MIN_EXCLUSIVE), 'value', None)
        max_inclusive = getattr(facets.get(XSD_MAX_INCLUSIVE), 'value', None)
        max_exclusive = getattr(facets.get(XSD_MAX_EXCLUSIVE), 'value', None)

        if min_inclusive is not None:
            if min_exclusive is not None:
                self.parse_error("cannot specify both 'minInclusive' and 'minExclusive")
            if max_inclusive is not None and min_inclusive > max_inclusive:
                self.parse_error("'minInclusive' must be less or equal to 'maxInclusive'")
            elif max_exclusive is not None and min_inclusive >= max_exclusive:
                self.parse_error("'minInclusive' must be lesser than 'maxExclusive'")

        elif min_exclusive is not None:
            if max_inclusive is not None and min_exclusive >= max_inclusive:
                self.parse_error("'minExclusive' must be lesser than 'maxInclusive'")
            elif max_exclusive is not None and min_exclusive > max_exclusive:
                self.parse_error("'minExclusive' must be less or equal to 'maxExclusive'")

        if max_inclusive is not None and max_exclusive is not None:
            self.parse_error("cannot specify both 'maxInclusive' and 'maxExclusive")

        # Checks fraction digits
        if XSD_TOTAL_DIGITS in facets:
            if XSD_FRACTION_DIGITS in facets and \
                    facets[XSD_TOTAL_DIGITS].value < facets[XSD_FRACTION_DIGITS].value:
                self.parse_error("fractionDigits facet value cannot be lesser than the "
                                 "value of totalDigits facet")
            total_digits = base_type.get_facet(XSD_TOTAL_DIGITS)
            if total_digits is not None and total_digits.value < facets[XSD_TOTAL_DIGITS].value:
                self.parse_error("totalDigits facet value cannot be greater than "
                                 "the value of the same facet in the base type")

        # Checks XSD 1.1 facets
        if XSD_EXPLICIT_TIMEZONE in facets:
            explicit_tz_facet = base_type.get_facet(XSD_EXPLICIT_TIMEZONE)
            if explicit_tz_facet and explicit_tz_facet.value in ('prohibited', 'required') \
                    and facets[XSD_EXPLICIT_TIMEZONE].value != explicit_tz_facet.value:
                self.parse_error("the explicitTimezone facet value cannot be changed if the base "
                                 "type has the same facet with value %r" % explicit_tz_facet.value)

        self.min_length = min_length
        self.max_length = max_length

    @property
    def min_value(self):
        min_exclusive_facet = self.get_facet(XSD_MIN_EXCLUSIVE)
        if min_exclusive_facet is None:
            return getattr(self.get_facet(XSD_MIN_INCLUSIVE), 'value', None)

        min_inclusive_facet = self.get_facet(XSD_MIN_INCLUSIVE)
        if min_inclusive_facet is None or min_inclusive_facet.value <= min_exclusive_facet.value:
            return min_exclusive_facet.value
        else:
            return min_inclusive_facet.value

    @property
    def max_value(self):
        max_exclusive_facet = self.get_facet(XSD_MAX_EXCLUSIVE)
        if max_exclusive_facet is None:
            return getattr(self.get_facet(XSD_MAX_INCLUSIVE), 'value', None)

        max_inclusive_facet = self.get_facet(XSD_MAX_INCLUSIVE)
        if max_inclusive_facet is None or max_inclusive_facet.value >= max_exclusive_facet.value:
            return max_exclusive_facet.value
        else:
            return max_inclusive_facet.value

    @property
    def admitted_facets(self):
        return XSD_10_FACETS if self.xsd_version == '1.0' else XSD_11_FACETS

    @property
    def built(self):
        return True

    @staticmethod
    def is_simple():
        return True

    @staticmethod
    def is_complex():
        return False

    @staticmethod
    def is_list():
        return False

    def is_empty(self):
        return self.max_length == 0

    def is_emptiable(self):
        return self.allow_empty

    def has_simple_content(self):
        return True

    def has_mixed_content(self):
        return False

    def is_element_only(self):
        return False

    def is_derived(self, other, derivation=None):
        if self is other:
            return True
        elif derivation and self.derivation and derivation != self.derivation:
            return False
        elif other.name in self._special_types:
            return True
        elif self.base_type is other:
            return True
        elif self.base_type is None:
            if hasattr(other, 'member_types'):
                return any(self.is_derived(m, derivation) for m in other.member_types)
            return False
        elif self.base_type.is_complex():
            if not self.base_type.has_simple_content():
                return False
            return self.base_type.content_type.is_derived(other, derivation)
        elif hasattr(other, 'member_types'):
            return any(self.is_derived(m, derivation) for m in other.member_types)
        else:
            return self.base_type.is_derived(other, derivation)

    def is_dynamic_consistent(self, other):
        return other.name in (XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE) or self.is_derived(other) or \
            hasattr(other, 'member_types') and any(self.is_derived(mt) for mt in other.member_types)

    def normalize(self, text):
        """
        Normalize and restrict value-space with pre-lexical and lexical facets.
        The normalized string is returned. Returns the argument if it isn't a string.

        :param text: text string encoded value.
        :return: normalized string.
        """
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        elif not isinstance(text, string_base_type):
            raise XMLSchemaValueError('argument is not a string: %r' % text)

        if self.white_space == 'replace':
            return self._REGEX_SPACE.sub(' ', text)
        elif self.white_space == 'collapse':
            return self._REGEX_SPACES.sub(' ', text).strip()
        else:
            return text

    def text_decode(self, text):
        return self.decode(text, validation='skip')

    def iter_decode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)

        if validation != 'skip' and obj is not None:
            if self.patterns is not None:
                for error in self.patterns(obj):
                    yield error

            for validator in self.validators:
                for error in validator(obj):
                    yield error
        yield obj

    def iter_encode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)
        elif validation != 'skip':
            yield self.encode_error(validation, obj, unicode_type)

        if validation != 'skip' and obj is not None:
            if self.patterns is not None:
                for error in self.patterns(obj):
                    yield error

            for validator in self.validators:
                for error in validator(obj):
                    yield error

        yield obj

    def get_facet(self, tag):
        return self.facets.get(tag)


#
# simpleType's derived classes:
class XsdAtomic(XsdSimpleType):
    """
    Class for atomic simpleType definitions. An atomic definition has
    a base_type attribute that refers to primitive or derived atomic
    built-in type or another derived simpleType.
    """
    to_python = str
    _special_types = {XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE}
    _ADMITTED_TAGS = {XSD_RESTRICTION, XSD_SIMPLE_TYPE}

    def __init__(self, elem, schema, parent, name=None, facets=None, base_type=None):
        if base_type is None:
            self.primitive_type = self
        else:
            self.base_type = base_type
        super(XsdAtomic, self).__init__(elem, schema, parent, name, facets)

    def __repr__(self):
        if self.name is None:
            return '%s(primitive_type=%r)' % (self.__class__.__name__, self.primitive_type.local_name)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        super(XsdAtomic, self).__setattr__(name, value)
        if name == 'base_type':
            assert isinstance(value, XsdType)
            if not hasattr(self, 'white_space'):
                try:
                    self.white_space = self.base_type.white_space
                except AttributeError:
                    pass
            try:
                if value.is_simple():
                    self.primitive_type = self.base_type.primitive_type
                else:
                    self.primitive_type = self.base_type.content_type.primitive_type
            except AttributeError:
                self.primitive_type = value

    @property
    def admitted_facets(self):
        if self.primitive_type.is_complex():
            return XSD_10_FACETS if self.xsd_version == '1.0' else XSD_11_FACETS
        return self.primitive_type.admitted_facets

    def get_facet(self, tag):
        try:
            return self.facets[tag]
        except KeyError:
            try:
                return self.base_type.get_facet(tag)
            except AttributeError:
                return

    @staticmethod
    def is_atomic():
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
    def __init__(self, elem, schema, name, python_type, base_type=None, admitted_facets=None,
                 facets=None, to_python=None, from_python=None):
        """
        :param name: the XSD type's qualified name.
        :param python_type: the correspondent Python's type. If a tuple or list of types \
        is provided uses the first and consider the others as compatible types.
        :param base_type: the reference base type, None if it's a primitive type.
        :param admitted_facets: admitted facets tags for type (required for primitive types).
        :param facets: optional facets validators.
        :param to_python: optional decode function.
        :param from_python: optional encode function.
        """
        if isinstance(python_type, (tuple, list)):
            self.instance_types, python_type = python_type, python_type[0]
        else:
            self.instance_types = python_type
        if not callable(python_type):
            raise XMLSchemaTypeError("%r object is not callable" % python_type.__class__)

        if base_type is None and not admitted_facets and name != XSD_ERROR:
            raise XMLSchemaValueError("argument 'admitted_facets' must be a not empty set of a primitive type")
        self._admitted_facets = admitted_facets

        super(XsdAtomicBuiltin, self).__init__(elem, schema, None, name, facets, base_type)
        self.python_type = python_type
        self.to_python = to_python or python_type
        self.from_python = from_python or unicode_type

    def __repr__(self):
        return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def _parse(self):
        pass

    @property
    def admitted_facets(self):
        return self._admitted_facets or self.primitive_type.admitted_facets

    def is_datetime(self):
        return self.to_python.__name__ == 'fromstring'

    def iter_decode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)
        elif validation != 'skip' and obj is not None and not isinstance(obj, self.instance_types):
            yield self.decode_error(validation, obj, self.to_python,
                                    reason="value is not an instance of {!r}".format(self.instance_types))

        if self.name == XSD_IDREF:
            try:
                id_map = kwargs['id_map']
            except KeyError:
                pass
            else:
                if obj not in id_map:
                    id_map[obj] = 0

        elif self.name == XSD_ID and kwargs.get('level') != 0:
            try:
                id_map = kwargs['id_map']
            except KeyError:
                pass
            else:
                if not id_map[obj]:
                    id_map[obj] = 1
                else:
                    yield self.validation_error(validation, "Duplicated xsd:ID value {!r}".format(obj))

        if validation == 'skip':
            try:
                yield self.to_python(obj)
            except (ValueError, DecimalException):
                yield unicode_type(obj)
            return

        if self.patterns is not None:
            for error in self.patterns(obj):
                yield error

        try:
            result = self.to_python(obj)
        except (ValueError, DecimalException) as err:
            yield self.decode_error(validation, obj, self.to_python, reason=str(err))
            yield None
            return
        except TypeError:
            # xs:error type (eg. an XSD 1.1 type alternative used to catch invalid values)
            yield self.validation_error(validation, "Invalid value {!r}".format(obj))
            yield None
            return

        for validator in self.validators:
            for error in validator(result):
                yield error

        yield result

    def iter_encode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)

        if validation == 'skip':
            try:
                yield self.from_python(obj)
            except ValueError:
                yield unicode_type(obj)
            return

        elif isinstance(obj, bool):
            types_ = self.instance_types
            if types_ is not bool or (isinstance(types_, tuple) and bool in types_):
                reason = "boolean value {!r} requires a {!r} decoder.".format(obj, bool)
                yield self.encode_error(validation, obj, self.from_python, reason)
                obj = self.python_type(obj)

        elif not isinstance(obj, self.instance_types):
            reason = "{!r} is not an instance of {!r}.".format(obj, self.instance_types)
            yield self.encode_error(validation, obj, self.from_python, reason)
            try:
                value = self.python_type(obj)
                if value != obj:
                    raise ValueError()
                else:
                    obj = value
            except ValueError:
                yield self.encode_error(validation, obj, self.from_python)
                yield None
                return
            except TypeError:
                yield self.validation_error(validation, "Invalid value {!r}".format(obj))
                yield None
                return

        for validator in self.validators:
            for error in validator(obj):
                yield error

        try:
            text = self.from_python(obj)
        except ValueError:
            yield self.encode_error(validation, obj, self.from_python)
            yield None
        else:
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield error
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
    _ADMITTED_TAGS = {XSD_LIST}
    _white_space_elem = etree_element(XSD_WHITE_SPACE, attrib={'value': 'collapse', 'fixed': 'true'})

    def __init__(self, elem, schema, parent, name=None):
        facets = {XSD_WHITE_SPACE: XsdWhiteSpaceFacet(self._white_space_elem, schema, self, self)}
        super(XsdList, self).__init__(elem, schema, parent, name, facets)

    def __repr__(self):
        if self.name is None:
            return '%s(item_type=%r)' % (self.__class__.__name__, self.base_type)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and value.tag != XSD_LIST:
            if value.tag == XSD_SIMPLE_TYPE:
                for child in value:
                    if child.tag == XSD_LIST:
                        super(XsdList, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError("a %r definition required for %r." % (XSD_LIST, self))
        elif name == 'base_type':
            if not value.is_atomic():
                raise XMLSchemaValueError("%r: a list must be based on atomic data types." % self)
        elif name == 'white_space' and value is None:
            value = 'collapse'
        super(XsdList, self).__setattr__(name, value)

    def _parse(self):
        super(XsdList, self)._parse()
        elem = self.elem

        child = self._parse_child_component(elem)
        if child is not None:
            # Case of a local simpleType declaration inside the list tag
            try:
                base_type = xsd_simple_type_factory(child, self.schema, self)
            except XMLSchemaParseError as err:
                self.parse_error(err, elem)
                base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]

            if 'itemType' in elem.attrib:
                self.parse_error("ambiguous list type declaration", self)

        else:
            # List tag with itemType attribute that refers to a global type
            try:
                item_qname = self.schema.resolve_qname(elem.attrib['itemType'])
            except (KeyError, ValueError, RuntimeError) as err:
                if 'itemType' not in elem.attrib:
                    self.parse_error("missing list type declaration")
                else:
                    self.parse_error(err)
                base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]
            else:
                try:
                    base_type = self.maps.lookup_type(item_qname)
                except KeyError:
                    self.parse_error("unknown itemType %r" % elem.attrib['itemType'], elem)
                    base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]
                else:
                    if isinstance(base_type, tuple):
                        self.parse_error("circular definition found for type {!r}".format(item_qname))
                        base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]

        if base_type.final == '#all' or 'list' in base_type.final:
            self.parse_error("'final' value of the itemType %r forbids derivation by list" % base_type)

        if base_type is self.any_atomic_type:
            self.parse_error("Cannot use xs:anyAtomicType as base type of a user-defined type")

        try:
            self.base_type = base_type
        except XMLSchemaValueError as err:
            self.parse_error(str(err), elem)
            self.base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]
        else:
            if not base_type.allow_empty and self.min_length != 0:
                self.allow_empty = False

    @property
    def admitted_facets(self):
        return XSD_10_LIST_FACETS if self.xsd_version == '1.0' else XSD_11_LIST_FACETS

    @property
    def item_type(self):
        return self.base_type

    @staticmethod
    def is_atomic():
        return False

    @staticmethod
    def is_list():
        return True

    def is_derived(self, other, derivation=None):
        if self is other:
            return True
        elif derivation and self.derivation and derivation != self.derivation:
            return False
        elif other.name in self._special_types:
            return True
        elif self.base_type is other:
            return True
        else:
            return False

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.base_type.parent is not None:
            for obj in self.base_type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)

        items = []
        for chunk in obj.split():
            for result in self.base_type.iter_decode(chunk, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    items.append(result)

        yield items

    def iter_encode(self, obj, validation='lax', **kwargs):
        if not hasattr(obj, '__iter__') or isinstance(obj, (str, unicode_type, bytes)):
            obj = [obj]

        encoded_items = []
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
    _ADMITTED_TYPES = XsdSimpleType
    _ADMITTED_TAGS = {XSD_UNION}

    member_types = None

    def __init__(self, elem, schema, parent, name=None):
        super(XsdUnion, self).__init__(elem, schema, parent, name, facets=None)

    def __repr__(self):
        if self.name is None:
            return '%s(member_types=%r)' % (self.__class__.__name__, self.member_types)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and value.tag != XSD_UNION:
            if value.tag == XSD_SIMPLE_TYPE:
                for child in value:
                    if child.tag == XSD_UNION:
                        super(XsdUnion, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError("a %r definition required for %r." % (XSD_UNION, self))

        elif name == 'white_space':
            if not (value is None or value == 'collapse'):
                raise XMLSchemaValueError("Wrong value % for attribute 'white_space'." % value)
            value = 'collapse'
        super(XsdUnion, self).__setattr__(name, value)

    def _parse(self):
        super(XsdUnion, self)._parse()
        elem = self.elem
        member_types = []

        for child in filter(lambda x: x.tag != XSD_ANNOTATION, elem):
            mt = xsd_simple_type_factory(child, self.schema, self)
            if isinstance(mt, XMLSchemaParseError):
                self.parse_error(mt)
            else:
                member_types.append(mt)

        if 'memberTypes' in elem.attrib:
            for name in elem.attrib['memberTypes'].split():
                try:
                    type_qname = self.schema.resolve_qname(name)
                except (KeyError, ValueError, RuntimeError) as err:
                    self.parse_error(err)
                    continue

                try:
                    mt = self.maps.lookup_type(type_qname)
                except KeyError:
                    self.parse_error("unknown member type %r" % type_qname)
                    mt = self.maps.types[XSD_ANY_ATOMIC_TYPE]
                except XMLSchemaParseError as err:
                    self.parse_error(err)
                    mt = self.maps.types[XSD_ANY_ATOMIC_TYPE]

                if isinstance(mt, tuple):
                    self.parse_error("circular definition found on xs:union type {!r}".format(self.name))
                    continue
                elif not isinstance(mt, self._ADMITTED_TYPES):
                    self.parse_error("a {!r} required, not {!r}".format(self._ADMITTED_TYPES, mt))
                    continue
                elif mt.final == '#all' or 'union' in mt.final:
                    self.parse_error("'final' value of the memberTypes %r forbids derivation by union" % member_types)

                member_types.append(mt)

        if not member_types:
            self.parse_error("missing xs:union type declarations", elem)
            self.member_types = [self.maps.types[XSD_ANY_ATOMIC_TYPE]]
        elif any(mt is self.any_atomic_type for mt in member_types):
            self.parse_error("Cannot use xs:anyAtomicType as base type of a user-defined type")
        else:
            self.member_types = member_types
            if all(not mt.allow_empty for mt in member_types):
                self.allow_empty = False

    @property
    def admitted_facets(self):
        return XSD_10_UNION_FACETS if self.xsd_version == '1.0' else XSD_11_UNION_FACETS

    def is_atomic(self):
        return all(mt.is_atomic() for mt in self.member_types)

    def is_list(self):
        return all(mt.is_list() for mt in self.member_types)

    def is_dynamic_consistent(self, other):
        return other.name in (XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE) or \
            other.is_derived(self) or hasattr(other, 'member_types') and \
            any(mt1.is_derived(mt2) for mt1 in other.member_types for mt2 in self.member_types)

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for mt in filter(lambda x: x.parent is not None, self.member_types):
            for obj in mt.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, obj, validation='lax', patterns=None, **kwargs):
        # Try decoding the whole text
        for member_type in self.member_types:
            for result in member_type.iter_decode(obj, validation='lax', **kwargs):
                if not isinstance(result, XMLSchemaValidationError):
                    if validation != 'skip' and patterns:
                        obj = member_type.normalize(obj)
                        for error in patterns(obj):
                            yield error

                    yield result
                    return
                break

        if validation != 'skip' and ' ' not in obj.strip():
            reason = "invalid value %r." % obj
            yield self.decode_error(validation, obj, self.member_types, reason)

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
                    items.append(unicode_type(chunk))

        if validation != 'skip':
            if not_decodable:
                reason = "no type suitable for decoding the values %r." % not_decodable
                yield self.decode_error(validation, obj, self.member_types, reason)

        yield items if len(items) > 1 else items[0] if items else None

    def iter_encode(self, obj, validation='lax', **kwargs):
        for member_type in self.member_types:
            for result in member_type.iter_encode(obj, validation='lax', **kwargs):
                if result is not None and not isinstance(result, XMLSchemaValidationError):
                    yield result
                    return
                elif validation == 'strict':
                    # In 'strict' mode avoid lax encoding by similar types (eg. float encoded by int)
                    break

        if hasattr(obj, '__iter__') and not isinstance(obj, (str, unicode_type, bytes)):
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
            reason = "no type suitable for encoding the object."
            yield self.encode_error(validation, obj, self.member_types, reason)
            yield None
        else:
            yield unicode_type(obj)


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
    FACETS_BUILDERS = XSD_10_FACETS_BUILDERS
    derivation = 'restriction'
    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE}

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None:
            if self.name != XSD_ANY_ATOMIC_TYPE and value.tag != XSD_RESTRICTION:
                if not (value.tag == XSD_SIMPLE_TYPE and value.get('name') is not None):
                    raise XMLSchemaValueError("an xs:restriction definition required for %r." % self)
        super(XsdAtomicRestriction, self).__setattr__(name, value)

    def _parse(self):
        super(XsdAtomicRestriction, self)._parse()
        elem = self.elem
        if elem.get('name') == XSD_ANY_ATOMIC_TYPE:
            return  # skip special type xs:anyAtomicType
        elif elem.tag == XSD_SIMPLE_TYPE and elem.get('name') is not None:
            elem = self._parse_child_component(elem)  # Global simpleType with internal restriction

        if self.name is not None and self.parent is not None:
            self.parse_error("'name' attribute in a local simpleType definition", elem)

        base_type = None
        facets = {}
        has_attributes = False
        has_simple_type_child = False

        if 'base' in elem.attrib:
            try:
                base_qname = self.schema.resolve_qname(elem.attrib['base'])
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err, elem)
                base_type = self.maps.type[XSD_ANY_ATOMIC_TYPE]
            else:
                if base_qname == self.name:
                    if self.redefine is None:
                        self.parse_error("wrong definition with self-reference", elem)
                        base_type = self.maps.type[XSD_ANY_ATOMIC_TYPE]
                    else:
                        base_type = self.base_type
                else:
                    if self.redefine is not None:
                        self.parse_error("wrong redefinition without self-reference", elem)

                    try:
                        base_type = self.maps.lookup_type(base_qname)
                    except KeyError:
                        self.parse_error("unknown type %r." % elem.attrib['base'])
                        base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]
                    except XMLSchemaParseError as err:
                        self.parse_error(err)
                        base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]
                    else:
                        if isinstance(base_type, tuple):
                            self.parse_error("circularity definition between %r and %r" % (self, base_qname), elem)
                            base_type = self.maps.types[XSD_ANY_ATOMIC_TYPE]

            if base_type.is_simple() and base_type.name == XSD_ANY_SIMPLE_TYPE:
                self.parse_error("wrong base type {!r}, an atomic type required")
            elif base_type.is_complex():
                if base_type.mixed and base_type.is_emptiable():
                    child = self._parse_child_component(elem, strict=False)
                    if child is None:
                        self.parse_error("an xs:simpleType definition expected")
                    elif child.tag != XSD_SIMPLE_TYPE:
                        # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                        self.parse_error(
                            "when a complexType with simpleContent restricts a complexType "
                            "with mixed and with emptiable content then a simpleType child "
                            "declaration is required.", elem
                        )
                elif self.parent is None or self.parent.is_simple():
                    self.parse_error("simpleType restriction of %r is not allowed" % base_type, elem)

        for child in filter(lambda x: x.tag != XSD_ANNOTATION, elem):
            if child.tag in self._CONTENT_TAIL_TAGS:
                has_attributes = True  # only if it's a complexType restriction
            elif has_attributes:
                self.parse_error("unexpected tag after attribute declarations", child)
            elif child.tag == XSD_SIMPLE_TYPE:
                # Case of simpleType declaration inside a restriction
                if has_simple_type_child:
                    self.parse_error("duplicated simpleType declaration", child)

                if base_type is None:
                    try:
                        base_type = xsd_simple_type_factory(child, self.schema, self)
                    except XMLSchemaParseError as err:
                        self.parse_error(err)
                        base_type = self.maps.types[XSD_ANY_SIMPLE_TYPE]
                elif base_type.is_complex():
                    if base_type.admit_simple_restriction():
                        base_type = self.schema.BUILDERS.complex_type_class(
                            elem=elem,
                            schema=self.schema,
                            parent=self,
                            content_type=xsd_simple_type_factory(child, self.schema, self),
                            attributes=base_type.attributes,
                            mixed=base_type.mixed,
                            block=base_type.block,
                            final=base_type.final,
                        )
                elif 'base' in elem.attrib:
                    self.parse_error("restriction with 'base' attribute and simpleType declaration", child)

                has_simple_type_child = True
            else:
                try:
                    facet_class = self.FACETS_BUILDERS[child.tag]
                except KeyError:
                    self.parse_error("unexpected tag %r in restriction:" % child.tag)
                    continue

                if child.tag not in facets:
                    facets[child.tag] = facet_class(child, self.schema, self, base_type)
                elif child.tag not in MULTIPLE_FACETS:
                    self.parse_error("multiple %r constraint facet" % local_name(child.tag))
                elif child.tag != XSD_ASSERTION:
                    facets[child.tag].append(child)
                else:
                    assertion = facet_class(child, self.schema, self, base_type)
                    try:
                        facets[child.tag].append(assertion)
                    except AttributeError:
                        facets[child.tag] = [facets[child.tag], assertion]

        if base_type is None:
            self.parse_error("missing base type in restriction:", self)
        elif base_type.final == '#all' or 'restriction' in base_type.final:
            self.parse_error("'final' value of the baseType %r forbids derivation by restriction" % base_type)
        if base_type is self.any_atomic_type:
            self.parse_error("Cannot use xs:anyAtomicType as base type of a user-defined type")

        self.base_type = base_type
        self.facets = facets

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.base_type.parent is not None:
            for obj in self.base_type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, obj, validation='lax', **kwargs):
        if isinstance(obj, (string_base_type, bytes)):
            obj = self.normalize(obj)

        if self.base_type.is_simple():
            base_type = self.base_type
        elif self.base_type.has_simple_content():
            base_type = self.base_type.content_type
        elif self.base_type.mixed:
            yield obj
            return
        else:
            raise XMLSchemaValueError("wrong base type %r: a simpleType or a complexType with "
                                      "simple or mixed content required." % self.base_type)

        if validation != 'skip' and self.patterns:
            if not isinstance(self.primitive_type, XsdUnion):
                for error in self.patterns(obj):
                    yield error
            elif 'patterns' not in kwargs:
                kwargs['patterns'] = self.patterns

        for result in base_type.iter_decode(obj, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
                if isinstance(result, XMLSchemaDecodeError):
                    yield unicode_type(obj) if validation == 'skip' else None
            else:
                if validation != 'skip' and result is not None:
                    for validator in self.validators:
                        for error in validator(result):
                            yield error

                yield result
                return

    def iter_encode(self, obj, validation='lax', **kwargs):
        if self.is_list():
            if not hasattr(obj, '__iter__') or isinstance(obj, (str, unicode_type, bytes)):
                obj = [] if obj is None or obj == '' else [obj]
            base_type = self.base_type
        else:
            if isinstance(obj, (string_base_type, bytes)):
                obj = self.normalize(obj)

            if self.base_type.is_simple():
                base_type = self.base_type
            elif self.base_type.has_simple_content():
                base_type = self.base_type.content_type
            elif self.base_type.mixed:
                yield unicode_type(obj)
                return
            else:
                raise XMLSchemaValueError("wrong base type %r: a simpleType or a complexType with "
                                          "simple or mixed content required." % self.base_type)

        for result in base_type.iter_encode(obj, validation):
            if isinstance(result, XMLSchemaValidationError):
                yield result
                if isinstance(result, XMLSchemaEncodeError):
                    yield unicode_type(obj) if validation == 'skip' else None
                    return
            else:
                if validation != 'skip' and self.validators and obj is not None:
                    if isinstance(obj, (string_base_type, bytes)):
                        if self.primitive_type.is_datetime():
                            obj = self.primitive_type.to_python(obj)

                    for validator in self.validators:
                        for error in validator(obj):
                            yield error

                yield result
                return

    def is_list(self):
        return self.primitive_type.is_list()


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
    FACETS_BUILDERS = XSD_11_FACETS_BUILDERS
    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE, XSD_ASSERT}
