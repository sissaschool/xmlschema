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
from collections import Counter

from ..compat import PY3, unicode_type, MutableSequence
from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..etree import etree_element
from ..qnames import XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_COMPLEX_TYPE, \
    XSD_ELEMENT, XSD_ANY, XSD_RESTRICTION, XSD_EXTENSION
from xmlschema.helpers import get_qname, local_name
from ..converters import XMLSchemaConverter

from .exceptions import XMLSchemaValidationError, XMLSchemaModelError
from .xsdbase import ValidationMixin, XsdComponent, ParticleMixin, XsdType
from .elements import XsdElement
from .wildcards import XsdAnyElement

XSD_GROUP_MODELS = {'sequence', 'choice', 'all'}

ANY_ELEMENT = etree_element(
    XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


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

    if path1[depth].model == 'sequence':
        if e1.min_occurs == e1.max_occurs:
            return True

        idx1 = path1[depth].index(path1[depth + 1])
        idx2 = path2[depth].index(path2[depth + 1])
        if any(not e.is_emptiable() for e in path1[depth][idx1 + 1:idx2]):
            return True

    before1 = False
    after1 = False
    for k in range(depth + 1, len(path1) - 1):
        if path1[k].model == 'sequence':
            idx = path1[k].index(path1[k + 1])
            if not before1 and any(not e.is_emptiable() for e in path1[k][:idx]):
                before1 = True
            if not after1 and any(not e.is_emptiable() for e in path1[k][idx + 1:]):
                after1 = True

    before2 = False
    after2 = False
    for k in range(depth + 1, len(path2) - 1):
        if path2[k].model == 'sequence':
            idx = path2[k].index(path2[k + 1])
            if not before2 and any(not e.is_emptiable() for e in path2[k][:idx]):
                before2 = True
            if not after2 and any(not e.is_emptiable() for e in path2[k][idx + 1:]):
                after2 = True

    if path1[depth].model != 'sequence':
        return before1 and before2 or (before1 and (e1.min_occurs == e1.max_occurs or after1)) \
               or (before2 and (e2.min_occurs == e2.max_occurs or after2))
    elif path1[depth].max_occurs == 1:
        return e1.min_occurs == e1.max_occurs or after1 or before2
    else:
        return (e1.min_occurs1 == e1.max_occurs or after1 or before2) and \
               (e2.min_occurs == e2.max_occurs or after2 or before1)

    #    return after1 or before2   # sequence
    #else:
    #    return before1 or after2 and before2 or after1   # choice/all


class XsdModelVisitor(MutableSequence):
    """
    A visitor design pattern class that can be used for validating XML data related to an
    XSD model group. The visit of the model is done using an external match information,
    counting the occurrences and yielding tuples in case of model's item occurrence errors.
    Ends setting the current element to `None`.

    :param root: the root XsdGroup instance of the model.
    :ivar occurs: the Counter instance for keeping track of occurrences of XSD elements and groups.
    :ivar element: the current XSD element, initialized to the first element of the model.
    :ivar broken: a boolean value that records if the model is still usable.
    :ivar group: the current XSD group, initialized to *root* argument.
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
            if item is None or not isinstance(item, XsdGroup):
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
            if isinstance(item, XsdGroup):
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
            if isinstance(item, XsdGroup):
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

                elif not isinstance(obj, XsdGroup):  # XsdElement or XsdAnyElement
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
    redefine = None
    admitted_tags = {
        XSD_COMPLEX_TYPE, XSD_EXTENSION, XSD_RESTRICTION,
        XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE
    }

    def __init__(self, elem, schema, parent, name=None):
        self.mixed = False if parent is None else parent.mixed
        self.model = None
        self._group = []
        XsdComponent.__init__(self, elem, schema, parent, name)

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
            if self.model is not None and value != self.model and self.model != 'all':
                raise XMLSchemaValueError("cannot change group model from %r to %r" % (self.model, value))
        elif name == '_group':
            if not all(isinstance(item, (tuple, ParticleMixin)) for item in value):
                raise XMLSchemaValueError("XsdGroup's items must be tuples or ParticleMixin instances.")
        super(XsdGroup, self).__setattr__(name, value)

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
                    ref = get_qname(self.target_namespace, child.attrib['ref'])
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
                    self.append(self.redefine)
            else:
                continue  # Error already caught by validation against the meta-schema

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
    def schema_elem(self):
        return self.elem if self.name else self.parent.elem

    @property
    def built(self):
        for item in self:
            if isinstance(item, XsdAnyElement):
                if not item.built:
                    return False
            elif isinstance(item, tuple):
                return False
            elif not isinstance(item, (XsdElement, XsdGroup)):
                raise XMLSchemaTypeError("wrong type for item %r of %r." % (item, self))
            elif item.parent is None:
                continue
            elif item.parent is not self.parent and isinstance(item.parent, XsdType) and item.parent.parent is None:
                continue
            elif not item.ref and not item.built:
                return False

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
            if item.parent is None:
                continue
            elif item.parent is not self.parent and isinstance(item.parent, XsdType) and item.parent.parent is None:
                continue
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

    def is_meaningless(self, parent=None):
        """
        A group that may be eliminated. A group is meaningless if one of those conditions is verified:

         - the group is empty
         - minOccurs == maxOccurs == 1 and the group has one child
         - minOccurs == maxOccurs == 1 and the group and its parent have a sequence model
         - minOccurs == maxOccurs == 1 and the group and its parent have a choice model

        :param parent: alternative parent, useful when expand complex content extensions.
        """
        if not self:
            return True
        elif self.min_occurs != 1 or self.max_occurs != 1:
            return False
        elif len(self) == 1:
            return True

        if parent is None:
            parent = self.parent

        if not isinstance(parent, XsdGroup):
            return False
        elif self.model == 'sequence' and parent.model != 'sequence':
            return False
        elif self.model == 'choice' and parent.model != 'choice':
            return False
        else:
            return True

    def has_particle_restriction(self, other):
        if not self:
            return True
        elif isinstance(other, XsdGroup):
            return super(XsdGroup, self).has_particle_restriction(other)

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

    def is_restriction(self, other, check_particle=True):
        if not self:
            return True
        elif self.ref is not None:
            return self[0].is_restriction(other, check_particle)
        elif isinstance(other, (XsdElement, XsdAnyElement)):
            if not self.has_particle_restriction(other):
                return False
            elif self.model == 'choice':
                if other.name in self.maps.substitution_groups and all(
                        isinstance(e, XsdElement) and e.substitution_group == other.name for e in self):
                    return True
                return any(e.is_restriction(other, False) for e in self)
            else:
                return all(e.is_restriction(other, False) or e.min_occurs == 0 for e in self)
        elif not isinstance(other, XsdGroup):
            return False
        elif not other:
            return False
        elif other.ref:
            return self.is_restriction(other[0], check_particle)
        elif other.model == 'choice' and self.model == 'all' and len(self) > 1:
            return False
        elif other.model == 'all' and self.model == 'choice' and len(self) > 1:
            return False
        elif len(other) == other.min_occurs == other.max_occurs == 1:
            if len(self) > 1:
                return self.is_restriction(other[0], check_particle)
            elif isinstance(self[0], XsdGroup) and self[0].is_meaningless(parent=self):
                return self[0].is_restriction(other[0], check_particle)

        # Aligned groups: compare group items one by one, discarding meaningless groups
        if self.model == other.model:
            if check_particle and not self.has_particle_restriction(other):
                return False
            if other.max_occurs == 0:
                check_particle = False

            # Same model: declarations must simply preserve order
            other_iterator = iter(other.iter_group())
            for item in self.iter_group():
                while True:
                    try:
                        other_item = next(other_iterator)
                    except StopIteration:
                        return False
                    if other_item is item or item.is_restriction(other_item, check_particle):
                        break
            return True

        elif other.model == 'sequence':
            if check_particle and not self.has_particle_restriction(other):
                return False
            if other.max_occurs == 0:
                check_particle = False

            other_iterator = iter(other.iter_group())
            for item in self.iter_group():
                while True:
                    try:
                        other_item = next(other_iterator)
                    except StopIteration:
                        return False

                    if other_item is item or item.is_restriction(other_item, check_particle):
                        break
                    elif not other_item.is_emptiable():
                        return False
            return True

        elif other.model == 'all':
            if check_particle and not self.has_particle_restriction(other):
                return False
            if other.max_occurs == 0:
                check_particle = False

            group_items = list(self)
            for other_item in other.iter_group():
                for item in group_items:
                    if other_item is item or item.is_restriction(other_item, check_particle):
                        break
                else:
                    if not other_item.is_emptiable():
                        return False
                    continue
                group_items.remove(item)
            return not bool(group_items)

        elif other.model == 'choice':
            if other.max_occurs == 0:
                check_particle = False

            group_items = list(self)
            max_occurs = 0
            other_max_occurs = 0
            for other_item in other.iter_group():
                for item in group_items:
                    if other_item is item or item.is_restriction(other_item, check_particle):
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
                group_items.remove(item)

            if group_items:
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

    def iter_group(self):
        """Creates an iterator for sub elements and groups. Skips meaningless groups."""
        for item in self:
            if not isinstance(item, XsdGroup):
                yield item
            elif item.parent is None or not item.is_meaningless(parent=self):
                yield item
            else:
                for obj in item.iter_group():
                    yield obj

    def iter_model(self):
        """
        Iterates model group through its group paths to leaf elements. Yields a list containing itself
        as first element, followed by any intermediate groups and the current XSD element at the end.
        """
        def _iter_model(group, depth):
            if depth <= 15:
                for item in group:
                    if isinstance(item, XsdGroup):
                        path.append(item)
                        for e in _iter_model(item, depth+1):
                            yield e
                        path.pop()
                    else:
                        yield item

        path = [self]
        for xsd_element in _iter_model(self, 0):
            yield xsd_element, path

    def iter_subelements(self, depth=0):
        if depth <= 15:
            for item in self:
                if isinstance(item, XsdGroup):
                    for e in item.iter_subelements(depth+1):
                        yield e
                else:
                    yield item

    def iter_elements(self, depth=0):
        if depth <= 15:
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

    def check_model(self):
        """
        Checks group particles. Types matching of same elements and Unique Particle Attribution
        Constraint are checked. Raises an `XMLSchemaModelError` at first violated constraint.
        """
        elements = {}
        for e, path in self.iter_model():
            for pe, previous_path in elements.values():
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
                #import pdb
                #pdb.set_trace()
                if not distinguishable_paths(previous_path + [pe], path + [e]):
                    # print(self.tostring())
                    # breakpoint()
                    # distinguishable_paths(previous_path + [pe], path + [e])
                    raise XMLSchemaModelError(
                        self, "Unique Particle Attribution violation between {!r} and {!r}".format(pe, e)
                    )
            elements[e.name] = e, path[:]

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

        model = XsdModelVisitor(self)
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

        model = XsdModelVisitor(self)
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
                    ref = get_qname(self.target_namespace, child.attrib['ref'])
                except KeyError:
                    self.parse_error("missing attribute 'ref' in local group", child)
                    continue

                if ref != self.name:
                    self.append(XsdGroup(child, self.schema, self))
                elif not hasattr(self, '_component'):
                    self.parse_error("Circular definition detected for group %r:" % self.ref, elem)
                else:
                    self.append(self._component)
            else:
                continue  # Error already caught by validation against the meta-schema
