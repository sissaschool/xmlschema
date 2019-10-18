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
from __future__ import print_function, unicode_literals
import pdb
import os
import pickle
import time
import logging
import warnings

from xmlschema import XMLSchemaBase
from xmlschema.compat import PY3, unicode_type
from xmlschema.etree import lxml_etree, py_etree_element
from xmlschema.xpath import XMLSchemaContext
from xmlschema.validators import XsdValidator

from xmlschema.tests import XsdValidatorTestCase
from .observers import SchemaObserver


def make_schema_test_class(test_file, test_args, test_num, schema_class, narrow, check_with_lxml):
    """
    Creates a schema test class.

    :param test_file: the schema test file path.
    :param test_args: line arguments for test case.
    :param test_num: a positive integer number associated with the test case.
    :param schema_class: the schema class to use.
    :param narrow: skip extra checks (observed inspections).
    :param check_with_lxml: if `True` compare with lxml XMLSchema class, reporting anomalies. \
    Works only for XSD 1.0 tests.
    """
    xsd_file = os.path.relpath(test_file)

    # Extract schema test arguments
    expected_errors = test_args.errors
    expected_warnings = test_args.warnings
    inspect = test_args.inspect
    locations = test_args.locations
    defuse = test_args.defuse
    debug_mode = test_args.debug
    loglevel = logging.DEBUG if debug_mode else None

    class TestSchema(XsdValidatorTestCase):

        @classmethod
        def setUpClass(cls):
            cls.schema_class = schema_class
            cls.errors = []
            cls.longMessage = True

            if debug_mode:
                print("\n##\n## Testing %r schema in debug mode.\n##" % xsd_file)
                pdb.set_trace()

        def check_xsd_file(self):
            if expected_errors > 0:
                xs = schema_class(xsd_file, validation='lax', locations=locations,
                                  defuse=defuse, loglevel=loglevel)
            else:
                xs = schema_class(xsd_file, locations=locations, defuse=defuse, loglevel=loglevel)
            self.errors.extend(xs.maps.all_errors)

            if narrow and inspect:
                components_ids = set([id(c) for c in xs.maps.iter_components()])
                missing = [c for c in SchemaObserver.components if id(c) not in components_ids]
                if any(c for c in missing):
                    raise ValueError("schema missing %d components: %r" % (len(missing), missing))

            # Pickling test (only for Python 3, skip inspected schema classes test)
            if not inspect and PY3:
                try:
                    obj = pickle.dumps(xs)
                    deserialized_schema = pickle.loads(obj)
                except pickle.PicklingError:
                    # Don't raise if some schema parts (eg. a schema loaded from remote)
                    # are built with the SafeXMLParser that uses pure Python elements.
                    for e in xs.maps.iter_components():
                        elem = getattr(e, 'elem', getattr(e, 'root', None))
                        if isinstance(elem, py_etree_element):
                            break
                    else:
                        raise
                else:
                    self.assertTrue(isinstance(deserialized_schema, XMLSchemaBase))
                    self.assertEqual(xs.built, deserialized_schema.built)

            # XPath API tests
            if not inspect and not self.errors:
                context = XMLSchemaContext(xs)
                elements = [x for x in xs.iter()]
                context_elements = [x for x in context.iter() if isinstance(x, XsdValidator)]
                self.assertEqual(context_elements, [x for x in context.iter_descendants()])
                self.assertEqual(context_elements, elements)

        def check_xsd_file_with_lxml(self, xmlschema_time):
            start_time = time.time()
            lxs = lxml_etree.parse(xsd_file)
            try:
                lxml_etree.XMLSchema(lxs.getroot())
            except lxml_etree.XMLSchemaParseError as err:
                if not self.errors:
                    print("\nSchema error with lxml.etree.XMLSchema for file {!r} ({}): {}".format(
                        xsd_file, self.__class__.__name__, unicode_type(err)
                    ))
            else:
                if self.errors:
                    print("\nUnrecognized errors with lxml.etree.XMLSchema for file {!r} ({}): {}".format(
                        xsd_file, self.__class__.__name__,
                        '\n++++++\n'.join([unicode_type(e) for e in self.errors])
                    ))
                lxml_schema_time = time.time() - start_time
                if lxml_schema_time >= xmlschema_time:
                    print(
                        "\nSlower lxml.etree.XMLSchema ({:.3f}s VS {:.3f}s) with file {!r} ({})".format(
                            lxml_schema_time, xmlschema_time, xsd_file, self.__class__.__name__
                        ))

        def test_xsd_file(self):
            if inspect:
                SchemaObserver.clear()
            del self.errors[:]

            start_time = time.time()
            if expected_warnings > 0:
                with warnings.catch_warnings(record=True) as ctx:
                    warnings.simplefilter("always")
                    self.check_xsd_file()
                    self.assertEqual(len(ctx), expected_warnings,
                                     "%r: Wrong number of include/import warnings" % xsd_file)
            else:
                self.check_xsd_file()

                # Check with lxml.etree.XMLSchema class
            if check_with_lxml and lxml_etree is not None:
                self.check_xsd_file_with_lxml(xmlschema_time=time.time() - start_time)
            self.check_errors(xsd_file, expected_errors)

    TestSchema.__name__ = TestSchema.__qualname__ = str('TestSchema{0:03}'.format(test_num))
    return TestSchema
