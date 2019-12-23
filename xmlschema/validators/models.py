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
from collections import defaultdict, deque, Counter

from .. import limits
from ..compat import PY3, MutableSequence
from ..exceptions import XMLSchemaValueError
from .exceptions import XMLSchemaModelError, XMLSchemaModelDepthError
from .xsdbase import ParticleMixin
from .wildcards import XsdAnyElement, Xsd11AnyElement


class ModelGroup(MutableSequence, ParticleMixin):
    """
    Class for XSD model group particles. This class implements only model related methods,
    schema element parsing and validation methods are implemented in derived classes.
    """
    parent = None

    def __init__(self, model):
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
            if value not in {'sequence', 'choice', 'all'}:
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
            return self.min_occurs == 0 or not self or any(item.is_emptiable() for item in self)
        else:
            return self.min_occurs == 0 or not self or all(item.is_emptiable() for item in self)

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

    @property
    def effective_min_occurs(self):
        if self.model == 'choice':
            return min(e.min_occurs for e in self.iter_model())
        return self.min_occurs * min(e.min_occurs for e in self.iter_model())

    @property
    def effective_max_occurs(self):
        if self.max_occurs == 0:
            return 0
        elif self.max_occurs is None:
            return None if any(e.max_occurs != 0 for e in self.iter_model()) else 0
        elif any(e.max_occurs is None for e in self.iter_model()):
            return None
        elif self.model == 'choice':
            return self.max_occurs * max(e.max_occurs for e in self.iter_model())
        else:
            return self.max_occurs * sum(e.max_occurs for e in self.iter_model())

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
        over `limits.MAX_MODEL_DEPTH` value.

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
                for obj in item.iter_model(depth + 1):
                    yield obj

    def iter_elements(self, depth=0):
        """
        A generator function iterating model's elements. Raises `XMLSchemaModelDepthError` if the
        argument *depth* is over `limits.MAX_MODEL_DEPTH` value.

        :param depth: guard for protect model nesting bombs, incremented at each deepest recursion.
        """
        if depth > limits.MAX_MODEL_DEPTH:
            raise XMLSchemaModelDepthError(self)
        for item in self:
            if isinstance(item, ModelGroup):
                for e in item.iter_elements(depth + 1):
                    yield e
            else:
                yield item

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
                    for _item in safe_iter_path(item, depth - 1):
                        yield _item
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
        idx = path1[k].index(path1[k + 1])
        if path1[k].model == 'sequence':
            before1 |= any(not e.is_emptiable() for e in path1[k][:idx])
            after1 |= any(not e.is_emptiable() for e in path1[k][idx + 1:])
        elif path1[k].model in ('all', 'choice'):
            if any(e.is_emptiable() for e in path1[k] if e is not path1[k][idx]):
                univocal1 = before1 = after1 = False
        else:
            if len(path2[k]) > 1 and all(e.is_emptiable() for e in path1[k] if e is not path1[k][idx]):
                univocal1 = before1 = after1 = False

    for k in range(depth + 1, len(path2) - 1):
        univocal2 &= path2[k].is_univocal()
        idx = path2[k].index(path2[k + 1])
        if path2[k].model == 'sequence':
            before2 |= any(not e.is_emptiable() for e in path2[k][:idx])
            after2 |= any(not e.is_emptiable() for e in path2[k][idx + 1:])
        elif path2[k].model in ('all', 'choice'):
            if any(e.is_emptiable() for e in path2[k] if e is not path2[k][idx]):
                univocal2 = before2 = after2 = False
        else:
            if len(path2[k]) > 1 and all(e.is_emptiable() for e in path2[k] if e is not path2[k][idx]):
                univocal2 = before2 = after2 = False

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
    :ivar group: the current XSD model group, initialized to *root* argument.
    :ivar items: the current XSD group's items iterator.
    :ivar match: if the XSD group has an effective item match.
    """
    def __init__(self, root):
        self.root = root
        self.occurs = Counter()
        self._subgroups = []
        self.element = None
        self.group = root
        self.items = self.iter_group()
        self.match = False
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
        self.group = self.root
        self.items = self.iter_group()
        self.match = False

    def _start(self):
        while True:
            item = next(self.items, None)
            if item is None:
                if not self:
                    break
                else:
                    self.group, self.items, self.match = self.pop()
            elif not isinstance(item, ModelGroup):
                self.element = item
                break
            elif item:
                self.append((self.group, self.items, self.match))
                self.group = item
                self.items = self.iter_group()
                self.match = False

    @property
    def expected(self):
        """
        Returns the expected elements of the current and descendant groups.
        """
        expected = []
        if self.group.model == 'choice':
            items = self.group
        elif self.group.model == 'all':
            items = (e for e in self.group if e.min_occurs > self.occurs[e])
        else:
            items = (e for e in self.group if e.min_occurs > self.occurs[e])

        for e in items:
            if isinstance(e, ModelGroup):
                expected.extend(e.iter_elements())
            else:
                expected.append(e)
                expected.extend(e.maps.substitution_groups.get(e.name, ()))
        return expected

    def restart(self):
        self.clear()
        self._start()

    def stop(self):
        while self.element is not None:
            for e in self.advance():
                yield e

    def iter_group(self):
        """Returns an iterator for the current model group."""
        if self.group.model != 'all':
            return iter(self.group)
        else:
            return (e for e in self.group.iter_elements() if not e.is_over(self.occurs[e]))

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
                self.group, self.items, self.match = self.pop()

            if self.group.model == 'choice':
                item_occurs = occurs[item]
                if not item_occurs:
                    return False
                item_max_occurs = occurs[(item,)] or item_occurs

                min_group_occurs = max(1, item_occurs // (item.max_occurs or item_occurs))
                max_group_occurs = max(1, item_max_occurs // (item.min_occurs or 1))

                occurs[self.group] += min_group_occurs
                occurs[(self.group,)] += max_group_occurs
                occurs[item] = 0

                self.items = self.iter_group()
                self.match = False
                return item.is_missing(item_max_occurs)

            elif self.group.model == 'all':
                return False
            elif self.match:
                pass
            elif occurs[item]:
                self.match = True
            elif item.is_emptiable():
                return False
            elif self.group.min_occurs <= max(occurs[self.group], occurs[(self.group,)]) or self:
                return stop_item(self.group)
            else:
                return True

            if item is self.group[-1]:
                for k, item2 in enumerate(self.group, start=1):
                    item_occurs = occurs[item2]
                    if not item_occurs:
                        continue

                    item_max_occurs = occurs[(item2,)] or item_occurs
                    if item_max_occurs == 1 or any(not x.is_emptiable() for x in self.group[k:]):
                        self.occurs[self.group] += 1
                        break

                    min_group_occurs = max(1, item_occurs // (item2.max_occurs or item_occurs))
                    max_group_occurs = max(1, item_max_occurs // (item2.min_occurs or 1))

                    occurs[self.group] += min_group_occurs
                    occurs[(self.group,)] += max_group_occurs
                    break

            return item.is_missing(max(occurs[item], occurs[(item,)]))

        element, occurs = self.element, self.occurs
        if element is None:
            raise XMLSchemaValueError("cannot advance, %r is ended!" % self)

        if match:
            occurs[element] += 1
            self.match = True
            if self.group.model == 'all':
                self.items = (e for e in self.group.iter_elements() if not e.is_over(occurs[e]))
            elif not element.is_over(occurs[element]):
                return
            elif self.group.model == 'choice' and element.is_ambiguous():
                return

        obj = None
        try:
            if stop_item(element):
                yield element, occurs[element], [element]

            while True:
                while self.group.is_over(max(occurs[self.group], occurs[(self.group,)])):
                    stop_item(self.group)

                obj = next(self.items, None)
                if isinstance(obj, ModelGroup):
                    # inner 'sequence' or 'choice' XsdGroup
                    self.append((self.group, self.items, self.match))
                    self.group = obj
                    self.items = self.iter_group()
                    self.match = False
                    occurs[obj] = occurs[(obj,)] = 0

                elif obj is not None:
                    # XsdElement or XsdAnyElement
                    self.element = obj
                    if self.group.model == 'sequence':
                        occurs[obj] = 0
                    return

                elif not self.match:
                    if self.group.model == 'all':
                        if all(e.min_occurs <= occurs[e] for e in self.group.iter_elements()):
                            occurs[self.group] = 1

                    group, expected = self.group, self.expected
                    if stop_item(group) and expected:
                        yield group, occurs[group], expected

                elif self.group.model != 'all':
                    self.items, self.match = self.iter_group(), False
                elif any(not e.is_over(occurs[e]) for e in self.group):
                    self.items = self.iter_group()
                    self.match = False
                else:
                    occurs[self.group] = 1

        except IndexError:
            # Model visit ended
            self.element = None
            if self.group.is_missing(max(occurs[self.group], occurs[(self.group,)])):
                if self.group.model == 'choice':
                    yield self.group, occurs[self.group], self.expected
                elif self.group.model == 'sequence':
                    if obj is not None:
                        yield self.group, occurs[self.group], self.expected
                elif any(e.min_occurs > occurs[e] for e in self.group):
                    yield self.group, occurs[self.group], self.expected

    def sort_content(self, content, restart=True):
        if restart:
            self.restart()
        return [(name, value) for name, value in self.iter_unordered_content(content)]

    def iter_unordered_content(self, content):
        """
        Takes an unordered content stored in a dictionary of lists and yields the
        content elements sorted with the ordering defined by the model. Character
        data parts are yielded at start and between child elements.

        Ordering is inferred from ModelVisitor instance with any elements that
        don't fit the schema placed at the end of the returned sequence. Checking
        the yielded content validity is the responsibility of method *iter_encode*
        of class :class:`XsdGroup`.

        :param content: a dictionary of element names to list of element contents \
        or an iterable composed of couples of name and value. In case of a \
        dictionary the values ​​must be lists where each item is the content \
        of a single element.
        :return: yields of a sequence of the Element being encoded's children.
        """
        if isinstance(content, dict):
            cdata_content = sorted(((k, v) for k, v in content.items() if isinstance(k, int)), reverse=True)
            consumable_content = {k: deque(v) for k, v in content.items() if not isinstance(k, int)}
        else:
            cdata_content = sorted(((k, v) for k, v in content if isinstance(k, int)), reverse=True)
            consumable_content = defaultdict(deque)
            for k, v in filter(lambda x: not isinstance(x[0], int), content):
                consumable_content[k].append(v)

        if cdata_content:
            yield cdata_content.pop()

        while self.element is not None and consumable_content:
            for name in consumable_content:
                if self.element.is_matching(name):
                    yield name, consumable_content[name].popleft()
                    if not consumable_content[name]:
                        del consumable_content[name]
                    for _ in self.advance(True):
                        pass
                    if cdata_content:
                        yield cdata_content.pop()
                    break
            else:
                # Consume the return of advance otherwise we get stuck in an infinite loop.
                for _ in self.advance(False):
                    pass

        # Add the remaining consumable content onto the end of the data.
        for name, values in consumable_content.items():
            for v in values:
                yield name, v
                if cdata_content:
                    yield cdata_content.pop()

        while cdata_content:
            yield cdata_content.pop()

    def iter_collapsed_content(self, content):
        """
        Iterates a content stored in a sequence of couples *(name, value)*, yielding
        items in the same order of the sequence, except for repetitions of the same
        tag that don't match with the current element of the :class:`ModelVisitor`
        instance. These items are included in an unsorted buffer and yielded asap
        when there is a match with the model's element or at the end of the iteration.

        This iteration mode, in cooperation with the method *iter_encode* of the class
        XsdGroup, facilitates the encoding of content formatted with a convention that
        collapses the children with the same tag into a list (eg. BadgerFish).

        :param content: an iterable containing couples of names and values.
        :return: yields of a sequence of the Element being encoded's children.
        """
        prev_name = None
        unordered_content = defaultdict(deque)

        for name, value in content:
            if isinstance(name, int) or self.element is None:
                yield name, value
                continue

            while self.element is not None:
                if self.element.is_matching(name):
                    yield name, value
                    prev_name = name
                    for _ in self.advance(True):
                        pass
                    break

                for key in unordered_content:
                    if self.element.is_matching(key):
                        break
                else:
                    if prev_name == name:
                        unordered_content[name].append(value)
                        break

                    for _ in self.advance(False):
                        pass
                    continue

                try:
                    yield key, unordered_content[key].popleft()
                except IndexError:
                    del unordered_content[key]
                else:
                    for _ in self.advance(True):
                        pass
            else:
                yield name, value
                prev_name = name

        # Add the remaining consumable content onto the end of the data.
        for name, values in unordered_content.items():
            for v in values:
                yield name, v
