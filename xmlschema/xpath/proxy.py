#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import cast, Any, Iterator, Optional, Union, TYPE_CHECKING

from elementpath import XPath2Parser, XPathSchemaContext, AbstractSchemaProxy, \
    SchemaElementNode, LazyElementNode
from elementpath.protocols import XsdTypeProtocol

from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..aliases import SchemaType
from ..names import XSD_NAMESPACE

if TYPE_CHECKING:
    from ..validators import XsdElement, XsdAnyElement, XsdAssert
    from .mixin import XPathElement

    BaseElementType = Union[XsdElement, XsdAnyElement, XPathElement, XsdAssert]
else:
    BaseElementType = Any


class XMLSchemaProxy(AbstractSchemaProxy):
    """XPath schema proxy for the *xmlschema* library."""
    _schema: SchemaType
    _base_element: BaseElementType

    def __init__(self, schema: Optional[SchemaType] = None,
                 base_element: Optional[BaseElementType] = None) -> None:

        if schema is None:
            from xmlschema import XMLSchema10
            schema = getattr(XMLSchema10, 'meta_schema', None)
            assert schema is not None

        super().__init__(schema, base_element)

        if base_element is not None:
            try:
                if base_element.schema is not schema:
                    msg = "{} is not an element of {}"
                    raise XMLSchemaValueError(msg.format(base_element, schema))
            except AttributeError:
                raise XMLSchemaTypeError("%r is not an XsdElement" % base_element)

    def bind_parser(self, parser: XPath2Parser) -> None:
        parser.schema = self
        parser.symbol_table = dict(parser.__class__.symbol_table)

        with self._schema.lock:
            if self._schema.xpath_tokens is None:
                self._schema.xpath_tokens = {
                    xsd_type.name: parser.schema_constructor(xsd_type.name)
                    for xsd_type in self.iter_atomic_types() if xsd_type.name
                }

        parser.symbol_table.update(self._schema.xpath_tokens)

    def get_context(self) -> XPathSchemaContext:
        item: Union[None, SchemaElementNode, LazyElementNode]
        if self._base_element is not None:
            item = self._base_element.xpath_node
        else:
            item = None

        return XPathSchemaContext(
            root=self._schema.xpath_node,
            namespaces=self._schema.namespaces,
            item=item,
        )

    def is_instance(self, obj: Any, type_qname: str) -> bool:
        # FIXME: use elementpath.datatypes for checking atomic datatypes
        xsd_type = self._schema.maps.types[type_qname]
        if isinstance(xsd_type, tuple):  # pragma: no cover
            from ..validators import XMLSchemaNotBuiltError
            schema = xsd_type[1]
            raise XMLSchemaNotBuiltError(schema, f"XSD type {type_qname!r} is not built")

        try:
            xsd_type.encode(obj)
        except ValueError:
            return False
        else:
            return True

    def cast_as(self, obj: Any, type_qname: str) -> Any:
        xsd_type = self._schema.maps.types[type_qname]
        if isinstance(xsd_type, tuple):  # pragma: no cover
            from ..validators import XMLSchemaNotBuiltError
            schema = xsd_type[1]
            raise XMLSchemaNotBuiltError(schema, f"XSD type {type_qname!r} is not built")

        return xsd_type.decode(obj)

    def iter_atomic_types(self) -> Iterator[XsdTypeProtocol]:
        for xsd_type in self._schema.maps.types.values():
            if not isinstance(xsd_type, tuple) and \
                    xsd_type.target_namespace != XSD_NAMESPACE and \
                    hasattr(xsd_type, 'primitive_type'):
                yield cast(XsdTypeProtocol, xsd_type)
