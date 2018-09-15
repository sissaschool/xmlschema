# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains functions and classes for managing namespaces's  
XSD declarations/definitions.
"""
from __future__ import unicode_literals
import re
from ..exceptions import XMLSchemaKeyError, XMLSchemaTypeError, XMLSchemaValueError
from ..namespaces import XSD_NAMESPACE, NamespaceResourcesMap
from ..qnames import (
    get_qname, local_name, prefixed_to_qname, XSD_INCLUDE_TAG, XSD_IMPORT_TAG,
    XSD_REDEFINE_TAG, XSD_NOTATION_TAG, XSD_SIMPLE_TYPE_TAG, XSD_COMPLEX_TYPE_TAG,
    XSD_GROUP_TAG, XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG,
    XSD_ANY_TYPE
)
from . import XMLSchemaNotBuiltError, XsdValidator, XsdKeyref, XsdComponent, XsdAttribute, \
    XsdSimpleType, XsdComplexType, XsdElement, XsdAttributeGroup, XsdGroup, XsdNotation
from .parseutils import get_xsd_attribute
from .builtins import xsd_builtin_types_factory


def camel_case_split(s):
    """
    Split words of a camel case string
    """
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', s)


def iterchildren_by_tag(tag):
    """
    Defines a generator that produce all child elements that have a specific tag.
    """
    def iterfind_function(elem):
        for e in elem:
            if e.tag == tag:
                yield e
    iterfind_function.__name__ = str('iterfind_xsd_%ss' % '_'.join(camel_case_split(local_name(tag))).lower())
    return iterfind_function


iterchildren_xsd_import = iterchildren_by_tag(XSD_IMPORT_TAG)
iterchildren_xsd_include = iterchildren_by_tag(XSD_INCLUDE_TAG)
iterchildren_xsd_redefine = iterchildren_by_tag(XSD_REDEFINE_TAG)


#
# Defines the load functions for XML Schema structures
def create_load_function(filter_function):

    def load_xsd_globals(xsd_globals, schemas):
        redefinitions = []
        for schema in schemas:
            target_namespace = schema.target_namespace
            for elem in iterchildren_xsd_redefine(schema.root):
                for child in filter_function(elem):
                    qname = get_qname(target_namespace, get_xsd_attribute(child, 'name'))
                    redefinitions.append((qname, (child, schema)))

            for elem in filter_function(schema.root):
                qname = get_qname(target_namespace, get_xsd_attribute(elem, 'name'))
                try:
                    xsd_globals[qname].append((elem, schema))
                except KeyError:
                    xsd_globals[qname] = (elem, schema)
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], (elem, schema)]

        for qname, obj in redefinitions:
            if qname not in xsd_globals:
                elem, schema = obj
                schema.parse_error("not a redefinition!", elem)
            else:
                try:
                    xsd_globals[qname].append(obj)
                except KeyError:
                    xsd_globals[qname] = obj
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], obj]

    return load_xsd_globals


load_xsd_simple_types = create_load_function(iterchildren_by_tag(XSD_SIMPLE_TYPE_TAG))
load_xsd_attributes = create_load_function(iterchildren_by_tag(XSD_ATTRIBUTE_TAG))
load_xsd_attribute_groups = create_load_function(iterchildren_by_tag(XSD_ATTRIBUTE_GROUP_TAG))
load_xsd_complex_types = create_load_function(iterchildren_by_tag(XSD_COMPLEX_TYPE_TAG))
load_xsd_elements = create_load_function(iterchildren_by_tag(XSD_ELEMENT_TAG))
load_xsd_groups = create_load_function(iterchildren_by_tag(XSD_GROUP_TAG))
load_xsd_notations = create_load_function(iterchildren_by_tag(XSD_NOTATION_TAG))


def create_lookup_function(xsd_classes):
    if isinstance(xsd_classes, tuple):
        types_desc = ' or '.join([c.__name__ for c in xsd_classes])
    else:
        types_desc = xsd_classes.__name__

    def lookup(global_map, qname, tag_map):
        try:
            obj = global_map[qname]
        except KeyError:
            raise XMLSchemaKeyError("missing a %s object for %r!" % (types_desc, qname))
        else:
            if isinstance(obj, xsd_classes):
                return obj

            elif isinstance(obj, tuple):
                # Not built XSD global component without redefinitions
                try:
                    elem, schema = obj
                except ValueError:
                    return obj[0]  # Circular build, simply return (elem, schema) couple

                try:
                    factory_or_class = tag_map[elem.tag]
                except KeyError:
                    raise XMLSchemaKeyError("wrong element %r for map %r." % (elem, global_map))

                global_map[qname] = obj,  # Encapsulate into a single-item tuple to catch circular builds
                global_map[qname] = factory_or_class(elem, schema, parent=None)
                return global_map[qname]

            elif isinstance(obj, list):
                if not isinstance(obj[0], xsd_classes):
                    # Not built XSD global component with redefinitions
                    try:
                        elem, schema = obj[0]
                    except ValueError:
                        return obj[0][0]  # Circular build, simply return (elem, schema) couple

                    try:
                        factory_or_class = tag_map[elem.tag]
                    except KeyError:
                        raise XMLSchemaKeyError("wrong element %r for map %r." % (elem, global_map))

                    global_map[qname] = obj[0],  # To catch circular builds
                    global_map[qname] = factory_or_class(elem, schema, parent=None)
                else:
                    # Built-in type
                    global_map[qname] = obj[0]

                for elem, schema in obj[1:]:
                    global_map[qname].schema = schema
                    global_map[qname].elem = elem
                return global_map[qname]

            else:
                raise XMLSchemaTypeError(
                    "wrong instance %s for XSD global %r, a %s required." % (obj, qname, types_desc)
                )

    return lookup


lookup_notation = create_lookup_function(XsdNotation)
lookup_type = create_lookup_function((XsdSimpleType, XsdComplexType))
lookup_attribute = create_lookup_function(XsdAttribute)
lookup_attribute_group = create_lookup_function(XsdAttributeGroup)
lookup_group = create_lookup_function(XsdGroup)
lookup_element = create_lookup_function(XsdElement)


class XsdGlobals(XsdValidator):
    """
    Mediator class for related XML schema instances. It stores the global
    declarations defined in the registered schemas. Register a schema to
    add it's declarations to the global maps.

    :param validator: the XMLSchema class to use for global maps.
    :param validation: the XSD validation mode to use, can be 'strict', 'lax' or 'skip'.
    """

    def __init__(self, validator, validation='strict'):
        super(XsdGlobals, self).__init__(validation)
        self.validator = validator

        self.namespaces = NamespaceResourcesMap()  # Registered schemas by namespace URI

        self.types = {}                 # Global types (both complex and simple)
        self.attributes = {}            # Global attributes
        self.attribute_groups = {}      # Attribute groups
        self.groups = {}                # Model groups
        self.notations = {}             # Notations
        self.elements = {}              # Global elements
        self.substitution_groups = {}   # Substitution groups
        self.constraints = {}           # Constraints (uniqueness, keys, keyref)

        self.global_maps = (self.notations, self.types, self.attributes,
                            self.attribute_groups, self.groups, self.elements)

    def copy(self, validation=None):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator, validation or self.validation)
        obj.namespaces.update(self.namespaces)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.notations.update(self.notations)
        obj.elements.update(self.elements)
        obj.substitution_groups.update(self.substitution_groups)
        obj.constraints.update(self.constraints)
        return obj

    __copy__ = copy

    def lookup_notation(self, qname):
        return lookup_notation(self.notations, qname, self.validator.TAG_MAP)

    def lookup_type(self, qname):
        return lookup_type(self.types, qname, self.validator.TAG_MAP)

    def lookup_attribute(self, qname):
        return lookup_attribute(self.attributes, qname, self.validator.TAG_MAP)

    def lookup_attribute_group(self, qname):
        return lookup_attribute_group(self.attribute_groups, qname, self.validator.TAG_MAP)

    def lookup_group(self, qname):
        return lookup_group(self.groups, qname, self.validator.TAG_MAP)

    def lookup_element(self, qname):
        return lookup_element(self.elements, qname, self.validator.TAG_MAP)

    @property
    def built(self):
        if not self.namespaces:
            return False
        xsd_global = None
        for xsd_global in self.iter_globals():
            if not isinstance(xsd_global, XsdComponent):
                return False
            if not xsd_global.built:
                return False
        if xsd_global is not None:
            return True
        else:
            return False

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any([schema.validation_attempted == 'partial' for schema in self.iter_schemas()]):
            return 'partial'
        else:
            return 'none'

    @property
    def validity(self):
        if not self.namespaces:
            return False
        if all(schema.validity == 'valid' for schema in self.iter_schemas()):
            return 'valid'
        elif any(schema.validity == 'invalid' for schema in self.iter_schemas()):
            return 'invalid'
        else:
            return 'notKnown'

    @property
    def resources(self):
        return [(schema.url, schema) for schemas in self.namespaces.values() for schema in schemas]

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.iter_globals():
            for obj in xsd_global.iter_components(xsd_classes):
                yield obj

    def iter_schemas(self):
        """Creates an iterator for the schemas registered in the instance."""
        for ns_schemas in self.namespaces.values():
            for schema in ns_schemas:
                yield schema

    def iter_globals(self):
        """
        Creates an iterator for XSD global definitions/declarations.
        """
        for global_map in self.global_maps:
            for obj in global_map.values():
                yield obj

    def register(self, schema):
        """
        Registers an XMLSchema instance.
        """
        try:
            ns_schemas = self.namespaces[schema.target_namespace]
        except KeyError:
            self.namespaces[schema.target_namespace] = [schema]
        else:
            if schema in ns_schemas:
                return
            if not any([schema.url == obj.url for obj in ns_schemas]):
                ns_schemas.append(schema)

    def clear(self, remove_schemas=False, only_unbuilt=False):
        """
        Clears the instance maps and schemas.

        :param remove_schemas: removes also the schema instances.
        :param only_unbuilt: removes only not built objects/schemas.
        """
        if only_unbuilt:
            not_built_schemas = {schema for schema in self.iter_schemas() if not schema.built}
            if not not_built_schemas:
                return

            for global_map in self.global_maps:
                for k in list(global_map.keys()):
                    obj = global_map[k]
                    if not isinstance(obj, XsdComponent) or obj.schema in not_built_schemas:
                        del global_map[k]
                        if k in self.substitution_groups:
                            del self.substitution_groups[k]
                        if k in self.constraints:
                            del self.constraints[k]

            if remove_schemas:
                namespaces = NamespaceResourcesMap()
                for uri, value in self.namespaces.items():
                    for schema in value:
                        if schema not in not_built_schemas:
                            namespaces[uri] = schema
                self.namespaces = namespaces

        else:
            for global_map in self.global_maps:
                global_map.clear()
            self.substitution_groups.clear()
            self.constraints.clear()

            if remove_schemas:
                self.namespaces.clear()

    def build(self):
        """
        Update the global maps adding the global not built registered schemas.
        """
        try:
            meta_schema = self.namespaces[XSD_NAMESPACE][0]
        except KeyError:
            raise XMLSchemaValueError("%r: %r namespace is not registered." % (self, XSD_NAMESPACE))

        not_built_schemas = [schema for schema in self.iter_schemas() if not schema.built]
        for schema in not_built_schemas:
            schema._root_elements = None

        # Load and build global declarations
        load_xsd_notations(self.notations, not_built_schemas)
        load_xsd_simple_types(self.types, not_built_schemas)
        load_xsd_attributes(self.attributes, not_built_schemas)
        load_xsd_attribute_groups(self.attribute_groups, not_built_schemas)
        load_xsd_complex_types(self.types, not_built_schemas)
        load_xsd_elements(self.elements, not_built_schemas)
        load_xsd_groups(self.groups, not_built_schemas)

        if not meta_schema.built:
            xsd_builtin_types_factory(meta_schema, self.types)

        for qname in self.notations:
            self.lookup_notation(qname)
        for qname in self.attributes:
            self.lookup_attribute(qname)
        for qname in self.attribute_groups:
            self.lookup_attribute_group(qname)
        for qname in self.types:
            self.lookup_type(qname)
        for qname in self.elements:
            self.lookup_element(qname)
        for qname in self.groups:
            self.lookup_group(qname)

        # Builds element declarations inside model groups.
        element_class = meta_schema.BUILDERS.element_class
        for schema in not_built_schemas:
            for group in schema.iter_components(XsdGroup):
                for k in range(len(group)):
                    if isinstance(group[k], tuple):
                        elem, schema = group[k]
                        group[k] = element_class(elem, schema, group)

        for schema in not_built_schemas:
            # Build substitution groups from global element declarations
            for xsd_element in schema.elements.values():
                if xsd_element.substitution_group:
                    qname = prefixed_to_qname(xsd_element.substitution_group, xsd_element.schema.namespaces)
                    if xsd_element.type.name == XSD_ANY_TYPE and 'type' not in xsd_element.elem.attrib:
                        xsd_element.type = self.elements[qname].type
                    try:
                        self.substitution_groups[qname].add(xsd_element)
                    except KeyError:
                        self.substitution_groups[qname] = {xsd_element}

            if schema.meta_schema is not None:
                # Set referenced key/unique constraints for keyrefs
                for constraint in schema.iter_components(XsdKeyref):
                    constraint.parse_refer()

                # Check for illegal restrictions
                # TODO: Fix for XsdGroup.is_restriction() method is needed before enabling this check
                # if schema.validation != 'skip':
                #     for xsd_type in schema.iter_components(XsdComplexType):
                #         xsd_type.check_restriction()

        if self.validation == 'strict' and not self.built:
            raise XMLSchemaNotBuiltError(self, "Global map %r not built!" % self)
