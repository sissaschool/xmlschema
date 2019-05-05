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
# Tests that are incompatible with XSD meta-schema validation or that are postponed
SKIPPED_TESTS = {
    # Signed as valid that have to be checked
    '../msData/additional/addB194.xsd',       # 4826: invalid xml:lang='enu'
    '../msData/particles/particlesZ001.xsd',  # 10957: Invalid in XSD 1.0
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

    # Invalid that may be valid
    '../sunData/combined/xsd003b/xsd003b.e.xsd',  # 3981: Redefinition that may be valid
    '../msData/additional/adhocAddC002.xsd',      # 4642: Lack of the processor on XML namespace knowledge
    '../msData/additional/test65026.xsd',         # 4712: Lack of the processor on XML namespace knowledge
    '../msData/annotations/annotF001.xsd',        # 4989: Annotation contains xml:lang="" ?? (but xml.xsd allows '')
    '../msData/datatypes/Facets/base64Binary/base64Binary_enumeration003.xsd',  # 7277: check base64 invalid values
    '../msData/datatypes/Facets/anyURI/anyURI_a001.xsd',  # 7292: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_a003.xsd',  # 7294: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_b004.xsd',  # 7310: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_b006.xsd',  # 7312: XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/element/elemZ026.xsd',  # 8541: This is good because the head element is abstract
    '../msData/element/elemZ031.xsd',  # 8557: Valid in Python that has arbitrary large integers
    '../msData/errata10/errC005.xsd',  # 8558: Typo: abstract attribute must be set to "true" to fail
    '../msData/group/groupH021.xsd',   # 8679: TODO: wrong in XSD 1.0, good in XSD 1.1
    '../msData/identityConstraint/idC019.xsd',  # 8936: TODO: is it an error?
    '../msData/identityConstraint/idI148.xsd',  # 9291: FIXME attribute::* in a selector (restrict XPath parser)
    '../msData/identityConstraint/idJ016.xsd',  # 9311: FIXME xpath="xpns: *" not allowed??
    '../msData/modelGroups/mgE006.xsd',         # 9712: Is valid (is mg007.xsd invalid for the same reason)

    # Invalid that are valid because depend by implementation choices
    '../msData/schema/schG6_a.xsd',     # 13639: Schema is valid because the ns import is done once, validation fails.
    '../msData/schema/schG11_a.xsd',    # 13544: Schema is valid because the ns import is done once, validation fails.
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


def create_w3c_test_group_case(filename, group_elem, group_number, xsd_version='1.0'):
    """
    Creates a test class for a W3C test group.

    :param filename: the filename of the testSet that owns the testGroup.
    :param group_elem: the Element instance of the test group.
    :param group_number: a positive integer to distinguish and order test groups.
    :param xsd_version: if '1.1' uses XSD 1.1 validator class, otherwise uses the XSD 1.0 validator.
    """
    name = group_elem.attrib['name']

    if xsd_version == '1.1':
        schema_class = xmlschema.validators.XMLSchema11
        if group_elem.get('version') == '1.0':
            raise ValueError("testGroup %r is not suited for XSD 1.1" % name)
    elif group_elem.get('version') == '1.1':
        pass  # raise ValueError("testGroup %r is not suited for XSD 1.0" % name)
    else:
        schema_class = xmlschema.XMLSchema

    schema_elem = group_elem.find('{%s}schemaTest' % TEST_SUITE_NAMESPACE)
    if schema_elem is not None:
        schema_document = schema_elem.find('{%s}schemaDocument' % TEST_SUITE_NAMESPACE)
        schema_path = schema_document.get('{%s}href' % XLINK_NAMESPACE)
        if schema_path in SKIPPED_TESTS:
            return

        schema_path = os.path.normpath(os.path.join(os.path.dirname(filename), schema_path))

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

    if expected == 'invalid':
        class TestGroupCase(unittest.TestCase):
            def test_invalid_schema(self):
                with self.assertRaises(XMLSchemaException, msg="Schema %r may be invalid" % schema_path) as _:
                    schema_class(schema_path, use_meta=False)

    elif expected == 'valid':
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
    else:
        return   # expected is None or 'indeterminate'

    TestGroupCase.__name__ = TestGroupCase.__qualname__ = str(
        'TestGroupCase{0:05}_{1}'.format(group_number, name.replace('-', '_'))
    )
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
