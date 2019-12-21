# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains functions and classes for namespaces XSD declarations/definitions.
"""
from __future__ import unicode_literals
import warnings
from collections import Counter

from ..compat import string_base_type, lru_cache
from ..exceptions import XMLSchemaKeyError, XMLSchemaTypeError, XMLSchemaValueError, XMLSchemaWarning
from ..namespaces import XSD_NAMESPACE, LOCATION_HINTS, NamespaceResourcesMap
from ..qnames import XSD_REDEFINE, XSD_OVERRIDE, XSD_NOTATION, XSD_ANY_TYPE, \
    XSD_SIMPLE_TYPE, XSD_COMPLEX_TYPE, XSD_GROUP, XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, \
    XSD_ELEMENT, XSI_TYPE, get_qname, local_name, qname_to_extended

from . import XMLSchemaNotBuiltError, XMLSchemaModelError, XMLSchemaModelDepthError, \
    XsdValidator, XsdComponent, XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement, \
    XsdAttributeGroup, XsdGroup, XsdNotation, Xsd11Element, XsdKeyref, XsdAssert
from .builtins import xsd_builtin_types_factory


#
# Defines the load functions for XML Schema structures
def create_load_function(tag):

    def load_xsd_globals(xsd_globals, schemas):
        redefinitions = []
        for schema in schemas:
            target_namespace = schema.target_namespace

            for elem in filter(lambda x: x.tag in (XSD_REDEFINE, XSD_OVERRIDE), schema.root):
                location = elem.get('schemaLocation')
                if location is None:
                    continue
                for child in filter(lambda x: x.tag == tag and 'name' in x.attrib, elem):
                    qname = get_qname(target_namespace, child.attrib['name'])
                    redefinitions.append((qname, elem, child, schema, schema.includes[location]))

            for elem in filter(lambda x: x.tag == tag and 'name' in x.attrib, schema.root):
                qname = get_qname(target_namespace, elem.attrib['name'])
                if qname not in xsd_globals:
                    xsd_globals[qname] = (elem, schema)
                else:
                    try:
                        other_schema = xsd_globals[qname][1]
                    except (TypeError, IndexError):
                        pass
                    else:
                        # It's ignored or replaced in case of an override
                        if other_schema.override is schema:
                            continue
                        elif schema.override is other_schema:
                            xsd_globals[qname] = (elem, schema)
                            continue

                    msg = "global {} with name={!r} is already defined"
                    schema.parse_error(msg.format(local_name(tag), qname))

        tags = Counter([x[0] for x in redefinitions])
        for qname, elem, child, schema, redefined_schema in redefinitions:

            # Checks multiple redefinitions
            if tags[qname] > 1:
                tags[qname] = 1

                redefined_schemas = [x[-1] for x in redefinitions if x[0] == qname]
                if any(redefined_schemas.count(x) > 1 for x in redefined_schemas):
                    msg = "multiple redefinition for {} {!r}"
                    schema.parse_error(msg.format(local_name(child.tag), qname), child)
                else:
                    redefined_schemas = {x[-1]: x[-2] for x in redefinitions if x[0] == qname}
                    for rs, s in redefined_schemas.items():
                        while True:
                            try:
                                s = redefined_schemas[s]
                            except KeyError:
                                break

                            if s is rs:
                                msg = "circular redefinition for {} {!r}"
                                schema.parse_error(msg.format(local_name(child.tag), qname), child)
                                break

            if elem.tag == XSD_OVERRIDE:
                xsd_globals[qname] = (child, schema)
            else:
                # Append to a list if it's a redefine
                try:
                    xsd_globals[qname].append((child, schema))
                except KeyError:
                    schema.parse_error("not a redefinition!", child)
                except AttributeError:
                    xsd_globals[qname] = [xsd_globals[qname], (child, schema)]

    return load_xsd_globals


load_xsd_simple_types = create_load_function(XSD_SIMPLE_TYPE)
load_xsd_attributes = create_load_function(XSD_ATTRIBUTE)
load_xsd_attribute_groups = create_load_function(XSD_ATTRIBUTE_GROUP)
load_xsd_complex_types = create_load_function(XSD_COMPLEX_TYPE)
load_xsd_elements = create_load_function(XSD_ELEMENT)
load_xsd_groups = create_load_function(XSD_GROUP)
load_xsd_notations = create_load_function(XSD_NOTATION)


def create_lookup_function(xsd_classes):
    if isinstance(xsd_classes, tuple):
        types_desc = ' or '.join([c.__name__ for c in xsd_classes])
    else:
        types_desc = xsd_classes.__name__

    def lookup(qname, global_map, tag_map):
        try:
            obj = global_map[qname]
        except KeyError:
            if '{' in qname:
                raise XMLSchemaKeyError("missing an %s component for %r!" % (types_desc, qname))
            raise XMLSchemaKeyError("missing an %s component for %r! As the name has no namespace "
                                    "maybe a missing default namespace declaration." % (types_desc, qname))
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
                global_map[qname] = component = factory_or_class(elem, schema, parent=None)

                # Apply redefinitions (changing elem involve a re-parsing of the component)
                for elem, schema in obj[1:]:
                    component.redefine = component.copy()
                    component.redefine.parent = component
                    component.schema = schema
                    component.elem = elem

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

    :param validator: the origin schema class/instance used for creating the global maps.
    :param validation: the XSD validation mode to use, can be 'strict', 'lax' or 'skip'.
    """
    def __init__(self, validator, validation='strict'):
        super(XsdGlobals, self).__init__(validation)
        if not all(hasattr(validator, a) for a in ('meta_schema', 'BUILDERS_MAP')):
            raise XMLSchemaValueError("The argument {!r} is not an XSD schema validator".format(validator))

        self.validator = validator
        self.namespaces = NamespaceResourcesMap()  # Registered schemas by namespace URI
        self.missing_locations = []     # Missing or failing resource locations

        self.types = {}                 # Global types (both complex and simple)
        self.attributes = {}            # Global attributes
        self.attribute_groups = {}      # Attribute groups
        self.groups = {}                # Model groups
        self.notations = {}             # Notations
        self.elements = {}              # Global elements
        self.substitution_groups = {}   # Substitution groups
        self.identities = {}            # Identity constraints (uniqueness, keys, keyref)

        self.global_maps = (self.notations, self.types, self.attributes,
                            self.attribute_groups, self.groups, self.elements)

    def __repr__(self):
        return '%s(validator=%r, validation=%r)' % (self.__class__.__name__, self.validator, self.validation)

    def copy(self, validator=None, validation=None):
        """Makes a copy of the object."""
        obj = XsdGlobals(self.validator if validator is None else validator, validation or self.validation)
        obj.namespaces.update(self.namespaces)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.notations.update(self.notations)
        obj.elements.update(self.elements)
        obj.substitution_groups.update(self.substitution_groups)
        obj.identities.update(self.identities)
        return obj

    __copy__ = copy

    def lookup_notation(self, qname):
        return lookup_notation(qname, self.notations, self.validator.BUILDERS_MAP)

    def lookup_type(self, qname):
        return lookup_type(qname, self.types, self.validator.BUILDERS_MAP)

    def lookup_attribute(self, qname):
        return lookup_attribute(qname, self.attributes, self.validator.BUILDERS_MAP)

    def lookup_attribute_group(self, qname):
        return lookup_attribute_group(qname, self.attribute_groups, self.validator.BUILDERS_MAP)

    def lookup_group(self, qname):
        return lookup_group(qname, self.groups, self.validator.BUILDERS_MAP)

    def lookup_element(self, qname):
        return lookup_element(qname, self.elements, self.validator.BUILDERS_MAP)

    def lookup(self, tag, qname):
        """
        General lookup method for XSD global components.

        :param tag: the expanded QName of the XSD the global declaration/definition \
        (eg. '{http://www.w3.org/2001/XMLSchema}element'), that is used to select \
        the global map for lookup.
        :param qname: the expanded QName of the component to be looked-up.
        :returns: an XSD global component.
        :raises: an XMLSchemaValueError if the *tag* argument is not appropriate for a global \
        component, an XMLSchemaKeyError if the *qname* argument is not found in the global map.
        """
        if tag in (XSD_SIMPLE_TYPE, XSD_COMPLEX_TYPE):
            return self.lookup_type(qname)
        elif tag == XSD_ELEMENT:
            return self.lookup_element(qname)
        elif tag == XSD_GROUP:
            return self.lookup_group(qname)
        elif tag == XSD_ATTRIBUTE:
            return self.lookup_attribute(qname)
        elif tag == XSD_ATTRIBUTE_GROUP:
            return self.lookup_attribute_group(qname)
        elif tag == XSD_NOTATION:
            return self.lookup_notation(qname)
        else:
            raise XMLSchemaValueError("wrong tag {!r} for an XSD global definition/declaration".format(tag))

    def get_instance_type(self, type_name, base_type, namespaces):
        """
        Returns the instance XSI type from global maps, validating it with the reference base type.

        :param type_name: the XSI type attribute value, a QName in prefixed format.
        :param base_type: the XSD from which the instance type has to be derived.
        :param namespaces: a map from prefixes to namespaces.
        """
        if base_type.is_complex() and XSI_TYPE in base_type.attributes:
            base_type.attributes[XSI_TYPE].validate(type_name)

        extended_name = qname_to_extended(type_name, namespaces)
        xsi_type = lookup_type(extended_name, self.types, self.validator.BUILDERS_MAP)
        if not xsi_type.is_derived(base_type):
            raise XMLSchemaTypeError("%r is not a derived type of %r" % (xsi_type, self))
        return xsi_type

    @property
    def built(self):
        return all(schema.built for schema in self.iter_schemas())

    @property
    def unbuilt(self):
        """Property that returns a list with unbuilt components."""
        return [c for s in self.iter_schemas() for c in s.iter_components()
                if c is not s and not c.built]

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any(schema.validation_attempted == 'partial' for schema in self.iter_schemas()):
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
    def xsd_version(self):
        return self.validator.XSD_VERSION

    @property
    def builders_map(self):
        return self.validator.BUILDERS_MAP

    @property
    def all_errors(self):
        errors = []
        for schema in self.iter_schemas():
            errors.extend(schema.all_errors)
        return errors

    @property
    def constraints(self):
        """
        Old reference to identity constraints, for backward compatibility. Will be removed in v1.1.0.
        """
        return self.identities

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
            elif not any(schema.url == obj.url and schema.__class__ == obj.__class__ for obj in ns_schemas):
                ns_schemas.append(schema)

    @lru_cache(maxsize=1000)
    def load_namespace(self, namespace, build=True):
        """
        Load namespace from available location hints. Returns `True` if the namespace
        is already loaded or if the namespace can be loaded from one of the locations,
        returns `False` otherwise. Failing locations are inserted into the missing
        locations list.

        :param namespace: the namespace to load.
        :param build: if left with `True` value builds the maps after load. If the \
        build fails the resource URL is added to missing locations.
        """
        namespace = namespace.strip()
        if namespace in self.namespaces:
            return True
        elif self.validator.meta_schema is None:
            return False  # Do not load additional namespaces for meta-schema (XHTML)

        # Try from schemas location hints: usually the namespaces related to these
        # hints are already loaded during schema construction, but it's better to
        # retry once if the initial load has failed.
        for schema in self.iter_schemas():
            for url in schema.get_locations(namespace):
                if url in self.missing_locations:
                    continue

                try:
                    if schema.import_schema(namespace, url, schema.base_url) is not None:
                        if build:
                            self.build()
                except (OSError, IOError):
                    pass
                except XMLSchemaNotBuiltError:
                    self.clear(remove_schemas=True, only_unbuilt=True)
                    self.missing_locations.append(url)
                else:
                    return True

        # Try from library location hint, if there is any.
        if namespace in LOCATION_HINTS:
            url = LOCATION_HINTS[namespace]
            if url not in self.missing_locations:
                try:
                    if self.validator.import_schema(namespace, url) is not None:
                        if build:
                            self.build()
                except (OSError, IOError):
                    return False
                except XMLSchemaNotBuiltError:
                    self.clear(remove_schemas=True, only_unbuilt=True)
                    self.missing_locations.append(url)
                else:
                    return True

        return False

    def clear(self, remove_schemas=False, only_unbuilt=False):
        """
        Clears the instance maps and schemas.

        :param remove_schemas: removes also the schema instances.
        :param only_unbuilt: removes only not built objects/schemas.
        """
        if only_unbuilt:
            not_built_schemas = {s for s in self.iter_schemas() if not s.built}
            if not not_built_schemas:
                return

            for global_map in self.global_maps:
                for k in list(global_map.keys()):
                    obj = global_map[k]
                    if not isinstance(obj, XsdComponent) or obj.schema in not_built_schemas:
                        del global_map[k]
                        if k in self.substitution_groups:
                            del self.substitution_groups[k]
                        if k in self.identities:
                            del self.identities[k]

            if remove_schemas:
                namespaces = NamespaceResourcesMap()
                for uri, value in self.namespaces.items():
                    for schema in value:
                        if schema not in not_built_schemas:
                            namespaces[uri] = schema
                self.namespaces = namespaces

        else:
            del self.missing_locations[:]
            for global_map in self.global_maps:
                global_map.clear()
            self.substitution_groups.clear()
            self.identities.clear()

            if remove_schemas:
                self.namespaces.clear()

    def build(self):
        """
        Build the maps of XSD global definitions/declarations. The global maps are
        updated adding and building the globals of not built registered schemas.
        """
        try:
            meta_schema = self.namespaces[XSD_NAMESPACE][0]
        except KeyError:
            # Meta-schemas are not registered. If any of base namespaces is already registered
            # create a new meta-schema, otherwise register the meta-schemas.
            meta_schema = self.validator.meta_schema
            if meta_schema is None:
                raise XMLSchemaValueError("{!r} has not a meta-schema".format(self.validator))

            if any(ns in self.namespaces for ns in meta_schema.BASE_SCHEMAS):
                base_schemas = {k: v for k, v in meta_schema.BASE_SCHEMAS.items() if k not in self.namespaces}
                meta_schema = self.validator.create_meta_schema(meta_schema.url, base_schemas, self)
                for schema in self.iter_schemas():
                    if schema.meta_schema is not None:
                        schema.meta_schema = meta_schema
            else:
                for schema in meta_schema.maps.iter_schemas():
                    self.register(schema)

                self.types.update(meta_schema.maps.types)
                self.attributes.update(meta_schema.maps.attributes)
                self.attribute_groups.update(meta_schema.maps.attribute_groups)
                self.groups.update(meta_schema.maps.groups)
                self.notations.update(meta_schema.maps.notations)
                self.elements.update(meta_schema.maps.elements)
                self.substitution_groups.update(meta_schema.maps.substitution_groups)
                self.identities.update(meta_schema.maps.identities)

        not_built_schemas = [schema for schema in self.iter_schemas() if not schema.built]
        for schema in not_built_schemas:
            schema._root_elements = None

        # Load and build global declarations
        load_xsd_simple_types(self.types, not_built_schemas)
        load_xsd_complex_types(self.types, not_built_schemas)
        load_xsd_notations(self.notations, not_built_schemas)
        load_xsd_attributes(self.attributes, not_built_schemas)
        load_xsd_attribute_groups(self.attribute_groups, not_built_schemas)
        load_xsd_elements(self.elements, not_built_schemas)
        load_xsd_groups(self.groups, not_built_schemas)

        if not meta_schema.built:
            xsd_builtin_types_factory(meta_schema, self.types)

        if self is not meta_schema.maps:
            # Rebuild xs:anyType for maps not owned by the meta-schema
            # in order to do a correct namespace lookup for wildcards.
            self.types[XSD_ANY_TYPE] = self.validator.create_any_type()

        for qname in self.notations:
            self.lookup_notation(qname)
        for qname in self.attributes:
            self.lookup_attribute(qname)

        for qname in self.attribute_groups:
            self.lookup_attribute_group(qname)
        for schema in filter(
                lambda x: isinstance(x.default_attributes, string_base_type),
                not_built_schemas):
            try:
                schema.default_attributes = schema.maps.attribute_groups[schema.default_attributes]
            except KeyError:
                schema.default_attributes = None
                msg = "defaultAttributes={!r} doesn't match an attribute group of {!r}"
                schema.parse_error(
                    error=msg.format(schema.root.get('defaultAttributes'), schema),
                    elem=schema.root,
                    validation=schema.validation
                )

        for qname in self.types:
            self.lookup_type(qname)
        for qname in self.elements:
            self.lookup_element(qname)
        for qname in self.groups:
            self.lookup_group(qname)

        # Builds element declarations inside model groups.
        for schema in not_built_schemas:
            for group in schema.iter_components(XsdGroup):
                group.build()

        # Builds xs:keyref's key references
        for constraint in filter(lambda x: isinstance(x, XsdKeyref), self.identities.values()):
            constraint.parse_refer()

        # Build XSD 1.1 identity references and assertions
        if self.xsd_version != '1.0':
            for schema in filter(lambda x: x.meta_schema is not None, not_built_schemas):
                for e in schema.iter_components(Xsd11Element):
                    for constraint in filter(lambda x: x.ref is not None, e.identities.values()):
                        try:
                            ref = self.identities[constraint.name]
                        except KeyError:
                            schema.parse_error("Unknown %r constraint %r" % (type(constraint), constraint.name))
                        else:
                            constraint.selector = ref.selector
                            constraint.fields = ref.fields
                            if not isinstance(ref, constraint.__class__):
                                constraint.parse_error("attribute 'ref' points to a different kind constraint")
                            elif isinstance(constraint, XsdKeyref):
                                constraint.refer = ref.refer
                            constraint.ref = ref

                for assertion in schema.iter_components(XsdAssert):
                    assertion.parse_xpath_test()

        self.check(filter(lambda x: x.meta_schema is not None, not_built_schemas), self.validation)

    def check(self, schemas=None, validation='strict'):
        """
        Checks the global maps. For default checks all schemas and raises an exception at first error.

        :param schemas: optional argument with the set of the schemas to check.
        :param validation: overrides the default validation mode of the validator.
        :raise: XMLSchemaParseError
        """
        schemas = set(schemas if schemas is not None else self.iter_schemas())

        # Checks substitution groups circularities
        for qname in self.substitution_groups:
            xsd_element = self.elements[qname]
            if any(e is xsd_element for e in xsd_element.iter_substitutes()):
                msg = "circularity found for substitution group with head element %r"
                xsd_element.parse_error(msg.format(xsd_element), validation=validation)

        if validation == 'strict' and not self.built:
            raise XMLSchemaNotBuiltError(self, "global map has unbuilt components: %r" % self.unbuilt)

        # Check redefined global groups restrictions
        for group in filter(lambda x: x.schema in schemas and x.redefine is not None, self.groups.values()):
            if not any(isinstance(e, XsdGroup) and e.name == group.name for e in group) \
                    and not group.is_restriction(group.redefine):
                msg = "the redefined group is an illegal restriction of the original group"
                group.parse_error(msg, validation=validation)

        # Check complex content types models restrictions
        for xsd_global in filter(lambda x: x.schema in schemas, self.iter_globals()):
            for xsd_type in xsd_global.iter_components(XsdComplexType):
                if not isinstance(xsd_type.content_type, XsdGroup):
                    continue

                if xsd_type.derivation == 'restriction':
                    base_type = xsd_type.base_type
                    if base_type and base_type.name != XSD_ANY_TYPE and base_type.is_complex():
                        if not xsd_type.content_type.is_restriction(base_type.content_type):
                            msg = "the derived group is an illegal restriction of the base type group"
                            xsd_type.parse_error(msg, validation=validation)

                    if base_type.is_complex() and not base_type.open_content and \
                            xsd_type.open_content and xsd_type.open_content.mode != 'none':
                        group = xsd_type.schema.create_any_content_group(
                            parent=xsd_type,
                            any_element=xsd_type.open_content.any_element
                        )
                        if not group.is_restriction(base_type.content_type):
                            msg = "restriction has an open content but base type has not"
                            group.parse_error(msg, validation=validation)

                try:
                    xsd_type.content_type.check_model()
                except XMLSchemaModelDepthError:
                    msg = "cannot verify the content model of {!r} due to maximum recursion depth exceeded"
                    xsd_type.schema.warnings.append(msg.format(xsd_type))
                    warnings.warn(msg, XMLSchemaWarning, stacklevel=4)
                except XMLSchemaModelError as err:
                    if validation == 'strict':
                        raise
                    xsd_type.errors.append(err)
