#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
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
import warnings

from .. import limits
from ..exceptions import XMLSchemaValueError
from ..names import XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ELEMENT, \
    XSD_ANY, XSI_TYPE, XSD_ANY_TYPE, XSD_ANNOTATION
from ..etree import etree_element
from ..helpers import get_qname, local_name

from .exceptions import XMLSchemaModelError, XMLSchemaModelDepthError, \
    XMLSchemaValidationError, XMLSchemaChildrenValidationError, \
    XMLSchemaTypeTableWarning
from .helpers import not_whitespace
from .xsdbase import ValidationMixin, XsdComponent, XsdType
from .particles import ParticleMixin, ModelGroup
from .elements import XsdElement
from .wildcards import XsdAnyElement, Xsd11AnyElement
from .models import ModelVisitor, distinguishable_paths

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
    Class for XSD 1.0 *model group* definitions.

    ..  <group
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded) : 1
          minOccurs = nonNegativeInteger : 1
          name = NCName
          ref = QName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (all | choice | sequence)?)
        </group>

    ..  <all
          id = ID
          maxOccurs = 1 : 1
          minOccurs = (0 | 1) : 1
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, element*)
        </all>

    ..  <choice
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (element | group | choice | sequence | any)*)
        </choice>

    ..  <sequence
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (element | group | choice | sequence | any)*)
        </sequence>
    """
    mixed = False
    restriction = None
    interleave = None  # an Xsd11AnyElement in case of XSD 1.1 openContent with mode='interleave'
    suffix = None  # an Xsd11AnyElement in case of openContent with mode='suffix' or 'interleave'

    _ADMITTED_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}

    def __init__(self, elem, schema, parent):
        self._group = []
        if parent is not None and parent.mixed:
            self.mixed = parent.mixed
        super(XsdGroup, self).__init__(elem, schema, parent)

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
        self._parse_particle(self.elem)

        if self.elem.tag != XSD_GROUP:
            # Local group (sequence|all|choice)
            if 'name' in self.elem.attrib:
                self.parse_error("attribute 'name' not allowed for a local group")
            self._parse_content_model(self.elem)

        elif self._parse_reference():
            try:
                xsd_group = self.maps.lookup_group(self.name)
            except KeyError:
                self.parse_error("missing group %r" % self.prefixed_name)
                xsd_group = self.schema.create_any_content_group(self, self.name)

            if isinstance(xsd_group, tuple):
                # Disallowed circular definition, substitute with any content group.
                self.parse_error("Circular definitions detected for group %r:" % self.name,
                                 xsd_group[0])
                self.model = 'sequence'
                self.mixed = True
                self.append(self.schema.BUILDERS.any_element_class(ANY_ELEMENT, self.schema, self))
            else:
                self.model = xsd_group.model
                if self.model == 'all':
                    if self.max_occurs != 1:
                        self.parse_error("maxOccurs must be 1 for 'all' model groups")
                    if self.min_occurs not in (0, 1):
                        self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")
                    if self.xsd_version == '1.0' and isinstance(self.parent, XsdGroup):
                        self.parse_error("in XSD 1.0 the 'all' model group cannot be nested")
                self.append(xsd_group)
                self.ref = xsd_group

        else:
            attrib = self.elem.attrib
            try:
                self.name = get_qname(self.target_namespace, attrib['name'])
            except KeyError:
                pass
            else:
                content_model = self._parse_child_component(self.elem, strict=True)
                if self.parent is not None:
                    self.parse_error("attribute 'name' not allowed for a local group")
                else:
                    if 'minOccurs' in attrib:
                        self.parse_error("attribute 'minOccurs' not allowed for a global group")
                    if 'maxOccurs' in attrib:
                        self.parse_error("attribute 'maxOccurs' not allowed for a global group")
                    if 'minOccurs' in content_model.attrib:
                        self.parse_error("attribute 'minOccurs' not allowed for the model "
                                         "of a global group", content_model)
                    if 'maxOccurs' in content_model.attrib:
                        self.parse_error("attribute 'maxOccurs' not allowed for the model "
                                         "of a global group", content_model)

                if content_model.tag in {XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
                    self._parse_content_model(content_model)
                else:
                    self.parse_error('unexpected tag %r' % content_model.tag, content_model)

    def _parse_content_model(self, content_model):
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs != 1:
                self.parse_error("maxOccurs must be 1 for 'all' model groups")
            if self.min_occurs not in (0, 1):
                self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")

        for child in content_model:
            if child.tag == XSD_ANNOTATION or callable(child.tag):
                continue
            elif child.tag == XSD_ELEMENT:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif content_model.tag == XSD_ALL:
                self.parse_error("'all' model can contains only elements.")
            elif child.tag == XSD_ANY:
                self.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE):
                self.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except (KeyError, ValueError, RuntimeError) as err:
                    if 'ref' not in child.attrib:
                        self.parse_error("missing attribute 'ref' in local group", child)
                    else:
                        self.parse_error(err, child)
                    continue

                if ref != self.name:
                    xsd_group = XsdGroup(child, self.schema, self)
                    if xsd_group.model == 'all':
                        self.parse_error("'all' model can appears only at 1st level "
                                         "of a model group")
                    else:
                        self.append(xsd_group)
                elif self.redefine is None:
                    self.parse_error("Circular definition detected for group %r:" % self.name)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        self.parse_error("Redefined group reference cannot have "
                                         "minOccurs/maxOccurs other than 1:")
                    self.append(self.redefine)

    def children_validation_error(self, validation, elem, index, particle, occurs=0, expected=None,
                                  source=None, namespaces=None, **_kwargs):
        """
        Helper method for generating model validation errors. If validation mode
        is 'lax' or 'skip' returns the error, otherwise raise the error.

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
        error = XMLSchemaChildrenValidationError(self, elem, index, particle, occurs,
                                                 expected, source, namespaces)
        if validation == 'strict':
            raise error
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
                continue
            elif item.parent is None:
                continue
            elif item.parent is not self.parent and \
                    isinstance(item.parent, XsdType) and item.parent.parent is None:
                continue
            elif not item.ref and not item.built:
                return False

        return True if self.model else False

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any(item.validation_attempted == 'partial' for item in self):
            return 'partial'
        else:
            return 'none'

    @property
    def schema_elem(self):
        return self.elem if self.name else self.parent.elem

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for item in self:
            if item.parent is None:
                continue
            elif item.parent is not self.parent and isinstance(item.parent, XsdType) \
                    and item.parent.parent is None:
                continue
            yield from item.iter_components(xsd_classes)

        if self.redefine is not None and self.redefine not in self:
            yield from self.redefine.iter_components(xsd_classes)

    def admits_restriction(self, model):
        if self.model == model:
            return True
        elif self.model == 'all':
            return model == 'sequence'
        elif self.model == 'choice':
            return model == 'sequence' or len(self.ref or self) <= 1
        else:
            return model == 'choice' or len(self.ref or self) <= 1

    def is_empty(self):
        return not self.mixed and (not self._group or self.max_occurs == 0)

    def is_restriction(self, other, check_occurs=True):
        if not self._group:
            return True
        elif not isinstance(other, ParticleMixin):
            raise XMLSchemaValueError("the argument 'base' must be a %r instance" % ParticleMixin)
        elif not isinstance(other, XsdGroup):
            return self.is_element_restriction(other)
        elif not other:
            return False
        elif len(other) == other.min_occurs == other.max_occurs == 1:
            if len(self) > 1:
                return self.is_restriction(other[0], check_occurs)
            elif self.ref is None and isinstance(self[0], XsdGroup) \
                    and self[0].is_pointless(parent=self):
                return self[0].is_restriction(other[0], check_occurs)

        # Compare model with model
        if self.model != other.model and self.model != 'sequence' and \
                (len(self) > 1 or self.ref is not None and len(self[0]) > 1):
            return False
        elif self.model == other.model or other.model == 'sequence':
            return self.is_sequence_restriction(other)
        elif other.model == 'all':
            return self.is_all_restriction(other)
        elif other.model == 'choice':
            return self.is_choice_restriction(other)

    def is_element_restriction(self, other):
        if self.xsd_version == '1.0' and isinstance(other, XsdElement) and \
                not other.ref and other.name not in self.schema.substitution_groups:
            return False
        elif not self.has_occurs_restriction(other):
            return False
        elif self.model == 'choice':
            if other.name in self.maps.substitution_groups and \
                    all(isinstance(e, XsdElement) and e.substitution_group == other.name
                        for e in self):
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
                elif other.model == 'choice':
                    if item.max_occurs != 0:
                        continue
                    elif not other_item.is_matching(item.name, self.default_namespace):
                        continue
                    elif all(e.max_occurs == 0 for e in self.iter_model()):
                        return False
                    else:
                        break
                elif not other_item.is_emptiable():
                    return False

        if other.model == 'choice':
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
        restriction_items = list(self) if self.ref is None else list(self[0])

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
        if self.ref is None:
            if self.parent is None and other.parent is not None:
                return False  # not allowed restriction in XSD 1.0
            restriction_items = list(self)
        elif other.parent is None:
            restriction_items = list(self[0])
        else:
            return False  # not allowed restriction in XSD 1.0

        check_occurs = other.max_occurs != 0
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
            if other.max_occurs != 0:
                return True
            other_max_occurs = 0
        elif other.max_occurs is None:
            if other_max_occurs != 0:
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

    def check_model(self):
        """
        Checks if the model group is deterministic. Element Declarations Consistent and
        Unique Particle Attribution constraints are checked.
        :raises: an `XMLSchemaModelError` at first violated constraint.
        """
        def safe_iter_path(group, depth):
            if not depth:
                raise XMLSchemaModelDepthError(group)
            for item in group:
                if isinstance(item, ModelGroup):
                    current_path.append(item)
                    yield from safe_iter_path(item, depth - 1)
                    current_path.pop()
                else:
                    yield item

        paths = {}
        current_path = [self]
        try:
            any_element = self.parent.open_content.any_element
        except AttributeError:
            any_element = None

        for e in safe_iter_path(self, limits.MAX_MODEL_DEPTH):
            for pe, previous_path in paths.values():
                # EDC check
                if not e.is_consistent(pe) or any_element and not any_element.is_consistent(pe):
                    msg = "Element Declarations Consistent violation between %r and %r: " \
                          "match the same name but with different types" % (e, pe)
                    raise XMLSchemaModelError(self, msg)

                # UPA check
                if pe is e or not pe.is_overlap(e):
                    continue
                elif pe.parent is e.parent:
                    if pe.parent.model in {'all', 'choice'}:
                        if isinstance(pe, Xsd11AnyElement) and not isinstance(e, XsdAnyElement):
                            pe.add_precedence(e, self)
                        elif isinstance(e, Xsd11AnyElement) and not isinstance(pe, XsdAnyElement):
                            e.add_precedence(pe, self)
                        else:
                            msg = "{!r} and {!r} overlap and are in the same {!r} group"
                            raise XMLSchemaModelError(self, msg.format(pe, e, pe.parent.model))
                    elif pe.min_occurs == pe.max_occurs:
                        continue

                if distinguishable_paths(previous_path + [pe], current_path + [e]):
                    continue
                elif isinstance(pe, Xsd11AnyElement) and not isinstance(e, XsdAnyElement):
                    pe.add_precedence(e, self)
                elif isinstance(e, Xsd11AnyElement) and not isinstance(pe, XsdAnyElement):
                    e.add_precedence(pe, self)
                else:
                    msg = "Unique Particle Attribution violation between {!r} and {!r}"
                    raise XMLSchemaModelError(self, msg.format(pe, e))

            paths[e.name] = e, current_path[:]

    def check_dynamic_context(self, elem, xsd_element, model_element, namespaces):
        if model_element is not xsd_element:
            if 'substitution' in model_element.block \
                    or xsd_element.type.is_blocked(model_element):
                raise XMLSchemaValidationError(
                    model_element, elem, "substitution of %r is blocked" % model_element
                )

        alternatives = ()
        if isinstance(xsd_element, XsdAnyElement):
            if xsd_element.process_contents == 'skip':
                return

            try:
                xsd_element = self.maps.lookup_element(elem.tag)
            except LookupError:
                try:
                    type_name = elem.attrib[XSI_TYPE].strip()
                except KeyError:
                    return
                else:
                    xsd_type = self.maps.get_instance_type(
                        type_name, self.any_type, namespaces
                    )
            else:
                alternatives = xsd_element.alternatives
                try:
                    type_name = elem.attrib[XSI_TYPE].strip()
                except KeyError:
                    xsd_type = xsd_element.type
                else:
                    xsd_type = self.maps.get_instance_type(
                        type_name, xsd_element.type, namespaces
                    )

        else:
            if XSI_TYPE not in elem.attrib:
                xsd_type = xsd_element.type
            else:
                alternatives = xsd_element.alternatives
                try:
                    type_name = elem.attrib[XSI_TYPE].strip()
                except KeyError:
                    xsd_type = xsd_element.type
                else:
                    xsd_type = self.maps.get_instance_type(
                        type_name, xsd_element.type, namespaces
                    )

            if model_element is not xsd_element and model_element.block:
                for derivation in model_element.block.split():
                    if xsd_type is not model_element.type and \
                            xsd_type.is_derived(model_element.type, derivation):
                        reason = "usage of %r with type %s is blocked by head element"
                        raise XMLSchemaValidationError(
                            self, elem, reason % (xsd_element, derivation)
                        )

            if XSI_TYPE not in elem.attrib:
                return

        # If it's a restriction the context is the base_type's group
        group = self.restriction if self.restriction is not None else self

        # Dynamic EDC check of matched element
        for e in filter(lambda x: isinstance(x, XsdElement), group.iter_elements()):
            if e.name == elem.tag:
                other = e
            else:
                for other in e.iter_substitutes():
                    if other.name == elem.tag:
                        break
                else:
                    continue

            if len(other.alternatives) != len(alternatives) or \
                    not xsd_type.is_dynamic_consistent(other.type):
                reason = "%r that matches %r is not consistent with local declaration %r"
                raise XMLSchemaValidationError(self, reason % (elem, xsd_element, other))
            elif not all(any(a == x for x in alternatives) for a in other.alternatives) or \
                    not all(any(a == x for x in other.alternatives) for a in alternatives):
                msg = "Maybe a not equivalent type table between elements %r and %r."
                warnings.warn(msg % (self, xsd_element), XMLSchemaTypeTableWarning, stacklevel=3)

    def match_element(self, name, default_namespace=None):
        """
        Try a model-less match of a child element. Returns the
        matched element, or `None` if there is no match.
        """
        for xsd_element in self.iter_elements():
            if xsd_element.is_matching(name, default_namespace, group=self):
                return xsd_element

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Creates an iterator for decoding an Element content.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a list of 3-tuples (key, decoded data, decoder), \
        eventually preceded by a sequence of validation or decoding errors.
        """
        result_list = []
        cdata_index = 1  # keys for CDATA sections are positive integers

        if not self._group and self.model == 'choice' and self.min_occurs:
            reason = "an empty 'choice' group with minOccurs > 0 cannot validate any content"
            yield self.validation_error(validation, reason, elem, **kwargs)
            yield result_list
            return

        if not self.mixed:
            # Check element CDATA
            if not_whitespace(elem.text) or any(not_whitespace(child.tail) for child in elem):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] equals to an empty complexType declaration
                else:
                    reason = "character data between child elements not allowed"
                    yield self.validation_error(validation, reason, elem, **kwargs)
                    cdata_index = 0  # Do not decode CDATA

        if cdata_index and elem.text is not None:
            text = str(elem.text.strip())
            if text:
                result_list.append((cdata_index, text, None))
                cdata_index += 1

        level = kwargs['level'] = kwargs.pop('level', 0) + 1
        over_max_depth = 'max_depth' in kwargs and kwargs['max_depth'] <= level
        if level > limits.MAX_XML_DEPTH:
            reason = "XML data depth exceeded (MAX_XML_DEPTH=%r)" % limits.MAX_XML_DEPTH
            self.validation_error('strict', reason, elem, **kwargs)

        try:
            namespaces = kwargs['namespaces']
        except KeyError:
            namespaces = default_namespace = None
        else:
            try:
                default_namespace = namespaces.get('')
            except AttributeError:
                default_namespace = None

        model = ModelVisitor(self)
        errors = []
        broken_model = False

        for index, child in enumerate(elem):
            if callable(child.tag):
                continue  # child is a <class 'lxml.etree._Comment'>

            while model.element is not None:
                xsd_element = model.element.match(
                    child.tag, default_namespace, group=self, occurs=model.occurs
                )
                if xsd_element is None:
                    if self.interleave is not None and self.interleave.is_matching(
                            child.tag, default_namespace, self, model.occurs):
                        xsd_element = self.interleave
                        break

                    for particle, occurs, expected in model.advance(False):
                        errors.append((index, particle, occurs, expected))
                        model.clear()
                        broken_model = True  # the model is broken, continues with raw decoding.
                        xsd_element = self.match_element(child.tag, default_namespace)
                        break
                    else:
                        continue
                    break

                try:
                    self.check_dynamic_context(child, xsd_element, model.element, namespaces)
                except XMLSchemaValidationError as err:
                    yield self.validation_error(validation, err, elem, **kwargs)

                for particle, occurs, expected in model.advance(True):
                    errors.append((index, particle, occurs, expected))
                break
            else:
                if self.suffix is not None and \
                        self.suffix.is_matching(child.tag, default_namespace, self):
                    xsd_element = self.suffix
                else:
                    xsd_element = self.match_element(child.tag, default_namespace)
                    if xsd_element is None:
                        errors.append((index, self, 0, None))
                        broken_model = True
                    elif not broken_model:
                        errors.append((index, xsd_element, 0, []))
                        broken_model = True

            if xsd_element is None:
                if kwargs.get('keep_unknown') and 'converter' in kwargs:
                    for result in self.any_type.iter_decode(child, validation, **kwargs):
                        result_list.append((child.tag, result, None))
                continue
            elif 'converter' not in kwargs:
                # Validation-only mode: do not append results
                for result in xsd_element.iter_decode(child, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                continue
            elif over_max_depth:
                if 'depth_filler' in kwargs:
                    obj = kwargs['depth_filler']
                    result_list.append((child.tag, obj(xsd_element), xsd_element))
                continue

            for result in xsd_element.iter_decode(child, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((child.tag, result, xsd_element))

            if cdata_index and child.tail is not None:
                tail = str(child.tail.strip())
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

        if errors:
            for model_error in errors:
                yield self.children_validation_error(validation, elem, *model_error, **kwargs)

        yield result_list

    def iter_encode(self, element_data, validation='lax', **kwargs):
        """
        Creates an iterator for encoding data to a list containing Element data.

        :param element_data: an ElementData instance with unencoded data.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields a couple with the text of the Element and a list of 3-tuples \
        (key, decoded data, decoder), eventually preceded by a sequence of validation \
        or encoding errors.
        """
        level = kwargs['level'] = kwargs.get('level', 0) + 1
        errors = []
        text = element_data.text
        children = []
        try:
            indent = kwargs['indent']
        except KeyError:
            indent = 4

        padding = '\n' + ' ' * indent * level

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        default_namespace = converter.get('')
        model = ModelVisitor(self)
        index = cdata_index = 0
        wrong_content_type = False

        if element_data.content is None:
            content = []
        elif isinstance(element_data.content, dict) or kwargs.get('unordered'):
            content = ModelVisitor(self).iter_unordered_content(element_data.content)
        elif not isinstance(element_data.content, list):
            wrong_content_type = True
            content = []
        elif converter.losslessly:
            content = element_data.content
        else:
            content = ModelVisitor(self).iter_collapsed_content(element_data.content)

        for index, (name, value) in enumerate(content):
            if isinstance(name, int):
                if not children:
                    text = padding + value if text is None else text + value + padding
                elif children[-1].tail is None:
                    children[-1].tail = padding + value
                else:
                    children[-1].tail += value + padding
                cdata_index += 1
                continue

            if self.interleave and self.interleave.is_matching(name, default_namespace, group=self):
                xsd_element = self.interleave
                value = get_qname(default_namespace, name), value
            else:
                while model.element is not None:
                    xsd_element = model.element.match(
                        name, default_namespace, group=self, occurs=model.occurs
                    )
                    if xsd_element is None:
                        for particle, occurs, expected in model.advance():
                            errors.append((index - cdata_index, particle, occurs, expected))
                        continue
                    elif isinstance(xsd_element, XsdAnyElement):
                        value = get_qname(default_namespace, name), value

                    for particle, occurs, expected in model.advance(True):
                        errors.append((index - cdata_index, particle, occurs, expected))
                    break
                else:
                    if self.suffix and self.suffix.is_matching(name, default_namespace, group=self):
                        xsd_element = self.suffix
                        value = get_qname(default_namespace, name), value
                    else:
                        errors.append((index - cdata_index, self, 0, []))
                        xsd_element = self.match_element(name, default_namespace)
                        if isinstance(xsd_element, XsdAnyElement):
                            value = get_qname(default_namespace, name), value
                        elif xsd_element is None:
                            if name.startswith('{') or ':' not in name:
                                reason = '{!r} does not match any declared element ' \
                                         'of the model group.'.format(name)
                            else:
                                reason = '{} has an unknown prefix {!r}'.format(
                                    name, name.split(':')[0]
                                )
                            yield self.validation_error(validation, reason, value, **kwargs)
                            continue

            for result in xsd_element.iter_encode(value, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    children.append(result)

        if model.element is not None:
            for particle, occurs, expected in model.stop():
                errors.append((index - cdata_index + 1, particle, occurs, expected))

        if children:
            if children[-1].tail is None:
                children[-1].tail = padding[:-indent] or '\n'
            else:
                children[-1].tail = children[-1].tail.strip() + (padding[:-indent] or '\n')

        cdata_not_allowed = not self.mixed and not_whitespace(text) and self and \
            (len(self) > 1 or not isinstance(self[0], XsdAnyElement))

        if errors or cdata_not_allowed or wrong_content_type:
            attrib = {k: str(v) for k, v in element_data.attributes.items()}
            if validation != 'strict' and converter.etree_element_class is not etree_element:
                child_tags = [converter.etree_element(e.tag, attrib=e.attrib) for e in children]
                elem = converter.etree_element(element_data.tag, text, child_tags, attrib)
            else:
                elem = converter.etree_element(element_data.tag, text, children, attrib)

            if wrong_content_type:
                reason = "wrong content type {!r}".format(type(element_data.content))
                yield self.validation_error(validation, reason, elem, **kwargs)

            if cdata_not_allowed:
                reason = "character data between child elements not allowed"
                yield self.validation_error(validation, reason, elem, **kwargs)

            for index, particle, occurs, expected in errors:
                yield self.children_validation_error(
                    validation, elem, index, particle, occurs, expected, **kwargs
                )

        yield text, children


class Xsd11Group(XsdGroup):
    """
    Class for XSD 1.1 *model group* definitions.

    .. The XSD 1.1 model groups differ from XSD 1.0 groups for the 'all' model,
    .. that can contains also other groups.
    ..  <all
          id = ID
          maxOccurs = (0 | 1) : 1
          minOccurs = (0 | 1) : 1
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (element | any | group)*)
        </all>
    """
    def _parse_content_model(self, content_model):
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs not in (0, 1):
                self.parse_error("maxOccurs must be (0 | 1) for 'all' model groups")
            if self.min_occurs not in (0, 1):
                self.parse_error("minOccurs must be (0 | 1) for 'all' model groups")

        for child in content_model:
            if child.tag == XSD_ELEMENT:
                # Builds inner elements and reference groups later, for avoids circularity.
                self.append((child, self.schema))
            elif child.tag == XSD_ANY:
                self.append(Xsd11AnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE, XSD_ALL):
                self.append(Xsd11Group(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except (KeyError, ValueError, RuntimeError) as err:
                    if 'ref' not in child.attrib:
                        self.parse_error("missing attribute 'ref' in local group", child)
                    else:
                        self.parse_error(err, child)
                    continue

                if ref != self.name:
                    self.append(Xsd11Group(child, self.schema, self))
                    if (self.model != 'all') ^ (self[-1].model != 'all'):
                        msg = "an xs:%s group cannot include a reference to an x:%s group"
                        self.parse_error(msg % (self.model, self[-1].model))
                        self.pop()

                elif self.redefine is None:
                    self.parse_error("Circular definition detected for group %r:" % self.name)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        self.parse_error("Redefined group reference cannot have "
                                         "minOccurs/maxOccurs other than 1:")
                    self.append(self.redefine)

    def admits_restriction(self, model):
        if self.model == model or self.model == 'all':
            return True
        elif self.model == 'choice':
            return model == 'sequence' or len(self.ref or self) <= 1
        else:
            return model == 'choice' or len(self.ref or self) <= 1

    def is_restriction(self, other, check_occurs=True):
        if not self._group:
            return True
        elif not isinstance(other, ParticleMixin):
            raise XMLSchemaValueError("the argument 'base' must be a %r instance" % ParticleMixin)
        elif not isinstance(other, XsdGroup):
            return self.is_element_restriction(other)
        elif not other:
            return False
        elif len(other) == other.min_occurs == other.max_occurs == 1:
            if len(self) > 1:
                return self.is_restriction(other[0], check_occurs)
            elif self.ref is None and isinstance(self[0], XsdGroup) \
                    and self[0].is_pointless(parent=self):
                return self[0].is_restriction(other[0], check_occurs)

        if other.model == 'sequence':
            return self.is_sequence_restriction(other)
        elif other.model == 'all':
            return self.is_all_restriction(other)
        elif other.model == 'choice':
            return self.is_choice_restriction(other)

    def is_sequence_restriction(self, other):
        if not self.has_occurs_restriction(other):
            return False

        check_occurs = other.max_occurs != 0

        item_iterator = iter(self.iter_model())
        item = next(item_iterator, None)

        for other_item in other.iter_model():
            if item is not None and item.is_restriction(other_item, check_occurs):
                item = next(item_iterator, None)
            elif not other_item.is_emptiable():
                break
        else:
            if item is None:
                return True

        # Restriction check failed: try another check without removing pointless groups
        item_iterator = iter(self)
        item = next(item_iterator, None)

        for other_item in other.iter_model():
            if item is not None and item.is_restriction(other_item, check_occurs):
                item = next(item_iterator, None)
            elif not other_item.is_emptiable():
                return False
        return item is None

    def is_all_restriction(self, other):
        if not self.has_occurs_restriction(other):
            return False
        restriction_items = list(self.iter_model())

        base_items = list(other.iter_model())

        # If the base includes more wildcard, calculates and appends a
        # wildcard union for validating wildcard unions in restriction
        wildcards = []
        for w1 in filter(lambda x: isinstance(x, XsdAnyElement), base_items):
            for w2 in wildcards:
                if w1.process_contents == w2.process_contents and w1.occurs == w2.occurs:
                    w2.union(w1)
                    w2.extended = True
                    break
            else:
                wildcards.append(w1.copy())

        base_items.extend(w for w in wildcards if hasattr(w, 'extended'))

        if self.model != 'choice':
            restriction_wildcards = [e for e in restriction_items if isinstance(e, XsdAnyElement)]

            for other_item in base_items:
                min_occurs, max_occurs = 0, other_item.max_occurs
                for k in range(len(restriction_items) - 1, -1, -1):
                    item = restriction_items[k]

                    if item.is_restriction(other_item, check_occurs=False):
                        if max_occurs is None:
                            min_occurs += item.min_occurs
                        elif item.max_occurs is None or max_occurs < item.max_occurs or \
                                min_occurs + item.min_occurs > max_occurs:
                            continue
                        else:
                            min_occurs += item.min_occurs
                            max_occurs -= item.max_occurs

                        restriction_items.remove(item)
                        if not min_occurs or max_occurs == 0:
                            break
                else:
                    if self.model == 'all' and restriction_wildcards:
                        try:
                            if other_item.type.name != XSD_ANY_TYPE:
                                for w in restriction_wildcards:
                                    if w.is_matching(other_item.name, self.target_namespace):
                                        return False
                        except AttributeError:
                            pass

                if min_occurs < other_item.min_occurs:
                    break
            else:
                if not restriction_items:
                    return True
            return False

        # Restriction with a choice model: this a more complex case
        # because the not emptiable elements of the base group have
        # to be included in each item of the choice group.
        not_emptiable_items = {x for x in base_items if x.min_occurs}

        for other_item in base_items:
            min_occurs, max_occurs = 0, other_item.max_occurs
            for k in range(len(restriction_items) - 1, -1, -1):
                item = restriction_items[k]

                if item.is_restriction(other_item, check_occurs=False):
                    if max_occurs is None:
                        min_occurs += item.min_occurs
                    elif item.max_occurs is None or max_occurs < item.max_occurs or \
                            min_occurs + item.min_occurs > max_occurs:
                        continue
                    else:
                        min_occurs += item.min_occurs
                        max_occurs -= item.max_occurs

                    if not_emptiable_items:
                        if len(not_emptiable_items) > 1:
                            continue
                        if other_item not in not_emptiable_items:
                            continue

                    restriction_items.remove(item)
                    if not min_occurs or max_occurs == 0:
                        break

            if min_occurs < other_item.min_occurs:
                break
        else:
            if not restriction_items:
                return True

        if any(not isinstance(x, XsdGroup) for x in restriction_items):
            return False

        # If the remaining items are groups try to verify if they are all
        # restrictions of the 'all' group and if each group contains all
        # not emptiable elements.
        for group in restriction_items:
            if not group.is_restriction(other):
                return False

            for item in not_emptiable_items:
                for e in group:
                    if e.name == item.name:
                        break
                else:
                    return False
        else:
            return True

    def is_choice_restriction(self, other):
        restriction_items = list(self.iter_model())
        has_not_empty_item = any(e.max_occurs != 0 for e in restriction_items)

        check_occurs = other.max_occurs != 0
        max_occurs = 0
        other_max_occurs = 0
        for other_item in other.iter_model():
            for item in restriction_items:
                if other_item is item or item.is_restriction(other_item, check_occurs):
                    if max_occurs is not None:
                        effective_max_occurs = item.effective_max_occurs
                        if effective_max_occurs is None:
                            max_occurs = None
                        elif self.model == 'choice':
                            max_occurs = max(max_occurs, effective_max_occurs)
                        else:
                            max_occurs += effective_max_occurs

                    if other_max_occurs is not None:
                        effective_max_occurs = other_item.effective_max_occurs
                        if effective_max_occurs is None:
                            other_max_occurs = None
                        else:
                            other_max_occurs = max(other_max_occurs, effective_max_occurs)
                    break
                elif item.max_occurs != 0:
                    continue
                elif not other_item.is_matching(item.name, self.default_namespace):
                    continue
                elif has_not_empty_item:
                    break
                else:
                    return False
            else:
                continue
            restriction_items.remove(item)

        if restriction_items:
            return False
        elif other_max_occurs is None:
            if other.max_occurs != 0:
                return True
            other_max_occurs = 0
        elif other.max_occurs is None:
            if other_max_occurs != 0:
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
