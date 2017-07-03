# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
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
from decimal import Decimal

from ..core import unicode_type
from ..exceptions import (
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError,
    XMLSchemaParseError, XMLSchemaAttributeError,
    XMLSchemaTypeError, XMLSchemaValueError)
from ..qnames import (
    get_qname, reference_to_qname, XSD_SIMPLE_TYPE_TAG, XSD_ANY_ATOMIC_TYPE,
    XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG, XSD_ENUMERATION_TAG, XSD_PATTERN_TAG,
    XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG, XSD_LENGTH_TAG,
    XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_WHITE_SPACE_TAG, local_name, XSD_LIST_TAG, XSD_ANY_SIMPLE_TYPE,
    XSD_UNION_TAG, XSD_RESTRICTION_TAG, XSD_COMPLEX_TYPE_TAG)
from ..utils import check_type, check_value
from .xsdbase import get_xsd_derivation_attribute, XsdComponent, get_xsd_component, iter_xsd_declarations
from .facets import (
    XsdFacet, XSD11_FACETS, LIST_FACETS, UNION_FACETS, XsdPatternsFacet, XsdUniqueFacet, XsdEnumerationFacet
)


def xsd_simple_type_factory(elem, schema, is_global=False):
    try:
        name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        name = None
    else:
        if name == XSD_ANY_SIMPLE_TYPE:
            return

    child = get_xsd_component(elem)
    if child.tag == XSD_RESTRICTION_TAG:
        return XsdAtomicRestriction(child, schema, is_global=is_global, name=name)
    elif child.tag == XSD_LIST_TAG:
        return XsdList(child, schema, is_global=is_global, name=name)
    elif child.tag == XSD_UNION_TAG:
        return XsdUnion(child, schema, is_global=is_global, name=name)
    else:
        # Return an error for the caller
        return XMLSchemaValueError('(restriction|list|union) expected', child)


