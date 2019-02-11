# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from __future__ import unicode_literals
from elementpath import XPath2Parser, XPathContext, XMLSchemaProxy, ElementPathSyntaxError

from ..etree import etree_element
from ..qnames import XSD_ASSERT
from ..helpers import get_xpath_default_namespace

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent


class XsdAssertion(XsdComponent):
    """
    Class for XSD 'assert' constraint declaration.

    <assert
      id = ID
      test = an XPath expression
      xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </assert>
    """
    admitted_tags = {XSD_ASSERT}

    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdAssertion, self).__init__(self, elem, schema, parent)

    @property
    def built(self):
        return self.base_type.is_global or self.base_type.built

    def _parse(self):
        super(XsdAssertion, self)._parse()
        self.path, self.root = self._parse_assertion(self.elem)

    def _parse_assertion(self, elem):
        try:
            path = elem.attrib['test']
        except KeyError as err:
            self.parse_error(str(err), elem=elem)
            path = 'true()'

        try:
            default_namespace = get_xpath_default_namespace(elem, self.namespaces[''], self.target_namespace)
        except ValueError as err:
            self.parse_error(str(err), elem=elem)
            parser = XPath2Parser(self.namespaces, strict=False, schema=XMLSchemaProxy(self.schema.meta_schema))
        else:
            parser = XPath2Parser(self.namespaces, strict=False, schema=XMLSchemaProxy(self.schema.meta_schema),
                                  default_namespace=default_namespace)

        try:
            root_token = parser.parse(path)
        except ElementPathSyntaxError as err:
            self.parse_error(err, elem=elem)
            return path, parser.parse('true()')

        primitive_type = self.base_type.primitive_type
        context = XPathContext(root=etree_element('root'), variables={'value': primitive_type.value})
        try:
            root_token.evaluate(context)
        except (TypeError, ValueError) as err:
            self.parse_error(err, elem=elem)
            return path, parser.parse('true()')
        else:
            return path, root_token

    def __call__(self, elem):
        context = XPathContext(root=elem)
        if not self.root.evaluate(context):
            msg = "expression is not true with test path %r."
            yield XMLSchemaValidationError(self, obj=elem, reason=msg % self.path)
