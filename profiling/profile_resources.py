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

from xmlschema.resources import XMLResource


def run_timeit(stmt='pass', setup='pass', number=1000):
    seconds = timeit(stmt, setup=setup, number=number)
    print("{}: {}s".format(stmt, seconds))


def iter_root(res: XMLResource):
    for e in res.root.iter():
        pass


def iter_res(res: XMLResource):
    for e in res.iter():
        pass


def iter_root_and_access_namespaces(res: XMLResource):
    for e in res.root.iter():
        res.get_nsmap(e)
        res.get_xmlns(e)


def iter_res_and_access_namespaces(res: XMLResource):
    for e in res.iter():
        res.get_nsmap(e)
        res.get_xmlns(e)


if __name__ == '__main__':
    print('*' * 58)
    print("*** Memory and timing profile of XMLResource instances ***")
    print('*' * 58)
    print()

    xml_data = "<a><b1/><b2><c1/><c2/><c3/></b2><b3>" + "<c4/>" * 500 + "</b3></a>"
    resource = XMLResource(xml_data)

    NUMBER = 10000

    print("*** Profile evaluation ***\n")

    setup = 'from __main__ import resource, iter_root'
    run_timeit('iter_root(resource)', setup=setup, number=NUMBER)

    setup = 'from __main__ import resource, iter_res'
    run_timeit('iter_res(resource)', setup=setup, number=NUMBER)

    print()

    setup = 'from __main__ import resource, iter_root_and_access_namespaces'
    run_timeit('iter_root_and_access_namespaces(resource)', setup=setup, number=NUMBER)

    setup = 'from __main__ import resource, iter_res_and_access_namespaces'
    run_timeit('iter_res_and_access_namespaces(resource)', setup=setup, number=NUMBER)
