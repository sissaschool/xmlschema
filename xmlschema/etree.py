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
This module contains functions to convert ElementTree's trees based on a schema
to or from other data formats (eg. dictionaries, json).
"""
from io import StringIO
from .core import etree_iterparse
from .validators import XMLSchemaDecodeError, XMLSchemaValidationError, XMLSchemaMultipleValidatorErrors


def etree_get_namespaces(source):
    """
    Extract namespaces with related prefixes from schema source.

    Note: cannot use the schema tree because the ElementTree library can modify
    the mapping of namespace's prefixes without updating the references (cannot
    change them because ElementTree doesn't parse XSD).
    """
    try:
        return [node for _, node in etree_iterparse(StringIO(source), events=['start-ns'])]
    except TypeError:
        return [node for _, node in etree_iterparse(source, events=['start-ns'])]


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


def etree_to_dict(etree, xml_schema, dict_class=dict, spaces_for_tab=4, use_defaults=True):
    root_node = etree.getroot()
    ret_dict = element_to_dict(
        root_node, xml_schema, dict_class=dict_class, spaces_for_tab=spaces_for_tab, use_defaults=use_defaults
    )
    return ret_dict


def element_to_dict(elem, schema, path=None, dict_class=dict, spaces_for_tab=4, use_defaults=True):

    def _element_to_dict(node, node_path):
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
            new_item = _element_to_dict(child, node_path='%s/%s' % (node_path, child.tag))
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
                    errors.append(XMLSchemaValidationError(
                        xsd_element, err.value, err.reason, xsd_element.elem, node
                    ))

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
            errors.append(XMLSchemaValidationError(
                xsd_element, err.value, err.reason, node, xsd_element.elem)
            )
        except XMLSchemaDecodeError as err:
            value = text
            errors.append(XMLSchemaDecodeError(
                xsd_element, err.text, err.decoder, err.reason, node, xsd_element.elem)
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
    path = elem.tag if path is None else '%s/%s' % (path, elem.tag)
    ret_dict = dict_class({elem.tag: _element_to_dict(elem, path)})
    if errors:
        raise XMLSchemaMultipleValidatorErrors(errors, ret_dict)
    return ret_dict
