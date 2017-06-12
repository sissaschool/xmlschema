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
This module contains XSD factories for the 'xmlschema' package.
"""
import logging as _logging

from .core import etree_iselement
from .exceptions import XMLSchemaParseError, XMLSchemaValidationError
from .qnames import *
from .builtins import ANY_TYPE, ANY_SIMPLE_TYPE
from .components import (
    check_tag, get_xsd_attribute, get_xsd_component, iter_xsd_declarations,
    XsdComponent, XsdUniqueFacet, XsdPatternsFacet, XsdEnumerationFacet, XsdElement,
    XsdAnyElement, XsdAttribute, XsdAnyAttribute, XsdAttributeGroup, XsdGroup, XsdNotation,
    XsdComplexType, XsdSimpleType, XsdAtomicBuiltin, XsdAtomicRestriction, XsdList, XsdUnion
)

_logger = _logging.getLogger(__name__)


def xsd_factory(xsd_class, *tags):
    """
    Check Element instance passed to a factory and log arguments.

    :param xsd_class: XSD class for the created instances.
    :param tags: Values admitted for Element's tag.
    """
    def make_factory_wrapper(factory_function):
        def xsd_factory_wrapper(elem, schema, instance=None, is_global=False, **kwargs):
            if instance is not None and not isinstance(instance, xsd_class):
                raise XMLSchemaParseError(
                    "instance=%r must be a %r." % (instance, xsd_class), elem
                )
            if is_global and 'name' not in elem.attrib:
                raise XMLSchemaParseError(
                    "a global declaration/definition requires a 'name' attribute.", elem
                )

            try:
                result = factory_function(
                    elem, schema, instance=instance, is_global=is_global, **kwargs
                )
            except XMLSchemaValidationError as err:
                raise XMLSchemaParseError(err.message, elem)
            except XMLSchemaParseError as err:
                schema.errors.append(err)
                if isinstance(err.obj, XsdComponent):
                    if isinstance(err.obj, (XsdAtomicRestriction, XsdUnion, XsdList)):
                        return err.obj
                    else:
                        return err.obj.name, err.obj
                elif etree_iselement(err.obj):
                    # Produce a dummy declaration for prosecuting the parse process
                    name = err.obj.get('name')
                    if issubclass(xsd_class, (XsdAtomicRestriction, XsdUnion, XsdList)):
                        return ANY_SIMPLE_TYPE
                    elif not name:
                        raise
                    elif issubclass(xsd_class, XsdSimpleType):
                        return name, ANY_SIMPLE_TYPE
                    elif issubclass(xsd_class, XsdComplexType):
                        return name, ANY_TYPE
                    elif issubclass(xsd_class, XsdGroup):
                        return name, xsd_class(name)
                    elif issubclass(xsd_class, XsdAttribute):
                        return name, xsd_class(name, xsd_type=ANY_SIMPLE_TYPE)
                    elif issubclass(xsd_class, XsdElement):
                        return name, xsd_class(name, xsd_type=ANY_TYPE)
                    else:
                        raise
            else:
                if instance is not None:
                    if isinstance(result, tuple):
                        if instance.name is not None and instance.name != result[0]:
                            raise XMLSchemaParseError(
                                "name mismatch with instance %r: %r." % (instance, result[0]), elem
                            )
                    if instance.elem is None:
                        instance.elem = elem
                    if instance.schema is None:
                        instance.schema = schema
                return result
            if _logger.getEffectiveLevel() == _logging.DEBUG:
                _logger.debug(
                    "%s: elem.tag=%r, elem.attrib=%r, kwargs.keys()=%r",
                    factory_function.__name__, elem.tag, elem.attrib, kwargs.keys()
                )
                _logger.debug("%s: return %r", factory_function.__name__, locals()['result'])

        return xsd_factory_wrapper
    return make_factory_wrapper


@xsd_factory(XsdSimpleType, XSD_SIMPLE_TYPE_TAG)
def xsd_simple_type_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD simpleType definitions.

    <simpleType
      final = (#all | List of (list | union | restriction))
      id = ID
      name = NCName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (restriction | list | union))
    </simpleType>
    """
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    list_factory = kwargs.get('list_factory', xsd_list_factory)
    union_factory = kwargs.get('union_factory', xsd_union_factory)
    kwargs.pop('is_global', False)

    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None

    # Don't rebuild XSD builtins (3 are instances of XsdList).
    if isinstance(instance, XsdAtomicBuiltin):
        instance.elem = elem
        instance.schema = schema
        return instance.name, instance

    child = get_xsd_component(elem)
    if child.tag == XSD_RESTRICTION_TAG:
        xsd_type = restriction_factory(child, schema, instance, **kwargs)
    elif child.tag == XSD_LIST_TAG:
        xsd_type = list_factory(child, schema, instance, **kwargs)
    elif child.tag == XSD_UNION_TAG:
        xsd_type = union_factory(child, schema, instance, **kwargs)
    else:
        raise XMLSchemaParseError('(restriction|list|union) expected', child)

    xsd_type.name = type_name
    return type_name, xsd_type


