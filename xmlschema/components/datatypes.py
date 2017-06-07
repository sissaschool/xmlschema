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
    XMLSchemaTypeError, XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError
)
from ..qnames import XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG
from .xsdbase import check_type, check_value, XsdComponent
from .facets import XSD11_FACETS, LIST_FACETS, UNION_FACETS, check_facets_group


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
    def __init__(self, name=None, elem=None, schema=None, facets=None):
        super(XsdSimpleType, self).__init__(name, elem, schema)
        self.facets = facets or {}
        self.white_space = getattr(self.facets.get(XSD_WHITE_SPACE_TAG), 'value', None)
        self.patterns = self.facets.get(XSD_PATTERN_TAG)
        self.validators = [
            v for k, v in self.facets.items()
            if k not in (XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG) and callable(v)
        ]
        check_facets_group(self.facets, self.admitted_facets, elem)

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('list', 'union', 'restriction'))

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS
        except AttributeError:
            return XSD11_FACETS.union({None})

    @staticmethod
    def is_simple():
        return True

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
            if self.patterns:
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
            if self.patterns:
                for error in self.patterns(text):
                    yield error
            for validator in self.validators:
                for error in validator(text):
                    yield error
        yield text


#
# simpleType's derived classes:
class XsdAtomic(XsdSimpleType):
    """
    Class for atomic simpleType definitions. An atomic definition has 
    a base_type attribute that refers to primitive or derived atomic 
    built-in type or another derived simpleType.
    """
    def __init__(self, base_type, name=None, elem=None, schema=None, facets=None):
        self.base_type = base_type
        super(XsdAtomic, self).__init__(name, elem, schema, facets)
        self.white_space = self.white_space or getattr(base_type, 'white_space', None)

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
    def admitted_facets(self):
        primitive_type = self.primitive_type
        if isinstance(primitive_type, (XsdList, XsdUnion)):
            return primitive_type.admitted_facets
        try:
            facets = set(primitive_type.facets.keys())
        except AttributeError:
            return XSD11_FACETS.union({None})
        else:
            if self.schema:
                return self.schema.FACETS.intersection(facets)
            else:
                return set(primitive_type.facets.keys()).union({None})


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
    def __init__(self, name, python_type, base_type=None, facets=None, to_python=None, from_python=None):
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
        super(XsdAtomicBuiltin, self).__init__(base_type, name, facets=facets)
        self.python_type = python_type
        self.to_python = to_python or python_type
        self.from_python = from_python or unicode_type

    def iter_decode(self, text, validate=True, **kwargs):
        _text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(_text):
                yield error

        try:
            result = self.to_python(_text)
        except ValueError:
            yield XMLSchemaDecodeError(self, text, self.to_python)
            yield unicode_type(text) if not kwargs.get('skip_errors') else None
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

    def __init__(self, item_type, name=None, elem=None, schema=None, facets=None):
        super(XsdList, self).__init__(name, elem, schema, facets)
        self.item_type = item_type
        self.white_space = self.white_space or 'collapse'

    def __setattr__(self, name, value):
        if name == "item_type":
            check_type(value, XsdSimpleType)
        super(XsdList, self).__setattr__(name, value)

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(LIST_FACETS)
        except AttributeError:
            return LIST_FACETS

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
                elif isinstance(result, XMLSchemaDecodeError):
                    yield result
                    if not kwargs.get('skip_errors'):
                        items.append(unicode_type(chunk))
                    else:
                        items.append(None)
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
    def __init__(self, member_types, name=None, elem=None, schema=None, facets=None):
        super(XsdUnion, self).__init__(name, elem, schema, facets)
        self.member_types = member_types
        self.white_space = self.white_space or 'collapse'

    def __setattr__(self, name, value):
        if name == "member_types":
            for member_type in value:
                check_type(member_type, XsdSimpleType)
        elif name == 'white_space':
            check_value(value, None, 'collapse')
        super(XsdUnion, self).__setattr__(name, value)

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(UNION_FACETS)
        except AttributeError:
            return UNION_FACETS

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
        yield XMLSchemaDecodeError(
            self, text, self.member_types, reason="no type suitable for decoding the text."
        )
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
    def __init__(self, base_type, name=None, elem=None, schema=None, facets=None):
        super(XsdAtomicRestriction, self).__init__(base_type, name, elem, schema, facets)

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate and self.patterns:
            for error in self.patterns(text):
                yield error

        for result in self.base_type.iter_decode(text, validate, **kwargs):
            if isinstance(result, XMLSchemaDecodeError):
                yield result
                yield unicode_type(text) if not kwargs.get('skip_errors') else None
                return
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
