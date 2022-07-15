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
"""
This script runs tests concerning the W3C XML Schema 1.1 test suite.
"""
import unittest
import argparse
import os.path
import warnings
from xml.etree import ElementTree

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from xmlschema import validate, XMLSchema10, XMLSchema11, XMLSchemaException

TEST_SUITE_NAMESPACE = "http://www.w3.org/XML/2004/xml-schema-test-suite/"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XSD_VERSION_VALUES = {'1.0 1.1', '1.0', '1.1'}
ADMITTED_VALIDITY = {'valid', 'invalid', 'indeterminate'}

####
# Tests that are incompatible with XSD meta-schema validation or that are postponed
SKIPPED_TESTS = {
    ##
    # Skip for typos in test data
    '../msData/regex/reZ003v.xml',                          # 13589
    '../ibmData/instance_invalid/S3_10_6/s3_10_6ii01.xsd',  # 14911
    '../ibmData/instance_invalid/S3_10_6/s3_10_6ii02.xsd',  # 14912
    '../ibmData/instance_invalid/S3_10_6/s3_10_6ii04.xsd',  # 14914
    '../ibmData/instance_invalid/S3_10_1/s3_10_1ii08.xsd',  # 15360
    '../ibmData/instance_invalid/S3_10_1/s3_10_1ii09.xsd',  # 15361

    ##
    # Invalid schemas marked as valid
    '../msData/additional/addB194.xsd',         # invalid xml:lang='enu' is a typo?
    '../msData/particles/particlesZ001.xsd',    # Invalid XSD 1.0 schema (valid with XSD 1.1)
    '../msData/simpleType/stE110.xsd',          # Circular xs:union declaration
    '../saxonData/Missing/missing001.xsd',      # missing type (this may be valid in 'lax' mode?)
    '../saxonData/Missing/missing002.xsd',      # missing substitution group
    '../saxonData/Missing/missing003.xsd',      # missing type and substitution group
    '../saxonData/Missing/missing006.xsd',      # missing list item type
    '../msData/annotations/annotF001.xsd',      # xml.xsd allows xml:lang="" for un-declarations

    ##
    # XSD 1.0 limited URI (see RFC 2396 + RFC 2732)
    '../msData/datatypes/Facets/anyURI/anyURI_a001.xsd',
    '../msData/datatypes/Facets/anyURI/anyURI_a003.xsd',
    '../msData/datatypes/Facets/anyURI/anyURI_b004.xsd',
    '../msData/datatypes/Facets/anyURI/anyURI_b006.xsd',

    ##
    # Uncertain cases (disputed tests)
    '../msData/group/groupH021.xsd',  # 8679: Unclear invalidity stated for XSD 1.0 ...
    #
    # Two uncertain equivalent cases related with element
    # substitution and its equivalence with a choice group.
    # Xerces says these are both invalid with XSD 1.0 and valid with XSD 1.1.
    #
    # http://www.w3.org/Bugs/Public/show_bug.cgi?id=4146
    # http://www.w3.org/Bugs/Public/show_bug.cgi?id=4147
    #
    '../msData/element/elemZ026.xsd',         # 8541: bug id=4147
    '../msData/particles/particlesV020.xsd',  # 10942: bug id=4147

    ##
    # 7295: Inapplicable test on URI (the first resource is not reachable anymore)
    # https://www.w3.org/Bugs/Public/show_bug.cgi?id=4126
    '../msData/datatypes/Facets/anyURI/anyURI_a004.xml',

    ##
    # Signed ad invalid, but valid because depends by implementation choices or platform.
    #   https://www.w3.org/Bugs/Public/show_bug.cgi?id=4133
    '../msData/schema/schG3.xml',
    '../msData/schema/schG6_a.xsd',  # Valid because the ns import is done once, validation fails.
    '../msData/schema/schG11_a.xsd',  # Valid because the ns import is done once, validation fails.
    '../msData/schema/schG12.xml',
    '../msData/element/elemZ031.xsd',  # Valid because Python has arbitrary large integers

    ##
    # Invalid XML tests
    '../sunData/combined/xsd005/xsd005.n05.xml',
    # 3984: Invalid if lxml is used (xsi:type and duplicate prefix)
    '../msData/additional/test93490_4.xml',
    # 4795: https://www.w3.org/Bugs/Public/show_bug.cgi?id=4078
    '../msData/additional/test93490_8.xml',  # 4799: Idem
    '../msData/datatypes/gMonth002.xml',
    # 8017: gMonth bogus: conflicts with other invalid schema tests
    '../msData/datatypes/gMonth004.xml',
    # 8019: (http://www.w3.org/Bugs/Public/show_bug.cgi?id=6901)
    '../wgData/sg/e1.xml',
    # 14896: wrong href for valid instanceTest name="e1bis.xml"

    ##
    # Unicode version related
    '../msData/regex/reJ11.xml',
    '../msData/regex/reJ13.xml',
    '../msData/regex/reJ19.xml',
    '../msData/regex/reJ21.xml',
    '../msData/regex/reJ23.xml',
    '../msData/regex/reJ25.xml',
    '../msData/regex/reJ29.xml',
    '../msData/regex/reJ31.xml',
    '../msData/regex/reJ33.xml',
    '../msData/regex/reJ35.xml',
    '../msData/regex/reJ61.xml',
    '../msData/regex/reJ69.xml',
    '../msData/regex/reJ75.xml',
    '../msData/regex/reJ77.xml',
    '../msData/regex/reL98.xml',
    '../msData/regex/reL99.xml',
    '../msData/regex/reM98.xml',
    '../msData/regex/reN99.xml',
    '../msData/regex/reS21.xml',
    '../msData/regex/reS42.xml',
    '../msData/regex/reT63.xml',
    '../msData/regex/reT84.xml',
    # http://www.w3.org/Bugs/Public/show_bug.cgi?id=4113

    '../msData/regex/reV16.xml',
    '../msData/regex/reV17.xml',
    '../msData/regex/reV18.xml',
    '../msData/regex/reV19.xml',
    '../msData/regex/reV20.xml',
    '../msData/regex/reV21.xml',
    '../msData/regex/reV22.xml',
    '../msData/regex/reV23.xml',
    '../msData/regex/reV24.xml',
    '../msData/regex/reV33.xml',
    '../msData/regex/reV34.xml',
    '../msData/regex/reV35.xml',
    '../msData/regex/reV36.xml',
    '../msData/regex/reV37.xml',
    '../msData/regex/reV38.xml',
    '../msData/regex/reV39.xml',
    '../msData/regex/reV40.xml',
    '../msData/regex/reV41.xml',
    '../msData/regex/reV42.xml',
    '../msData/regex/reV43.xml',
    # Tests with \W pattern and characters belonging to the M category

    ##
    # Skip for missing XML version 1.1 implementation
    '../saxonData/XmlVersions/xv001.v01.xml',  # 14850
    '../saxonData/XmlVersions/xv003.v01.xml',  # 14852
    '../saxonData/XmlVersions/xv004.xsd',      # 14853 non-BMP chars allowed in names in XML 1.1+
    '../saxonData/XmlVersions/xv005.v01.xml',  # 14854
    '../saxonData/XmlVersions/xv006.v01.xml',  # 14855 invalid character &#x07 (valid in XML 1.1)
    '../saxonData/XmlVersions/xv006.n02.xml',  # 14855 invalid character &#x10000 (valid in XML 1.1)
    '../saxonData/XmlVersions/xv007.v01.xml',  # 14856
    '../saxonData/XmlVersions/xv008.v01.xml',  # 14857
    '../saxonData/XmlVersions/xv008.n01.xml',
    '../saxonData/XmlVersions/xv009.v02.xml',  # 14858
    '../saxonData/XmlVersions/xv009.n02.xml',
    '../saxonData/XmlVersions/xv009.n03.xml',
    '../saxonData/XmlVersions/xv100.i.xml',    # 14859
    '../saxonData/XmlVersions/xv100.c.xml',    # 14860

    ##
    # Skip for TODO
    '../msData/additional/test93490_2.xml',  # 4793
    '../msData/additional/test93490_5.xml',  # 4796
    '../msData/additional/test93490_7.xml',  # 4798
    '../msData/additional/test93490_10.xml',  # 4801
    '../msData/additional/test93490_12.xml',  # 4803
    '../msData/additional/addB191.xml',       # 4824
    # Dynamic schema load cases
}

