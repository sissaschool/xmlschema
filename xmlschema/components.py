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
This module contains classes for XML Schema components.
"""
from collections import MutableMapping, MutableSequence

from .core import XSI_NAMESPACE_PATH, unicode_type
from .exceptions import *
from .utils import linked_flatten, meta_next_gen, split_reference, get_qname, listify_update
from .xsdbase import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, check_type, check_value,
    get_xsd_attribute, get_xsd_bool_attribute, get_xsd_int_attribute, lookup_attribute, XsdBase
)
from .facets import (
    XSD_PATTERN_TAG, XSD_WHITE_SPACE_TAG, XSD_v1_1_FACETS,
    LIST_FACETS, UNION_FACETS, check_facets_group
)


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

    def iter_model(self):
        try:
            for i in range(self.max_occurs):
                yield self
        except TypeError:
            while True:
                yield self


class XsdAttribute(XsdBase):
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

    def iter_decode(self, text, validate=True, **kwargs):
        for result in self.type.iter_decode(text or self.default, validate):
            yield result
            if not isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                return

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.type.iter_encode(obj, validate):
            yield result
            if not isinstance(result, (XMLSchemaEncodeError, XMLSchemaValidationError)):
                return


class XsdElement(XsdBase, ParticleMixin):
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
        try:
            self.attributes = self.type.attributes
        except AttributeError:
            self.attributes = XsdAttributeGroup(schema=schema)

    def __setattr__(self, name, value):
        if name == "type":
            check_type(self, name, None, value, (XsdSimpleType, XsdComplexType))
        super(XsdElement, self).__setattr__(name, value)

    def iter_decode(self, elem, validate=True, **kwargs):
        result_dict = {}
        use_defaults = kwargs.get('use_defaults', True)
        if elem.attrib:
            for result in self.attributes.iter_decode(elem, validate, **kwargs):
                if isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    yield result
                else:
                    result_dict.update(result)

        if len(elem):
            for result in self.type.iter_decode(elem, validate, **kwargs):
                if isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    yield result
                else:
                    if not isinstance(result, dict):
                        raise XMLSchemaTypeError("expected a %r, found %r." % (dict, type(result)))
                    elif not result:
                        raise XMLSchemaTypeError("the content dictionary of an element cannot be empty!")
                    listify_update(result_dict, result)
        else:
            if use_defaults:
                text = elem.text or self.default
            else:
                text = elem.text or ''

            for result in self.type.iter_decode(text, validate, **kwargs):
                if isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    yield result
                elif not result_dict:
                    yield result
                    return
                elif text:
                    result_dict['_text'] = result
                    break

        yield result_dict

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.type.iter_encode(obj, validate, **kwargs):
            yield result
            if isinstance(result, XMLSchemaEncodeError):
                return

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


class XsdComplexType(XsdBase):
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

    def iter_decode(self, obj, validate=True, **kwargs):
        for result in self.content_type.iter_decode(obj, validate, **kwargs):
            yield result

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.content_type.iter_encode(obj, validate, **kwargs):
            yield result


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

    def iter_decode(self, elem, validate=True, **kwargs):
        required_attributes = {
            k for k, v in self.items() if k is not None and not v.is_optional()
        }
        result_dict = {}
        for name, value in elem.items():
            qname = get_qname(self.schema.target_namespace, name)
            try:
                xsd_attribute = self[qname]
            except KeyError:
                qname, namespace = split_reference(name, self._namespaces)
                if namespace == XSI_NAMESPACE_PATH:
                    try:
                        xsd_attribute = lookup_attribute(qname, namespace, self._lookup_table)
                    except XMLSchemaLookupError:
                        yield XMLSchemaValidationError(
                            self, name, "not an attribute of the XSI namespace!", elem, self.elem
                        )
                        continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = {qname: value}
                    except KeyError:
                        yield XMLSchemaValidationError(
                            self, name, "attribute not allowed for this element", elem, self.elem
                        )
                        continue
            else:
                required_attributes.discard(qname)

            for result in xsd_attribute.iter_decode(value, validate, **kwargs):
                if isinstance(result, (XMLSchemaValidationError, XMLSchemaDecodeError)):
                    yield result
                else:
                    result_dict[name] = result
                    break

        if required_attributes:
            yield XMLSchemaValidationError(
                validator=self,
                value=elem.attrib,
                reason="missing required attributes %r" % required_attributes,
                elem=elem,
                schema_elem=self.elem
            )
        yield result_dict


class XsdGroup(MutableSequence, XsdBase, ParticleMixin):
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
        for item in self:
            if isinstance(item, XsdElement):
                yield item
            elif isinstance(item, XsdGroup):
                for xsd_element in item.iter_elements():
                    yield xsd_element

    def iter_model(self):
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
                    yield gen_cls([item.iter_model()])
            elif self.model == XSD_ALL_TAG:
                yield gen_cls([item.iter_model() for item in self._group])
            elif self.model == XSD_CHOICE_TAG:
                yield gen_cls([item.iter_model() for item in self._group])

    def iter_decode(self, elem, validate=True, **kwargs):
        # Validate character data between tags
        if validate and not self.mixed and \
                (elem.text.strip() or any([child.tail.strip() for child in elem])):
            yield XMLSchemaValidationError(
                self, elem, "character data between child elements not allowed!", elem, self.elem
            )

        # Decode elements
        group_elements = {e.name: e for e in self.iter_elements()}
        result_dict = {}
        target_namespace = self.schema.target_namespace
        for child in elem:
            try:
                xsd_element = group_elements[get_qname(target_namespace, child.tag)]
            except KeyError:
                yield XMLSchemaValidationError(
                    self, child.tag, "element not in schema!", child, self.elem
                )
            else:
                for result in xsd_element.iter_decode(child, validate, **kwargs):
                    if isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                        yield result
                    else:
                        listify_update(result_dict, (child.tag, result))

        # Validate child elements
        model_iterator = self.iter_model()
        elem_iterator = iter(elem)
        consumed_child = True
        while validate:
            try:
                content_model = next(model_iterator)
                validation_group = []
                for g, c in linked_flatten(content_model):
                    validation_group.extend([t for t in meta_next_gen(g, c)])
            except StopIteration:
                for child in elem_iterator:
                    yield XMLSchemaValidationError(self, child, "invalid tag", child, self.elem)
                break

            missing_tags = set([e[0].name for e in validation_group if not e[0].is_optional()])
            while validation_group:
                if consumed_child:
                    try:
                        child = next(elem_iterator)
                    except StopIteration:
                        if missing_tags:
                            yield XMLSchemaValidationError(
                                validator=self,
                                value=elem,
                                reason="tag expected: {}".format(missing_tags),
                                elem=elem,
                                schema_elem=self.elem
                            )
                        yield result_dict
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
                        if len(missing_tags) == 1:
                            msg = "element %r expected, found %r." % (missing_tags.pop(), child.tag)
                        else:
                            msg = "one element of %r expected, found %r." % (missing_tags, child.tag)
                        yield XMLSchemaValidationError(self, child, msg, child, self.elem)
                        consumed_child = True
                    break

        yield result_dict

    def iter_encode(self, obj, validate=True, **kwargs):
        return


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

    def iter_decode(self, obj, validate=True, **kwargs):
        if self.process_contents == 'skip':
            return

        if isinstance(obj, dict):
            attributes = obj
        elif isinstance(obj, str):
            attributes = {(attr.split('=', maxsplit=1) for attr in obj.split(''))}
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
                for result in xsd_attribute.iter_decode(value, validate, **kwargs):
                    yield result


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


class XsdSimpleType(XsdBase):
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
                obj = self._REGEX_SPACES.sub(u" ", obj)
            self.patterns(obj)
        except TypeError:
            pass
        return obj

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        if validate:
            for validator in self.validators:
                for error in validator(text):
                    yield error
        yield text

    def iter_encode(self, text, validate=True, **kwargs):
        if not isinstance(text, (str, unicode_type)):
            yield XMLSchemaEncodeError(self, text, unicode_type)

        if validate:
            for validator in self.validators:
                for error in validator(text):
                    yield error
        yield text


#
# simpleType's derived classes:
class XsdAtomic(XsdSimpleType):
    """
    Class for simpleType atomic variety declarations. An atomic
    declaration has a base_type attribute that refers to primitive
    or derived atomic built-in type or another derived simpleType.
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

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        try:
            result = self.to_python(text)
        except ValueError:
            yield XMLSchemaDecodeError(self, text, self.python_type)
            yield unicode_type(text)
            return

        if validate:
            for validator in self.validators:
                for error in validator(result):
                    yield error
        yield result

    def iter_encode(self, obj, validate=True, **kwargs):
        if not isinstance(obj, self.python_type):
            yield XMLSchemaEncodeError(self, obj, self.python_type)
            yield unicode_type(obj)
            return

        if validate:
            for validator in self.validators:
                for error in validator(obj):
                    yield error
        yield self.from_python(obj)


