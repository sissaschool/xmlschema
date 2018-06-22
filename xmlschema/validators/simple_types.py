# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
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

from ..compat import unicode_type
from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..qnames import (
    get_qname, reference_to_qname, XSD_SIMPLE_TYPE_TAG, XSD_ANY_ATOMIC_TYPE, XSD_ATTRIBUTE_TAG,
    XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG, XSD_ENUMERATION_TAG, XSD_PATTERN_TAG,
    XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG,
    XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG, XSD_WHITE_SPACE_TAG, local_name,
    XSD_LIST_TAG, XSD_ANY_SIMPLE_TYPE, XSD_UNION_TAG, XSD_RESTRICTION_TAG, XSD_ANNOTATION_TAG,
)
from .exceptions import (
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaDecodeError, XMLSchemaParseError
)
from .parseutils import get_xsd_derivation_attribute, get_xsd_component
from .xsdbase import XsdType, ValidatorMixin
from .facets import XsdFacet, XSD_10_FACETS, XsdPatternsFacet, XsdSingleFacet, XsdEnumerationFacet


def xsd_simple_type_factory(elem, schema, is_global=False):
    try:
        name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        name = None
    else:
        if name == XSD_ANY_SIMPLE_TYPE:
            return

    try:
        child = elem[0]
    except IndexError:
        return schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
    else:
        if child.tag == XSD_ANNOTATION_TAG:
            try:
                child = elem[1]
            except IndexError:
                return schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)

    if child.tag == XSD_RESTRICTION_TAG:
        return XsdAtomicRestriction(child, schema, is_global=is_global, name=name)
    elif child.tag == XSD_LIST_TAG:
        return XsdList(child, schema, is_global=is_global, name=name)
    elif child.tag == XSD_UNION_TAG:
        return XsdUnion(child, schema, is_global=is_global, name=name)
    else:
        return schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)


