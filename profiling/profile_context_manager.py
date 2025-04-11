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


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


if __name__ == '__main__':
    from contextlib import contextmanager

    print('*' * 50)
    print("*** Decoder profile for xmlschema package ***")
    print('*' * 50)
    print()

    def func():
        pass

    def inner1():
        yield 1

    def value_from_generator():
        value, = inner1()
        return value

    # inner should not be created again and again
    @contextmanager
    def inner2():
        yield 1

    def value_from_with():
        with inner2() as value:
            return value

    class CM:

        def __init__(self):
            self.level = 0

        def __enter__(self):
            self.level += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.level -= 1
            return

    cm = CM()
    level = 10

    def value_from_with2():
        with cm as value:
            return value

    NUMBER = 20000

    print("*** Profile evaluation ***\n")

    setup = 'from __main__ import value_from_with, value_from_with2'
    run_timeit("value_from_with()", setup=setup, number=NUMBER)
    run_timeit("value_from_with2()", setup=setup, number=NUMBER)

    setup = 'from __main__ import cm'
    run_timeit("cm.level += 1; pass; cm.level -= 1", setup=setup, number=NUMBER)

    setup = 'from __main__ import func'
    run_timeit("func()", setup=setup, number=NUMBER)

    setup = 'from __main__ import level'
    run_timeit("level += 1; pass; level -= 1", setup=setup, number=NUMBER)
