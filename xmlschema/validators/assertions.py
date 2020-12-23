#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import threading
from elementpath import XPath2Parser, XPathContext, ElementPathError

from ..names import XSD_ASSERT
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
        self._assert_xpath_lock = threading.Lock()  # Lock for assertion XPath operations
        super(XsdAssert, self).__init__(elem, schema, parent)
        ElementPathMixin.__init__(self)

    def __repr__(self):
        if len(self.path) < 40:
            return '%s(test=%r)' % (self.__class__.__name__, self.path)
        else:
            return '%s(test=%r)' % (self.__class__.__name__, self.path[:37] + '...')

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('_assert_xpath_lock', None)
        state.pop('_xpath_lock', None)
        state.pop('_xpath_parser', None)
        state.pop('xpath_tokens', None)  # For schema objects
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._xpath_lock = threading.Lock()
        self._assert_xpath_lock = threading.Lock()

    def _parse(self):
        super(XsdAssert, self)._parse()
        if self.base_type.is_simple():
            self.parse_error("base_type=%r is not a complexType definition" % self.base_type)
        else:
            try:
                self.path = self.elem.attrib['test'].strip()
            except KeyError as err:
                self.parse_error(err)

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace

    @property
    def built(self):
        return self.token is not None and (self.base_type.parent is None or self.base_type.built)

    def build(self):
        self.parser = XPath2Parser(
            namespaces=self.namespaces,
            variable_types={'value': self.base_type.sequence_type},
            strict=False,
            default_namespace=self.xpath_default_namespace,
            schema=XMLSchemaProxy(self.schema, self)
        )

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.parse_error(err)
            self.token = self.parser.parse('true()')
        finally:
            self.parser.variable_types.clear()

    def __call__(self, elem, value=None, namespaces=None, source=None, **kwargs):
        with self._xpath_lock:
            if not self.parser.is_schema_bound():
                self.parser.schema.bind_parser(self.parser)

        variables = {'value': None if value is None else self.base_type.text_decode(value)}
        if source is not None:
            context = XPathContext(source.root, namespaces=namespaces,
                                   item=elem, variables=variables)
        else:
            # If validated from a component (could not work with rooted XPath expressions)
            context = XPathContext(elem, variables=variables)

        try:
            if not self.token.evaluate(context):
                yield XMLSchemaValidationError(self, obj=elem, reason="assertion test if false")
        except ElementPathError as err:
            yield XMLSchemaValidationError(self, obj=elem, reason=str(err))

    # For implementing ElementPathMixin
    def __iter__(self):
        if not self.parent.has_simple_content():
            yield from self.parent.content.iter_elements()

    @property
    def attrib(self):
        return self.parent.attributes

    @property
    def type(self):
        return self.parent

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)
