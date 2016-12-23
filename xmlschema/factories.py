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
import logging

from .exceptions import XMLSchemaParseError
from .utils import get_qname, split_qname, split_reference
from .xsdbase import (
    XSD_SIMPLE_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_LIST_TAG,
    XSD_UNION_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG,
    XSD_GROUP_TAG, XSD_SIMPLE_CONTENT_TAG, XSD_EXTENSION_TAG,
    XSD_COMPLEX_CONTENT_TAG, XSD_ATTRIBUTE_TAG, XSD_ANY_ATTRIBUTE_TAG,
    XSD_ANY_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG, XSD_SEQUENCE_TAG,
    check_tag, create_lookup_function, get_xsd_attribute, get_xsd_declaration,
    get_xsd_declarations
)
from .facets import (
    XsdUniqueFacet, XsdPatternsFacet, XsdEnumerationFacet,
    XSD_v1_0_FACETS, XSD_PATTERN_TAG, XSD_ENUMERATION_TAG
)
from .structures import (
    XsdRestriction, XsdList, XsdUnion, XsdComplexType, XsdAttributeGroup,
    XsdGroup, XsdAttribute, XsdElement, XsdAnyAttribute, XsdAnyElement
)
from .builtins import ANY_TYPE, ANY_SIMPLE_TYPE


logger = logging.getLogger(__name__)

# Define lookup functions for factories
lookup_type = create_lookup_function("types")
lookup_attribute = create_lookup_function("attributes")
lookup_element = create_lookup_function("elements")
lookup_group = create_lookup_function("groups")
lookup_attribute_group = create_lookup_function("attribute_groups")


def check_factory(*args):
    """
    Check Element instance passed to a factory and log arguments.

    :param args: Values admitted for Element's tag (base argument of the factory)
    """
    def make_factory_checker(factory_function):
        def factory_checker(elem, schema, **kwargs):
            if logger.getEffectiveLevel() == logging.DEBUG:
                logger.debug(
                    "%s: elem.tag='%s', elem.attrib=%r, kwargs.keys()=%r",
                    factory_function.__name__, elem.tag, elem.attrib, kwargs.keys()
                )
                check_tag(elem, *args)
                factory_result = factory_function(elem, schema, **kwargs)
                logger.debug("%s: return %r", factory_function.__name__, factory_result)
                return factory_result
            check_tag(elem, *args)
            return factory_function(elem, schema, **kwargs)

        return factory_checker
    return make_factory_checker


