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
This module contains classes and functions for XML Schema validation.
"""
import re
from collections import MutableMapping, MutableSequence

from .utils import linked_flatten, meta_next_gen
from .core import PY3, XSI_NAMESPACE_PATH, XSD_NAMESPACE_PATH
from .exceptions import *
from .qnames import (
    split_reference, get_qname, split_qname, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG,
    XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG, XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG,
    XSD_MAX_LENGTH_TAG, XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG,
    XSD_MAX_EXCLUSIVE_TAG, XSD_TOTAL_DIGITS_TAG, XSD_FRACTION_DIGITS_TAG, XSD_STRING_TYPES
)
from .parse import (
    lookup_attribute, get_xsd_attribute, get_xsd_bool_attribute, get_xsd_int_attribute,
)


#
# Class hierarchy for XSD types and other structures
class XsdBase(object):
    """
    Abstract base class for representing generic XML Schema Definition object,
    providing common API interface.

    :param name: Name associated with the definition
    :param elem: ElementTree's node containing the definition
    """
    EMPTY_DICT = {}
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    def __init__(self, name=None, elem=None, schema=None):
        self.name = name
        self.elem = elem
        self.schema = schema
        self._attrib = dict(elem.attrib) if elem is not None else self.EMPTY_DICT

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name, id(self))

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.name and self.name[0] == '{':
            return self.name
        else:
            return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def _check_type(self, name, ref, value, types):
        """
        Checks the type of 'value' argument to be in a tuple of types.

        :param name: The name of the attribute/key of the object.
        :param ref: A reference to determine the type related to the name.
        :param value: The value to be checked.
        :param types: A tuple with admitted types.
        """
        if not isinstance(value, types):
            raise XMLSchemaComponentError(
                obj=self,
                name=name,
                ref=ref,
                message="wrong type %s, it must be one of %r." % (type(value), types)
            )

    def _check_value(self, name, ref, value, values):
        """
        Checks the value of 'value' argument to be in a tuple of values.

        :param name: The name of the attribute/key of the object.
        :param ref: A reference to determine the type related to the name.
        :param value: The value to be checked.
        :param values: A tuple with admitted values.
        """
        if value not in values:
            raise XMLSchemaComponentError(
                obj=self,
                name=name,
                ref=ref,
                message="wrong value %s, it must be one of %r." % (type(value), values)
            )

    def _get_namespace_attribute(self):
        """
        Get the namespace attribute value for anyAttribute and anyElement declaration,
        checking if the value is conforming to the specification.
        """
        value = get_xsd_attribute(self.elem, 'namespace', '##all')
        items = value.strip().split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            return value
        elif not all([s not in ('##all', '##other') for s in items]):
            raise XMLSchemaValueError("wrong value %r for the 'namespace' attribute." % value, self)
        return value

    def _get_derivation_attribute(self, attribute, values):
        value = get_xsd_attribute(self.elem, attribute, '#all')
        items = value.strip().split()
        if len(items) == 1 and items[0] == "#all":
            return
        elif not all([s not in values for s in items]):
            raise XMLSchemaValueError("wrong value %r for attribute %r" % (value, attribute), self)

    @property
    def id(self):
        return self._attrib.get('id')


class XsdFacet(XsdBase):

    def __init__(self, base_type, elem=None, schema=None):
        XsdBase.__init__(self, elem=elem, schema=schema)
        self.base_type = base_type


class XsdUniqueFacet(XsdFacet):

    def __init__(self, base_type, elem=None, schema=None):
        super(XsdUniqueFacet, self).__init__(base_type, elem=elem, schema=schema)
        self.name = '%s(value=%r)' % (split_qname(elem.tag)[1], elem.attrib['value'])
        self.fixed = self._attrib.get('fixed', 'false')

        # TODO: Add checks with base_type's constraints.
        if elem.tag == XSD_WHITE_SPACE_TAG:
            self.value = get_xsd_attribute(elem, 'value', enumeration=('preserve', 'replace', 'collapse'))
            white_space = getattr(base_type, 'white_space', None)
            if getattr(base_type, 'fixed_white_space', None) and white_space != self.value:
                XMLSchemaParseError("whiteSpace can be only %r." % base_type.white_space, elem)
            elif white_space == 'collapse' and self.value in ('preserve', 'replace'):
                XMLSchemaParseError("whiteSpace can be only 'collapse', so cannot change.", elem)
            elif white_space == 'replace' and self.value == 'preserve':
                XMLSchemaParseError("whiteSpace can be only 'replace' or 'collapse'.", elem)
        elif elem.tag in (XSD_LENGTH_TAG, XSD_MIN_LENGTH_TAG, XSD_MAX_LENGTH_TAG):
            self.value = get_xsd_int_attribute(elem, 'value')
            if elem.tag == XSD_LENGTH_TAG:
                self.validator = self.length_validator
            elif elem.tag in XSD_MIN_LENGTH_TAG:
                self.validator = self.min_length_validator
            elif elem.tag == XSD_MAX_LENGTH_TAG:
                self.validator = self.max_length_validator
        elif elem.tag in (
                XSD_MIN_INCLUSIVE_TAG, XSD_MIN_EXCLUSIVE_TAG, XSD_MAX_INCLUSIVE_TAG, XSD_MAX_EXCLUSIVE_TAG
                ):
            self.value = base_type.decode(get_xsd_attribute(elem, 'value'))
            if elem.tag == XSD_MIN_INCLUSIVE_TAG:
                self.validator = self.min_inclusive_validator
            elif elem.tag == XSD_MIN_EXCLUSIVE_TAG:
                self.validator = self.min_exclusive_validator
            elif elem.tag == XSD_MAX_INCLUSIVE_TAG:
                self.validator = self.max_inclusive_validator
            elif elem.tag == XSD_MAX_EXCLUSIVE_TAG:
                self.validator = self.max_exclusive_validator
        elif elem.tag == XSD_TOTAL_DIGITS_TAG:
            self.value = get_xsd_int_attribute(elem, 'value', minimum=1)
            self.validator = self.total_digits_validator
        elif elem.tag == XSD_FRACTION_DIGITS_TAG:
            if base_type.name != get_qname(XSD_NAMESPACE_PATH, 'decimal'):
                raise XMLSchemaParseError("fractionDigits require a {%s}decimal base type!" % XSD_NAMESPACE_PATH)
            self.value = get_xsd_int_attribute(elem, 'value', minimum=0)
            self.validator = self.fraction_digits_validator

    def __call__(self, *args, **kwargs):
        self.validator(*args, **kwargs)

    def length_validator(self, x):
        if len(x) != self.value:
            raise XMLSchemaValidationError(self, x)

    def min_length_validator(self, x):
        if len(x) < self.value:
            raise XMLSchemaValidationError(self, x)

    def max_length_validator(self, x):
        if len(x) > self.value:
            raise XMLSchemaValidationError(self, x)

    def min_inclusive_validator(self, x):
        if x < self.value:
            raise XMLSchemaValidationError(self, x)

    def min_exclusive_validator(self, x):
        if x <= self.value:
            raise XMLSchemaValidationError(self, x)

    def max_inclusive_validator(self, x):
        if x > self.value:
            raise XMLSchemaValidationError(self, x)

    def max_exclusive_validator(self, x):
        if x >= self.value:
            raise XMLSchemaValidationError(self, x)

    def total_digits_validator(self, x):
        if len([d for d in str(x) if d.isdigit()]) > self.value:
            raise XMLSchemaValidationError(self, x)

    def fraction_digits_validator(self, x):
        if len(str(x).partition('.')[2]) > self.value:
            raise XMLSchemaValidationError(self, x)


class XsdEnumerationFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(values=%r)'.format(split_qname(elem.tag)[1])
        self._elements = [elem]
        self.enumeration = [base_type.decode(get_xsd_attribute(elem, 'value'))]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        self.enumeration[i] = self.base_type.decode(get_xsd_attribute(item, 'value'))

    def __delitem__(self, i):
        del self._elements[i]
        del self.enumeration[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        self.enumeration.insert(i, self.base_type.decode(get_xsd_attribute(item, 'value')))

    def __repr__(self):
        return u"<%s %r at %#x>" % (self.__class__.__name__, self.enumeration, id(self))

    def __call__(self, value):
        if value not in self.enumeration:
            raise XMLSchemaValidationError(
                self, value, reason="invalid value, it must be one of %r" % self.enumeration
            )


class XsdPatternsFacet(MutableSequence, XsdFacet):

    def __init__(self, base_type, elem, schema=None):
        XsdFacet.__init__(self, base_type, schema=schema)
        self.name = '{}(patterns=%r)'.format(split_qname(elem.tag)[1])
        self._elements = [elem]
        self.patterns = [re.compile(re.escape(get_xsd_attribute(elem, 'value')))]

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._elements[i]

    def __setitem__(self, i, item):
        self._elements[i] = item
        self.patterns[i] = re.compile(re.escape(get_xsd_attribute(item, 'value')))

    def __delitem__(self, i):
        del self._elements[i]
        del self.patterns[i]

    def __len__(self):
        return len(self._elements)

    def insert(self, i, item):
        self._elements.insert(i, item)
        self.patterns.insert(i, re.compile(re.escape(get_xsd_attribute(item, 'value'))))

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.name % self.patterns, id(self))

    def __call__(self, value):
        if all(pattern.search(value) is None for pattern in self.patterns):
            msg = "value don't match any of patterns %r"
            raise XMLSchemaValidationError(self, value, reason= msg % [p.pattern for p in self.patterns])


class OccursMixin(object):

    def is_optional(self):
        return self._attrib.get('minOccurs', '').strip() == "0"

    @property
    def min_occurs(self):
        return get_xsd_int_attribute(self.elem, 'minOccurs', default=1, minimum=0)

    @property
    def max_occurs(self):
        try:
            return get_xsd_int_attribute(self.elem, 'maxOccurs', default=1, minimum=0)
        except (XMLSchemaTypeError, XMLSchemaValueError):
            if self._attrib['maxOccurs'] == 'unbounded':
                return None
            raise

    def model_generator(self):
        try:
            for i in range(self.max_occurs):
                yield self
        except TypeError:
            while True:
                yield self


class ValidatorMixin(object):

    def validate(self, text_or_obj):
        raise NotImplementedError("%r: you must provide a concrete validate() method" % self.__class__)

    def decode(self, text):
        raise NotImplementedError("%r: you must provide a concrete decode() method" % self.__class__)

    def encode(self, obj):
        raise NotImplementedError("%r: you must provide a concrete encode() method" % self.__class__)


class XsdAttributeGroup(MutableMapping, XsdBase):

    def __init__(self, name=None, elem=None, schema=None, initdict=None):
        XsdBase.__init__(self, name, elem, schema)
        self._namespaces = schema.namespaces if schema else {}
        self._lookup_table = schema.lookup_table if schema else {}
        self._attribute_group = dict()
        if initdict is not None:
            self._attribute_group.update(initdict.items())

    # Implements the abstract methods of MutableMapping
    def __getitem__(self, key):
        return self._attribute_group[key]

    def __setitem__(self, key, value):
        if key is None:
            self._check_type(key, self, value, (XsdAnyAttribute,))
        else:
            self._check_type(key, self, value, (XsdAttribute,))
        self._attribute_group[key] = value

    def __delitem__(self, key):
        del self._attribute_group[key]

    def __iter__(self):
        return iter(self._attribute_group)

    def __len__(self):
        return len(self._attribute_group)

    # Other methods
    def __setattr__(self, name, value):
        if name == '_attribute_group':
            self._check_type(name, None, value, (dict,))
            for k, v in value.items():
                self._check_type(name, dict, v, (XsdAnyAttribute,))
        super(XsdAttributeGroup, self).__setattr__(name, value)

    def validate(self, *args, **kwargs):
        for error in self.iter_errors(*args, **kwargs):
            raise error

    def iter_errors(self, attributes, elem=None):
        if not attributes:
            return
        any_attribute = self.get(None)  # 'None' is the key for the anyAttribute declaration.
        required_attributes = set(
            [k for k, v in self.items() if k is not None and not v.is_optional()]
        )
        target_namespace = self.schema.target_namespace

        # Verify instance attributes
        for key, value in attributes.items():
            qname = get_qname(target_namespace, key)
            try:
                xsd_attribute = self[qname]
                required_attributes.discard(qname)
            except KeyError:
                qname, namespace = split_reference(key, self._namespaces)
                if namespace == XSI_NAMESPACE_PATH:
                    lookup_attribute(qname, namespace, self._lookup_table).validate(value)
                elif any_attribute is not None:
                    any_attribute.validate({qname: value})
                else:
                    yield XMLSchemaValidationError(
                        self, key, "attribute not allowed for this element", elem, self.elem
                    )
            else:
                try:
                    xsd_attribute.decode(value)
                except (XMLSchemaValidationError, XMLSchemaDecodeError) as err:
                    yield XMLSchemaValidationError(
                        xsd_attribute, err.value, err.reason, elem, xsd_attribute.elem
                    )

        if required_attributes:
            yield XMLSchemaValidationError(
                self,
                elem.attrib,
                reason="missing required attributes %r" % required_attributes,
                elem=elem,
                schema_elem=self.elem
            )


class XsdGroup(MutableSequence, XsdBase, ValidatorMixin, OccursMixin):
    """
    A group can have a model, that indicate the elements that compose the content
    type associated with it.
    """
    def __init__(self, name=None, elem=None, schema=None, model=None, mixed=False, initlist=None):
        XsdBase.__init__(self, name, elem, schema)
        self.model = model
        self.mixed = mixed
        self._group = []
        if initlist is not None:
            if isinstance(initlist, type(self._group)):
                self._group[:] = initlist
            elif isinstance(initlist, XsdGroup):
                self._group[:] = initlist._group[:]
            else:
                self._group = list(initlist)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        self._check_type(i, list, item, (XsdGroup,))
        if self.model is None:
            raise XMLSchemaParseError(u"cannot add items when the group model is None.", self.elem)
        self._group[i] = item

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        self._group.insert(i, item)

    def __repr__(self):
        return XsdBase.__repr__(self)

    def __setattr__(self, name, value):
        if name == 'model':
            self._check_value(name, None, value, (None, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG))
        elif name == 'mixed':
            self._check_value(name, None, value, (True, False))
        elif name == '_group':
            self._check_type(name, None, value, (list,))
            for i in range(len(value)):
                self._check_type(name, i, value[i], (XsdGroup, XsdElement, XsdAnyElement))
        super(XsdGroup, self).__setattr__(name, value)

    def iter_elements(self):
        for group_item in self:
            if isinstance(group_item, XsdElement):
                yield group_item
            elif isinstance(group_item, XsdGroup):
                for xsd_element in group_item.iter_elements():
                    yield xsd_element

    def model_generator(self):
        try:
            occurs_iterator = range(self.max_occurs)
        except TypeError:
            occurs_iterator = iter(int, 1)
        gen_cls = type(
            'XsdGroupGenerator', (list,), {
                'name': self.name,
                'model': self.model,
                'mixed': self.mixed,
                'is_optional': lambda x: self.is_optional()
            })
        for _ in occurs_iterator:
            if self.model == XSD_SEQUENCE_TAG:
                for item in self:
                    yield gen_cls([item.model_generator()])
            elif self.model == XSD_ALL_TAG:
                yield gen_cls([item.model_generator() for item in self._group])
            elif self.model == XSD_CHOICE_TAG:
                yield gen_cls([item.model_generator() for item in self._group])

    def validate(self, value):
        if not isinstance(value, str):
            raise XMLSchemaValidationError(self, value, reason="value must be a string!")
        if not self.mixed and value:
            raise XMLSchemaValidationError(
                self, value, reason="character data not allowed for this content type (mixed=False)."
            )

    def iter_errors(self, elem):
        # Validate character data between tags
        if not self.mixed and (elem.text.strip() or any([child.tail.strip() for child in elem])):
            yield XMLSchemaValidationError(
                self, elem, "character data between child elements not allowed!", elem, self.elem
            )

        # Validate child elements
        model_generator = self.model_generator()
        elem_iterator = iter(elem)
        target_namespace = self.schema.target_namespace
        consumed_child = True
        while True:
            try:
                content_model = next(model_generator)
                validation_group = []
                for g, c in linked_flatten(content_model):
                    validation_group.extend([t for t in meta_next_gen(g, c)])
            except StopIteration:
                for child in elem_iterator:
                    yield XMLSchemaValidationError(self, child, "invalid tag", child, self.elem)
                return

            try:
                missing_tags = set([e[0].name for e in validation_group if not e[0].is_optional()])
            except (AttributeError, TypeError):
                raise

            while validation_group:
                if consumed_child:
                    try:
                        child = next(elem_iterator)
                    except StopIteration:
                        if missing_tags:
                            yield XMLSchemaValidationError(
                                self, elem, "tag expected: %r" % tuple(missing_tags), elem, self.elem
                            )
                        return
                    else:
                        name = get_qname(target_namespace, child.tag)
                        consumed_child = False

                for _index, (_element, _iterator, _container) in enumerate(validation_group):
                    if name == _element.name:
                        consumed_child = True
                        missing_tags.discard(name)
                        try:
                            validation_group[_index] = (next(_iterator), _iterator, _container)
                        except StopIteration:
                            validation_group = []
                            break
                        if _container.model == XSD_CHOICE_TAG:
                            # With choice model reduce the validation_group
                            # in order to match only the first matched tag.
                            validation_group = [
                                (e, g, c) for e, g, c in validation_group if c != _container or g == _iterator
                            ]
                            missing_tags.intersection_update({e[0].name for e in validation_group})
                        break
                else:
                    if missing_tags:
                        yield XMLSchemaValidationError(self, child, "invalid tag", child, self.elem)
                        consumed_child = True
                    break

    def decode(self, text):
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        self.validate(text)
        return text


class XsdSimpleType(XsdBase, ValidatorMixin):
    """
    Base class for simple types, used only for instances of xs:anySimpleType.
    """

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('list', 'union', 'restriction'))

    def validate(self, obj):
        if not isinstance(obj, str):
            raise XMLSchemaValidationError(self, obj, reason="value must be a string!")

    def decode(self, text):
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        self.validate(text)
        return str(text)

    def encode(self, obj):
        if not isinstance(obj, str):
            raise XMLSchemaEncodeError(self, obj, str)
        return str(obj)


class XsdAtomicType(XsdSimpleType, ValidatorMixin):
    """
    Class for defining XML Schema built-in simpleType atomic datatypes. An instance
    contains a Python's type transformation and a list of validator functions.

    Type conversion methods:
      - to_python(value): Decoding from XML:
      - from_python(value): Encoding to XML
    """
    def __init__(self, name, python_type, validators=None, to_python=None, from_python=None):
        """
        :param python_type: The correspondent Python's type
        :param validators: The optional validator for value objects
        :param to_python: The optional decode function
        :param from_python: The optional encode function
        """
        if not callable(python_type):
            raise XMLSchemaTypeError("%s object is not callable" % python_type.__class__.__name__)
        super(XsdAtomicType, self).__init__(name)
        self.python_type = python_type
        self.validators = validators or []
        self.to_python = to_python or python_type
        self.from_python = from_python or str
        self.white_space = 'preserve' if name in XSD_STRING_TYPES else 'collapse'
        self.fixed_white_space = False

    def validate(self, obj):
        if not isinstance(obj, self.python_type):
            raise XMLSchemaValidationError(
                self, obj, "value type is {} instead of {}".format(type(obj), repr(self.python_type))
            )
        if isinstance(obj, str):
            if self.white_space == 'replace':
                obj = self._REGEX_SPACE.sub(u" ", obj)
            elif self.white_space == 'collapse':
                obj = self._REGEX_SPACES.sub(u" ", obj)
        for validator in self.validators:
            validator(obj)

    def decode(self, text):
        """
        Transform an XML text into a Python object.
        :param text: XML text
        """
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        try:
            value = self.to_python(text)
            if value is None:
                raise ValueError
        except ValueError:
            raise XMLSchemaDecodeError(self, text, self.python_type)
        else:
            self.validate(value)
            return value

    def encode(self, obj):
        """
        Transform a Python object into an XML string.
        :param obj: The Python object that has to be encoded in XML
        """
        if not isinstance(obj, self.python_type):
            raise XMLSchemaEncodeError(self, obj, self.python_type)
        return self.from_python(obj)


class XsdRestriction(XsdSimpleType, ValidatorMixin):
    """
    A class for representing a user defined atomic simpleType (restriction).
    """
    def __init__(self, base_type, name=None, elem=None, schema=None, validators=None,
                 facets=None, lengths=(0, None)):
        super(XsdRestriction, self).__init__(name, elem, schema)
        self.base_type = base_type
        self.lengths = lengths
        self.facets = facets or {}

        try:
            self.white_space = facets[XSD_WHITE_SPACE_TAG].value
            self.fixed_white_space = facets[XSD_WHITE_SPACE_TAG].fixed
        except KeyError:
            self.white_space = self.fixed_white_space = None

        self.patterns = facets.get(XSD_PATTERN_TAG)
        self.validators = [
            v for k, v in facets.items() if k not in (XSD_WHITE_SPACE_TAG, XSD_PATTERN_TAG)
            ]

    def __setattr__(self, name, value):
        if name == "base_type":
            self._check_type(name, None, value, (XsdSimpleType, XsdComplexType))
        super(XsdRestriction, self).__setattr__(name, value)

    def validate(self, obj):
        self.base_type.validate(obj)
        for validator in self.validators:
            validator(obj)

    def decode(self, text):
        if self.white_space == 'replace':
            text = self._REGEX_SPACE.sub(u" ", text)
        elif self.white_space == 'collapse':
            text = self._REGEX_SPACES.sub(u" ", text)
        value = self.base_type.decode(text)
        self.validate(value)
        return value

    def encode(self, obj):
        return self.base_type.encode(obj)


class XsdList(XsdSimpleType, ValidatorMixin):

    def __init__(self, item_type, name=None, elem=None, schema=None):
        super(XsdList, self).__init__(name, elem, schema)
        self.item_type = item_type

    def __setattr__(self, name, value):
        if name == "item_type":
            self._check_type(name, None, value, (XsdSimpleType,))
        super(XsdList, self).__setattr__(name, value)

    def validate(self, obj):
        _validate = self.item_type.validate
        for item in obj:
            if isinstance(item, (list, tuple)):
                map(_validate, item)
            else:
                _validate(item)

    def decode(self, text):
        matrix = [item.strip() for item in text.split('\n') if item.strip()]
        if len(matrix) == 1:
            # Only one data line --> decode to simple list
            return [self.item_type.decode(item) for item in matrix[0].split()]
        else:
            # More data lines --> decode to nested lists
            return [
                [self.item_type.decode(item) for item in matrix[row].split()]
                for row in range(len(matrix))
            ]

    def encode(self, obj):
        return u' '.join([self.item_type.encode(item) for item in obj])


class XsdUnion(XsdSimpleType):

    def __init__(self, member_types, name=None, elem=None, schema=None):
        super(XsdUnion, self).__init__(name, elem, schema)
        self.member_types = member_types

    def __setattr__(self, name, value):
        if name == "member_types":
            for member_type in value:
                self._check_type(name, list, member_type, (XsdSimpleType,))
        super(XsdUnion, self).__setattr__(name, value)

    def validate(self, obj):
        for _type in self.member_types:
            try:
                return _type.validate(obj)
            except XMLSchemaValidationError:
                pass
        raise XMLSchemaValidationError(self, obj, reason="no type suitable for validating the value.")

    def decode(self, text):
        for _type in self.member_types:
            try:
                return _type.decode(text)
            except (XMLSchemaValidationError, XMLSchemaDecodeError):
                pass
        raise XMLSchemaDecodeError(
            self, text, self.member_types, reason="no type suitable for decoding the text."
        )

    def encode(self, obj):
        for _type in self.member_types:
            try:
                return _type.encode(obj)
            except XMLSchemaEncodeError:
                pass
        raise XMLSchemaEncodeError(self, obj, self.member_types)


class XsdComplexType(XsdBase, ValidatorMixin):
    """
    A class for representing a complexType definition for XML schemas.
    """
    def __init__(self, content_type, name=None, elem=None, schema=None, attributes=None, derivation=None, mixed=None):
        super(XsdComplexType, self).__init__(name, elem, schema)
        self.content_type = content_type
        self.attributes = attributes or XsdAttributeGroup(schema=schema)
        if mixed is not None:
            self.mixed = mixed
        else:
            self.mixed = get_xsd_bool_attribute(self.elem, 'mixed', default=False)
        self.derivation = derivation

    def __setattr__(self, name, value):
        if name == "content_type":
            self._check_type(name, None, value, (XsdSimpleType, XsdComplexType, XsdGroup))
        elif name == 'attributes':
            self._check_type(name, None, value, (XsdAttributeGroup,))
        super(XsdComplexType, self).__setattr__(name, value)

    @property
    def abstract(self):
        return get_xsd_bool_attribute(self.elem, 'abstract', default=False)

    @property
    def block(self):
        return self._get_derivation_attribute('block', ('extension', 'restriction'))

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('extension', 'restriction'))

    def has_restriction(self):
        return self.derivation is False

    def has_extension(self):
        return self.derivation is True

    def validate(self, obj):
        self.content_type.validate(obj)

    def decode(self, text):
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        value = self.content_type.decode(text)
        self.content_type.validate(value)
        return value

    def encode(self, obj):
        return self.content_type.encode(obj)


class XsdAttribute(XsdBase, ValidatorMixin):
    """
    Support structure to associate an attribute with XSD simple types.
    """
    def __init__(self, xsd_type, name, elem=None, schema=None, qualified=False):
        super(XsdAttribute, self).__init__(name, elem, schema)
        self.type = xsd_type
        self.qualified = qualified
        self.default = self._attrib.get('default', '')
        self.fixed = self._attrib.get('fixed', '')
        if self.default and self.fixed:
            raise XMLSchemaParseError("'default' and 'fixed' attributes are mutually exclusive", self.elem)

    def __setattr__(self, name, value):
        if name == "type":
            self._check_type(name, None, value, (XsdSimpleType,))
        super(XsdAttribute, self).__setattr__(name, value)

    @property
    def form(self):
        return get_xsd_attribute(self.elem, 'form', enumeration=('qualified', 'unqualified'))

    @property
    def use(self):
        return get_xsd_attribute(self.elem, 'use', 'optional', ('optional', 'prohibited', 'required'))

    def is_optional(self):
        return self.use == 'optional'

    def validate(self, obj):
        return self.type.validate(obj)

    def decode(self, text):
        return self.type.decode(text)

    def encode(self, obj):
        return self.type.encode(obj)


class XsdElement(XsdBase, ValidatorMixin, OccursMixin):
    """
    Support structure to associate an element and its attributes with XSD simple types.
    """
    def __init__(self, name, xsd_type, elem=None, schema=None, ref=False, qualified=False):
        super(XsdElement, self).__init__(name, elem, schema)
        self.type = xsd_type
        self.ref = ref
        self.qualified = qualified
        self.default = self._attrib.get('default', '')
        self.fixed = self._attrib.get('fixed', '')
        if self.default and self.fixed:
            raise XMLSchemaParseError("'default' and 'fixed' attributes are mutually exclusive", self.elem)

    def __setattr__(self, name, value):
        if name == "type":
            self._check_type(name, None, value, (XsdSimpleType, XsdComplexType))
        super(XsdElement, self).__setattr__(name, value)

    def validate(self, obj):
        self.type.validate(obj)

    def decode(self, text):
        return self.type.decode(text or self.default)

    def encode(self, obj):
        return self.type.encode(obj)

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.schema.target_namespace, name)]
        return self.type.attributes[name]

    @property
    def abstract(self):
        return get_xsd_bool_attribute(self.elem, 'abstract', default=False)

    @property
    def block(self):
        return self._get_derivation_attribute('block', ('extension', 'restriction', 'substitution'))

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('extension', 'restriction'))

    @property
    def form(self):
        return get_xsd_attribute(self.elem, 'form', enumeration=('qualified', 'unqualified'))

    @property
    def nillable(self):
        return get_xsd_bool_attribute(self.elem, 'nillable', default=False)

    @property
    def substitution_group(self):
        return self._attrib.get('substitutionGroup')


class XsdAnyAttribute(XsdBase, ValidatorMixin):

    def __init__(self, elem=None, schema=None):
        super(XsdAnyAttribute, self).__init__(elem=elem, schema=schema)
        self._target_namespace = schema.target_namespace if schema else ''
        self._namespaces = schema.namespaces if schema else {}
        self._lookup_table = schema.lookup_table if schema else {}

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(self.elem, 'processContents', 'strict', ('lax', 'skip', 'strict'))

    def validate(self, obj):
        if self.process_contents == 'skip':
            return

        if isinstance(obj, dict):
            attributes = obj
        elif isinstance(obj, str):
            attributes = dict([attr.split('=') for attr in obj.split('')])
        else:
            attributes = obj.attrib

        any_namespace = self.namespace
        for name, value in attributes.items():
            qname, namespace = split_reference(name, namespaces=self._namespaces)
            if not (namespace == XSI_NAMESPACE_PATH or namespace != self._target_namespace and
                    any([x in any_namespace for x in ("##any", "##other", "##local", namespace)]) or
                    namespace == self._target_namespace and
                    any([x in any_namespace for x in ("##any", "##targetNamespace", "##local", namespace)])):
                yield XMLSchemaValidationError(
                    self, name, "attribute not allowed for this element", obj, self.elem
                )
            try:
                xsd_attribute = lookup_attribute(qname, namespace, self._lookup_table)
            except XMLSchemaLookupError:
                if self.process_contents == 'strict':
                    yield XMLSchemaValidationError(
                        self, name, "attribute not found", obj, self.elem
                    )
            else:
                xsd_attribute.validate(value)


class XsdAnyElement(XsdBase, ValidatorMixin, OccursMixin):

    def __init__(self, elem=None, schema=None):
        super(XsdAnyElement, self).__init__(elem=elem, schema=schema)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(self.elem, 'processContents', 'strict', ('lax', 'skip', 'strict'))


__all__ = (
    'XsdBase', 'XsdUniqueFacet', 'XsdEnumerationFacet', 'XsdPatternsFacet',
    'XsdGroup', 'XsdSimpleType', 'XsdAtomicType', 'XsdRestriction',
    'XsdList', 'XsdUnion', 'XsdComplexType', 'XsdAttributeGroup',
    'XsdAttribute', 'XsdElement', 'XsdAnyAttribute', 'XsdAnyElement'
)