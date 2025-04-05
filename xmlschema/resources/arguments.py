#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import io
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import cast, overload, Any, Optional, Type, TYPE_CHECKING, Union
from urllib.request import OpenerDirector
from xml.etree import ElementTree

from xmlschema.aliases import XMLSourceType, UriMapperType, IterParseType
from xmlschema.exceptions import XMLSchemaValueError
from xmlschema.translation import gettext as _
from xmlschema.utils.etree import is_etree_element, is_etree_document
from xmlschema.utils.streams import is_file_object
from xmlschema.utils.urls import is_url
from xmlschema.utils.descriptors import Argument, ChoiceArgument, ValueArgument

if TYPE_CHECKING:
    from .xml_resource import XMLResource

DEFUSE_MODES = frozenset(('never', 'remote', 'nonlocal', 'always'))
SECURITY_MODES = frozenset(('all', 'remote', 'local', 'sandbox', 'none'))


class SourceArgument(Argument[XMLSourceType]):
    """The XML data source."""

    def __init__(self) -> None:
        super().__init__(
            types=(str, bytes, Path, io.StringIO, io.BytesIO),
            validators=(is_file_object, is_etree_element, is_etree_document)
        )

    def validated_value(self, value: Any) -> XMLSourceType:
        value = super().validated_value(value)
        if is_etree_document(value):
            if value.getroot() is None:
                raise XMLSchemaValueError(_("source XML document is empty"))
        return cast(XMLSourceType, value)


class BaseUrlArgument(Argument[Optional[str]]):
    """The effective base URL used for completing relative locations."""

    def __init__(self) -> None:
        super().__init__((str, bytes, Path))

    @overload
    def __get__(self, instance: None, owner: Type['XMLResource']) \
        -> 'BaseUrlArgument': ...

    @overload
    def __get__(self, instance: 'XMLResource', owner: Type['XMLResource']) \
        -> Optional[str]: ...

    def __get__(self, instance: Optional['XMLResource'], owner: Type['XMLResource']) \
            -> Union['BaseUrlArgument', Optional[str]]:
        if instance is None:
            return self

        if instance.url is not None:
            return os.path.dirname(instance.url)
        return self.validated_value(getattr(instance, self._private_name))

    def validated_value(self, value: Any) -> Optional[str]:
        value = super().validated_value(value)
        if value is None:
            return None
        elif not is_url(value):
            msg = _("invalid value {!r} for argument {!r}")
            raise XMLSchemaValueError(msg.format(value, self._name))
        elif isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            return value.decode()
        else:
            return str(value)


class AllowArgument(ChoiceArgument[str]):
    """The security mode for accessing resource locations."""

    def __init__(self) -> None:
        super().__init__(str, SECURITY_MODES)


class DefuseArgument(ChoiceArgument[str]):
    """When to defuse XML data."""
    def __init__(self) -> None:
        super().__init__(str, DEFUSE_MODES)


class TimeoutArgument(ValueArgument[int]):
    """The timeout in seconds for accessing remote resources."""
    def __init__(self) -> None:
        super().__init__(int, min_value=1)


class LazyArgument(ValueArgument[Union[bool, int]]):
    """Defines if the XML resource is lazy."""
    def __init__(self) -> None:
        super().__init__((bool, int), 0)


class ThinLazyArgument(ValueArgument[bool]):
    """Defines if the resource is lazy and thin."""
    def __init__(self) -> None:
        super().__init__(bool)


class UriMapperArgument(Argument[Optional[UriMapperType]]):
    """The optional URI mapper argument for relocating addressed resources."""
    def __init__(self) -> None:
        super().__init__(MutableMapping, (callable,))


class OpenerArgument(Argument[Optional[OpenerDirector]]):
    def __init__(self) -> None:
        super().__init__(OpenerDirector)


class IterParseArgument(Argument[Optional[IterParseType]]):
    def __init__(self) -> None:
        super().__init__(validators=(callable,))

    def validated_value(self, value: Any) -> IterParseType:
        value = super().validated_value(value)
        if value is not None:
            return cast(IterParseType, value)
        return ElementTree.iterparse