XSD10_SKIPPED_TESTS = {
    # Invalid schemas marked as valid
    '../msData/simpleType/stE072.xsd',  # 13868: a union derived from ID with a fixed value
    '../msData/simpleType/stE072.xml',
}

XSD11_SKIPPED_TESTS = {
    # Valid schemas marked ad invalid
    '../msData/regex/reK86.xsd',                # \P{Is} is valid in regex for XSD 1.1
    '../msData/regex/reK87.xsd',                # \P{Is} is valid in regex for XSD 1.1
    '../msData/particles/particlesZ033_g.xsd',  # valid in XSD 1.1 (invalid for engine limitation)
    '../saxonData/CTA/cta0043.xsd',  # Only a warning for type table difference on restriction

    # TODO: Parse ENTITY declarations in DOCTYPE before enforce checking
    '../saxonData/Id/id017.n01.xml',     # 14571-14575
    '../saxonData/Id/id018.n01.xml',
    '../saxonData/Id/id018.n02.xml',
    '../saxonData/Id/id019.n01.xml',
    '../saxonData/Id/id019.n02.xml',
    '../saxonData/Id/id020.n01.xml',
    '../saxonData/Id/id020.n02.xml',
    '../saxonData/Id/id021.n01.xml',
    '../saxonData/Id/id021.n02.xml',
}