class XsdSimpleType(XsdComponent):
    """
    Base class for simpleTypes definitions. Generally used only for
    instances of xs:anySimpleType.

    <simpleType
      final = (#all | List of (list | union | restriction))
      id = ID
      name = NCName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (restriction | list | union))
    </simpleType>
    """
    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None, facets=None):
        self.min_length = self.max_length = self.min_value = self.max_value = None
        self.white_space = None
        self.patterns = None
        self.validators = []
        super(XsdSimpleType, self).__init__(elem, schema, is_global, parent, name)

    def __setattr__(self, name, value):
        if name == 'facets':
            check_type(value, dict)
            try:
                self.min_length, self.max_length, self.min_value, self.max_value = self.check_facets(value)
            except XMLSchemaParseError as err:
                if hasattr(self, 'error'):
                    self.error.append(err)
                else:
                    raise
            else:
                self.white_space = getattr(value.get(XSD_WHITE_SPACE_TAG), 'value', None)
                self.patterns = value.get(XSD_PATTERN_TAG)
                self.validators = [
                    v for k, v in value.items()
                    if k not in (XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG) and callable(v)
                ]
        super(XsdSimpleType, self).__setattr__(name, value)

    @property
    def admitted_tags(self):
        return {XSD_SIMPLE_TYPE_TAG}

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS
        except AttributeError:
            return XSD11_FACETS.union({None})

    @property
    def final(self):
        return get_xsd_derivation_attribute(self.elem, 'final', ('list', 'union', 'restriction'))

    @staticmethod
    def is_simple():
        return True

    @staticmethod
    def is_complex():
        return False

    def is_empty(self):
        return self.max_length == 0

    def is_emptiable(self):
        return self.min_length is None or self.min_length == 0

    def check_facets(self, facets):
        """
        Verifies the applicability and the mutual incompatibility of a group of facets.
        Raises a parse error if the facets group is invalid.

        :param facets: Dictionary with XSD facets.
        :returns Min and max values, a `None` value means no min/max limit.
        """
        # Checks the applicability of the facets
        admitted_facets = self.admitted_facets
        if not admitted_facets.issuperset(set([k for k in facets if k is not None])):
            admitted_facets = {local_name(e) for e in admitted_facets if e}
            msg = "one or more facets are not applicable, admitted set is %r:"
            raise XMLSchemaParseError(msg % admitted_facets, self)

        # Check group base_type
        base_type = {t.base_type for t in facets.values() if isinstance(t, XsdFacet)}
        if len(base_type) > 1:
            raise XMLSchemaValueError("facet group must have the same base_type: %r" % base_type)
        base_type = base_type.pop() if base_type else None

        # Checks length based facets
        length = getattr(facets.get(XSD_LENGTH_TAG), 'value', None)
        min_length = getattr(facets.get(XSD_MIN_LENGTH_TAG), 'value', None)
        max_length = getattr(facets.get(XSD_MAX_LENGTH_TAG), 'value', None)
        if length is not None:
            if length < 0:
                raise XMLSchemaParseError("'length' value must be non negative integer.", self)
            if min_length is not None:
                if min_length > length:
                    raise XMLSchemaParseError("'minLength' value must be less or equal to 'length'.", self)
                min_length_facet = base_type.get_facet(XSD_MIN_LENGTH_TAG, recursive=True)
                length_facet = base_type.get_facet(XSD_LENGTH_TAG, recursive=True)
                if min_length_facet is None or \
                        (length_facet is not None and length_facet.base_type == min_length_facet.base_type):
                    raise XMLSchemaParseError("cannot specify both 'length' and 'minLength'.", self)
            if max_length is not None:
                if max_length < length:
                    raise XMLSchemaParseError("'maxLength' value must be greater or equal to 'length'.", self)
                max_length_facet = base_type.get_facet(XSD_MAX_LENGTH_TAG, recursive=True)
                length_facet = base_type.get_facet(XSD_LENGTH_TAG, recursive=True)
                if max_length_facet is None or \
                        (length_facet is not None and length_facet.base_type == max_length_facet.base_type):
                    raise XMLSchemaParseError("cannot specify both 'length' and 'maxLength'.", self)
            min_length = max_length = length
        elif min_length is not None:
            if min_length < 0:
                raise XMLSchemaParseError("'minLength' value must be non negative integer.", self)
            if max_length is not None and max_length < min_length:
                raise XMLSchemaParseError("'maxLength' value is lesser than 'minLength'.", self)
            min_length_facet = base_type.get_facet(XSD_MIN_LENGTH_TAG)
            if min_length_facet is not None and min_length_facet.value > min_length:
                raise XMLSchemaParseError("parent 'minLength' has a lesser value.", self)
        elif max_length is not None:
            if max_length < 0:
                raise XMLSchemaParseError("'maxLength' value must be non negative integer.", self)
            max_length_facet = base_type.get_facet(XSD_MAX_LENGTH_TAG)
            if max_length_facet is not None and max_length_facet.value > min_length:
                raise XMLSchemaParseError("parent 'maxLength' has a greater value.", self)

        # Checks max/min
        min_inclusive = getattr(facets.get(XSD_MIN_INCLUSIVE_TAG), 'value', None)
        min_exclusive = getattr(facets.get(XSD_MIN_EXCLUSIVE_TAG), 'value', None)
        max_inclusive = getattr(facets.get(XSD_MAX_INCLUSIVE_TAG), 'value', None)
        max_exclusive = getattr(facets.get(XSD_MAX_EXCLUSIVE_TAG), 'value', None)
        if min_inclusive is not None and min_exclusive is not None:
            raise XMLSchemaParseError("cannot specify both 'minInclusive' and 'minExclusive.", self)
        if max_inclusive is not None and max_exclusive is not None:
            raise XMLSchemaParseError("cannot specify both 'maxInclusive' and 'maxExclusive.", self)

        if min_inclusive is not None:
            if max_inclusive is not None and min_inclusive > max_inclusive:
                raise XMLSchemaParseError("'minInclusive' must be less or equal to 'maxInclusive'", self)
            elif max_exclusive is not None and min_inclusive >= max_exclusive:
                raise XMLSchemaParseError("'minInclusive' must be lesser than 'maxExclusive'", self)
            min_value = max_inclusive
        elif min_exclusive is not None:
            if max_inclusive is not None and min_exclusive >= max_inclusive:
                raise XMLSchemaParseError("'minExclusive' must be lesser than 'maxInclusive'", self)
            elif max_exclusive is not None and min_exclusive > max_exclusive:
                raise XMLSchemaParseError("'minExclusive' must be less or equal to 'maxExclusive'", self)
            min_value = min_exclusive + 1
        else:
            min_value = None

        if max_inclusive is not None:
            max_value = max_inclusive
        elif max_exclusive is not None:
            max_value = max_exclusive - 1
        else:
            max_value = None

        base_min_value = getattr(base_type, 'min_value', None)
        base_max_value = getattr(base_type, 'max_value', None)
        if base_min_value is not None and min_value is not None and base_min_value > min_value:
            raise XMLSchemaParseError("minimum value of base_type is greater.", self)
        if base_max_value is not None and max_value is not None and base_max_value < max_value:
            raise XMLSchemaParseError("maximum value of base_type is lesser.", self)

        return min_length, max_length, min_value, max_value

    def normalize(self, obj):
        """
        Normalize and restrict value-space with pre-lexical and lexical facets.
        The normalized string is returned. Returns the argument if it isn't a string.

        :param obj: Text string or decoded value.
        :return: Normalized and restricted string.
        """
        try:
            if self.white_space == 'replace':
                obj = self._REGEX_SPACE.sub(u" ", obj)
            elif self.white_space == 'collapse':
                obj = self._REGEX_SPACES.sub(u" ", obj).strip()
        except TypeError:
            pass
        return obj

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate:
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield error

            for validator in self.validators:
                for error in validator(text):
                    yield error
        yield text

    def iter_encode(self, text, validate=True, **kwargs):
        if not isinstance(text, (str, unicode_type)):
            yield XMLSchemaEncodeError(self, text, unicode_type)

        if validate:
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield error
            for validator in self.validators:
                for error in validator(text):
                    yield error
        yield text

    def get_facet(self, tag, recursive=False):
        try:
            return self.facets[tag]
        except KeyError:
            if recursive and hasattr(self, 'base_type'):
                return getattr(self, 'base_type').get_facets(tag, recursive)
            else:
                return None


