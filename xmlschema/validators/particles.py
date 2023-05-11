#
# Copyright (c), 2016-2021  , SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import Any, Optional, Tuple, Union

from ..exceptions import XMLSchemaValueError
from ..aliases import ElementType, ModelParticleType
from ..translation import gettext as _


class ParticleMixin:
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t

    :ivar min_occurs: the minOccurs property of the XSD particle. Defaults to 1.
    :ivar max_occurs: the maxOccurs property of the XSD particle. Defaults to 1, \
    a `None` value means 'unbounded'.
    """
    name: Any
    maps: Any

    min_occurs: int = 1
    max_occurs: Optional[int] = 1

    def __init__(self, min_occurs: int = 1, max_occurs: Optional[int] = 1) -> None:
        self.min_occurs = min_occurs
        self.max_occurs = max_occurs

    @property
    def occurs(self) -> Tuple[int, Optional[int]]:
        return self.min_occurs, self.max_occurs

    @property
    def effective_min_occurs(self) -> int:
        """
        A property calculated from minOccurs, that is equal to minOccurs
        for elements and may vary for content model groups, in dependance
        of group model and structure. Used for checking restrictions of
        model groups in XSD 1.1.
        """
        return self.min_occurs

    @property
    def effective_max_occurs(self) -> Optional[int]:
        """
        A property calculated from maxOccurs, that is equal to maxOccurs
        for elements and may vary for content model groups, in dependance
        of group model and structure. Used for checking restrictions of
        model groups in XSD 1.1.
        """
        return self.max_occurs

    def is_emptiable(self) -> bool:
        """
        Tests if max_occurs == 0. A zero-length model group is considered emptiable.
        For model groups the test outcome depends also on nested particles.
        """
        return self.min_occurs == 0

    def is_empty(self) -> bool:
        """
        Tests if max_occurs == 0. A zero-length model group is considered empty.
        """
        return self.max_occurs == 0

    def is_single(self) -> bool:
        """
        Tests if the particle has max_occurs == 1. For elements the test
        outcome depends also on parent group. For model groups the test
        outcome depends also on nested model groups.
        """
        return self.max_occurs == 1

    def is_multiple(self) -> bool:
        """Tests the particle can have multiple occurrences."""
        return not self.is_empty() and not self.is_single()

    def is_ambiguous(self) -> bool:
        """Tests if min_occurs != max_occurs."""
        return self.min_occurs != self.max_occurs

    def is_univocal(self) -> bool:
        """Tests if min_occurs == max_occurs."""
        return self.min_occurs == self.max_occurs

    def is_missing(self, occurs: int) -> bool:
        """Tests if provided occurrences are under the minimum."""
        return not self.is_emptiable() if occurs == 0 else self.min_occurs > occurs

    def is_over(self, occurs: int) -> bool:
        """Tests if provided occurrences are over the maximum."""
        return self.max_occurs is not None and self.max_occurs <= occurs

    def has_occurs_restriction(self, other: Union[ModelParticleType, 'OccursCalculator']) -> bool:
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

    def parse_error(self, message: Any) -> None:
        raise XMLSchemaValueError(message)

    def _parse_particle(self, elem: ElementType) -> None:
        if 'minOccurs' in elem.attrib:
            try:
                min_occurs = int(elem.attrib['minOccurs'])
            except (TypeError, ValueError):
                msg = _("minOccurs value is not an integer value")
                self.parse_error(msg)
            else:
                if min_occurs < 0:
                    msg = _("minOccurs value must be a non negative integer")
                    self.parse_error(msg)
                else:
                    self.min_occurs = min_occurs

        max_occurs = elem.get('maxOccurs')
        if max_occurs is None:
            if self.min_occurs > 1:
                msg = _("minOccurs must be lesser or equal than maxOccurs")
                self.parse_error(msg)
        elif max_occurs == 'unbounded':
            self.max_occurs = None
        else:
            try:
                self.max_occurs = int(max_occurs)
            except ValueError:
                msg = _("maxOccurs value must be a non negative integer or 'unbounded'")
                self.parse_error(msg)
            else:
                if self.min_occurs > self.max_occurs:
                    msg = _("maxOccurs must be 'unbounded' or greater than minOccurs")
                    self.parse_error(msg)
                    self.max_occurs = None


class OccursCalculator:
    """
    A helper class for adding and multiplying min/max occurrences of XSD particles.
    """
    min_occurs: int
    max_occurs: Optional[int]

    def __init__(self) -> None:
        self.min_occurs = self.max_occurs = 0

    def __repr__(self) -> str:
        return '%s(%r, %r)' % (self.__class__.__name__, self.min_occurs, self.max_occurs)

    def __add__(self, other: ParticleMixin) -> 'OccursCalculator':
        self.min_occurs += other.min_occurs
        if self.max_occurs is not None:
            if other.max_occurs is None:
                self.max_occurs = None
            else:
                self.max_occurs += other.max_occurs
        return self

    def __mul__(self, other: ParticleMixin) -> 'OccursCalculator':
        self.min_occurs *= other.min_occurs
        if self.max_occurs is None:
            if other.max_occurs == 0:
                self.max_occurs = 0
        elif other.max_occurs is None:
            if self.max_occurs != 0:
                self.max_occurs = None
        else:
            self.max_occurs *= other.max_occurs
        return self

    def reset(self) -> None:
        self.min_occurs = self.max_occurs = 0