class XsdList(XsdSimpleType):
    """
    Class for simpleType list variety declarations. A list declaration has an
    item_type attribute that refers to an atomic or union simpleType definition.
    """

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

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        items = []
        for chunk in text.split():
            for result in self.item_type.iter_decode(chunk, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                elif isinstance(result, XMLSchemaDecodeError):
                    yield result
                    items.append(unicode_type(chunk))
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
                    encoded_items.append(unicode_type(item))
                else:
                    encoded_items.append(result)
        yield u' '.join(encoded_items)


class XsdUnion(XsdSimpleType):
    """
    Class for simpleType union variety declarations. A union declaration
    has a member_types attribute that refers to a simpleType definition.
    """
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

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        for member_type in self.member_types:
            for result in member_type.iter_decode(text, validate, **kwargs):
                if not isinstance(result, (XMLSchemaDecodeError, XMLSchemaValidationError)):
                    if validate:
                        for validator in self.validators:
                            for error in validator(result):
                                yield error
                    yield result
                    return
        yield XMLSchemaDecodeError(
            self, text, self.member_types, reason="no type suitable for decoding the text."
        )
        yield unicode_type(text)

    def iter_encode(self, obj, validate=True, **kwargs):
        for member_type in self.member_types:
            for result in member_type.iter_encode(obj, validate):
                if not isinstance(result, (XMLSchemaEncodeError, XMLSchemaValidationError)):
                    if validate:
                        for validator in self.validators:
                            for error in validator(obj):
                                yield error
                    yield result
                    return
        yield XMLSchemaEncodeError(self, obj, self.member_types)
        yield unicode_type(obj)


class XsdAtomicRestriction(XsdAtomic):
    """
    Class for atomic simpleType and complexType's simpleContent restrictions.
    """
    def __init__(self, base_type, name=None, elem=None, schema=None, facets=None):
        super(XsdAtomicRestriction, self).__init__(base_type, name, elem, schema, facets)

    def iter_decode(self, text, validate=True, **kwargs):
        text = self.normalize(text)
        for result in self.base_type.iter_decode(text, validate, **kwargs):
            if isinstance(result, XMLSchemaDecodeError):
                yield result
                yield unicode_type(text)
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
                yield unicode_type(obj)
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