#
# simpleType's derived classes:
class XsdAtomic(XsdSimpleType):
    """
    Class for atomic simpleType definitions. An atomic definition has 
    a base_type attribute that refers to primitive or derived atomic 
    built-in type or another derived simpleType.
    """
    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None,
                 facets=None, base_type=None):
        super(XsdAtomic, self).__init__(elem, schema, is_global, parent, name, facets)
        if not hasattr(self, 'base_type'):
            if base_type is None and not isinstance(self, XsdAtomicBuiltin):
                raise XMLSchemaAttributeError("undefined 'base_type' attribute for %r." % self)
            self.base_type = base_type
        if not hasattr(self, 'facets'):
            self.facets = facets or {}
        elif not self.facets and facets:
            self.facets = facets

    def __setattr__(self, name, value):
        super(XsdAtomic, self).__setattr__(name, value)
        if name in ('base_type', 'white_space'):
            if getattr(self, 'white_space', None) is None:
                try:
                    white_space = self.base_type.white_space
                except AttributeError:
                    return
                else:
                    if white_space is not None:
                        self.white_space = white_space

    @property
    def primitive_type(self):
        if self.base_type is None:
            return self
        else:
            try:
                return self.base_type.primitive_type
            except AttributeError:
                # List or Union base_type.
                return self.base_type

    @property
    def admitted_tags(self):
        return {XSD_RESTRICTION_TAG, XSD_SIMPLE_TYPE_TAG}

    @property
    def admitted_facets(self):
        primitive_type = self.primitive_type
        if isinstance(primitive_type, (XsdList, XsdUnion)):
            return primitive_type.admitted_facets
        try:
            facets = set(primitive_type.facets.keys())
        except AttributeError:
            return XSD11_FACETS.union({None})
        else:
            try:
                return self.schema.FACETS.intersection(facets)
            except AttributeError:
                return set(primitive_type.facets.keys()).union({None})

    def check(self):
        if self.checked:
            return
        super(XsdAtomic, self).check()

        if self.name != XSD_ANY_ATOMIC_TYPE:
            try:
                self.base_type.check()
            except AttributeError:
                return  # For primitive atomic built-in types

            if self.base_type.valid is False:
                self._valid = False
            elif self.valid is not False and self.base_type.valid is None:
                self._valid = None


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
    def __init__(self, elem, schema, name, python_type, base_type=None,
                 facets=None, to_python=None, from_python=None):
        """
        :param name: The XSD type's qualified name.
        :param python_type: The correspondent Python's type.
        :param base_type: The reference base type, None if it's a primitive type.
        :param facets: Optional facets validators.
        :param to_python: The optional decode function.
        :param from_python: The optional encode function.
        """
        if not callable(python_type):
            raise XMLSchemaTypeError("%r object is not callable" % python_type.__class__)
        super(XsdAtomicBuiltin, self).__init__(elem, schema, is_global=True, facets=facets, base_type=base_type)
        self.name = name
        self.python_type = python_type
        self.to_python = to_python or python_type
        self.from_python = from_python or unicode_type

    def _parse(self):
        return

    def iter_decode(self, text, validate=True, **kwargs):
        _text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(_text):
                yield error

        try:
            result = self.to_python(_text)
        except ValueError as err:
            yield XMLSchemaDecodeError(self, text, self.to_python, reason=str(err))
            yield unicode_type(_text) if not kwargs.get('skip_errors') else None
            return

        if validate:
            for validator in self.validators:
                for error in validator(result):
                    yield error

        if isinstance(result, Decimal):
            try:
                result = kwargs.get('decimal_type')(result)
            except TypeError:
                pass
        yield result

    def iter_encode(self, obj, validate=True, **kwargs):
        try:
            if not isinstance(obj, self.python_type):
                if isinstance(obj, bool) or self.python_type == bool:
                    # Class checking is sufficient only for bool() values.
                    raise ValueError()
                elif self.python_type(obj) != obj:
                    raise ValueError()
        except ValueError:
            yield XMLSchemaEncodeError(self, obj, self.from_python)
            yield unicode_type(obj) if not kwargs.get('skip_errors') else None
            return

        if validate:
            for validator in self.validators:
                for error in validator(obj):
                    yield error
        yield self.from_python(obj)


