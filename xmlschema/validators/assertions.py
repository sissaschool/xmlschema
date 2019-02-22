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

from ..qnames import XSD_ASSERTION, XSD_ASSERT
from ..helpers import get_xpath_default_namespace
from ..xpath import ElementPathMixin

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent


class XsdAssertion(XsdComponent):
    """
    XSD 1.1 assertion facet for simpleType definitions.

    <assertion
      id = ID
      test = an XPath expression
      xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </assertion>
    """
    admitted_tags = {XSD_ASSERTION}

    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdAssertion, self).__init__(elem, schema, parent)
        if not self.base_type.is_simple() or not self.base_type.is_atomic():
            self.parse_error("base_type={!r} is not a simpleType restriction", elem=self.elem)
            self.path = 'true()'

    @property
    def built(self):
        return self.token is not None and (self.base_type.is_global or self.base_type.built)

    def _parse(self):
        super(XsdAssertion, self)._parse()
        try:
            self.path = self.elem.attrib['test']
        except KeyError as err:
            self.parse_error(str(err), elem=self.elem)
            self.path = 'true()'

        variables= {'value': self.base_type.primitive_type.value}

        try:
            default_namespace = get_xpath_default_namespace(self.elem, self.namespaces[''], self.target_namespace)
        except ValueError as err:
            self.parse_error(str(err), elem=self.elem)
            self.parser = XPath2Parser(self.namespaces, strict=False, variables=variables)
        else:
            self.parser = XPath2Parser(
                self.namespaces, strict=False, default_namespace=default_namespace, variables=variables
            )

        try:
            self.token = self.parser.parse(self.path)
        except (ElementPathSyntaxError, TypeError) as err:
            self.parse_error(err, elem=self.elem)
            self.token = self.parser.parse('true()')

    def __call__(self, value):
        self.parser.variables['value'] = value
        if not self.token.evaluate():
            msg = "value is not true with test path %r."
            yield XMLSchemaValidationError(self, value, reason=msg % self.path)


class XsdAssert(XsdComponent, ElementPathMixin):
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
    token = None

    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdAssert, self).__init__(elem, schema, parent)
        if not self.base_type.is_complex():
            self.parse_error("base_type={!r} is not a complexType definition", elem=self.elem)
            self.path = 'true()'

    def _parse(self):
        super(XsdAssert, self)._parse()
        try:
            self.path = self.elem.attrib['test']
        except KeyError as err:
            self.parse_error(str(err), elem=self.elem)
            self.path = 'true()'

        try:
            default_namespace = get_xpath_default_namespace(self.elem, self.namespaces[''], self.target_namespace)
        except ValueError as err:
            self.parse_error(str(err), elem=self.elem)
            self.parser = XPath2Parser(self.namespaces, strict=False)
        else:
            self.parser = XPath2Parser(self.namespaces, strict=False, default_namespace=default_namespace)

    @property
    def built(self):
        return self.token is not None and (self.base_type.is_global or self.base_type.built)

    def parse(self):
        self.parser.schema = XMLSchemaProxy(self.schema, self)
        try:
            self.token = self.parser.parse(self.path)
        except ElementPathSyntaxError as err:
            self.parse_error(err, elem=self.elem)
            self.token = self.parser.parse('true()')

    def __call__(self, elem):
        # TODO: protect from dynamic errors ...
        context = XPathContext(root=elem)
        if not self.token.evaluate(context):
            msg = "expression is not true with test path %r."
            yield XMLSchemaValidationError(self, obj=elem, reason=msg % self.path)

    # For implementing ElementPathMixin
    def __iter__(self):
        if not self.parent.has_simple_content():
            for e in self.parent.content_type.iter_subelements():
                yield e

    @property
    def attrib(self):
        return self.parent.attributes
