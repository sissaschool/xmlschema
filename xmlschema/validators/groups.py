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
from collections.abc import MutableMapping
from copy import copy as _copy
from typing import TYPE_CHECKING, cast, overload, Any, Iterable, Iterator, \
    List, MutableSequence, Optional, Tuple, Union
from xml.etree import ElementTree

from .. import limits
from ..exceptions import XMLSchemaValueError
from ..names import XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ELEMENT, \
    XSD_ANY, XSI_TYPE, XSD_ANY_TYPE, XSD_ANNOTATION
from ..aliases import ElementType, NamespacesType, SchemaType, IterDecodeType, \
    IterEncodeType, ModelParticleType, SchemaElementType, ComponentClassType
from ..translation import gettext as _
from ..helpers import get_qname, local_name, raw_xml_encode
from ..converters import ElementData

from .exceptions import XMLSchemaModelError, XMLSchemaModelDepthError, \
    XMLSchemaValidationError, XMLSchemaChildrenValidationError, \
    XMLSchemaTypeTableWarning
from .xsdbase import ValidationMixin, XsdComponent, XsdType
from .particles import ParticleMixin, OccursCalculator
from .elements import XsdElement, XsdAlternative
from .wildcards import XsdAnyElement, Xsd11AnyElement
from .models import ModelVisitor, iter_unordered_content, iter_collapsed_content

if TYPE_CHECKING:
    from .complex_types import XsdComplexType

ANY_ELEMENT = ElementTree.Element(
    XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })

GroupDecodeType = List[Tuple[Union[str, int], Any, Optional[SchemaElementType]]]
GroupEncodeType = Tuple[Optional[str], List[ElementType]]


