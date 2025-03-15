#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from typing import Any, Optional, Type, Union

from xmlschema.exceptions import XMLSchemaTypeError
from xmlschema.translation import gettext as _

from .base import ElementData, XMLSchemaConverter
from .unordered import UnorderedConverter
from .parker import ParkerConverter
from .badgerfish import BadgerFishConverter
from .gdata import GDataConverter
from .abdera import AbderaConverter
from .jsonml import JsonMLConverter
from .columnar import ColumnarConverter

__all__ = ['XMLSchemaConverter', 'UnorderedConverter', 'ParkerConverter',
           'BadgerFishConverter', 'AbderaConverter', 'JsonMLConverter',
           'ColumnarConverter', 'ElementData', 'GDataConverter',
           'ConverterType', 'check_converter_argument', 'get_converter']


ConverterType = Union[Type[XMLSchemaConverter], XMLSchemaConverter]


def check_converter_argument(converter: ConverterType) -> None:
    if converter is not None and \
            (not isinstance(converter, type) or not issubclass(converter, XMLSchemaConverter)) \
            and not isinstance(converter, XMLSchemaConverter):
        msg = _("'converter' argument must be a {0!r} subclass or instance: {1!r}")
        raise XMLSchemaTypeError(msg.format(XMLSchemaConverter, converter))


def get_converter(converter: Optional[ConverterType] = None,
                  **kwargs: Any) -> XMLSchemaConverter:
    """
    Returns a new converter instance.

    :param converter: can be a converter class or instance. If it's an instance \
    the new instance is copied from it and configured with the provided arguments.
    :param kwargs: optional arguments for initialize the converter instance.
    :return: a converter instance.
    """
    if converter is None:
        return XMLSchemaConverter(**kwargs)

    check_converter_argument(converter)
    if isinstance(converter, XMLSchemaConverter):
        return converter.copy(keep_namespaces=False, **kwargs)
    else:
        assert issubclass(converter, XMLSchemaConverter)
        return converter(**kwargs)
