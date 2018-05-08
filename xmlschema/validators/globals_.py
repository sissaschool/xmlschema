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
import re
from ..exceptions import XMLSchemaKeyError, XMLSchemaTypeError, XMLSchemaValueError
from ..namespaces import XSD_NAMESPACE, URIDict
from ..qnames import (
    get_qname, local_name, reference_to_qname, XSD_INCLUDE_TAG, XSD_IMPORT_TAG,
    XSD_REDEFINE_TAG, XSD_NOTATION_TAG, XSD_SIMPLE_TYPE_TAG, XSD_COMPLEX_TYPE_TAG,
    XSD_GROUP_TAG, XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ELEMENT_TAG,
    XSD_ANY_TYPE
)
from .exceptions import XMLSchemaParseError, XMLSchemaNotBuiltError
from .parseutils import get_xsd_attribute
from .xsdbase import XsdBaseComponent
from . import (
    XsdKeyref, XsdComponent, XsdAttribute, XsdSimpleType, XsdComplexType,
    XsdElement, XsdAttributeGroup, XsdGroup, XsdNotation
)


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
                raise XMLSchemaParseError("not a redefinition!", obj[0])
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


class XsdGlobals(XsdBaseComponent):
    """
    Mediator class for related XML schema instances. It stores the global
    declarations defined in the registered schemas. Register a schema to
    add it's declarations to the global maps.

    :param validator: the XMLSchema class that have to be used for initializing \
    the object.
    """

    def __init__(self, validator):
        super(XsdGlobals, self).__init__()
        self.validator = validator

        self.namespaces = URIDict()     # Registered schemas by namespace URI

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

    def copy(self):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator)
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

    def __setattr__(self, name, value):
        if name == 'notations':
            self.lookup_notation = self._create_lookup_function(
                value, XsdNotation, **{XSD_NOTATION_TAG: self.validator.BUILDERS.notation_class}
            )
        elif name == 'types':
            self.lookup_type = self._create_lookup_function(
                value, (XsdSimpleType, XsdComplexType), **{
                    XSD_SIMPLE_TYPE_TAG: self.validator.BUILDERS.simple_type_factory,
                    XSD_COMPLEX_TYPE_TAG: self.validator.BUILDERS.complex_type_class
                }
            )
        elif name == 'attributes':
            self.lookup_attribute = self._create_lookup_function(
                value, XsdAttribute, **{XSD_ATTRIBUTE_TAG: self.validator.BUILDERS.attribute_class}
            )
        elif name == 'attribute_groups':
            self.lookup_attribute_group = self._create_lookup_function(
                value, XsdAttributeGroup,
                **{XSD_ATTRIBUTE_GROUP_TAG: self.validator.BUILDERS.attribute_group_class}
            )
        elif name == 'groups':
            self.lookup_group = self._create_lookup_function(
                value, XsdGroup, **{XSD_GROUP_TAG: self.validator.BUILDERS.group_class}
            )
        elif name == 'elements':
            self.lookup_element = self._create_lookup_function(
                value, XsdElement, **{XSD_ELEMENT_TAG: self.validator.BUILDERS.element_class}
            )
        super(XsdGlobals, self).__setattr__(name, value)

    @staticmethod
    def _create_lookup_function(global_map, xsd_classes, **tag_map):
        if isinstance(xsd_classes, tuple):
            types_desc = ' or '.join([c.__name__ for c in xsd_classes])
        else:
            types_desc = xsd_classes.__name__

        def lookup(qname):
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
                    global_map[qname] = factory_or_class(elem, schema, is_global=True)
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
                        global_map[qname] = factory_or_class(elem, schema, is_global=True)
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

    def iter_schemas(self):
        """Creates an iterator for the schemas registered in the instance."""
        for ns_schemas in self.namespaces.values():
            for schema in ns_schemas:
                yield schema

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.iter_globals():
            for obj in xsd_global.iter_components(xsd_classes):
                yield obj

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

    def clear(self, remove_schemas=False):
        """
        Clears the instance maps, removing also all the registered schemas
        and cleaning the cache.
        """
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
            raise XMLSchemaValueError(
                "%r: %r namespace is not registered." % (self, XSD_NAMESPACE))

        not_built_schemas = [schema for schema in self.iter_schemas() if not schema.built]

        # Load and build global declarations
        load_xsd_notations(self.notations, not_built_schemas)
        load_xsd_simple_types(self.types, not_built_schemas)
        load_xsd_attributes(self.attributes, not_built_schemas)
        load_xsd_attribute_groups(self.attribute_groups, not_built_schemas)
        load_xsd_complex_types(self.types, not_built_schemas)
        load_xsd_elements(self.elements, not_built_schemas)
        load_xsd_groups(self.groups, not_built_schemas)

        if not meta_schema.built:
            meta_schema.BUILDERS.builtin_types_factory(meta_schema, self.types)

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
                        group[k] = element_class(elem, schema)

        for schema in not_built_schemas:
            # Build substitution groups from global element declarations
            for xsd_element in schema.elements.values():
                if xsd_element.substitution_group:
                    qname = reference_to_qname(xsd_element.substitution_group, xsd_element.schema.namespaces)
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
                # TODO: Complete is_restriction() methods before enabling this check
                # if schema.validation != 'skip':
                #     for xsd_type in schema.iter_components(XsdComplexType):
                #         xsd_type.check_restriction()

        if not self.built:
            raise XMLSchemaNotBuiltError("Global map %r not built!" % self)
