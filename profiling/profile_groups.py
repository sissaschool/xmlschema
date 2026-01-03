#!/usr/bin/env python
#
# Copyright (c), 2026, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from timeit import timeit


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


if __name__ == '__main__':
    print('*' * 62)
    print("*** Timing group iterations                                ***")
    print("***" + ' ' * 56 + "***")
    print("*** iter_elements(): gains 10x using a cache for elements  ***")
    print('*' * 62)
    print()

    import xmlschema
    import pathlib

    schema_file = (pathlib.Path(__file__).parent.parent /
                   'tests/test_cases/features/models/models.xsd')
    schema = xmlschema.XMLSchema(schema_file)

    NUMBER = 1000000

    print("*** Group iterations using a list of _elements  ***\n")

    run_timeit('for e in schema.groups["group2"].iter_elements(): e',
               'from __main__ import schema', NUMBER)

    run_timeit('for e in schema.groups["group2"].elements: e',
               'from __main__ import schema', NUMBER)

    print()
