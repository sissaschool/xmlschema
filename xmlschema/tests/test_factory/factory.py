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
import os
import glob
import fileinput
import logging

from xmlschema.validators import XMLSchema10, XMLSchema11
from .arguments import TEST_FACTORY_OPTIONS, get_test_args, create_test_line_args_parser
from .observers import ObservedXMLSchema10, ObservedXMLSchema11

logger = logging.getLogger(__file__)


test_line_parser = create_test_line_args_parser()


def tests_factory(test_class_builder, suffix='xml'):
    """
    Factory function for file based schema/validation cases.

    :param test_class_builder: the test class builder function.
    :param suffix: the suffix ('xml' or 'xsd') to consider for cases.
    :return: a list of test classes.
    """
    test_classes = {}
    test_num = 0
    debug_mode = False
    line_buffer = []

    test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    testfiles = [os.path.join(test_dir, 'test_cases/testfiles')]
    narrow = TEST_FACTORY_OPTIONS['narrow']
    if TEST_FACTORY_OPTIONS['extra_cases']:
        package_dir = os.path.dirname(os.path.dirname(test_dir))
        testfiles.extend(glob.glob(os.path.join(package_dir, 'test_cases/testfiles')))

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

        if test_args.version == '1.0':
            schema_class = ObservedXMLSchema10 if test_args.inspect else XMLSchema10
            check_with_lxml = TEST_FACTORY_OPTIONS['check_with_lxml']
        else:
            schema_class = ObservedXMLSchema11 if test_args.inspect else XMLSchema11
            check_with_lxml = False

        test_class = test_class_builder(
            test_file, test_args, test_num, schema_class, narrow, check_with_lxml
        )
        test_classes[test_class.__name__] = test_class
        logger.debug("Add XSD %s test class %r.", test_args.version, test_class.__name__)

    if line_buffer:
        raise ValueError("Not completed line continuation at the end!")

    return test_classes
