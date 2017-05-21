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

from .exceptions import XMLSchemaParseError, XMLSchemaValidationError
from .utils import get_qname, split_qname, split_reference
from .xsdbase import (
    XSD_SIMPLE_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_LIST_TAG,
    XSD_UNION_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG,
    XSD_GROUP_TAG, XSD_SIMPLE_CONTENT_TAG, XSD_EXTENSION_TAG,
    XSD_COMPLEX_CONTENT_TAG, XSD_ATTRIBUTE_TAG, XSD_ANY_ATTRIBUTE_TAG,
    XSD_ANY_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG, XSD_SEQUENCE_TAG,
    check_tag, get_xsd_attribute, get_xsd_declaration, iter_xsd_declarations, xsd_lookup
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


def xsd_factory(*args):
    """
    Check Element instance passed to a factory and log arguments.

    :param args: Values admitted for Element's tag (base argument of the factory)
    """
    def make_factory_wrapper(factory_function):
        def xsd_factory_wrapper(elem, schema, instance=None, **kwargs):
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
                result = factory_function(elem, schema, instance, **kwargs)
            except XMLSchemaValidationError as err:
                print(err)
                raise XMLSchemaParseError(err.message, elem)
            else:
                if instance is not None:
                    if isinstance(result, tuple):
                        if instance.name is not None and instance.name != result[0]:
                            raise XMLSchemaParseError(
                                "name mismatch wih instance %r: %r." % (instance, result[0]), elem
                            )
                    if instance.elem is None:
                        instance.elem = elem
                    if instance.schema is None:
                        instance.schema = schema
                return result

        return xsd_factory_wrapper
    return make_factory_wrapper


@xsd_factory(XSD_SIMPLE_TYPE_TAG)
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
    is_global = kwargs.pop('is_global', False)

    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        if is_global:
            raise XMLSchemaParseError("a global attribute require a 'name' attribute.", elem)
        type_name = None

    # Don't rebuild the XSD builtins (3 are instances of XsdList).
    if isinstance(instance, XsdAtomicBuiltin):
        instance.elem = elem
        instance.schema = schema
        return instance.name, instance

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


@xsd_factory(XSD_RESTRICTION_TAG)
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
            base_type = xsd_lookup(base_qname, schema.maps.types)
        if isinstance(base_type, XsdComplexType) and base_type.admit_simple_restriction():
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
                if isinstance(base_type, XsdComplexType) and base_type.admit_simple_restriction():
                    base_type = xsd_complex_type_class(
                        content_type=simple_type_factory(child, schema, **kwargs)[1],
                        name=None,
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


@xsd_factory(XSD_LIST_TAG)
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
            item_type = xsd_lookup(item_qname, schema.maps.types)
        if item_type.name != item_qname:
            XMLSchemaParseError("Wrong name for %r: %r." % (instance, item_qname), elem)
    else:
        raise XMLSchemaParseError("missing list type declaration", elem)

    if instance is not None:
        instance.update_attrs(elem=elem, schema=item_type.schema)
        return instance
    return xsd_list_class(item_type=item_type, elem=elem, schema=item_type.schema)


@xsd_factory(XSD_UNION_TAG)
def xsd_union_factory(elem, schema, instance=None, **kwargs):
    """
    Factory for XSD 'union' declarations:

    <union
        id = ID
        memberTypes = List of QName
        {any attributes with non-schema namespace ...}>
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
            xsd_lookup(split_reference(_type, schema.namespaces)[0], schema.maps.types)
            for _type in elem.attrib['memberTypes'].split()
        ])
    if not member_types:
        raise XMLSchemaParseError("missing union type declarations", elem)

    if instance is not None:
        instance.update_attrs(elem=elem, schema=schema)
        return instance
    return xsd_union_class(member_types, elem=elem, schema=schema)


@xsd_factory(XSD_ATTRIBUTE_TAG)
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
        {any attributes with non-schema namespace ...}>
        Content: (annotation?, simpleType?)
    </attribute>
    """
    simple_type_factory = kwargs.get('simple_type_factory', xsd_simple_type_factory)
    xsd_attribute_class = kwargs.get('xsd_attribute_class', XsdAttribute)
    is_global = kwargs.pop('is_global', False)
    if not isinstance(instance, (type(None), xsd_attribute_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_attribute_class), elem)

    qualified = elem.attrib.get('form', schema.attribute_form)

    try:
        name = elem.attrib['name']
    except KeyError:
        if is_global:
            raise XMLSchemaParseError("a global attribute require a 'name' attribute.", elem)
        # No 'name' attribute, must be a reference
        try:
            attribute_name = split_reference(elem.attrib['ref'], schema.namespaces)[0]
        except KeyError:
            # Missing also the 'ref' attribute
            raise XMLSchemaParseError("missing both 'name' and 'ref' in attribute declaration", elem)
        else:
            xsd_attribute = xsd_lookup(attribute_name, schema.maps.attributes)
            return attribute_name, xsd_attribute_class(
                xsd_type=xsd_attribute.type,
                name=attribute_name,
                elem=elem,
                schema=xsd_attribute.schema,
                qualified=xsd_attribute.qualified
            )
    else:
        attribute_name = get_qname(schema.target_namespace, name)

    xsd_type = getattr(instance, 'type', None)
    xsd_declaration = get_xsd_declaration(elem, required=False)
    try:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        xsd_type = xsd_type or xsd_lookup(type_qname, schema.maps.types)
        if xsd_type.name != type_qname:
            XMLSchemaParseError("wrong name for %r: %r." % (xsd_type, type_qname), elem)
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
        # schema = xsd_type.schema or schema

    if instance is not None:
        instance.update_attrs(type=xsd_type, elem=elem, schema=schema, qualified=qualified)
        return attribute_name, instance
    return attribute_name, xsd_attribute_class(
        name=attribute_name, xsd_type=xsd_type, elem=elem, schema=schema, qualified=qualified
    )


@xsd_factory(XSD_COMPLEX_TYPE_TAG)
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
    parse_local_groups = kwargs.get('parse_local_groups')
    xsd_complex_type_class = kwargs.get('complex_type_class', XsdComplexType)
    attribute_group_factory = kwargs.get('attribute_group_factory', xsd_attribute_group_factory)
    complex_type_factory = kwargs.get('complex_type_factory', xsd_complex_type_factory)
    group_factory = kwargs.get('group_factory', xsd_group_factory)
    restriction_factory = kwargs.get('restriction_factory', xsd_restriction_factory)
    xsd_group_class = kwargs.get('xsd_group_class', XsdGroup)
    xsd_attribute_group_class = kwargs.get('xsd_attribute_group_class', XsdAttributeGroup)
    is_global = kwargs.pop('is_global', False)
    if not isinstance(instance, (type(None), xsd_complex_type_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_complex_type_class), elem)

    # Get complexType's attributes and content
    try:
        type_name = get_qname(schema.target_namespace, elem.attrib['name'])
    except KeyError:
        if is_global:
            raise XMLSchemaParseError("a global type require a 'name' attribute.", elem)
        type_name = None

    mixed = elem.attrib.get('mixed') in ('true', '1')
    derivation = None
    content_node = get_xsd_declaration(elem, required=False, strict=False)

    if instance is None:
        content_type = None
        attributes = xsd_attribute_group_class(elem=elem, schema=schema)
    else:
        content_type = instance.content_type
        attributes = instance.attributes

    if content_node is None or content_node.tag in (
            XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG):
        #
        # complexType with empty content
        if content_type is None:
            content_type = xsd_group_class(elem=elem, schema=schema, mixed=mixed)
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG):
        #
        # complexType with child elements
        if content_type is None:
            content_type = xsd_group_class(elem=content_node, schema=schema, mixed=mixed)

        if parse_local_groups:
            content_type = group_factory(content_node, schema, content_type, mixed=mixed, **kwargs)[1]
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])

    elif content_node.tag == XSD_COMPLEX_CONTENT_TAG:
        #
        # complexType with complexContent restriction/extension
        if 'mixed' in content_node.attrib:
            mixed = content_node.attrib['mixed'] in ('true', '1')

        content_spec = get_xsd_declaration(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)
        derivation = content_spec.tag == XSD_EXTENSION_TAG

        if content_type is None:
            content_type = xsd_group_class(elem=content_node, schema=schema, mixed=mixed)

        # Get the base type: raise XMLSchemaLookupError if it's not defined.
        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = xsd_lookup(base_qname, schema.maps.types)

        if parse_local_groups and not content_type.parsed:
            if base_type != instance and isinstance(base_type.content_type, XsdGroup):
                if not base_type.content_type.parsed:
                    complex_type_factory(
                        base_type.elem, base_type.schema, instance=base_type, **kwargs
                    )
                if content_spec.tag == XSD_EXTENSION_TAG:
                    content_type.extend(base_type.content_type)
                content_type.model = base_type.content_type.model
                content_type.mixed = base_type.content_type.mixed

            try:
                content_declaration = get_xsd_declaration(content_spec, strict=False)
            except XMLSchemaParseError:
                pass
            else:
                if content_declaration.tag in (XSD_GROUP_TAG, XSD_CHOICE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG):
                    content_type.model = content_declaration.tag
                    xsd_group = group_factory(content_declaration, schema, mixed=mixed, **kwargs)[1]
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

        content_spec = get_xsd_declaration(content_node)
        check_tag(content_spec, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG)

        content_base = get_xsd_attribute(content_spec, 'base')
        base_qname, namespace = split_reference(content_base, schema.namespaces)
        base_type = xsd_lookup(base_qname, schema.maps.types)

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
            content_type = xsd_group_class(elem=elem, schema=schema, mixed=mixed)
        attributes.update(attribute_group_factory(elem, schema, instance=attributes, **kwargs)[1])
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