DO_NOT_USE_META_SCHEMA = {
    '../msData/additional/test264908_1.xsd',
}

DO_NOT_USE_FALLBACK_LOCATIONS = {
    '../msData/wildcards/wildZ001.xml',
}

# Total files counters
total_xsd_files = 0
total_xml_files = 0


def fetch_xsd_test_suite():
    parent = os.path.dirname
    xmlschema_test_dir = parent(os.path.abspath(__file__))
    xmlschema_base_dir = parent(xmlschema_test_dir)

    suite_file = os.path.join(parent(xmlschema_base_dir), 'xsdtests/suite.xml')
    if os.path.isfile(suite_file):
        return suite_file
    else:
        raise FileNotFoundError("can't find the XSD suite index file suite.xml ...")


def skip_message(source_href, group_num, version='each'):
    if source_href.endswith('.xsd'):
        msg = "Skip test number {} with schema {!r} for {} version ..."
    else:
        msg = "Skip test number {} with file {!r} for {} version ..."
    print(msg.format(group_num, source_href, version))


def create_w3c_test_group_case(args, filename, group_elem, group_num, xsd_version='1.0'):
    """
    Creates a test class for a W3C test group.

    :param args: parsed command line arguments.
    :type args: argparse.Namespace.
    :param filename: the filename of the testSet that owns the testGroup.
    :param group_elem: the Element instance of the test group.
    :param group_num: a positive integer to distinguish and order test groups.
    :param xsd_version: if '1.1' uses XSD 1.1 validator class, otherwise uses the XSD 1.0 validator.
    """
    def get_test_conf(elem):
        schema_test = elem.tag.endswith('schemaTest')
        if schema_test:
            tag = '{%s}schemaDocument' % TEST_SUITE_NAMESPACE
        else:
            tag = '{%s}instanceDocument' % TEST_SUITE_NAMESPACE

        try:
            source_href = elem.find(tag).get('{%s}href' % XLINK_NAMESPACE)
        except AttributeError:
            return
        else:
            if not schema_test and source_href.endswith('.testSet'):
                return
            if source_href in SKIPPED_TESTS:
                if args.numbers:
                    skip_message(source_href, group_num)
                return

        # Normalize and check file path
        source_path = os.path.normpath(os.path.join(os.path.dirname(filename), source_href))
        if not os.path.isfile(source_path):
            print("ERROR: file %r not found!" % source_path)
            return

        test_conf = {}

        for version in xsd_version.split():
            if 'version' in elem.attrib and version not in elem.attrib['version']:
                continue
            elif version not in args.version:
                continue
            elif source_href in XSD10_SKIPPED_TESTS and version == '1.0' or \
                    source_href in XSD11_SKIPPED_TESTS and version == '1.1':
                if args.numbers:
                    skip_message(source_href, group_num, version)
                continue

            for e in elem.findall('{%s}expected' % TEST_SUITE_NAMESPACE):
                if 'version' not in e.attrib:
                    test_conf[version] = e.attrib['validity']
                elif e.attrib['version'] == version or \
                        e.attrib['version'] == 'full-xpath-in-CTA':
                    test_conf[version] = e.attrib['validity']
                    break

            if version not in test_conf:
                msg = "ERROR: Missing expected validity for XSD version %s in %r of test group %r"
                print(msg % (version, elem, name))
                return
            elif test_conf[version] not in ADMITTED_VALIDITY:
                msg = "ERROR: Wrong validity=%r attribute for XSD version %s in %r test group %r"
                print(msg % (test_conf[version], version, elem, name))
                return
            elif test_conf[version] not in args.expected:
                test_conf.pop(version)
            elif test_conf[version] == 'indeterminate':
                if args.verbose:
                    print("WARNING: Skip indeterminate test group %r" % name)
                test_conf.pop(version)

        if test_conf:
            test_conf['source'] = source_path
            if schema_test:
                if not source_path.endswith('.xml'):
                    test_conf['sources'] = [
                        os.path.normpath(
                            os.path.join(os.path.dirname(filename),
                                         schema_href.get('{%s}href' % XLINK_NAMESPACE))
                        )
                        for schema_href in elem.findall(tag)
                    ]

            if source_href in DO_NOT_USE_META_SCHEMA:
                nonlocal use_meta
                use_meta = False

            if source_href in DO_NOT_USE_FALLBACK_LOCATIONS:
                nonlocal use_fallback
                use_fallback = False

        return test_conf

    if group_num == 1:
        return  # Skip introspection tests that have several failures due to schema mismatch.
    elif args.numbers and group_num not in args.numbers:
        return

    name = group_elem.attrib['name']
    group_tests = []
    global total_xsd_files
    global total_xml_files
    use_meta = True
    use_fallback = True

    # Get schema/instance path
    for k, child in enumerate(group_elem.iterfind('{%s}schemaTest' % TEST_SUITE_NAMESPACE)):
        if k:
            print("ERROR: multiple schemaTest definition in group %r" % name)
            return
        config = get_test_conf(child)
        if not config:
            return
        group_tests.append(config)
        total_xsd_files += 1

    if args.xml:
        for child in group_elem.iterfind('{%s}instanceTest' % TEST_SUITE_NAMESPACE):
            if 'version' in child.attrib and child.attrib['version'] not in args.version:
                continue
            config = get_test_conf(child)
            if config:
                group_tests.append(config)
                total_xml_files += 1

    if not group_tests:
        if len(args.expected) > 1 and args.xml:
            print("ERROR: Missing both schemaTest and instanceTest in test group %r" % name)
        return

    class TestGroupCase(unittest.TestCase):
        @unittest.skipIf(group_tests[0]['source'].endswith('.xml'), 'No schema test')
        def test_xsd_schema(self):
            for item in filter(lambda x: x['source'].endswith('.xsd'), group_tests):
                source = item['source']
                rel_path = os.path.relpath(source)

                for version, expected in \
                        sorted(filter(lambda x: not x[0].startswith('source'), item.items())):

                    if args.lxml and version == '1.0':
                        if expected == 'invalid':
                            with self.assertRaises(lxml_etree.XMLSchemaParseError):
                                schema_tree = lxml_etree.parse(source)
                                lxml_etree.XMLSchema(schema_tree)
                        else:
                            schema_tree = lxml_etree.parse(source)
                            lxml_etree.XMLSchema(schema_tree)
                        continue

                    schema_class = XMLSchema11 if version == '1.1' else XMLSchema10
                    if expected == 'invalid':
                        message = "schema %s should be invalid with XSD %s" % (rel_path, version)
                        with self.assertRaises(XMLSchemaException, msg=message):
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                if len(item['sources']) <= 1:
                                    schema_class(source, use_meta=use_meta,
                                                 use_fallback=use_fallback)
                                else:
                                    schema = schema_class(source, use_meta=use_meta,
                                                          use_fallback=use_fallback, build=False)
                                    for other in item['sources'][1:]:
                                        schema_class(other, global_maps=schema.maps,
                                                     use_fallback=use_fallback, build=False)
                                    schema.build()
                    else:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                if len(item['sources']) <= 1:
                                    schema = schema_class(source, use_meta=use_meta,
                                                          use_fallback=use_fallback)
                                else:
                                    schema = schema_class(source, use_meta=use_meta,
                                                          use_fallback=use_fallback, build=False)
                                    for other in item['sources'][1:]:
                                        schema_class(other, global_maps=schema.maps,
                                                     use_fallback=use_fallback, build=False)
                                    schema.build()
                        except XMLSchemaException as err:
                            schema = None
                            message = "schema %s should be valid with XSD %s, but an error " \
                                      "is raised:\n\n%s" % (rel_path, version, str(err))
                        else:
                            message = None

                        self.assertIsInstance(schema, schema_class, msg=message)

        @unittest.skipIf(
            group_tests[0]['source'].endswith('.xsd') and len(group_tests) == 1, 'No instance tests'
        )
        def test_xml_instances(self):
            if group_tests[0]['source'].endswith('.xsd'):
                schema = group_tests[0]['source']
                schemas = group_tests[0]['sources']
            else:
                schema = None
                schemas = []

            for item in filter(lambda x: not x['source'].endswith('.xsd'), group_tests):
                source = item['source']
                rel_path = os.path.relpath(source)

                for version, expected in sorted(filter(lambda x: x[0] != 'source', item.items())):
                    schema_class = XMLSchema11 if version == '1.1' else XMLSchema10
                    if expected == 'invalid':
                        message = "instance %s should be invalid with XSD %s" % (rel_path, version)
                        with self.assertRaises((XMLSchemaException, ElementTree.ParseError),
                                               msg=message):
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                if not schemas:
                                    validate(source, schema=schema, cls=schema_class)
                                else:
                                    xs = schema_class(schemas[0], use_meta=use_meta,
                                                      use_fallback=use_fallback, build=False)
                                    for other in schemas[1:]:
                                        schema_class(other, global_maps=xs.maps,
                                                     use_fallback=use_fallback, build=False)
                                    xs.build()
                                    xs.validate(source)
                    else:
                        try:
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore')
                                if len(schemas) <= 1 and use_meta and use_fallback:
                                    validate(source, schema=schema, cls=schema_class)
                                else:
                                    xs = schema_class(schemas[0], use_meta=use_meta,
                                                      use_fallback=use_fallback, build=False)
                                    for other in schemas[1:]:
                                        schema_class(other, global_maps=xs.maps, build=False)
                                    xs.build()
                                    xs.validate(source)

                        except (XMLSchemaException, ElementTree.ParseError) as err:
                            error = "instance %s should be valid with XSD %s, but an error " \
                                    "is raised:\n\n%s" % (rel_path, version, str(err))
                        else:
                            error = None
                        self.assertIsNone(error)

    if not any(g['source'].endswith('.xsd') for g in group_tests):
        del TestGroupCase.test_xsd_schema
    if not any(g['source'].endswith('.xml') for g in group_tests):
        del TestGroupCase.test_xml_instances

    TestGroupCase.__name__ = TestGroupCase.__qualname__ = str(
        'TestGroupCase{0:05}_{1}'.format(group_num, name.replace('-', '_'))
    )
    return TestGroupCase


