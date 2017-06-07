# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains base classes, functions and constants for the package.
"""
import logging
import sys
from xml.etree import ElementTree

try:
    # Python 2 import
    # noinspection PyCompatibility
    from StringIO import StringIO  # the io.StringIO accepts only unicode type
except ImportError:
    # Python 3 fallback
    from io import StringIO

PY3 = sys.version_info[0] >= 3

# Aliases for data types changed from version 2 to 3.
long_type = int if PY3 else long
unicode_type = str if PY3 else unicode
unicode_chr = chr if PY3 else unichr


# Namespaces for standards
XSD_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema'
"URI of the XML Schema Definition namespace (xs|xsd)"

XSI_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema-instance'
"URI of the XML Schema Instance namespace (xsi)"

XML_NAMESPACE_PATH = 'http://www.w3.org/XML/1998/namespace'
"URI of the XML namespace (xml)"

XHTML_NAMESPACE_PATH = 'http://www.w3.org/1999/xhtml'
XHTML_DATATYPES_NAMESPACE_PATH = "http://www.w3.org/1999/xhtml/datatypes/"
"URIs of the Extensible Hypertext Markup Language namespace (html)"

XLINK_NAMESPACE_PATH = 'http://www.w3.org/1999/xlink'
"URI of the XML Linking Language (XLink)"

XSLT_NAMESPACE_PATH = "http://www.w3.org/1999/XSL/Transform"
"URI of the XSL Transformations namespace (xslt)"

HFP_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty'
"URI of the XML Schema has Facet and Property namespace (hfp)"

VC_NAMESPACE_PATH = "http://www.w3.org/2007/XMLSchema-versioning"
"URI of the XML Schema Versioning namespace (vc)"


# Register missing namespaces into imported ElementTree module
ElementTree.register_namespace('xslt', XSLT_NAMESPACE_PATH)
ElementTree.register_namespace('hfp', HFP_NAMESPACE_PATH)
ElementTree.register_namespace('vc', VC_NAMESPACE_PATH)


def set_logger(name, loglevel=1, logfile=None):
    """
    Setup a basic logger with an handler and a formatter, using a
    corresponding numerical range [0..4], where a higher value means
    a more verbose logging. The loglevel value is mapped to correspondent
    logging module's value:

    LOG_CRIT=0 (syslog.h value is 2) ==> logging.CRITICAL
    LOG_ERR=1 (syslog.h value is 3) ==> logging.ERROR
    LOG_WARNING=2 (syslog.h value is 4) ==> logging.WARNING
    LOG_INFO=3 (syslog.h value is 6) ==> logging.INFO
    LOG_DEBUG=4 (syslog.h value is 7) ==> logging.DEBUG

    If a logfile name is passed then writes logs to file, instead of
    send logs to the standard output.

    :param name: logger name
    :param loglevel: Simplified POSIX's syslog like logging level index
    :param logfile: Logfile name for non-scripts runs
    """
    logger = logging.getLogger(name)

    # Higher or lesser argument values are also mapped to DEBUG or CRITICAL
    effective_level = max(logging.DEBUG, logging.CRITICAL - loglevel * 10)

    logger.setLevel(effective_level)

    # Add the first new handler
    if not logger.handlers:
        if logfile is None:
            lh = logging.StreamHandler()
        else:
            lh = logging.FileHandler(logfile)
        lh.setLevel(effective_level)

        if effective_level <= logging.DEBUG:
            formatter = logging.Formatter("[%(levelname)s:%(module)s:%(funcName)s: %(lineno)s] %(message)s")
        elif effective_level <= logging.INFO:
            formatter = logging.Formatter("[%(levelname)s:%(module)s] %(message)s")
        else:
            formatter = logging.Formatter("%(levelname)s: %(message)s")

        lh.setFormatter(formatter)
        logger.addHandler(lh)
    else:
        for handler in logger.handlers:
            handler.setLevel(effective_level)


# Define alias for ElementTree API for internal module imports
etree_iterparse = ElementTree.iterparse
etree_fromstring = ElementTree.fromstring
etree_parse_error = ElementTree.ParseError
etree_element = ElementTree.Element
etree_iselement = ElementTree.iselement
etree_register_namespace = ElementTree.register_namespace


def etree_tostring(elem, indent='', max_lines=None, spaces_for_tab=4):
    if PY3:
        lines = ElementTree.tostring(elem, encoding="unicode").splitlines()
    else:
        # noinspection PyCompatibility
        lines = unicode(ElementTree.tostring(elem)).splitlines()
    while lines and not lines[-1].strip():
        lines.pop(-1)
    lines[-1] = '  %s' % lines[-1].strip()

    if max_lines is not None:
        if indent:
            xml_text = '\n'.join([indent + line for line in lines[:max_lines]])
        else:
            xml_text = '\n'.join(lines[:max_lines])
        if len(lines) > max_lines + 2:
            xml_text += '\n%s    ...\n%s%s' % (indent, indent, lines[-1])
        elif len(lines) > max_lines:
            xml_text += '\n%s%s\n%s%s' % (indent, lines[-2], indent, lines[-1])
    elif indent:
        xml_text = '\n'.join([indent + line for line in lines])
    else:
        xml_text = '\n'.join(lines)

    return xml_text.replace('\t', ' ' * spaces_for_tab) if spaces_for_tab else xml_text


def etree_get_namespaces(source, namespaces=None):
    """
    Extracts namespaces with related prefixes from the XML source.
    The extracted namespaces are merged with the ones passed with
    the optional argument 'namespaces' and returned.
    
    :param source: A string containing the XML document or a file path 
    or a file like object or an etree Element.
    :param namespaces: An optional dictionary with a map from prefixes to full URI.
    :return: A dictionary for mapping namespace prefixes to full URI.
    """
    try:
        try:
            xml_namespaces = dict([
                node for _, node in etree_iterparse(StringIO(source), events=('start-ns',))
            ])
        except ElementTree.ParseError:
            xml_namespaces = dict([
                node for _, node in etree_iterparse(source, events=('start-ns',))
            ])
    except TypeError:
        try:
            if hasattr(source, 'getroot'):
                xml_namespaces = dict(source.getroot().nsmap)
            else:
                xml_namespaces = dict(source.nsmap)
        except (AttributeError, TypeError):
            xml_namespaces = {}

    if namespaces:
        uris = set(namespaces.values())
        namespaces.update({k: v for k, v in xml_namespaces.items() if v not in uris})
        return namespaces
    return xml_namespaces


def etree_iterpath(elem, tag=None, path='.'):
    """
    A version of ElementTree node's iter function that return a couple
    with node and its relative path.
    """
    if tag == "*":
        tag = None
    if tag is None or elem.tag == tag:
        yield elem, path
    for child in elem:
        if path == '/':
            child_path = '/%s' % child.tag
        elif path:
            child_path = '/'.join((path, child.tag))
        else:
            child_path = child.tag

        for _child, _child_path in etree_iterpath(child, tag, path=child_path):
            yield _child, _child_path
