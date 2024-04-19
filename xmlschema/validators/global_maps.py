#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
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
import warnings
from collections import Counter
from typing import cast, Any, Callable, Dict, List, Iterable, Iterator, \
    MutableMapping, Optional, Set, Union, Tuple, Type, TYPE_CHECKING

from ..exceptions import XMLSchemaKeyError, XMLSchemaTypeError, \
    XMLSchemaValueError, XMLSchemaWarning
from ..names import XSD_NAMESPACE, XSD_REDEFINE, XSD_OVERRIDE, XSD_NOTATION, \
    XSD_ANY_TYPE, XSD_SIMPLE_TYPE, XSD_COMPLEX_TYPE, XSD_GROUP, \
    XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ELEMENT, XSI_TYPE
from ..aliases import ComponentClassType, ElementType, SchemaType, BaseXsdType, \
    SchemaGlobalType
from ..helpers import get_qname, local_name, get_extended_qname
from ..namespaces import NamespaceResourcesMap
from ..translation import gettext as _

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaModelError, XMLSchemaModelDepthError, \
    XMLSchemaParseError
from .xsdbase import XsdValidator, XsdComponent
from .builtins import xsd_builtin_types_factory
from .models import check_model
from . import XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement, XsdAttributeGroup, \
    XsdGroup, XsdNotation, XsdIdentity, XsdAssert, XsdUnion, XsdAtomicRestriction

if TYPE_CHECKING:
    from .schemas import XMLSchemaBase


#
# Defines the load functions for XML Schema structures
def create_load_function(tag: str) \
        -> Callable[[Dict[str, Any], Iterable[SchemaType]], None]:

    def load_xsd_globals(xsd_globals: Dict[str, Any],
                         schemas: Iterable[SchemaType]) -> None:
        redefinitions = []
        for schema in schemas:
            target_namespace = schema.target_namespace

            for elem in schema.root:
                if elem.tag not in {XSD_REDEFINE, XSD_OVERRIDE}:
                    continue

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

                    msg = _("global {0} with name={1!r} is already defined")
                    schema.parse_error(
                        error=msg.format(local_name(tag), qname),
                        elem=elem
                    )

        redefined_names = Counter(x[0] for x in redefinitions)
        for qname, elem, child, schema, redefined_schema in reversed(redefinitions):

            # Checks multiple redefinitions
            if redefined_names[qname] > 1:
                redefined_names[qname] = 1

                redefined_schemas: Any
                redefined_schemas = [x[-1] for x in redefinitions if x[0] == qname]
                if any(redefined_schemas.count(x) > 1 for x in redefined_schemas):
                    msg = _("multiple redefinition for {0} {1!r}")
                    schema.parse_error(
                        error=msg.format(local_name(child.tag), qname),
                        elem=child
                    )
                else:
                    redefined_schemas = {x[-1]: x[-2] for x in redefinitions if x[0] == qname}
                    for rs, s in redefined_schemas.items():
                        while True:
                            try:
                                s = redefined_schemas[s]
                            except KeyError:
                                break

                            if s is rs:
                                msg = _("circular redefinition for {0} {1!r}")
                                schema.parse_error(
                                    error=msg.format(local_name(child.tag), qname),
                                    elem=child
                                )
                                break

            if elem.tag == XSD_OVERRIDE:
                # Components which match nothing in the target schema are ignored. See the
                # period starting with "Source declarations not present in the target set"
                # of the paragraph https://www.w3.org/TR/xmlschema11-1/#override-schema.
                if qname in xsd_globals:
                    xsd_globals[qname] = (child, schema)
            else:
                # Append to a list if it's a redefinition
                try:
                    xsd_globals[qname].append((child, schema))
                except KeyError:
                    schema.parse_error(_("not a redefinition!"), child)
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


