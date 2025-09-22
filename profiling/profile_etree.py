# !/usr/bin/env python
#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from timeit import timeit
from textwrap import indent
from xml.etree import ElementTree

from xmlschema.utils.etree import etree_getpath  # noqa
from xmlschema.utils.etree import iter_schema_namespaces, prune_etree  # noqa


def run_timeit(stmt='pass', setup='pass', number=1000):
    msg = "Total seconds for executing {} times the following code: {}\n\n{}"
    seconds = timeit(stmt, setup=setup, number=number)
    print('-' * 80)
    print(msg.format(number, seconds, indent(stmt, '   ')))


if __name__ == '__main__':
    print('*' * 43)
    print("*** Timing profile of XML etree helpers ***")
    print('*' * 43)
    print()

    xml_data = "<a xmlns:foo='bar'><b1><c1/><c2/></b1><b2>" + "<foo:c3/>" * 250 + "</b2></a>"
    root = ElementTree.fromstring(xml_data)

    run_timeit(
        'for e in etree_iter_namespaces(root):\n    pass',
        setup='from __main__ import root, etree_iter_namespaces',
        number=10000
    )

    subtree = ''.join([f'<c{k}>\n' for k in range(20)] + [f'</c{k}>' for k in reversed(range(20))])
    xml_data = "<a><b1>" + subtree * 100 + "</b1></a>"

    run_timeit(
        'root = ElementTree.fromstring(xml_data)\n'
        'prune_etree(root, lambda x: x.tag == "c10")',
        setup='from __main__ import ElementTree, xml_data, prune_etree',
        number=1000
    )

    root = ElementTree.fromstring("<a><b1>" + subtree * 10 + "</b1></a>")  # noqa
    run_timeit(
        'namespaces = {\'foo\': \'bar\'}\n'
        'for e in root.iter():\n'
        '    etree_getpath(e, root, namespaces, add_position=True)',
        setup='from __main__ import root, etree_getpath',
        number=100
    )

    print('-' * 80)
