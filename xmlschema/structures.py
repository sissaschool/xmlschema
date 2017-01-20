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
from collections import MutableMapping, MutableSequence

from .core import XSI_NAMESPACE_PATH, unicode_type
from .exceptions import *
from .utils import linked_flatten, meta_next_gen, split_reference, get_qname
from .xsdbase import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, check_type, check_value,
    get_xsd_attribute, get_xsd_bool_attribute, get_xsd_int_attribute, lookup_attribute, XsdBase
)
from .facets import (
    XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG, XSD_WHITE_SPACE_ENUM,
    XSD_v1_1_FACETS, LIST_FACETS, UNION_FACETS, check_facets_group
)


class ValidatorMixin(object):

    def validate(self, text_or_obj):
        raise NotImplementedError("%r: you must provide a concrete validate() method" % self.__class__)

    def decode(self, text):
        raise NotImplementedError("%r: you must provide a concrete decode() method" % self.__class__)

    def encode(self, obj):
        raise NotImplementedError("%r: you must provide a concrete encode() method" % self.__class__)


class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t
    """
    def is_optional(self):
        return getattr(self, '_attrib').get('minOccurs', '').strip() == "0"

    @property
    def min_occurs(self):
        return get_xsd_int_attribute(getattr(self, 'elem'), 'minOccurs', default=1, minimum=0)

    @property
    def max_occurs(self):
        try:
            return get_xsd_int_attribute(getattr(self, 'elem'), 'maxOccurs', default=1, minimum=0)
        except (XMLSchemaTypeError, XMLSchemaValueError):
            if getattr(self, '_attrib')['maxOccurs'] == 'unbounded':
                return None
            raise

    def model_generator(self):
        try:
            for i in range(self.max_occurs):
                yield self
        except TypeError:
            while True:
                yield self


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
            check_type(self, key, self, value, (XsdAnyAttribute,))
        else:
            check_type(self, key, self, value, (XsdAttribute,))
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
            check_type(self, name, None, value, (dict,))
            for k, v in value.items():
                check_type(self, name, dict, v, (XsdAnyAttribute,))
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


class XsdGroup(MutableSequence, XsdBase, ValidatorMixin, ParticleMixin):
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
        check_type(self, i, list, item, (XsdGroup,))
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
            check_value(self, name, None, value, (None, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG))
        elif name == 'mixed':
            check_value(self, name, None, value, (True, False))
        elif name == '_group':
            check_type(self, name, None, value, (list,))
            for i in range(len(value)):
                check_type(self, name, i, value[i], (XsdGroup, XsdElement, XsdAnyElement))
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

    def encode(self, obj):
        return


class XsdSimpleType(XsdBase, ValidatorMixin):
    """
    Base class for simple types, used only for instances of xs:anySimpleType.
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
            return XSD_v1_1_FACETS.union({None})

    def normalize(self, text):
        """
        Normalize and restrict value-space with pre-lexical and lexical facets.
        :param text: Text string.
        :return: Normalized and restricted string.
        """
        try:
            if self.white_space == 'replace':
                text = self._REGEX_SPACE.sub(u" ", text)
            elif self.white_space == 'collapse':
                text = self._REGEX_SPACES.sub(u" ", text)
            self.patterns(text)
        except TypeError:
            pass
        return text

    #
    # ValidatorMixin methods: used only for builtin anySimpleType.
    def validate(self, obj):
        if not isinstance(obj, unicode_type):
            raise XMLSchemaValidationError(self, obj, reason="value must be a string!")
        obj = self.normalize(obj)
        for validator in self.validators:
            validator(obj)

    def decode(self, text):
        if not isinstance(text, unicode_type):
            raise XMLSchemaTypeError("argument must be a string!")
        self.validate(text)
        return unicode_type(text)

    def encode(self, obj):
        if not isinstance(obj, unicode_type):
            raise XMLSchemaEncodeError(self, obj, unicode_type)
        return unicode_type(obj)


class XsdAtomic(XsdSimpleType):

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
            return XSD_v1_1_FACETS.union({None})
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
            raise XMLSchemaTypeError("%s object is not callable" % python_type.__class__.__name__)
        super(XsdAtomicBuiltin, self).__init__(base_type, name, facets=facets)
        self.python_type = python_type
        self.to_python = to_python or python_type
        self.from_python = from_python or unicode_type

    def validate(self, obj):
        if not isinstance(obj, self.python_type):
            raise XMLSchemaValidationError(
                self, obj, "value type is {} instead of {}".format(type(obj), repr(self.python_type))
            )
        obj = self.normalize(obj)
        for validator in self.validators:
            validator(obj)

    def decode(self, text):
        """
        Transform an XML text into a Python object, then validate.
        :param text: XML text
        """
        if not isinstance(text, (unicode_type, str)):
            raise XMLSchemaTypeError("argument must be a string!: %s" % type(text))
        text = self.normalize(text)
        try:
            obj = self.to_python(text)
        except ValueError:
            raise XMLSchemaDecodeError(self, text, self.python_type)
        else:
            for validator in self.validators:
                validator(obj)
            return obj

    def encode(self, obj):
        """
        Transform a Python object into an XML string.
        :param obj: The Python object that has to be encoded in XML
        """
        if not isinstance(obj, self.python_type):
            raise XMLSchemaEncodeError(self, obj, self.python_type)
        return self.from_python(obj)


