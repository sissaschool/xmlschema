# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains ElementTree setup and helpers for xmlschema package.
"""
from xml.etree import ElementTree
from .compat import PY3, StringIO
from .exceptions import XMLSchemaValueError
from .namespaces import XSLT_NAMESPACE, HFP_NAMESPACE, VC_NAMESPACE

import defusedxml.ElementTree

# Register missing namespaces into imported ElementTree module
ElementTree.register_namespace('xslt', XSLT_NAMESPACE)
ElementTree.register_namespace('hfp', HFP_NAMESPACE)
ElementTree.register_namespace('vc', VC_NAMESPACE)


# Define alias for ElementTree API for internal module imports
etree_iterparse = ElementTree.iterparse
etree_fromstring = ElementTree.fromstring
etree_parse_error = ElementTree.ParseError
etree_element = ElementTree.Element
etree_iselement = ElementTree.iselement
etree_register_namespace = ElementTree.register_namespace


# Safe APIs from defusedxml package
safe_etree_parse = defusedxml.ElementTree.parse
safe_etree_iterparse = defusedxml.ElementTree.iterparse
safe_etree_fromstring = defusedxml.ElementTree.fromstring
safe_etree_parse_error = defusedxml.ElementTree.ParseError


def etree_tostring(elem, indent='', max_lines=None, spaces_for_tab=4):
    if PY3:
        lines = ElementTree.tostring(elem, encoding="unicode").splitlines()
    else:
        # noinspection PyCompatibility,PyUnresolvedReferences
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


def etree_get_namespaces(source):
    """
    Extracts namespaces with related prefixes from the XML source. For
    each prefix takes the first entry. If source is an ElementTree node
    returns the nsmap attribute (works only for lxml).

    :param source: A string containing the XML document or a file path 
    or a file like object or an etree Element (lxml).
    :return: A dictionary for mapping namespace prefixes to full URI.
    """
    try:
        nsmap = {}
        try:
            for event, node in etree_iterparse(StringIO(source), events=('start-ns',)):
                if node[0] not in nsmap:
                    nsmap[node[0]] = node[1]
        except ElementTree.ParseError:
            with open(source) as f:
                for event, node in etree_iterparse(f, events=('start-ns', )):
                    if node[0] not in nsmap:
                        nsmap[node[0]] = node[1]
        return nsmap
    except (TypeError, ElementTree.ParseError):
        try:
            if hasattr(source, 'getroot'):
                return {k if k is not None else '': v for k, v in source.getroot().nsmap.items()}
            else:
                return {k if k is not None else '': v for k, v in source.nsmap.items()}
        except (AttributeError, TypeError):
            return {}


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


def etree_getpath(elem, root):
    """
    Returns the relative XPath path from *root* to descendant *elem* element.

    :param elem: Descendant element.
    :param root: Root element.
    :return: A path string or `None` if *elem* is not a descendant of *root*.
    """
    for e, path in etree_iterpath(root, tag=elem.tag):
        if e is elem:
            return path


def etree_child_index(elem, child):
    """Return the index or raise ValueError if it is not a *child* of *elem*."""
    for index in range(len(elem)):
        if elem[index] is child:
            return index
    raise XMLSchemaValueError("%r is not a child of %r" % (child, elem))
