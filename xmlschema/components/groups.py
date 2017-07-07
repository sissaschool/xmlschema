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
This module contains classes for XML Schema elements, complex types and model groups.
"""
from collections import MutableSequence

from ..core import unicode_type
from ..exceptions import (
    XMLSchemaValidationError, XMLSchemaParseError, XMLSchemaValueError,
    XMLSchemaEncodeError, XMLSchemaNotBuiltError, XMLSchemaTypeError
)
from ..qnames import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, reference_to_qname, get_qname,
    XSD_COMPLEX_TYPE_TAG, XSD_ELEMENT_TAG, XSD_ANY_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
    local_name, qname_to_prefixed
)
from ..utils import check_type, check_value, listify_update
from ..xsdbase import ValidatorMixin
from ..components import XsdAnnotated, ParticleMixin
from .wildcards import XsdAnyElement

XSD_MODEL_GROUP_TAGS = {XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}


class XsdGroup(MutableSequence, XsdAnnotated, ValidatorMixin, ParticleMixin):
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
        XsdAnnotated.__init__(self, elem, schema, name, is_global)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        check_type(item, ParticleMixin)
        self._group[i] = item

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        check_type(item, tuple, ParticleMixin)
        self._group.insert(i, item)

    def __repr__(self):
        return XsdAnnotated.__repr__(self)

    def __setattr__(self, name, value):
        if name == 'model':
            check_value(value, None, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG)
            model = getattr(self, 'model', None)
            if model is not None and value != model:
                raise XMLSchemaValueError("cannot change a valid group model: %r" % value)
        elif name == 'mixed':
            check_value(value, True, False)
        elif name == '_group':
            check_type(value, list)
            for item in value:
                check_type(item, ParticleMixin)
        super(XsdGroup, self).__setattr__(name, value)

    def _parse(self):
        super(XsdGroup, self)._parse()
        self._parse_particle()

        elem = self.elem
        self.clear()
        if elem.tag == XSD_GROUP_TAG:
            # Global group (group)
            name = elem.get('name')
            ref = elem.get('ref')
            if name is None:
                if ref is not None:
                    # Reference to a global group
                    group_name = reference_to_qname(ref, self.namespaces)
                    xsd_group = self.maps.lookup_group(group_name)
                    self.name = xsd_group.name
                    self.model = xsd_group.model
                    self.extend(xsd_group)
                    if self.is_global:
                        self._parse_error("a group reference cannot be global", elem)
                else:
                    self._parse_error("missing both attributes 'name' and 'ref'", elem)
                return
            elif ref is None:
                # Global group
                self.name = get_qname(self.target_namespace, name)
                content_model = self._parse_component(elem)
                if not self.is_global:
                    self._parse_error(
                        "attribute 'name' not allowed for a local group", self
                    )
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
                # Builds inner elements at the end for avoids circularity
                self.append((child, self.schema))
            elif content_model.tag == XSD_ALL_TAG:
                self._parse_error("'all' model can contains only elements.", elem)
            elif child.tag == XSD_ANY_TAG:
                self.append(XsdAnyElement(child, self.schema))
            elif child.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
                self.append(XsdGroup(child, self.schema, mixed=self.mixed))
            else:
                raise XMLSchemaParseError("unexpected element:", elem)

    @property
    def built(self):
        for item in self:
            try:
                if not item.is_global and not item.built:
                    return False
            except AttributeError:
                if isinstance(item, tuple):
                    return False
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

    @property
    def ref(self):
        return self.elem.get('ref')

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for item in self:
            try:
                if not item.is_global:
                    for obj in item.iter_components(xsd_classes):
                        yield obj
            except AttributeError:
                if isinstance(item, tuple):
                    raise XMLSchemaNotBuiltError(self)
                raise

    def clear(self):
        del self._group[:]

    def is_empty(self):
        return not self.mixed and not self

    def is_emptiable(self):
        return not self or all([item.is_emptiable() for item in self])

    def iter_elements(self):
        for item in self:
            if isinstance(item, (self.BUILDERS.element_class, XsdAnyElement)):
                yield item
            elif isinstance(item, XsdGroup):
                for e in item.iter_elements():
                    yield e

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Generator method for decoding complex content elements. A list of 3-tuples
        (key, decoded data, decoder) is returned, eventually preceded by a sequence
        of validation/decode errors.
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
                else:
                    if validation == 'lax':
                        cdata_index = 0
                    cdata_msg = "character data between child elements not allowed!"
                    yield XMLSchemaValidationError(self, elem, cdata_msg)

        if cdata_index and elem.text is not None:
            text = unicode_type(elem.text.strip())
            if text:
                result_list.append((cdata_index, text, None))
                cdata_index += 1

        # Decode child elements
        index = 0
        while index < len(elem):
            obj = index
            for obj in self.iter_decode_children(elem, index=index):
                if isinstance(obj, XMLSchemaValidationError):
                    yield obj
                elif isinstance(obj, tuple):
                    xsd_element, child = obj
                    for result in xsd_element.iter_decode(child, validation, **kwargs):
                        if isinstance(result, XMLSchemaValidationError):
                            yield result
                        else:
                            result_list.append((child.tag, result, xsd_element))
                    if cdata_index and elem.tail is not None:
                        tail = unicode_type(elem.tail.strip())
                        if tail:
                            result_list.append((cdata_index, tail, None))
                            cdata_index += 1
                elif obj < index:
                    raise XMLSchemaValueError("returned a lesser index, this is a bug!")
                else:
                    index = obj + 1
                    break
            else:
                if isinstance(obj, XMLSchemaValidationError):
                    raise XMLSchemaTypeError(
                        "the iteration cannot ends with a validation error, an integer expected.")
                break
        yield result_list

    def iter_encode(self, data, validation='lax', **kwargs):
        children = []
        children_map = {}
        level = kwargs.get('level', 0)
        indent = kwargs.get('indent', None)
        padding = (u'\n' + u' ' * indent * level) if indent is not None else None
        text = padding
        listify_update(children_map, [(e.name, e) for e in self.iter_elements()])
        if self.target_namespace:
            listify_update(children_map, [(local_name(e.name), e) for e in self.iter_elements() if not e.qualified])

        try:
            for name, value in data:
                if isinstance(name, int):
                    if children:
                        children[-1].tail = padding + value + padding
                    else:
                        text = padding + value + padding
                else:
                    try:
                        xsd_element = children_map[name]
                    except KeyError:
                        yield XMLSchemaValidationError(
                            self, obj=value, reason='%r does not match any declared element.' % name
                        )
                    else:
                        for result in xsd_element.iter_encode(value, validation, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield result
                            else:
                                children.append(result)
        except ValueError:
            yield XMLSchemaEncodeError(
                self,
                obj=data,
                encoder=self,
                reason='%r does not match content.' % data
            )

        if indent and level:
            if children:
                children[-1].tail = children[-1].tail[:-indent]
            else:
                text = text[:-indent]
        yield text, children

    def iter_decode_children(self, elem, index=0):
        if not len(self):
            return  # Skip empty groups!

        model_occurs = 0
        while index < len(elem):
            model_index = index
            if self.model == XSD_SEQUENCE_TAG:
                for item in self:
                    for obj in item.iter_decode_children(elem, model_index):
                        if isinstance(obj, XMLSchemaValidationError):
                            if self.min_occurs > model_occurs:
                                yield obj
                            yield index
                            return
                        elif isinstance(obj, tuple):
                            yield obj
                        else:
                            model_index = obj

            elif self.model == XSD_ALL_TAG:
                group = [e for e in self]
                while group:
                    for item in group:
                        for obj in item.iter_decode_children(elem, model_index):
                            if isinstance(obj, tuple):
                                yield obj
                            elif isinstance(obj, int):
                                model_index = obj
                                break
                        else:
                            continue
                        break
                    else:
                        if self.min_occurs > model_occurs:
                            yield XMLSchemaValidationError(
                                self, elem,
                                reason="child n.%d has a unexpected tag %r, must be one of %r." % (
                                    index + 1,
                                    qname_to_prefixed(elem[model_index].tag, self.namespaces),
                                    [qname_to_prefixed(e.name, self.namespaces) for e in group]
                                ))
                        yield index
                        return
                    group.remove(item)

            elif self.model == XSD_CHOICE_TAG:
                matched_choice = False
                for item in self:
                    for obj in item.iter_decode_children(elem, model_index):
                        if not isinstance(obj, XMLSchemaValidationError):
                            if isinstance(obj, tuple):
                                yield obj
                                continue
                            if model_index < obj:
                                matched_choice = True
                                model_index = obj
                        break
                    if matched_choice:
                        break
                else:
                    if self.min_occurs > model_occurs:
                        yield XMLSchemaValidationError(
                            self, elem,
                            reason="child n.%d has a unexpected tag %r, must be one of %r." % (
                                index + 1,
                                qname_to_prefixed(elem[model_index].tag, self.namespaces),
                                [qname_to_prefixed(e.name, self.namespaces) for e in self.iter_elements()]
                            ))
                    yield index
                    return
            else:
                raise XMLSchemaValueError("the group %r has no model!" % self)

            model_occurs += 1
            index = model_index
            if self.max_occurs is not None and model_occurs >= self.max_occurs:
                yield index
                return
        else:
            yield index


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
