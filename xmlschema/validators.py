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
This module contains classes for elements of the XML Schema.
"""
from collections import MutableMapping, MutableSequence
from .utils import linked_flatten, nested_next
from .core import (
    PY3, etree_tostring, XSI_NAMESPACE_PATH,
    XMLSchemaException, XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaLookupError
)
from .qnames import split_reference, get_qname
from .parse import (
    XMLSchemaParseError, lookup_attribute, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG
)

class XMLSchemaValidatorError(XMLSchemaException, ValueError):
    """Raised when the XML data string is not validated with the XSD schema."""

    def __init__(self, validator, message):
        self.validator = validator
        self.message = message or u''
        self.reason = None
        self.schema_elem = None
        self.elem = None

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return u''.join([
            self.message,
            u'\n\nReason: %s' % self.reason if self.reason is not None else '',
            u"\n\nSchema:\n\n  %s" % etree_tostring(self.schema_elem) if self.schema_elem is not None else '',
            u"\nInstance:\n\n  %s" % etree_tostring(self.elem) if self.elem is not None else ''
        ])

    if PY3:
        __str__ = __unicode__


class XMLSchemaMultipleValidatorErrors(XMLSchemaException):
    """Raised to report a list of validator errors."""
    def __init__(self, errors, result=None):
        if not errors:
            raise ValueError("passed an empty error list!")
        self.errors = errors
        self.result = result

    def __str__(self):
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        if self.result is not None:
            return u'n.%d errors creating <%s object at %s>: %s' % (
                len(self.errors),
                self.result.__class__.__name__, hex(id(self.result)),
                u'\n'.join([u'\n%s\n%s: %s' % (u'-' * 70, type(err), err) for err in self.errors])
            )
        return u'%r' % self.errors

    if PY3:
        __str__ = __unicode__


class XMLSchemaDecodeError(XMLSchemaValidatorError):
    """Raised when an XML data string is not decodable to a Python object."""

    def __init__(self, validator, text, decoder, reason=None, schema_elem=None, elem=None):
        self.message = u"cannot decode '%s' using the type %r of validator %r." % (text, decoder, validator)
        self.validator = validator
        self.text = text
        self.decoder = decoder
        self.reason = reason
        self.elem = elem
        self.schema_elem = schema_elem


class XMLSchemaEncodeError(XMLSchemaValidatorError):
    """Raised when an object is not encodable to an XML data string."""

    def __init__(self, validator, obj, encoder, reason=None, elem=None, schema_elem=None):
        self.message = u"cannot encode %r using the type %r of validator %r." % (obj, encoder, validator)
        self.validator = validator
        self.obj = obj
        self.encoder = encoder
        self.reason = reason
        self.elem = elem
        self.schema = schema_elem


class XMLSchemaValidationError(XMLSchemaValidatorError):
    """Raised when the XML data string is not validated with the XSD schema."""

    def __init__(self, validator, value, reason=None, elem=None, schema_elem=None):
        self.message = u"failed validating %r with %r." % (value, validator)
        self.validator = validator
        self.value = value
        self.reason = reason
        self.elem = elem
        self.schema_elem = schema_elem


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

    @staticmethod
    def _check_type(name, value, *types):
        if not isinstance(value, types):
            raise XMLSchemaTypeError(
                "wrong type {} for '{}' attribute, it must be one of {}.".format(type(value), name, types)
            )

    @staticmethod
    def _check_value(name, value, *values):
        if value not in values:
            raise XMLSchemaValueError(
                "wrong value {} for '{}' attribute, it must be one of {}.".format(value, name, values)
            )

    @property
    def id(self):
        return self._attrib.get('id')


class ParseElementMixin(object):

    def _get_boolean_attribute(self, name, default=None):
        try:
            value = self._attrib[name].strip()
            if value in ('true', '1'):
                return True
            elif value in ('false', '0'):
                return False
            else:
                raise XMLSchemaParseError("a Boolean value is required for attribute %r" % name, self.elem)
        except KeyError:
            return default

    def _get_natural_number_attribute(self, name, default=None):
        try:
            value = int(self._attrib[name])
            if value < 0:
                raise XMLSchemaParseError(
                    "a non negative integer is required for attribute %r" % name, self.elem
                )
        except KeyError:
            return default

    def _get_enumerated_attribute(self, name, enumeration, default=None):
        try:
            value = self._attrib[name]
            if value not in enumeration:
                raise XMLSchemaParseError("wrong value %r for %r attribute" % (value, name), self.elem)
            return value
        except KeyError:
            return default

    def _get_derivation_attribute(self, name, *args):
        try:
            values = self._attrib[name].strip().split()
            if not values:
                raise XMLSchemaParseError("wrong value for %r attribute" % name, self.elem)
            if values[0] == "#all" and len(values) == 1:
                return values
            for s in values:
                if s not in args:
                    raise XMLSchemaParseError("wrong value for %r attribute" % name, self.elem)
        except KeyError:
            return None

    def _get_namespace_attribute(self):
        name = 'namespace'
        try:
            values = self._attrib[name].strip().split()
            if not values:
                raise XMLSchemaParseError("wrong value for %r attribute" % name, self.elem)
            if values[0] in ('##all', '##other', '##local', '##targetNamespace') and len(values) == 1:
                return values
            for s in values:
                if s in ('##all', '##other'):
                    raise XMLSchemaParseError("wrong value for %r attribute" % name, self.elem)
        except KeyError:
            return '##any'


class OccursMixin(ParseElementMixin):

    def is_optional(self):
        return self._attrib.get('minOccurs', '').strip() == "0"

    @property
    def min_occurs(self):
        try:
            return self._get_natural_number_attribute('minOccurs', 1)
        except ValueError:
            raise XMLSchemaParseError(
                "a non negative integer is required for attribute 'minOccurs'", self.elem
            )

    @property
    def max_occurs(self):
        try:
            return self._get_natural_number_attribute('maxOccurs', 1)
        except ValueError:
            if self._attrib['maxOccurs'] == 'unbounded':
                return None
            raise XMLSchemaParseError(
                "a non negative integer is required for attribute 'maxOccurs'", self.elem
            )

    def model_generator(self):
        try:
            for i in range(self.max_occurs):
                yield self
        except TypeError:
            while True:
                yield self


class ValidatorMixin(object):

    def validate(self, value):
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
    def __getitem__(self, key): return self._attribute_group[key]
    def __setitem__(self, key, value):
        if key is None:
            self._check_type(key, value, XsdAnyAttribute)
        else:
            self._check_type(key, value, XsdAttribute)
        self._attribute_group[key] = value
    def __delitem__(self, key): del self._attribute_group[key]
    def __iter__(self): return iter(self._attribute_group)
    def __len__(self): return len(self._attribute_group)

    # Other methods
    def __setattr__(self, name, value):
        if name == '_attribute_group':
            self._check_type(name, value, dict)
            for k, v in value.items():
                if k is None:
                    self._check_type(k, v, XsdAnyAttribute)
                else:
                    self._check_type(k, v, XsdAttribute)
        super(XsdAttributeGroup, self).__setattr__(name, value)

    def validate(self, attributes, elem=None):
        if not attributes: return
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
            if type(initlist) == type(self._group):
                self._group[:] = initlist
            elif isinstance(initlist, XsdGroup):
                self._group[:] = initlist._group[:]
            else:
                self._group = list(initlist)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i): return self._group[i]
    def __setitem__(self, i, item):
        self._check_type(i, item, XsdGroup)
        if self.model is None:
            raise XMLSchemaParseError(u"cannot add items when the group model is None.", self.elem)
        self._group[i] = item
    def __delitem__(self, i): del self._group[i]
    def __len__(self): return len(self._group)
    def insert(self, i, item): self._group.insert(i, item)

    def __repr__(self):
        return XsdBase.__repr__(self)

    def __setattr__(self, name, value):
        if name == 'model':
            self._check_value(name, value, None, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG)
        elif name == 'mixed':
            self._check_value(name, value, True, False)
        elif name == '_group':
            self._check_type(name, value, list)
            for i in range(len(value)):
                self._check_type(i, value[i], XsdGroup, XsdElement, XsdAnyElement)
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
                yield gen_cls([item.model_generator() for item in self])
            elif self.model == XSD_CHOICE_TAG:
                yield gen_cls([item.model_generator() for item in self])

    def validate_content(self, elem):
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
                        validation_group.extend([t for t in nested_next(g, c)])
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

    def validate(self, value):
        if not isinstance(value, str):
            raise XMLSchemaValidationError(self, value, reason="value must be a string!")
        if not self.mixed and value:
            raise XMLSchemaValidationError(
                self, value, reason="character data not allowed for this content type (mixed=False)."
            )

    def decode(self, text):
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        self.validate(text)
        return text


class XsdSimpleType(XsdBase, ValidatorMixin, ParseElementMixin):
    """
    Base class for simple types, used only for instances of xs:anySimpleType.
    """

    @property
    def final(self):
        return self._get_derivation_attribute('final', 'list', 'union', 'restriction')

    def validate(self, value):
        if not isinstance(value, str):
            raise XMLSchemaValidationError(self, value, reason="value must be a string!")

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
    Class for defining XML Schema simpleType atomic datatypes. An instance contains
    a Python's type transformation and a list of validator functions.

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

    def check(self):
        pass

    def validate(self, value):
        """
        Validator for decoded values.
        :param value: The Python's object that has to be validated
        """
        if not isinstance(value, self.python_type):
            raise XMLSchemaValidationError(
                self, value, "value type is {} instead of {}".format(type(value), repr(self.python_type))
            )
        if not all([validator(value) for validator in self.validators]):
            raise XMLSchemaValidationError(self, value)

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
    def __init__(self, base_type, name=None, elem=None, schema=None,
                 length=None, validators=None, enumeration=None):
        super(XsdRestriction, self).__init__(name, elem, schema)
        self.base_type = base_type
        self.validators = validators or []
        self.length = length
        self.enumeration = [
            self.base_type.decode(value) for value in enumeration
        ] if enumeration else []

    def __setattr__(self, name, value):
        if name == "base_type":
            self._check_type(name, value, XsdSimpleType, XsdComplexType)
        super(XsdRestriction, self).__setattr__(name, value)

    def check(self):
        pass

    def validate(self, value):
        self.base_type.validate(value)
        try:
            if not all([validator(value) for validator in self.validators]):
                raise XMLSchemaValidationError(self, value)
        except TypeError:
            raise
        if self.enumeration and value not in self.enumeration:
            raise XMLSchemaValidationError(
                self, value, reason="invalid value, it must be one of %r" % self.enumeration
            )

    def decode(self, text):
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
            self._check_type(name, value, XsdSimpleType)
        super(XsdList, self).__setattr__(name, value)

    def check(self):
        pass

    def validate(self, value):
        _validate = self.item_type.validate
        for item in value:
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
                self._check_type("item of <%s>" % name, member_type, XsdSimpleType)
        super(XsdUnion, self).__setattr__(name, value)

    def check(self):
        pass

    def validate(self, value):
        for _type in self.member_types:
            try:
                _type.validate(value)
            except XMLSchemaValidationError:
                pass
            else:
                return
        raise XMLSchemaValidationError(self, value, reason="No type suitable for validating the value.")

    def decode(self, text):
        _decoded_type = None
        for _type in self.member_types:
            try:
                return _type.decode(text)
            except XMLSchemaDecodeError:
                pass
            except XMLSchemaValidationError:
                _decoded_type = _type
        if _decoded_type is not None:
            return _decoded_type.decode(text)
        raise XMLSchemaDecodeError(
            self, text, self.member_types, reason="No type suitable for decoding the text."
        )

    def encode(self, obj):
        for _type in self.member_types:
            try:
                return _type.encode(obj)
            except XMLSchemaEncodeError:
                pass
        raise XMLSchemaEncodeError(self, obj, self.member_types)


class XsdComplexType(XsdBase, ValidatorMixin, ParseElementMixin):
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
            self.mixed = self._get_boolean_attribute('mixed', default=False)
        self.derivation = derivation

    def __setattr__(self, name, value):
        if name == "content_type":
            self._check_type(name, value, XsdSimpleType, XsdComplexType, XsdGroup)
        elif name == 'attributes':
            self._check_type(name, value, XsdAttributeGroup)
        super(XsdComplexType, self).__setattr__(name, value)

    @property
    def abstract(self):
        return self._get_boolean_attribute('abstract', default=False)

    @property
    def block(self):
        return self._get_derivation_attribute('block', 'extension', 'restriction')

    @property
    def final(self):
        return self._get_derivation_attribute('final', 'extension', 'restriction')

    def has_restriction(self):
        return self.derivation is False

    def has_extension(self):
        return self.derivation is True

    def check(self):
        self.content_type.check()

    def validate(self, value):
        self.content_type.validate(value)

    def decode(self, text):
        if not isinstance(text, str):
            raise XMLSchemaTypeError("argument must be a string!")
        value = self.content_type.decode(text)
        self.content_type.validate(value)
        return value

    def encode(self, obj):
        return self.content_type.encode(obj)


class XsdAttribute(XsdBase, ValidatorMixin, ParseElementMixin):
    """
    Support structure to associate an attribute with XSD simple types.
    """
    def __init__(self, xsd_type, name, elem=None, schema=None, qualified=False):
        super(XsdAttribute, self).__init__(name, elem, schema)
        self.type = xsd_type
        self.qualified = qualified
        self.default = self._attrib.get('default')
        self.fixed = self._attrib.get('fixed')
        if self.default is not None and self.fixed is not None:
            raise XMLSchemaParseError("'default' and 'fixed' attributes are mutually exclusive", self.elem)

    def __setattr__(self, name, value):
        if name == "type":
            self._check_type(name, value, XsdSimpleType)
        super(XsdAttribute, self).__setattr__(name, value)

    @property
    def form(self):
        return self._get_enumerated_attribute('form', ('qualified', 'unqualified'))

    @property
    def use(self):
        return self._get_enumerated_attribute('use', ('optional', 'prohibited', 'required'), 'optional')

    def is_optional(self):
        return self.use == 'optional'

    def check(self):
        pass

    def validate(self, value):
        return self.type.validate(value)

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
        self.default = self._attrib.get('default')
        self.fixed = self._attrib.get('fixed')
        if self.default is not None and self.fixed is not None:
            raise XMLSchemaParseError("'default' and 'fixed' attributes are mutually exclusive", self.elem)

    def __setattr__(self, name, value):
        if name == "type":
            self._check_type(name, value, XsdSimpleType, XsdComplexType)
        super(XsdElement, self).__setattr__(name, value)

    def validate(self, value):
        self.type.validate(value)

    def decode(self, text):
        self.type.decode(text)

    def encode(self, obj):
        self.type.encode(obj)

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.schema.target_namespace, name)]
        return self.type.attributes[name]

    @property
    def abstract(self):
        return self._get_boolean_attribute('abstract', default=False)

    @property
    def block(self):
        return self._get_derivation_attribute('block', 'extension', 'restriction', 'substitution')

    @property
    def final(self):
        return self._get_derivation_attribute('final', 'extension', 'restriction')

    @property
    def form(self):
        return self._get_enumerated_attribute('form', ('qualified', 'unqualified'))

    @property
    def nillable(self):
        return self._get_boolean_attribute('nillable', default=False)

    @property
    def substitution_group(self):
        return self._attrib.get('substitutionGroup')


class XsdAnyAttribute(XsdBase, ValidatorMixin, ParseElementMixin):

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
        return self._get_enumerated_attribute('processContents', ('lax', 'skip', 'strict'), 'strict')

    def validate(self, attributes, elem=None):
        if self.process_contents == 'skip':
            return
        any_namespace = self.namespace
        for name, value in attributes.items():
            qname, namespace = split_reference(name, namespaces=self._namespaces)
            if not (namespace == XSI_NAMESPACE_PATH or
                    namespace != self._target_namespace and
                        any([x in any_namespace for x in
                             ("##any", "##other", "##local", namespace)]) or
                    namespace == self._target_namespace and
                        any([x in any_namespace for x in
                             ("##any", "##targetNamespace", "##local", namespace)])):
                yield XMLSchemaValidationError(
                    self, name, "attribute not allowed for this element", elem, self.elem
                )
            try:
                xsd_attribute = lookup_attribute(qname, namespace, self._lookup_table)
            except XMLSchemaLookupError:
                if self.process_contents == 'strict':
                    yield XMLSchemaValidationError(
                        self, name, "attribute not found", elem, self.elem
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
        return self._get_enumerated_attribute('processContents', ('lax', 'skip', 'strict'), 'strict')