@xsd_factory(XsdAtomicRestriction, XSD_RESTRICTION_TAG)
def xsd_restriction_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'restriction' definitions.

    <restriction
      base = QName
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive | 
      maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength | 
      enumeration | whiteSpace | pattern)*))
    </restriction>

    <restriction
      base = QName
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive | 
      maxInclusive | totalDigits | fractionDigits | length | minLength | maxLength | 
      enumeration | whiteSpace | pattern | assertion | explicitTimezone | 
      {any with namespace: ##other})*))
    </restriction>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    base_type = getattr(instance, 'base_type', None)
    facets = {}
    has_attributes = False
    has_simple_type_child = False

    if 'base' in elem.attrib:
        base_qname, namespace = split_reference(elem.attrib['base'], schema.namespaces)
        if base_type is None:
            base_type = schema.maps.lookup_type(base_qname)
        if isinstance(base_type, XsdComplexType) and base_type.admit_simple_restriction():
            if get_xsd_component(elem, strict=False).tag != XSD_SIMPLE_TYPE_TAG:
                # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                raise XMLSchemaParseError(
                    "when a complexType with simpleContent restricts a complexType "
                    "with mixed and with emptiable content then a simpleType child "
                    "declaration is required.", elem
                )

    for child in iter_xsd_declarations(elem):
        if child.tag in (XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
            has_attributes = True  # only if it's a complexType restriction
        elif has_attributes:
            raise XMLSchemaParseError("unexpected tag after attribute declarations", child)
        elif child.tag == XSD_SIMPLE_TYPE_TAG:
            # Case of simpleType declaration inside a restriction
            if has_simple_type_child:
                raise XMLSchemaParseError("duplicated simpleType declaration", child)
            elif base_type is None:
                _, base_type = simple_type_factory(child, schema, base_type, **kwargs)
            else:
                if isinstance(base_type, XsdComplexType) and base_type.admit_simple_restriction():
                    base_type = XsdComplexType(
                        content_type=simple_type_factory(child, schema, **kwargs)[1],
                        name=None,
                        elem=elem,
                        schema=schema,
                        attributes=base_type.attributes,
                        derivation=base_type.derivation,
                        mixed=base_type.mixed
                    )
            has_simple_type_child = True
        elif child.tag not in schema.FACETS:
            raise XMLSchemaParseError("unexpected tag in restriction", child)
        elif child.tag in (XSD_ENUMERATION_TAG, XSD_PATTERN_TAG):
            try:
                facets[child.tag].append(child)
            except KeyError:
                if child.tag == XSD_ENUMERATION_TAG:
                    facets[child.tag] = XsdEnumerationFacet(base_type, child, schema)
                else:
                    facets[child.tag] = XsdPatternsFacet(base_type, child, schema)
        elif child.tag not in facets:
            facets[child.tag] = XsdUniqueFacet(base_type, child, schema)
        else:
            raise XMLSchemaParseError("multiple %r constraint facet" % local_name(child.tag), elem)

    if base_type is None:
        raise XMLSchemaParseError("missing base type in simpleType declaration", elem)

    if instance is not None:
        instance.elem = elem
        instance.schema = base_type.schema
        instance.facets = facets
        return instance
    return XsdAtomicRestriction(base_type, elem=elem, schema=base_type.schema, facets=facets)


@xsd_factory(XsdList, XSD_LIST_TAG)
def xsd_list_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'list' declarations:

    <list
      id = ID
      itemType = QName
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType?)
    </list>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    item_type = getattr(instance, 'item_type', None)

    child = get_xsd_component(elem, required=False)
    if child is not None:
        # Case of a local simpleType declaration inside the list tag
        _, item_type = simple_type_factory(child, schema, item_type, **kwargs)
        if 'itemType' in elem.attrib:
            raise XMLSchemaParseError("ambiguous list type declaration", elem)
    elif 'itemType' in elem.attrib:
        # List tag with itemType attribute that refers to a global type
        item_qname, namespace = split_reference(elem.attrib['itemType'], schema.namespaces)
        if item_type is None:
            item_type = schema.maps.lookup_type(item_qname)
    else:
        raise XMLSchemaParseError("missing list type declaration", elem)

    if instance is not None:
        instance.schema = item_type.schema
        instance.elem = elem
        return instance
    return XsdList(item_type=item_type, elem=elem, schema=item_type.schema)


