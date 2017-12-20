#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module runs tests on XML Schema regular expressions.
"""
from _test_common import *

from sys import maxunicode
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.codepoints import CodePointSet


class TestCodePointSet(unittest.TestCase):

    def test_modify(self):
        cds = CodePointSet([50, 90, 10, 90])
        self.assertEqual(cds, [10, 50, 90])
        self.assertRaises(XMLSchemaValueError, cds.add, -1)
        self.assertRaises(XMLSchemaValueError, cds.add, maxunicode + 1)
        cds.add([100, 20000])
        cds.discard([100, 19000])
        self.assertEqual(cds, [10, 50, 90, (19001, 20000)])
        cds.add(0)
        cds.discard(1)
        self.assertEqual(cds, [0, 10, 50, 90, (19001, 20000)])
        cds.discard(0)
        self.assertEqual(cds, [10, 50, 90, (19001, 20000)])
        cds.discard([10, 100])
        self.assertEqual(cds, [(19001, 20000)])
        cds.add(20)
        cds.add(19)
        cds.add(30)
        cds.add([30, 33])
        cds.add(30000)
        cds.add(30001)
        self.assertEqual(cds, [(19, 20), (30, 33), (19001, 20000), (30000, 30001)])
        cds.add(22)
        cds.add(21)
        cds.add(22)
        self.assertEqual(cds, [(19, 21), 22, (30, 33), (19001, 20000), (30000, 30001)])
        cds.discard([90, 50000])
        self.assertEqual(cds, [(19, 21), 22, (30, 33)])
        cds.discard(21)
        cds.discard(19)
        self.assertEqual(cds, [20, 22, (30, 33)])
        cds.discard([0, 200])
        self.assertEqual(cds, [])

    def test_complement(self):
        cds = CodePointSet([50, 90, 10, 90])
        self.assertEqual(list(cds.complement()), [(0, 9), (11, 49), (51, 89), (91, 1114111)])
        cds.add(11)
        self.assertEqual(list(cds.complement()), [(0, 9), (12, 49), (51, 89), (91, 1114111)])
        cds.add([0, 9])
        self.assertEqual(list(cds.complement()), [(12, 49), (51, 89), (91, 1114111)])

    def test_union_and_intersection(self):
        cds1 = CodePointSet([50, (90, 200), 10])
        cds2 = CodePointSet([10, 51, (89, 150), 90])
        self.assertEqual(cds1 | cds2, [10, (50, 51), (89, 200)])
        self.assertEqual(cds1 & cds2, [10, (90, 150)])


if __name__ == '__main__':
    unittest.main()
