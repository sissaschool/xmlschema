# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
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
from __future__ import unicode_literals

from ..compat import unicode_type
from ..exceptions import XMLSchemaValueError
from ..etree import etree_element
from ..qnames import XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_COMPLEX_TYPE, \
    XSD_ELEMENT, XSD_ANY, XSD_RESTRICTION, XSD_EXTENSION
from xmlschema.helpers import get_qname, local_name
from ..converters import XMLSchemaConverter

from .exceptions import XMLSchemaValidationError, XMLSchemaChildrenValidationError
from .xsdbase import ValidationMixin, XsdComponent, XsdType
from .elements import XsdElement
from .wildcards import XsdAnyElement
from .models import MAX_MODEL_DEPTH, ParticleMixin, ModelGroup, ModelVisitor

ANY_ELEMENT = etree_element(
    XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


class XsdGroup(XsdComponent, ModelGroup, ValidationMixin):
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
    mixed = False
    model = None
    redefine = None
    _admitted_tags = {
        XSD_COMPLEX_TYPE, XSD_EXTENSION, XSD_RESTRICTION, XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE
    }

    def __init__(self, elem, schema, parent, name=None):
        self._group = []
        if parent is not None and parent.mixed:
            self.mixed = parent.mixed
        super(XsdGroup, self).__init__(elem, schema, parent, name)

    def __repr__(self):
        if self.name is None:
            return '%s(model=%r, occurs=%r)' % (self.__class__.__name__, self.model, self.occurs)
        elif self.ref is None:
            return '%s(name=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, self.occurs
            )
        else:
            return '%s(ref=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, self.occurs
            )

    def copy(self):
        group = object.__new__(self.__class__)
        group.__dict__.update(self.__dict__)
        group.errors = self.errors[:]
        group._group = self._group[:]
        return group

    __copy__ = copy

    def _parse(self):
        super(XsdGroup, self)._parse()
        self.clear()
        elem = self.elem
        self._parse_particle(elem)

        if elem.tag == XSD_GROUP:
            # Global group (group)
            name = elem.get('name')
            ref = elem.get('ref')
            if name is None:
                if ref is not None:
                    # Reference to a global group
                    if self.parent is None:
                        self.parse_error("a group reference cannot be global")

                    try:
                        self.name = self.schema.resolve_qname(ref)
                    except ValueError as err:
                        self.parse_error(err, elem)
                        return

                    try:
                        xsd_group = self.schema.maps.lookup_group(self.name)
                    except KeyError:
                        self.parse_error("missing group %r" % self.prefixed_name)
                        xsd_group = self.schema.create_any_content_group(self, self.name)

                    if isinstance(xsd_group, tuple):
                        # Disallowed circular definition, substitute with any content group.
                        self.parse_error("Circular definitions detected for group %r:" % self.ref, xsd_group[0])
                        self.model = 'sequence'
                        self.mixed = True
                        self.append(XsdAnyElement(ANY_ELEMENT, self.schema, self))
                    else:
                        self.model = xsd_group.model
                        if self.model == 'all':
                            if self.max_occurs != 1:
                                self.parse_error("maxOccurs must be 1 for 'all' model groups")
                            if self.min_occurs not in (0, 1):
                                self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")
                            if self.schema.XSD_VERSION == '1.0' and isinstance(self.parent, XsdGroup):
                                self.parse_error("in XSD 1.0 the 'all' model group cannot be nested")
                        self.append(xsd_group)
                else:
                    self.parse_error("missing both attributes 'name' and 'ref'")
                return
            elif ref is None:
                # Global group
                self.name = get_qname(self.target_namespace, name)
                content_model = self._parse_component(elem)
                if self.parent is not None:
                    self.parse_error("attribute 'name' not allowed for a local group")
                else:
                    if 'minOccurs' in elem.attrib:
                        self.parse_error("attribute 'minOccurs' not allowed for a global group")
                    if 'maxOccurs' in elem.attrib:
                        self.parse_error("attribute 'maxOccurs' not allowed for a global group")
                    if 'minOccurs' in content_model.attrib:
                        self.parse_error(
                            "attribute 'minOccurs' not allowed for the model of a global group", content_model
                        )
                    if 'maxOccurs' in content_model.attrib:
                        self.parse_error(
                            "attribute 'maxOccurs' not allowed for the model of a global group", content_model
                        )
                    if content_model.tag not in {XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
                        self.parse_error('unexpected tag %r' % content_model.tag, content_model)
                        return

            else:
                self.parse_error("found both attributes 'name' and 'ref'")
                return
        elif elem.tag in {XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
            # Local group (sequence|all|choice)
            if 'name' in elem.attrib:
                self.parse_error("attribute 'name' not allowed for a local group")
            content_model = elem
            self.name = None
        elif elem.tag in {XSD_COMPLEX_TYPE, XSD_EXTENSION, XSD_RESTRICTION}:
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
            if child.tag == XSD_ELEMENT:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif content_model.tag == XSD_ALL:
                self.parse_error("'all' model can contains only elements.", elem)
            elif child.tag == XSD_ANY:
                self.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE):
                self.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except KeyError:
                    self.parse_error("missing attribute 'ref' in local group", child)
                    continue

                if ref != self.name:
                    xsd_group = XsdGroup(child, self.schema, self)
                    if xsd_group.model == 'all':
                        self.parse_error("'all' model can appears only at 1st level of a model group")
                    else:
                        self.append(xsd_group)
                elif self.redefine is None:
                    self.parse_error("Circular definition detected for group %r:" % self.ref, elem)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        self.parse_error(
                            "Redefined group reference cannot have minOccurs/maxOccurs other than 1:", elem
                        )
                    self.append(self.redefine)
            else:
                continue  # Error already caught by validation against the meta-schema

    def children_validation_error(self, validation, elem, index, particle, occurs=0, expected=None,
                                  source=None, namespaces=None, **_kwargs):
        """
        Helper method for generating model validation errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raise the error.

        :param validation: the validation mode. Can be 'lax' or 'strict'.
        :param elem: the instance Element.
        :param index: the child index.
        :param particle: the XSD component (subgroup or element) associated to the child.
        :param occurs: the child tag occurs.
        :param expected: the expected element tags/object names.
        :param source: the XML resource related to the validation process.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param _kwargs: keyword arguments of the validation process that are not used.
        """
        if validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")

        error = XMLSchemaChildrenValidationError(self, elem, index, particle, occurs, expected, source, namespaces)
        if validation == 'strict':
            raise error
        else:
            return error

    def build(self):
        element_class = self.schema.BUILDERS.element_class
        for k in range(len(self._group)):
            if isinstance(self._group[k], tuple):
                elem, schema = self._group[k]
                self._group[k] = element_class(elem, schema, self)

        if self.redefine is not None:
            for group in self.redefine.iter_components(XsdGroup):
                group.build()

    @property
    def built(self):
        for item in self:
            if not isinstance(item, ParticleMixin):
                return False
            elif isinstance(item, XsdAnyElement):
                if not item.built:
                    return False
            elif item.parent is None:
                continue
            elif item.parent is not self.parent and isinstance(item.parent, XsdType) and item.parent.parent is None:
                continue
            elif not item.ref and not item.built:
                return False
        return True

    @property
    def schema_elem(self):
        return self.elem if self.name else self.parent.elem

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
            if item.parent is None:
                continue
            elif item.parent is not self.parent and isinstance(item.parent, XsdType) and item.parent.parent is None:
                continue
            for obj in item.iter_components(xsd_classes):
                yield obj

    def admitted_restriction(self, model):
        if self.model == model:
            return True
        elif self.model == 'all' and model == 'choice' and len(self) > 1:
            return False
        elif model == 'all' and self.model == 'choice' and len(self) > 1:
            return False
        if model == 'sequence' and self.model != 'sequence' and len(self) > 1:
            return False

    def is_empty(self):
        return not self.mixed and not self

    def is_restriction(self, other, check_occurs=True):
        if not self:
            return True
        elif self.ref is not None:
            return self[0].is_restriction(other, check_occurs)
        elif not isinstance(other, ParticleMixin):
            raise XMLSchemaValueError("the argument 'base' must be a %r instance" % ParticleMixin)
        elif not isinstance(other, XsdGroup):
            return self.is_element_restriction(other)
        elif not other:
            return False
        elif other.ref:
            return self.is_restriction(other[0], check_occurs)
        elif len(other) == other.min_occurs == other.max_occurs == 1:
            if len(self) > 1:
                return self.is_restriction(other[0], check_occurs)
            elif isinstance(self[0], XsdGroup) and self[0].is_pointless(parent=self):
                return self[0].is_restriction(other[0], check_occurs)

        # Compare model with model
        if self.model != other.model and self.model != 'sequence' and len(self) > 1:
            return False
        elif self.model == other.model or other.model == 'sequence':
            return self.is_sequence_restriction(other)
        elif other.model == 'all':
            return self.is_all_restriction(other)
        elif other.model == 'choice':
            return self.is_choice_restriction(other)

    def is_element_restriction(self, other):
        if self.schema.XSD_VERSION == '1.0' and isinstance(other, XsdElement) and \
                not other.ref and other.name not in self.schema.substitution_groups:
            return False
        elif not self.has_occurs_restriction(other):
            return False
        elif self.model == 'choice':
            if other.name in self.maps.substitution_groups and all(
                    isinstance(e, XsdElement) and e.substitution_group == other.name for e in self):
                return True
            return any(e.is_restriction(other, False) for e in self)
        else:
            min_occurs = max_occurs = 0
            for item in self.iter_model():
                if isinstance(item, XsdGroup):
                    return False
                elif item.min_occurs == 0 or item.is_restriction(other, False):
                    min_occurs += item.min_occurs
                    if max_occurs is not None:
                        if item.max_occurs is None:
                            max_occurs = None
                        else:
                            max_occurs += item.max_occurs
                    continue
                return False

            if min_occurs < other.min_occurs:
                return False
            elif max_occurs is None:
                return other.max_occurs is None
            elif other.max_occurs is None:
                return True
            else:
                return max_occurs <= other.max_occurs

    def is_sequence_restriction(self, other):
        if not self.has_occurs_restriction(other):
            return False
        check_occurs = other.max_occurs != 0
        check_emptiable = other.model != 'choice'  # or self.schema.XSD_VERSION == '1.0'

        # Same model: declarations must simply preserve order
        other_iterator = iter(other.iter_model())
        for item in self.iter_model():
            while True:
                try:
                    other_item = next(other_iterator)
                except StopIteration:
                    return False
                if other_item is item or item.is_restriction(other_item, check_occurs):
                    break
                elif check_emptiable and not other_item.is_emptiable():
                    return False

        if not check_emptiable:
            return True

        while True:
            try:
                other_item = next(other_iterator)
            except StopIteration:
                return True
            else:
                if not other_item.is_emptiable():
                    return False

    def is_all_restriction(self, other):
        if not self.has_occurs_restriction(other):
            return False

        check_occurs = other.max_occurs != 0
        restriction_items = list(self)

        for other_item in other.iter_model():
            for item in restriction_items:
                if other_item is item or item.is_restriction(other_item, check_occurs):
                    break
            else:
                if not other_item.is_emptiable():
                    return False
                continue
            restriction_items.remove(item)

        return not bool(restriction_items)

    def is_choice_restriction(self, other):
        if self.parent is None and other.parent is not None and self.schema.XSD_VERSION == '1.0':
            return False

        check_occurs = other.max_occurs != 0
        restriction_items = list(self)
        max_occurs = 0
        other_max_occurs = 0

        for other_item in other.iter_model():
            for item in restriction_items:

                if other_item is item or item.is_restriction(other_item, check_occurs):
                    if max_occurs is not None:
                        if item.max_occurs is None:
                            max_occurs = None
                        else:
                            max_occurs += item.max_occurs

                    if other_max_occurs is not None:
                        if other_item.max_occurs is None:
                            other_max_occurs = None
                        else:
                            other_max_occurs = max(other_max_occurs, other_item.max_occurs)
                    break
            else:
                continue
            restriction_items.remove(item)

        if restriction_items:
            return False
        elif other_max_occurs is None:
            if other.max_occurs:
                return True
            other_max_occurs = 0
        elif other.max_occurs is None:
            if other_max_occurs:
                return True
            other_max_occurs = 0
        else:
            other_max_occurs *= other.max_occurs

        if max_occurs is None:
            return self.max_occurs == 0
        elif self.max_occurs is None:
            return max_occurs == 0
        else:
            return other_max_occurs >= max_occurs * self.max_occurs

    def iter_elements(self, depth=0):
        if depth <= MAX_MODEL_DEPTH:
            for item in self:
                if isinstance(item, XsdGroup):
                    for e in item.iter_elements(depth+1):
                        yield e
                else:
                    yield item
                    for e in self.maps.substitution_groups.get(item.name, ()):
                        yield e

    def sort_children(self, elements, default_namespace=None):
        """
        Sort elements by group order, that maybe partial in case of 'all' or 'choice' ordering.
        The not matching elements are appended at the end.
        """
        def sorter(elem):
            for e in elements_order:
                if e.is_matching(elem.tag, default_namespace):
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

        model = ModelVisitor(self)
        errors = []

        if not isinstance(converter, XMLSchemaConverter):
            converter = self.schema.get_converter(converter, **kwargs)
        default_namespace = converter.get('')

        for index, child in enumerate(elem):
            if callable(child.tag):
                continue  # child is a <class 'lxml.etree._Comment'>

            if not default_namespace or child.tag[0] == '{':
                tag = child.tag
            else:
                tag = '{%s}%s' % (default_namespace, child.tag)

            while model.element is not None:
                if tag in model.element.names or model.element.name is None \
                        and model.element.is_matching(tag, default_namespace):
                    xsd_element = model.element
                else:
                    for xsd_element in model.element.iter_substitutes():
                        if tag in xsd_element.names:
                            break
                    else:
                        for particle, occurs, expected in model.advance(False):
                            errors.append((index, particle, occurs, expected))
                            model.clear()
                            model.broken = True  # the model is broken, continues with raw decoding.
                            break
                        continue

                for particle, occurs, expected in model.advance(True):
                    errors.append((index, particle, occurs, expected))
                break
            else:
                for xsd_element in self.iter_elements():
                    if tag in xsd_element.names or xsd_element.name is None \
                            and xsd_element.is_matching(child.tag, default_namespace):
                        if not model.broken:
                            model.broken = True
                            errors.append((index, xsd_element, 0, []))
                        break
                else:
                    errors.append((index, self, 0, None))
                    xsd_element = None
                    if not model.broken:
                        model.broken = True

            if xsd_element is None:
                # TODO: use a default decoder str-->str??
                continue

            for result in xsd_element.iter_decode(child, validation, converter, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((child.tag, result, xsd_element))

            if cdata_index and child.tail is not None:
                tail = unicode_type(child.tail.strip())
                if tail:
                    if result_list and isinstance(result_list[-1][0], int):
                        tail = result_list[-1][1] + ' ' + tail
                        result_list[-1] = result_list[-1][0], tail, None
                    else:
                        result_list.append((cdata_index, tail, None))
                        cdata_index += 1

        if model.element is not None:
            index = len(elem)
            for particle, occurs, expected in model.stop():
                errors.append((index, particle, occurs, expected))

        if validation != 'skip' and errors:
            for model_error in errors:
                yield self.children_validation_error(validation, elem, *model_error, **kwargs)

        yield result_list

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
        padding = '\n' + ' ' * indent * level
        default_namespace = converter.get('')
        losslessly = converter.losslessly

        model = ModelVisitor(self)
        cdata_index = 0

        for index, (name, value) in enumerate(element_data.content):
            if isinstance(name, int):
                if not children:
                    text = padding + value if text is None else text + value + padding
                elif children[-1].tail is None:
                    children[-1].tail = padding + value
                else:
                    children[-1].tail += value + padding
                cdata_index += 1
                continue

            if not default_namespace or name[0] == '{':
                tag = name
            else:
                tag = '{%s}%s' % (default_namespace, name)

            while model.element is not None:
                if tag in model.element.names or model.element.name is None \
                        and model.element.is_matching(tag, default_namespace):
                    xsd_element = model.element
                else:
                    for xsd_element in model.element.iter_substitutes():
                        if tag in xsd_element.names:
                            break
                    else:
                        for particle, occurs, expected in model.advance():
                            errors.append((index - cdata_index, particle, occurs, expected))
                        continue

                if isinstance(xsd_element, XsdAnyElement):
                    value = get_qname(default_namespace, name), value
                for result in xsd_element.iter_encode(value, validation, converter, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        children.append(result)

                for particle, occurs, expected in model.advance(True):
                    errors.append((index - cdata_index, particle, occurs, expected))
                break
            else:
                if losslessly:
                    errors.append((index - cdata_index, self, 0, []))

                for xsd_element in self.iter_elements():
                    if tag in xsd_element.names or xsd_element.name is None \
                            and xsd_element.is_matching(name, default_namespace):
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
            for particle, occurs, expected in model.stop():
                errors.append((index, particle, occurs, expected))

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

            for index, particle, occurs, expected in errors:
                yield self.children_validation_error(validation, elem, index, particle, occurs, expected, **kwargs)

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
            if child.tag == XSD_ELEMENT:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif child.tag == XSD_ANY:
                self.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE, XSD_ALL):
                self.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except KeyError:
                    self.parse_error("missing attribute 'ref' in local group", child)
                    continue

                if ref != self.name:
                    self.append(XsdGroup(child, self.schema, self))
                elif self.redefine is None:
                    self.parse_error("Circular definition detected for group %r:" % self.ref, elem)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        self.parse_error(
                            "Redefined group reference cannot have minOccurs/maxOccurs other than 1:", elem
                        )
                    self.append(self.redefine)
            else:
                continue  # Error already caught by validation against the meta-schema
