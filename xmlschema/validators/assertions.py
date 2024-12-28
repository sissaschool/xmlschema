#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import warnings
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Optional, Union

from elementpath import ElementPathError, XPathContext, XPathToken, \
    LazyElementNode, SchemaElementNode, build_schema_node_tree

from xmlschema.names import XSD_ASSERT
from xmlschema.aliases import ElementType, SchemaType, SchemaElementType
from xmlschema.translation import gettext as _
from xmlschema.xpath import ElementPathMixin, XMLSchemaProxy

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaAssertPathWarning
from .validation import DecodeContext
from .xsdbase import XsdComponent
from .groups import XsdGroup


if TYPE_CHECKING:
    from elementpath import XPath2Parser
    from elementpath.xpath3 import XPath3Parser
    from .attributes import XsdAttributeGroup
    from .complex_types import XsdComplexType
    from .elements import XsdElement
    from .wildcards import XsdAnyElement

warnings.filterwarnings(action="always", category=XMLSchemaAssertPathWarning)


class XsdAssert(XsdComponent, ElementPathMixin[Union['XsdAssert', SchemaElementType]]):
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
    parent: 'XsdComplexType'
    _ADMITTED_TAGS = XSD_ASSERT,

    __slots__ = (
        'token', 'parser', 'path', 'base_type', 'xpath_default_namespace'
    )

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: 'XsdComplexType',
                 base_type: 'XsdComplexType') -> None:

        self.token: Optional[XPathToken] = None
        self.parser: Optional[Union['XPath2Parser', 'XPath3Parser']] = None
        self.base_type = base_type
        super().__init__(elem, schema, parent)

    def __repr__(self) -> str:
        if len(self.path) < 40:
            return '%s(test=%r)' % (self.__class__.__name__, self.path)
        else:
            return '%s(test=%r)' % (self.__class__.__name__, self.path[:37] + '...')

    def _parse(self) -> None:
        if self.base_type.is_simple():
            msg = _("base_type={!r} is not a complexType definition")
            self.parse_error(msg.format(self.base_type))
            self.path = 'true()'
        else:
            try:
                self.path = self.elem.attrib['test'].strip()
            except KeyError as err:
                self.parse_error(err)
                self.path = 'true()'

        if 'xpathDefaultNamespace' in self.elem.attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace

    @property
    def built(self) -> bool:
        return self.parser is not None and self.token is not None

    def build(self) -> None:
        # Assert requires a schema bound parser because select
        # is on XML elements and with XSD type decoded values
        self.parser = self.schema.maps.config.xpath_parser_class(
            namespaces=self.namespaces,
            variable_types={'value': self.base_type.sequence_type},
            strict=False,
            default_namespace=self.xpath_default_namespace,
            schema=self.xpath_proxy,
        )

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.parse_error(err)
            self.token = self.parser.parse('true()')
        else:
            if any(len(tk) < 2 for tk in self.token.iter('/', '//')):
                msg = (
                    f"The XPath expression of {self} contains absolute location paths "
                    f"/ or //, but an assert XPath tree is rooted at a parentless elem"
                    f"ent so these operators will return empty sequences."
                )
                warnings.warn(msg, category=XMLSchemaAssertPathWarning, stacklevel=4)
        finally:
            if self.parser.variable_types:
                self.parser.variable_types.clear()

    def __call__(self,
                 obj: ElementType,
                 validation: str,
                 context: DecodeContext,
                 value: Any = None) -> None:

        if self.parser is None or self.token is None:
            raise XMLSchemaNotBuiltError(self, 'schema bound parser not set')

        if not self.parser.is_schema_bound() and self.parser.schema:
            self.parser.schema.bind_parser(self.parser)

        if value is not None:
            value = self.base_type.text_decode(value, context=context)

        kwargs: dict[str, Any] = {
            'uri': context.source.url,
            'fragment': True,
            'variables': {'value': value},
        }

        if context.source is not None:
            xpath_context = XPathContext(
                context.source.get_xpath_node(obj), context.namespaces, **kwargs
            )
        else:
            xpath_context = XPathContext(LazyElementNode(obj), **kwargs)

        try:
            if not self.token.evaluate(xpath_context):
                context.validation_error(validation, self, "assertion test is false", obj)
        except ElementPathError as err:
            context.validation_error(validation, self, err, obj)

    # For implementing ElementPathMixin
    def __iter__(self) -> Iterator[Union['XsdElement', 'XsdAnyElement']]:
        if isinstance(self.parent.content, XsdGroup):
            yield from self.parent.content.iter_elements()

    @property
    def attrib(self) -> 'XsdAttributeGroup':
        return self.parent.attributes

    @property
    def type(self) -> 'XsdComplexType':
        return self.parent

    @property
    def xpath_proxy(self) -> 'XMLSchemaProxy':
        return XMLSchemaProxy(self.schema, self)

    @property
    def xpath_node(self) -> SchemaElementNode:
        schema_node = self.schema.xpath_node
        node = schema_node.get_element_node(self)
        if isinstance(node, SchemaElementNode):
            return node

        return build_schema_node_tree(
            root=self,
            uri=schema_node.uri,
            elements=schema_node.elements,
            global_elements=schema_node.children,
        )
