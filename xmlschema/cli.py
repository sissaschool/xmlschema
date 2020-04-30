# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Command Line Interface"""
import sys
import os
import argparse
import logging
import pathlib
from urllib.error import URLError

import xmlschema
from xmlschema import XMLSchema, XMLSchema11, iter_errors, to_json, from_json
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.etree import etree_tostring


PROGRAM_NAME = os.path.basename(sys.argv[0])

CONVERTERS_MAP = {
    'Unordered': xmlschema.UnorderedConverter,
    'Parker': xmlschema.ParkerConverter,
    'BadgerFish': xmlschema.BadgerFishConverter,
    'Abdera': xmlschema.AbderaConverter,
    'JsonML': xmlschema.JsonMLConverter,
    'Columnar': xmlschema.ColumnarConverter,
}


def xsd_version_number(value):
    if value not in ('1.0', '1.1'):
        msg = "%r is not an XSD version." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def defuse_data(value):
    if value not in ('always', 'remote', 'never'):
        msg = "%r is not a valid value." % value
        raise argparse.ArgumentTypeError(msg)
    return value


def get_loglevel(verbosity):
    if verbosity <= 0:
        return logging.ERROR
    elif verbosity == 1:
        return logging.WARNING
    elif verbosity == 2:
        return logging.INFO
    else:
        return logging.DEBUG


def get_converter(name):
    if name is None:
        return

    try:
        return CONVERTERS_MAP[name]
    except KeyError:
        raise ValueError("--converter must be in {!r}".format_map(list(CONVERTERS_MAP)))


def xml2json():
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, add_help=True,
                                     description="decode a set of XML files to JSON.")
    parser.usage = "%(prog)s [OPTION]... [FILE]...\n" \
                   "Try '%(prog)s --help' for more information."

    parser.add_argument('-v', dest='verbosity', action='count', default=0,
                        help="increase output verbosity.")
    parser.add_argument('--schema', type=str, metavar='PATH',
                        help="path or URL to an XSD schema.")
    parser.add_argument('--version', type=xsd_version_number, default='1.0',
                        help="XSD schema validator to use (default is 1.0).")
    parser.add_argument('-L', dest='locations', nargs=2, type=str, action='append',
                        metavar="URI/URL", help="schema location hint overrides.")
    parser.add_argument('--converter', type=str, metavar='NAME',
                        help="use a different XML to JSON convention instead of "
                             "the default converter. Option value can be one of "
                             "{!r}.".format(tuple(CONVERTERS_MAP)))
    parser.add_argument('--lazy', action='store_true', default=False,
                        help="use lazy decoding mode (slower but use less memory).")
    parser.add_argument('-o', '--output', type=str, default='.',
                        help="where to write the encoded XML files, current dir by default.")
    parser.add_argument('-f', '--force', action="store_true", default=False,
                        help="do not prompt before overwriting.")
    parser.add_argument('files', metavar='[XML_FILE ...]', nargs='+',
                        help="XML files to be decoded to JSON.")

    args = parser.parse_args()

    loglevel = get_loglevel(args.verbosity)
    schema_class = XMLSchema if args.version == '1.0' else XMLSchema11
    converter = get_converter(args.converter)
    if args.schema is not None:
        schema = schema_class(args.schema, locations=args.locations, loglevel=loglevel)
    else:
        schema = None

    base_path = pathlib.Path(args.output)
    if not base_path.exists():
        base_path.mkdir()
    elif not base_path.is_dir():
        raise XMLSchemaValueError("{!r} is not a directory".format(str(base_path)))

    tot_errors = 0
    for xml_path in map(pathlib.Path, args.files):
        json_path = base_path.joinpath(xml_path.name).with_suffix('.json')
        if json_path.exists() and not args.force:
            print("skip {}: the destination file exists!".format(str(json_path)))
            continue

        with open(str(json_path), 'w') as fp:
            try:
                errors = to_json(
                    xml_document=str(xml_path),
                    fp=fp,
                    schema=schema,
                    cls=schema_class,
                    converter=converter,
                    lazy=args.lazy,
                    validation='lax',
                )
            except (xmlschema.XMLSchemaException, URLError) as err:
                tot_errors += 1
                print("error with {}: {}".format(str(xml_path), str(err)))
                continue
            else:
                if not errors:
                    print("{} converted to {}".format(str(xml_path), str(json_path)))
                else:
                    tot_errors += len(errors)
                    print("{} converted to {} with {} errors".format(
                        str(xml_path), str(json_path), len(errors)
                    ))

    sys.exit(tot_errors)


