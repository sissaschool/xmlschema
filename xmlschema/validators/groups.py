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
This module contains classes for XML Schema model groups.
"""
from collections import MutableSequence

from ..compat import unicode_type
from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..etree import etree_last_child, etree_child_index, etree_element
from ..namespaces import get_namespace
from ..qnames import local_name
from ..qnames import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, reference_to_qname, get_qname,
    XSD_COMPLEX_TYPE_TAG, XSD_ELEMENT_TAG, XSD_ANY_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
)

from .exceptions import (
    XMLSchemaValidationError, XMLSchemaParseError, XMLSchemaChildrenValidationError
)
from .xsdbase import ValidatorMixin, XsdComponent, XsdDeclaration, ParticleMixin
from .wildcards import XsdAnyElement

XSD_MODEL_GROUP_TAGS = {XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}

DUMMY_ANY_ELEMENT = etree_element(
    XSD_ANY_TAG,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


class XsdGroup(MutableSequence, XsdDeclaration, ValidatorMixin, ParticleMixin):
    """
    A class for XSD 'group', 'choice', 'sequence' definitions and
    XSD 1.0 'all' definitions.

    <group
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      name = NCName
      ref = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (all | choice | sequence)?)
    </group>

    <all
      id = ID
      maxOccurs = 1 : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, element*)
    </all>

    <choice
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </choice>

    <sequence
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </sequence>
    """
    def __init__(self, elem, schema, name=None, model=None, mixed=False,
                 initlist=None, is_global=False):
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
        XsdComponent.__init__(self, elem, schema, name, is_global)

    def __repr__(self):
        model = local_name(self.model)
        if self.name is None:
            return u'%s(model=%r)' % (self.__class__.__name__, model)
        elif self.ref is None:
            return u'%s(name=%r, model=%r)' % (self.__class__.__name__, self.prefixed_name, model)
        else:
            return u'%s(ref=%r, model=%r)' % (self.__class__.__name__, self.prefixed_name, model)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        assert isinstance(item, (tuple, ParticleMixin)), \
            "XsdGroup's items must be tuples or ParticleMixin instances."
        self._group[i] = item

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        assert isinstance(item, (tuple, ParticleMixin)), \
            "XsdGroup's items must be tuples or ParticleMixin instances."
        self._group.insert(i, item)

    def __setattr__(self, name, value):
        if name == 'model':
            assert value in (None, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG)
            model = getattr(self, 'model', None)
            if model is not None and value != model:
                raise XMLSchemaValueError("cannot change a valid group model: %r" % value)
        elif name == 'mixed':
            assert value in (True, False), "A boolean value is required for attribute 'mixed'."
        elif name == '_group':
            assert isinstance(value, list), "A list object is required for attribute '_group'."
            for item in value:
                assert isinstance(item, (tuple, ParticleMixin)), \
                    "XsdGroup's items must be tuples or ParticleMixin instances."
        super(XsdGroup, self).__setattr__(name, value)

    def _parse(self):
        super(XsdGroup, self)._parse()
        self._parse_particle()
        if self and not hasattr(self, '_elem'):
            self.clear()

        elem = self.elem
        if elem.tag == XSD_GROUP_TAG:
            # Global group (group)
            name = elem.get('name')
            ref = elem.get('ref')
            if name is None:
                if ref is not None:
                    # Reference to a global group
                    if self.is_global:
                        self._parse_error("a group reference cannot be global", elem)
                    self.name = reference_to_qname(ref, self.namespaces)
                    xsd_group = self.schema.maps.lookup_group(self.name)
                    if isinstance(xsd_group, tuple):
                        # Disallowed circular definition, substitute with any content group.
                        self._parse_error("Circular definitions detected for group %r:" % self.ref, xsd_group[0])
                        self.model = XSD_SEQUENCE_TAG
                        self.mixed = True
                        self.append(XsdAnyElement(DUMMY_ANY_ELEMENT, self.schema))
                    else:
                        self.model = xsd_group.model
                        self.append(xsd_group)
                else:
                    self._parse_error("missing both attributes 'name' and 'ref'", elem)
                return
            elif ref is None:
                # Global group
                self.name = get_qname(self.target_namespace, name)
                content_model = self._parse_component(elem)
                if not self.is_global:
                    self._parse_error("attribute 'name' not allowed for a local group", self)
                else:
                    if 'minOccurs' in elem.attrib:
                        self._parse_error(
                            "attribute 'minOccurs' not allowed for a global group", self
                        )
                    if 'maxOccurs' in elem.attrib:
                        self._parse_error(
                            "attribute 'maxOccurs' not allowed for a global group", self
                        )
                if content_model.tag not in {XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
                    self._parse_error('unexpected tag %r' % content_model.tag, content_model)
                    return
            else:
                self._parse_error("found both attributes 'name' and 'ref'", elem)
                return
        elif elem.tag in {XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
            # Local group (sequence|all|choice)
            content_model = elem
            self.name = None
        elif elem.tag in {XSD_COMPLEX_TYPE_TAG, XSD_EXTENSION_TAG, XSD_RESTRICTION_TAG}:
            self.name = self.model = None
            return
        else:
            self._parse_error('unexpected tag %r' % elem.tag, elem)
            return

        self.model = content_model.tag
        for child in self._iterparse_components(content_model):
            if child.tag == XSD_ELEMENT_TAG:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif content_model.tag == XSD_ALL_TAG:
                self._parse_error("'all' model can contains only elements.", elem)
            elif child.tag == XSD_ANY_TAG:
                self.append(XsdAnyElement(child, self.schema))
            elif child.tag in (XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
                self.append(XsdGroup(child, self.schema, mixed=self.mixed))
            elif child.tag == XSD_GROUP_TAG:
                xsd_group = XsdGroup(child, self.schema, mixed=self.mixed)
                if xsd_group.name != self.name:
                    self.append(xsd_group)
                elif not hasattr(self, '_elem'):
                    self._parse_error("Circular definitions detected for group %r:" % self.ref, elem)
            else:
                raise XMLSchemaParseError("unexpected element:", elem=elem)

    @property
    def built(self):
        for item in self:
            try:
                if not item.ref and not item.built:
                    return False
            except AttributeError:
                if isinstance(item, tuple):
                    return False
                elif isinstance(item, XsdAnyElement):
                    if not item.built:
                        return False
                else:
                    raise
        return True

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any([item.validation_attempted == 'partial' for item in self]):
            return 'partial'
        else:
            return 'none'

    @property
    def admitted_tags(self):
        return {XSD_COMPLEX_TYPE_TAG, XSD_EXTENSION_TAG, XSD_RESTRICTION_TAG,
                XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for item in self:
            if not item.is_global:
                for obj in item.iter_components(xsd_classes):
                    yield obj

    def clear(self):
        del self._group[:]

    def is_empty(self):
        return not self.mixed and not self

    def is_emptiable(self):
        if self.model == XSD_CHOICE_TAG:
            return self.min_occurs == 0 or not self or any([item.is_emptiable() for item in self])
        else:
            return self.min_occurs == 0 or not self or all([item.is_emptiable() for item in self])

    def is_meaningless(self, parent_group):
        """
        A group that may be eliminated. A group is meaningless if one of those conditions is verified:

         - the group is empty
         - minOccurs == maxOccurs == 1 and the group has one child
         - minOccurs == maxOccurs == 1 and the group and its parent have a sequence model
         - minOccurs == maxOccurs == 1 and the group and its parent have a choice model
        """
        if not self:
            return True
        elif self.min_occurs != 1 or self.max_occurs != 1:
            return False
        elif len(self) == 1:
            return True
        elif self.model == XSD_SEQUENCE_TAG and parent_group.model != XSD_SEQUENCE_TAG:
            return False
        elif self.model == XSD_CHOICE_TAG and parent_group.model != XSD_CHOICE_TAG:
            return False
        else:
            return True

    def is_restriction(self, other, check_particle=True):
        if not isinstance(other, XsdGroup):
            return False
        elif not self:
            return True
        elif not other:
            return False
        elif other.model == XSD_SEQUENCE_TAG and self.model != XSD_SEQUENCE_TAG:
            return False
        elif other.model == XSD_CHOICE_TAG and self.model == XSD_ALL_TAG:
            return False
        elif other.model == XSD_ALL_TAG and self.model == XSD_CHOICE_TAG:
            return False
        elif check_particle and not super(XsdGroup, self).is_restriction(other):
            return False

        other_iterator = iter(other.iter_group())
        for item in self.iter_group():
            while True:
                try:
                    other_item = next(other_iterator)
                except StopIteration:
                    return False

                if other_item is item:
                    break
                elif item.is_restriction(other_item):
                    break
                elif other.model == XSD_CHOICE_TAG:
                    continue
                elif other_item.is_optional():
                    continue
                elif isinstance(other_item, XsdGroup) and other_item.model == XSD_CHOICE_TAG and \
                        other_item.max_occurs == 1:
                    if any(item.is_restriction(s) for s in other_item.iter_group()):
                        break
                else:
                    return False

        return True

    def iter_group(self):
        for item in self:
            if not isinstance(item, XsdGroup):
                yield item
            elif item.is_global or not item.is_meaningless(self):
                yield item
            else:
                for obj in item.iter_group():
                    yield obj

    def iter_elements(self):
        for item in self:
            if isinstance(item, XsdGroup):
                for e in item.iter_elements():
                    yield e
            else:
                yield item
                for e in self.schema.substitution_groups.get(item.name, ()):
                    yield e

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Creates an iterator for decoding an Element content.

        :param elem: The Element that has to be decoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: Keyword arguments for the decoding process.
        :return: Yields a list of 3-tuples (key, decoded data, decoder), eventually \
        preceded by a sequence of validation or decoding errors.
        """
        def not_whitespace(s):
            return s is not None and s.strip()

        result_list = []
        cdata_index = 1  # keys for CDATA sections are positive integers
        if validation != 'skip' and not self.mixed:
            # Validate character data between tags
            if not_whitespace(elem.text) or any([not_whitespace(child.tail) for child in elem]):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] is equivalent to an empty complexType declaration
                elif validation != 'skip':
                    if validation == 'lax':
                        cdata_index = 0
                    cdata_msg = "character data between child elements not allowed!"
                    yield self._validation_error(cdata_msg, validation, obj=elem)

        if cdata_index and elem.text is not None:
            text = unicode_type(elem.text.strip())
            if text:
                result_list.append((cdata_index, text, None))
                cdata_index += 1

        if len(elem):
            child, obj = None, 0
            for obj in self.iter_decode_children(elem, validation):
                if isinstance(obj, tuple):
                    xsd_element, child = obj
                    if xsd_element is not None:
                        for result in xsd_element.iter_decode(child, validation, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield self._validation_error(result, validation)
                            else:
                                result_list.append((child.tag, result, xsd_element))
                        if cdata_index and child.tail is not None:
                            tail = unicode_type(child.tail.strip())
                            if tail:
                                result_list.append((cdata_index, tail, None))
                                cdata_index += 1
                elif isinstance(obj, int):
                    break
                elif isinstance(obj, XMLSchemaChildrenValidationError):
                    yield self._validation_error(obj, validation)
                    try:
                        child = elem[obj.index]
                    except IndexError:
                        pass  # Missing child node at the end
                else:
                    raise XMLSchemaTypeError("wrong type %r from children decoding: %r" % (type(obj), obj))
            else:
                assert isinstance(obj, int), "children decoding must ends with an index."

            # Unvalidated residual content, lxml comments excluded: model broken, perform a raw decoding.
            if child is not etree_last_child(elem):
                index = 0 if child is None else etree_child_index(elem, child) + 1
                if validation != 'skip' and self:
                    error = XMLSchemaChildrenValidationError(self, elem, index)
                    yield self._validation_error(error, validation)

                # raw children decoding
                for child_index, child in enumerate(elem[index:]):
                    for xsd_element in self.iter_elements():
                        if xsd_element.match(child.tag):
                            for result in xsd_element.iter_decode(child, validation, **kwargs):
                                if isinstance(result, XMLSchemaValidationError):
                                    yield self._validation_error(result, validation)
                                else:
                                    result_list.append((child.tag, result, xsd_element))
                            if cdata_index and child.tail is not None:
                                tail = unicode_type(child.tail.strip())
                                if tail:
                                    result_list.append((cdata_index, tail, None))
                                    cdata_index += 1
                            break
                    else:
                        if validation == 'skip':
                            pass  # TODO? try to use a "default decoder"?
                        elif self and child_index > index:
                            error = XMLSchemaChildrenValidationError(self, elem, child_index)
                            yield self._validation_error(error, validation)

        elif validation != 'skip' and not self.is_emptiable():
            # no child elements: generate errors if the model is not emptiable
            expected = [e.prefixed_name for e in self.iter_elements() if e.min_occurs]
            error = XMLSchemaChildrenValidationError(self, elem, 0, expected=expected)
            yield self._validation_error(error, validation)

        yield result_list

    def iter_decode_children(self, elem, validation='lax', index=0):
        """
        Creates an iterator for decoding the children of an element. Before ending the
        generator yields the last index used by inner validators.

        :param elem: The parent Element.
        :param index: Start child index, 0 for default.
        :param validation: Validation mode that can be 'strict', 'lax' or 'skip'.
        :return: Yields a sequence of values that can be tuples and/or \
        `XMLSchemaChildrenValidationError` errors and an integer at the end.
        """
        if not len(self):
            return  # Skip empty groups!

        model_occurs = 0
        max_occurs = self.max_occurs
        model = self.model
        while index < len(elem) and (not max_occurs or model_occurs < max_occurs):
            child_index = index

            if model == XSD_SEQUENCE_TAG:
                for item in self.iter_group():
                    for obj in item.iter_decode_children(elem, validation, child_index):
                        if isinstance(obj, tuple):
                            yield obj
                        elif isinstance(obj, int):
                            child_index = obj
                            break
                        else:
                            assert isinstance(obj, XMLSchemaChildrenValidationError)
                            if self.min_occurs > model_occurs:
                                yield obj
                            yield index

            elif model == XSD_ALL_TAG:
                elements = [e for e in self]
                while elements:
                    for item in elements:
                        for obj in item.iter_decode_children(elem, 'lax', child_index):
                            if isinstance(obj, tuple):
                                yield obj
                            elif isinstance(obj, int) and child_index < obj:
                                child_index = obj
                                break
                        else:
                            continue
                        break
                    else:
                        if any(not e.is_optional() for e in elements) and self.min_occurs > model_occurs:
                            expected = [e.prefixed_name for e in elements]
                            yield XMLSchemaChildrenValidationError(self, elem, child_index, expected)
                        yield child_index
                        return
                    elements.remove(item)

            elif model == XSD_CHOICE_TAG:
                matched_choice = False
                obj = None
                for item in self.iter_group():
                    for obj in item.iter_decode_children(elem, 'lax', child_index):
                        if isinstance(obj, tuple):
                            yield obj
                            continue
                        elif isinstance(obj, int) and child_index < obj:
                            child_index = obj
                            matched_choice = True
                        break
                    if matched_choice:
                        break
                else:
                    try:
                        if isinstance(obj.validator, XsdAnyElement):
                            yield obj
                    except AttributeError:
                        pass

                    if self.min_occurs > model_occurs:
                        expected = [e.prefixed_name for e in self.iter_elements()]
                        yield XMLSchemaChildrenValidationError(self, elem, child_index, expected)
                    yield index
                    return
            else:
                raise XMLSchemaValueError("the group %r has no model!" % self)

            model_occurs += 1
            index = child_index

        yield index

    def iter_encode(self, obj, validation='lax', **kwargs):
        """
        Creates an iterator for encoding data to a list containing Element data.

        :param obj: The data that has to be encoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: Keyword arguments for the encoding process.
        :return: Yields a couple with the text of the Element and a list of 3-tuples \
        (key, decoded data, decoder), eventually preceded by a sequence of validation \
        or encoding errors.
        """
        if obj is None:
            yield None
            return

        children = []
        level = kwargs.get('level', 0)
        indent = kwargs.get('indent', 4)
        padding = u'\n' + u' ' * indent * level

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        text = ''
        for name, value in obj:
            if isinstance(name, int):
                if children:
                    if children[-1].tail is None:
                        children[-1].tail = padding + value
                    else:
                        children[-1].tail += padding + value
                else:
                    text += padding + value
            else:
                for xsd_element in self.iter_elements():
                    if isinstance(xsd_element, XsdAnyElement):
                        namespace = get_namespace(name) or converter.get('', '')
                        if xsd_element.is_namespace_allowed(namespace):
                            if name[0] != '{' and namespace:
                                name = '{%s}%s' % (namespace, name)
                            for result in xsd_element.iter_encode((name, value), validation, **kwargs):
                                if isinstance(result, XMLSchemaValidationError):
                                    yield result
                                else:
                                    children.append(result)
                            break
                    elif xsd_element.match(name, converter.get('')):
                        for result in xsd_element.iter_encode(value, validation, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield result
                            else:
                                children.append(result)
                        break
                else:
                    if validation != 'skip':
                        yield self._validation_error(
                            '%r does not match any declared element.' % name, validation, obj=value
                        )

        if children:
            if children[-1].tail is None:
                children[-1].tail = padding[:-indent] or '\n'
            else:
                children[-1].tail = children[-1].tail.strip() + (padding[:-indent] or '\n')

        yield text or None, children


class Xsd11Group(XsdGroup):
    """
    A class for XSD 'group', 'choice', 'sequence' definitions and 
    XSD 1.1 'all' definitions.

    <all
      id = ID
      maxOccurs = (0 | 1) : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | any | group)*)
    </all>
    """
    pass
