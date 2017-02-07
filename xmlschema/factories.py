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

from .exceptions import XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaLookupError
from .utils import get_qname, split_qname, split_reference
from .xsdbase import (
    XSD_SIMPLE_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_LIST_TAG,
    XSD_UNION_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG,
    XSD_GROUP_TAG, XSD_SIMPLE_CONTENT_TAG, XSD_EXTENSION_TAG,
    XSD_COMPLEX_CONTENT_TAG, XSD_ATTRIBUTE_TAG, XSD_ANY_ATTRIBUTE_TAG,
    XSD_ANY_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG, XSD_SEQUENCE_TAG,
    check_tag, get_xsd_attribute, get_xsd_declaration, iter_xsd_declarations,
    lookup_type, lookup_attribute, lookup_element, lookup_group, lookup_attribute_group
)
from .facets import (
    XsdUniqueFacet, XsdPatternsFacet, XsdEnumerationFacet,
    XSD_v1_0_FACETS, XSD_PATTERN_TAG, XSD_ENUMERATION_TAG
)
from .components import (
    XsdElement, XsdAnyAttribute, XsdAnyElement,
    XsdComplexType, XsdAttributeGroup, XsdGroup, XsdAttribute,
    XsdAtomicBuiltin, XsdAtomicRestriction, XsdList, XsdUnion
)
from .builtins import ANY_TYPE, ANY_SIMPLE_TYPE


logger = logging.getLogger(__name__)


def check_factory(*args):
    """
    Check Element instance passed to a factory and log arguments.

    :param args: Values admitted for Element's tag (base argument of the factory)
    """
    def make_factory_checker(factory_function):
        def factory_checker(elem, schema, instance=None, **kwargs):
            if logger.getEffectiveLevel() == logging.DEBUG:
                logger.debug(
                    "%s: elem.tag='%s', elem.attrib=%r, kwargs.keys()=%r",
                    factory_function.__name__, elem.tag, elem.attrib, kwargs.keys()
                )
                check_tag(elem, *args)
                factory_result = factory_function(elem, schema, instance, **kwargs)
                logger.debug("%s: return %r", factory_function.__name__, factory_result)
                return factory_result
            check_tag(elem, *args)
            try:
                return factory_function(elem, schema, instance, **kwargs)
            except XMLSchemaValidationError as err:
                raise XMLSchemaParseError(err.message, elem)
        return factory_checker
    return make_factory_checker


@check_factory(XSD_SIMPLE_TYPE_TAG)
def xsd_simple_type_factory(elem, schema, instance=None, **kwargs):
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
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    list_factory = kwargs.get('list_factory', xsd_list_factory)
    union_factory = kwargs.get('union_factory', xsd_union_factory)

    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None

    # Don't rebuild the XSD builtins (3 are instances of XsdList).
    if isinstance(instance, XsdAtomicBuiltin):
        instance.elem = elem
        instance.schema = schema
        return instance.name, instance

    if instance is not None:
        if type_name != instance.name:
            XMLSchemaParseError("Wrong name for %r: %r." % (instance, type_name), elem)
    else:
        try:
            instance = lookup_type(type_name, schema.target_namespace, schema.imported_schemas)
        except XMLSchemaLookupError:
            pass

    child = get_xsd_declaration(elem)
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


@check_factory(XSD_RESTRICTION_TAG)
def xsd_restriction_factory(elem, schema, instance=None, **kwargs):
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
    xsd_restriction_class = kwargs.get('xsd_restriction_class', XsdAtomicRestriction)
    xsd_complex_type_class = kwargs.get('complex_type_class', XsdComplexType)
    if not isinstance(instance, (type(None), xsd_restriction_class, xsd_complex_type_class)):
        raise XMLSchemaParseError(
            "instance argument %r is not a %r" % (instance, xsd_restriction_class), elem
        )

    base_type = getattr(instance, 'base_type', None)
    facets = {}
    has_attributes = False
    has_simple_type_child = False

    if 'base' in elem.attrib:
        base_qname, namespace = split_reference(elem.attrib['base'], schema.namespaces)
        if base_type is None:
            base_type = lookup_type(base_qname, namespace, schema.imported_schemas)
        if base_type.name != base_qname:
            XMLSchemaParseError("Wrong name for %r: %r." % (instance, base_qname), elem)
        if isinstance(base_type, XsdComplexType):
            if base_type.mixed and base_type.content_type.is_emptiable():
                if get_xsd_declaration(elem, strict=False).tag != XSD_SIMPLE_TYPE_TAG:
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
                if isinstance(base_type, XsdComplexType) and \
                        base_type.mixed and base_type.content_type.is_emptiable():
                    base_type = xsd_complex_type_class(
                        content_type=simple_type_factory(child, schema, **kwargs)[1],
                        name=base_type.name,
                        elem=elem,
                        schema=schema,
                        attributes=base_type.attributes,
                        derivation=base_type.derivation,
                        mixed=base_type.mixed
                    )
            has_simple_type_child = True
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
            raise XMLSchemaParseError("multiple %r constraint facet" % split_qname(child.tag)[1], elem)

    if base_type is None:
        raise XMLSchemaParseError("missing base type in simpleType declaration", elem)

    if instance is not None:
        instance.update_attrs(elem=elem, schema=base_type.schema, facets=facets)
        return instance
    return xsd_restriction_class(base_type, elem=elem, schema=base_type.schema, facets=facets)


