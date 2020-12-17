#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections.abc import MutableSequence
from typing import Optional, List, Union
from xml.etree.ElementTree import Element

from .. import limits
from ..exceptions import XMLSchemaValueError
from .exceptions import XMLSchemaParseError, XMLSchemaModelError, XMLSchemaModelDepthError


class ParticleMixin:
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t

    :ivar min_occurs: the minOccurs property of the XSD particle. Defaults to 1.
    :ivar max_occurs: the maxOccurs property of the XSD particle. Defaults to 1, \
    a `None` value means 'unbounded'.
    """
    min_occurs: int = 1
    max_occurs: Optional[int] = 1

    def __init__(self, min_occurs=1, max_occurs: Optional[int] = 1):
        self.min_occurs = min_occurs
        self.max_occurs = max_occurs

    @property
    def occurs(self):
        return [self.min_occurs, self.max_occurs]

    @property
    def effective_min_occurs(self):
        """
        A property calculated from minOccurs, that is equal to minOccurs
        for elements and may vary for content model groups, in dependance
        of group model and structure.
        """
        return self.min_occurs

    @property
    def effective_max_occurs(self):
        """
        A property calculated from maxOccurs, that is equal to maxOccurs
        for elements and may vary for content model groups, in dependance
        of group model and structure. Used for checking restrictions of
        xs:choice model groups in XSD 1.1.
        """
        return self.max_occurs

    def is_emptiable(self):
        """
        Tests if max_occurs == 0. A zero-length model group is considered emptiable.
        For model groups the test outcome depends also on nested particles.
        """
        return self.min_occurs == 0

    def is_empty(self):
        """
        Tests if max_occurs == 0. A zero-length model group is considered empty.
        """
        return self.max_occurs == 0

    def is_single(self):
        """
        Tests if the particle has max_occurs == 1. For elements the test
        outcome depends also on parent group. For model groups the test
        outcome depends also on nested model groups.
        """
        return self.max_occurs == 1

    def is_multiple(self):
        """Tests the particle can have multiple occurrences."""
        return not self.is_empty() and not self.is_single()

    def is_ambiguous(self):
        """Tests if min_occurs != max_occurs."""
        return self.min_occurs != self.max_occurs

    def is_univocal(self):
        """Tests if min_occurs == max_occurs."""
        return self.min_occurs == self.max_occurs

    def is_missing(self, occurs: int):
        """Tests if provided occurrences are under the minimum."""
        return not self.is_emptiable() if occurs == 0 else self.min_occurs > occurs

    def is_over(self, occurs: int):
        """Tests if provided occurrences are over the maximum."""
        return self.max_occurs is not None and self.max_occurs <= occurs

    def has_occurs_restriction(self, other):
        if self.min_occurs < other.min_occurs:
            return False
        elif self.max_occurs == 0:
            return True
        elif other.max_occurs is None:
            return True
        elif self.max_occurs is None:
            return False
        else:
            return self.max_occurs <= other.max_occurs

    def parse_error(self, message):
        raise XMLSchemaParseError(self, message)  # pragma: no cover

    def _parse_particle(self, elem: Element):
        if 'minOccurs' in elem.attrib:
            try:
                min_occurs = int(elem.attrib['minOccurs'])
            except (TypeError, ValueError):
                self.parse_error("minOccurs value is not an integer value")
            else:
                if min_occurs < 0:
                    self.parse_error("minOccurs value must be a non negative integer")
                else:
                    self.min_occurs = min_occurs

        max_occurs = elem.get('maxOccurs')
        if max_occurs is None:
            if self.min_occurs > 1:
                self.parse_error("minOccurs must be lesser or equal than maxOccurs")
        elif max_occurs == 'unbounded':
            self.max_occurs = None
        else:
            try:
                max_occurs = int(max_occurs)
            except ValueError:
                self.parse_error("maxOccurs value must be a non negative integer or 'unbounded'")
            else:
                if self.min_occurs > max_occurs:
                    self.parse_error("maxOccurs must be 'unbounded' or greater than minOccurs")
                else:
                    self.max_occurs = max_occurs


class ModelGroup(MutableSequence, ParticleMixin):
    """
    Class for XSD model group particles. This class implements only model related methods,
    schema element parsing and validation methods are implemented in derived classes.
    """
    def __init__(self, model: str, min_occurs=1, max_occurs: Optional[int] = 1):
        super(ModelGroup, self).__init__(min_occurs, max_occurs)
        if model not in {'sequence', 'choice', 'all'}:
            raise XMLSchemaValueError("invalid model {!r} for a group".format(model))
        self._group: List[Union[tuple, ParticleMixin]] = []
        self.model = model

    def __repr__(self):
        return '%s(model=%r, occurs=%r)' % (self.__class__.__name__, self.model, self.occurs)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i: int):
        return self._group[i]

    def __setitem__(self, i: int, item: Union[tuple, ParticleMixin]):
        self._group[i] = item

    def __delitem__(self, i: int):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i: int, item: Union[tuple, ParticleMixin]):
        self._group.insert(i, item)

    def clear(self):
        del self._group[:]

    def is_emptiable(self):
        if self.model == 'choice':
            return self.min_occurs == 0 or not self or any(item.is_emptiable() for item in self)
        else:
            return self.min_occurs == 0 or not self or all(item.is_emptiable() for item in self)

    def is_empty(self):
        return not self._group or self.max_occurs == 0

    def is_single(self):
        if self.max_occurs != 1 or not self:
            return False
        elif len(self) > 1 or not isinstance(self[0], ModelGroup):
            return True
        else:
            return self[0].is_single()

    def is_pointless(self, parent: 'ModelGroup'):
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
    def effective_min_occurs(self):
        if not self.min_occurs or not self:
            return 0
        elif self.model == 'choice':
            if any(not e.effective_min_occurs for e in self.iter_model()):
                return 0
        else:
            if all(not e.effective_min_occurs for e in self.iter_model()):
                return 0
        return self.min_occurs

    @property
    def effective_max_occurs(self):
        if self.max_occurs == 0 or not self:
            return 0

        effective_items = list(e for e in self.iter_model() if e.effective_max_occurs != 0)
        if not effective_items:
            return 0
        elif self.max_occurs is None:
            return
        elif self.model == 'choice':
            if any(e.effective_max_occurs is None for e in effective_items):
                return
            return self.max_occurs * max(e.effective_max_occurs for e in effective_items)

        not_emptiable_items = [e for e in effective_items if e.effective_min_occurs]
        if not not_emptiable_items:
            if any(e.effective_max_occurs is None for e in effective_items):
                return
            return self.max_occurs * max(e.effective_max_occurs for e in effective_items)
        elif len(not_emptiable_items) > 1:
            return self.max_occurs

        try:
            return self.max_occurs * not_emptiable_items[0].effective_max_occurs
        except TypeError:
            return

    def has_occurs_restriction(self, other: 'ModelGroup'):
        if not self:
            return True
        elif isinstance(other, ModelGroup):
            return super(ModelGroup, self).has_occurs_restriction(other)

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
                return self.max_occurs * max(e.max_occurs for e in self) <= other.max_occurs

        else:
            if self.min_occurs * sum(e.min_occurs for e in self) < other.min_occurs:
                return False
            elif other.max_occurs is None:
                return True
            else:
                return self.max_occurs * sum(e.max_occurs for e in self) <= other.max_occurs

    def iter_model(self, depth=0):
        """
        A generator function iterating elements and groups of a model group.
        Skips pointless groups, iterating deeper through them.
        Raises `XMLSchemaModelDepthError` if the argument *depth* is over
        `limits.MAX_MODEL_DEPTH` value.

        :param depth: guard for protect model nesting bombs, incremented at each deepest recursion.
        """
        if depth > limits.MAX_MODEL_DEPTH:
            raise XMLSchemaModelDepthError(self)
        for item in self:
            if not isinstance(item, ModelGroup):
                yield item
            elif not item.is_pointless(parent=self):
                yield item
            else:
                yield from item.iter_model(depth + 1)

    def iter_elements(self, depth=0):
        """
        A generator function iterating model's elements. Raises `XMLSchemaModelDepthError`
        if the argument *depth* is over `limits.MAX_MODEL_DEPTH` value.

        :param depth: guard for protect model nesting bombs, incremented at each deepest recursion.
        """
        if depth > limits.MAX_MODEL_DEPTH:
            raise XMLSchemaModelDepthError(self)
        if self.max_occurs != 0:
            for item in self:
                if isinstance(item, ModelGroup):
                    yield from item.iter_elements(depth + 1)
                else:
                    yield item

    def get_subgroups(self, item: ParticleMixin) -> List['ModelGroup']:
        """
        Returns a list of the groups that represent the path to the enclosed particle.
        Raises an `XMLSchemaModelError` if *item* is not a particle of the model group.
        """
        subgroups = []
        group, children = self, iter(self)

        while True:
            try:
                child = next(children)
            except StopIteration:
                try:
                    group, children = subgroups.pop()
                except IndexError:
                    msg = '{!r} is not a particle of the model group'
                    raise XMLSchemaModelError(self, msg.format(item)) from None
                else:
                    continue

            if child is item:
                subgroups = [x[0] for x in subgroups]
                subgroups.append(group)
                return subgroups
            elif isinstance(child, ModelGroup):
                if len(subgroups) > limits.MAX_MODEL_DEPTH:
                    raise XMLSchemaModelDepthError(self)
                subgroups.append((group, children))
                group, children = child, iter(child)

    def overall_min_occurs(self, item: ParticleMixin) -> int:
        """Returns the overall min occurs of a particle in the model."""
        min_occurs = item.min_occurs

        for group in self.get_subgroups(item):
            if group.model == 'choice' and len(group) > 1:
                return 0
            min_occurs *= group.min_occurs

        return min_occurs

    def overall_max_occurs(self, item: ParticleMixin) -> Optional[int]:
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
