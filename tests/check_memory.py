#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
Check xmlschema package memory usage.

Refs:
    https://pypi.org/project/memory_profiler/
    https://github.com/brunato/xmlschema/issues/32
"""
import argparse


def test_choice_type(value):
    if value not in (str(v) for v in range(1, 14)):
        msg = "%r must be an integer between [1 ... 13]." % value
        raise argparse.ArgumentTypeError(msg)
    return int(value)


parser = argparse.ArgumentParser(add_help=True)
parser.usage = """%(prog)s TEST_NUM [XML_FILE [REPEAT]]

Run memory tests:
  1) Package import or schema build
  2) Iterate XML file with parse
  3) Iterate XML file with full iterparse
  4) Iterate XML file with emptied iterparse
  5) Decode XML file with xmlschema
  6) Decode XML file with xmlschema in lazy mode
  7) Validate XML file with xmlschema
  8) Validate XML file with xmlschema in lazy mode
  9) Iterate XML file with XMLResource instance
  10) Iterate XML file with lazy XMLResource instance
  11) Iterate XML file with lazy XMLResource instance (thin lazy iter)
  12) Iterate XML file with lxml parse
  13) Iterate XML file with lxml full iterparse

"""

parser.add_argument('test_num', metavar="TEST_NUM", type=test_choice_type,
                    help="Test number to run")
parser.add_argument('xml_file', metavar='XML_FILE', nargs='?', help='Input XML file')
parser.add_argument('repeat', metavar='REPEAT', nargs='?', type=int, default=1,
                    help='Repeat operation N times')
args = parser.parse_args()


def profile_memory(func):
    def wrapper(*a, **kw):
        mem = this_process.memory_info().rss
        result = func(*a, **kw)
        mem = this_process.memory_info().rss - mem
        print("Memory usage by %s(): %.2f MB (%d)" % (func.__name__, mem / 1024 ** 2, mem))
        return result

    return wrapper


@profile_memory
def import_package():
    # Imports of packages used by xmlschema that
    # have a significant memory usage impact.
    import xmlschema
    return xmlschema


@profile_memory
def build_schema(source):
    xs = xmlschema.XMLSchema(source)
    return xs


@profile_memory
def etree_parse(source, repeat=1):
    xt = ElementTree.parse(source)
    for _ in range(repeat):
        for _ in xt.iter():
            pass
    del xt


@profile_memory
def etree_full_iterparse(source, repeat=1):
    for _ in range(repeat):
        context = ElementTree.iterparse(source, events=('start', 'end'))
        for event, elem in context:
            if event == 'start':
                pass


@profile_memory
def etree_emptied_iterparse(source, repeat=1):
    for _ in range(repeat):
        context = ElementTree.iterparse(source, events=('start', 'end'))
        for event, elem in context:
            if event == 'end':
                elem.clear()


@profile_memory
def decode(source, repeat=1):
    decoder = xmlschema.XMLSchema.meta_schema if source.endswith('.xsd') else xmlschema
    for _ in range(repeat):
        decoder.to_dict(source)


@profile_memory
def lazy_decode(source, repeat=1):
    if source.endswith('.xsd'):
        decoder = xmlschema.XMLSchema.meta_schema.iter_decode
    else:
        decoder = xmlschema.iter_decode  # type: ignore

    for _ in range(repeat):
        for _result in decoder(xmlschema.XMLResource(source, lazy=True), path='*'):
            del _result


@profile_memory
def validate(source, repeat=1):
    validator = xmlschema.XMLSchema.meta_schema if source.endswith('.xsd') else xmlschema
    for _ in range(repeat):
        validator.validate(source)


@profile_memory
def lazy_validate(source, repeat=1):
    if source.endswith('.xsd'):
        validator, path = xmlschema.XMLSchema.meta_schema, '*'
    else:
        validator, path = xmlschema, None

    for _ in range(repeat):
        validator.validate(xmlschema.XMLResource(source, lazy=True), path=path)


@profile_memory
def full_xml_resource(source, repeat=1):
    xr = xmlschema.XMLResource(source)
    for _ in range(repeat):
        for _ in xr.iter():
            pass
    del xr


@profile_memory
def lazy_xml_resource(source, repeat=1):
    xr = xmlschema.XMLResource(source, lazy=True, thin_lazy=False)
    for _ in range(repeat):
        for _ in xr.iter():
            pass
    del xr


@profile_memory
def thin_lazy_xml_resource(source, repeat=1):
    xr = xmlschema.XMLResource(source, lazy=True)
    for _ in range(repeat):
        for _ in xr.iter():
            pass
    del xr


@profile_memory
def lxml_etree_parse(source, repeat=1):
    xt = etree.parse(source)
    for _ in range(repeat):
        for _ in xt.iter():
            pass
    del xt


@profile_memory
def lxml_etree_full_iterparse(source, repeat=1):
    for _ in range(repeat):
        context = etree.iterparse(source, events=('start', 'end'))
        for event, elem in context:
            if event == 'start':
                pass


if __name__ == '__main__':
    import os
    import decimal                     # noqa
    from urllib.error import URLError  # noqa
    from xml.etree import ElementTree

    import lxml.etree as etree         # noqa
    import elementpath                 # noqa
    import psutil

    this_process = psutil.Process(os.getpid())

    if args.test_num == 1 and args.xml_file is None:
        import_package()
    else:
        import xmlschema

        if args.test_num == 1:
            build_schema(args.xml_file)
        elif args.test_num == 2:
            etree_parse(args.xml_file, args.repeat)
        elif args.test_num == 3:
            etree_full_iterparse(args.xml_file, args.repeat)
        elif args.test_num == 4:
            etree_emptied_iterparse(args.xml_file, args.repeat)
        elif args.test_num == 5:
            xmlschema.XMLSchema.meta_schema.build()
            decode(args.xml_file, args.repeat)
        elif args.test_num == 6:
            xmlschema.XMLSchema.meta_schema.build()
            lazy_decode(args.xml_file, args.repeat)
        elif args.test_num == 7:
            xmlschema.XMLSchema.meta_schema.build()
            validate(args.xml_file, args.repeat)
        elif args.test_num == 8:
            xmlschema.XMLSchema.meta_schema.build()
            lazy_validate(args.xml_file, args.repeat)
        elif args.test_num == 9:
            full_xml_resource(args.xml_file, args.repeat)
        elif args.test_num == 10:
            lazy_xml_resource(args.xml_file, args.repeat)
        elif args.test_num == 11:
            thin_lazy_xml_resource(args.xml_file, args.repeat)
        elif args.test_num == 12:
            lxml_etree_parse(args.xml_file, args.repeat)
        elif args.test_num == 13:
            lxml_etree_full_iterparse(args.xml_file, args.repeat)