class XsdGlobals(XsdValidator):
    """
    Mediator class for related XML schema instances. It stores the global
    declarations defined in the registered schemas. Register a schema to
    add its declarations to the global maps.

    :param validator: the origin schema class/instance used for creating the global maps.
    :param validation: the XSD validation mode to use, can be 'strict', 'lax' or 'skip'.
    """
    types: Dict[str, Union[BaseXsdType, Tuple[ElementType, SchemaType]]]
    attributes: Dict[str, Union[XsdAttribute, Tuple[ElementType, SchemaType]]]
    attribute_groups: Dict[str, Union[XsdAttributeGroup, Tuple[ElementType, SchemaType]]]
    groups: Dict[str, Union[XsdGroup, Tuple[ElementType, SchemaType]]]
    notations: Dict[str, Union[XsdNotation, Tuple[ElementType, SchemaType]]]
    elements: Dict[str, Union[XsdElement, Tuple[ElementType, SchemaType]]]

    substitution_groups: Dict[str, Set[XsdElement]]
    identities: Dict[str, XsdIdentity]
    global_maps: Tuple[Dict[str, Any], ...]

    missing_locations: List[str]

    _loaded_schemas: Set['XMLSchemaBase']
    _lookup_function_resolver = {
        XSD_SIMPLE_TYPE: 'lookup_type',
        XSD_COMPLEX_TYPE: 'lookup_type',
        XSD_ELEMENT: 'lookup_element',
        XSD_GROUP: 'lookup_group',
        XSD_ATTRIBUTE: 'lookup_attribute',
        XSD_ATTRIBUTE_GROUP: 'lookup_attribute_group',
        XSD_NOTATION: 'lookup_notation',
    }

    def __init__(self, validator: SchemaType, validation: str = 'strict') -> None:
        super().__init__(validation)

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

        self._builders: Dict[str, Callable[[ElementType, SchemaType], Any]] = {
            XSD_NOTATION: validator.xsd_notation_class,
            XSD_SIMPLE_TYPE: validator.simple_type_factory,
            XSD_COMPLEX_TYPE: validator.xsd_complex_type_class,
            XSD_ATTRIBUTE: validator.xsd_attribute_class,
            XSD_ATTRIBUTE_GROUP: validator.xsd_attribute_group_class,
            XSD_GROUP: validator.xsd_group_class,
            XSD_ELEMENT: validator.xsd_element_class,
        }
        self._loaded_schemas = set()

    def __repr__(self) -> str:
        return '%s(validator=%r, validation=%r)' % (
            self.__class__.__name__, self.validator, self.validation
        )

    def copy(self, validator: Optional[SchemaType] = None,
             validation: Optional[str] = None) -> 'XsdGlobals':
        """
        Creates a shallow copy of the object. The associated schemas do not change
        the original global maps. This is useful for sharing the same meta-schema
        without copying the full tree objects, saving time and memory.
        """
        obj = self.__class__(
            validator=self.validator if validator is None else validator,
            validation=validation or self.validation
        )
        obj.namespaces.update(self.namespaces)
        obj.types.update(self.types)
        obj.attributes.update(self.attributes)
        obj.attribute_groups.update(self.attribute_groups)
        obj.groups.update(self.groups)
        obj.notations.update(self.notations)
        obj.elements.update(self.elements)
        obj.substitution_groups.update(self.substitution_groups)
        obj.identities.update(self.identities)
        obj._loaded_schemas.update(self._loaded_schemas)
        return obj

    __copy__ = copy

    def lookup(self, tag: str, qname: str) -> SchemaGlobalType:
        """
        General lookup method for XSD global components.

        :param tag: the expanded QName of the XSD the global declaration/definition \
        (e.g. '{http://www.w3.org/2001/XMLSchema}element'), that is used to select \
        the global map for lookup.
        :param qname: the expanded QName of the component to be looked-up.
        :returns: an XSD global component.
        :raises: an XMLSchemaValueError if the *tag* argument is not appropriate for a global \
        component, an XMLSchemaKeyError if the *qname* argument is not found in the global map.
        """
        lookup_function: Callable[[str], SchemaGlobalType]
        try:
            lookup_function = getattr(self, self._lookup_function_resolver[tag])
        except KeyError:
            msg = _("wrong tag {!r} for an XSD global definition/declaration")
            raise XMLSchemaValueError(msg.format(tag)) from None
        else:
            return lookup_function(qname)

    def lookup_notation(self, qname: str) -> XsdNotation:
        try:
            obj = self.notations[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'xs:notation {qname!r} not found')
        else:
            if isinstance(obj, XsdNotation):
                return obj
            return cast(XsdNotation, self._build_global(obj, qname, self.notations))

    def lookup_type(self, qname: str) -> BaseXsdType:
        try:
            obj = self.types[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'global xs:simpleType/xs:complexType {qname!r} not found')
        else:
            if isinstance(obj, (XsdSimpleType, XsdComplexType)):
                return obj
            return cast(BaseXsdType, self._build_global(obj, qname, self.types))

    def lookup_attribute(self, qname: str) -> XsdAttribute:
        try:
            obj = self.attributes[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'global xs:attribute {qname!r} not found')
        else:
            if isinstance(obj, XsdAttribute):
                return obj
            return cast(XsdAttribute, self._build_global(obj, qname, self.attributes))

    def lookup_attribute_group(self, qname: str) -> XsdAttributeGroup:
        try:
            obj = self.attribute_groups[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'global xs:attributeGroup {qname!r} not found')
        else:
            if isinstance(obj, XsdAttributeGroup):
                return obj
            return cast(XsdAttributeGroup, self._build_global(obj, qname, self.attribute_groups))

    def lookup_group(self, qname: str) -> XsdGroup:
        try:
            obj = self.groups[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'global xs:group {qname!r} not found')
        else:
            if isinstance(obj, XsdGroup):
                return obj
            return cast(XsdGroup, self._build_global(obj, qname, self.groups))

    def lookup_element(self, qname: str) -> XsdElement:
        try:
            obj = self.elements[qname]
        except KeyError:
            raise XMLSchemaKeyError(f'global xs:element {qname!r} not found')
        else:
            if isinstance(obj, XsdElement):
                return obj
            return cast(XsdElement, self._build_global(obj, qname, self.elements))

    def _build_global(self, obj: Any, qname: str,
                      global_map: Dict[str, Any]) -> Any:
        factory_or_class: Callable[[ElementType, SchemaType], Any]

        if isinstance(obj, tuple):
            # Not built XSD global component without redefinitions
            try:
                elem, schema = obj
            except ValueError:
                return obj[0]  # Circular build, simply return (elem, schema) couple

            try:
                factory_or_class = self._builders[elem.tag]
            except KeyError:
                msg = _("wrong element {0!r} for map {1!r}")
                raise XMLSchemaKeyError(msg.format(elem, global_map))

            global_map[qname] = obj,  # Encapsulate into a tuple to catch circular builds
            global_map[qname] = factory_or_class(elem, schema)
            return global_map[qname]

        elif isinstance(obj, list):
            # Not built XSD global component with redefinitions
            try:
                elem, schema = obj[0]
            except ValueError:
                return obj[0][0]  # Circular build, simply return (elem, schema) couple

            try:
                factory_or_class = self._builders[elem.tag]
            except KeyError:
                msg = _("wrong element {0!r} for map {1!r}")
                raise XMLSchemaKeyError(msg.format(elem, global_map))

            global_map[qname] = obj[0],  # To catch circular builds
            global_map[qname] = component = factory_or_class(elem, schema)

            # Apply redefinitions (changing elem involve reparse of the component)
            for elem, schema in obj[1:]:
                if component.schema.target_namespace != schema.target_namespace:
                    msg = _("redefined schema {!r} has a different targetNamespace")
                    raise XMLSchemaValueError(msg.format(schema))

                component.redefine = component.copy()
                component.redefine.parent = component
                component.schema = schema
                component.elem = elem

            return global_map[qname]

        else:
            msg = _("unexpected instance {!r} in global map")
            raise XMLSchemaTypeError(msg.format(obj))

    def get_instance_type(self, type_name: str, base_type: BaseXsdType,
                          namespaces: MutableMapping[str, str]) -> BaseXsdType:
        """
        Returns the instance XSI type from global maps, validating it with the reference base type.

        :param type_name: the XSI type attribute value, a QName in prefixed format.
        :param base_type: the XSD from which the instance type has to be derived.
        :param namespaces: a mapping from prefixes to namespaces.
        """
        if isinstance(base_type, XsdComplexType) and XSI_TYPE in base_type.attributes:
            xsd_attribute = cast(XsdAttribute, base_type.attributes[XSI_TYPE])
            xsd_attribute.validate(type_name)

        extended_name = get_extended_qname(type_name, namespaces)
        xsi_type = self.lookup_type(extended_name)
        if xsi_type.is_derived(base_type):
            return xsi_type
        elif isinstance(base_type, XsdSimpleType) and \
                base_type.is_union() and not base_type.facets:
            # Can be valid only if the union doesn't have facets, see:
            #   https://www.w3.org/Bugs/Public/show_bug.cgi?id=4065
            if isinstance(base_type, XsdAtomicRestriction) and \
                    isinstance(base_type.primitive_type, XsdUnion):
                if xsi_type in base_type.primitive_type.member_types:
                    return xsi_type
            elif isinstance(base_type, XsdUnion):
                if xsi_type in base_type.member_types:
                    return xsi_type

        msg = _("{0!r} cannot substitute {1!r}")
        raise XMLSchemaTypeError(msg.format(xsi_type, base_type))

    @property
    def built(self) -> bool:
        return all(schema.built for schema in self.iter_schemas())

    @property
    def unbuilt(self) -> List[Union[XsdComponent, SchemaType]]:
        """Property that returns a list with unbuilt components."""
        return [c for s in self.iter_schemas() for c in s.iter_components()
                if c is not s and not c.built]

    @property
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif any(schema.validation_attempted == 'partial' for schema in self.iter_schemas()):
            return 'partial'
        else:
            return 'none'

    @property
    def validity(self) -> str:
        if not self.namespaces:
            return 'notKnown'
        if all(schema.validity == 'valid' for schema in self.iter_schemas()):
            return 'valid'
        elif any(schema.validity == 'invalid' for schema in self.iter_schemas()):
            return 'invalid'
        else:
            return 'notKnown'

    @property
    def xsd_version(self) -> str:
        return self.validator.XSD_VERSION

    @property
    def all_errors(self) -> List[XMLSchemaParseError]:
        errors = []
        for schema in self.iter_schemas():
            errors.extend(schema.all_errors)
        return errors

    def create_bindings(self, *bases: Type[Any], **attrs: Any) -> None:
        """Creates data object bindings for the XSD elements of built schemas."""
        for xsd_element in self.iter_components(xsd_classes=XsdElement):
            assert isinstance(xsd_element, XsdElement)
            if xsd_element.target_namespace != XSD_NAMESPACE:
                xsd_element.get_binding(*bases, replace_existing=True, **attrs)

    def clear_bindings(self) -> None:
        for xsd_element in self.iter_components(xsd_classes=XsdElement):
            assert isinstance(xsd_element, XsdElement)
            xsd_element.binding = None

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[Union['XsdGlobals', XsdComponent]]:
        """Creates an iterator for the XSD components of built schemas."""
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.iter_globals():
            yield from xsd_global.iter_components(xsd_classes)

    def iter_globals(self) -> Iterator[SchemaGlobalType]:
        """Creates an iterator for the XSD global components of built schemas."""
        for global_map in self.global_maps:
            yield from global_map.values()

    def iter_schemas(self) -> Iterator[SchemaType]:
        """Creates an iterator for the registered schemas."""
        for schemas in self.namespaces.values():
            yield from schemas

    def register(self, schema: SchemaType) -> None:
        """Registers an XMLSchema instance."""
        try:
            ns_schemas = self.namespaces[schema.target_namespace]
        except KeyError:
            self.namespaces[schema.target_namespace] = [schema]
        else:
            if schema in ns_schemas:
                return
            elif schema.url is None:
                # only by multi-source init or add_schema() by user initiative
                ns_schemas.append(schema)
            elif not any(schema.url == obj.url and schema.__class__ is obj.__class__
                         for obj in ns_schemas):
                ns_schemas.append(schema)

    def load_namespace(self, namespace: str, build: bool = True) -> bool:
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
                except OSError:
                    pass
                except XMLSchemaNotBuiltError:
                    self.clear(remove_schemas=True, only_unbuilt=True)
                    self.missing_locations.append(url)
                else:
                    return True

        # Try from library location hint, if there is any.
        if namespace in self.validator.fallback_locations:
            url = self.validator.fallback_locations[namespace]
            if url not in self.missing_locations:
                try:
                    if self.validator.import_schema(namespace, url) is not None:
                        if build:
                            self.build()
                except OSError:
                    return False
                except XMLSchemaNotBuiltError:
                    self.clear(remove_schemas=True, only_unbuilt=True)
                    self.missing_locations.append(url)
                else:
                    return True

        return False

    def clear(self, remove_schemas: bool = False, only_unbuilt: bool = False) -> None:
        """
        Clears the instance maps and schemas.

        :param remove_schemas: removes also the schema instances.
        :param only_unbuilt: removes only not built objects/schemas.
        """
        global_map: Dict[str, XsdComponent]
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

            self._loaded_schemas.difference_update(not_built_schemas)

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
            self._loaded_schemas.clear()

            if remove_schemas:
                self.namespaces.clear()

    def build(self) -> None:
        """
        Build the maps of XSD global definitions/declarations. The global maps are
        updated adding and building the globals of not built registered schemas.
        """
        meta_schema: Optional['XMLSchemaBase']
        try:
            meta_schema = self.namespaces[XSD_NAMESPACE][0]
        except KeyError:
            if self.validator.meta_schema is None:
                msg = _("missing XSD namespace in meta-schema instance {!r}")
                raise XMLSchemaValueError(msg.format(self.validator))
            meta_schema = None

        if meta_schema is None or meta_schema.meta_schema is not None:
            # XSD namespace not imported or XSD namespace not managed by a meta-schema.
            # Creates a new meta-schema instance from the XSD meta-schema source and
            # replaces the default meta-schema instance in all registered schemas.
            meta_schema = self.validator.create_meta_schema(global_maps=self)

            for schema in self.iter_schemas():
                if schema.meta_schema is not None:
                    schema.meta_schema = meta_schema
        else:
            if not self.types and meta_schema.maps is not self:
                for source_map, target_map in zip(meta_schema.maps.global_maps, self.global_maps):
                    target_map.update(source_map)
                self._loaded_schemas.update(meta_schema.maps._loaded_schemas)

        not_loaded_schemas = [s for s in self.iter_schemas() if s not in self._loaded_schemas]
        for schema in not_loaded_schemas:
            schema._root_elements = None
            self._loaded_schemas.add(schema)

        # Load and build global declarations
        load_xsd_simple_types(self.types, not_loaded_schemas)
        load_xsd_complex_types(self.types, not_loaded_schemas)
        load_xsd_notations(self.notations, not_loaded_schemas)
        load_xsd_attributes(self.attributes, not_loaded_schemas)
        load_xsd_attribute_groups(self.attribute_groups, not_loaded_schemas)
        load_xsd_elements(self.elements, not_loaded_schemas)
        load_xsd_groups(self.groups, not_loaded_schemas)

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
        for schema in not_loaded_schemas:
            if not isinstance(schema.default_attributes, str):
                continue

            try:
                attributes = schema.maps.attribute_groups[schema.default_attributes]
            except KeyError:
                schema.default_attributes = None
                msg = _("defaultAttributes={0!r} doesn't match any attribute group of {1!r}")
                schema.parse_error(
                    error=msg.format(schema.root.get('defaultAttributes'), schema),
                    elem=schema.root
                )
            else:
                schema.default_attributes = cast(XsdAttributeGroup, attributes)

        for qname in self.types:
            self.lookup_type(qname)
        for qname in self.elements:
            self.lookup_element(qname)
        for qname in self.groups:
            self.lookup_group(qname)

        # Build element declarations inside model groups.
        for schema in not_loaded_schemas:
            for group in schema.iter_components(XsdGroup):
                group.build()

        # Build identity references and XSD 1.1 assertions
        for schema in not_loaded_schemas:
            for obj in schema.iter_components((XsdIdentity, XsdAssert)):
                obj.build()

        self.check(filter(lambda x: x.meta_schema is not None, not_loaded_schemas), self.validation)

    def check(self, schemas: Optional[Iterable[SchemaType]] = None,
              validation: str = 'strict') -> None:
        """
        Checks the global maps. For default checks all schemas and raises an
        exception at first error.

        :param schemas: optional argument with the set of the schemas to check.
        :param validation: overrides the default validation mode of the validator.
        :raise: XMLSchemaParseError
        """
        _schemas = set(schemas if schemas is not None else self.iter_schemas())

        # Checks substitution groups circularity
        for qname in self.substitution_groups:
            xsd_element = self.elements[qname]
            assert isinstance(xsd_element, XsdElement), _("global element not built!")
            if any(e is xsd_element for e in xsd_element.iter_substitutes()):
                msg = _("circularity found for substitution group with head element {}")
                xsd_element.parse_error(msg.format(xsd_element), validation=validation)

        if validation == 'strict' and not self.built:
            raise XMLSchemaNotBuiltError(
                self, _("global map has unbuilt components: %r") % self.unbuilt
            )

        # Check redefined global groups restrictions
        for group in self.groups.values():
            assert isinstance(group, XsdGroup), _("global group not built!")
            if group.schema not in _schemas or group.redefine is None:
                continue

            while group.redefine is not None:
                if not any(isinstance(e, XsdGroup) and e.name == group.name for e in group) \
                        and not group.is_restriction(group.redefine):
                    msg = _("the redefined group is an illegal restriction")
                    group.parse_error(msg, validation=validation)

                group = group.redefine

        # Check complex content types models restrictions
        for xsd_global in filter(lambda x: x.schema in _schemas, self.iter_globals()):
            xsd_type: Any
            for xsd_type in xsd_global.iter_components(XsdComplexType):
                if not isinstance(xsd_type.content, XsdGroup):
                    continue

                if xsd_type.derivation == 'restriction':
                    base_type = xsd_type.base_type
                    if base_type and base_type.name != XSD_ANY_TYPE and base_type.is_complex():
                        if not xsd_type.content.is_restriction(base_type.content):
                            msg = _("the derived group is an illegal restriction")
                            xsd_type.parse_error(msg, validation=validation)

                    if base_type.is_complex() and not base_type.open_content and \
                            xsd_type.open_content and xsd_type.open_content.mode != 'none':
                        _group = xsd_type.schema.create_any_content_group(
                            parent=xsd_type,
                            any_element=xsd_type.open_content.any_element
                        )
                        if not _group.is_restriction(base_type.content):
                            msg = _("restriction has an open content but base type has not")
                            _group.parse_error(msg, validation=validation)

                try:
                    check_model(xsd_type.content)
                except XMLSchemaModelDepthError:
                    msg = _("can't verify the content model of {!r} "
                            "due to exceeding of maximum recursion depth")
                    xsd_type.schema.warnings.append(msg.format(xsd_type))
                    warnings.warn(msg, XMLSchemaWarning, stacklevel=4)
                except XMLSchemaModelError as err:
                    if validation == 'strict':
                        raise
                    xsd_type.errors.append(err)