class XsdAtomicRestriction(XsdAtomic):
    """
    A class for representing a user defined atomic simpleType (restriction).
    """
    def __init__(self, base_type, name=None, elem=None, schema=None, facets=None):
        super(XsdAtomicRestriction, self).__init__(base_type, name, elem, schema, facets)

    def validate(self, obj):
        for validator in self.validators:
            validator(obj)
        self.base_type.validate(obj)

    def decode(self, text):
        text = self.normalize(text)
        value = self.base_type.decode(text)
        for validator in self.validators:
            validator(value)
        return value

    def encode(self, obj):
        return self.base_type.encode(obj)


class XsdList(XsdSimpleType):

    def __init__(self, item_type, name=None, elem=None, schema=None, facets=None):
        super(XsdList, self).__init__(name, elem, schema, facets)
        self.item_type = item_type
        self.white_space = self.white_space or 'collapse'

    def __setattr__(self, name, value):
        if name == "item_type":
            check_type(self, name, None, value, (XsdSimpleType,))
        super(XsdList, self).__setattr__(name, value)

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(LIST_FACETS)
        except AttributeError:
            return LIST_FACETS

    def validate(self, obj):
        for validator in self.validators:
            validator(obj)
        for item in obj:
            if isinstance(item, (list, tuple)):
                map(self.item_type.validate, item)
            else:
                self.item_type.validate(item)

    def decode(self, text):
        # text = self.normalize(text)
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

    def __init__(self, member_types, name=None, elem=None, schema=None, facets=None):
        super(XsdUnion, self).__init__(name, elem, schema, facets)
        self.member_types = member_types
        self.white_space = self.white_space or 'collapse'

    def __setattr__(self, name, value):
        if name == "member_types":
            for member_type in value:
                check_type(self, name, list, member_type, (XsdSimpleType,))
        elif name == 'white_space':
            check_value(self, name, "whiteSpace facet", value, ('collapse',))
        super(XsdUnion, self).__setattr__(name, value)

    @property
    def admitted_facets(self):
        try:
            return self.schema.FACETS.intersection(UNION_FACETS)
        except AttributeError:
            return UNION_FACETS

    def validate(self, obj):
        for validator in self.validators:
            validator(obj)
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
    def __init__(self, content_type, name=None, elem=None, schema=None, attributes=None,
                 derivation=None, mixed=None):
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
            check_type(self, name, None, value, (XsdSimpleType, XsdComplexType, XsdGroup))
        elif name == 'attributes':
            check_type(self, name, None, value, (XsdAttributeGroup,))
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
            check_type(self, name, None, value, (XsdSimpleType,))
        super(XsdAttribute, self).__setattr__(name, value)

    @property
    def form(self):
        return get_xsd_attribute(self.elem, 'form', ('qualified', 'unqualified'))

    @property
    def use(self):
        return get_xsd_attribute(
            self.elem, 'use', ('optional', 'prohibited', 'required'), default='optional'
        )

    def is_optional(self):
        return self.use == 'optional'

    def validate(self, obj):
        return self.type.validate(obj)

    def decode(self, text):
        return self.type.decode(text)

    def encode(self, obj):
        return self.type.encode(obj)


class XsdElement(XsdBase, ValidatorMixin, ParticleMixin):
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
            check_type(self, name, None, value, (XsdSimpleType, XsdComplexType))
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
        return get_xsd_attribute(self.elem, 'form', ('qualified', 'unqualified'))

    @property
    def nillable(self):
        return get_xsd_bool_attribute(self.elem, 'nillable', default=False)

    @property
    def substitution_group(self):
        return self._attrib.get('substitutionGroup')


class XsdAnyAttribute(XsdBase):

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
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict',
        )

    def validate(self, obj):
        if self.process_contents == 'skip':
            return

        if isinstance(obj, dict):
            attributes = obj
        elif isinstance(obj, str):
            attributes = dict((attr.split('=', maxsplit=1) for attr in obj.split('')))
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


class XsdAnyElement(XsdBase, ParticleMixin):

    def __init__(self, elem=None, schema=None):
        super(XsdAnyElement, self).__init__(elem=elem, schema=schema)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict'
        )