@check_factory(XSD_LIST_TAG)
def xsd_list_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_list_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_list_class))
    item_type = getattr(instance, 'item_type', None)

    child = get_xsd_declaration(elem, required=False)
    if child is not None:
        # Case of a local simpleType declaration inside the list tag
        _, item_type = simple_type_factory(child, schema, item_type, **kwargs)
        if 'itemType' in elem.attrib:
            raise XMLSchemaParseError("ambiguous list type declaration", elem)
    elif 'itemType' in elem.attrib:
        # List tag with itemType attribute that refers to a global type
        item_qname, namespace = split_reference(elem.attrib['itemType'], schema.namespaces)
        if item_type is None:
            item_type = lookup_type(item_qname, namespace, schema.imported_schemas)
        if item_type.name != item_qname:
            XMLSchemaParseError("Wrong name for %r: %r." % (instance, item_qname), elem)
    else:
        raise XMLSchemaParseError("missing list type declaration", elem)

    if instance is not None:
        instance.update_attrs(elem=elem, schema=item_type.schema)
        return instance
    return xsd_list_class(item_type=item_type, elem=elem, schema=item_type.schema)


@check_factory(XSD_UNION_TAG)
def xsd_union_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_union_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_union_class), elem)

    member_types = [
        simple_type_factory(child, schema, **kwargs)[1] for child in iter_xsd_declarations(elem)
    ]
    if 'memberTypes' in elem.attrib:
        member_types.extend([
            lookup_type(
                *(split_reference(_type, schema.namespaces)),
                imported_schemas=schema.imported_schemas
            )
            for _type in elem.attrib['memberTypes'].split()
        ])
    if not member_types:
        raise XMLSchemaParseError("missing union type declarations", elem)

    if instance is not None:
        instance.update_attrs(elem=elem, schema=schema)
        return instance
    return xsd_union_class(member_types, elem=elem, schema=schema)


@check_factory(XSD_ATTRIBUTE_TAG)
def xsd_attribute_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_attribute_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_attribute_class), elem)

    qualified = elem.attrib.get('form', schema.attribute_form)

    try:
        name = elem.attrib['name']
    except KeyError:
        # No 'name' attribute, must be a reference
        try:
            xsd_attribute = lookup_attribute(
                *(split_reference(elem.attrib['ref'], schema.namespaces)),
                imported_schemas=schema.imported_schemas
            )
        except KeyError:
            # Missing also the 'ref' attribute
            raise XMLSchemaParseError("missing both 'name' and 'ref' in attribute declaration", elem)
        else:
            attribute_name = xsd_attribute.name
            return attribute_name, xsd_attribute_class(
                xsd_type=xsd_attribute.type,
                name=attribute_name,
                elem=elem,
                schema=xsd_attribute.schema,
                qualified=xsd_attribute.qualified
            )
    else:
        attribute_name = get_qname(schema.target_namespace, name)

    if instance is not None and instance.name != attribute_name:
        XMLSchemaParseError("Wrong name for %r: %r." % (instance, attribute_name), elem)

    xsd_type = getattr(instance, 'type', None)
    xsd_declaration = get_xsd_declaration(elem, required=False)
    try:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        xsd_type = xsd_type or lookup_type(type_qname, namespace, schema.imported_schemas)
        if xsd_type.name != type_qname:
            XMLSchemaParseError("Wrong name for %r: %r." % (xsd_type, type_qname), elem)
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
                "not allowed element in XSD attribute declaration: {}".format(xsd_declaration[0]), elem)
        schema = xsd_type.schema

    if instance is not None:
        instance.update_attrs(type=xsd_type, elem=elem, schema=schema, qualified=qualified)
        return attribute_name, instance
    return attribute_name, xsd_attribute_class(
        name=attribute_name, xsd_type=xsd_type, elem=elem, schema=schema, qualified=qualified
    )


