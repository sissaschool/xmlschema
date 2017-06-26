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

from .exceptions import XMLSchemaKeyError, XMLSchemaParseError
from .qnames import *
from .utils import get_namespace, URIDict
from .components import (
    get_xsd_attribute, XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement,
    XsdAttributeGroup, XsdGroup, XsdNotation, iterchildren_by_tag, iterchildren_xsd_redefine
)

_logger = _logging.getLogger(__name__)


#
# Defines the update functions for XML Schema structures
def create_load_function(filter_function):

    def load_xsd_globals(xsd_globals, schemas):
        redefinitions = []
        for schema in schemas:
            if schema.built:
                continue

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

    def lookup(global_maps, qname, **kwargs):
        global_map = getattr(global_maps, map_name)
        try:
            obj = global_map[qname]
        except KeyError:
            raise XMLSchemaKeyError("missing a %s object for %r!" % (types_desc, qname))
        else:
            if isinstance(obj, xsd_classes):
                if obj.built:
                    return obj
                else:
                    elem, schema = obj.elem, obj.schema
                    factory_function = kwargs[obj.FACTORY_KWARG]
                    obj2 = factory_function(elem, schema, obj, is_global=True, **kwargs)
                    global_map[qname] = obj2
                    return obj2
            elif isinstance(obj, (tuple, list)) and obj and isinstance(obj[0], xsd_classes):
                # More complex: redefine case
                start = int(isinstance(obj[0], xsd_classes))
                xsd_instance = obj[0] if start else None    # No
                for k in range(start, len(obj)):
                    elem, schema = obj[k]

                    if isinstance(xsd_classes, (tuple, list)):
                        for xsd_class in xsd_classes:
                            if elem.tag == xsd_class.XSD_GLOBAL_TAG:
                                factory_function = kwargs[xsd_class.FACTORY_KWARG]
                                break
                        else:
                            raise XMLSchemaValueError("Element not compatible!")
                    else:
                        factory_function = kwargs[xsd_classes.FACTORY_KWARG]

                    xsd_instance = factory_function(
                        elem, schema, xsd_instance, is_global=True, **kwargs
                    )
                    obj[0] = xsd_instance
                global_map[qname] = xsd_instance
                return obj[0]

            elif isinstance(obj, (tuple, list)) and len(obj) == 2:
                # print("Build %r(%r)" % (xsd_classes, qname))
                # global_map[qname] = None
                # The map entry is a couple with etree element and reference schema.
                elem, schema = obj
                if isinstance(xsd_classes, (tuple, list)):
                    for xsd_class in xsd_classes:
                        if elem.tag == xsd_class.XSD_GLOBAL_TAG:
                            factory_function = kwargs[xsd_class.FACTORY_KWARG]
                            break
                    else:
                        raise XMLSchemaValueError("Element not compatible!")
                else:
                    factory_function = kwargs[xsd_classes.FACTORY_KWARG]

                obj = factory_function(elem, schema, is_global=True, **kwargs)
                global_map[qname] = obj
                return obj
            else:
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

    def __init__(self, validator):
        self.validator = validator
        self.namespaces = URIDict()     # Registered schemas by namespace URI
        self.resources = URIDict()      # Registered schemas by resource URI

        self.types = {}                 # Global types (both complex and simple)
        self.attributes = {}            # Global attributes
        self.attribute_groups = {}      # Attribute groups
        self.groups = {}                # Model groups
        self.substitution_groups = {}   # Substitution groups
        self.notations = {}             # Notations
        self.elements = {}              # Global elements
        self.base_elements = {}         # Global elements + global groups expansion
        self._view_cache = {}           # Cache for namespace views
        self.errors = []                # Building errors

        self.types.update(validator.BUILTIN_TYPES)
        self.global_maps = (self.notations, self.types, self.attributes,
                            self.attribute_groups, self.groups, self.elements)
        self.built_token = uuid.uuid4()
        self.checked_token = uuid.uuid4()

    def copy(self):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator)
        obj.namespaces.update(self.namespaces)
        obj.resources.update(self.resources)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.substitution_groups.update(self.substitution_groups)
        obj.notations.update(self.notations)
        obj.elements.update(self.elements)
        obj.base_elements.update(self.base_elements)
        obj.errors.extend(self.errors)
        return obj

    __copy__ = copy

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

    def get_globals(self, map_name, namespace, fqn_keys=True):
        """
        Get a global map for a namespace. The map is cached by the instance.

        :param map_name: can be the name of one of the XSD global maps \
        (``'attributes'``, ``'attribute_groups'``, ``'elements'``, \
        ``'groups'``, ``'elements'``).
        :param namespace: is an optional mapping from namespace prefix \
        to full qualified name. 
        :param fqn_keys: if ``True`` the returned map's keys are fully \
        qualified names, if ``False`` the returned map's keys are local names.
        :return: a dictionary.
        """
        try:
            return self._view_cache[(map_name, namespace, fqn_keys)]
        except KeyError:
            if fqn_keys:
                view = self._view_cache[(map_name, namespace, fqn_keys)] = {
                    k: v for k, v in getattr(self, map_name).items()
                    if namespace == get_namespace(k)
                }
            else:
                view = self._view_cache[(map_name, namespace, fqn_keys)] = {
                    local_name(k): v for k, v in getattr(self, map_name).items()
                    if namespace == get_namespace(k)
                }
            return view

    lookup_type = create_lookup_function('types', (XsdSimpleType, XsdComplexType))
    lookup_attribute = create_lookup_function('attributes', XsdAttribute)
    lookup_attribute_group = create_lookup_function('attribute_groups', XsdAttributeGroup)
    lookup_group = create_lookup_function('groups', XsdGroup)
    lookup_notation = create_lookup_function('notations', XsdNotation)
    lookup_element = create_lookup_function('elements', XsdElement)
    lookup_base_element = create_lookup_function('base_elements', XsdElement)

    def iter_schemas(self):
        """Creates an iterator for the schemas registered in the instance."""
        for ns_schemas in self.namespaces.values():
            for schema in ns_schemas:
                yield schema

    def iter_globals(self):
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
        self._view_cache.clear()
        del self.errors[:]

        self.types.update(self.validator.BUILTIN_TYPES)
        for schema in self.iter_schemas():
            schema.built = False

        if remove_schemas:
            self.namespaces = URIDict()
            self.resources = URIDict()

    def build(self):
        """
        Builds the schemas registered in the instance, excluding
        those that are already built.
        """
        kwargs = self.validator.OPTIONS.copy()

        # Load and build global declarations
        load_xsd_notations(self.notations, self.iter_schemas())
        load_xsd_simple_types(self.types, self.iter_schemas())
        load_xsd_attributes(self.attributes, self.iter_schemas())
        load_xsd_attribute_groups(self.attribute_groups, self.iter_schemas())
        load_xsd_complex_types(self.types, self.iter_schemas())
        load_xsd_elements(self.elements, self.iter_schemas())
        load_xsd_groups(self.groups, self.iter_schemas())

        for qname in self.notations:
            self.lookup_notation(qname, **kwargs)
        for qname in self.attributes:
            self.lookup_attribute(qname, **kwargs)
        for qname in self.attribute_groups:
            self.lookup_attribute_group(qname, **kwargs)
        for qname in self.types:
            self.lookup_type(qname, **kwargs)
        for qname in self.elements:
            self.lookup_element(qname, **kwargs)
        for qname in self.groups:
            self.lookup_group(qname, **kwargs)

        for qname in self.groups:
            self.lookup_group(qname, parse_local_groups=True, **kwargs)
        for qname in self.types:
            self.lookup_type(qname, parse_local_groups=True, **kwargs)
        for qname in self.elements:
            self.lookup_element(qname, parse_local_groups=True, **kwargs)

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
        self._view_cache.clear()

    def check(self):
        for xsd_global in self.iter_globals():
            xsd_global.check()

        for e in self.iter_globals():
            print(repr(e.validity), repr(e.validation_attempted), repr(e))

        for schema in self.iter_schemas():
            schema.check()

        if self.errors:
            if len(self.errors) == 2:
                raise self.errors[0]
            else:
                err = self.errors[0]
                msg = "found %d errors parsing the schema: %s"
                raise XMLSchemaParseError(
                    msg % (len(self.errors), err.message),
                    obj=self.errors[0].obj
                )
