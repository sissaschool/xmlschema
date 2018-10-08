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
Tests subpackage imports and methods for unittest scripts of the 'xmlschema' package.
"""
import unittest
import re
import os
import sys
import glob
import fileinput
import argparse
import logging
from functools import wraps

import xmlschema
from xmlschema import XMLSchema, XMLSchema10
from xmlschema.validators import XMLSchema11
from xmlschema.compat import urlopen, URLError
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.etree import (
    is_etree_element, etree_element, etree_register_namespace, etree_elements_assert_equal
)
from xmlschema.resources import fetch_namespaces
from xmlschema.qnames import XSD_SCHEMA
from xmlschema.helpers import get_namespace
from xmlschema.namespaces import XSD_NAMESPACE

logger = logging.getLogger('xmlschema.tests')


def has_network_access(*locations):
    for url in locations:
        try:
            urlopen(url, timeout=5)
        except (URLError, OSError):
            pass
        else:
            return True
    return False


SKIP_REMOTE_TESTS = not has_network_access('http://www.sissa.it', 'http://www.w3.org/', 'http://dublincore.org/')

PROTECTED_PREFIX_PATTERN = re.compile("ns\d:")


def print_test_header():
    header = "Test %r" % xmlschema
    print("*" * len(header) + '\n' + header + '\n' + "*" * len(header))


def get_testfiles(test_dir):
    # Checks arguments and defines the testfiles lists to use
    if '-x' not in sys.argv and '--extra' not in sys.argv:
        testfiles = glob.glob(os.path.join(test_dir, 'cases/testfiles'))
    else:
        testfiles = glob.glob(os.path.join(test_dir, '*/testfiles'))
        try:
            sys.argv.remove('-x')
        except ValueError:
            sys.argv.remove('--extra')
    return testfiles


class SchemaObserver(object):
    components = []

    @classmethod
    def observe_builder(cls, builder):
        if isinstance(builder, type):
            class BuilderProxy(builder):
                def __init__(self, *args, **kwargs):
                    super(BuilderProxy, self).__init__(*args, **kwargs)
                    cls.components.append(self)
            BuilderProxy.__name__ = builder.__name__
            return BuilderProxy

        elif callable(builder):
            @wraps(builder)
            def builder_proxy(*args, **kwargs):
                result = builder(*args, **kwargs)
                cls.components.append(result)
                return result
            return builder_proxy

    @classmethod
    def clear(cls):
        del cls.components[:]


class ObservedXMLSchema10(XMLSchema10):
    BUILDERS = {
        k: SchemaObserver.observe_builder(getattr(XMLSchema10.BUILDERS, k))
        for k in getattr(XMLSchema10.BUILDERS, '_fields')
    }


def get_test_args(args_line):
    try:
        args_line, _ = args_line.split('#', 1)
    except ValueError:
        pass
    return re.split(r'(?<!\\) ', args_line.strip())


def xsd_version_number(value):
    if value not in ('1.0', '1.1'):
        msg = "%r is not an XSD version." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def defuse_data(value):
    if value not in ('always', 'remote', 'never'):
        msg = "%r is not a valid value." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def get_args_parser():
    parser = argparse.ArgumentParser(add_help=True)
    parser.usage = "TEST_FILE [OPTIONS]\nTry 'TEST_FILE --help' for more information."
    parser.add_argument('filename', metavar='TEST_FILE', type=str, help="Test filename (relative path).")
    parser.add_argument(
        '-L', dest='locations', nargs=2, type=str, default=None, action='append',
        metavar="URI-URL", help="Schema location hint overrides."
    )
    parser.add_argument(
        '--version', dest='version', metavar='VERSION', type=xsd_version_number, default='1.0',
        help="XSD schema version to use for the test case (default is 1.0)."
    )
    parser.add_argument(
        '--errors', type=int, default=0, metavar='NUM', help="Number of errors expected (default=0)."
    )
    parser.add_argument(
        '--warnings', type=int, default=0, metavar='NUM', help="Number of warnings expected (default=0)."
    )
    parser.add_argument(
        '--inspect', action="store_true", default=False, help="Inspect using an observed custom schema class."
    )
    parser.add_argument(
        '--defuse', metavar='(always, remote, never)', type=defuse_data, default='remote',
        help="Define when to use the defused XML data loaders."
    )
    parser.add_argument(
        '--timeout', type=int, default=300, metavar='SEC', help="Timeout for fetching resources (default=300)."
    )
    parser.add_argument(
        '--defaults', action="store_true", default=False,
        help="Test data uses default or fixed values (skip strict encoding checks).",
    )
    parser.add_argument(
        '--skip', action="store_true", default=False,
        help="Skip strict encoding checks (for cases where test data uses default or "
             "fixed values or some test data are skipped by wildcards processContents)."
    )
    parser.add_argument(
        '--debug', action="store_true", default=False,
        help="Activate the debug mode (only the cases with --debug are executed).",
    )
    return parser


test_line_parser = get_args_parser()


def tests_factory(test_class_builder, testfiles, suffix="xml"):
    test_classes = {}
    test_num = 0
    debug_mode = False
    line_buffer = []

    for line in fileinput.input(testfiles):
        line = line.strip()
        if not line or line[0] == '#':
            if not line_buffer:
                continue
            else:
                raise SyntaxError("Empty continuation at line %d!" % fileinput.filelineno())
        elif '#' in line:
            line = line.split('#', 1)[0].rstrip()

        # Process line continuations
        if line[-1] == '\\':
            line_buffer.append(line[:-1].strip())
            continue
        elif line_buffer:
            line_buffer.append(line)
            line = ' '.join(line_buffer)
            del line_buffer[:]

        test_args = test_line_parser.parse_args(get_test_args(line))
        if test_args.locations is not None:
            test_args.locations = {k.strip('\'"'): v for k, v in test_args.locations}

        test_file = os.path.join(os.path.dirname(fileinput.filename()), test_args.filename)
        if os.path.isdir(test_file):
            logger.debug("Skip %s: is a directory.", test_file)
            continue
        elif os.path.splitext(test_file)[1].lower() != '.%s' % suffix:
            logger.debug("Skip %s: wrong suffix.", test_file)
            continue
        elif not os.path.isfile(test_file):
            logger.error("Skip %s: is not a file.", test_file)
            continue

        test_num += 1

        # Debug mode activation
        if debug_mode:
            if not test_args.debug:
                continue
        elif test_args.debug:
            debug_mode = True
            logger.debug("Debug mode activated: discard previous %r test classes.", len(test_classes))
            test_classes.clear()

        if test_args.inspect:
            test_class = test_class_builder(test_file, test_args, test_num, ObservedXMLSchema10)
        else:
            test_class = test_class_builder(test_file, test_args, test_num)

        test_classes[test_class.__name__] = test_class
        logger.debug("Add XSD 1.0 test class %r.", test_class.__name__)

        # test_class = test_class_builder(test_file, test_args, test_num, XMLSchema11)
        # test_classes[test_class.__name__] = test_class
        # logger.debug("Add XSD 1.1 test class for %r.", test_class.__name__)

    if line_buffer:
        raise ValueError("Not completed line continuation at the end!")

    return test_classes


class XMLSchemaTestCase(unittest.TestCase):
    """
    XMLSchema TestCase class.

    Setup tests common environment. The tests parts have to use empty prefix for
    XSD namespace names and 'ns' prefix for XMLSchema test namespace names.
    """

    test_dir = os.path.dirname(__file__)
    etree_register_namespace(prefix='', uri=XSD_NAMESPACE)
    etree_register_namespace(prefix='ns', uri="ns")
    SCHEMA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
    <schema xmlns:ns="ns" xmlns="http://www.w3.org/2001/XMLSchema" 
        targetNamespace="ns" elementFormDefault="unqualified" version="{0}">
        {1}
    </schema>"""

    schema_class = XMLSchema

    @classmethod
    def setUpClass(cls):
        cls.xsd_types = cls.schema_class.builtin_types()
        cls.content_pattern = re.compile(r'(xs:sequence|xs:choice|xs:all)')

        cls.default_namespaces = {'ns': 'ns', 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}

        cls.vh_dir = cls.abspath('cases/examples/vehicles')
        cls.vh_xsd_file = cls.abspath('cases/examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = cls.abspath('cases/examples/vehicles/vehicles.xml')
        cls.vh_json_file = cls.abspath('cases/examples/vehicles/vehicles.json')
        cls.vh_schema = cls.schema_class(cls.vh_xsd_file)
        cls.vh_namespaces = fetch_namespaces(cls.vh_xml_file)

        cls.col_dir = cls.abspath('cases/examples/collection')
        cls.col_xsd_file = cls.abspath('cases/examples/collection/collection.xsd')
        cls.col_xml_file = cls.abspath('cases/examples/collection/collection.xml')
        cls.col_json_file = cls.abspath('cases/examples/collection/collection.json')
        cls.col_schema = cls.schema_class(cls.col_xsd_file)
        cls.col_namespaces = fetch_namespaces(cls.col_xml_file)

        cls.st_xsd_file = cls.abspath('cases/features/decoder/simple-types.xsd')
        cls.st_schema = cls.schema_class(cls.st_xsd_file)

        cls.models_xsd_file = cls.abspath('cases/features/models/models.xsd')
        cls.models_schema = cls.schema_class(cls.models_xsd_file)

    @classmethod
    def abspath(cls, path):
        return os.path.join(cls.test_dir, path)

    def retrieve_schema_source(self, source):
        """
        Returns a schema source that can be used to create an XMLSchema instance.

        :param source: A string or an ElementTree's Element.
        :return: An schema source string, an ElementTree's Element or a full pathname.
        """
        if is_etree_element(source):
            if source.tag in (XSD_SCHEMA, 'schema'):
                return source
            elif get_namespace(source.tag):
                raise XMLSchemaValueError("source %r namespace has to be empty." % source)
            elif source.tag not in {'element', 'attribute', 'simpleType', 'complexType',
                                    'group', 'attributeGroup', 'notation'}:
                raise XMLSchemaValueError("% is not an XSD global definition/declaration." % source)

            root = etree_element('schema', attrib={
                'xmlns:ns': "ns",
                'xmlns': "http://www.w3.org/2001/XMLSchema",
                'targetNamespace':  "ns",
                'elementFormDefault': "qualified",
                'version': self.schema_class.XSD_VERSION,
            })
            root.append(source)
            return root
        else:
            source = source.strip()
            if not source.startswith('<'):
                return os.path.join(self.test_dir, source)
            else:
                return self.SCHEMA_TEMPLATE.format(self.schema_class.XSD_VERSION, source)

    def get_schema(self, source):
        return self.schema_class(self.retrieve_schema_source(source))

    def get_element(self, name, **attrib):
        source = '<element name="{}" {}/>'.format(
            name, ' '.join('%s="%s"' % (k, v) for k, v in attrib.items())
        )
        schema = self.schema_class(self.retrieve_schema_source(source))
        return schema.elements[name]

    def check_etree_elements(self, elem, other):
        """Checks if two ElementTree elements are equal."""
        try:
            self.assertIsNone(etree_elements_assert_equal(elem, other, strict=False, skip_comments=True))
        except AssertionError as err:
            self.assertIsNone(err, None)

    def check_namespace_prefixes(self, s):
        """Checks that a string doesn't contain protected prefixes (ns0, ns1 ...)."""
        match = PROTECTED_PREFIX_PATTERN.search(s)
        if match:
            msg = "Protected prefix {!r} found:\n {}".format(match.group(0), s)
            self.assertIsNone(match, msg)
