#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
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
from collections.abc import Callable, Collection, Iterator, Iterable, Mapping
from typing import Any, cast, NamedTuple, Optional, Union, Type, TypeVar

from xmlschema.aliases import ComponentClassType, ElementType, SchemaSourceType, \
    SchemaType, BaseXsdType, SchemaGlobalType, NsmapType
from xmlschema.exceptions import XMLSchemaKeyError, XMLSchemaTypeError, \
    XMLSchemaValueError, XMLSchemaWarning, XMLSchemaNamespaceError
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import local_name, get_extended_qname
from xmlschema.utils.urls import get_url, normalize_url
from xmlschema.loaders import NamespaceResourcesMap, SchemaLoader
from xmlschema.resources import XMLResource
import xmlschema.names as nm

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaModelError, XMLSchemaModelDepthError, \
    XMLSchemaParseError
from .xsdbase import XsdValidator, XsdComponent
from .builtins import xsd_builtin_types_factory
from .models import check_model
from . import XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement, XsdAttributeGroup, \
    XsdGroup, XsdNotation, XsdIdentity, XsdAssert, XsdUnion, XsdAtomicRestriction

GLOBAL_TAGS = frozenset((
    nm.XSD_NOTATION, nm.XSD_SIMPLE_TYPE, nm.XSD_COMPLEX_TYPE,
    nm.XSD_ATTRIBUTE, nm.XSD_ATTRIBUTE_GROUP, nm.XSD_GROUP, nm.XSD_ELEMENT
))

T = TypeVar('T')

StagingItemType = Union[T, tuple[ElementType, SchemaType], list[tuple[ElementType, SchemaType]]]

BuilderType =  Callable[[ElementType, SchemaType], T]


class XsdBuilders(NamedTuple):
    notation: BuilderType[XsdNotation]
    attribute: BuilderType[XsdAttribute]
    attribute_group: BuilderType[XsdAttributeGroup]
    type: BuilderType[BaseXsdType]
    group: BuilderType[XsdGroup]
    element: BuilderType[XsdElement]


class NamespaceView(Mapping[str, T]):
    """
    A mapping for filtered access to a dictionary that stores objects by FQDN.
    """
    __slots__ = '_target_dict', '_namespace', '_prefix', '_prefix_len'

    def __init__(self, target_dict: dict[str, T], namespace: str):
        self._target_dict = target_dict
        self._namespace = namespace
        self._prefix = f'{{{namespace}}}' if namespace else ''
        self._prefix_len = len(self._prefix)

    def __getitem__(self, key: str) -> T:
        try:
            return self._target_dict[self._prefix + key]
        except KeyError:
            raise KeyError(key) from None

    def __len__(self) -> int:
        if not self._namespace:
            return sum(1 for k in self._target_dict if k[:1] != '{')
        return sum(1 for k in self._target_dict if self._prefix == k[:self._prefix_len])

    def __iter__(self) -> Iterator[str]:
        if not self._namespace:
            for k in self._target_dict:
                if k[:1] != '{':
                    yield k
        else:
            for k in self._target_dict:
                if self._prefix == k[:self._prefix_len]:
                    yield k[self._prefix_len:]

    def __repr__(self) -> str:
        return '%s(%s)' % (self.__class__.__name__, str(self.as_dict()))

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and (self._prefix + key) in self._target_dict

    def __eq__(self, other: Any) -> Any:
        return self.as_dict() == other

    def as_dict(self) -> dict[str, T]:
        if not self._namespace:
            return {k: v for k, v in self._target_dict.items() if k[:1] != '{'}
        else:
            return {
                k[self._prefix_len:]: v for k, v in self._target_dict.items()
                if self._prefix == k[:self._prefix_len]
            }


class GlobalMaps(NamedTuple):
    notations: dict[str, XsdNotation]
    attributes: dict[str, XsdAttribute]
    attribute_groups: dict[str, XsdAttributeGroup]
    types: dict[str, BaseXsdType]
    elements: dict[str, XsdElement]
    groups: dict[str, XsdGroup]
    substitution_groups: dict[str, set[XsdElement]]
    identities: dict[str, XsdIdentity]

    def clear(self):
        for item in self:
            item.clear()

    def update(self, other: 'GlobalMaps') -> None:
        for m1, m2 in zip(self, other):
            m1.update(m2)

    def copy(self) -> 'GlobalMaps':
        return GlobalMaps(*[m.copy() for m in self])

    def iter_globals(self) -> Iterator[XsdComponent]:
        for k in range(6):
            yield from self[k].values()


