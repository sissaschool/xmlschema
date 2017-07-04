# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This subpackage contains classes and constants for XML Schema components.
"""
from .xsdbase import XsdAnnotation, XsdComponent, check_tag, \
    get_xsd_attribute, get_xsd_derivation_attribute, iterchildren_xsd_import, \
    iterchildren_xsd_include, iterchildren_xsd_redefine, iterchildren_by_tag
from .notations import XsdNotation
from .wildcards import XsdAnyElement, XsdAnyAttribute
from .attributes import XsdAttribute, XsdAnyAttribute, XsdAttributeGroup
from .simple_types import (
    xsd_simple_type_factory, XsdSimpleType, XsdAtomic, XsdAtomicBuiltin,
    XsdAtomicRestriction, XsdList, XsdUnion
)
from .complex_types import XsdComplexType
from .groups import XsdGroup
from .elements import XsdElement
from .facets import (
    XSD_FACETS, XSD11_FACETS, STRING_FACETS, BOOLEAN_FACETS, FLOAT_FACETS,
    DECIMAL_FACETS, DATETIME_FACETS, XsdUniqueFacet, XsdPatternsFacet, XsdEnumerationFacet
)
from .builtins import xsd_builtin_types_factory, xsd_build_any_attribute_group, \
    xsd_build_any_content_group
