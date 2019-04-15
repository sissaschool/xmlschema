# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
XML Schema validators subpackage.
"""
from .exceptions import XMLSchemaValidatorError, XMLSchemaParseError, XMLSchemaModelError, \
    XMLSchemaModelDepthError, XMLSchemaValidationError, XMLSchemaDecodeError, XMLSchemaEncodeError, \
    XMLSchemaNotBuiltError, XMLSchemaChildrenValidationError, XMLSchemaIncludeWarning, XMLSchemaImportWarning

from .xsdbase import XsdValidator, XsdComponent, XsdAnnotation, XsdType, ValidationMixin, ParticleMixin

from .assertions import XsdAssert
from .notations import XsdNotation
from .identities import XsdSelector, XsdFieldSelector, XsdIdentity, XsdKeyref, XsdKey, XsdUnique
from .facets import XsdPatternFacets, XsdEnumerationFacets
from .wildcards import XsdAnyElement, Xsd11AnyElement, XsdAnyAttribute, Xsd11AnyAttribute
from .attributes import XsdAttribute, Xsd11Attribute, XsdAttributeGroup
from .simple_types import xsd_simple_type_factory, XsdSimpleType, XsdAtomic, XsdAtomicBuiltin, \
    XsdAtomicRestriction, Xsd11AtomicRestriction, XsdList, XsdUnion
from .complex_types import XsdComplexType, Xsd11ComplexType
from .models import ModelGroup, ModelVisitor
from .groups import XsdGroup, Xsd11Group
from .elements import XsdElement, Xsd11Element

from .globals_ import XsdGlobals
from .schema import XMLSchemaMeta, XMLSchemaBase, XMLSchema, XMLSchema10, XMLSchema11
