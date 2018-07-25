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
from abc import abstractmethod
from collections import Sequence
from elementpath import XPath2Parser, XPathContext


class ElementPathContext(XPathContext):

    def _iter_descendants(self):
        def iter_descendants():
            elem = self.item
            yield elem
            if elem.text is not None:
                self.item = elem.text
                yield self.item
            if len(elem):
                self.size = len(elem)
                for self.position, self.item in enumerate(elem):
                    if getattr(self.item, 'ref', None) is not None:
                        yield self.item
                    else:
                        sentinel_item = None
                        for item in iter_descendants():
                            if sentinel_item is None:
                                sentinel_item = item
                            elif sentinel_item is item:
                                break
                            yield item

        yielded_items = []
        for obj in iter_descendants():
            if obj in yielded_items:
                continue
            else:
                yielded_items.append(obj)
                yield obj

    def _iter_context(self):
        def iter_context():
            elem = self.item
            yield elem
            if elem.text is not None:
                self.item = elem.text
                yield self.item

            for item in elem.attrib.items():
                self.item = item
                yield item

            if len(elem):
                self.size = len(elem)
                for self.position, self.item in enumerate(elem):
                    if getattr(self.item, 'ref', None) is not None:
                        yield self.item
                    else:
                        sentinel_item = None
                        for item in iter_context():
                            if sentinel_item is None:
                                sentinel_item = item
                            elif sentinel_item is item:
                                break
                            yield item

        yielded_items = []
        for obj in iter_context():
            if obj in yielded_items:
                continue
            else:
                yielded_items.append(obj)
                yield obj


class ElementPathMixin(Sequence):
    """
    Mixin abstract class for enabling the XPath API.
    """
    _attrib = {}
    text = None
    tail = None

    @property
    def tag(self):
        return getattr(self, 'name')

    @property
    def attrib(self):
        return getattr(self, 'attributes', self._attrib)

    def get(self, key, default=None):
        return self.attrib.get(key, default)

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
        namespaces = self.xpath_namespaces if namespaces is None else namespaces
        parser = XPath2Parser(namespaces, strict=False)
        root_token = parser.parse(path)
        context = ElementPathContext(self)
        return root_token.select(context)

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
        namespaces = self.xpath_namespaces if namespaces is None else namespaces
        parser = XPath2Parser(namespaces, strict=False)
        root_token = parser.parse(path)
        context = ElementPathContext(self)
        return next(root_token.select(context), None)

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
        namespaces = self.xpath_namespaces if namespaces is None else namespaces
        parser = XPath2Parser(namespaces, strict=False)
        root_token = parser.parse(path)
        context = ElementPathContext(self)
        return root_token.get_results(context)

    @property
    def xpath_namespaces(self):
        if hasattr(self, 'namespaces'):
            namespaces = {k: v for k, v in self.namespaces.items() if k}
            xpath_default_namespace = getattr(self, 'xpath_default_namespace', None)
            if xpath_default_namespace is not None:
                namespaces[''] = xpath_default_namespace
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

    @abstractmethod
    def __iter__(self):
        pass

    @abstractmethod
    def iter(self, tag=None):
        pass

    @abstractmethod
    def iterchildren(self, tag=None):
        pass
