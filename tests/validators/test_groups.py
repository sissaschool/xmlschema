#!/usr/bin/env python
#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import unittest
from typing import Any, Union, List, Optional

from xmlschema import XMLSchemaModelError, XMLSchemaModelDepthError
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.validators.particles import ParticleMixin
from xmlschema.validators.groups import XsdGroup


class ModelGroup(XsdGroup):
    """A subclass for testing XSD models, that disables element parsing and schema bindings."""

    def __init__(self, model: str, min_occurs: int = 1, max_occurs: Optional[int] = 1) -> None:
        ParticleMixin.__init__(self, min_occurs, max_occurs)
        if model not in {'sequence', 'choice', 'all'}:
            raise XMLSchemaValueError("invalid model {!r} for a group".format(model))
        self._group: List[Union[ParticleMixin, 'ModelGroup']] = []
        self.model: str = model

    def __repr__(self) -> str:
        return '%s(model=%r, occurs=%r)' % (self.__class__.__name__, self.model, self.occurs)

    @property
    def xsd_version(self) -> str:
        return '1.0'

    append: Any


class TestXsdGroups(unittest.TestCase):

    def test_model_group_init(self):
        group = ModelGroup('sequence')
        self.assertEqual(group.model, 'sequence')

        with self.assertRaises(ValueError):
            ModelGroup('mixed')

    def test_model_group_repr(self):
        group = ModelGroup('choice')
        self.assertEqual(repr(group), "ModelGroup(model='choice', occurs=(1, 1))")

    def test_model_group_container(self):
        # group: List[GroupItemType]
        group = ModelGroup('choice')

        group.append(('a',))
        self.assertListEqual(group[:], [('a',)])

        group[0] = ('a', 'b')
        self.assertListEqual(group[:], [('a', 'b')])

        group.append(('c',))
        self.assertListEqual(group[:], [('a', 'b'), ('c',)])

        del group[0]
        self.assertListEqual(group[:], [('c',)])

    def test_is_empty(self):
        group = ModelGroup('all')
        self.assertTrue(group.is_empty())
        group.append(('A',))
        self.assertFalse(group.is_empty())

    def test_is_pointless(self):
        root_group = ModelGroup('choice')
        group = ModelGroup('sequence')
        root_group.append(group)

        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('A',))
        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('B',))
        self.assertFalse(group.is_pointless(parent=root_group))

        root_group = ModelGroup('sequence')
        group = ModelGroup('choice')
        root_group.append(group)

        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('A',))
        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('B',))
        self.assertFalse(group.is_pointless(parent=root_group))

        root_group = ModelGroup('choice')
        group = ModelGroup('choice')
        root_group.append(group)

        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('A',))
        self.assertTrue(group.is_pointless(parent=root_group))
        group.append(('B',))
        self.assertTrue(group.is_pointless(parent=root_group))

    def test_effective_min_occurs(self):
        group = ModelGroup('sequence')
        self.assertEqual(group.effective_min_occurs, 0)
        group.append(ParticleMixin())
        self.assertEqual(group.effective_min_occurs, 1)
        group.append(ParticleMixin())
        group[0].min_occurs = 0
        self.assertEqual(group.effective_min_occurs, 1)
        group.model = 'choice'
        self.assertEqual(group.effective_min_occurs, 0)
        group[1].min_occurs = 0
        group.model = 'sequence'
        self.assertEqual(group.effective_min_occurs, 0)
        group.model = 'choice'
        group[0].min_occurs = group[1].min_occurs = 1
        self.assertEqual(group.effective_min_occurs, 1)

    def test_effective_max_occurs(self):
        group = ModelGroup('sequence')
        self.assertEqual(group.effective_max_occurs, 0)
        group.append(ParticleMixin())
        self.assertEqual(group.effective_max_occurs, 1)
        group.append(ParticleMixin(max_occurs=2))
        self.assertEqual(group.effective_max_occurs, 1)
        group[0].min_occurs = group[0].max_occurs = 0
        self.assertEqual(group.effective_max_occurs, 2)
        group[1].min_occurs = group[1].max_occurs = 0
        self.assertEqual(group.effective_max_occurs, 0)

        group.append(ParticleMixin())
        self.assertEqual(group.effective_max_occurs, 1)
        group[2].min_occurs = 0
        self.assertEqual(group.effective_max_occurs, 1)
        group[0].max_occurs = None
        self.assertIsNone(group.effective_max_occurs)
        group[2].min_occurs = 1

        group = ModelGroup('choice')
        group.append(ParticleMixin())
        self.assertEqual(group.effective_max_occurs, 1)
        group.append(ParticleMixin())
        group[0].min_occurs = group[0].max_occurs = 0
        self.assertEqual(group.effective_max_occurs, 1)
        group[0].max_occurs = None
        self.assertIsNone(group.effective_max_occurs)

        group = ModelGroup('sequence')
        group.append(ParticleMixin())
        self.assertEqual(group.effective_max_occurs, 1)
        group[0].max_occurs = None
        self.assertIsNone(group.effective_max_occurs)
        group[0].max_occurs = 1
        self.assertEqual(group.effective_max_occurs, 1)
        group.max_occurs = None
        self.assertIsNone(group.effective_max_occurs)

    def test_has_occurs_restriction(self):
        group = ModelGroup('sequence')
        other = ModelGroup('sequence')
        other.append(ParticleMixin())
        self.assertTrue(group.has_occurs_restriction(other))
        group.append(ParticleMixin())
        self.assertTrue(group.has_occurs_restriction(other))

        for model in ['sequence', 'all', 'choice']:
            group = ModelGroup(model)
            group.append(ParticleMixin())
            self.assertTrue(group.has_occurs_restriction(other=ParticleMixin()))
            self.assertFalse(group.has_occurs_restriction(other=ParticleMixin(2, 2)))
            self.assertTrue(group.has_occurs_restriction(other=ParticleMixin(1, None)))
            group.max_occurs = None
            self.assertFalse(group.has_occurs_restriction(other=ParticleMixin()))
            self.assertTrue(group.has_occurs_restriction(other=ParticleMixin(1, None)))

    def test_iter_model(self):
        # Model group with pointless inner groups
        root_group = group = ModelGroup('sequence')
        for k in range(3):
            for _ in range(k + 1):
                group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            group = group[-1]

        particles = [e for e in root_group.iter_model()]
        self.assertEqual(len(particles), 6)
        for e in particles:
            self.assertIsInstance(e, ParticleMixin)
            self.assertNotIsInstance(e, ModelGroup)

        # Model group with no-pointless inner groups
        root_group = group = ModelGroup('sequence')
        for k in range(3):
            for _ in range(k + 1):
                group.append(ParticleMixin())
            group.append(ModelGroup('sequence', max_occurs=None))
            group = group[-1]

        particles = [e for e in root_group.iter_model()]
        self.assertEqual(len(particles), 2)
        self.assertIsInstance(particles[0], ParticleMixin)
        self.assertNotIsInstance(particles[0], ModelGroup)
        self.assertIsInstance(particles[1], ModelGroup)

        # Model group with an excessive depth
        root_group = group = ModelGroup('sequence')
        for k in range(16):
            group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            group = group[1]

        with self.assertRaises(XMLSchemaModelDepthError):
            for _ in root_group.iter_model():
                pass

    def test_iter_elements(self):
        # Model group with pointless inner groups
        root_group = group = ModelGroup('sequence')
        for k in range(3):
            for _ in range(k + 1):
                group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            group = group[-1]

        particles = [e for e in root_group.iter_elements()]
        self.assertEqual(len(particles), 6)
        for e in particles:
            self.assertIsInstance(e, ParticleMixin)
            self.assertNotIsInstance(e, ModelGroup)

        # Model group with no-pointless inner groups
        root_group = group = ModelGroup('sequence')
        for k in range(3):
            for _ in range(k + 1):
                group.append(ParticleMixin())
            group.append(ModelGroup('sequence', max_occurs=None))
            group = group[-1]

        particles = [e for e in root_group.iter_elements()]
        self.assertEqual(len(particles), 6)
        for e in particles:
            self.assertIsInstance(e, ParticleMixin)
            self.assertNotIsInstance(e, ModelGroup)

        root_group.min_occurs = root_group.max_occurs = 0
        self.assertListEqual(list(root_group.iter_elements()), [])

        # Model group with an excessive depth
        root_group = group = ModelGroup('sequence')
        for k in range(16):
            group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            group = group[1]

        with self.assertRaises(XMLSchemaModelDepthError):
            for _ in root_group.iter_elements():
                pass

    def test_get_subgroups(self):
        # Model group with pointless inner groups
        root_group = group = ModelGroup('sequence')
        subgroups = []
        for k in range(4):
            for _ in range(k + 1):
                group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            subgroups.append(group)
            group = group[-1]

        self.assertListEqual(root_group.get_subgroups(group), subgroups)
        self.assertListEqual(root_group.get_subgroups(subgroups[-1][0]), subgroups)
        self.assertListEqual(root_group.get_subgroups(subgroups[-2][0]), subgroups[:-1])
        self.assertListEqual(root_group.get_subgroups(subgroups[-3][0]), subgroups[:-2])
        self.assertListEqual(root_group.get_subgroups(subgroups[-4][0]), subgroups[:-3])

        with self.assertRaises(XMLSchemaModelError):
            root_group.get_subgroups(ParticleMixin())

        # Model group with an excessive depth
        root_group = group = ModelGroup('sequence')
        for k in range(18):
            group.append(ParticleMixin())
            group.append(ModelGroup('sequence'))
            group = group[1]

        with self.assertRaises(XMLSchemaModelDepthError):
            root_group.get_subgroups(group)

    def test_overall_min_occurs(self):
        root_group = group = ModelGroup('sequence')
        subgroups = []
        for k in range(4):
            group.append(ParticleMixin())
            group.append(ModelGroup('sequence', max_occurs=10))
            subgroups.append(group)
            group = group[-1]

        self.assertEqual(root_group.overall_min_occurs(group), 1)
        root_group[1].min_occurs = 0
        self.assertEqual(root_group.overall_min_occurs(group), 0)
        root_group[1][1].min_occurs = 2
        self.assertEqual(root_group.overall_min_occurs(group), 0)
        root_group[1].min_occurs = 1
        self.assertEqual(root_group.overall_min_occurs(group), 2)
        root_group[1].min_occurs = 3
        self.assertEqual(root_group.overall_min_occurs(group), 6)

        root_group = group = ModelGroup('choice')
        subgroups = []
        for k in range(4):
            group.append(ParticleMixin())
            group.append(ModelGroup('choice', max_occurs=10))
            subgroups.append(group)
            group = group[-1]

        self.assertEqual(root_group.overall_min_occurs(group), 0)

    def test_overall_max_occurs(self):
        root_group = group = ModelGroup('sequence', min_occurs=0)
        subgroups = []
        for k in range(4):
            group.append(ParticleMixin())
            group.append(ModelGroup('sequence', min_occurs=0))
            subgroups.append(group)
            group = group[-1]

        self.assertEqual(root_group.overall_max_occurs(group), 1)
        root_group[1].max_occurs = 0
        self.assertEqual(root_group.overall_max_occurs(group), 0)
        root_group[1][1].max_occurs = 2
        self.assertEqual(root_group.overall_max_occurs(group), 0)
        root_group[1].max_occurs = 1
        self.assertEqual(root_group.overall_max_occurs(group), 2)
        root_group[1].max_occurs = 3
        self.assertEqual(root_group.overall_max_occurs(group), 6)
        root_group[1].max_occurs = None
        self.assertIsNone(root_group.overall_max_occurs(group))


if __name__ == '__main__':
    import platform

    header_template = "Test xmlschema's XSD groups with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
