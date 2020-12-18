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
"""Tests concerning model groups validation"""
import unittest
import os.path
from textwrap import dedent

from xmlschema import XMLSchema10, XMLSchema11
from xmlschema.validators import XsdElement, ModelVisitor, XMLSchemaValidationError
from xmlschema.validators.particles import ParticleMixin, ModelGroup
from xmlschema.validators.models import distinguishable_paths
from xmlschema.testing import XsdValidatorTestCase


class TestModelValidation(XsdValidatorTestCase):

    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), '../test_cases')
    schema_class = XMLSchema10

    # --- Test helper functions ---

    def check_advance_true(self, model, expected=None):
        """
        Advances a model with a match condition and checks the expected error list or exception.

        :param model: an ModelGroupVisitor instance.
        :param expected: can be an exception class or a list. Leaving `None` means that an empty \
        list is expected.
        """
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), True)
        else:
            self.assertEqual([e for e in model.advance(True)], expected or [])

    def check_advance_false(self, model, expected=None):
        """
        Advances a model with a no-match condition and checks the
        expected error list or  or exception.

        :param model: an ModelGroupVisitor instance.
        :param expected: can be an exception class or a list. Leaving `None` means that \
        an empty list is expected.
        """
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), False)
        else:
            self.assertEqual([e for e in model.advance(False)], expected or [])

    def check_advance(self, model, match, expected=None):
        """
        Advances a model with an argument match condition and checks the expected error list.

        :param model: an ModelGroupVisitor instance.
        :param match: the matching boolean condition.
        :param expected: can be an exception class or a list. Leaving `None` means that an empty \
        list is expected.
        """
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), match)
        else:
            self.assertEqual([e for e in model.advance(match)], expected or [])

    def check_stop(self, model, expected=None):
        """
        Stops a model and checks the expected errors list.

        :param model: an ModelGroupVisitor instance.
        :param expected: can be an exception class or a list. Leaving `None` means that an empty \
        list is expected.
        """
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda: list(model.stop()))
        else:
            self.assertEqual([e for e in model.stop()], expected or [])

    # --- ModelVisitor methods ---

    def test_iter_group(self):
        group = ModelGroup('sequence', min_occurs=0, max_occurs=0)
        model = ModelVisitor(group)
        self.assertListEqual(list(model.items), [])

        group = ModelGroup('choice')
        group.append(ParticleMixin())
        group.append(ParticleMixin())
        group.append(ParticleMixin())

        model = ModelVisitor(group)
        model.occurs[group[1]] = 1
        self.assertListEqual(list(model.items), group[1:])

        group = ModelGroup('all')
        group.append(ParticleMixin())
        group.append(ParticleMixin())
        group.append(ParticleMixin())

        model = ModelVisitor(group)
        model.occurs[group[1]] = 1
        self.assertListEqual(list(model.items), group[2:])

    # --- Vehicles schema ---

    def test_vehicles_model(self):
        # Sequence with two not-emptiable single-occurs elements
        group = self.vh_schema.elements['vehicles'].type.content

        model = ModelVisitor(group)
        self.check_advance_true(model)                # <cars>
        self.check_advance_true(model)                # <bikes>
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_true(model)                # <cars>
        self.check_advance_true(model)                # <bikes>
        self.check_advance_true(model, ValueError)    # <bikes>
        self.assertIsNone(model.element)

    def test_cars_model(self):
        # Emptiable 1:1 sequence with one emptiable and unlimited element.
        group = self.vh_schema.elements['cars'].type.content

        model = ModelVisitor(group)
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_false(model)    # (end)
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model)    # <not-a-car>
        self.assertIsNone(model.element)

    # --- Collection schema ---

    def test_collection_model(self):
        # Sequence with one not-emptiable and unlimited element.
        group = self.col_schema.elements['collection'].type.content

        model = ModelVisitor(group)
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_false(model)    # (end)
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model, [(group[0], 0, [group[0]])])  # <not-a-car>
        self.assertIsNone(model.element)

    def test_person_type_model(self):
        # Sequence with four single elements, last two are also emptiable.
        group = self.col_schema.types['personType'].content

        model = ModelVisitor(group)
        self.check_advance_true(model)     # <name>
        self.check_advance_true(model)     # <born>
        self.check_advance_true(model)     # <dead>
        self.check_advance_true(model)     # <qualification>
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_true(model)     # <name>
        self.check_advance_true(model)     # <born>
        self.check_stop(model)
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_true(model)                                # <name> match
        self.check_advance_false(model, [(group[1], 0, [group[1]])])  # <born> missing!
        self.check_advance_true(model)                                # <dead> match
        self.check_stop(model)                                        # <qualification> is optional
        self.assertIsNone(model.element)

    # --- XSD 1.0/1.1 meta-schema models ---

    def test_meta_simple_derivation_model(self):
        """
        <xs:group name="simpleDerivation">
          <xs:choice>
            <xs:element ref="xs:restriction"/>
            <xs:element ref="xs:list"/>
            <xs:element ref="xs:union"/>
          </xs:choice>
        </xs:group>
        """
        group = XMLSchema10.meta_schema.groups['simpleDerivation']

        model = ModelVisitor(group)
        self.check_advance_true(model)     # <restriction> matches
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model)    # <list> doesn't match with <restriction>
        self.check_advance_true(model)     # <list> matches
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model)    # <union> doesn't match with <restriction>
        self.check_advance_false(model)    # <union> doesn't match with <list>
        self.check_advance_true(model)     # <union> matches
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model)  # <other> doesn't match with <restriction>
        self.check_advance_false(model)  # <other> doesn't match with <list>
        self.check_advance_false(model,
                                 [(group, 0, group[:])])  # <other> doesn't match with <union>
        self.assertIsNone(model.element)

    def test_meta_simple_restriction_model(self):
        """
        <!-- XSD 1.0 -->
        <xs:group name="facets">
          <xs:choice>
            <xs:element ref="xs:minExclusive"/>
            <xs:element ref="xs:minInclusive"/>
            <xs:element ref="xs:maxExclusive"/>
            <xs:element ref="xs:maxInclusive"/>
            <xs:element ref="xs:totalDigits"/>
            <xs:element ref="xs:fractionDigits"/>
            <xs:element ref="xs:length"/>
            <xs:element ref="xs:minLength"/>
            <xs:element ref="xs:maxLength"/>
            <xs:element ref="xs:enumeration"/>
            <xs:element ref="xs:whiteSpace"/>
            <xs:element ref="xs:pattern"/>
          </xs:choice>
        </xs:group>

        <xs:group name="simpleRestrictionModel">
          <xs:sequence>
            <xs:element name="simpleType" type="xs:localSimpleType" minOccurs="0"/>
            <xs:group ref="xs:facets" minOccurs="0" maxOccurs="unbounded"/>
          </xs:sequence>
        </xs:group>

        <!-- XSD 1.1 -->
        <xs:group name="simpleRestrictionModel">
          <xs:sequence>
            <xs:element name="simpleType" type="xs:localSimpleType" minOccurs="0"/>
            <xs:choice minOccurs="0" maxOccurs="unbounded">
              <xs:element ref="xs:facet"/>  <!-- Use a substitution group -->
              <xs:any processContents="lax" namespace="##other"/>
            </xs:choice>
          </xs:sequence>
        </xs:group>
        """
        # Sequence with an optional single element and an optional unlimited choice.
        group = self.schema_class.meta_schema.groups['simpleRestrictionModel']

        model = ModelVisitor(group)

        if self.schema_class.XSD_VERSION == '1.0':
            self.assertEqual(model.element, group[0])
            self.check_advance_true(model)      # <simpleType> matches
            self.assertEqual(model.element, group[1][0][0])
            self.check_advance_false(model)     # <maxExclusive> does not match
            self.assertEqual(model.element, group[1][0][1])
            self.check_advance_false(model)     # <maxExclusive> does not match
            self.assertEqual(model.element, group[1][0][2])
            self.check_advance_true(model)      # <maxExclusive> matches
            self.assertEqual(model.element, group[1][0][0])
            for _ in range(12):
                self.check_advance_false(model)  # no match for the inner choice group "xs:facets"
            self.assertIsNone(model.element)

    def test_meta_schema_top_model(self):
        """
        <xs:group name="schemaTop">
          <xs:choice>
            <xs:group ref="xs:redefinable"/>
            <xs:element ref="xs:element"/>
            <xs:element ref="xs:attribute"/>
            <xs:element ref="xs:notation"/>
          </xs:choice>
        </xs:group>

        <xs:group name="redefinable">
          <xs:choice>
            <xs:element ref="xs:simpleType"/>
            <xs:element ref="xs:complexType"/>
            <xs:element ref="xs:group"/>
            <xs:element ref="xs:attributeGroup"/>
          </xs:choice>
        </xs:group>
        """
        group = self.schema_class.meta_schema.groups['schemaTop']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> doesn't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_true(model)                  # <complexType> matches
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> doesn't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_false(model)                 # <complexType> doesn't match
        self.assertEqual(model.element, group[0][0][2])
        self.check_advance_false(model)                 # <group> doesn't match
        self.assertEqual(model.element, group[0][0][3])
        self.check_advance_false(model)                 # <attributeGroup> doesn't match
        self.assertEqual(model.element, group[1])
        self.check_advance_false(model)                 # <element> doesn't match
        self.assertEqual(model.element, group[2])
        self.check_advance_false(model)                 # <attribute> doesn't match
        self.assertEqual(model.element, group[3])
        self.check_advance_false(
            model, [(group, 0, group[0][0][:] + group[1:])])  # <notation> doesn't match

        model.restart()
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> doesn't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_false(model)                 # <complexType> doesn't match
        self.assertEqual(model.element, group[0][0][2])
        self.check_advance_false(model)                 # <group> doesn't match
        self.assertEqual(model.element, group[0][0][3])
        self.check_advance_false(model)                 # <attributeGroup> doesn't match
        self.assertEqual(model.element, group[1])
        self.check_advance_false(model)                 # <element> doesn't match
        self.assertEqual(model.element, group[2])
        self.check_advance_true(model)                  # <attribute> doesn't match
        self.assertIsNone(model.element)

    def test_meta_attr_declarations_group(self):
        """
        <xs:group name="attrDecls">
          <xs:sequence>
            <xs:choice minOccurs="0" maxOccurs="unbounded">
              <xs:element name="attribute" type="xs:attribute"/>
              <xs:element name="attributeGroup" type="xs:attributeGroupRef"/>
            </xs:choice>
            <xs:element ref="xs:anyAttribute" minOccurs="0"/>
          </xs:sequence>
        </xs:group>
        """
        group = self.schema_class.meta_schema.groups['attrDecls']

        model = ModelVisitor(group)
        for match in [False, False, True]:
            self.check_advance(model, match)
        self.assertIsNone(model.element)

        model = ModelVisitor(group)
        self.check_advance_false(model)
        self.check_advance_true(model)
        self.assertEqual(model.element, group[0][0])

        model = ModelVisitor(group)
        for match in [False, True, False, False]:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[1])

        model = ModelVisitor(group)
        for match in [False, True, True, False, True, False, False]:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[1])

    def test_meta_complex_type_model(self):
        """
        <xs:group name="complexTypeModel">
          <xs:choice>
            <xs:element ref="xs:simpleContent"/>
            <xs:element ref="xs:complexContent"/>
            <xs:sequence>
              <xs:group ref="xs:typeDefParticle" minOccurs="0"/>
              <xs:group ref="xs:attrDecls"/>
            </xs:sequence>
          </xs:choice>
        </xs:group>

        <xs:group name="typeDefParticle">
          <xs:choice>
            <xs:element name="group" type="xs:groupRef"/>
            <xs:element ref="xs:all"/>
            <xs:element ref="xs:choice"/>
            <xs:element ref="xs:sequence"/>
          </xs:choice>
        </xs:group>

        <xs:group name="complexTypeModel">
          <xs:choice>
            <xs:element ref="xs:simpleContent"/>
            <xs:element ref="xs:complexContent"/>
            <xs:sequence>
              <xs:element ref="xs:openContent" minOccurs="0"/>
              <xs:group ref="xs:typeDefParticle" minOccurs="0"/>
              <xs:group ref="xs:attrDecls"/>
              <xs:group ref="xs:assertions"/>
            </xs:sequence>
          </xs:choice>
        </xs:group>

        """
        group = self.schema_class.meta_schema.groups['complexTypeModel']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_advance_true(model)                  # <simpleContent> matches
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0])
        self.check_advance_false(model)
        self.check_advance_true(model)                  # <complexContent> matches
        self.assertIsNone(model.element)

        if self.schema_class.XSD_VERSION == '1.0':
            model.restart()
            self.assertEqual(model.element, group[0])
            for match in [False, False, False, False, True]:
                self.check_advance(model, match)            # <all> matches
            self.check_stop(model)
            self.assertIsNone(model.element)

            model.restart()
            self.assertEqual(model.element, group[0])
            for match in [False, False, False, False, True, False, True, False, False, False]:
                self.check_advance(model, match)            # <all> and <attributeGroup> match
            self.assertIsNone(model.element)

    def test_meta_schema_document_model(self):
        group = self.schema_class.meta_schema.elements['schema'].type.content

        # A schema model with a wrong tag
        model = ModelVisitor(group)
        if self.schema_class.XSD_VERSION == '1.0':
            self.assertEqual(model.element, group[0][0])
            self.check_advance_false(model)                 # eg. anyAttribute
            self.check_stop(model)
        else:
            self.assertEqual(model.element, group[0][0][0])

    #
    # Tests on schema test_cases/features/models/models.xsd
    def test_model_group1(self):
        group = self.models_schema.groups['group1']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_stop(model)

        model.restart()
        self.assertEqual(model.element, group[0])
        for _ in range(3):
            self.check_advance_false(model)
        self.assertIsNone(model.element)

        model.restart()
        for match in [False, True, False]:
            self.check_advance(model, match)
        self.assertIsNone(model.element)

    def test_model_group2(self):
        group = self.models_schema.groups['group2']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for _ in range(3):
            self.check_advance_false(model)                 # group1 do not match
        self.assertEqual(model.element, group[1][0][0][2])  # <elem3> of group1
        for _ in range(8):
            self.check_advance_false(model)
        self.assertEqual(model.element, group[2])           # <elem12>
        self.check_advance_false(model)
        self.assertEqual(model.element, group[3])           # <elem13>
        self.check_advance_false(model)
        self.assertIsNone(model.element)

    def test_model_group3(self):
        group = self.models_schema.groups['group3']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for match in [True, False, True]:
            self.check_advance(model, match)
        self.check_stop(model)

    def test_model_group4(self):
        group = self.models_schema.groups['group4']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for match in [True, False, True]:
            self.check_advance(model, match)
        self.check_stop(model)

    def test_model_group5(self):
        group = self.models_schema.groups['group5']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        for _ in range(5):   # match [<elem1> .. <elem5>]
            self.check_advance_true(model)
        self.assertEqual(model.element.name, 'elem6')
        self.check_advance_true(model)                 # match choice with <elem6>
        self.check_stop(model)

    def test_model_group6(self):
        group = self.models_schema.groups['group6']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_advance_true(model)                 # match choice with <elem1>
        self.check_advance_true(model)                 # match choice with <elem2>
        self.assertIsNone(model.element)

    def test_model_group7(self):
        group = self.models_schema.types['complexType7'].content

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_stop(model, [(group[0][0], 0, [group[0][0]])])

        group = self.models_schema.types['complexType7_emptiable'].content

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_stop(model)

    def test_model_group8(self):
        group = self.models_schema.groups['group8']

        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_advance_true(model)                 # match choice with <elem1>
        self.check_advance_false(model)
        self.assertEqual(model.element, group[0][1])
        self.check_advance_true(model)                 # match choice with <elem2>
        self.assertEqual(model.element, group[0][2])
        self.check_advance_true(model)                 # match choice with <elem3>
        self.assertEqual(model.element, group[0][3])
        self.check_advance_true(model)                 # match choice with <elem4>
        self.assertIsNone(model.element)

    #
    # Test pathological cases
    def test_empty_choice_groups(self):
        schema = self.schema_class("""<?xml version="1.0"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:group name="group1">
                <xs:sequence>
                    <xs:choice minOccurs="0">
                        <xs:choice minOccurs="0"/>
                    </xs:choice>
                    <xs:element name="elem1"/>
                </xs:sequence>
            </xs:group>
            <xs:element name="root">
                <xs:complexType>
                    <xs:choice>
                        <xs:group ref="group1"/>
                    </xs:choice>
                </xs:complexType>
            </xs:element>
        </xs:schema>""")

        xml_data = "<root><elem1/></root>"
        model = ModelVisitor(schema.elements['root'].type.content)
        self.assertIsInstance(model.element, XsdElement)
        self.assertEqual(model.element.name, 'elem1')
        self.assertIsNone(schema.validate(xml_data))

        # W3C test group 'complex022'
        schema = self.schema_class("""<?xml version="1.0" encoding="utf-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="root">
                <xs:complexType>
                    <xs:choice/>
                </xs:complexType>
            </xs:element>
        </xs:schema>""")

        reason = "an empty 'choice' group with minOccurs > 0 cannot validate any content"
        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate("<root><elem1/></root>")
        self.assertIn(reason, str(ctx.exception))

        with self.assertRaises(XMLSchemaValidationError) as ctx:
            schema.validate("<root/>")
        self.assertIn(reason, str(ctx.exception))

    def test_single_item_groups(self):
        schema = self.schema_class("""<?xml version="1.0"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element name="a1">
                <xs:complexType>
                    <xs:choice>
                        <xs:any maxOccurs="2" processContents="lax"/>
                    </xs:choice>
                </xs:complexType>                
            </xs:element>
            <xs:element name="a2">
                <xs:complexType>
                    <xs:choice>
                        <xs:any maxOccurs="2" processContents="strict"/>
                    </xs:choice>
                </xs:complexType>                
            </xs:element>
            <xs:element name="a3">
                <xs:complexType>
                    <xs:sequence>
                        <xs:any maxOccurs="2" processContents="lax"/>
                    </xs:sequence>
                </xs:complexType>                
            </xs:element>
            <xs:element name="a4">
                <xs:complexType>
                    <xs:choice>
                        <xs:element name="b" maxOccurs="2"/>
                    </xs:choice>
                </xs:complexType>                
            </xs:element>
            <xs:element name="a5">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="b" maxOccurs="2"/>
                    </xs:sequence>
                </xs:complexType>                
            </xs:element>
            <xs:element name="b"/>
        </xs:schema>""")

        self.assertFalse(schema.is_valid('<a1></a1>'))
        self.assertFalse(schema.is_valid('<a2></a2>'))
        self.assertFalse(schema.is_valid('<a3></a3>'))
        self.assertFalse(schema.is_valid('<a4></a4>'))
        self.assertFalse(schema.is_valid('<a5></a5>'))

        self.assertTrue(schema.is_valid('<a1><c/></a1>'))
        self.assertFalse(schema.is_valid('<a2><c/></a2>'))
        self.assertTrue(schema.is_valid('<a3><c/></a3>'))
        self.assertFalse(schema.is_valid('<a4><c/></a4>'))
        self.assertFalse(schema.is_valid('<a5><c/></a5>'))

        self.assertTrue(schema.is_valid('<a1><b/></a1>'))
        self.assertTrue(schema.is_valid('<a2><b/></a2>'))
        self.assertTrue(schema.is_valid('<a3><b/></a3>'))
        self.assertTrue(schema.is_valid('<a4><b/></a4>'))
        self.assertTrue(schema.is_valid('<a5><b/></a5>'))

        self.assertTrue(schema.is_valid('<a1><b/><b/></a1>'))
        self.assertTrue(schema.is_valid('<a2><b/><b/></a2>'))
        self.assertTrue(schema.is_valid('<a3><b/><b/></a3>'))
        self.assertTrue(schema.is_valid('<a4><b/><b/></a4>'))
        self.assertTrue(schema.is_valid('<a5><b/><b/></a5>'))

        self.assertFalse(schema.is_valid('<a1><b/><b/><b/></a1>'))
        self.assertFalse(schema.is_valid('<a2><b/><b/><b/></a2>'))
        self.assertFalse(schema.is_valid('<a3><b/><b/><b/></a3>'))
        self.assertFalse(schema.is_valid('<a4><b/><b/><b/></a4>'))
        self.assertFalse(schema.is_valid('<a5><b/><b/><b/></a5>'))

    def test_sequence_model_with_extended_occurs(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence minOccurs="2" maxOccurs="unbounded">
                            <xs:element name="ax" maxOccurs="unbounded"/>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><ax/><ax/></root>'))

        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence minOccurs="0" maxOccurs="unbounded">
                            <xs:element name="a" minOccurs="2" maxOccurs="unbounded"/>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/><a/><a/><a/></root>'))

    def test_sequence_model_with_nested_choice_model(self):

        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence minOccurs="0" maxOccurs="unbounded">
                            <xs:group ref="group1" minOccurs="2" maxOccurs="unbounded"/>
                        </xs:sequence>
                    </xs:complexType>
                </xs:element>
                <xs:group name="group1">
                    <xs:choice>
                        <xs:element name="a" maxOccurs="unbounded"/>
                        <xs:element name="b"/>
                        <xs:element name="c"/>
                    </xs:choice>
                </xs:group>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/><a/><a/><a/></root>'))

    def test_sequence_model_with_optional_elements(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:sequence minOccurs="2" maxOccurs="2">
                            <xs:element name="a" minOccurs="1" maxOccurs="2" />
                            <xs:element name="b" minOccurs="0" />
                        </xs:sequence>
                    </xs:complexType>
               </xs:element>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><a/><a/><b/></root>'))

    def test_choice_model_with_extended_occurs(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:choice maxOccurs="unbounded" minOccurs="0">
                            <xs:element maxOccurs="5" minOccurs="3" name="a"/>
                            <xs:element maxOccurs="5" minOccurs="3" name="b"/>
                        </xs:choice>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><a/><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/><a/><a/></root>'))
        self.assertIsNone(schema.validate('<root><a/><a/><a/><a/><a/><a/></root>'))

        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                    <xs:choice minOccurs="2" maxOccurs="3">
                        <xs:element name="a" maxOccurs="unbounded"/>
                        <xs:element name="b" maxOccurs="unbounded"/>
                        <xs:element name="c"/>
                    </xs:choice>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate('<root><a/><a/><a/></root>'))

    def test_emptiable_all_model(self):
        schema = self.schema_class(dedent(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:all minOccurs="0">
                            <xs:element name="a" />
                            <xs:element name="b" />
                        </xs:all>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """))

        self.assertIsNone(schema.validate('<root><b/><a/></root>'))
        self.assertIsNone(schema.validate('<root/>'))
        self.assertFalse(schema.is_valid('<root><b/></root>'))

    #
    # Tests on issues
    def test_issue_086(self):
        issue_086_xsd = self.casepath('issues/issue_086/issue_086.xsd')
        schema = self.schema_class(issue_086_xsd)
        group = schema.types['Foo'].content

        # issue_086-1.xml sequence simulation
        model = ModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_advance_true(model)  # <header> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_true(model)  # <a> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_true(model)  # <a> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][1][0])  # 'b' element
        self.check_advance_true(model)  # <b> matching
        self.assertEqual(model.element, group[1][1][0])  # 'b' element
        self.check_advance_true(model)  # <b> matching
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][0][0])  # 'a' element (choice group restarted)
        self.check_advance_false(model)
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][2][0])  # 'c' element
        self.check_advance_true(model)  # <c> matching
        self.assertEqual(model.element, group[1][2][0])  # 'c' element
        self.check_advance_true(model)  # <c> matching
        self.check_stop(model)

        # issue_086-2.xml sequence simulation
        model = ModelVisitor(group)
        self.check_advance_true(model)  # <header> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][1][0])  # 'b' element
        self.check_advance_true(model)  # <b> matching
        self.assertEqual(model.element, group[1][1][0])  # 'b' element
        self.check_advance_true(model)  # <b> matching
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][0][0])  # 'a' element (choice group restarted)
        self.check_advance_false(model)
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][2][0])  # 'c' element
        self.check_advance_true(model)  # <c> matching
        self.assertEqual(model.element, group[1][2][0])  # 'c' element
        self.check_advance_true(model)  # <c> matching
        self.check_advance_false(model)
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_true(model)  # <a> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_advance_true(model)  # <a> matching
        self.assertEqual(model.element, group[1][0][0])  # 'a' element
        self.check_stop(model)


class TestModelValidation11(TestModelValidation):
    schema_class = XMLSchema11

    def test_all_model_with_wildcard(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:all>
                            <xs:element name="a" type="xs:string" />
                            <xs:any maxOccurs="3" processContents="lax" />
                        </xs:all>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        xml_data = """
            <root>
              <wildcard1/>
              <a>1</a>
              <wildcard2/>
              <wildcard3/>
            </root>
            """

        self.assertIsNone(schema.validate(xml_data))

    def test_all_model_with_extended_occurs(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:all>
                            <xs:element name="a" minOccurs="0" maxOccurs="5"/>
                            <xs:element name="b" maxOccurs="5"/>
                            <xs:element name="c" minOccurs="2" maxOccurs="5"/>
                            <xs:element name="d" />
                        </xs:all>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        xml_data = '<root><a/><b/><d/><c/><a/><c/></root>'

        self.assertIsNone(schema.validate(xml_data))

    def test_all_model_with_relaxed_occurs(self):
        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:all>
                            <xs:element name="a" minOccurs="0" maxOccurs="5"/>
                            <xs:element name="b" maxOccurs="5"/>
                            <xs:element name="c" minOccurs="2" maxOccurs="unbounded"/>
                            <xs:element name="d" />
                        </xs:all>
                    </xs:complexType>
                </xs:element>
            </xs:schema>
            """)

        xml_data = '<root><a/><b/><d/><c/><a/><c/><c/><a/><a/><b/></root>'

        self.assertIsNone(schema.validate(xml_data))

        schema = self.schema_class(
            """<?xml version="1.0" encoding="UTF-8"?>
            <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
                <xs:element name="root">
                    <xs:complexType>
                        <xs:all>
                            <xs:element name="a" minOccurs="0" maxOccurs="5"/>
                            <xs:group ref="group1"/>
                        </xs:all>
                    </xs:complexType>
                </xs:element>

                <xs:group name="group1">
                    <xs:all>
                        <xs:element name="b" maxOccurs="5"/>
                        <xs:element name="c" minOccurs="2" maxOccurs="unbounded"/>
                        <xs:element name="d" />
                    </xs:all>
                </xs:group>
            </xs:schema>
            """)

        self.assertIsNone(schema.validate(xml_data))


class TestModelBasedSorting(XsdValidatorTestCase):
    TEST_CASES_DIR = os.path.join(os.path.dirname(__file__), 'test_cases')

    def test_sort_content(self):
        # test of ModelVisitor's sort_content/iter_unordered_content
        schema = self.get_schema("""
            <xs:element name="A" type="A_type" />
            <xs:complexType name="A_type">
                <xs:sequence>
                    <xs:element name="B1" type="xs:string"/>
                    <xs:element name="B2" type="xs:integer"/>
                    <xs:element name="B3" type="xs:boolean"/>
                </xs:sequence>
            </xs:complexType>
            """)

        model = ModelVisitor(schema.types['A_type'].content)

        self.assertListEqual(
            model.sort_content([('B2', 10), ('B1', 'abc'), ('B3', True)], restart=False),
            [('B1', 'abc'), ('B2', 10), ('B3', True)]
        )
        self.assertListEqual(
            model.sort_content([('B2', 10), ('B1', 'abc'), ('B3', True)]),
            [('B1', 'abc'), ('B2', 10), ('B3', True)]
        )
        self.assertListEqual(
            model.sort_content([('B2', 10), ('B1', 'abc'), ('B3', True)], restart=False),
            [('B2', 10), ('B1', 'abc'), ('B3', True)]
        )

        self.assertListEqual(
            model.sort_content([('B3', True), ('B2', 10), ('B1', 'abc')]),
            [('B1', 'abc'), ('B2', 10), ('B3', True)]
        )
        self.assertListEqual(
            model.sort_content([('B2', 10), ('B4', None), ('B1', 'abc'), ('B3', True)]),
            [('B1', 'abc'), ('B2', 10), ('B3', True), ('B4', None)]
        )

        content = [('B2', 10), ('B4', None), ('B1', 'abc'), (1, 'hello'), ('B3', True)]
        self.assertListEqual(
            model.sort_content(content),
            [(1, 'hello'), ('B1', 'abc'), ('B2', 10), ('B3', True), ('B4', None)]
        )

        content = [
            (2, 'world!'), ('B2', 10), ('B4', None), ('B1', 'abc'), (1, 'hello'), ('B3', True)
        ]
        self.assertListEqual(
            model.sort_content(content),
            [(1, 'hello'), ('B1', 'abc'), (2, 'world!'), ('B2', 10), ('B3', True), ('B4', None)]
        )

        content = [
            ('B2', 10), ('B4', None), ('B1', 'abc'), ('B3', True), (6, 'six'),
            (5, 'five'), (4, 'four'), (2, 'two'), (3, 'three'), (1, 'one')
        ]
        self.assertListEqual(
            model.sort_content(content),
            [(1, 'one'), ('B1', 'abc'), (2, 'two'), ('B2', 10), (3, 'three'),
             ('B3', True), (4, 'four'), ('B4', None), (5, 'five'), (6, 'six')]
        )

        # With a dict-type argument
        content = dict([('B2', [10]), ('B1', ['abc']), ('B3', [True])])
        self.assertListEqual(
            model.sort_content(content), [('B1', 'abc'), ('B2', 10), ('B3', True)]
        )
        content = dict([('B2', [10]), ('B1', ['abc']), ('B3', [True]), (1, 'hello')])
        self.assertListEqual(
            model.sort_content(content), [(1, 'hello'), ('B1', 'abc'), ('B2', 10), ('B3', True)]
        )

        # With partial content
        self.assertListEqual(model.sort_content([]), [])
        self.assertListEqual(model.sort_content([('B1', 'abc')]), [('B1', 'abc')])
        self.assertListEqual(model.sort_content([('B2', 10)]), [('B2', 10)])
        self.assertListEqual(model.sort_content([('B3', True)]), [('B3', True)])
        self.assertListEqual(
            model.sort_content([('B3', True), ('B1', 'abc')]), [('B1', 'abc'), ('B3', True)]
        )
        self.assertListEqual(
            model.sort_content([('B2', 10), ('B1', 'abc')]), [('B1', 'abc'), ('B2', 10)]
        )
        self.assertListEqual(
            model.sort_content([('B3', True), ('B2', 10)]), [('B2', 10), ('B3', True)]
        )

    def test_iter_collapsed_content_with_optional_elements(self):
        schema = self.get_schema("""
            <xs:element name="A" type="A_type" />
            <xs:complexType name="A_type">
                <xs:sequence>
                    <xs:element name="B1" minOccurs="0" />
                    <xs:element name="B2" minOccurs="0" />
                    <xs:element name="B3" />
                    <xs:element name="B4" />
                    <xs:element name="B5" />
                    <xs:element name="B6" minOccurs="0" />
                    <xs:element name="B7" />
                </xs:sequence>
            </xs:complexType>
            """)

        model = ModelVisitor(schema.types['A_type'].content)

        content = [('B3', 10), ('B4', None), ('B5', True), ('B6', 'alpha'), ('B7', 20)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)), content
        )

        content = [('B3', 10), ('B5', True), ('B6', 'alpha'), ('B7', 20)]  # Missing B4
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)), content
        )

    def test_iter_collapsed_content_with_repeated_elements(self):
        schema = self.get_schema("""
            <xs:element name="A" type="A_type" />
            <xs:complexType name="A_type">
                <xs:sequence>
                    <xs:element name="B1" minOccurs="0" />
                    <xs:element name="B2" minOccurs="0" maxOccurs="unbounded" />
                    <xs:element name="B3" maxOccurs="unbounded" />
                    <xs:element name="B4" />
                    <xs:element name="B5" maxOccurs="unbounded" />
                    <xs:element name="B6" minOccurs="0" />
                    <xs:element name="B7" maxOccurs="unbounded" />
                </xs:sequence>
            </xs:complexType>
            """)

        model = ModelVisitor(schema.types['A_type'].content)

        content = [
            ('B3', 10), ('B4', None), ('B5', True), ('B5', False), ('B6', 'alpha'), ('B7', 20)
        ]
        self.assertListEqual(
            list(model.iter_collapsed_content(content)), content
        )

        content = [('B3', 10), ('B3', 11), ('B3', 12), ('B4', None), ('B5', True),
                   ('B5', False), ('B6', 'alpha'), ('B7', 20), ('B7', 30)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)), content
        )

        content = [('B3', 10), ('B3', 11), ('B3', 12), ('B4', None), ('B5', True), ('B5', False)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)), content
        )

    def test_iter_collapsed_content_with_repeated_groups(self):
        schema = self.get_schema("""
            <xs:element name="A" type="A_type" />
            <xs:complexType name="A_type">
                <xs:sequence minOccurs="1" maxOccurs="2">
                    <xs:element name="B1" minOccurs="0" />
                    <xs:element name="B2" minOccurs="0" />
                </xs:sequence>
            </xs:complexType>
            """)

        model = ModelVisitor(schema.types['A_type'].content)

        content = [('B1', 1), ('B1', 2), ('B2', 3), ('B2', 4)]
        self.assertListEqual(
            list(model.iter_collapsed_content(content)),
            [('B1', 1), ('B2', 3), ('B1', 2), ('B2', 4)]
        )

        # Model broken by unknown element at start
        content = [('X', None), ('B1', 1), ('B1', 2), ('B2', 3), ('B2', 4)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B1', 1), ('X', None), ('B1', 2), ('B2', 3), ('B2', 4)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B1', 1), ('B1', 2), ('X', None), ('B2', 3), ('B2', 4)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B1', 1), ('B1', 2), ('B2', 3), ('X', None), ('B2', 4)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)),
            [('B1', 1), ('B2', 3), ('B1', 2), ('X', None), ('B2', 4)]
        )

        content = [('B1', 1), ('B1', 2), ('B2', 3), ('B2', 4), ('X', None)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)),
            [('B1', 1), ('B2', 3), ('B1', 2), ('B2', 4), ('X', None)]
        )

    def test_iter_collapsed_content_with_single_elements(self):
        schema = self.get_schema("""
            <xs:element name="A" type="A_type" />
            <xs:complexType name="A_type">
                <xs:sequence>
                    <xs:element name="B1" />
                    <xs:element name="B2" />
                    <xs:element name="B3" />
                </xs:sequence>
            </xs:complexType>
            """)

        model = ModelVisitor(schema.types['A_type'].content)

        content = [('B1', 'abc'), ('B2', 10), ('B3', False)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B3', False), ('B1', 'abc'), ('B2', 10)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B1', 'abc'), ('B3', False), ('B2', 10)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('B1', 'abc'), ('B1', 'def'), ('B2', 10), ('B3', False)]
        model.restart()
        self.assertListEqual(
            list(model.iter_collapsed_content(content)),
            [('B1', 'abc'), ('B2', 10), ('B3', False), ('B1', 'def')]
        )

        content = [('B1', 'abc'), ('B2', 10), ('X', None)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)

        content = [('X', None), ('B1', 'abc'), ('B2', 10), ('B3', False)]
        model.restart()
        self.assertListEqual(list(model.iter_collapsed_content(content)), content)