@check_factory(XSD_SIMPLE_TYPE_TAG)
def xsd_simple_type_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0 'simpleType' declarations:

    <simpleType
        final = (#all | List of (list | union | restriction))
        id = ID
        name = NCName
        {any attributes with non-schema namespace . . .}>
        Content: (annotation?, (restriction | list | union))
    </simpleType>
    """
    xsd_types = kwargs['xsd_types']
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    list_factory = kwargs.get('list_factory', xsd_list_factory)
    union_factory = kwargs.get('union_factory', xsd_union_factory)

    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None
    logger.debug("Parse simpleType '%r'", type_name)

    child = get_xsd_declaration(elem, min_occurs=1)
    if child.tag == XSD_RESTRICTION_TAG:
        xsd_type = restriction_factory(child, schema, **kwargs)
    elif child.tag == XSD_LIST_TAG:
        xsd_type = list_factory(child, schema, **kwargs)
    elif child.tag == XSD_UNION_TAG:
        xsd_type = union_factory(child, schema, **kwargs)
    else:
        raise XMLSchemaParseError('(restriction|list|union) expected', child)

    try:
        # simpleType already exists, return only a reference to it
        return type_name, xsd_types[type_name]
    except KeyError:
        xsd_type.name = type_name

    logger.debug("Created %r for simpleType declaration.", xsd_type)
    return type_name, xsd_type


@check_factory(XSD_RESTRICTION_TAG)
def xsd_restriction_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0 'restriction' declarations:

    <restriction
        base = QName
        id = ID
        {any attributes with non-schema namespace . . .}>
        Content: (annotation?, (simpleType?, (minExclusive | minInclusive | maxExclusive | maxInclusive |
        totalDigits | fractionDigits | length | minLength | maxLength | enumeration | whiteSpace | pattern)*))
    </restriction>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    xsd_restriction_class = kwargs.get('xsd_restriction_class', XsdRestriction)

    facets = {}
    has_attributes = False
    has_simple_type = False

    try:
        base_qname, namespace = split_reference(elem.attrib['base'], schema.namespaces)
    except KeyError:
        base_type = None
    else:
        base_type = lookup_type(base_qname, namespace, schema.lookup_table)
        logger.debug("Associated to base type '%r': %s", base_type, base_type)

    for child in get_xsd_declarations(elem):
        if child.tag in (XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
            has_attributes = True
        elif has_attributes:
            raise XMLSchemaParseError("unexpected tag after attribute declarations", child)
        elif child.tag == XSD_SIMPLE_TYPE_TAG:
            # Case of simpleType declaration inside a restriction
            if has_simple_type:
                raise XMLSchemaParseError("duplicated simpleType declaration", child)
            elif base_type is not None:
                # See: "http://www.w3.org/TR/xmlschema-2/#element-restriction"
                raise XMLSchemaParseError(
                    "base attribute and simpleType declaration are mutually exclusive", elem
                )
            _, base_type = simple_type_factory(child, schema, **kwargs)
            has_simple_type = True
        elif child.tag not in XSD_v1_0_FACETS:
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
            XMLSchemaParseError("multiple %r constraint facet" % split_qname(child.tag)[1], elem)

    if base_type is None:
        raise XMLSchemaParseError("missing base type in simpleType declaration", elem)

    return xsd_restriction_class(base_type, elem=elem, schema=base_type.schema, facets=facets)


@check_factory(XSD_LIST_TAG)
def xsd_list_factory(elem, schema, **kwargs):
    """
    Factory for XSD 'list' declarations:

    <list
        id = ID
        itemType = QName
        {any attributes with non-schema namespace . . .}>
        Content: (annotation?, simpleType?)
    </list>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    xsd_list_class = kwargs.get('xsd_list_class', XsdList)

    child_declarations = get_xsd_declarations(elem)
    if len(child_declarations) > 1:
        raise XMLSchemaParseError("not parsable XSD child declarations", elem)
    elif child_declarations:
        # Case of a simpleType declaration inside the list tag
        _, item_type = simple_type_factory(child_declarations[0], schema, **kwargs)
        if 'itemType' in elem.attrib:
            raise XMLSchemaParseError("ambiguous list type declaration", elem)
    elif 'itemType' in elem.attrib:
        # Case 1: List tag with itemType attribute
        type_qname, namespace = split_reference(elem.attrib['itemType'], schema.namespaces)
        item_type = lookup_type(type_qname, namespace, schema.lookup_table)
        logger.debug("Associated to item type '%r': %s", item_type, item_type.name)
    else:
        raise XMLSchemaParseError("missing list type declaration", elem)

    return xsd_list_class(item_type, elem=elem, schema=item_type.schema)


@check_factory(XSD_UNION_TAG)
def xsd_union_factory(elem, schema, **kwargs):
    """
    Factory for XSD 'union' declarations:

    <union
        id = ID
        memberTypes = List of QName
        {any attributes with non-schema namespace . . .}>
        Content: (annotation?, simpleType*)
    </union>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    xsd_union_class = kwargs.get('xsd_union_class', XsdUnion)

    member_types = [simple_type_factory(child, schema, **kwargs)[1] for child in get_xsd_declarations(elem)]
    if 'memberTypes' in elem.attrib:
        member_types.extend([
            lookup_type(*(split_reference(_type, schema.namespaces)), lookup_schemas=schema.lookup_table)
            for _type in elem.attrib['memberTypes'].split()
        ])
    if not member_types:
        raise XMLSchemaParseError("missing union type declarations", elem)

    return xsd_union_class(member_types, elem=elem, schema=schema)


@check_factory(XSD_ATTRIBUTE_TAG)
def xsd_attribute_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0 'attribute' declarations:

    <attribute
        default = string
        fixed = string
        form = (qualified | unqualified)
        id = ID
        name = NCName
        ref = QName
        type = QName
        use = (optional | prohibited | required) : optional
        {any attributes with non-schema namespace . . .}>
        Content: (annotation?, simpleType?)
    </attribute>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    xsd_attribute_class = kwargs.get('xsd_attribute_class', XsdAttribute)

    qualified = elem.attrib.get('form', schema.attribute_form)

    try:
        name = elem.attrib['name']
    except KeyError:
        # No 'name' attribute, must be a reference
        try:
            xsd_attribute = lookup_attribute(
                *(split_reference(elem.attrib['ref'], schema.namespaces)),
                lookup_schemas=schema.lookup_table
            )
        except KeyError:
            # Missing also the 'ref' attribute
            raise XMLSchemaParseError("missing both 'name' and 'ref' in attribute declaration", elem)
        else:
            attribute_name = xsd_attribute.name
            logger.debug("Refer to the global attribute '%s'", attribute_name)
            return attribute_name, xsd_attribute
    else:
        attribute_name = get_qname(schema.target_namespace, name)

    declarations = get_xsd_declarations(elem, max_occurs=1)
    try:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        xsd_type = lookup_type(type_qname, namespace, schema.lookup_table)
    except KeyError:
        if declarations:
            # No 'type' attribute in declaration, parse for child local simpleType
            _, xsd_type = simple_type_factory(declarations[0], schema, **kwargs)
            return attribute_name, xsd_attribute_class(xsd_type, attribute_name, elem, schema, qualified)
        else:
            # Not type declaration: use xsdAnySimpleType
            return attribute_name, xsd_attribute_class(ANY_SIMPLE_TYPE, attribute_name, elem, schema, qualified)
    else:
        if declarations and declarations[0].tag == XSD_SIMPLE_TYPE_TAG:
            raise XMLSchemaParseError("ambiguous type declaration for XSD attribute", elem)
        elif declarations:
            raise XMLSchemaParseError(
                "not allowed element in XSD attribute declaration: {}".format(declarations[0]), elem)
        return attribute_name, xsd_attribute_class(xsd_type, attribute_name, elem, xsd_type.schema, qualified)


@check_factory(XSD_COMPLEX_TYPE_TAG)
def xsd_complex_type_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0 'complexType' declarations:

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
    """
    parse_content_type = kwargs.get('parse_content_type')
    xsd_types = kwargs['xsd_types']
    xsd_complex_type_class = kwargs.get('complex_type_class', XsdComplexType)
    attribute_group_factory = kwargs.get('attribute_group_factory', xsd_attribute_group_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    xsd_group_class = kwargs.get('xsd_group_class', XsdGroup)
    xsd_attribute_group_class = kwargs.get('xsd_attribute_group_class', XsdAttributeGroup)

    attributes = xsd_attribute_group_class(elem=elem, schema=schema)
    mixed = elem.attrib.get('mixed') in ('true', '1')
    derivation = None

    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None
    logger.debug("Parsing complexType '%s'", type_name)

    declarations = get_xsd_declarations(elem)
    try:
        content_node = declarations[0]
    except IndexError:
        logger.debug("empty complexType, return a new 'xs:anyType' instance")
        attributes[None] = XsdAnyAttribute()
        return type_name, xsd_complex_type_class(
            content_type=XsdGroup(initlist=[XsdAnyElement()]),
            name=type_name,
            elem=elem,
            schema=schema,
            attributes=attributes,
            mixed=True
        )
    else:
        check_tag(
            content_node, XSD_SIMPLE_CONTENT_TAG, XSD_COMPLEX_CONTENT_TAG,
            XSD_SEQUENCE_TAG, XSD_GROUP_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG,
            XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG
        )

    try:
        xsd_type = xsd_types[type_name]
    except KeyError:
        xsd_type = None
    else:
        logger.debug("complexType %r already exists ...", type_name)
        if content_node.tag not in \
                (XSD_COMPLEX_CONTENT_TAG, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG):
            return type_name, xsd_type

    if content_node.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG):
        content_type = xsd_type.content_type if xsd_type is not None else xsd_group_class(elem=elem, schema=schema)
        if parse_content_type and not content_type:
            # Build type's content model only when a parent path is provided
            xsd_group = group_factory(content_node, schema, **kwargs)[1]
            content_type.extend(xsd_group)
            content_type.__dict__.update(xsd_group.__dict__)

        if xsd_type is not None:
            return type_name, xsd_type
        attributes.update(attribute_group_factory(elem, schema, **kwargs)[1])

    elif content_node.tag == XSD_COMPLEX_CONTENT_TAG:
        content_type = xsd_type.content_type if xsd_type is not None else xsd_group_class(elem=elem, schema=schema)
        content_spec = get_xsd_declaration(content_node, min_occurs=1)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        # check if base type exists
        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = lookup_type(base_qname, namespace, schema.lookup_table)

        content_type.elem = content_spec
        derivation = content_spec.tag == XSD_EXTENSION_TAG
        if parse_content_type and not content_type:
            # Build type's content model only when a parent path is provided
            try:
                if base_type.content_type.model is None:
                    complex_type_factory(base_type.elem, base_type.schema, **kwargs)
            except AttributeError:
                pass
            else:
                if content_spec.tag == XSD_EXTENSION_TAG:
                    content_type.extend(base_type.content_type)
                content_type.model = base_type.content_type.model
                content_type.mixed = base_type.content_type.mixed

            try:
                content_declaration = get_xsd_declarations(content_spec)[0]
            except IndexError:
                pass  # Empty extension or restriction declaration.
            else:
                if content_declaration.tag in (XSD_GROUP_TAG, XSD_CHOICE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG):
                    xsd_group = group_factory(content_declaration, schema, **kwargs)[1]
                    if content_spec.tag == XSD_RESTRICTION_TAG:
                        pass  # TODO: Checks if restrictions are effective.
                    content_type.extend(xsd_group)
                    content_type.model = xsd_group.model
                    content_type.mixed = xsd_group.mixed

        if xsd_type is not None:
            return type_name, xsd_type

        attributes.update(attribute_group_factory(content_spec, schema, **kwargs)[1])
        if 'mixed' in content_node.attrib:
            mixed = content_node.attrib['mixed'] in ('true', '1')
        content_type.mixed = mixed

    elif content_node.tag == XSD_SIMPLE_CONTENT_TAG:
        if 'mixed' in content_node.attrib:
            raise XMLSchemaParseError("'mixed' attribute not allowed with simpleContent", elem)

        content_spec = get_xsd_declaration(content_node, min_occurs=1)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        # Check base type
        # check_xsd_attribute(content_spec, 'base', namespaces, lookup_schemas)
        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = lookup_type(base_qname, namespace, schema.lookup_table)

        derivation = content_spec.tag == XSD_EXTENSION_TAG
        if content_spec.tag == XSD_RESTRICTION_TAG:
            content_type = restriction_factory(content_spec, schema, **kwargs)
        else:
            content_type = base_type
        attributes.update(attribute_group_factory(content_spec, schema, **kwargs)[1])
    elif content_node.tag in (XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
        content_type = ANY_SIMPLE_TYPE
        attributes.update(attribute_group_factory(elem, schema, **kwargs)[1])
    else:
        raise ValueError(repr(content_node.tag))

    # Add attribute wildcards if there is the anyAttribute declaration.
    if declarations[-1].tag == XSD_ANY_ATTRIBUTE_TAG:
        any_attribute = declarations[-1].attrib

    xsd_type = xsd_complex_type_class(
        content_type, type_name, elem, schema, attributes, derivation, mixed
    )

    logger.debug("Created %r", xsd_type)
    return type_name, xsd_type


@check_factory(XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
               XSD_ATTRIBUTE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_attribute_group_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0/1.1 'attributeGroup' declarations:

        <attributeGroup
            id = ID
            name = NCName
            ref = QName
            {any attributes with non-schema namespace . . .}>
            Content: (annotation?, ((attribute | attributeGroup)*, anyAttribute?))
        </attributeGroup>
    """
    attribute_factory = kwargs.get('attribute_factory', xsd_attribute_factory)
    xsd_attribute_group_class = kwargs.get('xsd_attribute_group_class', XsdAttributeGroup)

    any_attribute = False

    if elem.tag == XSD_ATTRIBUTE_GROUP_TAG:
        try:
            attribute_group_name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            attribute_group_name = None
    else:
        attribute_group_name = None

    attribute_group = xsd_attribute_group_class(attribute_group_name, elem, schema)
    for child in get_xsd_declarations(elem):
        if any_attribute:
            if child.tag == XSD_ANY_ATTRIBUTE_TAG:
                raise XMLSchemaParseError("more anyAttribute declarations in the same attribute group", child)
            else:
                raise XMLSchemaParseError("another declaration after anyAttribute", child)
        elif child.tag == XSD_ANY_ATTRIBUTE_TAG:
            any_attribute = True
            attribute_group.update({None: XsdAnyAttribute(elem=child)})
        elif child.tag == XSD_ATTRIBUTE_TAG:
            attribute_group.update([attribute_factory(child, schema, **kwargs)])
        elif child.tag == XSD_ATTRIBUTE_GROUP_TAG:
            _attribute_group_qname, namespace = split_reference(get_xsd_attribute(child, 'ref'), schema.namespaces)
            _attribute_group = lookup_attribute_group(_attribute_group_qname, namespace, schema.lookup_table)
            attribute_group.update(_attribute_group.items())
        elif attribute_group:
            raise XMLSchemaParseError("(attribute | attributeGroup) expected, found", child)
    return str(attribute_group_name), attribute_group


@check_factory(XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_group_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0/1.1 model 'group' declarations:

        <group
            id = ID
            maxOccurs = (nonNegativeInteger | unbounded)  : 1
            minOccurs = nonNegativeInteger : 1
            name = NCName
            ref = QName
            {any attributes with non-schema namespace . . .}>
            Content: (annotation?, (all | choice | sequence)?)
        </group>
    """
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    element_factory = kwargs.get('element_factory', xsd_element_factory)
    xsd_group_class = kwargs.get('xsd_group_class', XsdGroup)
    xsd_any_class = kwargs.get('xsd_any_class', XsdAnyElement)

    if elem.tag == XSD_GROUP_TAG:
        # Model group with 'name' or 'ref'
        name = elem.attrib.get('name')
        ref = elem.attrib.get('ref')
        if not name and not ref:
            raise XMLSchemaParseError("missing both attributes 'name' and 'ref'", elem)
        elif name and ref:
            raise XMLSchemaParseError("found both attributes 'name' and 'ref'", elem)
        elif ref:
            group_name, namespace = split_reference(ref, schema.namespaces)
            return group_name, lookup_group(group_name, namespace, schema.lookup_table)
        else:
            group_name = get_qname(schema.target_namespace, name)
            content_model = get_xsd_declaration(elem, min_occurs=1)
    else:
        # Local group (SEQUENCE|ALL|CHOICE)
        content_model = elem
        group_name = None

    check_tag(content_model, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_GROUP_TAG)
    xsd_group = xsd_group_class(name=group_name, elem=elem, schema=schema, model=content_model.tag)
    for child in get_xsd_declarations(content_model):
        if child.tag == XSD_ELEMENT_TAG:
            element_path, xsd_element = element_factory(child, schema, **kwargs)
            xsd_group.append(xsd_element)
        elif content_model.tag == XSD_ALL_TAG:
            raise XMLSchemaParseError("'all' tags can only contain elements.", elem)
        elif child.tag == XSD_ANY_TAG:
            xsd_group.append(xsd_any_class(child, schema))
        elif child.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
            xsd_group.append(group_factory(child, schema, **kwargs)[1])
    return group_name, xsd_group


@check_factory(XSD_ELEMENT_TAG)
def xsd_element_factory(elem, schema, **kwargs):
    """
    Factory for XSD 1.0 'element' declarations:

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
    """
    element_form_default = kwargs.get('element_form', 'unqualified')
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)
    xsd_element_class = kwargs.get('xsd_element_class', XsdElement)

    element_type = None
    qualified = elem.attrib.get('form', element_form_default) == 'qualified'

    # Checking element attributes
    try:
        element_name, namespace = split_reference(elem.attrib['ref'], schema.namespaces)
    except KeyError:
        # No 'ref' attribute, must be an explicit declaration
        try:
            element_name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            # Missing also the 'ref' attribute
            raise XMLSchemaParseError("invalid element declaration in XSD schema", elem)
    else:
        # Reference to a global element
        msg = "attribute '{}' is not allowed when element reference is used!"
        if 'name' in elem.attrib:
            raise XMLSchemaParseError(msg.format('name'), elem)
        elif 'type' in elem.attrib:
            raise XMLSchemaParseError(msg.format('type'), elem)
        xsd_element = lookup_element(element_name, namespace, schema.lookup_table)
        return element_name, xsd_element_class(
            name=xsd_element.name,
            xsd_type=xsd_element.type,
            elem=xsd_element.elem,
            schema=xsd_element.schema,
            qualified=qualified,
            ref=True
        )

    if 'type' in elem.attrib:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        element_type = lookup_type(type_qname, namespace, schema.lookup_table)
        if isinstance(element_type, XsdComplexType):
            try:
                _, element_type = complex_type_factory(element_type.elem, element_type.schema, **kwargs)
            except AttributeError:
                # The complexType is a builtin type.
                pass
    else:
        declarations = get_xsd_declarations(elem)
        if declarations:
            child = declarations[0]
            if child.tag == XSD_COMPLEX_TYPE_TAG:
                _, element_type = complex_type_factory(child, schema, **kwargs)
            elif child.tag == XSD_SIMPLE_TYPE_TAG:
                _, element_type = simple_type_factory(child, schema, **kwargs)
        else:
            element_type = ANY_TYPE

    logger.debug("Add element '%s' of type %r", element_name, element_type)
    return element_name, xsd_element_class(element_name, element_type, elem, schema, qualified=qualified)