@xsd_factory(XsdUnion, XSD_UNION_TAG)
def xsd_union_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'union' definitions.

    <union
      id = ID
      memberTypes = List of QName
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType*)
    </union>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)

    member_types = [
        simple_type_factory(child, schema, **kwargs)[1] for child in iter_xsd_declarations(elem)
    ]
    if 'memberTypes' in elem.attrib:
        member_types.extend([
            schema.maps.lookup_type(split_reference(_type, schema.namespaces)[0])
            for _type in elem.attrib['memberTypes'].split()
        ])
    if not member_types:
        raise XMLSchemaParseError("missing union type declarations", elem)

    if instance is not None:
        instance.schema = schema
        instance.elem = elem
        return instance
    return XsdUnion(member_types, elem=elem, schema=schema)


@xsd_factory(XsdAttribute, XSD_ATTRIBUTE_TAG)
def xsd_attribute_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'attribute' declarations.

    <attribute
      default = string
      fixed = string
      form = (qualified | unqualified)
      id = ID
      name = NCName
      ref = QName
      type = QName
      use = (optional | prohibited | required) : optional
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType?)
    </attribute>

    <attribute
      default = string
      fixed = string
      form = (qualified | unqualified)
      id = ID
      name = NCName
      ref = QName
      targetNamespace = anyURI
      type = QName
      use = (optional | prohibited | required) : optional
      inheritable = boolean
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, simpleType?)
    </attribute>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    qualified = elem.attrib.get('form', schema.attribute_form)
    kwargs.pop('is_global', False)

    try:
        name = elem.attrib['name']
    except KeyError:
        # No 'name' attribute, must be a reference
        try:
            attribute_name = split_reference(elem.attrib['ref'], schema.namespaces)[0]
        except KeyError:
            # Missing also the 'ref' attribute
            raise XMLSchemaParseError("missing both 'name' and 'ref' in attribute declaration", elem)
        else:
            xsd_attribute = schema.maps.lookup_attribute(attribute_name)
            return attribute_name, XsdAttribute(
                xsd_type=xsd_attribute.type,
                name=attribute_name,
                elem=elem,
                schema=xsd_attribute.schema,
                qualified=xsd_attribute.qualified
            )
    else:
        attribute_name = get_qname(schema.target_namespace, name)

    xsd_type = getattr(instance, 'type', None)
    xsd_declaration = get_xsd_component(elem, required=False)
    try:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        xsd_type = xsd_type or schema.maps.lookup_type(type_qname)
        if xsd_type.name != type_qname:
            # must implement substitution groups before!?
            # raise XMLSchemaParseError("wrong name for %r: %r." % (xsd_type, type_qname), elem)
            pass
    except KeyError:
        if xsd_declaration is not None:
            # No 'type' attribute in declaration, parse for child local simpleType
            _, xsd_type = simple_type_factory(xsd_declaration, schema, xsd_type, **kwargs)
        else:
            xsd_type = ANY_SIMPLE_TYPE  # Empty declaration means xsdAnySimpleType
    else:
        if xsd_declaration is not None and xsd_declaration.tag == XSD_SIMPLE_TYPE_TAG:
            raise XMLSchemaParseError("ambiguous type declaration for XSD attribute", elem)
        elif xsd_declaration:
            raise XMLSchemaParseError(
                "not allowed element in XSD attribute declaration: {}".format(xsd_declaration[0]),
                elem
            )

    if instance is not None:
        instance.type = xsd_type
        instance.elem = elem
        instance.schema = schema
        instance.qualified = qualified
        return attribute_name, instance
    return attribute_name, XsdAttribute(
        name=attribute_name, xsd_type=xsd_type, elem=elem, schema=schema, qualified=qualified
    )