class TestModelPaths(unittest.TestCase):

    def test_distinguishable_paths_one_level(self):
        group = ModelGroup('sequence', min_occurs=0)
        group.append(ModelGroup('sequence'))
        group.append(ModelGroup('sequence'))
        group[0].append(ParticleMixin())
        group[1].append(ParticleMixin())

        path1 = [group[0]]
        path2 = [group[1]]
        self.assertTrue(distinguishable_paths(path1, path2))  # Disjoined paths
        self.assertTrue(distinguishable_paths(path1, []))

        with self.assertRaises(IndexError):
            distinguishable_paths([], path2)  # path1 cannot be empty

        path1 = [group, group[0]]
        path2 = [group, group[1]]
        self.assertTrue(distinguishable_paths(path1, path2))
        group[0].min_occurs = 0
        self.assertFalse(distinguishable_paths(path1, path2))
        group.max_occurs = 0
        self.assertTrue(distinguishable_paths(path1, path2))

    def test_distinguishable_paths_two_levels(self):
        group = ModelGroup('sequence', min_occurs=0)
        group.append(ModelGroup('choice'))
        group.append(ModelGroup('choice'))
        group[0].append(ParticleMixin())
        group[0].append(ParticleMixin())
        group[1].append(ParticleMixin())
        group[1].append(ParticleMixin())

        path1 = [group, group[0], group[0][0]]
        path2 = [group, group[1], group[1][0]]
        self.assertTrue(distinguishable_paths(path1, path2))  # All univocal subgroups
        group[0].max_occurs = 2
        self.assertFalse(distinguishable_paths(path1, path2))

        group[0].max_occurs = 1
        group[0].min_occurs = 0
        self.assertFalse(distinguishable_paths(path1, path2))

        group.max_occurs = None
        self.assertFalse(distinguishable_paths(path1, path2))

    def test_distinguishable_paths_three_levels(self):
        group = ModelGroup('sequence', min_occurs=0)
        group.append(ModelGroup('choice'))
        group.append(ModelGroup('choice'))
        group[0].append(ModelGroup('choice'))
        group[1].append(ModelGroup('choice'))
        group[0][0].append(ParticleMixin())
        group[0][0].append(ParticleMixin())
        group[1][0].append(ParticleMixin())
        group[1][0].append(ParticleMixin())

        path1 = [group, group[0], group[0][0], group[0][0][0]]
        path2 = [group, group[1], group[1][0], group[1][0][0]]
        self.assertTrue(distinguishable_paths(path1, path2))  # All univocal subgroups

        group[0][0][1].min_occurs = 0
        self.assertFalse(distinguishable_paths(path1, path2))  # All univocal subgroups


if __name__ == '__main__':
    import platform
    header_template = "Test xmlschema's XSD model groups with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    unittest.main()
