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
import xmlschema.validators
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.etree import etree_iselement, etree_element, etree_register_namespace
from xmlschema.qnames import XSD_SCHEMA_TAG, get_namespace
from xmlschema.namespaces import XSD_NAMESPACE

logger = logging.getLogger('xmlschema.tests')


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


class ObservedXMLSchema10(xmlschema.XMLSchema10):
    BUILDERS = {
        k: SchemaObserver.observe_builder(v)
        for k, v in xmlschema.validators.schema.DEFAULT_BUILDERS.items()
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.usage = """TEST_FILE [TOT_ERRORS] [-i] [-v=VERSION]"""
    parser.add_argument('filename', metavar='TEST_FILE', type=str, help="Test filename (relative path).")
    parser.add_argument('tot_errors', nargs='?', type=int, default=0, help="Total errors expected (default=0).")
    parser.add_argument(
        '-i', dest="inspect", action="store_true", default=False,
        help="inspect using an observed custom schema class."
    )
    parser.add_argument(
        "-v", dest="version", metavar='VERSION', type=xsd_version_number, default='1.0',
        help="XSD version to use for schema (default is 1.0)."
    )
    parser.add_argument(
        '-l', dest='locations', nargs=2, type=str, default=None, action='append'
    )
    parser.add_argument(
        '-d', dest='defuse', metavar='(always, remote, never)', type=defuse_data, default='remote',
        help="Define when to use the defused XML data loaders."
    )
    return parser


test_line_parser = get_args_parser()


def tests_factory(test_function_builder, testfiles, label="validation", suffix="xml"):
    tests = {}
    test_num = 0

    for line in fileinput.input(testfiles):
        line = line.strip()
        if not line or line[0] == '#':
            continue

        test_args = test_line_parser.parse_args(get_test_args(line))
        if test_args.locations is not None:
            test_args.locations = {k.strip('\'"'): v for k, v in test_args.locations}

        test_file = os.path.join(os.path.dirname(fileinput.filename()), test_args.filename)
        if not os.path.isfile(test_file) or os.path.splitext(test_file)[1].lower() != '.%s' % suffix:
            continue

        if test_args.inspect:
            schema_class = ObservedXMLSchema10
        else:
            schema_class = xmlschema.XMLSchema

        test_func = test_function_builder(
            test_file, schema_class, test_args.tot_errors, test_args.inspect, test_args.locations, test_args.defuse
        )
        test_name = os.path.relpath(test_file)
        test_num += 1
        if test_func is not None:
            class_name = 'Test{0}{1:03}'.format(label.title(), test_num)
            tests[class_name] = type(
                class_name, (unittest.TestCase,),
                {'test_{0}_{1:03}_{2}'.format(label, test_num, test_name): test_func}
            )
            logger.debug("Add %s test case %r.", label, class_name)
        else:
            logger.debug("Skip %s test case %d (%r).", label, test_num, test_num, test_name)
    return tests


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

    @classmethod
    def setUpClass(cls):
        cls.namespaces = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'vh': 'http://example.com/vehicles',
            'col': 'http://example.com/ns/collection',
            'ns': 'ns',
        }

        cls.schema_class = xmlschema.XMLSchema
        cls.xsd_types = xmlschema.XMLSchema.builtin_types()
        cls.content_pattern = re.compile(r'(xs:sequence|xs:choice|xs:all)')

        cls.vh_schema = xmlschema.XMLSchema(cls.abspath('cases/examples/vehicles/vehicles.xsd'))
        cls.col_schema = xmlschema.XMLSchema(cls.abspath('cases/examples/collection/collection.xsd'))
        cls.st_schema = xmlschema.XMLSchema(cls.abspath('cases/features/decoder/simple-types.xsd'))

    @classmethod
    def abspath(cls, path):
        return os.path.join(cls.test_dir, path)

    def retrieve_schema_source(self, source):
        """
        Returns a schema source that can be used to create an XMLSchema instance.

        :param source: A string or an ElementTree's Element.
        :return: An schema source string, an ElementTree's Element or a full pathname.
        """
        if etree_iselement(source):
            if source.tag in (XSD_SCHEMA_TAG, 'schema'):
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
