#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import Any, Dict, runtime_checkable, Protocol

from elementpath import protocols

XsdTypeProtocol = protocols.XsdTypeProtocol
XsdSchemaProtocol = protocols.XsdSchemaProtocol


@runtime_checkable
class XsdElementProtocol(protocols.XsdElementProtocol, Protocol):
    schema: XsdSchemaProtocol
    attributes: Dict[str, Any]
