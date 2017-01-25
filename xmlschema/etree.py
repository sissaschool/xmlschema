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
This module contains functions for ElementTree's structures.
"""
from .exceptions import (
    XMLSchemaDecodeError, XMLSchemaLookupError, XMLSchemaValidationError, XMLSchemaMultipleValidatorErrors
)
from .utils import get_namespace, get_qname, uri_to_prefixes


def etree_iterpath(elem, tag=None, path='.'):
    """
    A version of ElementTree node's iter function that return a couple
    with node and his relative path.

    :param elem:
    :param tag:
    :param path:
    :return:
    """
    if tag == "*":
        tag = None
    if tag is None or elem.tag == tag:
        yield elem, path
    for child in elem:
        if path == '/':
            child_path = '/%s' % child.tag
        elif path:
            child_path = '/'.join((path, child.tag))
        else:
            child_path = child.tag

        for _child, _child_path in etree_iterpath(child, tag, path=child_path):
            yield _child, _child_path


def etree_to_dict(elem, schema, path=None, dict_class=dict, spaces_for_tab=4, use_defaults=True):
    """
    Converts a XML document loaded in an ElementTree structure into a dictionary.

    :param elem: The starting element of the ElementTree structure, usually
    the root element of the tree.
    :param schema: The XMLSchema instance used for validation.
    :param path: The base path of the starting element.
    :param dict_class: The class used to build the dictionary.
    :param spaces_for_tab: Number of spaces.
    :param use_defaults: Fill the dictionary with the default values.
    :return: A dictionary of type dict_class.
    """

    def subtree_to_dict(node, node_path):
        node_dict = dict_class()
        xsd_element = schema.get_element(node_path)

        if node.attrib:
            # if we have attributes, decode them
            attr_dict = dict_class()
            for name, value_string in node.attrib.items():
                try:
                    try:
                        xsd_attribute = schema.get_attribute(name, node_path)
                    except KeyError:
                        xsd_attribute = xsd_element.get_attribute(name)
                except KeyError as err:
                    errors.append(XMLSchemaValidationError(
                        validator=xsd_element,
                        value=value_string,
                        reason="attribute %s not in the schema" % err,
                        elem=node,
                        schema_elem=xsd_element.elem
                    ))
                    continue

                try:
                    attr_dict[name] = xsd_attribute.decode(value_string)
                except XMLSchemaValidationError as err:
                    attr_dict[name] = err.value
                    errors.append(XMLSchemaValidationError(
                        err.validator, err.value, err.reason, node, xsd_attribute.elem
                    ))
                except XMLSchemaDecodeError as err:
                    attr_dict[name] = value_string
                    errors.append(err)

            if use_defaults:
                # Set defaults for missing schema's attributes
                for name in list(set(schema.get_attributes(node_path)) - set(node.keys())):
                    default_value = schema.get_attribute(name, node_path).default
                    if default_value is not None:
                        attr_dict[name] = schema.get_attribute(name, node_path).decode(default_value)
            node_dict.update(attr_dict)

        # Adds the subelements recursively
        for child in node:
            new_item = subtree_to_dict(child, node_path='%s/%s' % (node_path, child.tag))
            try:
                node_item = node_dict[child.tag]
            except KeyError:
                node_dict[child.tag] = new_item
            else:
                # found duplicate child tag, force a list
                if not isinstance(node_item, list):
                    # Create a list with two items
                    node_dict[child.tag] = [node_item, new_item]
                elif all(not isinstance(i, list) for i in node_item):
                    # Create a list of lists
                    if isinstance(new_item, list):
                        node_dict[child.tag] = [node_item, new_item]
                    else:
                        node_dict[child.tag] = [node_item, [new_item]]
                elif isinstance(new_item, list):
                    node_dict[child.tag].append(new_item)
                else:
                    node_dict[child.tag].append([new_item])

            tail = child.tail.strip()
            if tail:
                try:
                    xsd_element.validate(tail)
                except XMLSchemaValidationError as err:
                    errors.append(
                        XMLSchemaValidationError(xsd_element, err.value, err.reason, xsd_element.elem, node)
                    )

        # Add the element's content
        if node.text is None:
            if use_defaults:
                text = xsd_element.default or ''
            else:
                text = ''
        else:
            text = node.text.strip() if list(node) else node.text
            if spaces_for_tab is not None:
                text = text.replace('\t', ' ' * spaces_for_tab)

        try:
            value = xsd_element.decode(text)
        except XMLSchemaValidationError as err:
            value = err.value
            errors.append(
                XMLSchemaValidationError(xsd_element, err.value, err.reason, node, xsd_element.elem)
            )
        except XMLSchemaDecodeError as err:
            value = text
            errors.append(
                XMLSchemaDecodeError(xsd_element, err.text, err.decoder, err.reason, node, xsd_element.elem)
            )

        if node_dict:
            # if we have a dictionary add the text as a dictionary value (if there is any)
            if len(text) > 0:
                node_dict['_text'] = value
        else:
            # if we don't have child nodes or attributes, just set the text
            node_dict = value
        return node_dict

    errors = []
    if path is None:
        elem_path = get_qname(schema.target_namespace, elem.tag)
    else:
        elem_path = u'%s/%s' % (path, get_qname(schema.target_namespace, elem.tag))

    ret_dict = dict_class({elem.tag: subtree_to_dict(elem, elem_path)})
    if errors:
        raise XMLSchemaMultipleValidatorErrors(errors, ret_dict)
    return ret_dict


def etree_validate(elem, schema, path=None):
    """
    Generator function for validating an XML document loaded in an ElementTree structure.

    :param elem: The starting element of the ElementTree structure, usually
    the root element of the tree.
    :param schema: The XMLSchema instance used for validation.
    :param path: The base path of the starting element.
    """

    def subtree_validate(node, node_path, schema_elem):
        try:
            xsd_element = schema.get_element(node_path)
        except XMLSchemaLookupError:
            yield XMLSchemaValidationError(
                validator=schema,
                value=node.tag,
                reason="element with path /%s not in schema!" % node_path,
                elem=node,
                schema_elem=schema_elem
            )
        else:
            # Validate the tag format.
            if xsd_element.qualified and not get_namespace(node.tag):
                yield XMLSchemaValidationError(
                    validator=schema,
                    value=node.tag,
                    reason="tag must be a fully qualified name!",
                    elem=node,
                    schema_elem=schema_elem
                )

            # Validate the attributes.
            try:
                for error in xsd_element.type.attributes.iter_errors(node.attrib, node):
                    yield error
            except AttributeError:
                # The node hasn't attributes, then generate errors for each node attribute.
                for key in node.attrib:
                    yield XMLSchemaValidationError(
                        validator=schema,
                        value=key,
                        reason="attribute not allowed for this element",
                        elem=node,
                        schema_elem=schema_elem
                    )

            # Validate the content of the node.
            content_type = getattr(xsd_element.type, 'content_type', None)
            try:
                # complexContent (XsdGroup): validate the content tags.
                for error in content_type.iter_errors(node):
                    yield error
            except AttributeError:
                # simpleType or simpleContent
                try:
                    xsd_element.decode(node.text or '')
                except (XMLSchemaValidationError, XMLSchemaDecodeError) as err:
                    value = getattr(err, 'value', None) or getattr(err, 'text', None)
                    yield XMLSchemaValidationError(
                        validator=xsd_element,
                        value=value,
                        reason=err.reason,
                        elem=node,
                        schema_elem=xsd_element.elem
                    )

                # The node cannot have children, then generate an error for each child.
                for child in node:
                    child_path = uri_to_prefixes('%s/%s' % (node_path, child.tag), schema.namespaces)
                    yield XMLSchemaValidationError(
                        validator=xsd_element,
                        value=child.tag,
                        reason="element with path /%s not in schema!" % child_path,
                        elem=child,
                        schema_elem=xsd_element.elem
                    )
            else:
                # Validate each subtree
                for child in node:
                    for error in subtree_validate(child, '%s/%s' % (node_path, child.tag), xsd_element.elem):
                        yield error

    if path is None:
        elem_path = get_qname(schema.target_namespace, elem.tag)
    else:
        elem_path = u'%s/%s' % (path, get_qname(schema.target_namespace, elem.tag))
    return subtree_validate(elem, elem_path, schema._root)
