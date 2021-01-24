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
import os
import unittest

from xmlschema import XMLSchema10, XMLSchemaParseError, \
    XMLSchemaModelError, XMLSchemaModelDepthError
from xmlschema.etree import ElementTree
from xmlschema.validators.particles import ParticleMixin, ModelGroup

CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestParticleMixin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_occurs_property(self):
        self.assertListEqual(self.schema.elements['cars'].occurs, [1, 1])
        self.assertListEqual(self.schema.elements['cars'].type.content[0].occurs, [0, None])

    def test_effective_min_occurs_property(self):
        self.assertEqual(self.schema.elements['cars'].effective_min_occurs, 1)
        self.assertEqual(self.schema.elements['cars'].type.content[0].effective_min_occurs, 0)

    def test_effective_max_occurs_property(self):
        self.assertEqual(self.schema.elements['cars'].effective_max_occurs, 1)
        self.assertIsNone(self.schema.elements['cars'].type.content[0].effective_max_occurs)

    def test_is_emptiable(self):
        self.assertFalse(self.schema.elements['cars'].is_emptiable())
        self.assertTrue(self.schema.elements['cars'].type.content[0].is_emptiable())

    def test_is_empty(self):
        self.assertFalse(self.schema.elements['cars'].is_empty())

    def test_is_single(self):
        self.assertTrue(self.schema.elements['cars'].is_single())
        self.assertFalse(self.schema.elements['cars'].type.content[0].is_single())

        # The base method is used only by xs:any wildcards
        wildcard = self.schema.meta_schema.types['anyType'].content[0]
        self.assertFalse(wildcard.is_single())

    def test_is_multiple(self):
        self.assertFalse(self.schema.elements['cars'].is_multiple())

    def test_is_ambiguous(self):
        self.assertFalse(self.schema.elements['cars'].is_ambiguous())
        self.assertTrue(self.schema.elements['cars'].type.content[0].is_ambiguous())

    def test_is_univocal(self):
        self.assertTrue(self.schema.elements['cars'].is_univocal())
        self.assertFalse(self.schema.elements['cars'].type.content[0].is_univocal())

    def test_is_missing(self):
        self.assertTrue(self.schema.elements['cars'].is_missing(0))
        self.assertFalse(self.schema.elements['cars'].is_missing(1))
        self.assertFalse(self.schema.elements['cars'].is_missing(2))
        self.assertFalse(self.schema.elements['cars'].type.content[0].is_missing(0))

    def test_is_over(self):
        self.assertFalse(self.schema.elements['cars'].is_over(0))
        self.assertTrue(self.schema.elements['cars'].is_over(1))
        self.assertFalse(self.schema.elements['cars'].type.content[0].is_over(1000))

    def test_has_occurs_restriction(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:complexType name="barType">
                         <xs:sequence>
                             <xs:element name="node0" />
                             <xs:element name="node1" minOccurs="0"/>
                             <xs:element name="node2" minOccurs="0" maxOccurs="unbounded"/>
                             <xs:element name="node3" minOccurs="2" maxOccurs="unbounded"/>
                             <xs:element name="node4" minOccurs="2" maxOccurs="10"/>
                             <xs:element name="node5" minOccurs="4" maxOccurs="10"/>
                             <xs:element name="node6" minOccurs="4" maxOccurs="9"/>
                             <xs:element name="node7" minOccurs="1" maxOccurs="9"/>
                             <xs:element name="node8" minOccurs="3" maxOccurs="11"/>
                             <xs:element name="node9" minOccurs="0" maxOccurs="0"/>
                         </xs:sequence>
                     </xs:complexType>                             
                 </xs:schema>""")

        xsd_group = schema.types['barType'].content

        for k in range(9):
            self.assertTrue(
                xsd_group[k].has_occurs_restriction(xsd_group[k]), msg="Fail for node%d" % k
            )

        self.assertTrue(xsd_group[0].has_occurs_restriction(xsd_group[1]))
        self.assertFalse(xsd_group[1].has_occurs_restriction(xsd_group[0]))
        self.assertTrue(xsd_group[3].has_occurs_restriction(xsd_group[2]))
        self.assertFalse(xsd_group[2].has_occurs_restriction(xsd_group[1]))
        self.assertFalse(xsd_group[2].has_occurs_restriction(xsd_group[3]))
        self.assertTrue(xsd_group[4].has_occurs_restriction(xsd_group[3]))
        self.assertTrue(xsd_group[4].has_occurs_restriction(xsd_group[2]))
        self.assertFalse(xsd_group[4].has_occurs_restriction(xsd_group[5]))
        self.assertTrue(xsd_group[5].has_occurs_restriction(xsd_group[4]))
        self.assertTrue(xsd_group[6].has_occurs_restriction(xsd_group[5]))
        self.assertFalse(xsd_group[5].has_occurs_restriction(xsd_group[6]))
        self.assertFalse(xsd_group[7].has_occurs_restriction(xsd_group[6]))
        self.assertFalse(xsd_group[5].has_occurs_restriction(xsd_group[7]))
        self.assertTrue(xsd_group[6].has_occurs_restriction(xsd_group[7]))
        self.assertFalse(xsd_group[7].has_occurs_restriction(xsd_group[8]))
        self.assertFalse(xsd_group[8].has_occurs_restriction(xsd_group[7]))
        self.assertTrue(xsd_group[9].has_occurs_restriction(xsd_group[1]))
        self.assertTrue(xsd_group[9].has_occurs_restriction(xsd_group[2]))

    def test_parse_particle(self):
        schema = XMLSchema10("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                     <xs:element name="root"/>
                 </xs:schema>""")
        xsd_element = schema.elements['root']

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='1')
        xsd_element._parse_particle(elem)

        elem = ElementTree.Element('root', minOccurs='2', maxOccurs='1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs must be 'unbounded' or greater than minOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='-1', maxOccurs='1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs value must be a non negative integer", str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='-1')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs must be 'unbounded' or greater than minOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='1', maxOccurs='none')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("maxOccurs value must be a non negative integer or 'unbounded'",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='2')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs must be lesser or equal than maxOccurs",
                      str(ctx.exception))

        elem = ElementTree.Element('root', minOccurs='none')
        with self.assertRaises(XMLSchemaParseError) as ctx:
            xsd_element._parse_particle(elem)
        self.assertIn("minOccurs value is not an integer value",
                      str(ctx.exception))


class TestModelGroup(unittest.TestCase):

    def test_model_group_init(self):
        group = ModelGroup('sequence')
        self.assertEqual(group.model, 'sequence')

        with self.assertRaises(ValueError):
            ModelGroup('mixed')

    def test_model_group_repr(self):
        group = ModelGroup('choice')
        self.assertEqual(repr(group), "ModelGroup(model='choice', occurs=[1, 1])")

    def test_model_group_container(self):
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

    header_template = "Test xmlschema's XSD paricles with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
