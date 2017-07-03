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
This module contains functions and classes for managing namespaces's  
XSD declarations/definitions.
"""
import logging as _logging
import uuid
from collections import Mapping

from .exceptions import XMLSchemaKeyError, XMLSchemaParseError
from .qnames import *
from .utils import get_namespace, URIDict
from .components import (
    get_xsd_attribute, XsdComponent, XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement,
    XsdAttributeGroup, XsdGroup, XsdNotation, iterchildren_by_tag, iterchildren_xsd_redefine
)

_logger = _logging.getLogger(__name__)


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


#
# Defines the builder function for maps lookup functions.
def create_lookup_function(map_name, xsd_classes):
    if isinstance(xsd_classes, tuple):
        types_desc = ' or '.join([c.__name__ for c in xsd_classes])
    else:
        types_desc = xsd_classes.__name__

    def lookup(global_maps, qname, **options):
        if not options:
            raise XMLSchemaValueError("cannot build components without options.")
        global_map = getattr(global_maps, map_name)
        try:
            obj = global_map[qname]
        except KeyError:
            raise XMLSchemaKeyError("missing a %s object for %r!" % (types_desc, qname))
        else:
            if isinstance(obj, xsd_classes):
                return obj

            elif isinstance(obj, tuple):
                # Not built XSD global component without redefinitions
                elem, schema = obj
                factory_or_class = options[elem.tag]
                component = factory_or_class(elem, schema, is_global=True, **options)
                global_map[qname] = component
                return component

            elif isinstance(obj, list):
                if not isinstance(obj[0], xsd_classes):
                    # Not built XSD global component with redefinitions
                    elem, schema = obj[0]
                    factory_or_class = options[elem.tag]
                    component = factory_or_class(elem, schema, is_global=True, **options)
                else:
                    # Built-in type
                    component = obj[0]

                for elem, schema in obj[1:]:
                    if not component.options:
                        component.options = options
                    component.schema = schema
                    component.elem = elem
                global_map[qname] = component
                return component

            else:
                print(repr(obj))
                raise XMLSchemaTypeError(
                    "wrong type %s for %r, a %s required." % (type(obj), qname, types_desc)
                )
    return lookup


class XsdGlobals(object):
    """
    Mediator class for related XML schema instances. It stores the global 
    declarations defined in the registered schemas. Register a schema to 
    add it's declarations to the global maps.

    :param validator: the XMLSchema class that have to be used for initializing \
    the object.
    """

    def __init__(self, validator, validation='strict'):
        self.validator = validator
        self.validation = validation

        self.namespaces = URIDict()     # Registered schemas by namespace URI
        self.resources = URIDict()      # Registered schemas by resource URI

        self.types = {}                 # Global types (both complex and simple)
        self.attributes = {}            # Global attributes
        self.attribute_groups = {}      # Attribute groups
        self.groups = {}                # Model groups
        self.notations = {}             # Notations
        self.elements = {}              # Global elements

        self.substitution_groups = {}   # Substitution groups
        self.base_elements = {}         # Global elements + global groups expansion

        self.global_maps = (self.notations, self.types, self.attributes,
                            self.attribute_groups, self.groups, self.elements)
        self.check_token = uuid.uuid4()

    def copy(self):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator)
        obj.namespaces.update(self.namespaces)
        obj.resources.update(self.resources)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.notations.update(self.notations)
        obj.elements.update(self.elements)
        obj.substitution_groups.update(self.substitution_groups)
        obj.base_elements.update(self.base_elements)
        return obj

    __copy__ = copy

    def __setattr__(self, name, value):
        if name == 'notations':
            self.lookup_notation = self._create_lookup_function(
                value, XsdNotation, **{XSD_NOTATION_TAG: self.validator.notation_class}
            )
        elif name == 'types':
            self.lookup_type = self._create_lookup_function(
                value, (XsdSimpleType, XsdComplexType), **{
                    XSD_SIMPLE_TYPE_TAG: self.validator.simple_type_factory,
                    XSD_COMPLEX_TYPE_TAG: self.validator.complex_type_class
                }
            )
        elif name == 'attributes':
            self.lookup_attribute = self._create_lookup_function(
                value, XsdAttribute, **{XSD_ATTRIBUTE_TAG: self.validator.attribute_class}
            )
        elif name == 'attribute_groups':
            self.lookup_attribute_group = self._create_lookup_function(
                value, XsdAttributeGroup,
                **{XSD_ATTRIBUTE_GROUP_TAG: self.validator.attribute_group_class}
            )
        elif name == 'groups':
            self.lookup_group = self._create_lookup_function(
                value, XsdGroup, **{XSD_GROUP_TAG: self.validator.group_class}
            )
        elif name == 'elements':
            self.lookup_element = self._create_lookup_function(
                value, XsdElement, **{XSD_ELEMENT_TAG: self.validator.element_class}
            )
        elif name == 'base_elements':
            self.lookup_base_element = self._create_lookup_function(value, XsdElement)
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
                    elem, schema = obj
                    try:
                        factory_or_class = tag_map[elem.tag]
                    except KeyError:
                        raise XMLSchemaKeyError(
                            "wrong element %r for map %r." % (elem, global_map)
                        )
                    component = factory_or_class(elem, schema, is_global=True)
                    global_map[qname] = component
                    return component

                elif isinstance(obj, list):
                    if not isinstance(obj[0], xsd_classes):
                        # Not built XSD global component with redefinitions
                        elem, schema = obj[0]
                        try:
                            factory_or_class = tag_map[elem.tag]
                        except KeyError:
                            raise XMLSchemaKeyError(
                                "wrong element %r for map %r." % (elem, global_map)
                            )
                        component = factory_or_class(elem, schema, is_global=True)
                    else:
                        # Built-in type
                        component = obj[0]

                    for elem, schema in obj[1:]:
                        component.schema = schema
                        component.elem = elem
                    global_map[qname] = component
                    return component

                else:
                    raise XMLSchemaTypeError(
                        "wrong instance %s for XSD global %r, a %s required." % (obj, qname, types_desc)
                    )
        return lookup

    def register(self, schema):
        """
        Registers an XMLSchema instance.         
        """
        if schema.uri:
            if schema.uri not in self.resources:
                self.resources[schema.uri] = schema
            elif self.resources[schema.uri] != schema:
                return

        try:
            ns_schemas = self.namespaces[schema.target_namespace]
        except KeyError:
            self.namespaces[schema.target_namespace] = [schema]
        else:
            if schema in ns_schemas:
                return
            if not any([schema.uri == obj.uri for obj in ns_schemas]):
                ns_schemas.append(schema)

    def iter_schemas(self):
        """Creates an iterator for the schemas registered in the instance."""
        for ns_schemas in self.namespaces.values():
            for schema in ns_schemas:
                yield schema

    def iter_globals(self):
        """Creates an iterator for XSD global definitions/declarations."""
        for global_map in self.global_maps:
            for obj in global_map.values():
                yield obj

    def clear(self, remove_schemas=False):
        """
        Clears the instance maps, removing also all the registered schemas 
        and cleaning the cache.
        """
        for global_map in self.global_maps:
            global_map.clear()
        self.base_elements.clear()
        self.substitution_groups.clear()

        for schema in self.iter_schemas():
            schema.errors = []

        if remove_schemas:
            self.namespaces = URIDict()
            self.resources = URIDict()

    def build(self, skip_check=False):
        """
        Builds the schemas registered in the instance, excluding
        those that are already built.
        """
        self.clear()
        if any([schema.errors for schema in self.iter_schemas()]) or \
                any([d for d in self.global_maps]) or \
                self.base_elements or self.substitution_groups:
            raise XMLSchemaValueError("%r is not cleared." % self)

        try:
            meta_schema = self.namespaces[XSD_NAMESPACE_PATH][0]
        except KeyError:
            raise XMLSchemaValueError(
                "%r: %r namespace is not registered." % (self, XSD_NAMESPACE_PATH))

        # Check schemas with meta_schema
        if self.validation == 'lax':
            for schema in self.iter_schemas():
                schema.errors.extend([e for e in meta_schema.iter_errors(schema.root)])

        # Load and build global declarations
        load_xsd_notations(self.notations, self.iter_schemas())
        load_xsd_simple_types(self.types, self.iter_schemas())
        load_xsd_attributes(self.attributes, self.iter_schemas())
        load_xsd_attribute_groups(self.attribute_groups, self.iter_schemas())
        load_xsd_complex_types(self.types, self.iter_schemas())
        load_xsd_elements(self.elements, self.iter_schemas())
        load_xsd_groups(self.groups, self.iter_schemas())

        meta_schema.builtin_types_factory(self.types)

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
        element_class = meta_schema.element_class
        for xsd_global in self.iter_globals():
            for obj in xsd_global.iter_components(XsdGroup):
                for k in range(len(obj)):
                    if isinstance(obj[k], tuple):
                        elem, schema = obj[k]
                        obj[k] = element_class(elem, schema)

        # Build substitution groups from element declarations
        for xsd_element in self.elements.values():
            if xsd_element.substitution_group:
                name = reference_to_qname(xsd_element.substitution_group, xsd_element.namespaces)
                if name[0] != '{':
                    name = get_qname(xsd_element.target_namespace, name)
                try:
                    self.substitution_groups[name].add(xsd_element)
                except KeyError:
                    self.substitution_groups[name] = {xsd_element}

        # Update base_elements
        self.base_elements.update(self.elements)
        for group in self.groups.values():
            self.base_elements.update({e.name: e for e in group.iter_elements()})

        if not skip_check:
            self.check()

    @property
    def built(self):
        if not self.namespaces:
            return False
        xsd_global = None
        for xsd_global in self.iter_globals():
            if not isinstance(xsd_global, XsdComponent):
                return False
            for xsd_group in xsd_global.iter_components(XsdGroup):
                for item in xsd_group:
                    if not isinstance(item, XsdComponent):
                        return False
        if xsd_global is not None:
            return True
        else:
            return False

    def check(self):
        self.check_token = uuid.uuid4()
        for schema in self.iter_schemas():
            schema.check()

    @property
    def valid(self):
        if not self.namespaces:
            return False
        return all([schema.valid for schema in self.iter_schemas()])


class NamespaceView(Mapping):
    """
    A read-only map for filtered access to a dictionary that stores objects mapped from QNames.
    """
    def __init__(self, qname_dict, namespace_uri):
        self.target_dict = qname_dict
        self.namespace = namespace_uri
        if namespace_uri:
            self.key_fmt = '{' + namespace_uri + '}%s'
        else:
            self.key_fmt = '%s'

    def __getitem__(self, key):
        return self.target_dict[self.key_fmt % key]

    def __len__(self):
        return len(self.as_dict())

    def __iter__(self):
        return iter(self.as_dict())

    def __repr__(self):
        return '<%s %r at %#x>' % (self.__class__.__name__, self.as_dict(), id(self))

    def __contains__(self, key):
        return self.key_fmt % key in self.target_dict

    def __eq__(self, other):
        return self.as_dict() == dict(other.items())

    def copy(self, **kwargs):
        return self.__class__(self, **kwargs)

    def as_dict(self, fqn_keys=False):
        if fqn_keys:
            return {
                k: v for k, v in self.target_dict.items()
                if self.namespace == get_namespace(k)
            }
        else:
            return {
                local_name(k): v for k, v in self.target_dict.items()
                if self.namespace == get_namespace(k)
            }
