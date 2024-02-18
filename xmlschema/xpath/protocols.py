#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import Any, Dict, runtime_checkable, Optional, Protocol, Type
import threading

from elementpath import protocols, XPathToken, SchemaElementNode

from ..aliases import NamespacesType

###
# FIXME!!: Defined protocols are incorrect, need a fix in elementpath protocols (use generic)


@runtime_checkable
class XsdSchemaProtocol(protocols.XsdSchemaProtocol, Protocol):
    target_namespace: Optional[str]
    namespaces: NamespacesType
    xpath_node: SchemaElementNode
    lock: threading.Lock
    xpath_tokens: Optional[Dict[str, Type[XPathToken]]]


@runtime_checkable
class XsdTypeProtocol(protocols.XsdTypeProtocol, Protocol):
    target_namespace: Optional[str]
    schema: XsdSchemaProtocol

    def encode(self, obj: Any, validation: str = 'strict', **kwargs: Any) -> Any: ...


@runtime_checkable
class XsdElementProtocol(protocols.XsdElementProtocol, Protocol):
    target_namespace: Optional[str]
    schema: XsdSchemaProtocol
    attributes: Dict[str, Any]
    xpath_node: SchemaElementNode
