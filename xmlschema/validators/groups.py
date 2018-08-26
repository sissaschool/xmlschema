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
from collections import MutableSequence, Counter

from ..compat import PY3, unicode_type
from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..etree import etree_last_child, etree_child_index, etree_element
from ..qnames import local_name
from ..qnames import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, reference_to_qname, get_qname,
    XSD_COMPLEX_TYPE_TAG, XSD_ELEMENT_TAG, XSD_ANY_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
)
from ..converters import XMLSchemaConverter

from .exceptions import XMLSchemaValidationError, XMLSchemaChildrenValidationError
from .xsdbase import ValidationMixin, XsdComponent, ParticleMixin
from .wildcards import XsdAnyElement

XSD_GROUP_MODELS = {'sequence', 'choice', 'all'}

ANY_ELEMENT = etree_element(
    XSD_ANY_TAG,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


def iter_elements(items):
    for item in items:
        if isinstance(item, XsdGroup):
            for e in item.iter_elements():
                yield e
        else:
            yield item
            for e in item.schema.substitution_groups.get(item.name, ()):
                yield e


class XsdModelVisitor(object):
    """
    A visitor design pattern class that can be used for validating XML data related to an
    XSD model group. The visit of the model is done using an external match information,
    counting the occurrences and yielding tuples in case of model's item occurrence errors.
    Ends setting the current element to `None`.

    :param root: the root XsdGroup instance of the model.
    :ivar element: the current XSD element, initialized to the first element of the model.
    :ivar group: the current XSD group, initialized to *root* argument.
    :ivar iterator: the current XSD group iterator.
    :ivar expected: the current XSD group expected items.
    :ivar match: if the XSD group has an effective item match.
    :ivar occurs: a Counter instance for occurrences of model elements and groups.
    :ivar: ancestors: the stack of statuses of current group's ancestors.
    """
    def __init__(self, root, start=True):
        self.root = root
        self.group = self.iterator = self.expected = self.match = self.element = None
        self.occurs = Counter()
        self.ancestors = []
        if start:
            self.start()

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def __repr__(self):
        return u'%s(root=%r)' % (self.__class__.__name__, self.root)

    def start(self):
        self.group = self.root
        self.iterator = iter(self.root)
        self.expected = self.root[:]
        self.match = False
        self.occurs.clear()
        del self.ancestors[:]

        while True:
            item = next(self.iterator, None)
            if item is None or not isinstance(item, XsdGroup):
                self.element = item
                break
            elif item:
                self.ancestors.append((self.group, self.iterator, self.expected, False))
                self.group, self.iterator, self.expected = item, iter(item), item[:]

    def stop(self):
        while self.element is not None:
            for e in self.advance():
                yield e

    def advance(self, match=False):
        """
        Generator function for advance to the next element. Yields tuples with
        particles information when occurrence violation is found.

        :param match: provides current element match.
        """
        element, occurs = self.element, self.occurs
        if element is None:
            raise XMLSchemaValueError("cannot advance, %r is ended!" % self)

        if match:
            occurs[element] += 1
            self.match = True
            if not element.is_over(occurs[element]):
                return
        try:
            if self.stop_item(element):
                yield element, occurs[element], [element]

            while True:
                while self.group.is_over(occurs[self.group]):
                    group = self.group
                    self.group, self.iterator, self.expected, self.match = self.ancestors.pop()
                    self.stop_item(group)

                item = next(self.iterator, None)
                if item is None:
                    if self.match:
                        if not self.expected:
                            self.iterator, self.expected, self.match = iter(self.group), self.group[:], False
                            continue
                        elif self.group.model == 'all':
                            self.match = False
                            self.iterator = iter(self.expected)
                            continue
                        elif all(e.min_occurs == 0 for e in self.expected):
                            self.iterator, self.expected, self.match = iter(self.group), self.group[:], False
                            occurs[self.group] += 1
                            continue
                    elif self.group.model == 'all' and all(e.min_occurs == 0 for e in self.expected):
                        occurs[self.group] += 1

                    group, expected = self.group, self.expected
                    self.group, self.iterator, self.expected, self.match = self.ancestors.pop()
                    if self.stop_item(group):
                        yield group, occurs[group], list(iter_elements(expected))

                elif not isinstance(item, XsdGroup):  # XsdElement or XsdAnyElement
                    self.element, occurs[item] = item, 0
                    return

                elif item:
                    self.ancestors.append((self.group, self.iterator, self.expected, self.match))
                    self.group, self.iterator, self.expected, self.match = item, iter(item), item[:], False
                    occurs[item] = 0

        except IndexError:
            self.element = None
            if self.group.is_missing(occurs[self.group]):
                yield self.group, occurs[self.group], list(iter_elements(self.expected))

    def stop_item(self, item):
        """
        Stops item match, incrementing current group counter and reporting if the item
        has violated the minimum occurrences.

        :param item: an XsdElement or an XsdAnyElement or an XsdGroup.
        :return: `True` if the item violates the minimum occurrences, `False` otherwise.
        """
        occurs = self.occurs
        if occurs[item]:
            occurs_error = item.is_missing(occurs[item])
            self.match = True
            if self.group.model == 'choice':
                occurs[item] = 0
                occurs[self.group] += 1
                self.iterator, self.match = iter(self.group), False
            else:
                self.expected.remove(item)
                if not self.expected:
                    occurs[self.group] += 1
            return occurs_error

        elif self.group.model == 'sequence':
            if self.match or item.is_emptiable():
                self.expected.remove(item)
                if self.match and not self.expected:
                    occurs[self.group] += 1
                return not item.is_emptiable()
            elif self.group.min_occurs <= occurs[self.group]:
                self.group, self.iterator, self.expected, self.match = self.ancestors.pop()
            elif self.ancestors and self.ancestors[-1][0].model == 'choice':
                self.group, self.iterator, self.expected, self.match = self.ancestors.pop()
            else:
                return True

        return False


class XsdGroup(MutableSequence, XsdComponent, ValidationMixin, ParticleMixin):
    """
    A class for XSD 1.0 model group definitions.

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
    admitted_tags = {
        XSD_COMPLEX_TYPE_TAG, XSD_EXTENSION_TAG, XSD_RESTRICTION_TAG,
        XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG
    }

    def __init__(self, elem, schema, parent, name=None, initlist=None):
        self.mixed = False if parent is None else parent.mixed
        self.model = None
        self._group = []
        if initlist is not None:
            if isinstance(initlist, type(self._group)):
                self._group[:] = initlist
            elif isinstance(initlist, XsdGroup):
                self._group[:] = initlist._group[:]
            else:
                self._group = list(initlist)
        XsdComponent.__init__(self, elem, schema, parent, name)

    def __repr__(self):
        if self.name is None:
            return u'%s(model=%r, occurs=%r)' % (self.__class__.__name__, self.model, self.occurs)
        elif self.ref is None:
            return u'%s(name=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, self.occurs
            )
        else:
            return u'%s(ref=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, self.occurs
            )

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
        if name == 'model' and value is not None:
            if value not in XSD_GROUP_MODELS:
                raise XMLSchemaValueError("invalid model group %r." % value)
            if self.model is not None and value != self.model:
                raise XMLSchemaValueError("cannot change a valid group model: %r" % value)
        elif name == '_group':
            if not all(isinstance(item, (tuple, ParticleMixin)) for item in value):
                raise XMLSchemaValueError("XsdGroup's items must be tuples or ParticleMixin instances.")
        super(XsdGroup, self).__setattr__(name, value)

    def _parse(self):
        super(XsdGroup, self)._parse()
        if self and not hasattr(self, '_elem'):
            self.clear()
        elem = self.elem
        self._parse_particle(elem)

        if elem.tag == XSD_GROUP_TAG:
            # Global group (group)
            name = elem.get('name')
            ref = elem.get('ref')
            if name is None:
                if ref is not None:
                    # Reference to a global group
                    if self.is_global:
                        self.parse_error("a group reference cannot be global", elem)
                    self.name = reference_to_qname(ref, self.namespaces)

                    try:
                        xsd_group = self.schema.maps.lookup_group(self.name)
                    except KeyError:
                        self.parse_error("missing group %r" % self.prefixed_name, elem)
                        xsd_group = self.schema.create_any_content_group(self, self.name)

                    if isinstance(xsd_group, tuple):
                        # Disallowed circular definition, substitute with any content group.
                        self.parse_error("Circular definitions detected for group %r:" % self.ref, xsd_group[0])
                        self.model = 'sequence'
                        self.mixed = True
                        self.append(XsdAnyElement(ANY_ELEMENT, self.schema, self))
                    else:
                        self.model = xsd_group.model
                        self.append(xsd_group)
                else:
                    self.parse_error("missing both attributes 'name' and 'ref'", elem)
                return
            elif ref is None:
                # Global group
                self.name = get_qname(self.target_namespace, name)
                content_model = self._parse_component(elem)
                if not self.is_global:
                    self.parse_error("attribute 'name' not allowed for a local group", self)
                else:
                    if 'minOccurs' in elem.attrib:
                        self.parse_error(
                            "attribute 'minOccurs' not allowed for a global group", self
                        )
                    if 'maxOccurs' in elem.attrib:
                        self.parse_error(
                            "attribute 'maxOccurs' not allowed for a global group", self
                        )
                if content_model.tag not in {XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
                    self.parse_error('unexpected tag %r' % content_model.tag, content_model)
                    return
            else:
                self.parse_error("found both attributes 'name' and 'ref'", elem)
                return
        elif elem.tag in {XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
            # Local group (sequence|all|choice)
            content_model = elem
            self.name = None
        elif elem.tag in {XSD_COMPLEX_TYPE_TAG, XSD_EXTENSION_TAG, XSD_RESTRICTION_TAG}:
            self.name = self.model = None
            return
        else:
            self.parse_error('unexpected tag %r' % elem.tag, elem)
            return

        self._parse_content_model(elem, content_model)

    def _parse_content_model(self, elem, content_model):
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs != 1:
                self.parse_error("maxOccurs must be 1 for 'all' model groups")
            if self.min_occurs not in (0, 1):
                self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")

        for child in self._iterparse_components(content_model):
            if child.tag == XSD_ELEMENT_TAG:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif content_model.tag == XSD_ALL_TAG:
                self.parse_error("'all' model can contains only elements.", elem)
            elif child.tag == XSD_ANY_TAG:
                self.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
                self.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP_TAG:
                xsd_group = XsdGroup(child, self.schema, self)
                if xsd_group.name != self.name:
                    self.append(xsd_group)
                elif not hasattr(self, '_elem'):
                    self.parse_error("Circular definitions detected for group %r:" % self.ref, elem)
            else:
                continue  # Error already caught by validation against the meta-schema

    @property
    def schema_elem(self):
        return self.elem if self.name else self.parent.elem

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
    def ref(self):
        return self.elem.get('ref')

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
        if self.model == 'choice':
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
        elif self.model == 'sequence' and parent_group.model != 'sequence':
            return False
        elif self.model == 'choice' and parent_group.model != 'choice':
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
        elif other.model == 'sequence' and self.model != 'sequence':
            return False
        elif other.model == 'choice' and self.model == 'all':
            return False
        elif other.model == 'all' and self.model == 'choice':
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
                elif other.model == 'choice':
                    continue
                elif other_item.is_emptiable():
                    continue
                elif isinstance(other_item, XsdGroup) and other_item.model == 'choice' and \
                        other_item.max_occurs == 1:
                    if any(item.is_restriction(s) for s in other_item.iter_group()):
                        break
                else:
                    return False

        return True

    def iter_group(self):
        """Creates an iterator for sub elements and groups. Skips meaningless groups."""
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

    def sort_children(self, elements, default_namespace=None):
        """
        Sort elements by group order, that maybe partial in case of 'all' or 'choice' ordering.
        The not matching elements are appended at the end.
        """
        def sorter(elem):
            for e in elements_order:
                if e.match(elem.tag, default_namespace):
                    return elements_order[e]
            return len(elements_order)

        elements_order = {e: p for p, e in enumerate(self.iter_elements())}
        return sorted(elements, key=sorter)

    def iter_decode(self, elem, validation='lax', converter=None, **kwargs):
        """
        Creates an iterator for decoding an Element content.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a list of 3-tuples (key, decoded data, decoder), eventually \
        preceded by a sequence of validation or decoding errors.
        """
        def not_whitespace(s):
            return s is not None and s.strip()

        result_list = []
        cdata_index = 1  # keys for CDATA sections are positive integers

        if validation != 'skip' and not self.mixed:
            # Check element CDATA
            if not_whitespace(elem.text) or any([not_whitespace(child.tail) for child in elem]):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] is equivalent to an empty complexType declaration
                else:
                    reason = "character data between child elements not allowed!"
                    yield self.validation_error(validation, reason, elem, **kwargs)
                    cdata_index = 0  # Do not decode CDATA

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
                        for result in xsd_element.iter_decode(child, validation, converter, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield result
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
                    yield obj
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
                    yield self.children_validation_error(validation, elem, index, **kwargs)

                # raw children decoding
                for child_index, child in enumerate(elem[index:]):
                    for xsd_element in self.iter_elements():
                        if xsd_element.match(child.tag):
                            for result in xsd_element.iter_decode(child, validation, converter, **kwargs):
                                if isinstance(result, XMLSchemaValidationError):
                                    yield result
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
                            yield self.children_validation_error(validation, elem, index, **kwargs)

        elif validation != 'skip' and not self.is_emptiable():
            # no child elements: generate errors if the model is not emptiable
            expected = [e for e in self.iter_elements() if e.min_occurs]
            yield self.children_validation_error(validation, elem, 0, expected, **kwargs)

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

            if model == 'sequence':
                for item in self.iter_group():
                    for obj in item.iter_decode_children(elem, validation, child_index):
                        if isinstance(obj, tuple):
                            yield obj
                        elif isinstance(obj, int):
                            child_index = obj
                            break
                        else:
                            assert isinstance(obj, XMLSchemaChildrenValidationError), \
                                "%r is not an XMLSchemaChildrenValidationError." % obj
                            if self.min_occurs > model_occurs:
                                yield obj
                            yield index

            elif model == 'all':
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
                        if any(not e.is_emptiable() for e in elements) and self.min_occurs > model_occurs:
                            yield XMLSchemaChildrenValidationError(self, elem, child_index, elements)
                        yield child_index
                        return
                    elements.remove(item)

            elif model == 'choice':
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
                        yield XMLSchemaChildrenValidationError(self, elem, child_index, list(self.iter_elements()))
                    yield index
                    return
            else:
                raise XMLSchemaValueError("the group %r has no model!" % self)

            model_occurs += 1
            index = child_index

        yield index

    def iter_encode(self, element_data, validation='lax', converter=None, **kwargs):
        """
        Creates an iterator for encoding data to a list containing Element data.

        :param element_data: an ElementData instance with unencoded data.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: Keyword arguments for the encoding process.
        :return: Yields a couple with the text of the Element and a list of 3-tuples \
        (key, decoded data, decoder), eventually preceded by a sequence of validation \
        or encoding errors.
        """
        if not element_data.content:  # <tag/> or <tag></tag>
            yield element_data.content
            return

        if not isinstance(converter, XMLSchemaConverter):
            converter = self.schema.get_converter(converter, **kwargs)

        errors = []
        text = None
        children = []
        level = kwargs.get('level', 0)
        indent = kwargs.get('indent', 4)
        padding = u'\n' + u' ' * indent * level
        default_namespace = converter.get('')
        losslessly = converter.losslessly

        model = XsdModelVisitor(self)
        cdata_index = 0

        for position, (name, value) in enumerate(element_data.content):
            if isinstance(name, int):
                if not children:
                    text = padding + value if text is None else text + value + padding
                elif children[-1].tail is None:
                    children[-1].tail = padding + value
                else:
                    children[-1].tail += value + padding
                cdata_index += 1
                continue

            while model.element is not None:
                if model.element.match(name, default_namespace):
                    xsd_element = model.element
                else:
                    for xsd_element in self.schema.substitution_groups.get(model.element.name, ()):
                        if xsd_element.match(name, default_namespace):
                            break
                    else:
                        for validator, occurs, expected in model.advance():
                            errors.append((validator, occurs, expected, position - cdata_index))
                        continue

                if isinstance(xsd_element, XsdAnyElement):
                    value = get_qname(default_namespace, name), value
                for result in xsd_element.iter_encode(value, validation, converter, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        children.append(result)

                for validator, occurs, expected in model.advance(True):
                    errors.append((validator, occurs, expected, position - cdata_index))
                break
            else:
                if losslessly:
                    errors.append((self, 0, [], position - cdata_index))

                for xsd_element in self.iter_elements():
                    if xsd_element.match(name, default_namespace):
                        if isinstance(xsd_element, XsdAnyElement):
                            value = get_qname(default_namespace, name), value
                        for result in xsd_element.iter_encode(value, validation, converter, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield result
                            else:
                                children.append(result)
                        break
                else:
                    if validation != 'skip':
                        reason = '%r does not match any declared element of the model group.' % name
                        yield self.validation_error(validation, reason, value, **kwargs)

        if model.element is not None:
            index = len(element_data.content) - cdata_index
            for validator, occurs, expected in model.stop():
                errors.append((validator, occurs, expected, index))

        # If the validation is not strict tries to solve model errors with a reorder of the children
        if errors and validation != 'strict':
            children = self.sort_children(children, default_namespace)

        if children:
            if children[-1].tail is None:
                children[-1].tail = padding[:-indent] or '\n'
            else:
                children[-1].tail = children[-1].tail.strip() + (padding[:-indent] or '\n')

        if validation != 'skip' and errors:
            attrib = {k: unicode_type(v) for k, v in element_data.attributes.items()}
            if validation == 'lax' and converter.etree_element_class is not etree_element:
                child_tags = [converter.etree_element(e.tag, attrib=e.attrib) for e in children]
                elem = converter.etree_element(element_data.tag, text, child_tags, attrib)
            else:
                elem = converter.etree_element(element_data.tag, text, children, attrib)

            for validator, occurs, expected, index in errors:
                yield self.children_validation_error(validation, elem, index, expected, **kwargs)

        yield text, children

    def update_occurs(self, counter):
        """
        Update group occurrences.

        :param counter: a Counter object that trace occurrences for elements and groups.
        """
        if self.model in ('sequence', 'all'):
            if all(counter[item] for item in self if not item.is_emptiable()):
                counter[self] += 1
                for item in self:
                    counter[item] = 0
        elif self.model == 'choice':
            if any(counter[item] for item in self):
                counter[self] += 1
                for item in self:
                    counter[item] = 0
        else:
            raise XMLSchemaValueError("the group %r has no model!" % self)


class Xsd11Group(XsdGroup):
    """
    A class for XSD 1.1 model group definitions. The XSD 1.1 model groups differ
    from XSD 1.0 groups for the 'all' model, that can contains also other groups.

    <all
      id = ID
      maxOccurs = (0 | 1) : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | any | group)*)
    </all>
    """
    def _parse_content_model(self, elem, content_model):
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs != 1:
                self.parse_error("maxOccurs must be (0 | 1) for 'all' model groups")
            if self.min_occurs not in (0, 1):
                self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")

        for child in self._iterparse_components(content_model):
            if child.tag == XSD_ELEMENT_TAG:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif child.tag == XSD_ANY_TAG:
                self.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG):
                self.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP_TAG:
                xsd_group = XsdGroup(child, self.schema, self)
                if xsd_group.name != self.name:
                    self.append(xsd_group)
                elif not hasattr(self, '_elem'):
                    self.parse_error("Circular definitions detected for group %r:" % self.ref, elem)
            else:
                continue  # Error already caught by validation against the meta-schema
