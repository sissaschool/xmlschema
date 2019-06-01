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
Check ElementTree memory usage for a given file.

Refs:
    https://pypi.org/project/memory_profiler/
"""
import argparse
from memory_profiler import profile
import xml.etree.ElementTree as ElementTree


def mode_type(value):
    if value not in ('full', 'iter', 'clear'):
        msg = "%r must be one of ('full', 'iter', 'clear')." % value
        raise argparse.ArgumentTypeError(msg)
    return value


parser = argparse.ArgumentParser(add_help=True)
parser.add_argument(
    '-m', '--mode', default='full', type=mode_type,
    help="XML parse mode, for default the XML parsed data is fully loaded into "
         "memory using the parse method. Passing 'iter' the check is done using "
         "the iterparse method, with 'clear' also delete already used subelements."
)
parser.add_argument(
    'file', metavar='FILE',
    help='Input XML file.'
)
args = parser.parse_args()


@profile
def etree_parse_memory(source):
    xt = ElementTree.parse(source)
    for _ in xt.iter():
        pass


@profile
def etree_iterparse_memory(source):
    context = ElementTree.iterparse(source, events=('start', 'end'))
    for event, elem in context:
        if event == "start":
            pass


@profile
def etree_light_iterparse_memory(source):
    context = ElementTree.iterparse(source, events=('start', 'end'))
    for event, elem in context:
        if event == 'end':
            elem.clear()


if __name__ == '__main__':
    if args.mode == 'full':
        etree_parse_memory(args.file)
    elif args.mode == 'iter':
        etree_iterparse_memory(args.file)
    else:
        etree_light_iterparse_memory(args.file)
