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
This module contains an XPath parser and other XPath related classes and functions.
"""
from elementpath import select, iter_select, XPath1Parser


def relative_path(path, levels, namespaces=None):
    """
    Return a relative XPath expression from parsed tree.
    
    :param path: An XPath expression.
    :param levels: Number of path levels to remove.
    :param namespaces: is an optional mapping from namespace 
    prefix to full qualified name.
    :return: a string with a relative XPath expression.
    """
    parser = XPath1Parser(namespaces)
    root_token = parser.parse(path)
    path_parts = [t.value for t in root_token.iter()]
    i = 0
    if path_parts[0] == '.':
        i += 1
    if path_parts[i] == '/':
        i += 1
    for value in path_parts[i:]:
        if levels <= 0:
            break
        if value == '/':
            levels -= 1
        i += 1
    return ''.join(path_parts[i:])


class ElementPathMixin(object):
    """
    Mixin class that defines the ElementPath API for XSD classes (schemas and elements).
    """
    @property
    def tag(self):
        return getattr(self, 'name')

    @property
    def attrib(self):
        return getattr(self, 'attributes')

    text = None

    def __len__(self):
        return 1

    def iterfind(self, path, namespaces=None):
        """
        Generates all matching XSD/XML element declarations by path.

        :param path: is an XPath expression that considers the schema as the root element \
        with global elements as its children.
        :param namespaces: is an optional mapping from namespace prefix to full name.
        :return: an iterable yielding all matching declarations in the XSD/XML order.
        """
        if path.startswith('/'):
            path = u'.%s' % path  # Avoid document root positioning
        return iter_select(self, path, namespaces or self.xpath_namespaces, strict=False)

    def find(self, path, namespaces=None):
        """
        Finds the first XSD/XML element or attribute matching the path.

        :param path: is an XPath expression that considers the schema as the root element \
        with global elements as its children.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: The first matching XSD/XML element or attribute or ``None`` if there is not match.
        """
        if path.startswith('/'):
            path = u'.%s' % path
        return next(iter_select(self, path, namespaces or self.xpath_namespaces, strict=False), None)

    def findall(self, path, namespaces=None):
        """
        Finds all matching XSD/XML elements or attributes.

        :param path: is an XPath expression that considers the schema as the root element \
        with global elements as its children.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: a list containing all matching XSD/XML elements or attributes. An empty list \
        is returned if there is no match.
        """
        if path.startswith('/'):
            path = u'.%s' % path
        return select(self, path, namespaces or self.xpath_namespaces, strict=False)

    @property
    def xpath_namespaces(self):
        if hasattr(self, 'namespaces'):
            namespaces = {k: v for k, v in self.namespaces.items() if k}
            if hasattr(self, 'xpath_default_namespace'):
                namespaces[''] = self.xpath_default_namespace
            return namespaces

    def iter(self, name=None):
        raise NotImplementedError

    def iterchildren(self, name=None):
        raise NotImplementedError