def json2xml():
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, add_help=True,
                                     description="encode a set of JSON files to XML.")
    parser.usage = "%(prog)s [OPTION]... [FILE]...\n" \
                   "Try '%(prog)s --help' for more information."

    parser.add_argument('-v', dest='verbosity', action='count', default=0,
                        help="increase output verbosity.")
    parser.add_argument('--schema', type=str, metavar='PATH',
                        help="path or URL to an XSD schema.")
    parser.add_argument('--version', type=xsd_version_number, default='1.0',
                        help="XSD schema validator to use (default is 1.0).")
    parser.add_argument('-L', dest='locations', nargs=2, type=str, action='append',
                        metavar="URI/URL", help="schema location hint overrides.")
    parser.add_argument('--converter', type=str, metavar='NAME',
                        help="use a different XML to JSON convention instead of "
                             "the default converter. Option value can be one of "
                             "{!r}.".format(tuple(CONVERTERS_MAP)))
    parser.add_argument('-o', '--output', type=str, default='.',
                        help="where to write the encoded XML files, current dir by default.")
    parser.add_argument('-f', '--force', action="store_true", default=False,
                        help="do not prompt before overwriting")
    parser.add_argument('files', metavar='[JSON_FILE ...]', nargs='+',
                        help="JSON files to be encoded to XML.")

    args = parser.parse_args()

    loglevel = get_loglevel(args.verbosity)
    schema_class = XMLSchema if args.version == '1.0' else XMLSchema11
    converter = get_converter(args.converter)
    schema = schema_class(args.schema, locations=args.locations, loglevel=loglevel)

    base_path = pathlib.Path(args.output)
    if not base_path.exists():
        base_path.mkdir()
    elif not base_path.is_dir():
        raise XMLSchemaValueError("{!r} is not a directory".format(str(base_path)))

    tot_errors = 0
    for json_path in map(pathlib.Path, args.files):
        xml_path = base_path.joinpath(json_path.name).with_suffix('.xml')
        if xml_path.exists() and not args.force:
            print("skip {}: the destination file exists!".format(str(xml_path)))
            continue

        with open(str(json_path)) as fp:
            try:
                root, errors = from_json(
                    source=fp,
                    schema=schema,
                    converter=converter,
                    validation='lax',
                )
            except (xmlschema.XMLSchemaException, URLError) as err:
                tot_errors += 1
                print("error with {}: {}".format(str(xml_path), str(err)))
                continue
            else:
                if not errors:
                    print("{} converted to {}".format(str(json_path), str(xml_path)))
                else:
                    tot_errors += len(errors)
                    print("{} converted to {} with {} errors".format(
                        str(json_path), str(xml_path), len(errors)
                    ))

        with open(str(xml_path), 'w') as fp:
            fp.write(etree_tostring(root))

    sys.exit(tot_errors)


def validate():
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, add_help=True,
                                     description="validate a set of XML files.")
    parser.usage = "%(prog)s [OPTION]... [FILE]...\n" \
                   "Try '%(prog)s --help' for more information."
    parser.add_argument('-v', dest='verbosity', action='count', default=0,
                        help="increase output verbosity.")
    parser.add_argument('--schema', type=str, metavar='PATH',
                        help="path or URL to an XSD schema.")
    parser.add_argument('--version', type=xsd_version_number, default='1.0',
                        help="XSD schema validator to use (default is 1.0).")
    parser.add_argument('-L', dest='locations', nargs=2, type=str, action='append',
                        metavar="URI/URL", help="schema location hint overrides.")
    parser.add_argument('--lazy', action='store_true', default=False,
                        help="use lazy validation mode (slower but use less memory).")
    parser.add_argument('files', metavar='[XML_FILE ...]', nargs='+',
                        help="XML files to be validated.")

    args = parser.parse_args()

    tot_errors = 0
    for filepath in args.files:
        try:
            errors = list(iter_errors(filepath, schema=args.schema, lazy=args.lazy))
        except (xmlschema.XMLSchemaException, URLError) as err:
            tot_errors += 1
            print(str(err))
            continue
        else:
            if not errors:
                print("{} is valid".format(filepath))
            else:
                tot_errors += len(errors)
                print("{} is not valid".format(filepath))

    sys.exit(tot_errors)


if __name__ == '__main__':
    if sys.version_info < (3, 5, 0):
        sys.stderr.write("You need python 3.5 or later to run this program\n")
        sys.exit(1)

    validate()
