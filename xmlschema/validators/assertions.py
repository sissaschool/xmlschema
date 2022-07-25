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
from typing import TYPE_CHECKING, cast, Any, Dict, Iterator, Optional, Union
from elementpath import ElementPathError, XPath2Parser, XPathContext, XPathToken, \
    LazyElementNode, SchemaElementNode, build_schema_node_tree

from ..names import XSD_ASSERT
from ..aliases import ElementType, SchemaType, SchemaElementType, NamespacesType
from ..translation import gettext as _
from ..xpath import XsdSchemaProtocol, XsdElementProtocol, ElementPathMixin, XMLSchemaProxy

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaValidationError
from .xsdbase import XsdComponent
from .groups import XsdGroup


if TYPE_CHECKING:
    from ..resources import XMLResource
    from .attributes import XsdAttributeGroup
    from .complex_types import XsdComplexType
    from .elements import XsdElement
    from .wildcards import XsdAnyElement


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
    _ADMITTED_TAGS = {XSD_ASSERT}
    token: Optional[XPathToken] = None
    parser: Optional[XPath2Parser] = None
    path = 'true()'

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: 'XsdComplexType',
                 base_type: 'XsdComplexType') -> None:

        self._xpath_lock = threading.Lock()
        self.base_type = base_type
        super(XsdAssert, self).__init__(elem, schema, parent)

    def __repr__(self) -> str:
        if len(self.path) < 40:
            return '%s(test=%r)' % (self.__class__.__name__, self.path)
        else:
            return '%s(test=%r)' % (self.__class__.__name__, self.path[:37] + '...')

    def __getstate__(self) -> Dict[str, Any]:
        state = self.__dict__.copy()
        state.pop('_xpath_lock', None)
        return state

    def __setstate__(self, state: Any) -> None:
        self.__dict__.update(state)
        self._xpath_lock = threading.Lock()

    def _parse(self) -> None:
        if self.base_type.is_simple():
            msg = _("base_type={!r} is not a complexType definition")
            self.parse_error(msg.format(self.base_type))
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
    def built(self) -> bool:
        return self.parser is not None and self.token is not None

    def build(self) -> None:
        # Assert requires a schema bound parser because select
        # is on XML elements and with XSD type decoded values
        self.parser = XPath2Parser(
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
        finally:
            if self.parser.variable_types:
                self.parser.variable_types.clear()

    def __call__(self, elem: ElementType,
                 value: Any = None,
                 namespaces: Optional[NamespacesType] = None,
                 source: Optional['XMLResource'] = None,
                 **kwargs: Any) -> Iterator[XMLSchemaValidationError]:

        if self.parser is None or self.token is None:
            raise XMLSchemaNotBuiltError(self, 'schema bound parser not set')

        with self._xpath_lock:
            if not self.parser.is_schema_bound() and self.parser.schema:
                self.parser.schema.bind_parser(self.parser)

        if namespaces is None or isinstance(namespaces, dict):
            _namespaces = namespaces
        else:
            _namespaces = dict(namespaces)

        variables = {'value': None if value is None else self.base_type.text_decode(value)}
        if source is not None:
            context = XPathContext(
                root=source.get_xpath_node(elem),
                namespaces=_namespaces,
                variables=variables
            )
        else:
            # If validated from a component (could not work with rooted XPath expressions)
            context = XPathContext(LazyElementNode(elem), variables=variables)

        try:
            if not self.token.evaluate(context):
                yield XMLSchemaValidationError(self, obj=elem, reason="assertion test if false")
        except ElementPathError as err:
            yield XMLSchemaValidationError(self, obj=elem, reason=str(err))

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
        return XMLSchemaProxy(
            schema=cast(XsdSchemaProtocol, self.schema),
            base_element=cast(XsdElementProtocol, self)
        )

    @property
    def xpath_node(self) -> SchemaElementNode:
        schema_node = self.schema.xpath_node
        node = schema_node.get_element_node(cast(XsdElementProtocol, self))
        if isinstance(node, SchemaElementNode):
            return node

        return build_schema_node_tree(
            root=cast(XsdElementProtocol, self),
            elements=schema_node.elements,
            global_elements=schema_node.children,
        )
