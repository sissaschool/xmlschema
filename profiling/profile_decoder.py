#!/usr/bin/env python
#
# Copyright (c), 2022, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from timeit import timeit
from pathlib import Path

import xmlschema


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


if __name__ == '__main__':
    print('*' * 50)
    print("*** Decoder profile for xmlschema package ***")
    print('*' * 50)
    print()

    project_dir = Path(__file__).absolute().parent.parent
    collection_dir = project_dir.joinpath('tests/test_cases/examples/collection')

    schema = xmlschema.XMLSchema(collection_dir.joinpath('collection.xsd'))
    xml_file = collection_dir.joinpath('collection.xml').as_posix()

    print(xml_file)

    NUMBER = 1000

    print("*** Profile evaluation ***\n")

    setup = 'from __main__ import schema, xml_file'
    run_timeit("schema.decode(xml_file)", setup=setup, number=NUMBER)
    run_timeit("schema.is_valid(xml_file)", setup=setup, number=NUMBER)
