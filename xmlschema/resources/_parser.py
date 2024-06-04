#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from xml.sax import expatreader  # type: ignore[attr-defined]

from xmlschema.exceptions import XMLResourceForbidden


class SafeExpatParser(expatreader.ExpatParser):  # type: ignore[misc]

    def forbid_entity_declaration(self, name, is_parameter_entity,  # type: ignore
                                  value, base, sysid, pubid, notation_name):
        raise XMLResourceForbidden(f"Entities are forbidden (entity_name={name!r})")

    def forbid_unparsed_entity_declaration(self, name, base,  # type: ignore
                                           sysid, pubid, notation_name):
        raise XMLResourceForbidden(f"Unparsed entities are forbidden (entity_name={name!r})")

    def forbid_external_entity_reference(self, context, base, sysid, pubid):  # type: ignore
        raise XMLResourceForbidden(
            f"External references are forbidden (system_id={sysid!r}, public_id={pubid!r})"
        )  # pragma: no cover

    def reset(self) -> None:
        super().reset()
        self._parser.EntityDeclHandler = self.forbid_entity_declaration
        self._parser.UnparsedEntityDeclHandler = self.forbid_unparsed_entity_declaration
        self._parser.ExternalEntityRefHandler = self.forbid_external_entity_reference