class StagingMaps(NamedTuple):
    notations: dict[str, StagingItemType[XsdNotation]]
    attributes: dict[str, StagingItemType[XsdAttribute]]
    attribute_groups: dict[str, StagingItemType[XsdAttributeGroup]]
    types: dict[str, StagingItemType[BaseXsdType]]
    elements: dict[str, StagingItemType[XsdElement]]
    groups: dict[str, StagingItemType[XsdGroup]]

    builders: dict[str, Callable[[ElementType, SchemaType], Any]]

    _map_index = {
        nm.XSD_NOTATION: 0,
        nm.XSD_ATTRIBUTE: 1,
        nm.XSD_ATTRIBUTE_GROUP: 2,
        nm.XSD_SIMPLE_TYPE: 3,
        nm.XSD_COMPLEX_TYPE: 3,
        nm.XSD_ELEMENT: 4,
        nm.XSD_GROUP: 5,
    }

    def __iter__(self):
        for k in range(6):
            yield self[k]

    def __len__(self) -> int:
        return sum(len(item) for item in self)

    def clear(self) -> None:
        for item in self:
            item.clear()

    def update(self, other: 'GlobalMaps') -> None:
        for m1, m2 in zip(self, other):
            m1.update(m2)

    def flush(self, other: 'GlobalMaps') -> None:
        for m1, m2 in zip(self, other):
            unbuilt = {}
            for k, v in m1.items():
                if isinstance(v, XsdComponent):
                    m2[k] = v
                else:
                    unbuilt[k] = v

            m1.clear()
            m1.update(unbuilt)

    def lookup_notation(self, qname: str) -> XsdNotation:
        obj = self.notations[qname]
        if isinstance(obj, XsdNotation):
            return obj
        return cast(XsdNotation, self._build_global(obj, qname, self.notations))

    def lookup_type(self, qname: str) -> BaseXsdType:
        obj = self.types[qname]
        if isinstance(obj, (XsdSimpleType, XsdComplexType)):
            return obj
        return cast(BaseXsdType, self._build_global(obj, qname, self.types))

    def lookup_attribute(self, qname: str) -> XsdAttribute:
        obj = self.attributes[qname]
        if isinstance(obj, XsdAttribute):
            return obj
        return cast(XsdAttribute, self._build_global(obj, qname, self.attributes))

    def lookup_attribute_group(self, qname: str) -> XsdAttributeGroup:
        obj = self.attribute_groups[qname]
        if isinstance(obj, XsdAttributeGroup):
            return obj
        return cast(XsdAttributeGroup, self._build_global(obj, qname, self.attribute_groups))

    def lookup_group(self, qname: str) -> XsdGroup:
        obj = self.groups[qname]
        if isinstance(obj, XsdGroup):
            return obj
        return cast(XsdGroup, self._build_global(obj, qname, self.groups))

    def lookup_element(self, qname: str) -> XsdElement:
        obj = self.elements[qname]
        if isinstance(obj, XsdElement):
            return obj
        return cast(XsdElement, self._build_global(obj, qname, self.elements))

    def _build_global(self, obj: Any, qname: str,
                      global_map: dict[str, Any]) -> Any:
        factory_or_class: Callable[[ElementType, SchemaType], Any]

        if isinstance(obj, tuple):
            # Not built XSD global component without redefinitions
            try:
                elem, schema = obj
            except ValueError:
                return obj[0]  # Circular build, simply return (elem, schema) couple

            try:
                factory_or_class = self.builders[elem.tag]
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
                factory_or_class = self.builders[elem.tag]
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
                component.parse(elem)

            return global_map[qname]

        else:
            msg = _("unexpected instance {!r} in global map")
            raise XMLSchemaTypeError(msg.format(obj))

    def load_globals(self, schemas: Iterable[SchemaType]) -> None:
        """Loads global XSD components for the given schemas."""
        redefinitions = []

        for schema in schemas:
            target_namespace = schema.target_namespace
            target_prefix = '' if not target_namespace else f'{{{target_namespace}}}%s'

            for elem in schema.root:
                if elem.tag in (nm.XSD_REDEFINE, nm.XSD_OVERRIDE):
                    location = elem.get('schemaLocation')
                    if location is None:
                        continue

                    for child in elem:
                        try:
                            if not target_prefix:
                                qname = child.attrib['name']
                            else:
                                qname = target_prefix % child.attrib['name']
                        except KeyError:
                            continue

                        redefinitions.append(
                            (qname, elem, child, schema, schema.includes[location])
                        )

                if (map_index := self._map_index.get(elem.tag)) is not None:
                    target_map = self[map_index]
                    try:
                        if not target_prefix:
                            qname = elem.attrib['name']
                        else:
                            qname = target_prefix % elem.attrib['name']
                    except KeyError:
                        continue  # Invalid global: skip

                    if qname not in target_map:
                        target_map[qname] = (elem, schema)
                    else:
                        value = target_map[qname]
                        if not isinstance(value, (list, tuple)):
                            if value.schema is schema:
                                continue
                        else:
                            try:
                                other_schema = target_map[qname][1]
                            except IndexError:
                                pass
                            else:
                                # It's ignored or replaced in case of an override
                                if other_schema.override is schema:
                                    continue
                                elif schema.override is other_schema:
                                    target_map[qname] = (elem, schema)
                                    continue

                        msg = _("global xs:{} with name={!r} is already defined")
                        schema.parse_error(
                            error=msg.format(local_name(elem.tag), qname),
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
                    msg = _("multiple redefinition for {} {!r}")
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
                                msg = _("circular redefinition for {} {!r}")
                                schema.parse_error(
                                    error=msg.format(local_name(child.tag), qname),
                                    elem=child
                                )
                                break

            try:
                map_index = self._map_index[child.tag]
            except KeyError:
                continue

            target_map = self[map_index]
            try:
                item = target_map[qname]
            except KeyError:
                # Overrides that match nothing in the target schema are ignored. See the
                # period starting with "Source declarations not present in the target set"
                # of the paragraph https://www.w3.org/TR/xmlschema11-1/#override-schema.
                if elem.tag == nm.XSD_OVERRIDE:
                    continue

                schema.parse_error(_("not a redefinition!"), child)
            else:
                if elem.tag == nm.XSD_OVERRIDE:
                    target_map[qname] = (child, schema)
                elif isinstance(item, list):
                    item.append((child, schema))
                else:
                    target_map[qname] = [item, (child, schema)]

    def build(self, validator: SchemaType, target_schemas: list[SchemaType]):
        if validator.meta_schema is None or nm.XSD_STRING not in self.types:
            xsd_builtin_types_factory(validator, self.types)
        else:
            # Rebuild xs:anyType for maps not owned by the meta-schema
            # in order to do a correct namespace lookup for wildcards.
            validator.maps.types[nm.XSD_ANY_TYPE] = validator.create_any_type()

        for qname in self.notations:
            self.lookup_notation(qname)
        for qname in self.attributes:
            self.lookup_attribute(qname)

        for qname in self.attribute_groups:
            self.lookup_attribute_group(qname)
        for schema in target_schemas:
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


# Default placeholder for deprecation of argument 'validation' in XsdGlobals
_strict = type('str', (str,), {})('strict')


class XsdGlobals(XsdValidator):
    """
    Mediator set for composing XML schema instances and provides lookup maps. It stores the global
    declarations defined in the registered schemas. Register a schema to
    add its declarations to the global maps.

    :param validator: the origin schema class/instance used for creating the global maps.
    :param loader: an optional subclass of :class:`SchemaLoader` to use for creating \
    the loader instance.
    :param parent: an optional parent schema, that is required to be built and with \
    no use of the target namespace of the validator.
    """
    _schemas: set[SchemaType]
    loader: SchemaLoader

    _resolvers = {
        nm.XSD_SIMPLE_TYPE: 'lookup_type',
        nm.XSD_COMPLEX_TYPE: 'lookup_type',
        nm.XSD_ELEMENT: 'lookup_element',
        nm.XSD_GROUP: 'lookup_group',
        nm.XSD_ATTRIBUTE: 'lookup_attribute',
        nm.XSD_ATTRIBUTE_GROUP: 'lookup_attribute_group',
        nm.XSD_NOTATION: 'lookup_notation',
    }

    def __init__(self, validator: SchemaType, validation: str = _strict,
                 loader: Optional[Type[SchemaLoader]] = None,
                 parent: Optional[SchemaType] = None) -> None:

        if not isinstance(validation, _strict.__class__):
            msg = "argument 'validation' is not used and will be removed in v5.0"
            warnings.warn(msg, DeprecationWarning, stacklevel=1)

        super().__init__(validator.validation)
        self._built = False
        self._validation_attempted = 'none'

        self._schemas = set()
        self.validator = validator
        self.parent = parent

        self.namespaces = NamespaceResourcesMap()  # Registered schemas by namespace URI
        if parent is None:
            self._builders = validator.get_builders()
        else:
            self._builders = self.parent.maps._builders

        builders: dict[str, Callable[[ElementType, SchemaType], Any]] = {
            nm.XSD_NOTATION: validator.xsd_notation_class,
            nm.XSD_SIMPLE_TYPE: validator.simple_type_factory,
            nm.XSD_COMPLEX_TYPE: validator.xsd_complex_type_class,
            nm.XSD_ATTRIBUTE: validator.xsd_attribute_class,
            nm.XSD_ATTRIBUTE_GROUP: validator.xsd_attribute_group_class,
            nm.XSD_GROUP: validator.xsd_group_class,
            nm.XSD_ELEMENT: validator.xsd_element_class,
        }
        self.notations: dict[str, XsdNotation] = {}
        self.attributes: dict[str, XsdAttribute] = {}
        self.attribute_groups: dict[str, XsdAttributeGroup] = {}
        self.types: dict[str, BaseXsdType] = {}
        self.elements: dict[str, XsdElement] = {}
        self.groups: dict[str, XsdGroup] = {}
        self.substitution_groups: dict[str, set[XsdElement]] = {}
        self.identities: dict[str, XsdIdentity] = {}

        self.global_maps = GlobalMaps(*(getattr(self, n) for n in GlobalMaps._fields))
        self._staging_maps = StagingMaps({}, {}, {}, {}, {}, {}, builders)

        self.loader = (loader or SchemaLoader)(self)

        if parent is not None:
            self._include_schemas(parent.maps)
        self.register(self.validator)

    @property
    def schemas(self) -> set[SchemaType]:
        return self._schemas

    def _include_schemas(self, maps: 'XsdGlobals') -> None:
        """Includes parent schemas, recursively."""
        if maps.parent is not None:
            self._include_schemas(maps.parent.maps)
        if self.validator.target_namespace in maps.namespaces:
            return
        self._schemas.update(maps._schemas)
        self.namespaces.update(maps.namespaces)

    def _include_maps(self, maps: 'XsdGlobals') -> None:
        """Reuse components of the maps of the parent schema, recursively."""
        if maps.parent is not None:
            self._include_maps(maps.parent.maps)
        if self.validator.target_namespace in maps.namespaces:
            return
        if not maps.built:
            maps.build()
        self.global_maps.update(maps.global_maps)

    def __repr__(self) -> str:
        return '%s(validator=%r)' % (self.__class__.__name__, self.validator)

    def __len__(self) -> int:
        return len(self._schemas)

    def __iter__(self) -> Iterator[SchemaType]:
        yield from self._schemas

    def __contains__(self, obj: object) -> bool:
        return obj in self._schemas

    def copy(self) -> 'XsdGlobals':
        obj = type(self)(
            validator=self.validator.copy(),
            loader=self.loader.__class__,
            parent=self.parent
        )
        obj.validator.maps = obj
        for schema in self._schemas:
            if schema.maps is self and schema is not self.validator:
                schema.copy().maps = obj
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
            lookup_function = getattr(self, self._resolvers[tag])
        except KeyError:
            msg = _("wrong tag {!r} for an XSD global definition/declaration")
            raise XMLSchemaValueError(msg.format(tag)) from None
        else:
            return lookup_function(qname)

    def lookup_notation(self, qname: str) -> XsdNotation:
        try:
            return self.notations[qname]
        except KeyError:
            if qname in self._staging_maps.notations:
                obj = self._staging_maps.lookup_notation(qname)
                if qname not in self.notations:
                    self.notations[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'xs:notation {qname!r} not found')

    def lookup_type(self, qname: str) -> BaseXsdType:
        try:
            return self.types[qname]
        except KeyError:
            if qname in self._staging_maps.types:
                obj = self._staging_maps.lookup_type(qname)
                if qname not in self.types:
                    self.types[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'global xs:simpleType/xs:complexType {qname!r} not found')

    def lookup_attribute(self, qname: str) -> XsdAttribute:
        try:
            return self.attributes[qname]
        except KeyError:
            if qname in self._staging_maps.attributes:
                obj = self._staging_maps.lookup_attribute(qname)
                if qname not in self.attributes:
                    self.attributes[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'global xs:attribute {qname!r} not found')

    def lookup_attribute_group(self, qname: str) -> XsdAttributeGroup:
        try:
            return self.attribute_groups[qname]
        except KeyError:
            if qname in self._staging_maps.attribute_groups:
                obj = self._staging_maps.lookup_attribute_group(qname)
                if qname not in self.attribute_groups:
                    self.attribute_groups[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'global xs:attributeGroup {qname!r} not found')

    def lookup_group(self, qname: str) -> XsdGroup:
        try:
            return self.groups[qname]
        except KeyError:
            if qname in self._staging_maps.groups:
                obj = self._staging_maps.lookup_group(qname)
                if qname not in self.groups:
                    self.groups[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'global xs:group {qname!r} not found')

    def lookup_element(self, qname: str) -> XsdElement:
        try:
            return self.elements[qname]
        except KeyError:
            if qname in self._staging_maps.elements:
                obj = self._staging_maps.lookup_element(qname)
                if qname not in self.elements:
                    self.elements[qname] = obj
                return obj
            raise XMLSchemaKeyError(f'global xs:element {qname!r} not found')

    def get_instance_type(self, type_name: str, base_type: BaseXsdType,
                          namespaces: NsmapType) -> BaseXsdType:
        """
        Returns the instance XSI type from global maps, validating it with the reference base type.

        :param type_name: the XSI type attribute value, a QName in prefixed format.
        :param base_type: the XSD from which the instance type has to be derived.
        :param namespaces: a mapping from prefixes to namespaces.
        """
        if isinstance(base_type, XsdComplexType) and nm.XSI_TYPE in base_type.attributes:
            xsd_attribute = cast(XsdAttribute, base_type.attributes[nm.XSI_TYPE])
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
        return self._built

    @property
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif any(True for x in self.iter_unbuilt()):
            return 'partial'
        else:
            return 'none'

    @property
    def validity(self) -> str:
        if not self or all(not g for g in self.global_maps):
            return 'notKnown'
        if all(s.validity == 'valid' for s in self._schemas):
            return 'valid'
        elif any(s.validity == 'invalid' for s in self._schemas):
            return 'invalid'
        else:
            return 'notKnown'

    @property
    def use_meta(self):
        if self.validator.meta_schema is None:
            return True
        elif self.parent is None:
            return False
        else:
            return self.parent.use_meta

    @property
    def total_globals(self):
        return sum(1 for _comp in self.iter_globals())

    @property
    def built_globals(self):
        return sum(1 for c in self.iter_globals() if isinstance(c, XsdComponent) and c.built)

    @property
    def unbuilt_globals(self):
        return sum(1 for c in self.iter_globals()
                   if not isinstance(c, XsdComponent) or not c.built)

    @property
    def unbuilt(self) -> list[Union[XsdComponent, SchemaType]]:
        """Property that returns a list with unbuilt components."""
        return [c for s in self._schemas for c in s.iter_components()
                if c is not s and not c.built]

    @property
    def xsd_version(self) -> str:
        return self.validator.XSD_VERSION

    @property
    def all_errors(self) -> list[XMLSchemaParseError]:
        return [e for s in self._schemas for e in s.all_errors]

    def create_bindings(self, *bases: Type[Any], **attrs: Any) -> None:
        """Creates data object bindings for the XSD elements of built schemas."""
        for xsd_element in self.iter_components(xsd_classes=XsdElement):
            assert isinstance(xsd_element, XsdElement)
            if xsd_element.target_namespace != nm.XSD_NAMESPACE:
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
        for global_map in self.global_maps[:6]:
            yield from global_map.values()

    def iter_unbuilt(self) -> Iterator[StagingItemType[XsdComponent]]:
        for staging_map in self._staging_maps:
            for v in staging_map.values():
                if not isinstance(v, XsdComponent):
                    yield v

    def iter_schemas(self) -> Iterator[SchemaType]:
        """Creates an iterator for the registered schemas."""
        yield from self._schemas

    def match_source(self, source: SchemaSourceType, base_url: Optional[str] = None) \
            -> Optional[SchemaType]:
        url = get_url(source)
        if url is not None:
            url = normalize_url(url, base_url)
            for schema in self._schemas:
                if url == schema.url:
                    return schema
        elif isinstance(source, XMLResource):
            for schema in self._schemas:
                if source is schema.source or source.source is schema.source.source:
                    return schema
        else:
            for schema in self._schemas:
                if source is schema.source.source:
                    return schema

        return None

    def register(self, schema: SchemaType) -> None:
        """Registers an XMLSchema instance."""
        namespace = schema.target_namespace
        if schema not in self._schemas:
            if self.match_source(schema.url or schema.source) is not None:
                raise XMLSchemaValueError(
                    f"another schema loaded from {schema.source} is already registered"
                )
            self._schemas.add(schema)

            try:
                self.namespaces[namespace].append(schema)
            except KeyError:
                self.namespaces[namespace] = [schema]

        schema.notations = NamespaceView(self.notations, namespace)
        schema.types = NamespaceView(self.types, namespace)
        schema.attributes = NamespaceView(self.attributes, namespace)
        schema.attribute_groups = NamespaceView(self.attribute_groups, namespace)
        schema.groups = NamespaceView(self.groups, namespace)
        schema.elements = NamespaceView(self.elements, namespace)
        schema.substitution_groups = NamespaceView(self.substitution_groups, namespace)
        schema.identities = NamespaceView(self.identities, namespace)
        schema.loader = self.loader

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
        if namespace in self.namespaces:
            return True
        elif not self.built or self.validator.meta_schema is None:
            return False  # Do not load additional namespaces for meta-schema (XHTML)

        if not build:
            return self.validator.loader.load_namespace(namespace)

        global_maps = self.global_maps.copy()
        if not self.validator.loader.load_namespace(namespace):
            return False

        try:
            self.build()
        except XMLSchemaNotBuiltError:
            self.global_maps.clear()
            self.global_maps.update(global_maps)
            return False
        else:
            return True

    def clear(self, remove_schemas: bool = False) -> None:
        """
        Clears the instance maps and schemas.

        :param remove_schemas: removes also the schema instances, keeping only the \
        validator that created the global maps instance and schemas and namespaces \
        inherited from ancestors.
        """
        self.global_maps.clear()
        for schema in self._schemas:
            if schema.maps is self:
                schema.clear()

        if remove_schemas:
            self._schemas.clear()
            self.namespaces.clear()
            if self.parent is not None:
                self._include_schemas(self.parent.maps)
            self.register(self.validator)

        self._built = False
        self._validation_attempted = 'none'

    def build(self) -> None:
        """
        Build the maps of XSD global definitions/declarations. The global maps are
        updated adding and building the globals of not built registered schemas.
        """
        self.check_schemas()
        self.clear()
        self.global_maps.clear()
        if self.parent is not None:
            self._include_maps(self.parent.maps)

        target_schemas = [s for s in self.schemas if s.maps is self]

        self._staging_maps.clear()
        self._staging_maps.update(self.global_maps)
        parent_components = len(self._staging_maps)

        self._staging_maps.load_globals(target_schemas)
        new_components = len(self._staging_maps) - parent_components

        self._staging_maps.build(self.validator, target_schemas)
        self._staging_maps.flush(self.global_maps)

        # Build element declarations inside model groups.
        for schema in target_schemas:
            for group in schema.iter_components(XsdGroup):
                group.build()

        # Build identity references and XSD 1.1 assertions
        for schema in target_schemas:
            for obj in schema.iter_components((XsdIdentity, XsdAssert)):
                obj.build()

        if self.validator.meta_schema is not None:
            self.check_components(target_schemas)

        if len(self._staging_maps):
            self._validation_attempted = 'partial'
            print('UNBUILT!')
        elif any(not c.built for c in self.iter_globals()):
            print("UNBUILT COMPONENTS!")
            self._validation_attempted = 'partial'
        else:
            self._validation_attempted = 'full'

        self._built = True

    def check_schemas(self) -> None:
        if self.validator not in self._schemas:
            raise XMLSchemaValueError(_('global maps main validator is not registered'))

        registered_schemas = set()
        for namespace, schemas in self.namespaces.items():
            for s in schemas:
                if s.target_namespace != namespace:
                    raise XMLSchemaNamespaceError(
                        _('schema {} does not belong to namespace {!r}').format(s, namespace)
                    )
                if s in registered_schemas:
                    raise XMLSchemaNamespaceError(
                        _('duplicate of schema {} found in namespace {!r}').format(s, namespace)
                    )
                registered_schemas.add(s)

        if self._schemas != registered_schemas:
            raise XMLSchemaValueError(_('registered schemas do not match namespace mapped schemas'))

    def check_components(self, schemas: Optional[Iterable[SchemaType]] = None) -> None:
        """
        Checks the components of the global maps. For default checks all schemas
        and raises an exception at first error.

        :param schemas: optional argument with the set of the schemas to check.
        :raise: XMLSchemaParseError
        """
        _schemas = schemas if schemas is not None else self._schemas

        # Checks substitution groups circularity
        for qname in self.substitution_groups:
            xsd_element = self.elements[qname]
            assert isinstance(xsd_element, XsdElement), _("global element not built!")
            if any(e is xsd_element for e in xsd_element.iter_substitutes()):
                msg = _("circularity found for substitution group with head element {}")
                xsd_element.parse_error(msg.format(xsd_element))

        if self.validation == 'strict' and any(not (schema := s).built for s in _schemas):
            raise XMLSchemaNotBuiltError(
                schema, _("global map has unbuilt components: %r") % self.unbuilt
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
                    group.parse_error(msg)

                group = group.redefine

        # Check complex content types models restrictions
        for xsd_global in filter(lambda x: x.schema in _schemas, self.iter_globals()):
            xsd_type: Any
            for xsd_type in xsd_global.iter_components(XsdComplexType):
                if not isinstance(xsd_type.content, XsdGroup):
                    continue

                if xsd_type.derivation == 'restriction':
                    base_type = xsd_type.base_type
                    if base_type and base_type.name != nm.XSD_ANY_TYPE and base_type.is_complex():
                        if not xsd_type.content.is_restriction(base_type.content):
                            msg = _("the derived group is an illegal restriction")
                            xsd_type.parse_error(msg)

                    if base_type.is_complex() and not base_type.open_content and \
                            xsd_type.open_content and xsd_type.open_content.mode != 'none':
                        _group = xsd_type.schema.create_any_content_group(
                            parent=xsd_type,
                            any_element=xsd_type.open_content.any_element
                        )
                        if not _group.is_restriction(base_type.content):
                            msg = _("restriction has an open content but base type has not")
                            _group.parse_error(msg)

                try:
                    check_model(xsd_type.content)
                except XMLSchemaModelDepthError:
                    msg = _("can't verify the content model of {!r} "
                            "due to exceeding of maximum recursion depth")
                    xsd_type.schema.warnings.append(msg.format(xsd_type))
                    warnings.warn(msg, XMLSchemaWarning, stacklevel=4)
                except XMLSchemaModelError as err:
                    if self.validation == 'strict':
                        raise
                    xsd_type.errors.append(err)