@xsd_factory(XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
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
    is_global = kwargs.pop('is_global', False)
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

    if attribute_group_name is None and is_global:
        raise XMLSchemaParseError("a global attribute group requires a 'name' attribute.", elem)

    if instance is None:
        attribute_group = xsd_attribute_group_class(attribute_group_name, elem, schema)
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
            ref_attribute_group = xsd_lookup(qname, schema.maps.attribute_groups)
            attribute_group.update(ref_attribute_group.items())
        elif attribute_group.name is not None:
            raise XMLSchemaParseError("(attribute | attributeGroup) expected, found", child)
    return attribute_group_name, attribute_group


@xsd_factory(XSD_COMPLEX_TYPE_TAG, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
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
    mixed = kwargs.pop('mixed', False)
    is_global = kwargs.pop('is_global', False)
    if not isinstance(instance, (type(None), xsd_group_class)):
        raise XMLSchemaParseError("instance argument %r is not a %r" % (instance, xsd_group_class))

    if elem.tag == XSD_GROUP_TAG:
        # Model group with 'name' or 'ref'
        name = elem.attrib.get('name')
        ref = elem.attrib.get('ref')
        if name is None:
            if is_global:
                raise XMLSchemaParseError("a global group require a 'name' attribute.", elem)
            elif ref is not None:
                group_name, namespace = split_reference(ref, schema.namespaces)
                xsd_group = xsd_lookup(group_name, schema.maps.groups)
                return group_name, xsd_group_class(
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
            content_model = get_xsd_declaration(elem)
        else:
            raise XMLSchemaParseError("found both attributes 'name' and 'ref'", elem)
    else:
        # Local group (SEQUENCE|ALL|CHOICE)
        if is_global:
            raise XMLSchemaParseError("a global group require a 'name' attribute.", elem)
        else:
            content_model = elem
            group_name = None

    check_tag(content_model, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_GROUP_TAG)
    if instance is None:
        xsd_group = xsd_group_class(
            name=group_name, elem=elem, schema=schema, model=content_model.tag, mixed=mixed
        )
    else:
        instance.update_attrs(elem=elem, schema=schema, model=content_model.tag, mixed=mixed)
        xsd_group = instance

    if not xsd_group.parsed or is_global:
        for child in iter_xsd_declarations(content_model):
            if child.tag == XSD_ELEMENT_TAG:
                _, xsd_element = element_factory(child, schema, **kwargs)
                xsd_group.append(xsd_element)
            elif content_model.tag == XSD_ALL_TAG:
                raise XMLSchemaParseError("'all' tags can contain only elements.", elem)
            elif child.tag == XSD_ANY_TAG:
                xsd_group.append(xsd_any_class(child, schema))
            elif child.tag in (XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG):
                xsd_group.append(
                    group_factory(child, schema, mixed=mixed, **kwargs)[1]
                )
        xsd_group.parsed = True
    return group_name, xsd_group


@xsd_factory(XSD_ELEMENT_TAG)
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
    is_global = kwargs.pop('is_global', False)
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
        elif is_global:
            raise XMLSchemaParseError("a global element require a 'name' attribute.", elem)
        ref = True
        xsd_element = xsd_lookup(element_name, schema.maps.elements)
        element_type = xsd_element.type
        # schema = xsd_element.schema or schema

    if instance is not None and instance.name != element_name:
        XMLSchemaParseError("Wrong name for %r: %r." % (instance, element_name), elem)

    if ref:
        if get_xsd_declaration(elem, required=False, strict=False) is not None:
            raise XMLSchemaParseError("Element reference declaration can't have children:", elem)
    elif 'type' in elem.attrib:
        type_qname, namespace = split_reference(elem.attrib['type'], schema.namespaces)
        element_type = xsd_lookup(type_qname, schema.maps.types)
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