class XsdGroup(XsdComponent, MutableSequence[ModelParticleType],
               ParticleMixin, ValidationMixin[ElementType, GroupDecodeType]):
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
    parent: Optional[Union['XsdComplexType', 'XsdGroup']]
    model: str
    mixed: bool = False
    ref: Optional['XsdGroup']
    restriction: Optional['XsdGroup'] = None

    # For XSD 1.1 openContent processing
    interleave: Optional[Xsd11AnyElement] = None  # if openContent with mode='interleave'
    suffix: Optional[Xsd11AnyElement] = None  # if openContent with mode='suffix'/'interleave'

    _ADMITTED_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[Union['XsdComplexType', 'XsdGroup']] = None) -> None:

        self._group: List[ModelParticleType] = []
        if parent is not None and parent.mixed:
            self.mixed = parent.mixed
        super(XsdGroup, self).__init__(elem, schema, parent)

    def __repr__(self) -> str:
        if self.name is None:
            return '%s(model=%r, occurs=%r)' % (
                self.__class__.__name__, self.model, list(self.occurs)
            )
        elif self.ref is None:
            return '%s(name=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, list(self.occurs)
            )
        else:
            return '%s(ref=%r, model=%r, occurs=%r)' % (
                self.__class__.__name__, self.prefixed_name, self.model, list(self.occurs)
            )

    @overload
    def __getitem__(self, i: int) -> ModelParticleType: ...

    @overload
    def __getitem__(self, s: slice) -> MutableSequence[ModelParticleType]: ...

    def __getitem__(self, i: Union[int, slice]) \
            -> Union[ModelParticleType, MutableSequence[ModelParticleType]]:
        return self._group[i]

    def __setitem__(self, i: Union[int, slice], o: Any) -> None:
        self._group[i] = o

    def __delitem__(self, i: Union[int, slice]) -> None:
        del self._group[i]

    def __len__(self) -> int:
        return len(self._group)

    def insert(self, i: int, item: ModelParticleType) -> None:
        self._group.insert(i, item)

    def clear(self) -> None:
        del self._group[:]

    def is_emptiable(self) -> bool:
        if self.model == 'choice':
            return self.min_occurs == 0 or not self or any(item.is_emptiable() for item in self)
        else:
            return self.min_occurs == 0 or not self or all(item.is_emptiable() for item in self)

    def is_single(self) -> bool:
        if self.max_occurs != 1 or not self:
            return False
        elif len(self) > 1 or not isinstance(self[0], XsdGroup):
            return True
        else:
            return self[0].is_single()

    def is_pointless(self, parent: 'XsdGroup') -> bool:
        """
        Returns `True` if the group may be eliminated without affecting the model,
        `False` otherwise. A group is pointless if one of those conditions is verified:

         - the group is empty
         - minOccurs == maxOccurs == 1 and the group has one child
         - minOccurs == maxOccurs == 1 and the group and its parent have a sequence model
         - minOccurs == maxOccurs == 1 and the group and its parent have a choice model

        Ref: https://www.w3.org/TR/2004/REC-xmlschema-1-20041028/#coss-particle

        :param parent: effective parent of the model group.
        """
        if not self:
            return True
        elif self.min_occurs != 1 or self.max_occurs != 1:
            return False
        elif len(self) == 1:
            return True
        elif self.model == 'sequence' and parent.model != 'sequence':
            return False
        elif self.model == 'choice' and parent.model != 'choice':
            return False
        else:
            return True

    @property
    def effective_min_occurs(self) -> int:
        if not self.min_occurs or not self:
            return 0

        effective_items: List[Any]
        min_occurs: int
        effective_items = [e for e in self.iter_model() if e.effective_max_occurs != 0]
        if not effective_items:
            return 0
        elif self.model == 'choice':
            min_occurs = min(e.effective_min_occurs for e in effective_items)
            return self.min_occurs * min_occurs
        elif self.model == 'all':
            min_occurs = max(e.effective_min_occurs for e in effective_items)
            return min_occurs

        not_emptiable_items = [e for e in effective_items if e.effective_min_occurs]
        if not not_emptiable_items:
            return 0
        elif len(not_emptiable_items) > 1:
            return self.min_occurs

        min_occurs = not_emptiable_items[0].effective_min_occurs
        return self.min_occurs * min_occurs

    @property
    def effective_max_occurs(self) -> Optional[int]:
        if self.max_occurs == 0 or not self:
            return 0

        effective_items: List[Any]
        max_occurs: int

        model_items = [(e, e.effective_max_occurs) for e in self.iter_model()]
        effective_items = [x for x in model_items if x[1] != 0]
        if not effective_items:
            return 0
        elif self.max_occurs is None:
            return None
        elif self.model == 'choice':
            if any(x[1] is None for x in effective_items):
                return None
            else:
                max_occurs = max(x[1] for x in effective_items)
                return self.max_occurs * max_occurs

        not_emptiable_items = [x for x in effective_items if x[0].effective_min_occurs]
        if not not_emptiable_items:
            if any(x[1] is None for x in effective_items):
                return None
            else:
                max_occurs = max(x[1] for x in effective_items)
                return self.max_occurs * max_occurs

        elif len(not_emptiable_items) > 1:
            if self.model == 'sequence':
                return self.max_occurs
            elif all(x[1] is None for x in not_emptiable_items):
                return None
            else:
                max_occurs = min(x[1] for x in not_emptiable_items if x[1] is not None)
                return max_occurs
        elif not_emptiable_items[0][1] is None:
            return None
        else:
            return self.max_occurs * cast(int, not_emptiable_items[0][1])

    def has_occurs_restriction(
            self, other: Union[ModelParticleType, ParticleMixin, 'OccursCalculator']) -> bool:

        if not self:
            return True
        elif isinstance(other, XsdGroup):
            return super(XsdGroup, self).has_occurs_restriction(other)

        # Group particle compared to element particle
        if self.max_occurs is None or any(e.max_occurs is None for e in self):
            if other.max_occurs is not None:
                return False
            elif self.model == 'choice':
                return self.min_occurs * min(e.min_occurs for e in self) >= other.min_occurs
            else:
                return self.min_occurs * sum(e.min_occurs for e in self) >= other.min_occurs

        elif self.model == 'choice':
            if self.min_occurs * min(e.min_occurs for e in self) < other.min_occurs:
                return False
            elif other.max_occurs is None:
                return True
            else:
                value: int
                try:
                    value = max(e.max_occurs for e in self)  # type: ignore[type-var, assignment]
                except TypeError:
                    return False
                else:
                    return self.max_occurs * value <= other.max_occurs

        else:
            if self.min_occurs * sum(e.min_occurs for e in self) < other.min_occurs:
                return False
            elif other.max_occurs is None:
                return True
            else:
                try:
                    value = sum(e.max_occurs for e in self)  # type: ignore[misc]
                except TypeError:
                    return False
                else:
                    return self.max_occurs * value <= other.max_occurs

    def iter_model(self) -> Iterator[ModelParticleType]:
        """
        A generator function iterating elements and groups of a model group.
        Skips pointless groups, iterating deeper through them.
        Raises `XMLSchemaModelDepthError` if the *depth* of the model is over
        `limits.MAX_MODEL_DEPTH` value.
        """
        iterators: List[Iterator[ModelParticleType]] = []
        particles = iter(self)

        while True:
            for item in particles:
                if isinstance(item, XsdGroup) and item.is_pointless(parent=self):
                    iterators.append(particles)
                    particles = iter(item)
                    if len(iterators) > limits.MAX_MODEL_DEPTH:
                        raise XMLSchemaModelDepthError(self)
                    break
                else:
                    yield item
            else:
                try:
                    particles = iterators.pop()
                except IndexError:
                    return

    def iter_elements(self) -> Iterator[SchemaElementType]:
        """
        A generator function iterating model's elements. Raises `XMLSchemaModelDepthError`
        if the overall depth of the model groups is over `limits.MAX_MODEL_DEPTH`.
        """
        if self.max_occurs == 0:
            return

        iterators: List[Iterator[ModelParticleType]] = []
        particles = iter(self)

        while True:
            for item in particles:
                if isinstance(item, XsdGroup):
                    iterators.append(particles)
                    particles = iter(item)
                    if len(iterators) > limits.MAX_MODEL_DEPTH:
                        raise XMLSchemaModelDepthError(self)
                    break
                else:
                    yield item
            else:
                try:
                    particles = iterators.pop()
                except IndexError:
                    return

    def get_subgroups(self, item: ModelParticleType) -> List['XsdGroup']:
        """
        Returns a list of the groups that represent the path to the enclosed particle.
        Raises an `XMLSchemaModelError` if *item* is not a particle of the model group.
        """
        subgroups: List[Tuple[XsdGroup, Iterator[ModelParticleType]]] = []
        group, children = self, iter(self)

        while True:
            for child in children:
                if child is item:
                    _subgroups = [x[0] for x in subgroups]
                    _subgroups.append(group)
                    return _subgroups
                elif isinstance(child, XsdGroup):
                    if len(subgroups) > limits.MAX_MODEL_DEPTH:
                        raise XMLSchemaModelDepthError(self)
                    subgroups.append((group, children))
                    group, children = child, iter(child)
                    break
            else:
                try:
                    group, children = subgroups.pop()
                except IndexError:
                    msg = _('{!r} is not a particle of the model group')
                    raise XMLSchemaModelError(self, msg.format(item)) from None

    def overall_min_occurs(self, item: ModelParticleType) -> int:
        """Returns the overall min occurs of a particle in the model."""
        min_occurs = item.min_occurs

        for group in self.get_subgroups(item):
            if group.model == 'choice' and len(group) > 1:
                return 0
            min_occurs *= group.min_occurs

        return min_occurs

    def overall_max_occurs(self, item: ModelParticleType) -> Optional[int]:
        """Returns the overall max occurs of a particle in the model."""
        max_occurs = item.max_occurs

        for group in self.get_subgroups(item):
            if max_occurs == 0:
                return 0
            elif max_occurs is None:
                continue
            elif group.max_occurs is None:
                max_occurs = None
            else:
                max_occurs *= group.max_occurs

        return max_occurs

    def copy(self) -> 'XsdGroup':
        group: XsdGroup = object.__new__(self.__class__)
        group.__dict__.update(self.__dict__)
        group.errors = self.errors[:]
        group._group = self._group[:]
        return group

    __copy__ = copy

    def _parse(self) -> None:
        self.clear()
        self._parse_particle(self.elem)

        if self.elem.tag != XSD_GROUP:
            # Local group (sequence|all|choice)
            if 'name' in self.elem.attrib:
                msg = _("attribute 'name' not allowed in a local group")
                self.parse_error(msg)
            self._parse_content_model(self.elem)

        elif self._parse_reference():
            assert self.name is not None
            try:
                xsd_group = self.maps.lookup_group(self.name)
            except KeyError:
                self.parse_error(_("missing group %r") % self.prefixed_name)
                xsd_group = self.schema.create_any_content_group(parent=self)

            if isinstance(xsd_group, XsdGroup):
                self.model = xsd_group.model
                if self.model == 'all':
                    if self.max_occurs != 1:
                        msg = _("maxOccurs must be 1 for 'all' model groups")
                        self.parse_error(msg)
                    if self.min_occurs not in (0, 1):
                        msg = _("minOccurs must be (0 | 1) for 'all' model groups")
                        self.parse_error(msg)
                    if self.xsd_version == '1.0' and isinstance(self.parent, XsdGroup):
                        msg = _("in XSD 1.0 an 'all' model group cannot be nested")
                        self.parse_error(msg)
                self._group.append(xsd_group)
                self.ref = xsd_group
            else:
                # Disallowed circular definition, substitute with any content group.
                msg = _("Circular definition detected for group %r")
                self.parse_error(msg % self.name, xsd_group[0])
                self.model = 'sequence'
                self.mixed = True
                self._group.append(self.schema.xsd_any_class(ANY_ELEMENT, self.schema, self))

        else:
            attrib = self.elem.attrib
            try:
                self.name = get_qname(self.target_namespace, attrib['name'])
            except KeyError:
                pass
            else:
                if self.parent is not None:
                    msg = _("attribute 'name' not allowed in a local group")
                    self.parse_error(msg)
                else:
                    if 'minOccurs' in attrib:
                        msg = _("attribute 'minOccurs' not allowed in a global group")
                        self.parse_error(msg)
                    if 'maxOccurs' in attrib:
                        msg = _("attribute 'maxOccurs' not allowed in a global group")
                        self.parse_error(msg)

                content_model = self._parse_child_component(self.elem, strict=True)
                if content_model is not None:
                    if self.parent is None:
                        if 'minOccurs' in content_model.attrib:
                            msg = _("attribute 'minOccurs' not allowed in a global group")
                            self.parse_error(msg, content_model)
                        if 'maxOccurs' in content_model.attrib:
                            msg = _("attribute 'maxOccurs' not allowed in a global group")
                            self.parse_error(msg, content_model)

                    if content_model.tag in {XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
                        self._parse_content_model(content_model)
                    else:
                        msg = _('unexpected tag %r')
                        self.parse_error(msg % content_model.tag, content_model)

    def _parse_content_model(self, content_model: ElementType) -> None:
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs != 1:
                msg = _("maxOccurs must be 1 for 'all' model groups")
                self.parse_error(msg)
            if self.min_occurs not in (0, 1):
                msg = _("minOccurs must be (0 | 1) for 'all' model groups")
                self.parse_error(msg)

        child: ElementType
        for child in content_model:
            if child.tag == XSD_ANNOTATION or callable(child.tag):
                continue
            elif child.tag == XSD_ELEMENT:
                # Builds inner elements later, for avoid circularity.
                self.append(self.schema.xsd_element_class(child, self.schema, self, False))
            elif content_model.tag == XSD_ALL:
                self.parse_error(_("'all' model can contain only elements"))
            elif child.tag == XSD_ANY:
                self._group.append(XsdAnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE):
                self._group.append(XsdGroup(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except (KeyError, ValueError, RuntimeError) as err:
                    if 'ref' not in child.attrib:
                        msg = _("missing attribute 'ref' in local group")
                        self.parse_error(msg, child)
                    else:
                        self.parse_error(err, child)
                    continue

                if ref != self.name:
                    xsd_group = XsdGroup(child, self.schema, self)
                    if xsd_group.model == 'all':
                        msg = _("'all' model can appears only at 1st level of a model group")
                        self.parse_error(msg)
                    else:
                        self._group.append(xsd_group)
                elif self.redefine is None:
                    msg = _("Circular definition detected for group %r")
                    self.parse_error(msg % self.name)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        msg = _("Redefined group reference cannot have "
                                "minOccurs/maxOccurs other than 1")
                        self.parse_error(msg)
                    self._group.append(self.redefine)

    def build(self) -> None:
        for item in self._group:
            if isinstance(item, XsdElement):
                item.build()

        if self.redefine is not None:
            for group in self.redefine.iter_components(XsdGroup):
                group.build()

    @property
    def built(self) -> bool:
        for item in self:
            if isinstance(item, XsdElement):
                if not item.built:
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
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif any(item.validation_attempted == 'partial' for item in self):
            return 'partial'
        else:
            return 'none'

    @property
    def schema_elem(self) -> ElementType:
        return self.parent.elem if self.parent is not None else self.elem

    def iter_components(self, xsd_classes: Optional[ComponentClassType] = None) \
            -> Iterator[XsdComponent]:
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

    def admits_restriction(self, model: str) -> bool:
        if self.model == model:
            return True
        elif self.model == 'all':
            return model == 'sequence'
        elif self.model == 'choice':
            return model == 'sequence' or len(self.ref or self) <= 1
        else:
            return model == 'choice' or len(self.ref or self) <= 1

    def is_empty(self) -> bool:
        return not self.mixed and (not self._group or self.max_occurs == 0)

    def is_restriction(self, other: ModelParticleType, check_occurs: bool = True) -> bool:
        if not self._group:
            return True
        elif not isinstance(other, ParticleMixin):
            raise XMLSchemaValueError("the argument 'other' must be an XSD particle")
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
        else:  # other.model == 'choice':
            return self.is_choice_restriction(other)

    def is_element_restriction(self, other: ModelParticleType) -> bool:
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
            min_occurs = 0
            max_occurs: Optional[int] = 0
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

    def is_sequence_restriction(self, other: 'XsdGroup') -> bool:
        if not self.has_occurs_restriction(other):
            return False

        check_occurs = other.max_occurs != 0

        # Same model: declarations must simply preserve order
        other_iterator = iter(other.iter_model())
        for item in self.iter_model():
            for other_item in other_iterator:
                if other_item is item or item.is_restriction(other_item, check_occurs):
                    break
                elif other.model == 'choice':
                    if item.max_occurs != 0:
                        continue
                    elif not other_item.is_matching(item.name):
                        continue
                    elif all(e.max_occurs == 0 for e in self.iter_model()):
                        return False
                    else:
                        break
                elif not other_item.is_emptiable():
                    return False
            else:
                return False

        if other.model != 'choice':
            for other_item in other_iterator:
                if not other_item.is_emptiable():
                    return False
        return True

    def is_all_restriction(self, other: 'XsdGroup') -> bool:
        if not self.has_occurs_restriction(other):
            return False

        check_occurs = other.max_occurs != 0
        if self.ref is None:
            restriction_items = [x for x in self]
        else:
            restriction_items = [x for x in self[0]]

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

    def is_choice_restriction(self, other: 'XsdGroup') -> bool:
        if self.ref is None:
            if self.parent is None and other.parent is not None:
                return False  # not allowed restriction in XSD 1.0
            restriction_items = [x for x in self]
        elif other.parent is None:
            restriction_items = [x for x in self[0]]
        else:
            return False  # not allowed restriction in XSD 1.0

        check_occurs = other.max_occurs != 0
        max_occurs: Optional[int] = 0
        other_max_occurs: Optional[int] = 0

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

    def check_dynamic_context(self, elem: ElementType,
                              xsd_element: SchemaElementType,
                              model_element: SchemaElementType,
                              namespaces: NamespacesType) -> None:

        if model_element is not xsd_element and isinstance(model_element, XsdElement):
            if 'substitution' in model_element.block \
                    or xsd_element.type and xsd_element.type.is_blocked(model_element):
                reason = _("substitution of %r is blocked") % model_element
                raise XMLSchemaValidationError(model_element, elem, reason)

        alternatives: Union[Tuple[()], List[XsdAlternative]] = []
        if isinstance(xsd_element, XsdAnyElement):
            if xsd_element.process_contents == 'skip':
                return

            try:
                xsd_element = self.maps.lookup_element(elem.tag)
            except LookupError:
                if self.schema.meta_schema is None:
                    # Meta-schema groups ignore xsi:type (issue #350)
                    return

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
            if XSI_TYPE not in elem.attrib or self.schema.meta_schema is None:
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

            if model_element is not xsd_element and \
                    isinstance(model_element, XsdElement) and model_element.block:
                for derivation in model_element.block.split():
                    if xsd_type is not model_element.type and \
                            xsd_type.is_derived(model_element.type, derivation):
                        reason = _("usage of {0!r} with type {1} is blocked by "
                                   "head element").format(xsd_element, derivation)
                        raise XMLSchemaValidationError(self, elem, reason)

            if XSI_TYPE not in elem.attrib or self.schema.meta_schema is None:
                return

        # If it's a restriction the context is the base_type's group
        group = self.restriction if self.restriction is not None else self

        # Dynamic EDC check of matched element
        for e in group.iter_elements():
            if not isinstance(e, XsdElement):
                continue
            elif e.name == elem.tag:
                other = e
            else:
                for other in e.iter_substitutes():
                    if other.name == elem.tag:
                        break
                else:
                    continue

            if len(other.alternatives) != len(alternatives) or \
                    not xsd_type.is_dynamic_consistent(other.type):
                reason = _("{0!r} that matches {1!r} is not consistent with local "
                           "declaration {2!r}").format(elem, xsd_element, other)
                raise XMLSchemaValidationError(self, reason)

            if not all(any(a == x for x in alternatives) for a in other.alternatives) or \
                    not all(any(a == x for x in other.alternatives) for a in alternatives):
                msg = _("Maybe a not equivalent type table between elements "
                        "{0!r} and {1!r}.").format(self, xsd_element)
                warnings.warn(msg, XMLSchemaTypeTableWarning, stacklevel=3)

    def match_element(self, name: str) -> Optional[SchemaElementType]:
        """
        Try a model-less match of a child element. Returns the
        matched element, or `None` if there is no match.
        """
        for xsd_element in self.iter_elements():
            if xsd_element.is_matching(name, group=self):
                return xsd_element
        return None

    def iter_decode(self, obj: ElementType, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[GroupDecodeType]:
        """
        Creates an iterator for decoding an Element content.

        :param obj: an Element.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a list of 3-tuples (key, decoded data, decoder), \
        eventually preceded by a sequence of validation or decoding errors.
        """
        result_list: GroupDecodeType = []
        cdata_index = 1  # keys for CDATA sections are positive integers

        if not self._group and self.model == 'choice' and self.min_occurs:
            reason = _("an empty 'choice' group with minOccurs > 0 cannot validate any content")
            yield self.validation_error(validation, reason, obj, **kwargs)
            yield result_list
            return

        if not self.mixed:
            # Check element CDATA
            if obj.text and obj.text.strip() or \
                    any(child.tail and child.tail.strip() for child in obj):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] equals to an empty complexType declaration
                else:
                    reason = _("character data between child elements not allowed")
                    yield self.validation_error(validation, reason, obj, **kwargs)
                    cdata_index = 0  # Do not decode CDATA

        if cdata_index and obj.text is not None:
            text = str(obj.text.strip())
            if text:
                result_list.append((cdata_index, text, None))
                cdata_index += 1

        level = kwargs['level'] = kwargs.pop('level', 0) + 1
        over_max_depth = 'max_depth' in kwargs and kwargs['max_depth'] <= level
        if level > limits.MAX_XML_DEPTH:
            reason = _("XML data depth exceeded (MAX_XML_DEPTH=%r)") % limits.MAX_XML_DEPTH
            self.validation_error('strict', reason, obj, **kwargs)

        try:
            namespaces = kwargs['namespaces']
        except KeyError:
            namespaces = default_namespace = None
        else:
            try:
                default_namespace = namespaces.get('')
            except AttributeError:
                default_namespace = None

        errors: List[Tuple[int, ModelParticleType, int, Optional[List[SchemaElementType]]]]
        xsd_element: Optional[SchemaElementType]
        expected: Optional[List[SchemaElementType]]

        model = ModelVisitor(self)
        errors = []
        broken_model = False

        for index, child in enumerate(obj):
            if callable(child.tag):
                continue  # child is a <class 'lxml.etree._Comment'>

            while model.element is not None:
                if model.element.max_occurs == 0:
                    xsd_element = None
                else:
                    xsd_element = model.element.match(
                        child.tag, group=self, occurs=model.occurs
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
                        xsd_element = self.match_element(child.tag)
                        break
                    else:
                        continue
                    break

                try:
                    self.check_dynamic_context(child, xsd_element, model.element, namespaces)
                except XMLSchemaValidationError as err:
                    yield self.validation_error(validation, err, obj, **kwargs)

                for particle, occurs, expected in model.advance(True):
                    errors.append((index, particle, occurs, expected))
                break
            else:
                if self.suffix is not None and \
                        self.suffix.is_matching(child.tag, default_namespace, self):
                    xsd_element = self.suffix
                else:
                    xsd_element = self.match_element(child.tag)
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
                    func = kwargs['depth_filler']
                    result_list.append((child.tag, func(xsd_element), xsd_element))
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
            index = len(obj)
            for particle, occurs, expected in model.stop():
                errors.append((index, particle, occurs, expected))

        if errors:
            source = kwargs.get('source')
            for index, particle, occurs, expected in errors:
                error = XMLSchemaChildrenValidationError(
                    self, obj, index, particle, occurs, expected, source, namespaces
                )
                if validation == 'strict':
                    raise error
                yield error

        yield result_list

    def iter_encode(self, obj: ElementData, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[GroupEncodeType]:
        """
        Creates an iterator for encoding data to a list containing Element data.

        :param obj: an ElementData instance.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields a couple with the text of the Element and a list of child \
        elements, eventually preceded by a sequence of validation errors.
        """
        level = kwargs['level'] = kwargs.get('level', 0) + 1
        errors = []
        text = raw_xml_encode(obj.text)
        children: List[ElementType] = []
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
        over_max_depth = 'max_depth' in kwargs and kwargs['max_depth'] <= level

        content: Iterable[Any]
        if not obj.content:
            content = []
        elif isinstance(obj.content, MutableMapping) or kwargs.get('unordered'):
            content = iter_unordered_content(obj.content, self, default_namespace)
        elif not isinstance(obj.content, MutableSequence):
            wrong_content_type = True
            content = []
        elif not isinstance(obj.content[0], tuple):
            if len(obj.content) > 1 or text is not None:
                wrong_content_type = True
            else:
                text = raw_xml_encode(obj.content[0])
            content = []
        elif converter.losslessly:
            content = obj.content
        else:
            content = iter_collapsed_content(obj.content, self, default_namespace)

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

            xsd_element: Optional[SchemaElementType]
            if self.interleave and self.interleave.is_matching(name, default_namespace, group=self):
                xsd_element = self.interleave
                value = get_qname(default_namespace, name), value
            else:
                while model.element is not None:
                    if model.element.max_occurs == 0:
                        xsd_element = None
                    else:
                        xsd_element = model.element.match(
                            name, group=self, occurs=model.occurs
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
                        xsd_element = self.match_element(name)
                        if isinstance(xsd_element, XsdAnyElement):
                            value = get_qname(default_namespace, name), value
                        elif xsd_element is None:
                            if name.startswith('{') or ':' not in name:
                                reason = _('{!r} does not match any declared element '
                                           'of the model group').format(name)
                            else:
                                reason = _('{0} has an unknown prefix {1!r}').format(
                                    name, name.split(':')[0]
                                )
                            yield self.validation_error(validation, reason, value, **kwargs)
                            continue

            if over_max_depth:
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

        cdata_not_allowed = not self.mixed and text and text.strip() and self and \
            (len(self) > 1 or not isinstance(self[0], XsdAnyElement))

        if errors or cdata_not_allowed or wrong_content_type:
            attrib = {k: raw_xml_encode(v) for k, v in obj.attributes.items()}
            elem = converter.etree_element(obj.tag, text, children, attrib)

            if wrong_content_type:
                reason = _("wrong content type {!r}").format(type(obj.content))
                yield self.validation_error(validation, reason, elem, **kwargs)

            if cdata_not_allowed:
                reason = _("character data between child elements not allowed")
                yield self.validation_error(validation, reason, elem, **kwargs)

            for index, particle, occurs, expected in errors:
                error = XMLSchemaChildrenValidationError(
                    validator=self,
                    elem=elem,
                    index=index,
                    particle=particle,
                    occurs=occurs,
                    expected=expected,
                    namespaces=converter.namespaces,
                )
                if validation == 'strict':
                    raise error

                error.elem = None  # replace with the element of the encoded tree
                yield error

        yield text, children


class Xsd11Group(XsdGroup):
    """
    Class for XSD 1.1 *model group* definitions.

    .. The XSD 1.1 model groups differ from XSD 1.0 groups for the 'all' model,
       that can contains also other groups.
    ..  <all
          id = ID
          maxOccurs = (0 | 1) : 1
          minOccurs = (0 | 1) : 1
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (element | any | group)*)
        </all>
    """
    def _parse_content_model(self, content_model: ElementType) -> None:
        self.model = local_name(content_model.tag)
        if self.model == 'all':
            if self.max_occurs not in (0, 1):
                msg = _("maxOccurs must be (0 | 1) for 'all' model groups")
                self.parse_error(msg)
            if self.min_occurs not in (0, 1):
                msg = _("minOccurs must be (0 | 1) for 'all' model groups")
                self.parse_error(msg)

        for child in content_model:
            if child.tag == XSD_ELEMENT:
                # Builds inner elements later, for avoid circularity.
                self.append(self.schema.xsd_element_class(child, self.schema, self, False))
            elif child.tag == XSD_ANY:
                self._group.append(Xsd11AnyElement(child, self.schema, self))
            elif child.tag in (XSD_SEQUENCE, XSD_CHOICE, XSD_ALL):
                self._group.append(Xsd11Group(child, self.schema, self))
            elif child.tag == XSD_GROUP:
                try:
                    ref = self.schema.resolve_qname(child.attrib['ref'])
                except (KeyError, ValueError, RuntimeError) as err:
                    if 'ref' not in child.attrib:
                        msg = _("missing attribute 'ref' in local group")
                        self.parse_error(msg, child)
                    else:
                        self.parse_error(err, child)
                    continue

                if ref != self.name:
                    xsd_group = Xsd11Group(child, self.schema, self)
                    self._group.append(xsd_group)
                    if (self.model != 'all') ^ (xsd_group.model != 'all'):
                        msg = _("an xs:{0} group cannot include a reference to an "
                                "xs:{1} group").format(self.model, xsd_group.model)
                        self.parse_error(msg)
                        self.pop()

                elif self.redefine is None:
                    msg = _("Circular definition detected for group %r")
                    self.parse_error(msg % self.name)
                else:
                    if child.get('minOccurs', '1') != '1' or child.get('maxOccurs', '1') != '1':
                        msg = _("Redefined group reference cannot have "
                                "minOccurs/maxOccurs other than 1")
                        self.parse_error(msg)
                    self._group.append(self.redefine)

    def admits_restriction(self, model: str) -> bool:
        if self.model == model or self.model == 'all':
            return True
        elif self.model == 'choice':
            return model == 'sequence' or len(self.ref or self) <= 1
        else:
            return model == 'choice' or len(self.ref or self) <= 1

    def is_restriction(self, other: ModelParticleType, check_occurs: bool = True) -> bool:
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
        else:  # other.model == 'choice':
            return self.is_choice_restriction(other)

    def has_occurs_restriction(
            self, other: Union[ModelParticleType, ParticleMixin, 'OccursCalculator']) -> bool:
        if not isinstance(other, XsdGroup):
            return super().has_occurs_restriction(other)
        elif not self:
            return True
        elif self.effective_min_occurs < other.effective_min_occurs:
            return False

        effective_max_occurs = self.effective_max_occurs
        if effective_max_occurs == 0:
            return True
        elif effective_max_occurs is None:
            return other.effective_max_occurs is None

        try:
            return effective_max_occurs <= other.effective_max_occurs  # type: ignore[operator]
        except TypeError:
            return True

    def is_sequence_restriction(self, other: XsdGroup) -> bool:
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
                break
        else:
            if item is None:
                return True

        # Restriction check failed again: try checking other items against self
        other_items = other.iter_model()
        for other_item in other_items:
            if self.is_restriction(other_item, check_occurs):
                return all(x.is_emptiable() for x in other_items)
            elif not other_item.is_emptiable():
                return False
        else:
            return False

    def is_all_restriction(self, other: XsdGroup) -> bool:
        restriction_items = [x for x in self.iter_model()]

        base_items = [x for x in other.iter_model()]

        # If the base includes more wildcard, calculates and appends a
        # wildcard union for validating wildcard unions in restriction
        wildcards: List[XsdAnyElement] = []
        for w1 in base_items:
            if isinstance(w1, XsdAnyElement):
                for w2 in wildcards:
                    if w1.process_contents == w2.process_contents and w1.occurs == w2.occurs:
                        w2.union(w1)
                        w2.extended = True
                        break
                else:
                    wildcards.append(_copy(w1))

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
                        if not isinstance(other_item, XsdGroup) and other_item.type \
                                and other_item.type.name != XSD_ANY_TYPE:

                            for w in restriction_wildcards:
                                if w.is_matching(other_item.name, self.target_namespace):
                                    return False

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

    def is_choice_restriction(self, other: XsdGroup) -> bool:
        restriction_items = [x for x in self.iter_model()]
        has_not_empty_item = any(e.max_occurs != 0 for e in restriction_items)

        check_occurs = other.max_occurs != 0
        max_occurs: Optional[int] = 0
        other_max_occurs: Optional[int] = 0

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
                elif not other_item.is_matching(item.name):
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
