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
This module runs tests concerning the W3C XML Schema 1.1 test suite.
"""
from __future__ import print_function, unicode_literals
import unittest
import os.path
import xml.etree.ElementTree as ElementTree

import xmlschema
from xmlschema import XMLSchemaException

TEST_SUITE_NAMESPACE = "http://www.w3.org/XML/2004/xml-schema-test-suite/"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
ADMITTED_VALIDITY = {'valid', 'invalid', 'indeterminate'}

####
# Tests that are incompatible with XSD meta-schema validation
SKIPPED_TESTS = {
    '../msData/additional/addB194.xsd',     # 4826: invalid xml:lang='enu'
    '../msData/simpleType/stE110.xsd',      # 13892: Circular xs:union declaration
    '../saxonData/Missing/missing001.xsd',  # 14405: missing type (this may be valid in 'lax' mode?)
    '../saxonData/Missing/missing002.xsd',  # 14406: missing substitution group
    '../saxonData/Missing/missing003.xsd',  # 14406: missing type and substitution group
    '../saxonData/Missing/missing006.xsd',  # 14410: missing list item type
    '../saxonData/VC/vc001.xsd',            # 14411: VC namespace required
    '../saxonData/VC/vc002.xsd',            # 14412: VC namespace required
    '../saxonData/VC/vc014.xsd',            # 14413: VC namespace required
    '../saxonData/VC/vc024.xsd',            # 14414: VC 1.1? required
    '../saxonData/XmlVersions/xv004.xsd',   # 14419: non-BMP chars allowed in names in XML 1.1+

    # Invalid that are valid
    '../sunData/combined/xsd003b/xsd003b.e.xsd',  # 3981: Redefinition that may be valid
    '../msData/additional/adhocAddC002.xsd',      # 4642: Lack of the processor on XML namespace knowledge
    '../msData/additional/test65026.xsd',         # 4712: Lack of the processor on XML namespace knowledge
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

    schema_elem = testgroup_elem.find('{%s}schemaTest' % TEST_SUITE_NAMESPACE)
    if schema_elem is not None:
        schema_document = schema_elem.find('{%s}schemaDocument' % TEST_SUITE_NAMESPACE)
        schema_path = schema_document.get('{%s}href' % XLINK_NAMESPACE)
        if schema_path in SKIPPED_TESTS:
            return

        schema_path = os.path.normpath(os.path.join(os.path.dirname(testset_file), schema_path))

        if not os.path.isfile(schema_path):
            raise ValueError("Schema file %r not found!" % schema_path)

        expected = elem = None
        for elem in schema_elem.findall('{%s}expected' % TEST_SUITE_NAMESPACE):
            if 'version' not in elem.attrib:
                expected = elem.attrib['validity']
            elif elem.attrib['version'] in (xsd_version, 'full-xpath-in-CTA'):
                expected = elem.attrib['validity']
                break

        if expected is None:
            raise ValueError("Missing expected validity for XSD %s" % xsd_version)
        elif expected not in ADMITTED_VALIDITY:
            raise ValueError("Wrong validity=%r attribute for %r" % (expected, elem))

    else:
        schema_path = expected = None

    if expected is not None and expected != 'valid':
        return
        class TestGroupCase(unittest.TestCase):
            def test_invalid_schema(self):
                with self.assertRaises(XMLSchemaException, msg="Schema %r may be invalid" % schema_path) as _:
                    schema_class(schema_path, use_meta=False)

    else:
        #return
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
    if testgroup_num >= 0: #4815:
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

        testset_xml = ElementTree.parse(testset_file)
        testset_version = testset_xml.getroot().get('version')
        if testset_version is not None and '1.0' not in testset_version:
            continue

        # print("*** {} ***".format(testset_file))

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
