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
import logging
import sys
from xml.etree import ElementTree

try:
    # Python 3 specific imports
    from urllib.request import urlopen, urljoin, urlsplit
    from urllib.parse import uses_relative, urlparse
    from urllib.error import URLError
except ImportError:
    # Python 2 fallback
    from urllib2 import urlopen, URLError
    from urlparse import urlsplit, urljoin, uses_relative, urlparse

PY3 = sys.version_info[0] >= 3


# Core Exceptions
class XMLSchemaException(Exception):
    """Package's base exception class"""
    pass


class XMLSchemaTypeError(XMLSchemaException, TypeError):
    pass


class XMLSchemaValueError(XMLSchemaException, ValueError):
    pass


class XMLSchemaOSError(XMLSchemaException, OSError):
    pass


class XMLSchemaLookupError(XMLSchemaException, LookupError):
    pass


class XMLSchemaIndexError(XMLSchemaLookupError, IndexError):
    pass


class XMLSchemaKeyError(XMLSchemaLookupError, KeyError):
    pass



# Namespaces for standards
XSD_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema'
"URI of the XML Schema Definition namespace (xs|xsd)"

XSI_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema-instance'
"URI of the XML Schema Instance namespace (xsi)"

XML_NAMESPACE_PATH = 'http://www.w3.org/XML/1998/namespace'
"URI of the XML namespace (xml)"

XHTML_NAMESPACE_PATH = 'http://www.w3.org/1999/xhtml'
"URI of the Extensible Hypertext Markup Language namespace (html)"

XSLT_NAMESPACE_PATH = "http://www.w3.org/1999/XSL/Transform"
"URI of the XSL Transformations namespace (xslt)"

HFP_NAMESPACE_PATH = 'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty'
"URI of the XML Schema has Facet and Property namespace (hfp)"

VC_NAMESPACE_PATH = "http://www.w3.org/2007/XMLSchema-versioning"
"URI of the XML Schema Versioning namespace (vc)"


BASE_SCHEMAS = {
    XSD_NAMESPACE_PATH: None,
    XHTML_NAMESPACE_PATH: None,
    XML_NAMESPACE_PATH: 'schemas/XML/xml.xsd',
    XSI_NAMESPACE_PATH: 'schemas/XSI/XMLSchema-instance.xsd',
    XSLT_NAMESPACE_PATH: 'schemas/XSLT/schema-for-xslt20.xsd',
    HFP_NAMESPACE_PATH: 'schemas/HFP/XMLSchema-hasFacetAndProperty.xsd'
}
"""Base namespaces and related schema definition path."""


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


# Define ElementTree API for internal module imports
etree_iterparse = ElementTree.iterparse
etree_fromstring = ElementTree.fromstring
etree_parse_error = ElementTree.ParseError


def etree_tostring(elem, indent='', max_lines=None, spaces_for_tab=4):
    if PY3:
        xml_text = ElementTree.tostring(elem, encoding="unicode")
    else:
        xml_text = unicode(ElementTree.tostring(elem))

    if max_lines is not None and indent:
        xml_text = '\n'.join([indent + line for line in xml_text.splitlines()[:max_lines]])
    elif max_lines is not None:
        xml_text = '\n'.join(xml_text.splitlines()[:max_lines])
    elif indent:
        xml_text = '\n'.join([indent + line for line in xml_text.splitlines()])

    if spaces_for_tab:
        xml_text.replace('\t', ' ' * spaces_for_tab)
    return xml_text
