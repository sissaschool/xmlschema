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
from xml.etree import ElementTree

from xmlschema import XMLSchema10, XMLSchemaParseError
from xmlschema.validators.particles import ParticleMixin

CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')


class TestParticleMixin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        xsd_file = os.path.join(CASES_DIR, 'examples/vehicles/vehicles.xsd')
        cls.schema = XMLSchema10(xsd_file)

    def test_occurs_property(self):
        self.assertEqual(self.schema.elements['cars'].occurs, (1, 1))
        self.assertEqual(self.schema.elements['cars'].type.content[0].occurs, (0, None))

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
        self.assertFalse(ParticleMixin().is_empty())
        self.assertTrue(ParticleMixin(min_occurs=0, max_occurs=0).is_empty())

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

    def test_default_parse_error(self):
        with self.assertRaises(ValueError) as ctx:
            ParticleMixin().parse_error('unexpected error')
        self.assertEqual(str(ctx.exception), 'unexpected error')

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


if __name__ == '__main__':
    import platform

    header_template = "Test xmlschema's XSD particles with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
