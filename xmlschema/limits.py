#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""Package protection limits. Values can be changed after import to set different limits."""
import sys
from importlib import import_module
from types import ModuleType
from typing import Any

from xmlschema.translation import gettext as _
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError


class LimitsModule(ModuleType):
    def __setattr__(self, attr: str, value: Any) -> None:
        if attr not in ('MAX_MODEL_DEPTH', 'MAX_SCHEMA_SOURCES',
                        'MAX_XML_DEPTH', 'MAX_XML_ELEMENTS'):
            pass
        elif not isinstance(value, int):
            raise XMLSchemaTypeError(_('Value {!r} is not an int').format(value))
        elif attr == 'MAX_MODEL_DEPTH':
            if value < 5:
                raise XMLSchemaValueError(_('{} limit must be at least 5').format(attr))
            module = import_module('xmlschema.validators.models')
            setattr(module, f'_{attr}', value)
            module = import_module('xmlschema.validators.groups')
            setattr(module, f'_{attr}', value)
        elif attr == 'MAX_SCHEMA_SOURCES':
            if value < 10:
                raise XMLSchemaValueError(_('{} limit must be at least 10').format(attr))
            module = import_module('xmlschema.validators.xsd_globals')
            setattr(module, f'_{attr}', value)
        elif value < 1:
            raise XMLSchemaValueError(_('{} limit must be at least 1').format(attr))
        else:
            module = import_module('xmlschema.resources.xml_loader')
            setattr(module, f'_{attr}', value)

        super().__setattr__(attr, value)


sys.modules[__name__].__class__ = LimitsModule


MAX_MODEL_DEPTH = 15
"""
Maximum XSD model group depth. An `XMLSchemaModelDepthError` is raised if
this limit is exceeded.
"""

MAX_SCHEMA_SOURCES = 1000
"""
Maximum number of XSD schema sources loadable by each `XsdGlobals` instance.
An `XMLSchemaValidatorError` is raised if this limit is exceeded.
"""

MAX_XML_DEPTH = 1000
"""
Maximum depth of XML data. An `XMLResourceExceeded` is raised if this limit is exceeded.
The default value is related limits.MAX_XML_DEPTH effective value.
"""

MAX_XML_ELEMENTS = 10 ** 5
"""
Maximum number of XML elements allowed in a XML document. An `XMLResourceExceeded`
is raised if this limit is exceeded. Not affects lazy resources.
"""