@xsd_factory(XsdComplexType, XSD_COMPLEX_TYPE_TAG)
def xsd_complex_type_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'complexType' definitions.

    <complexType
      abstract = boolean : false
      block = (#all | List of (extension | restriction))
      final = (#all | List of (extension | restriction))
      id = ID
      mixed = boolean : false
      name = NCName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleContent | complexContent | 
      ((group | all | choice | sequence)?, ((attribute | attributeGroup)*, anyAttribute?))))
    </complexType>

    <complexType
      abstract = boolean : false
      block = (#all | List of (extension | restriction))
      final = (#all | List of (extension | restriction))
      id = ID
      mixed = boolean
      name = NCName
      defaultAttributesApply = boolean : true
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleContent | complexContent | (openContent?, 
      (group | all | choice | sequence)?, ((attribute | attributeGroup)*, anyAttribute?), assert*)))
    </complexType>
    """
    parse_local_groups = kwargs.get('parse_local_groups')
    attribute_group_factory = kwargs.get('attribute_group_factory', xsd_attribute_group_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    kwargs.pop('is_global', False)

    # Get complexType's attributes and content
    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None

    mixed = elem.attrib.get('mixed') in ('true', '1')
    derivation = None
    content_node = get_xsd_component(elem, required=False, strict=False)

    if instance is None:
        content_type = None
        attributes = XsdAttributeGroup(elem=elem, schema=schema)
    else:
        content_type = instance.content_type
        attributes = instance.attributes

    if content_node is None or content_node.tag in (
            XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
        #
        # complexType with empty content
        if content_type is None:
            content_type = XsdGroup(elem=elem, schema=schema, mixed=mixed)
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG):
        #
        # complexType with child elements
        if content_type is None:
            content_type = XsdGroup(elem=content_node, schema=schema, mixed=mixed)

        if parse_local_groups:
            content_type = group_factory(content_node, schema, content_type, mixed=mixed, **kwargs)[1]
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag == XSD_COMPLEX_CONTENT_TAG:
        #
        # complexType with complexContent restriction/extension
        if 'mixed' in content_node.attrib:
            mixed = content_node.attrib['mixed'] in ('true', '1')

        content_spec = get_xsd_component(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)
        derivation = content_spec.tag == XSD_EXTENSION_TAG

        if content_type is None:
            content_type = XsdGroup(elem=content_node, schema=schema, mixed=mixed)

        # Get the base type: raise XMLSchemaLookupError if it's not defined.
        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = schema.maps.lookup_type(base_qname)

        if parse_local_groups and not content_type:
            if base_type != instance and isinstance(base_type.content_type, XsdGroup):
                if not base_type.content_type:
                    complex_type_factory(
                        base_type.elem, base_type.schema, instance=base_type, **kwargs
                    )
                if content_spec.tag == XSD_EXTENSION_TAG:
                    content_type.extend(base_type.content_type)
                content_type.model = base_type.content_type.model
                content_type.mixed = base_type.content_type.mixed

            try:
                content_definition = get_xsd_component(content_spec, strict=False)
            except XMLSchemaParseError:
                pass  # Empty extension
            else:
                if content_definition.tag in (XSD_GROUP_TAG, XSD_CHOICE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG):
                    content_type.model = content_definition.tag
                    xsd_group = group_factory(content_definition, schema, mixed=mixed, **kwargs)[1]
                    if content_spec.tag == XSD_RESTRICTION_TAG:
                        pass  # TODO: Checks if restrictions are effective.
                    content_type.extend(xsd_group)
                    content_type.model = xsd_group.model
                    content_type.mixed = xsd_group.mixed
            finally:
                content_type.parsed = True

        if base_type != instance and isinstance(base_type, XsdComplexType):
            attributes.update(base_type.attributes)
        attributes.update(attribute_group_factory(content_spec, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag == XSD_SIMPLE_CONTENT_TAG:
        if 'mixed' in content_node.attrib:
            raise XMLSchemaParseError("'mixed' attribute not allowed with simpleContent", elem)

        content_spec = get_xsd_component(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = schema.maps.lookup_type(base_qname)

        derivation = content_spec.tag == XSD_EXTENSION_TAG
        if content_spec.tag == XSD_RESTRICTION_TAG:
            content_type = restriction_factory(content_spec, schema, instance=content_type, **kwargs)
        else:
            content_type = base_type

        if hasattr(base_type, 'attributes'):
            attributes.update(base_type.attributes)
        attributes.update(attribute_group_factory(content_spec, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag in (XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
        if content_type is None:
            content_type = XsdGroup(elem=elem, schema=schema, mixed=mixed)
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])
    else:
        raise XMLSchemaParseError(
            "unexpected tag for complexType content: %r " % content_node.tag, elem
        )

    if instance is not None:
        instance.content_type = content_type
        instance.attributes = attributes
        instance.name = type_name
        instance.elem = elem
        instance.schema = schema
        instance.derivation = derivation
        instance.mixed = mixed
        return type_name, instance
    return type_name, XsdComplexType(
        content_type, type_name, elem, schema, attributes, derivation, mixed
    )


@xsd_factory(XsdAttributeGroup, XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG,
             XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG, XSD_ATTRIBUTE_TAG,
             XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_attribute_group_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'attributeGroup' definitions. Used for attributeGroup
    definitions and equivalents in complexType attribute declarations.

    <attributeGroup
      id = ID
      name = NCName
      ref = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, ((attribute | attributeGroup)*, anyAttribute?))
    </attributeGroup>
    """
    attribute_factory = kwargs.get('attribute_factory', xsd_attribute_factory)
    kwargs.pop('is_global', False)
    any_attribute = False

    if elem.tag == XSD_ATTRIBUTE_GROUP_TAG:
        try:
            attribute_group_name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            raise XMLSchemaParseError(
                "an attribute group declaration requires a 'name' attribute.", elem
            )
    else:
        attribute_group_name = None

    if instance is None:
        attribute_group = XsdAttributeGroup(attribute_group_name, elem, schema)
    else:
        attribute_group = instance

    for child in iter_xsd_declarations(elem):
        if any_attribute:
            if child.tag == XSD_ANY_ATTRIBUTE_TAG:
                raise XMLSchemaParseError("more anyAttribute declarations in the same attribute group", child)
            else:
                raise XMLSchemaParseError("another declaration after anyAttribute", child)
        elif child.tag == XSD_ANY_ATTRIBUTE_TAG:
            any_attribute = True
            attribute_group.update({None: XsdAnyAttribute(elem=child, schema=schema)})
        elif child.tag == XSD_ATTRIBUTE_TAG:
            attribute_group.update([attribute_factory(child, schema, **kwargs)])
        elif child.tag == XSD_ATTRIBUTE_GROUP_TAG:
            qname, namespace = split_reference(get_xsd_attribute(child, 'ref'), schema.namespaces)
            ref_attribute_group = schema.maps.lookup_attribute_group(qname)
            attribute_group.update(ref_attribute_group.items())
        elif attribute_group.name is not None:
            raise XMLSchemaParseError("(attribute | attributeGroup) expected, found", child)
    return attribute_group_name, attribute_group


