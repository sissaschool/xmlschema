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
import unittest
import pdb
import os
import sys
import pickle
import warnings

import xmlschema
from xmlschema import XMLSchemaValidationError, ParkerConverter, \
    BadgerFishConverter, AbderaConverter, JsonMLConverter, UnorderedConverter

from xmlschema.compat import unicode_type, ordered_dict_class
from xmlschema.etree import etree_tostring, ElementTree, \
    etree_elements_assert_equal, lxml_etree, lxml_etree_element
from xmlschema.resources import fetch_namespaces

from xmlschema.tests import XsdValidatorTestCase
from . import tests_factory


def iter_nested_items(items, dict_class=dict, list_class=list):
    if isinstance(items, dict_class):
        for k, v in items.items():
            for value in iter_nested_items(v, dict_class, list_class):
                yield value
    elif isinstance(items, list_class):
        for item in items:
            for value in iter_nested_items(item, dict_class, list_class):
                yield value
    elif isinstance(items, dict):
        raise TypeError("%r: is a dict() instead of %r." % (items, dict_class))
    elif isinstance(items, list):
        raise TypeError("%r: is a list() instead of %r." % (items, list_class))
    else:
        yield items


def make_validator_test_class(test_file, test_args, test_num, schema_class, narrow, check_with_lxml):
    """
    Creates a validator test class.

    :param test_file: the XML test file path.
    :param test_args: line arguments for test case.
    :param test_num: a positive integer number associated with the test case.
    :param schema_class: the schema class to use.
    :param narrow: skip other converters checks.
    :param check_with_lxml: if `True` compare with lxml XMLSchema class, reporting anomalies. \
    Works only for XSD 1.0 tests.
    """
    xml_file = os.path.relpath(test_file)
    msg_tmpl = "\n\n{}: %s.".format(xml_file)

    # Extract schema test arguments
    expected_errors = test_args.errors
    expected_warnings = test_args.warnings
    inspect = test_args.inspect
    locations = test_args.locations
    defuse = test_args.defuse
    skip_strict = test_args.skip
    debug_mode = test_args.debug

    class TestValidator(XsdValidatorTestCase):

        @classmethod
        def setUpClass(cls):
            # Builds schema instance using 'lax' validation mode to accepts also schemas with not crashing errors.
            cls.schema_class = schema_class
            source, _locations = xmlschema.fetch_schema_locations(xml_file, locations)
            cls.schema = schema_class(source, validation='lax', locations=_locations, defuse=defuse)
            if check_with_lxml and lxml_etree is not None:
                cls.lxml_schema = lxml_etree.parse(source)

            cls.errors = []
            cls.chunks = []
            cls.longMessage = True

            if debug_mode:
                print("\n##\n## Testing %r validation in debug mode.\n##" % xml_file)
                pdb.set_trace()

        def check_etree_encode(self, root, converter=None, **kwargs):
            namespaces = kwargs.get('namespaces', {})

            lossy = converter in (ParkerConverter, AbderaConverter)
            losslessly = converter is JsonMLConverter
            unordered = converter not in (AbderaConverter, JsonMLConverter) or \
                kwargs.get('unordered', False)

            data1 = self.schema.decode(root, converter=converter, **kwargs)
            if isinstance(data1, tuple):
                data1 = data1[0]  # When validation='lax'

            for _ in iter_nested_items(data1, dict_class=ordered_dict_class):
                pass

            try:
                elem1 = self.schema.encode(data1, path=root.tag, converter=converter, **kwargs)
            except XMLSchemaValidationError as err:
                raise AssertionError(str(err) + msg_tmpl % "error during re-encoding")

            if isinstance(elem1, tuple):
                # When validation='lax'
                if converter is not ParkerConverter:
                    for e in elem1[1]:
                        self.check_namespace_prefixes(unicode_type(e))
                elem1 = elem1[0]

            # Checks the encoded element to not contains reserved namespace prefixes
            if namespaces and all('ns%d' % k not in namespaces for k in range(10)):
                self.check_namespace_prefixes(etree_tostring(elem1, namespaces=namespaces))

            # Main check: compare original a re-encoded tree
            try:
                etree_elements_assert_equal(root, elem1, strict=False, unordered=unordered)
            except AssertionError as err:
                # If the check fails retry only if the converter is lossy (eg. ParkerConverter)
                # or if the XML case has defaults taken from the schema or some part of data
                # decoding is skipped by schema wildcards (set the specific argument in testfiles).
                if skip_strict:
                    pass  # can't ensure encode equivalence if the test case use defaults
                elif lossy:
                    pass  # can't check encode equivalence if the converter is lossy
                elif losslessly:
                    if debug_mode:
                        pdb.set_trace()
                    raise AssertionError(str(err) + msg_tmpl % "encoded tree differs from original")
                else:
                    # Lossy or augmenting cases are checked with another decoding/encoding pass
                    data2 = self.schema.decode(elem1, converter=converter, **kwargs)
                    if isinstance(data2, tuple):
                        data2 = data2[0]

                    if sys.version_info >= (3, 6):
                        # For Python < 3.6 cannot ensure attribute decoding order
                        try:
                            self.assertEqual(data1, data2, msg_tmpl % "re-decoded data changed")
                        except AssertionError:
                            if debug_mode:
                                pdb.set_trace()
                            raise

                    elem2 = self.schema.encode(data2, path=root.tag, converter=converter, **kwargs)
                    if isinstance(elem2, tuple):
                        elem2 = elem2[0]

                    try:
                        etree_elements_assert_equal(elem1, elem2, strict=False, unordered=unordered)
                    except AssertionError as err:
                        if debug_mode:
                            pdb.set_trace()
                        raise AssertionError(str(err) + msg_tmpl % "encoded tree differs after second pass")

        def check_json_serialization(self, root, converter=None, **kwargs):
            lossy = converter in (ParkerConverter, AbderaConverter)
            unordered = converter not in (AbderaConverter, JsonMLConverter) or \
                kwargs.get('unordered', False)

            data1 = xmlschema.to_json(root, schema=self.schema, converter=converter, **kwargs)
            if isinstance(data1, tuple):
                data1 = data1[0]

            elem1 = xmlschema.from_json(data1, schema=self.schema, path=root.tag, converter=converter, **kwargs)
            if isinstance(elem1, tuple):
                elem1 = elem1[0]

            data2 = xmlschema.to_json(elem1, schema=self.schema, converter=converter, **kwargs)
            if isinstance(data2, tuple):
                data2 = data2[0]

            if data2 != data1 and (skip_strict or lossy or unordered):
                # Can't ensure decode equivalence if the test case use defaults,
                # or the converter is lossy or the decoding is unordered.
                return

            if sys.version_info >= (3, 6):
                if data1 != data2:
                    print(data1)
                    print(data2)
                    print(converter, unordered)
                self.assertEqual(data2, data1, msg_tmpl % "serialized data changed at second pass")
            else:
                elem2 = xmlschema.from_json(data2, schema=self.schema, path=root.tag, converter=converter, **kwargs)
                if isinstance(elem2, tuple):
                    elem2 = elem2[0]

                try:
                    self.assertIsNone(etree_elements_assert_equal(
                        elem1, elem2, strict=False, skip_comments=True, unordered=unordered
                    ))
                except AssertionError as err:
                    self.assertIsNone(err, None)

        def check_decoding_with_element_tree(self):
            del self.errors[:]
            del self.chunks[:]

            def do_decoding():
                for obj in self.schema.iter_decode(xml_file):
                    if isinstance(obj, (xmlschema.XMLSchemaDecodeError, xmlschema.XMLSchemaValidationError)):
                        self.errors.append(obj)
                    else:
                        self.chunks.append(obj)

            if expected_warnings == 0:
                do_decoding()
            else:
                with warnings.catch_warnings(record=True) as ctx:
                    warnings.simplefilter("always")
                    do_decoding()
                    self.assertEqual(len(ctx), expected_warnings, "Wrong number of include/import warnings")

            self.check_errors(xml_file, expected_errors)

            if not self.chunks:
                raise ValueError("No decoded object returned!!")
            elif len(self.chunks) > 1:
                raise ValueError("Too many ({}) decoded objects returned: {}".format(len(self.chunks), self.chunks))
            elif not isinstance(self.chunks[0], dict):
                raise ValueError("Decoded object is not a dictionary: {}".format(self.chunks))
            else:
                self.assertTrue(True, "Successfully test decoding for {}".format(xml_file))

        def check_schema_serialization(self):
            # Repeat with serialized-deserialized schema (only for Python 3)
            serialized_schema = pickle.dumps(self.schema)
            deserialized_schema = pickle.loads(serialized_schema)
            errors = []
            chunks = []
            for obj in deserialized_schema.iter_decode(xml_file):
                if isinstance(obj, xmlschema.XMLSchemaValidationError):
                    errors.append(obj)
                else:
                    chunks.append(obj)

            self.assertEqual(len(errors), len(self.errors), msg_tmpl % "wrong number errors")
            self.assertEqual(chunks, self.chunks, msg_tmpl % "decoded data differ")

        def check_decode_api(self):
            # Compare with the decode API and other validation modes
            strict_data = self.schema.decode(xml_file)
            lax_data = self.schema.decode(xml_file, validation='lax')
            skip_data = self.schema.decode(xml_file, validation='skip')
            self.assertEqual(strict_data, self.chunks[0], msg_tmpl % "decode() API has a different result")
            self.assertEqual(lax_data[0], self.chunks[0], msg_tmpl % "'lax' validation has a different result")
            self.assertEqual(skip_data, self.chunks[0], msg_tmpl % "'skip' validation has a different result")

        def check_encoding_with_element_tree(self):
            root = ElementTree.parse(xml_file).getroot()
            namespaces = fetch_namespaces(xml_file)
            options = {'namespaces': namespaces, 'dict_class': ordered_dict_class}

            self.check_etree_encode(root, cdata_prefix='#', **options)  # Default converter
            if not narrow:
                self.check_etree_encode(root, ParkerConverter, validation='lax', **options)
                self.check_etree_encode(root, ParkerConverter, validation='skip', **options)
                self.check_etree_encode(root, BadgerFishConverter, **options)
                self.check_etree_encode(root, AbderaConverter, **options)
                self.check_etree_encode(root, JsonMLConverter, **options)
                self.check_etree_encode(root, UnorderedConverter, cdata_prefix='#', **options)

            options.pop('dict_class')
            self.check_json_serialization(root, cdata_prefix='#', **options)
            if not narrow:
                self.check_json_serialization(root, ParkerConverter, validation='lax', **options)
                self.check_json_serialization(root, ParkerConverter, validation='skip', **options)
                self.check_json_serialization(root, BadgerFishConverter, **options)
                self.check_json_serialization(root, AbderaConverter, **options)
                self.check_json_serialization(root, JsonMLConverter, **options)
                self.check_json_serialization(root, UnorderedConverter, **options)

        def check_decoding_and_encoding_with_lxml(self):
            xml_tree = lxml_etree.parse(xml_file)
            namespaces = fetch_namespaces(xml_file)

            errors = []
            chunks = []
            for obj in self.schema.iter_decode(xml_tree, namespaces=namespaces):
                if isinstance(obj, xmlschema.XMLSchemaValidationError):
                    errors.append(obj)
                else:
                    chunks.append(obj)

            self.assertEqual(chunks, self.chunks, msg_tmpl % "decoded data change with lxml")
            self.assertEqual(len(errors), len(self.errors), msg_tmpl % "errors number change with lxml")

            if not errors:
                root = xml_tree.getroot()
                if namespaces.get(''):
                    # Add a not empty prefix for encoding to avoid the use of reserved prefix ns0
                    namespaces['tns0'] = namespaces['']

                options = {
                    'etree_element_class': lxml_etree_element,
                    'namespaces': namespaces,
                    'dict_class': ordered_dict_class,
                }
                self.check_etree_encode(root, cdata_prefix='#', **options)  # Default converter
                if not narrow:
                    self.check_etree_encode(root, ParkerConverter, validation='lax', **options)
                    self.check_etree_encode(root, ParkerConverter, validation='skip', **options)
                    self.check_etree_encode(root, BadgerFishConverter, **options)
                    self.check_etree_encode(root, AbderaConverter, **options)
                    self.check_etree_encode(root, JsonMLConverter, **options)
                    self.check_etree_encode(root, UnorderedConverter, cdata_prefix='#', **options)

                options.pop('dict_class')
                self.check_json_serialization(root, cdata_prefix='#', **options)
                if not narrow:
                    self.check_json_serialization(root, ParkerConverter, validation='lax', **options)
                    self.check_json_serialization(root, ParkerConverter, validation='skip', **options)
                    self.check_json_serialization(root, BadgerFishConverter, **options)
                    self.check_json_serialization(root, AbderaConverter, **options)
                    self.check_json_serialization(root, JsonMLConverter, **options)
                    self.check_json_serialization(root, UnorderedConverter, **options)

        def check_validate_and_is_valid_api(self):
            if expected_errors:
                self.assertFalse(self.schema.is_valid(xml_file), msg_tmpl % "file with errors is valid")
                self.assertRaises(XMLSchemaValidationError, self.schema.validate, xml_file)
            else:
                self.assertTrue(self.schema.is_valid(xml_file), msg_tmpl % "file without errors is not valid")
                self.assertEqual(self.schema.validate(xml_file), None,
                                 msg_tmpl % "file without errors not validated")

        def check_iter_errors(self):
            self.assertEqual(len(list(self.schema.iter_errors(xml_file))), expected_errors,
                             msg_tmpl % "wrong number of errors (%d expected)" % expected_errors)

        def check_lxml_validation(self):
            try:
                schema = lxml_etree.XMLSchema(self.lxml_schema.getroot())
            except lxml_etree.XMLSchemaParseError:
                print("\nSkip lxml.etree.XMLSchema validation test for {!r} ({})".
                      format(xml_file, TestValidator.__name__, ))
            else:
                xml_tree = lxml_etree.parse(xml_file)
                if self.errors:
                    self.assertFalse(schema.validate(xml_tree))
                else:
                    self.assertTrue(schema.validate(xml_tree))

        def test_xml_document_validation(self):
            self.check_decoding_with_element_tree()

            if not inspect and sys.version_info >= (3,):
                self.check_schema_serialization()

            if not self.errors:
                self.check_encoding_with_element_tree()

            if lxml_etree is not None:
                self.check_decoding_and_encoding_with_lxml()

            self.check_iter_errors()
            self.check_validate_and_is_valid_api()
            if check_with_lxml and lxml_etree is not None:
                self.check_lxml_validation()

    TestValidator.__name__ = TestValidator.__qualname__ = 'TestValidator{0:03}'.format(test_num)
    return TestValidator


if __name__ == '__main__':
    from xmlschema.tests import print_test_header

    # Creates decoding/encoding tests classes from XML files
    globals().update(tests_factory(make_validator_test_class, 'xml'))

    print_test_header()
    unittest.main()
