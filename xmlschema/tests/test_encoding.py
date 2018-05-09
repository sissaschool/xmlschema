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
This module runs tests concerning the encoding to XML data with the 'xmlschema' package.
"""
import unittest
import os
import sys
from collections import OrderedDict
from decimal import Decimal
from xml.etree import ElementTree as _ElementTree

try:
    import lxml.etree as _lxml_etree
except ImportError:
    _lxml_etree = None

try:
    import xmlschema
except ImportError:
    # Adds the package base dir path as first search path for imports
    pkg_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, pkg_base_dir)
    import xmlschema

from xmlschema.qnames import local_name


class TestEncoding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.dirname(__file__)
        cls.namespaces = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'vh': 'http://example.com/vehicles',
            'col': 'http://example.com/ns/collection',
            'dt': 'http://example.com/decoder'
        }
        cls.vh_schema = xmlschema.XMLSchema(os.path.join(cls.test_dir, 'cases/examples/vehicles/vehicles.xsd'))
        cls.col_schema = xmlschema.XMLSchema(os.path.join(cls.test_dir, 'cases/examples/collection/collection.xsd'))
        cls.decoder_schema = xmlschema.XMLSchema(os.path.join(cls.test_dir, 'cases/features/decoding/decoder.xsd'))

    def test_decode_encode(self):
        filename = os.path.join(self.test_dir, 'cases/examples/collection/collection.xml')
        xt = _ElementTree.parse(filename)
        xd = self.col_schema.to_dict(filename, dict_class=OrderedDict)
        elem = self.col_schema.encode(xd, path='./col:collection', namespaces=self.namespaces)

        self.assertEqual(
            len([e for e in elem.iter()]), 20,
            msg="The encoded tree must have 20 elements as the origin."
        )
        self.assertTrue(all([
            local_name(e1.tag) == local_name(e2.tag)
            for e1, e2 in zip(elem.iter(), xt.getroot().iter())
        ]))


if __name__ == '__main__':
    from xmlschema.tests import print_test_header
    print_test_header()
    unittest.main()