@xsd_factory(XsdGroup, XSD_COMPLEX_TYPE_TAG, XSD_GROUP_TAG,
             XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_group_factory(elem, schema, instance=None, is_global=False, **kwargs):
    """
    Factory for XSD 'group', 'sequence', 'choice', 'all' definitions.

    <group
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      name = NCName
      ref = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (all | choice | sequence)?)
    </group>

    <all
      id = ID
      maxOccurs = 1 : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, element*)
    </all>

    <all
      id = ID
      maxOccurs = (0 | 1) : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | any | group)*)
    </all>
    
    <choice
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </choice>

    <sequence
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </sequence>
    """
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    element_factory = kwargs.get('element_factory', xsd_element_factory)
    mixed = kwargs.pop('mixed', False)

    if elem.tag == XSD_GROUP_TAG:
        # Model group with 'name' or 'ref'
        name = elem.attrib.get('name')
        ref = elem.attrib.get('ref')
        if name is None:
            if ref is not None:
                group_name, namespace = split_reference(ref, schema.namespaces)
                xsd_group = schema.maps.lookup_group(group_name)
                return group_name, XsdGroup(
                    name=xsd_group.name,
                    elem=elem,
                    schema=schema,
                    model=xsd_group.model,
                    mixed=mixed,
                    initlist=list(xsd_group)
                )
            else:
                raise XMLSchemaParseError("missing both attributes 'name' and 'ref'", elem)
        elif ref is None:
            group_name = get_qname(schema.target_namespace, name)
            content_model = get_xsd_component(elem)
        else:
            raise XMLSchemaParseError("found both attributes 'name' and 'ref'", elem)
    else:
        # Local group (SEQUENCE|ALL|CHOICE)
        content_model = elem
        group_name = None

    check_tag(content_model, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_GROUP_TAG)
    if instance is None:
        xsd_group = XsdGroup(
            name=group_name, elem=elem, schema=schema, model=content_model.tag, mixed=mixed
        )
    else:
        instance.elem = elem
        instance.schema = schema
        instance.model = content_model.tag
        instance.mixed = mixed
        xsd_group = instance

    if not xsd_group or is_global:
        for child in iter_xsd_declarations(content_model):
            if child.tag == XSD_ELEMENT_TAG:
                _, xsd_element = element_factory(child, schema, **kwargs)
                xsd_group.append(xsd_element)
            elif content_model.tag == XSD_ALL_TAG:
                raise XMLSchemaParseError("'all' tags can contain only elements.", elem)
            elif child.tag == XSD_ANY_TAG:
                xsd_group.append(XsdAnyElement(child, schema))
            elif child.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
                xsd_group.append(
                    group_factory(child, schema, mixed=mixed, **kwargs)[1]
                )
        xsd_group.elements = [e for e in xsd_group.iter_elements()]
    return group_name, xsd_group


@xsd_factory(XsdElement, XSD_ELEMENT_TAG)
def xsd_element_factory(elem, schema, instance=None, is_global=False, **kwargs):
    """
    Factory for XSD 'element' declarations:

    <element
      abstract = boolean : false
      block = (#all | List of (extension | restriction | substitution))
      default = string
      final = (#all | List of (extension | restriction))
      fixed = string
      form = (qualified | unqualified)
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      name = NCName
      nillable = boolean : false
      ref = QName
      substitutionGroup = QName
      type = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, ((simpleType | complexType)?, (unique | key | keyref)*))
    </element>
        
    <element
      abstract = boolean : false
      block = (#all | List of (extension | restriction | substitution))
      default = string
      final = (#all | List of (extension | restriction))
      fixed = string
      form = (qualified | unqualified)
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      name = NCName
      nillable = boolean : false
      ref = QName
      substitutionGroup = List of QName
      targetNamespace = anyURI
      type = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, ((simpleType | complexType)?, alternative*, (unique | key | keyref)*))
    </element>
    """
    element_form_default = kwargs.get('element_form', 'unqualified')
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)

    element_type = getattr(instance, 'type', None)
    qualified = elem.attrib.get('form', element_form_default) == 'qualified'

    # Parse element attributes
    try:
        element_name, namespace = split_reference(elem.attrib['ref'], schema.namespaces)
    except KeyError:
        # No 'ref' attribute ==> 'name' attribute required.
        if 'name' not in elem.attrib:
            raise XMLSchemaParseError("invalid element declaration in XSD schema", elem)
        element_name = get_qname(schema.target_namespace, elem.attrib['name'])
        ref = False
    else:
        # Reference to a global element
        if is_global:
            raise XMLSchemaParseError("an element reference can't be global:", elem)
        msg = "attribute '{}' is not allowed when element reference is used!"
        if 'name' in elem.attrib:
            raise XMLSchemaParseError(msg.format('name'), elem)
        elif 'type' in elem.attrib:
            raise XMLSchemaParseError(msg.format('type'), elem)
        ref = True
        xsd_element = schema.maps.lookup_element(element_name)
        element_type = xsd_element.type

    if instance is not None and instance.name != element_name:
        raise XMLSchemaParseError("wrong name for %r: %r." % (instance, element_name), elem)

    if 'substitutionGroup' in elem.attrib and not is_global:
        raise XMLSchemaParseError("a substitution group declaration must be global:", elem)

    if ref:
        if get_xsd_component(elem, required=False, strict=False) is not None:
            raise XMLSchemaParseError("element reference declaration can't has children:", elem)
    elif 'type' in elem.attrib:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        element_type = schema.maps.lookup_type(type_qname)
    else:
        child = get_xsd_component(elem, required=False, strict=False)
        if child is not None:
            if child.tag == XSD_COMPLEX_TYPE_TAG:
                _, element_type = complex_type_factory(child, schema, element_type, **kwargs)
            elif child.tag == XSD_SIMPLE_TYPE_TAG:
                _, element_type = simple_type_factory(child, schema, element_type, **kwargs)
        else:
            element_type = ANY_TYPE

    if instance is not None:
        instance.type = element_type
        instance.elem = elem
        instance.schema = schema
        instance.qualified = qualified
        instance.ref = ref
        return element_name, instance

    return element_name, XsdElement(
        name=element_name, xsd_type=element_type, elem=elem, schema=schema, qualified=qualified, ref=ref
    )


@xsd_factory(XsdNotation, XSD_NOTATION_TAG)
def xsd_notation_factory(elem, schema, **kwargs):
    """
    Factory for XSD 'notation' definitions.

    <notation
      id = ID
      name = NCName
      public = token
      system = anyURI
      {any attributes with non-schema namespace}...>
      Content: (annotation?)
    </notation>
    """
    is_global = kwargs.pop('is_global', False)
    if not is_global:
        raise XMLSchemaParseError("a notation declaration must be global.", elem)
    try:
        notation_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        raise XMLSchemaParseError("a notation must have a 'name'.", elem)
    return notation_name, XsdNotation(notation_name, elem, schema)


__all__ = [
    'xsd_attribute_factory', 'xsd_element_factory',
    'xsd_attribute_group_factory', 'xsd_group_factory',
    'xsd_complex_type_factory', 'xsd_simple_type_factory',
    'xsd_restriction_factory', 'xsd_list_factory',
    'xsd_union_factory', 'xsd_notation_factory'
]