class XsdSimpleType(XsdType, ValidatorMixin):
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
    def __init__(self, elem, schema, name=None, facets=None, is_global=False):
        super(XsdSimpleType, self).__init__(elem, schema, name, is_global)
        if not hasattr(self, 'facets'):
            self.facets = facets or {}
        elif facets:
            for k, v in self.facets:
                if k not in facets:
                    facets[k] = v
            self.facets = facets

    def __setattr__(self, name, value):
        if name == 'facets':
            assert isinstance(value, dict), "A dictionary is required for attribute 'facets'."
            super(XsdSimpleType, self).__setattr__(name, value)
            try:
                self.min_length, self.max_length, self.min_value, self.max_value = self.check_facets(value)
            except XMLSchemaParseError as err:
                if hasattr(self, 'errors'):
                    self._parse_error(err)
                else:
                    raise
                self.min_length = self.max_length = self.min_value = self.max_value = None
                self.white_space = None
                self.patterns = None
                self.validators = []
            else:
                self.white_space = getattr(self.get_facet(XSD_WHITE_SPACE_TAG), 'value', None)
                self.patterns = self.get_facet(XSD_PATTERN_TAG)
                self.validators = [
                    v for k, v in value.items()
                    if k not in (XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG) and callable(v)
                ]
        else:
            super(XsdSimpleType, self).__setattr__(name, value)

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_SIMPLE_TYPE_TAG}

    @property
    def admitted_facets(self):
        return self.schema.FACETS

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

    def has_simple_content(self):
        return True

    def has_mixed_content(self):
        return False

    def is_element_only(self):
        return False

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
                min_length_facet = base_type.get_facet(XSD_MIN_LENGTH_TAG)
                length_facet = base_type.get_facet(XSD_LENGTH_TAG)
                if min_length_facet is None or \
                        (length_facet is not None and length_facet.base_type == min_length_facet.base_type):
                    raise XMLSchemaParseError("cannot specify both 'length' and 'minLength'.", self)
            if max_length is not None:
                if max_length < length:
                    raise XMLSchemaParseError("'maxLength' value must be greater or equal to 'length'.", self)
                max_length_facet = base_type.get_facet(XSD_MAX_LENGTH_TAG)
                length_facet = base_type.get_facet(XSD_LENGTH_TAG)
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
                raise XMLSchemaParseError("Child 'minLength' has a lesser value than parent", self)
        elif max_length is not None:
            if max_length < 0:
                raise XMLSchemaParseError("'maxLength' value must be non negative integer.", self)
            max_length_facet = base_type.get_facet(XSD_MAX_LENGTH_TAG)
            if max_length_facet is not None and max_length > max_length_facet.value:
                raise XMLSchemaParseError("Child 'maxLength' has a greater value than parent", self)

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
            min_value = min_inclusive
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
        if isinstance(obj, bytes):
            obj = obj.decode('utf-8')
        elif not isinstance(obj, (str, unicode_type)):
            return obj

        if self.white_space == 'replace':
            return self._REGEX_SPACE.sub(' ', obj)
        elif self.white_space == 'collapse':
            return self._REGEX_SPACES.sub(' ', obj).strip()
        else:
            return obj

    def iter_decode(self, text, validation='lax', **kwargs):
        text = self.normalize(text)
        if validation != 'skip':
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield self._validation_error(error, validation)

            for validator in self.validators:
                for error in validator(text):
                    yield self._validation_error(error, validation)
        yield text

    def iter_encode(self, text, validation='lax', **kwargs):
        if isinstance(text, (str, unicode_type, bytes)):
            text = self.normalize(text)
        elif validation != 'skip':
            error = XMLSchemaEncodeError(self, text, unicode_type)
            yield self._validation_error(error, validation)

        if validation != 'skip':
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield self._validation_error(error, validation)

            for validator in self.validators:
                for error in validator(text):
                    yield self._validation_error(error, validation)

        yield text

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
    def __init__(self, elem, schema, name=None, facets=None, base_type=None, is_global=False):
        self.base_type = base_type
        super(XsdAtomic, self).__init__(elem, schema, name, facets, is_global)

    def __repr__(self):
        if self.name is None:
            return u'%s(primitive_type=%r)' % (self.__class__.__name__, self.primitive_type.local_name)
        else:
            return u'%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == 'base_type':
            assert value is None or isinstance(value, XsdType), \
                "%r attribute must be an XsdType instance or None: %r" % (name, value)
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
    def built(self):
        if self.base_type is None:
            return True
        else:
            return self.base_type.is_global or self.base_type.built

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        else:
            return self.base_type.validation_attempted

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
            return XSD_10_FACETS.union({None})
        else:
            try:
                return self.schema.FACETS.intersection(facets)
            except AttributeError:
                return set(primitive_type.facets.keys()).union({None})

    @property
    def primitive_type(self):
        if self.base_type is None:
            return self
        else:
            try:
                return self.base_type.primitive_type
            except AttributeError:
                # The base_type is XsdList or XsdUnion.
                return self.base_type

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

    @staticmethod
    def is_list():
        return False


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
    def __init__(self, elem, schema, name, python_type, base_type=None, facets=None,
                 to_python=None, from_python=None):
        """
        :param name: The XSD type's qualified name.
        :param python_type: The correspondent Python's type. If a tuple or list of types \
        is provided uses the first and consider the others as compatible types.
        :param base_type: The reference base type, None if it's a primitive type.
        :param facets: Optional facets validators.
        :param to_python: The optional decode function.
        :param from_python: The optional encode function.
        """
        if isinstance(python_type, (tuple, list)):
            self.instance_types, python_type = python_type, python_type[0]
        else:
            self.instance_types = python_type
        if not callable(python_type):
            raise XMLSchemaTypeError("%r object is not callable" % python_type.__class__)

        super(XsdAtomicBuiltin, self).__init__(elem, schema, name, facets, base_type, is_global=True)
        self.python_type = python_type
        self.to_python = to_python or python_type
        self.from_python = from_python or unicode_type

    def __repr__(self):
        return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def _parse(self):
        return

    def iter_decode(self, text, validation='lax', **kwargs):
        text = self.normalize(text)
        if validation != 'skip' and self.patterns:
            for error in self.patterns(text):
                yield self._validation_error(error, validation)

        try:
            result = self.to_python(text)
        except (ValueError, DecimalException) as err:
            if validation == 'skip':
                yield unicode_type(text)
            else:
                error = XMLSchemaDecodeError(self, text, self.to_python, reason=str(err))
                yield self._validation_error(error, validation)
                yield None
            return

        if validation != 'skip':
            for validator in self.validators:
                for error in validator(result):
                    yield self._validation_error(error, validation)

        yield result

    def iter_encode(self, data, validation='lax', **kwargs):
        data = self.normalize(data)
        if validation == 'skip':
            try:
                yield self.from_python(data)
            except ValueError:
                yield unicode_type(data)
            return

        elif isinstance(data, bool):
            types_ = self.instance_types
            if types_ is not bool or (isinstance(types_, tuple) and bool in types_):
                reason = "boolean value %r requires a %r decoder." % (data, bool)
                error = XMLSchemaEncodeError(self, data, self.from_python, reason)
                yield self._validation_error(error, validation, data)
                data = self.python_type(data)

        elif not isinstance(data, self.instance_types):
            reason = "%r is not an instance of %r." % (data, self.instance_types)
            error = XMLSchemaEncodeError(self, data, self.from_python, reason)
            yield self._validation_error(error, validation, data)
            try:
                value = self.python_type(data)
                if value != data:
                    raise ValueError()
                else:
                    data = value
            except ValueError:
                error = XMLSchemaEncodeError(self, data, self.from_python)
                yield self._validation_error(error, validation, data)
                yield None
                return

        for validator in self.validators:
            for error in validator(data):
                yield self._validation_error(error, validation)

        try:
            text = self.from_python(data)
        except ValueError:
            error = XMLSchemaEncodeError(self, data, self.from_python)
            yield self._validation_error(error, validation, data)
            yield None
        else:
            if self.patterns is not None:
                for error in self.patterns(text):
                    yield self._validation_error(error, validation)
            yield text


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

    def __init__(self, elem, schema, name=None, facets=None, base_type=None, is_global=False):
        super(XsdList, self).__init__(elem, schema, name, facets, is_global)
        if not hasattr(self, 'base_type'):
            self.base_type = base_type

    def __repr__(self):
        if self.name is None:
            return u'%s(item_type=%r)' % (self.__class__.__name__, self.base_type)
        else:
            return u'%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and value.tag != XSD_LIST_TAG:
            if value.tag == XSD_SIMPLE_TYPE_TAG:
                for child in value:
                    if child.tag == XSD_LIST_TAG:
                        super(XsdList, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError("a %r definition required for %r." % (XSD_LIST_TAG, self))
        elif name == 'base_type':
            assert value.is_atomic(), "%r: a list must be based on atomic data types." % self
        elif name == 'white_space' and value is None:
            value = 'collapse'
        super(XsdList, self).__setattr__(name, value)

    def _parse(self):
        super(XsdList, self)._parse()
        elem = self.elem
        base_type = None

        child = self._parse_component(elem, required=False)
        if child is not None:
            # Case of a local simpleType declaration inside the list tag
            base_type = xsd_simple_type_factory(child, self.schema, base_type)
            if isinstance(base_type, XMLSchemaParseError):
                self._parse_error(base_type, elem)
                base_type = self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)
            if 'itemType' in elem.attrib:
                self._parse_error("ambiguous list type declaration", self)
        elif 'itemType' in elem.attrib:
            # List tag with itemType attribute that refers to a global type
            item_qname = reference_to_qname(elem.attrib['itemType'], self.namespaces)
            base_type = self.maps.lookup_type(item_qname)
            if isinstance(base_type, XMLSchemaParseError):
                self._parse_error(base_type, elem)
                base_type = self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)
        else:
            self._parse_error("missing list type declaration", elem)
            base_type = self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)

        try:
            self.base_type = base_type
        except AssertionError as err:
            self._parse_error(str(err), elem)
            self.base_type = self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)

    @property
    def item_type(self):
        return self.base_type

    @property
    def built(self):
        return self.base_type.is_global or self.base_type.built

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        else:
            return self.base_type.validation_attempted

    @property
    def admitted_tags(self):
        return {XSD_LIST_TAG}

    @property
    def admitted_facets(self):
        return self.schema.LIST_FACETS

    @staticmethod
    def is_atomic():
        return False

    @staticmethod
    def is_list():
        return True

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if not self.base_type.is_global:
            for obj in self.base_type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, text, validation='lax', **kwargs):
        text = self.normalize(text)
        if validation != 'skip' and self.patterns:
            for error in self.patterns(text):
                yield self._validation_error(error, validation)

        items = []
        for chunk in text.split():
            for result in self.base_type.iter_decode(chunk, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self._validation_error(result, validation)
                else:
                    items.append(result)

        if validation != 'skip':
            for validator in self.validators:
                for error in validator(items):
                    yield self._validation_error(error, validation)

        yield items

    def iter_encode(self, data, validation='lax', **kwargs):
        if not hasattr(data, '__iter__') or isinstance(data, (str, unicode_type, bytes)):
            data = [data]

        if validation != 'skip':
            for validator in self.validators:
                for error in validator(data):
                    yield self._validation_error(error, validation)

        encoded_items = []
        for item in data:
            for result in self.base_type.iter_encode(item, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self._validation_error(result, validation)
                else:
                    encoded_items.append(result)

        yield u' '.join(item for item in encoded_items if item is not None)


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
    def __init__(self, elem, schema, name=None, facets=None, member_types=None, is_global=False):
        super(XsdUnion, self).__init__(elem, schema, name, facets, is_global)
        if not hasattr(self, 'member_types'):
            self.member_types = member_types

    def __repr__(self):
        if self.name is None:
            return u'%s(member_types=%r)' % (self.__class__.__name__, self.member_types)
        else:
            return u'%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None and value.tag != XSD_UNION_TAG:
            if value.tag == XSD_SIMPLE_TYPE_TAG:
                for child in value:
                    if child.tag == XSD_UNION_TAG:
                        super(XsdUnion, self).__setattr__(name, child)
                        return
            raise XMLSchemaValueError("a %r definition required for %r." % (XSD_UNION_TAG, self))

        elif name == "member_types":
            assert value, "%r attribute cannot be empty or None." % name
            assert all(isinstance(mt, (XsdAtomic, XsdList, XsdUnion)) for mt in value), \
                "%r: member types must be all atomic or list types." % self  # FIXME: Union only for XSD 1.1

        elif name == 'white_space':
            assert value is None or value == 'collapse', "Wrong value % for attribute 'white_space'." % value
            value = 'collapse'
        super(XsdUnion, self).__setattr__(name, value)

    def _parse(self):
        super(XsdUnion, self)._parse()
        elem = self.elem
        member_types = []

        for child in self._iterparse_components(elem):
            mt = xsd_simple_type_factory(child, self.schema)
            if isinstance(mt, XMLSchemaParseError):
                self._parse_error(mt)
            else:
                member_types.append(mt)

        if 'memberTypes' in elem.attrib:
            for name in elem.attrib['memberTypes'].split():
                type_qname = reference_to_qname(name, self.namespaces)
                mt = self.maps.lookup_type(type_qname)
                if isinstance(mt, XMLSchemaParseError):
                    self._parse_error(mt)
                elif not isinstance(mt, XsdSimpleType):
                    self._parse_error("a simpleType required", mt)
                else:
                    member_types.append(mt)

        if not member_types:
            self._parse_error("missing union type declarations", elem)

        try:
            self.member_types = member_types
        except AssertionError as err:
            self._parse_error(str(err), elem)
            self.member_types = [self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)]

    @property
    def built(self):
        return all([mt.is_global or mt.built for mt in self.member_types])

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any([mt.validation_attempted == 'partial' for mt in self.member_types]):
            return 'partial'
        else:
            return 'none'

    @property
    def admitted_tags(self):
        return {XSD_UNION_TAG}

    @property
    def admitted_facets(self):
        return self.schema.UNION_FACETS

    def is_atomic(self):
        return all(mt.is_atomic() for mt in self.member_types)

    def is_list(self):
        return all(mt.is_list() for mt in self.member_types)

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for mt in self.member_types:
            if not mt.is_global:
                for obj in mt.iter_components(xsd_classes):
                    yield obj

    def iter_decode(self, text, validation='lax', **kwargs):
        text = self.normalize(text)
        if validation != 'skip' and self.patterns:
            for error in self.patterns(text):
                yield self._validation_error(error, validation)

        # Try the text as a whole
        for member_type in self.member_types:
            for result in member_type.iter_decode(text, validation='lax', **kwargs):
                if not isinstance(result, XMLSchemaValidationError):
                    if validation != 'skip':
                        for validator in self.validators:
                            for error in validator(result):
                                yield self._validation_error(error, validation)
                    yield result
                    return
                break

        if ' ' not in text.strip():
            reason = "no type suitable for decoding %r." % text
            error = XMLSchemaDecodeError(self, text, self.member_types, reason)
            yield self._validation_error(error, validation)

        items = []
        not_decodable = []
        for chunk in text.split():
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

        if not_decodable:
            reason = "no type suitable for decoding the values %r." % not_decodable
            error = XMLSchemaDecodeError(self, text, self.member_types, reason)
            yield self._validation_error(error, validation)

        if validation != 'skip':
            for validator in self.validators:
                for error in validator(items):
                    yield self._validation_error(error, validation)

        yield items if len(items) > 1 else items[0] if items else None

    def iter_encode(self, data, validation='lax', **kwargs):
        for member_type in self.member_types:
            for result in member_type.iter_encode(data, validation='lax', **kwargs):
                if result is not None and not isinstance(result, XMLSchemaValidationError):
                    if validation == 'skip':
                        for validator in self.validators:
                            for error in validator(data):
                                yield self._validation_error(error, validation)
                        for error in self.patterns(result):
                            yield self._validation_error(error, validation)

                    yield result
                    return
                elif validation == 'strict':
                    # In 'strict' mode avoid lax encoding by similar types (eg. float encoded by int)
                    break

        if hasattr(data, '__iter__') and not isinstance(data, (str, unicode_type, bytes)):
            for member_type in self.member_types:
                results = []
                for item in data:
                    for result in member_type.iter_encode(item, validation='lax', **kwargs):
                        if result is not None and not isinstance(result, XMLSchemaValidationError):
                            if validation != 'skip':
                                for validator in self.validators:
                                    for error in validator(result):
                                        yield self._validation_error(error, validation)
                            for error in self.patterns(result):
                                yield self._validation_error(error, validation)

                            results.append(result)
                            break
                        elif validation == 'strict':
                            break

                if len(results) == len(data):
                    yield results
                    break

        if validation != 'skip':
            error = XMLSchemaEncodeError(self, data, self.member_types, "no type suitable for encoding the object.")
            yield self._validation_error(error, validation)
            yield None
        else:
            yield unicode_type(data)


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
    def __setattr__(self, name, value):
        if name == 'elem' and value is not None:
            if self.name != XSD_ANY_ATOMIC_TYPE and value.tag != XSD_RESTRICTION_TAG:
                if not (value.tag == XSD_SIMPLE_TYPE_TAG and value.get('name') is not None):
                    raise XMLSchemaValueError(
                        "a %r definition required for %r." % (XSD_RESTRICTION_TAG, self)
                    )
        super(XsdAtomicRestriction, self).__setattr__(name, value)

    def _parse(self):
        super(XsdAtomicRestriction, self)._parse()
        elem = self.elem
        if elem.get('name') == XSD_ANY_ATOMIC_TYPE:
            return  # skip special type xs:anyAtomicType
        elif elem.tag == XSD_SIMPLE_TYPE_TAG and elem.get('name') is not None:
            elem = get_xsd_component(elem)  # Global simpleType with internal restriction

        base_type = None
        facets = {}
        has_attributes = False
        has_simple_type_child = False

        if 'base' in elem.attrib:
            base_qname = reference_to_qname(elem.attrib['base'], self.namespaces)
            base_type = self.maps.lookup_type(base_qname)
            if isinstance(base_type, XMLSchemaParseError):
                self._parse_error(base_qname)
                base_type = self.maps.lookup_type(XSD_ANY_ATOMIC_TYPE)

            if base_type.is_complex() and base_type.mixed and base_type.is_emptiable():
                if self._parse_component(elem, strict=False).tag != XSD_SIMPLE_TYPE_TAG:
                    # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                    self._parse_error(
                        "when a complexType with simpleContent restricts a complexType "
                        "with mixed and with emptiable content then a simpleType child "
                        "declaration is required.", elem
                    )

        for child in self._iterparse_components(elem):
            if child.tag in {XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG}:
                has_attributes = True  # only if it's a complexType restriction
            elif has_attributes:
                self._parse_error("unexpected tag after attribute declarations", child)
            elif child.tag == XSD_SIMPLE_TYPE_TAG:
                # Case of simpleType declaration inside a restriction
                if has_simple_type_child:
                    self._parse_error("duplicated simpleType declaration", child)
                elif base_type is None:
                    base_type = xsd_simple_type_factory(child, self.schema)
                    if isinstance(base_type, XMLSchemaParseError):
                        self._parse_error(base_type)
                        base_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                else:
                    if base_type.is_complex() and base_type.admit_simple_restriction():
                        content_type = xsd_simple_type_factory(child, self.schema)
                        base_type = self.schema.BUILDERS.complex_type_class(
                            elem=elem,
                            schema=self.schema,
                            content_type=content_type,
                            attributes=base_type.attributes,
                            mixed=base_type.mixed
                        )
                has_simple_type_child = True
            elif child.tag not in self.schema.FACETS:
                raise XMLSchemaParseError("unexpected tag %r in restriction:" % child, self)
            elif child.tag in (XSD_ENUMERATION_TAG, XSD_PATTERN_TAG):
                try:
                    facets[child.tag].append(child)
                except KeyError:
                    if child.tag == XSD_ENUMERATION_TAG:
                        facets[child.tag] = XsdEnumerationFacet(base_type, child, self.schema)
                    else:
                        facets[child.tag] = XsdPatternsFacet(base_type, child, self.schema)
            elif child.tag not in facets:
                facets[child.tag] = XsdSingleFacet(base_type, child, self.schema)
            else:
                raise XMLSchemaParseError("multiple %r constraint facet" % local_name(child.tag), self)

        if base_type is None:
            self._parse_error("missing base type in restriction:", self)
        self.base_type = base_type
        self.facets = facets

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if not self.base_type.is_global:
            for obj in self.base_type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, text, validation='lax', **kwargs):
        text = self.normalize(text)
        if validation != 'skip' and self.patterns:
            for error in self.patterns(text):
                yield self._validation_error(error, validation)

        if self.base_type.is_simple():
            base_type = self.base_type
        elif self.base_type.has_simple_content():
            base_type = self.base_type.content_type
        elif self.base_type.mixed:
            yield text
            return
        else:
            raise XMLSchemaValueError("wrong base type %r: a simpleType or a complexType with "
                                      "simple or mixed content required." % self.base_type)

        for result in base_type.iter_decode(text, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield self._validation_error(result, validation)
                if isinstance(result, XMLSchemaDecodeError):
                    yield unicode_type(text) if validation == 'skip' else None
            else:
                if validation != 'skip':
                    for validator in self.validators:
                        for error in validator(result):
                            yield self._validation_error(error, validation)

                yield result
                return

    def iter_encode(self, data, validation='lax', **kwargs):
        if self.is_list():
            if not hasattr(data, '__iter__') or isinstance(data, (str, unicode_type, bytes)):
                data = [] if data is None or data == '' else [data]

            if validation != 'skip':
                for validator in self.validators:
                    for error in validator(data):
                        yield self._validation_error(error, validation)

            for result in self.base_type.iter_encode(data, validation):
                if isinstance(result, XMLSchemaValidationError):
                    if validation == 'strict':
                        raise result
                    yield result
                    if isinstance(result, XMLSchemaEncodeError):
                        yield unicode_type(data) if validation == 'skip' else None
                        return
                else:
                    yield result
            return

        data = self.normalize(data)

        if self.base_type.is_simple():
            base_type = self.base_type
        elif self.base_type.has_simple_content():
            base_type = self.base_type.content_type
        elif self.base_type.mixed:
            yield unicode_type(data)
            return
        else:
            raise XMLSchemaValueError("wrong base type %r: a simpleType or a complexType with "
                                      "simple or mixed content required." % self.base_type)

        for result in base_type.iter_encode(data, validation):
            if isinstance(result, XMLSchemaValidationError):
                if validation == 'strict':
                    raise result
                yield result
                if isinstance(result, XMLSchemaEncodeError):
                    yield unicode_type(data) if validation == 'skip' else None
                    return
            else:
                if validation != 'skip':
                    for validator in self.validators:
                        for error in validator(data):
                            yield self._validation_error(error, validation)

                yield result
                return

    def is_list(self):
        return self.primitive_type.is_list()


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
