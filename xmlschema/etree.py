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

from .compat import PY3
from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .namespaces import XSLT_NAMESPACE, HFP_NAMESPACE, VC_NAMESPACE, get_namespace
from .qnames import get_qname
from .xpath import ElementPathMixin

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
    lxml_etree_parse = None
    lxml_etree_element = None
    lxml_etree_comment = None
    lxml_etree_register_namespace = None


def is_etree_element(elem):
    """More safer test for matching ElementTree elements."""
    return hasattr(elem, 'tag') and not isinstance(elem, ElementPathMixin)


def etree_tostring(elem, indent='', max_lines=None, spaces_for_tab=4, xml_declaration=False):
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
    lines[-1] = u'  %s' % lines[-1].strip()

    if max_lines is not None:
        if indent:
            xml_text = u'\n'.join([indent + line for line in lines[:max_lines]])
        else:
            xml_text = u'\n'.join(lines[:max_lines])
        if len(lines) > max_lines + 2:
            xml_text += u'\n%s    ...\n%s%s' % (indent, indent, lines[-1])
        elif len(lines) > max_lines:
            xml_text += u'\n%s%s\n%s%s' % (indent, lines[-2], indent, lines[-1])
    elif indent:
        xml_text = u'\n'.join([indent + line for line in lines])
    else:
        xml_text = u'\n'.join(lines)

    if spaces_for_tab:
        xml_text = xml_text.replace(u'\t', u' ' * spaces_for_tab)

    if xml_declaration:
        xml_text = indent + u'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_text

    return xml_text


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


def etree_last_child(elem):
    """Returns the last child of the element, ignoring children that are lxml comments."""
    for child in reversed(elem):
        if not callable(child.tag):
            return child


def etree_child_index(elem, child):
    """Return the index or raise ValueError if it is not a *child* of *elem*."""
    for index in range(len(elem)):
        if elem[index] is child:
            return index
    raise XMLSchemaValueError("%r is not a child of %r" % (child, elem))


def etree_elements_assert_equal(elem, other, strict=True, skip_comments=True):
    """
    Tests the equality of two XML Element trees.

    :param elem: the master Element tree, reference for namespace mapping.
    :param other: the other Element tree that has to be compared.
    :param strict: asserts strictly equality. `True` for default.
    :param skip_comments: Skip comments for e
    :raise: an AssertionError containing information about first difference encountered.
    """
    _REGEX_SPACES = re.compile(r'\s+')

    other_elements = iter(other.iter())
    namespace = ''
    for e1 in elem.iter():
        if skip_comments and e1.tag is lxml_etree_comment:
            continue

        try:
            e2 = next(other_elements)
        except StopIteration:
            assert False, "Second tree ends before the first: %r." % e1

        if strict or e1 is elem:
            assert e1.tag == e2.tag, "%r != %r: tags differ." % (e1, e2)
        else:
            namespace = get_namespace(e1.tag) or namespace
            assert get_qname(namespace, e1.tag) == get_qname(namespace, e1.tag), "%r != %r: tags differ." % (e1, e2)

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

    try:
        e2 = next(other_elements)
    except StopIteration:
        pass
    else:
        assert False, "First tree ends before the second: %r." % e2