def w3c_tests_factory(argv=None):
    import sys

    if argv is None:
        argv = sys.argv[1:]

    def xsd_versions(value):
        if value not in ('1.0', '1.1', '1.0 1.1', '1.1 1.0'):
            raise argparse.ArgumentTypeError("%r is not an XSD version string" % value)
        return value

    def number_or_interval(value):
        try:
            return int(value)
        except ValueError:
            if '-' not in value:
                raise
            try:
                start, stop = value.split('-')
                return [int(start), int(stop)]
            except ValueError:
                pass
            raise

    def iter_numbers(numbers):
        for x in numbers:
            if isinstance(x, int):
                yield x
            elif isinstance(x, list) and len(x) == 2:
                yield from range(x[0], x[1] + 1)

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('-v', '--verbose', default=False, action='store_true')
    parser.add_argument('--version', dest='version', type=xsd_versions,
                        default='1.0 1.1',
                        help="Run only tests related to a specific XSD version.")
    parser.add_argument('--xml', default=False, action='store_true',
                        help="Include XML validation tests.")
    parser.add_argument('--lxml', default=False, action='store_true',
                        help="Use lxml's XMLSchema validator for XSD 1.0 tests.")
    parser.add_argument('--valid', dest='expected', default=ADMITTED_VALIDITY,
                        const='valid', action='store_const',
                        help="Run only expected 'valid' tests.")
    parser.add_argument('--invalid', dest='expected',
                        const='invalid', action='store_const',
                        help="Run only expected 'invalid' tests.")
    parser.add_argument('--unknown', dest='expected',
                        const='indeterminate', action='store_const',
                        help="Run only expected 'indeterminate' tests.")
    parser.add_argument('numbers', metavar='TEST_NUMBER', type=number_or_interval, nargs='*',
                        help='Runs only specific tests, selected by numbers.')
    args = parser.parse_args(args=argv)

    args.numbers = [x for x in iter_numbers(args.numbers)]

    if lxml_etree is None and args.lxml:
        print("Ignore --lxml option: library lxml is not available ...")
        args.lxml = False

    quiet = __name__ == '__main__'
    index_path = fetch_xsd_test_suite()
    index_dir = os.path.dirname(index_path)

    suite_xml = ElementTree.parse(index_path)
    test_classes = {}
    testgroup_num = 0

    if args.verbose and not quiet:
        print("\n>>>>> ADD TEST GROUPS FROM TESTSET FILES <<<<<\n")

    for testset_elem in suite_xml.iter("{%s}testSetRef" % TEST_SUITE_NAMESPACE):
        href_attr = testset_elem.attrib.get("{%s}href" % XLINK_NAMESPACE, '')
        testset_file = os.path.join(index_dir, href_attr)
        testset_groups = 0

        testset = ElementTree.parse(testset_file)
        testset_version = testset.getroot().get('version', '1.0 1.1')
        if testset_version not in XSD_VERSION_VALUES:
            if not quiet:
                msg = "Testset file %r has an invalid version=%r, skip ..."
                print(msg % (href_attr, testset_version))
            continue

        for testgroup_elem in testset.iter("{%s}testGroup" % TEST_SUITE_NAMESPACE):
            testgroup_num += 1

            testgroup_version = testgroup_elem.get('version', testset_version)
            if testgroup_version == 'full-xpath-in-CTA':
                # skip full XPath test for the moment ...
                if args.verbose and not quiet:
                    print("Skip full XPath test %r ..." % testgroup_elem.get('name'))
                continue
            elif testgroup_version not in XSD_VERSION_VALUES:
                if not quiet:
                    _msg = "Test group %r has an invalid version=%r, skip ..."
                    print(_msg % (testgroup_elem.get('name'), testgroup_version))
                continue
            elif testgroup_version not in testset_version:
                if args.verbose and not quiet:
                    _msg = "Warning: Test group %r version=%r is not included " \
                           "in test set version=%r"
                    print(_msg % (testgroup_elem.get('name'), testgroup_version, testset_version))

            cls = create_w3c_test_group_case(
                args=args,
                filename=testset_file,
                group_elem=testgroup_elem,
                group_num=testgroup_num,
                xsd_version=testgroup_version,
            )
            if cls is not None:
                test_classes[cls.__name__] = cls
                testset_groups += 1

        if args.verbose and testset_groups and not quiet:
            print("Added {} test groups from {}".format(testset_groups, href_attr))

    if test_classes and not quiet:
        print("\n+++ Number of classes under test: %d +++" % len(test_classes))
        if total_xml_files:
            print("+++ Number of XSD schemas under test: %d +++" % total_xsd_files)
            print("+++ Number of XML files under test: %d +++" % total_xml_files)
        print()

    if args.verbose and not quiet:
        print("\n>>>>> RUN TEST GROUPS <<<<<\n")

    return test_classes


if __name__ == '__main__':
    import platform
    header_template = "W3C XSD tests for xmlschema with Python {} on {}"
    header = header_template.format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{0}'.format("*" * len(header), header))

    globals().update(w3c_tests_factory())
    unittest.main(argv=[__name__])
