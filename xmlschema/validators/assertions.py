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
from elementpath import XPath2Parser, XPathContext, ElementPathError
from elementpath.datatypes import XSD_BUILTIN_TYPES

from ..qnames import XSD_ASSERT
from ..xpath import ElementPathMixin, XMLSchemaProxy

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent


class XsdAssert(XsdComponent, ElementPathMixin):
    """
    Class for XSD *assert* constraint definitions.

    ..  <assert
          id = ID
          test = an XPath expression
          xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </assert>
    """
    _ADMITTED_TAGS = {XSD_ASSERT}
    token = None
    parser = None
    path = 'true()'

    def __init__(self, elem, schema, parent, base_type):
        self.base_type = base_type
        super(XsdAssert, self).__init__(elem, schema, parent)
        ElementPathMixin.__init__(self)

    def __repr__(self):
        return '%s(test=%r)' % (self.__class__.__name__, self.path)

    def _parse(self):
        super(XsdAssert, self)._parse()
        if self.base_type.is_simple():
            self.parse_error("base_type=%r is not a complexType definition" % self.base_type)
        else:
            try:
                self.path = self.elem.attrib['test'].strip()
            except KeyError as err:
                self.parse_error(str(err), elem=self.elem)

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace

    @property
    def built(self):
        return self.token is not None and (self.base_type.parent is None or self.base_type.built)

    def parse_xpath_test(self):
        if not self.base_type.has_simple_content():
            variables = {'value': XSD_BUILTIN_TYPES['anyType'].value}
        else:
            try:
                builtin_type_name = self.base_type.content_type.primitive_type.local_name
            except AttributeError:
                variables = {'value': XSD_BUILTIN_TYPES['anySimpleType'].value}
            else:
                variables = {'value': XSD_BUILTIN_TYPES[builtin_type_name].value}

        self.parser = XPath2Parser(
            namespaces=self.namespaces,
            variables=variables,
            strict=False,
            default_namespace=self.xpath_default_namespace,
            schema=XMLSchemaProxy(self.schema, self)
        )

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.parse_error(err, elem=self.elem)
            self.token = self.parser.parse('true()')

    def __call__(self, elem, value=None, source=None, namespaces=None, **kwargs):
        if value is not None:
            self.parser.variables['value'] = self.base_type.text_decode(value)
        if not self.parser.is_schema_bound():
            self.parser.schema.bind_parser(self.parser)

        if source is None:
            context = XPathContext(root=elem)
        else:
            context = XPathContext(root=source.root, item=elem)

        default_namespace = self.parser.namespaces['']
        if namespaces and '' in namespaces:
            self.parser.namespaces[''] = namespaces['']

        try:
            if not self.token.evaluate(context.copy()):
                msg = "expression is not true with test path %r."
                yield XMLSchemaValidationError(self, obj=elem, reason=msg % self.path)
        except ElementPathError as err:
            yield XMLSchemaValidationError(self, obj=elem, reason=str(err))

        self.parser.namespaces[''] = default_namespace

    # For implementing ElementPathMixin
    def __iter__(self):
        if not self.parent.has_simple_content():
            for e in self.parent.content_type.iter_elements():
                yield e

    @property
    def attrib(self):
        return self.parent.attributes

    @property
    def type(self):
        return self.parent

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)
