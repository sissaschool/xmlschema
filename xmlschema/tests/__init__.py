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
Tests subpackage module: common definitions for unittest scripts of the 'xmlschema' package.
"""
import unittest
import platform
import re
import os

import xmlschema
from xmlschema import XMLSchema
from xmlschema.compat import urlopen, URLError
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.etree import (
    is_etree_element, etree_element, etree_register_namespace, etree_elements_assert_equal
)
from xmlschema.resources import fetch_namespaces
from xmlschema.qnames import XSD_SCHEMA
from xmlschema.helpers import get_namespace
from xmlschema.namespaces import XSD_NAMESPACE

from .schema_observers import SchemaObserver
from .test_factory import tests_factory


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
PROTECTED_PREFIX_PATTERN = re.compile(r'ns\d:')


def print_test_header():
    header1 = "Test %r" % xmlschema
    header2 = "with Python {} on platform {}".format(platform.python_version(), platform.platform())
    print('{0}\n{1}\n{2}\n{0}'.format("*" * max(len(header1), len(header2)), header1, header2))


class XMLSchemaTestCase(unittest.TestCase):
    """
    XMLSchema TestCase class.

    Setup tests common environment. The tests parts have to use empty prefix for
    XSD namespace names and 'ns' prefix for XMLSchema test namespace names.
    """

    test_dir = os.path.dirname(__file__)
    test_cases_dir = os.path.join(test_dir, 'test_cases/')
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

        cls.vh_dir = cls.casepath('examples/vehicles')
        cls.vh_xsd_file = cls.casepath('examples/vehicles/vehicles.xsd')
        cls.vh_xml_file = cls.casepath('examples/vehicles/vehicles.xml')
        cls.vh_json_file = cls.casepath('examples/vehicles/vehicles.json')
        cls.vh_schema = cls.schema_class(cls.vh_xsd_file)
        cls.vh_namespaces = fetch_namespaces(cls.vh_xml_file)

        cls.col_dir = cls.casepath('examples/collection')
        cls.col_xsd_file = cls.casepath('examples/collection/collection.xsd')
        cls.col_xml_file = cls.casepath('examples/collection/collection.xml')
        cls.col_json_file = cls.casepath('examples/collection/collection.json')
        cls.col_schema = cls.schema_class(cls.col_xsd_file)
        cls.col_namespaces = fetch_namespaces(cls.col_xml_file)

        cls.st_xsd_file = cls.casepath('features/decoder/simple-types.xsd')
        cls.st_schema = cls.schema_class(cls.st_xsd_file)

        cls.models_xsd_file = cls.casepath('features/models/models.xsd')
        cls.models_schema = cls.schema_class(cls.models_xsd_file)

    @classmethod
    def casepath(cls, path):
        """
        Returns the absolute path for a test case file.

        :param path: the relative path of the case file from base dir ``test_cases/``.
        """
        return os.path.join(cls.test_cases_dir, path)

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
