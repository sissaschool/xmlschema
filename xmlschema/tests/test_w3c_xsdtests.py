#!/usr/bin/env python
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
This module runs tests concerning the building of XSD schemas with the 'xmlschema' package.
"""
from __future__ import print_function, unicode_literals
import unittest
import os.path
import xml.etree.ElementTree as ElementTree
import xmlschema

TEST_SUITE_NAMESPACE = "http://www.w3.org/XML/2004/xml-schema-test-suite/"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
ADMITTED_VALIDITY = {'valid', 'invalid', 'indeterminate'}

####
# Tests that are incompatible with XSD meta-schema validation
SKIPPED_TESTS = {
    '../msData/additional/adhocAddC002.xsd',  # 'xml' namespace not implicit
    '../sunData/ElemDecl/name/name00505m/name00505m1.xsd',  # resolving keyref dilemma (ancestors or descendants)
    '../msData/additional/test72232_1.xsd',  # resolving keyref dilemma
    '../msData/additional/test72232_2.xsd',
    '../msData/additional/addB194.xsd',  # keyref and invalid xml:lang='enu'
    '../msData/errata10/errC004.xsd', # Extra attribute, must check this
    '../msData/identityConstraint/idI009.xsd', # FIXME xpath="child::imp:iid" in elementpath
    '../msData/identityConstraint/idI013.xsd', #
    # 9163 : wrong pattern
    # TestGroupCase11278_reG26: bad character range 'a'-'1' at position 2: 'a-c-1-4x-z-7-9'
    # TestGroupCase11278_reG26: bad character range 'a'-'1' at position 2: 'a-c-1-4x-z-7-9'
    # TestGroupCase11293_reG41: re.error: unterminated character set at position 2
    #
}

def fetch_xsd_test_suite():
    parent = os.path.dirname
    xmlschema_test_dir = parent(os.path.abspath(__file__))
    xmlschema_base_dir = parent(parent(xmlschema_test_dir))

    suite_file = os.path.join(parent(xmlschema_base_dir), 'xsdtests/suite.xml')
    if os.path.isfile(suite_file):
        return suite_file
    else:
        raise FileNotFoundError("can't find the XSD suite index file suite.xml ...")


def create_w3c_test_group_case(testset_file, testgroup_elem, testgroup_num, xsd_version='1.0'):
    """
    Creates a test class for a W3C test group.

    :param testset_file: the file path of the testSet that owns the testGroup.
    :param testgroup_elem: the Element instance of the test group.
    :param testgroup_num: a positive integer to distinguish and order test groups.
    :param xsd_version: if '1.1' uses XSD 1.1 validator class, otherwise uses the XSD 1.0 validator.
    """
    name = testgroup_elem.attrib['name']

    if xsd_version == '1.1':
        schema_class = xmlschema.validators.XMLSchema11
        if testgroup_elem.get('version') == '1.0':
            raise ValueError("testGroup %r is not suited for XSD 1.1" % name)
    elif testgroup_elem.get('version') == '1.1':
        pass # raise ValueError("testGroup %r is not suited for XSD 1.0" % name)
    else:
        schema_class = xmlschema.XMLSchema

    if name == 'addA006':
        pass
        # import pdb
        # pdb.set_trace()

    schema_elem = testgroup_elem.find('{%s}schemaTest' % TEST_SUITE_NAMESPACE)
    if schema_elem is not None:
        schema_document = schema_elem.find('{%s}schemaDocument' % TEST_SUITE_NAMESPACE)
        schema_path = schema_document.get('{%s}href' % XLINK_NAMESPACE)
        if schema_path in SKIPPED_TESTS:
            return

        schema_path = os.path.normpath(os.path.join(os.path.dirname(testset_file), schema_path))

        if not os.path.isfile(schema_path):
            raise ValueError("Schema file %r not found!" % schema_path)

        expected = None
        for elem in schema_elem.findall('{%s}expected' % TEST_SUITE_NAMESPACE):
            if 'version' not in elem.attrib:
                expected = elem.attrib['validity']
            elif elem.attrib['version'] in (xsd_version, 'full-xpath-in-CTA'):
                expected = elem.attrib['validity']
                break

        if expected is None:
            raise ValueError("Missing expected validity for XSD %s" % xsd_version)
        elif expected not in ADMITTED_VALIDITY:
            raise ValueError("wrong validity=%r attribute for %r" % (expected, elem))

    else:
        schema_path = expected = None

    if expected is not None and expected != 'valid':
        class TestGroupCase(unittest.TestCase):
            def test_invalid_schema(self):
                try:
                    self.assertRaises(
                        (xmlschema.XMLSchemaParseError, xmlschema.XMLSchemaValidationError, ValueError),
                        schema_class, schema_path, use_meta=False
                    )
                except AssertionError:
                    print(schema_path)
                    raise

    else:
        # return
        class TestGroupCase(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                try:
                    cls.schema = schema_class(schema_path, use_meta=False) if schema_path else None
                except TypeError:
                    cls.schema = None

            def test_valid_schema(self):
                if schema_path:
                    self.assertIsInstance(schema_class(schema_path, use_meta=False), schema_class)

    TestGroupCase.__name__ = TestGroupCase.__qualname__ = str(
        'TestGroupCase{0:05}_{1}'.format(testgroup_num, name.replace('-', '_'))
    )
    if testgroup_num >= 0: # 11289: # 9151: #8390: # 5607: # 4825:  # 4818:  #4746:  #4462: #4349:  #4225:
        return TestGroupCase

if __name__ == '__main__':
    index_path = fetch_xsd_test_suite()
    index_dir = os.path.dirname(index_path)

    suite_xml = ElementTree.parse(index_path)
    HREF_ATTRIBUTE = "{%s}href" % XLINK_NAMESPACE
    test_classes = {}
    testgroup_num = 1

    for testset_elem in suite_xml.iter("{%s}testSetRef" % TEST_SUITE_NAMESPACE):
        testset_file = os.path.join(index_dir, testset_elem.attrib.get(HREF_ATTRIBUTE, ''))
        # print("*** {} ***".format(testset_file))

        testset_xml = ElementTree.parse(testset_file)

        for testgroup_elem in testset_xml.iter("{%s}testGroup" % TEST_SUITE_NAMESPACE):
            if testgroup_elem.get('version') == '1.1':
                continue

            cls = create_w3c_test_group_case(testset_file, testgroup_elem, testgroup_num)
            if cls is not None:
                test_classes[cls.__name__] = cls
            testgroup_num += 1

    globals().update(test_classes)

    # print_test_header()
    unittest.main()
