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
import elementpath
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
        self._assert_xpath_lock = threading.Lock()  # Lock for assertion XPath operations
        super(XsdAssert, self).__init__(elem, schema, parent)
        ElementPathMixin.__init__(self)

    def __repr__(self):
        return '%s(test=%r)' % (self.__class__.__name__, self.path)

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
                self.parse_error(str(err), elem=self.elem)

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace

    @property
    def built(self):
        return self.token is not None and (self.base_type.parent is None or self.base_type.built)

    def build(self):
        if not self.base_type.has_simple_content():
            builtin_type = XSD_BUILTIN_TYPES['anyType']
        else:
            try:
                builtin_type_name = self.base_type.content.primitive_type.local_name
            except AttributeError:
                builtin_type = XSD_BUILTIN_TYPES['anySimpleType']
            else:
                builtin_type = XSD_BUILTIN_TYPES[builtin_type_name]

        # Patch for compatibility with next elementpath minor release (v1.5)
        # where parser variables will be filled with types.
        if elementpath.__version__.startswith('1.4.'):
            variables = {'value': builtin_type.value}
        else:
            variables = {'value': builtin_type}

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
        finally:
            self.parser.variables.clear()

    def __call__(self, elem, value=None, source=None, **kwargs):
        with self._xpath_lock:
            if not self.parser.is_schema_bound():
                self.parser.schema.bind_parser(self.parser)

        if value is not None:
            variables = {'value': self.base_type.text_decode(value)}
        else:
            variables = {'value': ''}

        if source is not None:
            context = XPathContext(root=source.root, item=elem, variables=variables)
        else:
            # If validated from a component (could not work with rooted XPath expressions)
            context = XPathContext(root=elem, variables=variables)

        try:
            if not self.token.evaluate(context):
                msg = "expression is not true with test path %r."
                yield XMLSchemaValidationError(self, obj=elem, reason=msg % self.path)
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
