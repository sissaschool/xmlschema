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
from dataclasses import dataclass
from collections import namedtuple


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


if __name__ == '__main__':
    print('*' * 50)
    print("*** Decoder profile for xmlschema package ***")
    print('*' * 50)
    print()
    from xmlschema.arguments import BooleanOption

    @dataclass(slots=True)
    class DataParams:
        boolean_option: bool
        converter: None
        errors: list
        source: str
        namespaces: dict
        a: None = None
        b: None = None
        c: None = None
        d: None = None
        e: None = None
        f: None = None
        k: None = None
        g: None = None
        h: None = None
        j: None = None

    class Params:
        boolean_option: BooleanOption = BooleanOption(default=False)

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SlotParams:
        boolean_option: BooleanOption = BooleanOption(default=False)
        __slots__ = ('_boolean_option', 'converter', 'errors', 'source', 'namespaces')

        def __init__(self):
            self._boolean_option = False
            self.converter = None
            self.errors = []
            self.source = 'data'
            self.namespaces = {}

    ParamTup = namedtuple('ParamTup', ('converter', 'errors', 'source', 'namespaces'))
    tuple_params = ParamTup(None, [], 'data', {})

    dict_params = {
        'boolean_option': True,
        'converter': None,
        'errors': [],
        'source': 'data',
        'namespaces': {},
    }

    data_params = DataParams(**dict_params)

    params = Params(**dict_params)
    slot_params = SlotParams()

    NUMBER = 1000000

    print("*** Profile evaluation ***\n")

    setup = 'from __main__ import dict_params as params'
    run_timeit("params['converter']", setup=setup, number=NUMBER)

    setup = 'from __main__ import params'
    run_timeit("params.converter", setup=setup, number=NUMBER)

    setup = 'from __main__ import params'
    run_timeit("params.boolean_option", setup=setup, number=NUMBER)

    setup = 'from __main__ import tuple_params'
    run_timeit("tuple_params.converter", setup=setup, number=NUMBER)

    setup = 'from __main__ import data_params'
    run_timeit("data_params.converter", setup=setup, number=NUMBER)

    setup = 'from __main__ import slot_params'
    run_timeit("slot_params.converter", setup=setup, number=NUMBER)
    run_timeit("slot_params._boolean_option", setup=setup, number=NUMBER)
    run_timeit("slot_params.boolean_option", setup=setup, number=NUMBER)
