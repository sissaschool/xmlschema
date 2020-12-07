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
from memory_profiler import profile


def test_choice_type(value):
    if value not in (str(v) for v in range(1, 9)):
        msg = "%r must be an integer between [1 ... 8]." % value
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

"""

parser.add_argument('test_num', metavar="TEST_NUM", type=test_choice_type,
                    help="Test number to run")
parser.add_argument('xml_file', metavar='XML_FILE', nargs='?', help='Input XML file')
parser.add_argument('repeat', metavar='REPEAT', nargs='?', type=int, default=1,
                    help='Repeat operation N times')
args = parser.parse_args()


# noinspection PyUnresolvedReferences
@profile
def import_package():
    # Imports of packages used by xmlschema that
    # have a significant memory usage impact.
    import decimal
    from urllib.error import URLError
    import lxml.etree
    import elementpath

    import xmlschema
    return xmlschema


@profile
def build_schema(source):
    xs = xmlschema.XMLSchema(source)
    return xs


@profile
def etree_parse(source, repeat=1):
    xt = ElementTree.parse(source)
    for _ in range(repeat):
        for _ in xt.iter():
            pass


@profile
def etree_full_iterparse(source, repeat=1):
    for _ in range(repeat):
        context = ElementTree.iterparse(source, events=('start', 'end'))
        for event, elem in context:
            if event == 'start':
                pass


@profile
def etree_emptied_iterparse(source, repeat=1):
    for _ in range(repeat):
        context = ElementTree.iterparse(source, events=('start', 'end'))
        for event, elem in context:
            if event == 'end':
                elem.clear()


@profile
def decode(source, repeat=1):
    decoder = xmlschema.XMLSchema.meta_schema if source.endswith('.xsd') else xmlschema
    for _ in range(repeat):
        decoder.to_dict(source)


@profile
def lazy_decode(source, repeat=1):
    decoder = xmlschema.XMLSchema.meta_schema if source.endswith('.xsd') else xmlschema
    for _ in range(repeat):
        for _result in decoder.to_dict(xmlschema.XMLResource(source, lazy=True), path='*'):
            del _result


@profile
def validate(source, repeat=1):
    validator = xmlschema.XMLSchema.meta_schema if source.endswith('.xsd') else xmlschema
    for _ in range(repeat):
        validator.validate(source)


@profile
def lazy_validate(source, repeat=1):
    if source.endswith('.xsd'):
        validator, path = xmlschema.XMLSchema.meta_schema, '*'
    else:
        validator, path = xmlschema, None

    for _ in range(repeat):
        validator.validate(xmlschema.XMLResource(source, lazy=True), path=path)


if __name__ == '__main__':
    if args.test_num == 1:
        if args.xml_file is None:
            import_package()
        else:
            import xmlschema
            build_schema(args.xml_file)
    elif args.test_num == 2:
        import xml.etree.ElementTree as ElementTree
        etree_parse(args.xml_file, args.repeat)
    elif args.test_num == 3:
        import xml.etree.ElementTree as ElementTree
        etree_full_iterparse(args.xml_file, args.repeat)
    elif args.test_num == 4:
        import xml.etree.ElementTree as ElementTree
        etree_emptied_iterparse(args.xml_file, args.repeat)
    elif args.test_num == 5:
        import xmlschema
        xmlschema.XMLSchema.meta_schema.build()
        decode(args.xml_file, args.repeat)
    elif args.test_num == 6:
        import xmlschema
        xmlschema.XMLSchema.meta_schema.build()
        lazy_decode(args.xml_file, args.repeat)
    elif args.test_num == 7:
        import xmlschema
        xmlschema.XMLSchema.meta_schema.build()
        validate(args.xml_file, args.repeat)
    elif args.test_num == 8:
        import xmlschema
        xmlschema.XMLSchema.meta_schema.build()
        lazy_validate(args.xml_file, args.repeat)
