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
This module contains a function and a class for validating XSD content models,
plus a set of functions for manipulating encoded content.
"""
from collections import defaultdict, deque
from typing import Any, Counter, Dict, Iterable, Iterator, List, \
    MutableMapping, MutableSequence, Optional, Tuple, Union

from ..exceptions import XMLSchemaValueError
from ..aliases import ModelGroupType, ModelParticleType, SchemaElementType
from ..translation import gettext as _
from .. import limits
from .exceptions import XMLSchemaModelError, XMLSchemaModelDepthError
from .wildcards import XsdAnyElement, Xsd11AnyElement
from . import groups

AdvanceYieldedType = Tuple[ModelParticleType, int, List[SchemaElementType]]
ContentItemType = Tuple[Union[int, str], Any]
EncodedContentType = Union[MutableMapping[Union[int, str], Any], Iterable[ContentItemType]]


def distinguishable_paths(path1: List[ModelParticleType], path2: List[ModelParticleType]) -> bool:
    """
    Checks if two model paths are distinguishable in a deterministic way, without looking forward
    or backtracking. The arguments are lists containing paths from the base group of the model to
    a couple of leaf elements. Returns `True` if there is a deterministic separation between paths,
    `False` if the paths are ambiguous.
    """
    e: ModelParticleType

    for k, e in enumerate(path1):
        if e not in path2:
            if not k:
                return True
            depth = k - 1
            break
    else:
        depth = 0

    if path1[depth].max_occurs == 0:
        return True

    univocal1 = univocal2 = True
    if path1[depth].model == 'sequence':  # type: ignore[union-attr]
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
        if path1[k].model == 'sequence':  # type: ignore[union-attr]
            before1 |= any(not e.is_emptiable() for e in path1[k][:idx])
            after1 |= any(not e.is_emptiable() for e in path1[k][idx + 1:])
        elif any(e.is_emptiable() for e in path1[k] if e is not path1[k][idx]):
            univocal1 = False

    for k in range(depth + 1, len(path2) - 1):
        univocal2 &= path2[k].is_univocal()
        idx = path2[k].index(path2[k + 1])
        if path2[k].model == 'sequence':  # type: ignore[union-attr]
            before2 |= any(not e.is_emptiable() for e in path2[k][:idx])
            after2 |= any(not e.is_emptiable() for e in path2[k][idx + 1:])
        elif any(e.is_emptiable() for e in path2[k] if e is not path2[k][idx]):
            univocal2 = False

    if path1[depth].model != 'sequence':  # type: ignore[union-attr]
        if before1 and before2:
            return True
        elif before1:
            return univocal1 and path1[-1].is_univocal() or after1 or path1[depth].max_occurs == 1
        elif before2:
            return univocal2 and path2[-1].is_univocal() or after2 or path2[depth].max_occurs == 1
        else:
            return False
    elif path1[depth].max_occurs == 1:
        return before2 or (before1 or univocal1) and (path1[-1].is_univocal() or after1)
    else:
        return (before2 or (before1 or univocal1) and (path1[-1].is_univocal() or after1)) and \
               (before1 or (before2 or univocal2) and (path2[-1].is_univocal() or after2))


def check_model(group: ModelGroupType) -> None:
    """
    Checks if the model group is deterministic. Element Declarations Consistent and
    Unique Particle Attribution constraints are checked.

    :param group: the model group to check.
    :raises: an `XMLSchemaModelError` at first violated constraint.
    """
    def safe_iter_path() -> Iterator[SchemaElementType]:
        iterators: List[Iterator[ModelParticleType]] = []
        particles = iter(group)

        while True:
            for item in particles:
                if isinstance(item, groups.XsdGroup):
                    current_path.append(item)
                    iterators.append(particles)
                    particles = iter(item)
                    if len(iterators) > limits.MAX_MODEL_DEPTH:
                        raise XMLSchemaModelDepthError(group)
                    break
                else:
                    yield item
            else:
                try:
                    current_path.pop()
                    particles = iterators.pop()
                except IndexError:
                    return

    paths: Any = {}
    current_path: List[ModelParticleType] = [group]
    try:
        any_element = group.parent.open_content.any_element  # type: ignore[union-attr]
    except AttributeError:
        any_element = None

    for e in safe_iter_path():

        previous_path: List[ModelParticleType]
        for pe, previous_path in paths.values():
            # EDC check
            if not e.is_consistent(pe) or any_element and not any_element.is_consistent(pe):
                msg = _("Element Declarations Consistent violation between {0!r} and {1!r}"
                        ": match the same name but with different types").format(e, pe)
                raise XMLSchemaModelError(group, msg)

            # UPA check
            if pe is e or not pe.is_overlap(e):
                continue
            elif pe.parent is e.parent:
                if pe.parent.model in {'all', 'choice'}:
                    if isinstance(pe, Xsd11AnyElement) and not isinstance(e, XsdAnyElement):
                        pe.add_precedence(e, group)
                    elif isinstance(e, Xsd11AnyElement) and not isinstance(pe, XsdAnyElement):
                        e.add_precedence(pe, group)
                    else:
                        msg = _("{0!r} and {1!r} overlap and are in the same {2!r} group")
                        raise XMLSchemaModelError(group, msg.format(pe, e, pe.parent.model))
                elif pe.is_univocal():
                    continue

            if distinguishable_paths(previous_path + [pe], current_path + [e]):
                continue
            elif isinstance(pe, Xsd11AnyElement) and not isinstance(e, XsdAnyElement):
                pe.add_precedence(e, group)
            elif isinstance(e, Xsd11AnyElement) and not isinstance(pe, XsdAnyElement):
                e.add_precedence(pe, group)
            else:
                msg = _("Unique Particle Attribution violation between {0!r} and {1!r}")
                raise XMLSchemaModelError(group, msg.format(pe, e))

        paths[e.name] = e, current_path[:]


class ModelVisitor:
    """
    A visitor design pattern class that can be used for validating XML data related to an XSD
    model group. The visit of the model is done using an external match information,
    counting the occurrences and yielding tuples in case of model's item occurrence errors.
    Ends setting the current element to `None`.

    :param root: the root model group.
    :ivar occurs: the Counter instance for keeping track of occurrences of XSD elements and groups.
    :ivar element: the current XSD element, initialized to the first element of the model.
    :ivar group: the current XSD model group, initialized to *root* argument.
    :ivar items: the current XSD group's items iterator.
    :ivar match: if the XSD group has an effective item match.
    """
    _groups: List[Tuple[ModelGroupType, Iterator[ModelParticleType], bool]]
    element: Optional[SchemaElementType]

    __slots__ = '_groups', 'root', 'occurs', 'element', 'group', 'items', 'match'

    def __init__(self, root: ModelGroupType) -> None:
        self._groups = []
        self.root = root
        self.occurs = Counter[Union[ModelParticleType, Tuple[ModelParticleType]]]()
        self.element = None
        self.group = root
        self.items = self.iter_group()
        self.match = False
        self._start()

    def __repr__(self) -> str:
        return '%s(root=%r)' % (self.__class__.__name__, self.root)

    def clear(self) -> None:
        del self._groups[:]
        self.occurs.clear()
        self.element = None
        self.group = self.root
        self.items = self.iter_group()
        self.match = False

    def _start(self) -> None:
        while True:
            item = next(self.items, None)
            if item is None:
                if not self._groups:
                    break
                self.group, self.items, self.match = self._groups.pop()
            elif not isinstance(item, groups.XsdGroup):
                self.element = item
                break
            elif item:
                self._groups.append((self.group, self.items, self.match))
                self.group = item
                self.items = self.iter_group()
                self.match = False

    @property
    def expected(self) -> List[SchemaElementType]:
        """
        Returns the expected elements of the current and descendant groups.
        """
        expected: List[SchemaElementType] = []
        items: Union[ModelGroupType, Iterator[ModelParticleType]]

        if self.group.model == 'choice':
            items = self.group
        elif self.group.model == 'all':
            items = (e for e in self.group if e.min_occurs > self.occurs[e])
        else:
            items = (e for e in self.group if e.min_occurs > self.occurs[e])

        for e in items:
            if isinstance(e, groups.XsdGroup):
                expected.extend(e.iter_elements())
            else:
                expected.append(e)
                expected.extend(e.maps.substitution_groups.get(e.name or '', ()))
        return expected

    def restart(self) -> None:
        self.clear()
        self._start()

    def stop(self) -> Iterator[AdvanceYieldedType]:
        while self.element is not None:
            for e in self.advance():
                yield e

    def iter_group(self) -> Iterator[ModelParticleType]:
        """Returns an iterator for the current model group."""
        if self.group.max_occurs == 0:
            return iter(())
        elif self.group.model != 'all':
            return iter(self.group)
        else:
            return (e for e in self.group.iter_elements() if not e.is_over(self.occurs[e]))

    def advance(self, match: bool = False) -> Iterator[AdvanceYieldedType]:
        """
        Generator function for advance to the next element. Yields tuples with
        particles information when occurrence violation is found.

        :param match: provides current element match.
        """
        def stop_item(item: ModelParticleType) -> bool:
            """
            Stops element or group matching, incrementing current group counter.

            :return: `True` if the item has violated the minimum occurrences for itself \
            or for the current group, `False` otherwise.
            """
            if isinstance(item, groups.XsdGroup):
                self.group, self.items, self.match = self._groups.pop()

            if self.group.model == 'choice':
                item_occurs = occurs[item]
                if not item_occurs:
                    return False
                item_max_occurs = occurs[(item,)] or item_occurs

                if item.max_occurs is None:
                    min_group_occurs = 1
                elif item_occurs % item.max_occurs:
                    min_group_occurs = 1 + item_occurs // item.max_occurs
                else:
                    min_group_occurs = item_occurs // item.max_occurs

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
            elif self._groups:
                return stop_item(self.group)
            elif self.group.min_occurs <= max(occurs[self.group], occurs[(self.group,)]):
                return stop_item(self.group)
            else:
                return True

            if item is self.group[-1]:
                for k, item2 in enumerate(self.group, start=1):  # pragma: no cover
                    item_occurs = occurs[item2]
                    if not item_occurs:
                        continue

                    item_max_occurs = occurs[(item2,)] or item_occurs
                    if item_max_occurs == 1 or any(not x.is_emptiable() for x in self.group[k:]):
                        occurs[self.group] += 1
                        break

                    min_group_occurs = max(1, item_occurs // (item2.max_occurs or item_occurs))
                    max_group_occurs = max(1, item_max_occurs // (item2.min_occurs or 1))

                    occurs[self.group] += min_group_occurs
                    occurs[(self.group,)] += max_group_occurs
                    break

            return item.is_missing(max(occurs[item], occurs[(item,)]))

        occurs = self.occurs
        if self.element is None:
            raise XMLSchemaValueError("cannot advance, %r is ended!" % self)

        if match:
            occurs[self.element] += 1
            self.match = True
            if self.group.model == 'all':
                self.items = (e for e in self.group.iter_elements() if not e.is_over(occurs[e]))
            elif not self.element.is_over(occurs[self.element]):
                return
            elif self.group.model == 'choice' and self.element.is_ambiguous():
                return

        obj = None
        try:
            element_occurs = occurs[self.element]
            if stop_item(self.element):
                yield self.element, element_occurs, [self.element]

            while True:
                while self.group.is_over(max(occurs[self.group], occurs[(self.group,)])):
                    stop_item(self.group)

                obj = next(self.items, None)
                if isinstance(obj, groups.XsdGroup):
                    # inner 'sequence' or 'choice' XsdGroup
                    self._groups.append((self.group, self.items, self.match))
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
                elif any(e.min_occurs > occurs[e] for e in self.group.iter_elements()):
                    if not self.group.min_occurs:
                        yield self.group, occurs[self.group], self.expected
                    self.group, self.items, self.match = self._groups.pop()
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
            elif self.group.max_occurs is not None and self.group.max_occurs < occurs[self.group]:
                yield self.group, occurs[self.group], self.expected

    # Kept for backward compatibility
    def iter_unordered_content(
            self, content: EncodedContentType,
            default_namespace: Optional[str] = None) -> Iterator[ContentItemType]:
        return iter_unordered_content(content, self.root, default_namespace)

    def iter_collapsed_content(
            self, content: Iterable[ContentItemType],
            default_namespace: Optional[str] = None) -> Iterator[ContentItemType]:
        return iter_collapsed_content(content, self.root, default_namespace)


#
# Functions for manipulating encoded content

def iter_unordered_content(
        content: EncodedContentType,
        group: ModelGroupType,
        default_namespace: Optional[str] = None) -> Iterator[ContentItemType]:
    """
    Takes an unordered content stored in a dictionary of lists and yields the
    content elements sorted with the ordering defined by the model group. Character
    data parts are yielded at start and between child elements.

    Ordering is inferred from ModelVisitor instance with any elements that
    don't fit the schema placed at the end of the returned sequence. Checking
    the yielded content validity is the responsibility of method *iter_encode*
    of class :class:`XsdGroup`.

    :param content: a dictionary of element names to list of element contents \
    or an iterable composed of couples of name and value. In case of a \
    dictionary the values must be lists where each item is the content \
    of a single element.
    :param group: the model group related to content.
    :param default_namespace: the default namespace to apply for matching names.
    """
    consumable_content: Dict[str, Any]

    if isinstance(content, MutableMapping):
        cdata_content = sorted(
            ((k, v) for k, v in content.items() if isinstance(k, int)), reverse=True
        )
        consumable_content = {
            k: deque(v) if isinstance(v, MutableSequence) else deque([v])
            for k, v in content.items() if not isinstance(k, int)
        }
    else:
        cdata_content = sorted(((k, v) for k, v in content if isinstance(k, int)), reverse=True)
        consumable_content = defaultdict(deque)
        for k, v in content:
            if isinstance(k, str):
                consumable_content[k].append(v)

    if cdata_content:
        yield cdata_content.pop()

    model = ModelVisitor(group)
    while model.element is not None and consumable_content:  # pragma: no cover
        for name in consumable_content:
            if model.element.is_matching(name, default_namespace, group=group):
                yield name, consumable_content[name].popleft()
                if not consumable_content[name]:
                    del consumable_content[name]
                for _err in model.advance(True):
                    pass
                if cdata_content:
                    yield cdata_content.pop()
                break
        else:
            # Consume the return of advance otherwise we get stuck in an infinite loop.
            for _err in model.advance(False):
                pass

    # Add the remaining consumable content onto the end of the data.
    for name, values in consumable_content.items():
        for v in values:
            yield name, v
            if cdata_content:
                yield cdata_content.pop()

    while cdata_content:
        yield cdata_content.pop()


def sort_content(content: EncodedContentType,
                 group: ModelGroupType,
                 default_namespace: Optional[str] = None) -> List[ContentItemType]:
    return [x for x in iter_unordered_content(content, group, default_namespace)]


def iter_collapsed_content(
        content: Iterable[ContentItemType],
        group: ModelGroupType,
        default_namespace: Optional[str] = None) -> Iterator[ContentItemType]:
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
    :param group: the model group related to content.
    :param default_namespace: the default namespace to apply for matching names.
    """
    prev_name = None
    unordered_content: Dict[str, Any] = defaultdict(deque)

    model = ModelVisitor(group)
    for name, value in content:
        if isinstance(name, int) or model.element is None:
            yield name, value
            continue

        while model.element is not None:
            if model.element.is_matching(name, default_namespace, group=group):
                yield name, value
                prev_name = name
                for _err in model.advance(True):
                    pass
                break

            for key in unordered_content:
                if model.element.is_matching(key, default_namespace, group=group):
                    break
            else:
                if prev_name == name:
                    unordered_content[name].append(value)
                    break

                for _err in model.advance(False):
                    pass
                continue

            try:
                yield key, unordered_content[key].popleft()
            except IndexError:
                del unordered_content[key]
            else:
                for _err in model.advance(True):
                    pass
        else:
            yield name, value
            prev_name = name

    # Add the remaining consumable content onto the end of the data.
    for name, values in unordered_content.items():
        for v in values:
            yield name, v
