#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests concerning model groups validation.
"""
import unittest
import os
import sys

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.validators import XsdModelVisitor
from xmlschema.tests import XMLSchemaTestCase


class TestModelValidation(XMLSchemaTestCase):

    def check_advance(self, model, match, expected=None):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), match)
        else:
            self.assertEqual([e for e in model.advance(match)], expected or [])

    def check_advance_true(self, model, expected=None):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), True)
        else:
            self.assertEqual([e for e in model.advance(True)], expected or [])

    def check_advance_false(self, model, expected=None):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda x: list(model.advance(x)), False)
        else:
            self.assertEqual([e for e in model.advance(False)], expected or [])

    def check_stop(self, model, expected=None):
        if isinstance(expected, type) and issubclass(expected, Exception):
            self.assertRaises(expected, lambda: list(model.stop()))
        else:
            self.assertEqual([e for e in model.stop()], expected or [])

    # --- Vehicles schema ---

    def test_vehicles_model(self):
        # Sequence with two not-emptiable single-occurs elements
        group = self.vh_schema.elements['vehicles'].type.content_type

        model = XsdModelVisitor(group)
        self.check_advance_true(model)                # <cars>
        self.check_advance_true(model)                # <bikes>
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_true(model)                # <cars>
        self.check_advance_true(model)                # <bikes>
        self.check_advance_true(model, ValueError)    # <bikes>
        self.assertIsNone(model.element)

    def test_cars_model(self):
        # Emptiable 1:1 sequence with one emptiable and unlimited element.
        group = self.vh_schema.elements['cars'].type.content_type

        model = XsdModelVisitor(group)
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_false(model)    # (end)
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_false(model)    # <not-a-car>
        self.assertIsNone(model.element)

    # --- Collection schema ---

    def test_collection_model(self):
        # Sequence with one not-emptiable and unlimited element.
        group = self.col_schema.elements['collection'].type.content_type

        model = XsdModelVisitor(group)
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_true(model)     # <car>
        self.check_advance_false(model)    # (end)
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_false(model, [(group[0], 0, [group[0]])])  # <not-a-car>
        self.assertIsNone(model.element)

    def test_person_type_model(self):
        # Sequence with four single elements, last two are also emptiable.
        group = self.col_schema.types['personType'].content_type

        model = XsdModelVisitor(group)
        self.check_advance_true(model)     # <name>
        self.check_advance_true(model)     # <born>
        self.check_advance_true(model)     # <dead>
        self.check_advance_true(model)     # <qualification>
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_true(model)     # <name>
        self.check_advance_true(model)     # <born>
        self.check_stop(model)
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_true(model)                                # <name> match
        self.check_advance_false(model, [(group[1], 0, [group[1]])])  # <born> missing!
        self.check_advance_true(model)                                # <dead> match
        self.check_stop(model)                                        # <qualification> is optional
        self.assertIsNone(model.element)

    # --- XSD 1.0 schema ---

    def test_simple_derivation_model(self):
        """
        <xs:group name="simpleDerivation">
          <xs:choice>
            <xs:element ref="xs:restriction"/>
            <xs:element ref="xs:list"/>
            <xs:element ref="xs:union"/>
          </xs:choice>
        </xs:group>
        """
        group = self.schema_class.meta_schema.groups['simpleDerivation']

        model = XsdModelVisitor(group)
        self.check_advance_true(model)     # <restriction> match
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_false(model)    # <list> not match with <restriction>
        self.check_advance_true(model)     # <list> match
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_false(model)    # <union> not match with <restriction>
        self.check_advance_false(model)    # <union> not match with <list>
        self.check_advance_true(model)     # <union> match
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        self.check_advance_false(model)                          # <other> not match with <restriction>
        self.check_advance_false(model)                          # <other> not match with <list>
        self.check_advance_false(model, [(group, 0, group[:])])  # <other> not match with <union>
        self.assertIsNone(model.element)

    def test_simple_restriction_model(self):
        """
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
        """
        # Sequence with an optional single element and an optional unlimited choice.
        group = self.schema_class.meta_schema.groups['simpleRestrictionModel']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_advance_true(model)      # <simpleType> match
        self.assertEqual(model.element, group[1][0][0])
        self.check_advance_false(model)     # <maxExclusive> do not match
        self.assertEqual(model.element, group[1][0][1])
        self.check_advance_false(model)     # <maxExclusive> do not match
        self.assertEqual(model.element, group[1][0][2])
        self.check_advance_true(model)      # <maxExclusive> match
        self.assertEqual(model.element, group[1][0][0])
        for _ in range(12):
            self.check_advance_false(model)  # no match for all the inner choice group "xs:facets"
        self.assertIsNone(model.element)

    def test_schema_model(self):
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

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> don't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_true(model)                  # <complexType> match
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> don't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_false(model)                 # <complexType> don't match
        self.assertEqual(model.element, group[0][0][2])
        self.check_advance_false(model)                 # <group> don't match
        self.assertEqual(model.element, group[0][0][3])
        self.check_advance_false(model)                 # <attributeGroup> don't match
        self.assertEqual(model.element, group[1])
        self.check_advance_false(model)                 # <element> don't match
        self.assertEqual(model.element, group[2])
        self.check_advance_false(model)                 # <attribute> don't match
        self.assertEqual(model.element, group[3])
        self.check_advance_false(model, [(group, 0, group[0][0][:]+group[1:])])  # <notation> don't match

        model.restart()
        self.assertEqual(model.element, group[0][0][0])
        self.check_advance_false(model)                 # <simpleType> don't match
        self.assertEqual(model.element, group[0][0][1])
        self.check_advance_false(model)                 # <complexType> don't match
        self.assertEqual(model.element, group[0][0][2])
        self.check_advance_false(model)                 # <group> don't match
        self.assertEqual(model.element, group[0][0][3])
        self.check_advance_false(model)                 # <attributeGroup> don't match
        self.assertEqual(model.element, group[1])
        self.check_advance_false(model)                 # <element> don't match
        self.assertEqual(model.element, group[2])
        self.check_advance_true(model)                  # <attribute> match
        self.assertIsNone(model.element)

    def test_attr_declaration(self):
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

        model = XsdModelVisitor(group)
        for match in [False, False, True]:
            self.check_advance(model, match)
        self.assertIsNone(model.element)

        model = XsdModelVisitor(group)
        for match in [False, True]:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[0][0])

        model = XsdModelVisitor(group)
        for match in [False, True, False, False]:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[1])

        model = XsdModelVisitor(group)
        for match in [False, True, True, False, True, False, False]:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[1])

    def test_complex_type_model(self):
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
        """
        group = self.schema_class.meta_schema.groups['complexTypeModel']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_advance_true(model)                  # <simpleContent> match
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0])
        for match in [False, True]:
            self.check_advance(model, match)            # <complexContent> match
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0])
        for match in [False, False, False, False, True]:
            self.check_advance(model, match)            # <all> match
        self.check_stop(model)
        self.assertIsNone(model.element)

        model.restart()
        self.assertEqual(model.element, group[0])
        for match in [False, False, False, False, True, False, True, False, False, False]:
            self.check_advance(model, match)            # <all> match, <attributeGroup> match
        self.assertIsNone(model.element)

    #
    # Tests on schema cases/features/models/models.xsd
    def test_model_group1(self):
        group = self.models_schema.groups['group1']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        self.check_stop(model)

        model.restart()
        self.assertEqual(model.element, group[0])
        for match in [False, False, False]:
            self.check_advance(model, match)
        self.assertIsNone(model.element)

        model.restart()
        for match in [False, True, False]:
            self.check_advance(model, match)
        self.assertIsNone(model.element)

    def test_model_group2(self):
        group = self.models_schema.groups['group2']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for match in [False, False, False]:
            self.check_advance(model, match)                # group1 do not match
        self.assertEqual(model.element, group[1][0][0][2])  # <elem3> of group1
        for match in [False] * 8:
            self.check_advance(model, match)
        self.assertEqual(model.element, group[2])           # <elem12>
        self.check_advance_false(model)
        self.assertEqual(model.element, group[3])           # <elem13>
        self.check_advance_false(model)
        self.assertIsNone(model.element)

    def test_model_group3(self):
        group = self.models_schema.groups['group3']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for match in [True, False, True]:
            self.check_advance(model, match)
        self.check_stop(model)

    def test_model_group4(self):
        group = self.models_schema.groups['group4']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0])
        for match in [True, False, True]:
            self.check_advance(model, match)
        self.check_stop(model)

    def test_model_group5(self):
        group = self.models_schema.groups['group5']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        for match in [True, True, True, True, True]:   # match [<elem1> .. <elem5>]
            self.check_advance(model, match)
        self.assertEqual(model.element.name, 'elem6')
        self.check_advance_true(model)                 # match choice with <elem6>
        self.check_stop(model)

    def test_model_group6(self):
        group = self.models_schema.groups['group6']

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_advance_true(model)                 # match choice with <elem1>
        self.check_advance_true(model)                 # match choice with <elem2>
        self.assertIsNone(model.element)

    def test_model_group7(self):
        group = self.models_schema.types['complexType7'].content_type

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_stop(model, [(group[0][0], 0, [group[0][0]])])

        group = self.models_schema.types['complexType7_emptiable'].content_type

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_stop(model)

    #
    # Tests on schemas
    def test_schema_document_model(self):
        group = self.schema_class.meta_schema.elements['schema'].type.content_type

        model = XsdModelVisitor(group)
        self.assertEqual(model.element, group[0][0])
        self.check_advance_false(model)                 # eg. anyAttribute


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    print_test_header()
    unittest.main()
