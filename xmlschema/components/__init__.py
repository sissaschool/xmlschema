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
from .xsdbase import (
    check_tag, check_attrs, check_type, check_value, get_xsd_annotation,
    get_xsd_component, iter_xsd_declarations, get_xsd_attribute,
    get_xsd_bool_attribute, get_xsd_int_attribute, XsdAnnotation, XsdComponent
)
from .attributes import XsdAttribute, XsdAnyAttribute, XsdAttributeGroup
from .datatypes import (
    XsdSimpleType, XsdAtomic, XsdAtomicBuiltin, XsdAtomicRestriction, XsdList, XsdUnion
)
from .elements import XsdElement, XsdAnyElement, XsdComplexType, XsdGroup
from .facets import (
    XSD_FACETS, XSD11_FACETS, STRING_FACETS, BOOLEAN_FACETS, FLOAT_FACETS,
    DECIMAL_FACETS, DATETIME_FACETS, XsdUniqueFacet, XsdPatternsFacet, XsdEnumerationFacet
)
from ..exceptions import XMLSchemaParseError


class XsdNotation(XsdComponent):
    """
    Class for XSD 'notation' definitions.

    <notation
      id = ID
      name = NCName
      public = token
      system = anyURI
      {any attributes with non-schema namespace}...>
      Content: (annotation?)
    </notation>
    """
    def __init__(self, name, elem, schema):
        super(XsdNotation, self).__init__(name, elem, schema)
        for key in self._attrib:
            if key not in {'id', 'name', 'public', 'system'}:
                schema.errors.append(XMLSchemaParseError(
                    "wrong attribute %r for notation definition." % key, elem
                ))
        if 'public' not in elem.attrib and 'system' not in elem.attrib:
            schema.errors.append(XMLSchemaParseError(
                "a notation may have 'public' or 'system' attribute.", elem
            ))

    @property
    def public(self):
        return self._attrib.get('public')

    @property
    def system(self):
        return self._attrib.get('system')
