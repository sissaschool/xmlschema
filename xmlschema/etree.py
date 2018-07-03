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
import re

try:
    import lxml.etree as lxml_etree
except ImportError:
    lxml_etree = None

from .compat import PY3, StringIO
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .namespaces import XSLT_NAMESPACE, HFP_NAMESPACE, VC_NAMESPACE

import defusedxml.ElementTree

# Register missing namespaces into imported ElementTree module
ElementTree.register_namespace('xslt', XSLT_NAMESPACE)
ElementTree.register_namespace('hfp', HFP_NAMESPACE)
ElementTree.register_namespace('vc', VC_NAMESPACE)

# Define alias for ElementTree API for internal module imports
etree_parse = ElementTree.parse
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

# Lxml APIs
if lxml_etree is not None:
    lxml_etree_parse = lxml_etree.parse
    lxml_etree_element = lxml_etree.Element
    lxml_etree_comment = lxml_etree.Comment
    lxml_etree_register_namespace = lxml_etree.register_namespace
    lxml_etree_register_namespace('xslt', XSLT_NAMESPACE)
    lxml_etree_register_namespace('hfp', HFP_NAMESPACE)
    lxml_etree_register_namespace('vc', VC_NAMESPACE)
else:
    lxml_etree_parse = lxml_etree.parse
    lxml_etree_element = None
    lxml_etree_comment = None


def etree_tostring(elem, indent='', max_lines=None, spaces_for_tab=4):
    if isinstance(elem, etree_element):
        tostring = ElementTree.tostring
    elif lxml_etree is not None:
        tostring = lxml_etree.tostring
    else:
        raise XMLSchemaTypeError("cannot serialize %r: lxml library not available." % type(elem))

    if PY3:
        lines = tostring(elem, encoding="unicode").splitlines()
    else:
        # noinspection PyCompatibility,PyUnresolvedReferences
        lines = unicode(tostring(elem)).splitlines()
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
    Extracts namespaces with related prefixes from the XML source. If the source is
    an ElementTree node returns the nsmap attribute (works only for lxml).
    If a duplicate prefix declaration is encountered then, if the namespace URI is
    not already mapped with the same or another prefix, adds a different prefix.

    :param source: A string containing the XML document or a file path 
    or a file like object or an ElementTree or Element.
    :return: A dictionary for mapping namespace prefixes to full URI.
    """
    def update_nsmap(prefix, uri):
        if prefix not in nsmap:
            nsmap[prefix] = uri
        elif not any(uri == ns for ns in nsmap.values()):
            if not prefix:
                try:
                    prefix = re.search('(\w+)$', uri.strip()).group()
                except AttributeError:
                    return

            while prefix in nsmap:
                match = re.search('(\d+)$', prefix)
                if not match:
                    prefix += '2'
                else:
                    index = int(match.group()) + 1
                    prefix = prefix[:match.span()[0]] + str(index)
            nsmap[prefix] = uri

    nsmap = {}
    try:
        try:
            for event, node in etree_iterparse(StringIO(source), events=('start-ns',)):
                update_nsmap(*node)
        except ElementTree.ParseError:
            for event, node in etree_iterparse(source, events=('start-ns', )):
                update_nsmap(*node)
    except (TypeError, ElementTree.ParseError):
        try:
            # Can extracts namespace information only from lxml etree structures
            for elem in source.iter():
                for k, v in elem.nsmap.items():
                    update_nsmap(k if k is not None else '', v)
        except (AttributeError, TypeError):
            pass  # Non an lxml's tree or element

    return nsmap


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


def etree_elements_equal(elem, other, strict=True, skip_comments=True):
    try:
        etree_elements_assert_equal(elem, other, strict=strict, skip_comments=skip_comments)
    except AssertionError:
        return False
    else:
        return True


def etree_elements_assert_equal(elem, other, strict=True, skip_comments=True):
    _REGEX_SPACES = re.compile(r'\s+')

    other_elements = iter(other.iter())
    for e1 in elem.iter():
        if skip_comments and e1.tag is lxml_etree_comment:
            continue

        try:
            e2 = next(other_elements)
        except StopIteration:
            assert False, "Second tree ends before the first: %r." % e1

        assert e1.tag == e2.tag, "%r != %r: tags differ." % (e1, e2)

        # Attributes
        if e1.attrib != e2.attrib:
            if strict:
                raise AssertionError("%r != %r: attribute differ: %r != %r." % (e1, e2, e1.attrib, e2.attrib))
            else:
                assert e1.attrib.keys() == e2.attrib.keys(), \
                    "%r != %r: attribute keys differ: %r != %r." % (e1, e2, e1.attrib.keys(), e2.attrib.keys())
                for k in e1.attrib:
                    a1, a2 = e1.attrib[k].strip(), e2.attrib[k].strip()
                    if a1 != a2:
                        try:
                            assert float(a1) == float(a2)
                        except (AssertionError, ValueError, TypeError):
                            raise AssertionError(
                                "%r != %r: attribute %r differ: %r != %r." % (e1, e2, k, a1, a2)
                            )

        # Number of children
        if skip_comments:
            nc1 = len([c for c in e1 if c.tag is not lxml_etree_comment])
            nc2 = len([c for c in e2 if c.tag is not lxml_etree_comment])
        else:
            nc1 = len(e1)
            nc2 = len(e2)
        assert nc1 == nc2, "%r != %r: children number differ: %r != %r." % (e1, e2, nc1, nc2)

        # Text
        if e1.text != e2.text:
            message = "%r != %r: texts differ: %r != %r." % (e1, e2, e1.text, e2.text)
            if strict:
                raise AssertionError(message)
            elif e1.text is None:
                assert not e2.text.strip(), message
            elif e2.text is None:
                assert not e1.text.strip(), message
            elif _REGEX_SPACES.sub(e1.text.strip(), '') != _REGEX_SPACES.sub(e2.text.strip(), ''):
                try:
                    assert float(e1.text.strip()) == float(e2.text.strip())
                except (AssertionError, ValueError, TypeError):
                    raise AssertionError(message)

        # Tail
        if e1.tail != e2.tail:
            message = "%r != %r: tails differ: %r != %r." % (e1, e2, e1.tail, e2.tail)
            if strict:
                raise AssertionError(message)
            elif e1.tail is None:
                assert not e2.tail.strip(), message
            elif e2.text is None:
                assert not e1.tail.strip(), message
            else:
                assert e1.tail.strip() == e2.tail.strip(), message