class XsdList(XsdSimpleType):
    """
    Class for 'list' definitions. A list definition has an item_type attribute 
    that refers to an atomic or union simpleType definition.
    
    <list
      id = ID
      itemType = QName
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType?)
    </list>
    """

    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None,
                 facets=None, item_type=None):
        super(XsdList, self).__init__(elem, schema, is_global, parent, name, facets)
        if not hasattr(self, 'item_type'):
            if item_type is None:
                raise XMLSchemaAttributeError("undefined 'item_type' for %r." % self)
            self.item_type = item_type
        if not hasattr(self, 'facets'):
            self.facets = facets or {}
        elif not self.facets and facets:
            self.facets = facets

    def __setattr__(self, name, value):
        if name == 'item_type':
            check_type(value, XsdSimpleType)
        elif name == 'white_space' and value is None:
            value = 'collapse'
        super(XsdList, self).__setattr__(name, value)

    def _parse(self):
        super(XsdList, self)._parse()
        elem = self.elem
        schema = self.schema
        item_type = None

        child = get_xsd_component(elem, required=False)
        if child is not None:
            # Case of a local simpleType declaration inside the list tag
            item_type = xsd_simple_type_factory(child, schema, item_type)
            if isinstance(item_type, XMLSchemaParseError):
                self.errors.append(item_type)
                item_type = schema.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)
            if 'itemType' in elem.attrib:
                self.errors.append(XMLSchemaParseError("ambiguous list type declaration", self))
        elif 'itemType' in elem.attrib:
            # List tag with itemType attribute that refers to a global type
            item_qname = reference_to_qname(elem.attrib['itemType'], schema.namespaces)
            item_type = schema.maps.lookup_type(item_qname)
            if isinstance(item_type, XMLSchemaParseError):
                self.errors.append(item_type)
                item_type = schema.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)
        else:
            self.errors.append(XMLSchemaParseError("missing list type declaration", self))
            item_type = schema.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)
        self.item_type = item_type

    @property
    def admitted_tags(self):
        return {XSD_LIST_TAG}

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(LIST_FACETS)
        except AttributeError:
            return LIST_FACETS

    def check(self):
        if self.checked:
            return
        super(XsdList, self).check()

        self.item_type.check()
        if self.item_type.valid is False:
            self._valid = False
        elif self.valid is not False and self.item_type.valid is None:
            self._valid = None

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(text):
                yield error

        items = []
        for chunk in text.split():
            for result in self.item_type.iter_decode(chunk, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    items.append(result)

        if validate:
            for validator in self.validators:
                for error in validator(items):
                    yield error
        yield items

    def iter_encode(self, items, validate=True, **kwargs):
        if validate:
            for validator in self.validators:
                for error in validator(items):
                    yield error

        encoded_items = []
        for item in items:
            for result in self.item_type.iter_encode(item, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                elif isinstance(result, XMLSchemaEncodeError):
                    yield result
                    if not kwargs.get('skip_errors'):
                        encoded_items.append(unicode_type(item))
                    else:
                        items.append(None)
                else:
                    encoded_items.append(result)
        yield u' '.join(encoded_items)


class XsdUnion(XsdSimpleType):
    """
    Class for 'union' definitions. A union definition has a member_types 
    attribute that refers to a 'simpleType' definition.

    <union
      id = ID
      memberTypes = List of QName
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType*)
    </union>
    """
    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None,
                 facets=None, member_types=None):
        super(XsdUnion, self).__init__(elem, schema, is_global, parent, name, facets)
        if not hasattr(self, 'member_types'):
            if member_types is None:
                raise XMLSchemaAttributeError("undefined 'member_types' for %r." % self)
            self.member_types = member_types
        if not hasattr(self, 'facets'):
            self.facets = facets or {}
        elif not self.facets and facets:
            self.facets = facets

    def __setattr__(self, name, value):
        if name == "member_types":
            for member_type in value:
                check_type(member_type, XsdSimpleType)
            if not value:
                raise XMLSchemaValueError("%r attribute cannot be empty or None." % name)
        elif name == 'white_space':
            check_value(value, None, 'collapse')
            value = 'collapse'
        super(XsdUnion, self).__setattr__(name, value)

    def _parse(self):
        super(XsdUnion, self)._parse()
        elem = self.elem
        schema = self.schema
        member_types = []

        for child in iter_xsd_declarations(elem):
            mt = xsd_simple_type_factory(child, schema)
            if isinstance(mt, XMLSchemaParseError):
                self.errors.append(mt)
            else:
                member_types.append(mt)

        if 'memberTypes' in elem.attrib:
            for name in elem.attrib['memberTypes'].split():
                type_qname = reference_to_qname(name, schema.namespaces)
                mt = schema.maps.lookup_type(type_qname)
                if isinstance(mt, XMLSchemaParseError):
                    self.errors.append(mt)
                elif not isinstance(mt, XsdSimpleType):
                    self.errors.append(XMLSchemaParseError("a simpleType required", mt))
                else:
                    member_types.append(mt)

        if not member_types:
            self.errors.append(XMLSchemaParseError("missing union type declarations", self))

        self.member_types = member_types

    @property
    def admitted_tags(self):
        return {XSD_UNION_TAG}

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(UNION_FACETS)
        except AttributeError:
            return UNION_FACETS

    def check(self):
        if self.checked:
            return
        super(XsdUnion, self).check()

        for member_type in self.member_types:
            member_type.check()

        if any([mt.valid is False for mt in self.member_types]):
            self._valid = False
        elif self.valid is not False and any([mt.valid is None for mt in self.member_types]):
            self._valid = None

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(text):
                yield error

        for member_type in self.member_types:
            for result in member_type.iter_decode(text, validate, **kwargs):
                if not isinstance(result, XMLSchemaValidationError):
                    if validate:
                        for validator in self.validators:
                            for error in validator(result):
                                yield error
                    yield result
                    return

        error = XMLSchemaDecodeError(
            self, text, self.member_types, reason="no type suitable for decoding the text."
        )
        yield error
        yield unicode_type(text) if not kwargs.get('skip_errors') else None

    def iter_encode(self, obj, validate=True, **kwargs):
        for member_type in self.member_types:
            for result in member_type.iter_encode(obj, validate):
                if not isinstance(result, XMLSchemaValidationError):
                    if validate:
                        for validator in self.validators:
                            for error in validator(obj):
                                yield error
                    yield result
                    return
        yield XMLSchemaEncodeError(
            self, obj, self.member_types, reason="no type suitable for encoding the object."
        )
        yield unicode_type(obj) if not kwargs.get('skip_errors') else None


class XsdAtomicRestriction(XsdAtomic):
    """
    Class for XSD 1.0 atomic simpleType and complexType's simpleContent restrictions.

    <restriction
      base = QName
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive | 
      maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength | 
      enumeration | whiteSpace | pattern)*))
    </restriction>
    """
    def _parse(self):
        super(XsdAtomicRestriction, self)._parse()
        elem = self.elem
        schema = self.schema
        base_type = None
        facets = {}
        has_attributes = False
        has_simple_type_child = False

        if 'base' in self.elem.attrib:
            base_qname = reference_to_qname(elem.attrib['base'], schema.namespaces)
            base_type = schema.maps.lookup_type(base_qname)
            if isinstance(base_type, XMLSchemaParseError):
                self.errors.append(base_qname)
                base_type = schema.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)

            if base_type.is_complex() and base_type.admit_simple_restriction():
                if get_xsd_component(elem, strict=False).tag != XSD_SIMPLE_TYPE_TAG:
                    # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                    self.errors.append(XMLSchemaParseError(
                        "when a complexType with simpleContent restricts a complexType "
                        "with mixed and with emptiable content then a simpleType child "
                        "declaration is required.", elem
                    ))

        for child in iter_xsd_declarations(elem):
            if child.tag in {XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG}:
                has_attributes = True  # only if it's a complexType restriction
            elif has_attributes:
                self.errors.append(XMLSchemaParseError(
                    "unexpected tag after attribute declarations", child
                ))
            elif child.tag == XSD_SIMPLE_TYPE_TAG:
                # Case of simpleType declaration inside a restriction
                if has_simple_type_child:
                    self.errors.append(XMLSchemaParseError("duplicated simpleType declaration", child))
                elif base_type is None:
                    base_type = xsd_simple_type_factory(child, schema)
                    if isinstance(base_type, XMLSchemaParseError):
                        self.errors.append(base_type)
                        base_type = schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                else:
                    if base_type.is_complex() and base_type.admit_simple_restriction():
                        content_type = xsd_simple_type_factory(child, schema)
                        base_type = self.schema.complex_type_class(
                            content_type=content_type,
                            attributes=base_type.attributes,
                            name=None,
                            elem=elem,
                            schema=schema,
                            derivation=base_type.derivation,
                            mixed=base_type.mixed
                        )
                has_simple_type_child = True
            elif child.tag not in schema.FACETS:
                raise XMLSchemaParseError("unexpected tag in restriction", child)
            elif child.tag in (XSD_ENUMERATION_TAG, XSD_PATTERN_TAG):
                try:
                    facets[child.tag].append(child)
                except KeyError:
                    if child.tag == XSD_ENUMERATION_TAG:
                        facets[child.tag] = XsdEnumerationFacet(base_type, child, schema)
                    else:
                        facets[child.tag] = XsdPatternsFacet(base_type, child, schema)
            elif child.tag not in facets:
                facets[child.tag] = XsdUniqueFacet(base_type, child, schema)
            else:
                raise XMLSchemaParseError("multiple %r constraint facet" % local_name(child.tag), elem)

        if base_type is None:
            self.errors.append(XMLSchemaParseError("missing base type in restriction:", self))
        self.base_type = base_type
        self.facets = facets

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(text):
                yield error

        for result in self.base_type.iter_decode(text, validate, **kwargs):
            if isinstance(result, XMLSchemaDecodeError):
                yield result
                yield unicode_type(result) if not kwargs.get('skip_errors') else None
            elif isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                if validate:
                    for validator in self.validators:
                        for error in validator(result):
                            yield error
                yield result
                return

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.base_type.iter_encode(obj, validate):
            if isinstance(result, XMLSchemaEncodeError):
                yield result
                yield unicode_type(obj) if not kwargs.get('skip_errors') else None
                return
            elif isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                if validate:
                    for validator in self.validators:
                        for error in validator(obj):
                            yield error
                yield result
                return


class Xsd11AtomicRestriction(XsdAtomicRestriction):
    """
    Class for XSD 1.1 atomic simpleType and complexType's simpleContent restrictions.

    <restriction
      base = QName
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive | 
      maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength | 
      enumeration | whiteSpace | pattern | assertion | explicitTimezone | 
      {any with namespace: ##other})*))
    </restriction>
    """
    pass
