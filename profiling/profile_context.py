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

import xmlschema


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


if __name__ == '__main__':
    from xmlschema import XMLResource
    from xmlschema.validators import DecodeContext

    print('*' * 50)
    print("*** Decoder profile for xmlschema package ***")
    print('*' * 50)
    print()

    def func(**kwargs):
        return kwargs

    def func2(context):
        return context

    resource = XMLResource('<root/>')

    data = DecodeContext(xmlschema.XMLSchema.meta_schema, source=None)
    # kwargs = asdict(data)

    # print(kwargs)
    NUMBER = 20000

    print("*** Profile evaluation ***\n")

    setup = 'from __main__ import resource, func, func2, data, replace, copy'
    run_timeit("copy(resource)", setup=setup, number=NUMBER)
    run_timeit("copy(data)", setup=setup, number=NUMBER)
    # run_timeit("copy(kwargs)", setup=setup, number=NUMBER)
    # run_timeit("replace(data)", setup=setup, number=NUMBER)
    # run_timeit("replace(data, validation='skip')", setup=setup, number=NUMBER)

    print()

    # run_timeit("func(**kwargs)", setup=setup, number=NUMBER)
    run_timeit("func2(data)", setup=setup, number=NUMBER)

    print()

    run_timeit("resource.root", setup=setup, number=NUMBER)
    run_timeit("resource._parent_map", setup=setup, number=NUMBER)
    run_timeit("resource._allow", setup=setup, number=NUMBER)
    run_timeit("resource.url", setup=setup, number=NUMBER)
    run_timeit("data.errors", setup=setup, number=NUMBER)
    run_timeit("data.converter", setup=setup, number=NUMBER)
    run_timeit("data.validation", setup=setup, number=NUMBER)
    run_timeit("data.element_hook", setup=setup, number=NUMBER)
    # run_timeit("kwargs['errors']", setup=setup, number=NUMBER)
