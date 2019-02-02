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
Check ElementTree import with xmlschema.
"""
import argparse
import sys

parser = argparse.ArgumentParser(add_help=True)
parser.add_argument(
    '--before', action="store_true", default=False,
    help="Import ElementTree before xmlschema. If not provided the ElementTree library "
         "is loaded after xmlschema."
)
args = parser.parse_args()

if args.before:
    print("Importing ElementTree before xmlschema ...")
    import xml.etree.ElementTree as ElementTree
    import xmlschema.etree
else:
    print("Importing ElementTree after xmlschema ...")
    import xmlschema.etree
    import xml.etree.ElementTree as ElementTree

# Check if all modules are loaded in the system table
assert 'xml.etree.ElementTree' in sys.modules, "ElementTree not loaded!"
assert 'xmlschema' in sys.modules, 'xmlschema not loaded'
assert 'xmlschema.etree' in sys.modules, 'xmlschema.etree not loaded'

if sys.version_info >= (3,):
    assert '_elementtree' in sys.modules, "cElementTree is not loaded!"

    # Check imported ElementTree
    assert ElementTree._Element_Py is not ElementTree.Element, "ElementTree is pure Python!"
    assert xmlschema.etree.ElementTree is ElementTree, "xmlschema has a different ElementTree module!"

    # Check ElementTree and pure Python ElementTree imported in xmlschema
    PyElementTree = xmlschema.etree.PyElementTree
    assert xmlschema.etree.ElementTree.Element is not xmlschema.etree.ElementTree._Element_Py, \
        "xmlschema's ElementTree is pure Python!"
    assert PyElementTree.Element is PyElementTree._Element_Py, "PyElementTree is not pure Python!"
    assert xmlschema.etree.ElementTree is not PyElementTree, "xmlschema ElementTree is PyElementTree!"

print("\nTest OK: ElementTree import is working as expected!")
