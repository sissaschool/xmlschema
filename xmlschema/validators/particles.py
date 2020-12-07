#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#

class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t

    :ivar min_occurs: the minOccurs property of the XSD particle. Defaults to 1.
    :ivar max_occurs: the maxOccurs property of the XSD particle. Defaults to 1, \
    a `None` value means 'unbounded'.
    """
    min_occurs = 1
    max_occurs = 1

    def parse_error(self, message):
        raise NotImplementedError()

    @property
    def occurs(self):
        return [self.min_occurs, self.max_occurs]

    @property
    def effective_min_occurs(self):
        return self.min_occurs

    @property
    def effective_max_occurs(self):
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

    def is_missing(self, occurs):
        """Tests if provided occurrences are under the minimum."""
        return not self.is_emptiable() if occurs == 0 else self.min_occurs > occurs

    def is_over(self, occurs):
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

    def _parse_particle(self, elem):
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


class ParticleCounter:
    """
    An helper class for counting total min/max occurrences of XSD particles.
    """
    def __init__(self):
        self.min_occurs = self.max_occurs = 0

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.min_occurs, self.max_occurs)

    def __add__(self, other):
        self.min_occurs += other.min_occurs
        if self.max_occurs is not None:
            if other.max_occurs is None:
                self.max_occurs = None
            else:
                self.max_occurs += other.max_occurs
        return self

    def __mul__(self, other):
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

    def reset(self):
        self.min_occurs = self.max_occurs = 0
