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
This module contains classes and functions for processing XSD content models.
"""
from __future__ import unicode_literals
from collections import Counter

from ..compat import PY3, MutableSequence
from ..exceptions import XMLSchemaValueError
from .exceptions import XMLSchemaModelError, XMLSchemaModelDepthError
from .xsdbase import ParticleMixin

MAX_MODEL_DEPTH = 15
"""Limit depth for safe visiting of models"""

XSD_GROUP_MODELS = {'sequence', 'choice', 'all'}


class ModelGroup(MutableSequence, ParticleMixin):
    """
    Class for XSD model group particles. This class implements only model related methods,
    schema element parsing and validation methods are implemented in derived classes.
    """
    def __init__(self, model):
        assert model in XSD_GROUP_MODELS, "Not a valid value for 'model'"
        self._group = []
        self.model = model

    def __repr__(self):
        return '%s(model=%r, occurs=%r)' % (self.__class__.__name__, self.model, self.occurs)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        assert isinstance(item, (tuple, ParticleMixin)), "Items must be tuples or XSD particles"
        self._group[i] = item

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        assert isinstance(item, (tuple, ParticleMixin)), "Items must be tuples or XSD particles"
        self._group.insert(i, item)

    def __setattr__(self, name, value):
        if name == 'model' and value is not None:
            if value not in XSD_GROUP_MODELS:
                raise XMLSchemaValueError("invalid model group %r." % value)
            if self.model is not None and value != self.model and self.model != 'all':
                raise XMLSchemaValueError("cannot change group model from %r to %r" % (self.model, value))
        elif name == '_group':
            if not all(isinstance(item, (tuple, ParticleMixin)) for item in value):
                raise XMLSchemaValueError("XsdGroup's items must be tuples or ParticleMixin instances.")
        super(ModelGroup, self).__setattr__(name, value)

    def clear(self):
        del self._group[:]

    def is_emptiable(self):
        if self.model == 'choice':
            return self.min_occurs == 0 or not self or any([item.is_emptiable() for item in self])
        else:
            return self.min_occurs == 0 or not self or all([item.is_emptiable() for item in self])

    def is_empty(self):
        return not self._group or self.max_occurs == 0

    def is_pointless(self, parent):
        """
        Returns `True` if the group may be eliminated without affecting the model, `False` otherwise.
        A group is pointless if one of those conditions is verified:

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
        elif not isinstance(parent, ModelGroup):
            return False
        elif self.model == 'sequence' and parent.model != 'sequence':
            return False
        elif self.model == 'choice' and parent.model != 'choice':
            return False
        else:
            return True

    def has_occurs_restriction(self, other):
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
        A generator function iterating elements and groups of a model group. Skips pointless groups,
        iterating deeper through them. Raises `XMLSchemaModelDepthError` if the argument *depth* is
        over `MAX_MODEL_DEPTH` value.

        :param depth: guard for protect model nesting bombs, incremented at each deepest recursion.
        """
        if depth > MAX_MODEL_DEPTH:
            raise XMLSchemaModelDepthError(self)
        for item in self:
            if not isinstance(item, ModelGroup):
                yield item
            elif not item.is_pointless(parent=self):
                yield item
            else:
                for obj in item.iter_model(depth+1):
                    yield obj

    def iter_elements(self, depth=0):
        """
        A generator function iterating model's elements. Raises `XMLSchemaModelDepthError` if the
        argument *depth* is over `MAX_MODEL_DEPTH` value.

        :param depth: guard for protect model nesting bombs, incremented at each deepest recursion.
        """
        if depth > MAX_MODEL_DEPTH:
            raise XMLSchemaModelDepthError(self)
        for item in self:
            if isinstance(item, ModelGroup):
                for e in item.iter_elements(depth+1):
                    yield e
            else:
                yield item

    def iter_subelements(self, depth=0):
        if depth <= MAX_MODEL_DEPTH:
            for item in self:
                if isinstance(item, ModelGroup):
                    for e in item.iter_subelements(depth+1):
                        yield e
                else:
                    yield item

    def check_model(self):
        """
        Checks if the model group is deterministic. Types matching of same elements and Unique Particle
        Attribution Constraint are checked. Raises an `XMLSchemaModelError` at first violated constraint.
        """
        def safe_iter_path(group, depth):
            if depth > MAX_MODEL_DEPTH:
                raise XMLSchemaModelDepthError(group)
            for item in group:
                if isinstance(item, ModelGroup):
                    current_path.append(item)
                    for _item in safe_iter_path(item, depth + 1):
                        yield _item
                    current_path.pop()
                else:
                    yield item

        paths = {}
        current_path = [self]
        for e in safe_iter_path(self, 0):
            for pe, previous_path in paths.values():
                if pe.name == e.name and pe.name is not None and pe.type is not e.type:
                    raise XMLSchemaModelError(
                        self, "The model has elements with the same name %r but a different type" % e.name
                    )
                elif not pe.overlap(e):
                    continue
                elif pe is not e and pe.parent is e.parent:
                    if pe.parent.model in {'all', 'choice'}:
                        msg = "{!r} and {!r} overlap and are in the same {!r} group"
                        raise XMLSchemaModelError(self, msg.format(pe, e, pe.parent.model))
                    elif pe.min_occurs == pe.max_occurs:
                        continue

                if not distinguishable_paths(previous_path + [pe], current_path + [e]):
                    raise XMLSchemaModelError(
                        self, "Unique Particle Attribution violation between {!r} and {!r}".format(pe, e)
                    )
            paths[e.name] = e, current_path[:]


def distinguishable_paths(path1, path2):
    """
    Checks if two model paths are distinguishable in a deterministic way, without looking forward
    or backtracking. The arguments are lists containing paths from the base group of the model to
    a couple of leaf elements. Returns `True` if there is a deterministic separation between paths,
    `False` if the paths are ambiguous.
    """
    e1, e2 = path1[-1], path2[-1]

    for k, e in enumerate(path1):
        if e not in path2:
            depth = k - 1
            break
    else:
        depth = 0

    if path1[depth].max_occurs == 0:
        return True

    univocal1 = univocal2 = True
    if path1[depth].model == 'sequence':
        idx1 = path1[depth].index(path1[depth + 1])
        idx2 = path2[depth].index(path2[depth + 1])
        before1 = any(not e.is_emptiable() for e in path1[depth][:idx1])
        after1 = before2 = any(not e.is_emptiable() for e in path1[depth][idx1 + 1:idx2])
        after2 = any(not e.is_emptiable() for e in path1[depth][idx2 + 1:])
    else:
        before1 = after1 = before2 = after2 = False

    for k in range(depth + 1, len(path1) - 1):
        univocal1 &= path1[k].is_univocal()
        if path1[k].model == 'sequence':
            idx = path1[k].index(path1[k + 1])
            before1 |= any(not e.is_emptiable() for e in path1[k][:idx])
            after1 |= any(not e.is_emptiable() for e in path1[k][idx + 1:])

    for k in range(depth + 1, len(path2) - 1):
        univocal2 &= path2[k].is_univocal()
        if path2[k].model == 'sequence':
            idx = path2[k].index(path2[k + 1])
            before2 |= any(not e.is_emptiable() for e in path2[k][:idx])
            after2 |= any(not e.is_emptiable() for e in path2[k][idx + 1:])

    if path1[depth].model != 'sequence':
        return before1 and before2 or \
               (before1 and (univocal1 and e1.is_univocal() or after1 or path1[depth].max_occurs == 1)) or \
               (before2 and (univocal2 and e2.is_univocal() or after2 or path2[depth].max_occurs == 1))
    elif path1[depth].max_occurs == 1:
        return before2 or (before1 or univocal1) and (e1.is_univocal() or after1)
    else:
        return (before2 or (before1 or univocal1) and (e1.is_univocal() or after1)) and \
               (before1 or (before2 or univocal2) and (e2.is_univocal() or after2))


class ModelVisitor(MutableSequence):
    """
    A visitor design pattern class that can be used for validating XML data related to an XSD
    model group. The visit of the model is done using an external match information,
    counting the occurrences and yielding tuples in case of model's item occurrence errors.
    Ends setting the current element to `None`.

    :param root: the root ModelGroup instance of the model.
    :ivar occurs: the Counter instance for keeping track of occurrences of XSD elements and groups.
    :ivar element: the current XSD element, initialized to the first element of the model.
    :ivar broken: a boolean value that records if the model is still usable.
    :ivar group: the current XSD model group, initialized to *root* argument.
    :ivar iterator: the current XSD group iterator.
    :ivar items: the current XSD group unmatched items.
    :ivar match: if the XSD group has an effective item match.
    """
    def __init__(self, root):
        self.root = root
        self.occurs = Counter()
        self._subgroups = []
        self.element = None
        self.broken = False
        self.group, self.iterator, self.items, self.match = root, iter(root), root[::-1], False
        self._start()

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    def __repr__(self):
        return '%s(root=%r)' % (self.__class__.__name__, self.root)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._subgroups[i]

    def __setitem__(self, i, item):
        self._subgroups[i] = item

    def __delitem__(self, i):
        del self._subgroups[i]

    def __len__(self):
        return len(self._subgroups)

    def insert(self, i, item):
        self._subgroups.insert(i, item)

    def clear(self):
        del self._subgroups[:]
        self.occurs.clear()
        self.element = None
        self.broken = False
        self.group, self.iterator, self.items, self.match = self.root, iter(self.root), self.root[::-1], False

    def _start(self):
        while True:
            item = next(self.iterator, None)
            if item is None or not isinstance(item, ModelGroup):
                self.element = item
                break
            elif item:
                self.append((self.group, self.iterator, self.items, self.match))
                self.group, self.iterator, self.items, self.match = item, iter(item), item[::-1], False

    @property
    def expected(self):
        """
        Returns the expected elements of the current and descendant groups.
        """
        expected = []
        for item in reversed(self.items):
            if isinstance(item, ModelGroup):
                expected.extend(item.iter_elements())
            else:
                expected.append(item)
                expected.extend(item.maps.substitution_groups.get(item.name, ()))
        return expected

    def restart(self):
        self.clear()
        self._start()

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
        def stop_item(item):
            """
            Stops element or group matching, incrementing current group counter.

            :return: `True` if the item has violated the minimum occurrences for itself \
            or for the current group, `False` otherwise.
            """
            if isinstance(item, ModelGroup):
                self.group, self.iterator, self.items, self.match = self.pop()

            item_occurs = occurs[item]
            model = self.group.model
            if item_occurs:
                self.match = True
                if model == 'choice':
                    occurs[item] = 0
                    occurs[self.group] += 1
                    self.iterator, self.match = iter(self.group), False
                else:
                    if model == 'all':
                        self.items.remove(item)
                    else:
                        self.items.pop()
                    if not self.items:
                        self.occurs[self.group] += 1
                return item.is_missing(item_occurs)

            elif model == 'sequence':
                if self.match:
                    self.items.pop()
                    if not self.items:
                        occurs[self.group] += 1
                    return not item.is_emptiable()
                elif item.is_emptiable():
                    self.items.pop()
                    return False
                elif self.group.min_occurs <= occurs[self.group] or self:
                    return stop_item(self.group)
                else:
                    self.items.pop()
                    return True

        element, occurs = self.element, self.occurs
        if element is None:
            raise XMLSchemaValueError("cannot advance, %r is ended!" % self)

        if match:
            occurs[element] += 1
            self.match = True
            if not element.is_over(occurs[element]):
                return
        try:
            if stop_item(element):
                yield element, occurs[element], [element]

            while True:
                while self.group.is_over(occurs[self.group]):
                    stop_item(self.group)

                obj = next(self.iterator, None)
                if obj is None:
                    if not self.match:
                        if self.group.model == 'all' and all(e.min_occurs == 0 for e in self.items):
                            occurs[self.group] += 1
                        group, expected = self.group, self.items
                        if stop_item(group) and expected:
                            yield group, occurs[group], self.expected
                    elif not self.items:
                        self.iterator, self.items, self.match = iter(self.group), self.group[::-1], False
                    elif self.group.model == 'all':
                        self.iterator, self.match = iter(self.items), False
                    elif all(e.min_occurs == 0 for e in self.items):
                        self.iterator, self.items, self.match = iter(self.group), self.group[::-1], False
                        occurs[self.group] += 1

                elif not isinstance(obj, ModelGroup):  # XsdElement or XsdAnyElement
                    self.element, occurs[obj] = obj, 0
                    return

                elif obj:
                    self.append((self.group, self.iterator, self.items, self.match))
                    self.group, self.iterator, self.items, self.match = obj, iter(obj), obj[::-1], False
                    occurs[obj] = 0

        except IndexError:
            self.element = None
            if self.group.is_missing(occurs[self.group]) and self.items:
                yield self.group, occurs[self.group], self.expected