@check_factory(XSD_COMPLEX_TYPE_TAG)
def xsd_complex_type_factory(elem, schema, instance=None, **kwargs):
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
    xsd_complex_type_class = kwargs.get('complex_type_class', XsdComplexType)
    attribute_group_factory = kwargs.get('attribute_group_factory', xsd_attribute_group_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    xsd_group_class = kwargs.get('xsd_group_class', XsdGroup)
    xsd_attribute_group_class = kwargs.get('xsd_attribute_group_class', XsdAttributeGroup)
    if not isinstance(instance, (type(None), xsd_complex_type_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_complex_type_class), elem)

    # Get complexType declaration from arguments
    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        type_name = None
    else:
        if instance is None:
            try:
                instance = lookup_type(type_name, schema.target_namespace, schema.imported_schemas)
            except XMLSchemaLookupError:
                pass

    if instance is not None and getattr(instance, 'name') != type_name:
        XMLSchemaParseError("Wrong name for %r: %r." % (instance, type_name), elem)

    content_type = getattr(instance, 'content_type', None)
    attributes = getattr(instance, 'attributes', None)
    mixed = elem.attrib.get('mixed') in ('true', '1')
    derivation = None

    # Get and check the content declaration
    content_node = get_xsd_declaration(elem, required=False, strict=False)
    if content_node is None:
        # Empty complexType ==> return a new 'xs:anyType' instance
        if instance is None:
            content_type = xsd_group_class(initlist=[XsdAnyElement()])
            attributes = xsd_attribute_group_class(
                elem=elem, schema=schema, initdict={None: XsdAnyAttribute()}
            )
        mixed = True
    elif content_node.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG):
        if instance is None:
            content_type = xsd_group_class(elem=elem, schema=schema)
            attributes = xsd_attribute_group_class(elem=elem, schema=schema)

        if parse_content_type and content_type.model is None:
            content_type.model = content_node.tag
            # Build type's content model only when a parent path is provided
            xsd_group = group_factory(content_node, schema, **kwargs)[1]
            content_type.extend(xsd_group)
            content_type.__dict__.update(xsd_group.__dict__)

        if instance is not None:
            return type_name, instance  # doesn't require a second pass for attributes.

        attributes.update(attribute_group_factory(elem, schema, **kwargs)[1])

    elif content_node.tag == XSD_COMPLEX_CONTENT_TAG:
        if 'mixed' in content_node.attrib:
            mixed = content_node.attrib['mixed'] in ('true', '1')
        if instance is None:
            content_type = xsd_group_class(elem=elem, schema=schema, mixed=mixed)
            attributes = xsd_attribute_group_class(elem=elem, schema=schema)

        content_spec = get_xsd_declaration(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        # check if base type exists
        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = lookup_type(base_qname, namespace, schema.imported_schemas)

        content_type.elem = content_spec
        derivation = content_spec.tag == XSD_EXTENSION_TAG
        if parse_content_type and content_type.model is None:
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

            content_declaration = get_xsd_declaration(content_spec, required=False, strict=False)
            if content_declaration is not None:
                if content_declaration.tag in (XSD_GROUP_TAG, XSD_CHOICE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG):
                    content_type.model = content_declaration.tag
                    xsd_group = group_factory(content_declaration, schema, **kwargs)[1]
                    if content_spec.tag == XSD_RESTRICTION_TAG:
                        pass  # TODO: Checks if restrictions are effective.
                    content_type.extend(xsd_group)
                    content_type.model = xsd_group.model
                    content_type.mixed = xsd_group.mixed

        if instance is not None:
            return type_name, instance  # doesn't require a second pass for attributes.

        if hasattr(base_type, 'attributes'):
            attributes.update(base_type.attributes)
        attributes.update(attribute_group_factory(content_spec, schema, **kwargs)[1])

    elif content_node.tag == XSD_SIMPLE_CONTENT_TAG:
        if instance is not None:
            return type_name, instance   # simpleContent doesn't require a second pass.

        if 'mixed' in content_node.attrib:
            raise XMLSchemaParseError("'mixed' attribute not allowed with simpleContent", elem)

        attributes = xsd_attribute_group_class(elem=elem, schema=schema)
        content_spec = get_xsd_declaration(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = lookup_type(base_qname, namespace, schema.imported_schemas)

        derivation = content_spec.tag == XSD_EXTENSION_TAG
        if content_spec.tag == XSD_RESTRICTION_TAG:
            content_type = restriction_factory(content_spec, schema, **kwargs)
        else:
            content_type = base_type

        if hasattr(base_type, 'attributes'):
            attributes.update(base_type.attributes)
        attributes.update(attribute_group_factory(content_spec, schema, **kwargs)[1])

    elif content_node.tag in (XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
        if instance is not None:
            return type_name, instance  # doesn't require a second pass for attributes.

        content_type = ANY_TYPE  # ANY_SIMPLE_TYPE??
        attributes = xsd_attribute_group_class(elem=elem, schema=schema)
        attributes.update(attribute_group_factory(elem, schema, **kwargs)[1])
    else:
        raise XMLSchemaParseError(
            "unexpected tag for complexType content: %r " % content_node.tag, elem
        )

    instance_attrs = {
        'content_type': content_type,
        'attributes': attributes,
        'name': type_name,
        'elem': elem,
        'schema': schema,
        'derivation': derivation,
        'mixed': mixed
    }
    if instance is not None:
        instance.update_attrs(**instance_attrs)
        return type_name, instance
    return type_name, xsd_complex_type_class(**instance_attrs)


@check_factory(XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
               XSD_ATTRIBUTE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_attribute_group_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_attribute_group_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_attribute_group_class))

    any_attribute = False

    if elem.tag == XSD_ATTRIBUTE_GROUP_TAG:
        try:
            attribute_group_name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            attribute_group_name = None
    else:
        attribute_group_name = None

    attribute_group = xsd_attribute_group_class(attribute_group_name, elem, schema)
    for child in iter_xsd_declarations(elem):
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
            _attribute_group = lookup_attribute_group(_attribute_group_qname, namespace, schema.imported_schemas)
            attribute_group.update(_attribute_group.items())
        elif attribute_group.name is not None:
            raise XMLSchemaParseError("(attribute | attributeGroup) expected, found", child)
    return str(attribute_group_name), attribute_group


@check_factory(XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
def xsd_group_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_group_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_group_class))

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
            xsd_group = lookup_group(group_name, namespace, schema.imported_schemas)
            return group_name, xsd_group_class(
                name=xsd_group.name,
                elem=elem,
                schema=schema,
                model=xsd_group.model,
                mixed=xsd_group.mixed,
                initlist=list(xsd_group)
            )
        else:
            group_name = get_qname(schema.target_namespace, name)
            content_model = get_xsd_declaration(elem)
    else:
        # Local group (SEQUENCE|ALL|CHOICE)
        content_model = elem
        group_name = None

    if instance is not None and instance.name != group_name:
        XMLSchemaParseError("Wrong name for %r: %r." % (instance, group_name), elem)

    check_tag(content_model, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_GROUP_TAG)
    if instance is None:
        xsd_group = xsd_group_class(name=group_name, elem=elem, schema=schema, model=content_model.tag)
    else:
        instance.update_attrs(elem=elem, schema=schema, model=content_model.tag)
        xsd_group = instance
        xsd_group.clear()
    for child in iter_xsd_declarations(content_model):
        if child.tag == XSD_ELEMENT_TAG:
            _, xsd_element = element_factory(child, schema, **kwargs)
            xsd_group.append(xsd_element)
        elif content_model.tag == XSD_ALL_TAG:
            raise XMLSchemaParseError("'all' tags can contain only elements.", elem)
        elif child.tag == XSD_ANY_TAG:
            xsd_group.append(xsd_any_class(child, schema))
        elif child.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
            xsd_group.append(group_factory(child, schema, **kwargs)[1])
    return group_name, xsd_group


@check_factory(XSD_ELEMENT_TAG)
def xsd_element_factory(elem, schema, instance=None, **kwargs):
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
    if not isinstance(instance, (type(None), xsd_element_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_element_class))

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
        msg = "attribute '{}' is not allowed when element reference is used!"
        if 'name' in elem.attrib:
            raise XMLSchemaParseError(msg.format('name'), elem)
        elif 'type' in elem.attrib:
            raise XMLSchemaParseError(msg.format('type'), elem)
        ref = True
        xsd_element = lookup_element(element_name, namespace, schema.imported_schemas)
        element_type = xsd_element.type
        schema = xsd_element.schema

    if instance is not None and instance.name != element_name:
        XMLSchemaParseError("Wrong name for %r: %r." % (instance, element_name), elem)

    if ref:
        if get_xsd_declaration(elem, required=False, strict=False) is not None:
            raise XMLSchemaParseError("Element reference declaration can't have children:", elem)
    elif 'type' in elem.attrib:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        try:
            element_type = lookup_type(type_qname, namespace, schema.imported_schemas)
        except XMLSchemaLookupError:
            raise XMLSchemaParseError("Missing type reference!", elem)
    else:
        child = get_xsd_declaration(elem, required=False, strict=False)
        if child is not None:
            if child.tag == XSD_COMPLEX_TYPE_TAG:
                _, element_type = complex_type_factory(child, schema, element_type, **kwargs)
            elif child.tag == XSD_SIMPLE_TYPE_TAG:
                _, element_type = simple_type_factory(child, schema, element_type, **kwargs)
        else:
            element_type = ANY_TYPE

    if instance is not None:
        instance.update_attrs(
            type=element_type, elem=elem, schema=schema, qualified=qualified, ref=ref
        )
        return element_name, instance

    return element_name, xsd_element_class(
        name=element_name, xsd_type=element_type, elem=elem, schema=schema, qualified=qualified, ref=ref
    )
