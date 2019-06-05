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
Check xmlschema decoding memory usage for a given file.

Refs:
    https://pypi.org/project/memory_profiler/
"""
import argparse
from memory_profiler import profile
import xmlschema
from xmlschema import XMLResource



parser = argparse.ArgumentParser(add_help=True)
parser.add_argument('file', metavar='FILE', help='Input XML file.')
args = parser.parse_args()


@profile
def lazy_etree_decode_memory(source):
    #source = XMLResource(source, lazy=True)
    return xmlschema.to_dict(source, path="spirit:busInterfaces")


@profile
def full_tree_decode_memory(source):
    return xmlschema.to_dict(source)


if __name__ == '__main__':
    lazy_etree_decode_memory(args.file)
    full_tree_decode_memory(args.file)
