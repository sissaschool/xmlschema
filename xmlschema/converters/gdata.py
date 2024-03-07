#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Mikhail Razgovorov <1338833@gmail.com>
#
from typing import TYPE_CHECKING, Any, Optional, List, Dict, Type

from .badgerfish import BadgerFishConverter
from ..aliases import NamespacesType

if TYPE_CHECKING:
    pass


class GData(BadgerFishConverter):
    """
    XML Schema based converter class for Badgerfish convention.

    ref: http://www.sklar.com/badgerfish/
    ref: http://badgerfish.ning.com/

    :param namespaces: Map from namespace prefixes to URI.
    :param dict_class: Dictionary class to use for decoded data. Default is `dict`.
    :param list_class: List class to use for decoded data. Default is `list`.
    """
    __slots__ = ()

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 dict_class: Optional[Type[Dict[str, Any]]] = None,
                 list_class: Optional[Type[List[Any]]] = None,
                 **kwargs: Any) -> None:
        kwargs.update(attr_prefix='', text_key='$t', cdata_prefix='$')
        super(BadgerFishConverter, self).__init__(
            namespaces, dict_class, list_class, **kwargs
        )
