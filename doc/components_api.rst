.. _xsd-components-api:

******************
XSD Components API
******************

XSD elements
============

.. autoclass:: xmlschema.validators.Xsd11Element
.. autoclass:: xmlschema.validators.XsdElement


XSD attributes
==============

.. autoclass:: xmlschema.validators.Xsd11Attribute
.. autoclass:: xmlschema.validators.XsdAttribute


XSD types
=========

.. autoclass:: xmlschema.validators.XsdType
    :members: is_simple, is_complex, is_atomic, is_empty, is_emptiable, has_simple_content,
        has_mixed_content, is_element_only, is_restriction, is_extension, is_key, is_qname
.. autoclass:: xmlschema.validators.Xsd11ComplexType
.. autoclass:: xmlschema.validators.XsdComplexType
.. autoclass:: xmlschema.validators.XsdSimpleType
.. autoclass:: xmlschema.validators.XsdAtomicBuiltin
.. autoclass:: xmlschema.validators.XsdList
.. autoclass:: xmlschema.validators.Xsd11Union
.. autoclass:: xmlschema.validators.XsdUnion
.. autoclass:: xmlschema.validators.Xsd11AtomicRestriction
.. autoclass:: xmlschema.validators.XsdAtomicRestriction


Attribute and model groups
==========================

.. autoclass:: xmlschema.validators.XsdAttributeGroup
.. autoclass:: xmlschema.validators.Xsd11Group
.. autoclass:: xmlschema.validators.XsdGroup


Wildcards
=========

.. autoclass:: xmlschema.validators.Xsd11AnyElement
.. autoclass:: xmlschema.validators.XsdAnyElement
.. autoclass:: xmlschema.validators.Xsd11AnyAttribute
.. autoclass:: xmlschema.validators.XsdAnyAttribute
.. autoclass:: xmlschema.validators.XsdOpenContent
.. autoclass:: xmlschema.validators.XsdDefaultOpenContent


Identity constraints
====================

.. autoclass:: xmlschema.validators.XsdIdentity
.. autoclass:: xmlschema.validators.XsdSelector
.. autoclass:: xmlschema.validators.XsdFieldSelector
.. autoclass:: xmlschema.validators.Xsd11Unique
.. autoclass:: xmlschema.validators.XsdUnique
.. autoclass:: xmlschema.validators.Xsd11Key
.. autoclass:: xmlschema.validators.XsdKey
.. autoclass:: xmlschema.validators.Xsd11Keyref
.. autoclass:: xmlschema.validators.XsdKeyref


Facets
======

.. autoclass:: xmlschema.validators.XsdFacet
.. autoclass:: xmlschema.validators.XsdWhiteSpaceFacet
.. autoclass:: xmlschema.validators.XsdLengthFacet
.. autoclass:: xmlschema.validators.XsdMinLengthFacet
.. autoclass:: xmlschema.validators.XsdMaxLengthFacet
.. autoclass:: xmlschema.validators.XsdMinInclusiveFacet
.. autoclass:: xmlschema.validators.XsdMinExclusiveFacet
.. autoclass:: xmlschema.validators.XsdMaxInclusiveFacet
.. autoclass:: xmlschema.validators.XsdMaxExclusiveFacet
.. autoclass:: xmlschema.validators.XsdTotalDigitsFacet
.. autoclass:: xmlschema.validators.XsdFractionDigitsFacet
.. autoclass:: xmlschema.validators.XsdExplicitTimezoneFacet
.. autoclass:: xmlschema.validators.XsdAssertionFacet
.. autoclass:: xmlschema.validators.XsdEnumerationFacets
.. autoclass:: xmlschema.validators.XsdPatternFacets


Other XSD components
====================

.. autoclass:: xmlschema.validators.XsdAssert
.. autoclass:: xmlschema.validators.XsdAlternative
.. autoclass:: xmlschema.validators.XsdNotation
.. autoclass:: xmlschema.validators.XsdAnnotation
