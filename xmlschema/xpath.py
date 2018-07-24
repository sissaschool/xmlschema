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
This module defines a mixin class for enabling XPath on schemas.
"""
from collections import Sequence
from elementpath import select, iter_select


class ElementPathMixin(Sequence):
    """
    Mixin class that defines the ElementPath API for XSD classes (schemas and elements).
    """
    _attrib = {}

    @property
    def tag(self):
        return getattr(self, 'name')

    @property
    def attrib(self):
        return getattr(self, 'attributes', self._attrib)

    def get(self, key, default=None):
        return self.attrib.get(key, default)

    text = None
    tail = None

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

    def __getitem__(self, i):
        try:
            return [e for e in self][i]
        except AttributeError:
            raise IndexError('child index out of range')

    def __reversed__(self):
        return reversed([e for e in self])

    def __len__(self):
        return len([e for e in self])

    def __iter__(self):
        return iter(())

    def iter(self, tag=None):
        return iter(())

    def iterchildren(self, tag=None):
        return iter(())
