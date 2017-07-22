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
This module contains classes for other XML Schema constraints.
"""
from ..exceptions import XMLSchemaParseError
from ..qnames import XSD_UNIQUE_TAG, XSD_KEY_TAG, XSD_KEYREF_TAG, XSD_SELECTOR_TAG, XSD_FIELD_TAG
from ..xpath import XPathParser, XPathSelector, TokenMeta
from .component import XsdAnnotated


class XsdPathSelector(XPathSelector, XsdAnnotated):

    def __init__(self, elem, schema, context):
        self.context = context
        XsdAnnotated.__init__(self, elem, schema)

    def _parse(self):
        super(XsdPathSelector, self)._parse()
        try:
            self.xpath = self.elem.attrib['xpath']
        except KeyError:
            self._parse_error("'xpath' attribute required:", self.elem)
            self.xpath = "*"

        parser = XPathParser(TokenMeta.registry, self.xpath, self.namespaces)
        try:
            token_tree = parser.parse()
        except XMLSchemaParseError as err:
            self._parse_error("invalid XPath expression: %s" % str(err), self.elem)
            self._selector = []
        else:
            self._selector = [f for f in token_tree.iter_selectors()]

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_SELECTOR_TAG, XSD_FIELD_TAG}


class XsdConstraint(XsdAnnotated):

    def __init__(self, elem, schema, context):
        self.context = context
        super(XsdConstraint, self).__init__(elem, schema)

    def _parse(self):
        super(XsdConstraint, self)._parse()
        elem = self.elem
        try:
            self.name = elem.attrib['name']
        except KeyError:
            self._parse_error("missing required attribute 'name'", elem)
            self.name = None

        child = self._parse_component(elem, required=False, strict=False)
        if child is None or child.tag != XSD_SELECTOR_TAG:
            self._parse_error("missing 'selector' declaration.", elem)
            self.selector = None
            skip = 0
        else:
            self.selector = XsdPathSelector(child, self.schema, self.context)
            skip = 1

        self.fields = []
        for child in self._iterparse_components(elem, skip=skip):
            if child.tag == XSD_FIELD_TAG:
                self.fields.append(XsdPathSelector(child, self.schema, self.context))
            else:
                self._parse_error("element %r not allowed here:" % child.tag, elem)

    @property
    def built(self):
        return self.selector.built and all([f.built for f in self.fields])

    @property
    def admitted_tags(self):
        return {XSD_UNIQUE_TAG, XSD_KEY_TAG, XSD_KEYREF_TAG}
