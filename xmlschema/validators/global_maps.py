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
import dataclasses
import threading
import warnings
from collections import Counter
from collections.abc import Callable, Collection, ItemsView, Iterator, Iterable, \
    Mapping, ValuesView
from operator import attrgetter, itemgetter
from types import MappingProxyType
from typing import Any, cast, NamedTuple, Optional, Union, Type, TypeVar
from xml.etree.ElementTree import Element

from xmlschema.aliases import ClassInfoType, ElementType, SchemaSourceType, \
    SchemaType, BaseXsdType, SchemaGlobalType, NsmapType, StagedItemType
from xmlschema.exceptions import XMLSchemaKeyError, XMLSchemaTypeError, \
    XMLSchemaValueError, XMLSchemaWarning, XMLSchemaNamespaceError, \
    XMLSchemaAttributeError
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import local_name, get_extended_qname
from xmlschema.utils.urls import get_url, normalize_url
from xmlschema.loaders import NamespaceResourcesMap, SchemaLoader
from xmlschema.resources import XMLResource
import xmlschema.names as nm

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaModelError, XMLSchemaModelDepthError, \
    XMLSchemaParseError, XMLSchemaValidatorError
from .xsdbase import XsdValidator, XsdComponent
from .facets import XSD_11_FACETS_BUILDERS, XSD_10_FACETS_BUILDERS
from .builtins import XSD_11_BUILTIN_TYPES, XSD_10_BUILTIN_TYPES
from .models import check_model
from . import XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement, XsdAttributeGroup, \
    XsdGroup, XsdNotation, XsdIdentity, XsdAssert, XsdUnion, XsdAtomicRestriction, \
    XsdAtomicBuiltin

GLOBAL_TAGS = frozenset((
    nm.XSD_NOTATION, nm.XSD_SIMPLE_TYPE, nm.XSD_COMPLEX_TYPE,
    nm.XSD_ATTRIBUTE, nm.XSD_ATTRIBUTE_GROUP, nm.XSD_GROUP, nm.XSD_ELEMENT
))

CT = TypeVar('CT', bound=XsdComponent)

BuilderType =  Callable[[ElementType, SchemaType], CT]


@dataclasses.dataclass(frozen=True)
class XsdBuilders:
    notation: BuilderType[XsdNotation]
    attribute: BuilderType[XsdAttribute]
    attribute_group: BuilderType[XsdAttributeGroup]
    simple_type: BuilderType[XsdSimpleType]
    complex_type: BuilderType[XsdComplexType]
    group: BuilderType[XsdGroup]
    element: BuilderType[XsdElement]

    _builder_getters = {
        nm.XSD_SIMPLE_TYPE: attrgetter('simple_type'),
        nm.XSD_COMPLEX_TYPE: attrgetter('complex_type'),
        nm.XSD_NOTATION: attrgetter('notation'),
        nm.XSD_ATTRIBUTE: attrgetter('attribute'),
        nm.XSD_ATTRIBUTE_GROUP: attrgetter('attribute_group'),
        nm.XSD_ELEMENT: attrgetter('element'),
        nm.XSD_GROUP: attrgetter('group'),
    }

    def __getitem__(self, tag: str) -> BuilderType[XsdComponent]:
        return self._builder_getters[tag](self)


class StagedMap(Mapping[str, CT]):
    label = 'component'

    def __init__(self, validator: SchemaType):
        self._store: dict[str, CT] = {}
        self._staging: dict[str, StagedItemType] = {}
        self._validator = validator
        self._builders: XsdBuilders = validator.get_builders()

        # Schema counters for built and staged component
        self._store_counter: Counter[SchemaType] = Counter()
        self._staging_counter: Counter[SchemaType] = Counter()

    def __getitem__(self, qname: str) -> CT:
        try:
            return self._store[qname]
        except KeyError:
            msg = _('global {} {!r} not found').format(self.label, qname)
            raise XMLSchemaKeyError(msg) from None

    def __iter__(self) -> Iterator[CT]:
        yield from self._store

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return repr(self._store)

    def copy(self):
        obj: StagedMap[CT] = object.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        obj._staging = self._staging.copy()
        obj._store = self._store.copy()
        obj._store_counter = self._store_counter.copy()
        obj._staging_counter = self._staging_counter.copy()
        return obj

    def clear(self) -> None:
        self._store.clear()
        self._staging.clear()
        self._store_counter.clear()
        self._staging_counter.clear()

    def update(self, other: 'StagedMap[CT]') -> None:
        if not isinstance(other, self.__class__):
            raise XMLSchemaTypeError(_("argument global map must be of the same type"))
        self._store.update(other._store)

    def get_total(self, schema: Optional[SchemaType] = None) -> int:
        return len(self._store) if schema is None else self._store_counter[schema]

    def get_total_staged(self, schema: Optional[SchemaType] = None) -> int:
        return len(self._staging) if schema is None else self._staging_counter[schema]

    @property
    def staged(self) -> list[str]:
        return list(self._staging)

    @property
    def staged_items(self) -> ItemsView[str, StagedItemType]:
        return self._staging.items()

    @property
    def staged_values(self) -> ValuesView[StagedItemType]:
        return self._staging.values()

    def load(self, qname, elem: ElementType, schema: SchemaType) -> None:
        if qname in self._store:
            comp = self._store[qname]
            if comp.schema is schema:
                msg = _("global xs:{} with name={!r} is already built")
            elif comp.schema.maps is schema.maps or comp.schema.meta_schema is None:
                msg = _("global xs:{} with name={!r} is already defined")
            else:
                # Allows rebuilding of parent maps components for descendant maps
                # but not allows substitution of meta-schema components.
                self._staging[qname] = elem, schema
                return

        elif qname in self._staging:

            obj = self._staging[qname]
            if len(obj) == 2:
                _elem, _schema = obj
                if _elem is elem and _schema is schema:
                    return  # ignored: it's the same component
                elif schema is _schema.override:
                    return  # ignored: the loaded component is overridden
                elif schema.override is _schema:
                    # replaced: the loaded component is an override
                    self._staging[qname] = (elem, schema)
                    return

            msg = _("global xs:{} with name={!r} is already loaded")
        else:
            self._staging[qname] = elem, schema
            return

        schema.parse_error(
            error=msg.format(local_name(elem.tag), qname),
            elem=elem
        )

    def load_redefine(self, qname, elem: ElementType, schema: SchemaType) -> None:
        try:
            item = self._staging[qname]
        except KeyError:
            schema.parse_error(_("not a redefinition!"), elem)
        else:
            if isinstance(item, list):
                item.append((elem, schema))
            else:
                self._staging[qname] = [item, (elem, schema)]

    def load_override(self, qname, elem: ElementType, schema: SchemaType) -> None:
        if qname not in self._staging:
            # Overrides that match nothing in the target schema are ignored. See the
            # period starting with "Source declarations not present in the target set"
            # of the paragraph https://www.w3.org/TR/xmlschema11-1/#override-schema.
            return

        self._staging[qname] = elem, schema

    def lookup(self, qname: str) -> Union[CT, StagedItemType]:
        if qname not in self._staging:
            return self.__getitem__(qname)
        elif self._validator.built:
            msg = _('global XSD {} {!r} failed to build').format(self.label, qname)
            raise XMLSchemaKeyError(msg) from None
        else:
            return self._build_global(qname)

    def build(self):
        for name in [x for x in self._staging]:
            if name in self._staging:
                self._build_global(name)

    def _build_global(self, qname: str) -> Union[CT, StagedItemType]:
        factory_or_class: Callable[[ElementType, SchemaType], Any]

        obj = self._staging[qname]
        if isinstance(obj, tuple):
            # Not built XSD global component without redefinitions
            try:
                elem, schema = obj
            except ValueError:
                return obj[0]  # Circular build, simply return (elem, schema) couple

            try:
                factory_or_class = self._builders[elem.tag]
            except KeyError:
                msg = _("wrong element {!r} for XSD {}s global map")
                raise XMLSchemaKeyError(msg.format(elem, self.label))

            self._staging[qname] = obj,  # Encapsulate into a tuple to catch circular builds
            self._store[qname] = factory_or_class(elem, schema)
            self._staging.pop(qname)

            self._store_counter[schema] += 1
            self._staging_counter[schema] -= 1

            return self._store[qname]

        elif isinstance(obj, list):
            # Not built XSD global component with redefinitions
            try:
                elem, schema = obj[0]
            except ValueError:
                if not isinstance(obj, tuple):
                    raise
                return obj[0][0]  # Circular build, simply return (elem, schema) couple

            try:
                factory_or_class = self._builders[elem.tag]
            except KeyError:
                msg = _("wrong element {!r} for XSD {}s global map")
                raise XMLSchemaKeyError(msg.format(elem, self.label))

            self._staging[qname] = obj[0],  # To catch circular builds
            self._store[qname] = component = factory_or_class(elem, schema)
            self._staging.pop(qname)

            self._store_counter[schema] += 1
            self._staging_counter[schema] -= 1

            # Apply redefinitions (changing elem involve reparse of the component)
            for elem, schema in obj[1:]:
                if component.schema.target_namespace != schema.target_namespace:
                    msg = _("redefined schema {!r} has a different targetNamespace")
                    raise XMLSchemaValueError(msg.format(schema))

                component.redefine = component.copy()
                component.redefine.parent = component
                component.schema = schema
                component.parse(elem)

            return self._store[qname]

        else:
            msg = _("unexpected instance {!r} in XSD {} global map")
            raise XMLSchemaTypeError(msg.format(obj, self.label))


class Notations(StagedMap[XsdNotation]):
    pass


class StagedTypesMap(StagedMap[BaseXsdType]):
    @property
    def label(self):
        return 'type'

    def build_builtins(self):
        if self._validator.meta_schema is not None and nm.XSD_ANY_TYPE in self._store:
            # builtin types already provided, rebuild only xs:anyType for wildcards
            self._store[nm.XSD_ANY_TYPE] = self._validator.create_any_type()
            return

        if self._validator.XSD_VERSION == '1.1':
            builtin_types = XSD_11_BUILTIN_TYPES
            facets_map = XSD_11_FACETS_BUILDERS
        else:
            builtin_types = XSD_10_BUILTIN_TYPES
            facets_map = XSD_10_FACETS_BUILDERS

        #
        # Special builtin types.
        #
        # xs:anyType
        # Ref: https://www.w3.org/TR/xmlschema11-1/#builtin-ctd
        self._store[nm.XSD_ANY_TYPE] = self._validator.create_any_type()

        # xs:anySimpleType
        # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
        xsd_any_simple_type = self._store[nm.XSD_ANY_SIMPLE_TYPE] = XsdSimpleType(
            elem=Element(nm.XSD_SIMPLE_TYPE, name=nm.XSD_ANY_SIMPLE_TYPE),
            schema=self._validator,
            parent=None,
            name=nm.XSD_ANY_SIMPLE_TYPE
        )

        # xs:anyAtomicType
        # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
        self._store[nm.XSD_ANY_ATOMIC_TYPE] = self._validator.xsd_atomic_restriction_class(
            elem=Element(nm.XSD_SIMPLE_TYPE, name=nm.XSD_ANY_ATOMIC_TYPE),
            schema=self._validator,
            parent=None,
            name=nm.XSD_ANY_ATOMIC_TYPE,
            base_type=xsd_any_simple_type,
        )

        for item in builtin_types:
            item = item.copy()
            name: str = item['name']
            try:
                value = self._staging.pop(name)
            except KeyError:
                # If builtin type element is missing create a dummy element. Necessary for the
                # meta-schema XMLSchema.xsd of XSD 1.1, that not includes builtins declarations.
                elem = Element(nm.XSD_SIMPLE_TYPE, name=name, id=name)
            else:
                if isinstance(value, XsdAtomicBuiltin):
                    if value.schema is not self._validator:
                        raise XMLSchemaValueError("built component schema is not the meta-schema!")
                    continue

                elem, schema = value
                if schema is not self._validator:
                    raise XMLSchemaValueError("loaded entry schema is not the meta-schema!")

            base_type: Union[None, BaseXsdType, tuple[ElementType, SchemaType]]
            if 'base_type' in item:
                base_type = item['base_type'] = self._store[item['base_type']]
            else:
                base_type = None

            facets = item.pop('facets', None)
            xsd_type = XsdAtomicBuiltin(elem, self._validator, **item)
            if facets:
                built_facets = xsd_type.facets
                for e in facets:
                    try:
                        cls: Any = facets_map[e.tag]
                    except AttributeError:
                        built_facets[None] = e
                    else:
                        built_facets[e.tag] = cls(e, self._validator, xsd_type, base_type)
                xsd_type.facets = built_facets

            self._store[name] = xsd_type


class GlobalMaps(NamedTuple):
    types: StagedTypesMap
    notations: StagedMap[XsdNotation]
    attributes: StagedMap[XsdAttribute]
    attribute_groups: StagedMap[XsdAttributeGroup]
    elements: StagedMap[XsdElement]
    groups: StagedMap[XsdGroup]

    _map_getters = {
        nm.XSD_SIMPLE_TYPE: itemgetter(0),
        nm.XSD_COMPLEX_TYPE: itemgetter(0),
        nm.XSD_NOTATION: itemgetter(1),
        nm.XSD_ATTRIBUTE: itemgetter(2),
        nm.XSD_ATTRIBUTE_GROUP: itemgetter(3),
        nm.XSD_ELEMENT: itemgetter(4),
        nm.XSD_GROUP: itemgetter(5),
    }

    def clear(self):
        for item in self:
            item.clear()

    def update(self, other: 'GlobalMaps') -> None:
        for m1, m2 in zip(self, other):
            m1.update(m2)

    def copy(self) -> 'GlobalMaps':
        return GlobalMaps(*[m.copy() for m in self])

    def iter_globals(self) -> Iterator[SchemaGlobalType]:
        for item in self:
            yield from item.values()

    def iter_staged(self) -> Iterator[StagedItemType]:
        for item in self:
            yield from item.staged_values()

    def load_globals(self, schemas: Iterable[SchemaType]) -> None:
        """Loads global XSD components for the given schemas."""
        redefinitions = []

        for schema in schemas:
            if schema.target_namespace:
                ns_prefix = f'{{{schema.target_namespace}}}'
            else:
                ns_prefix = ''

            for elem in schema.root:
                if (tag := elem.tag) in (nm.XSD_REDEFINE, nm.XSD_OVERRIDE):
                    location = elem.get('schemaLocation')
                    if location is None:
                        continue

                    for child in elem:
                        try:
                            qname = ns_prefix + child.attrib['name']
                        except KeyError:
                            continue

                        redefinitions.append(
                            (qname, elem, child, schema, schema.includes[location])
                        )

                elif tag in GLOBAL_TAGS:
                    try:
                        qname = ns_prefix + elem.attrib['name']
                    except KeyError:
                        continue  # Invalid global: skip

                    self._map_getters[tag](self).load(qname, elem, schema)

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
                if elem.tag == nm.XSD_REDEFINE:
                    self._map_getters[child.tag](self).load_redefine(qname, child, schema)
                else:
                    self._map_getters[child.tag](self).load_override(qname, child, schema)
            except KeyError:
                print("MISSING")
                continue


T = TypeVar('T')


class NamespaceView(Mapping[str, T]):
    """
    A mapping for filtered access to a dictionary that stores objects by FQDN.
    """
    __slots__ = '_target_dict', '_namespace', '_prefix', '_prefix_len'

    def __init__(self, target_dict: Mapping[str, T], namespace: str):
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

    types: StagedTypesMap
    notations: StagedMap[XsdNotation]
    attributes: StagedMap[XsdAttribute]
    attribute_groups: StagedMap[XsdAttributeGroup]
    elements: StagedMap[XsdElement]
    groups: StagedMap[XsdGroup]
    substitution_groups: dict[str, set[XsdElement]]
    identities: dict[str, XsdIdentity]

    _resolvers = {
        nm.XSD_SIMPLE_TYPE: 'lookup_type',
        nm.XSD_COMPLEX_TYPE: 'lookup_type',
        nm.XSD_ATTRIBUTE: 'lookup_attribute',
        nm.XSD_ATTRIBUTE_GROUP: 'lookup_attribute_group',
        nm.XSD_NOTATION: 'lookup_notation',
        nm.XSD_ELEMENT: 'lookup_element',
        nm.XSD_GROUP: 'lookup_group',
    }

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state.pop('_build_lock', None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._build_lock = threading.Lock()

    def __init__(self, validator: SchemaType, validation: str = _strict,
                 loader: Optional[Type[SchemaLoader]] = None,
                 parent: Optional[SchemaType] = None) -> None:

        if not isinstance(validation, _strict.__class__):
            msg = "argument 'validation' is not used and will be removed in v5.0"
            warnings.warn(msg, DeprecationWarning, stacklevel=1)

        super().__init__(validator.validation)
        self._build_lock = threading.Lock()
        self._staged_globals = 0
        self._validation_attempted = 'none'
        self._validity = 'notKnown'

        self._schemas = set()
        self.validator = validator
        self._parent = parent

        self.namespaces = NamespaceResourcesMap()  # Registered schemas by namespace URI
        if parent is None:
            self._builders = validator.get_builders()
        else:
            self._builders = self._parent.maps._builders

        self.types = StagedTypesMap(self.validator)
        self.notations = StagedMap(self.validator)
        self.attributes = StagedMap(self.validator)
        self.attribute_groups = StagedMap(self.validator)
        self.elements = StagedMap(self.validator)
        self.groups = StagedMap(self.validator)
        self.global_maps = GlobalMaps(*(getattr(self, n) for n in GlobalMaps._fields))

        self.substitution_groups = {}
        self.identities = {}

        self.loader = (loader or SchemaLoader)(self)

        for ancestor in self.iter_ancestors():
            self._schemas.update(ancestor.maps.schemas)
            self.namespaces.update(ancestor.maps.namespaces)

        self.register(self.validator)


    @property
    def schemas(self) -> set[SchemaType]:
        return self._schemas

    @property
    def parent(self) -> Optional[SchemaType]:
        return self._parent

    def _include_schemas(self, parent: SchemaType) -> None:
        """Includes schemas of parent maps, recursively."""
        if parent.meta_schema is None:
            if self.validator.target_namespace in parent.maps.namespaces:
                return  # don't include meta-schema if namespaces overlap

        if parent.maps._parent is not None:
            self._include_schemas(parent.maps._parent)
        self._schemas.update(parent.maps._schemas)
        self.namespaces.update(parent.maps.namespaces)

    def _include_maps(self, parent: SchemaType) -> None:
        """Reuse components of the maps of the parent schema, recursively."""
        if parent.meta_schema is None:
            if self.validator.target_namespace in parent.maps.namespaces:
                return  # don't include meta-schema if namespaces overlap

        if parent.maps._parent is not None:
            self._include_maps(parent.maps._parent)

        parent.maps.build()
        self.global_maps.update(parent.maps.global_maps)
        self.substitution_groups.update(parent.maps.substitution_groups)
        self.identities.update(parent.maps.identities)

    def __repr__(self) -> str:
        return '%s(validator=%r)' % (self.__class__.__name__, self.validator)

    def __setattr__(self, name: str, value: Any) -> None:
        if name[:1] != '_' and name in self.__dict__ and value is not self.__dict__[name]:
            msg = _("can't change attribute {!r} of a global maps instance")
            raise XMLSchemaAttributeError(msg.format(name))
        super().__setattr__(name, value)

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
            parent=self._parent
        )
        obj.validator.__dict__['maps'] = obj
        for schema in self._schemas:
            if schema.maps is self and schema is not self.validator:
                schema = schema.copy()
                obj.register(schema)
                schema.__dict__['maps'] = obj

        obj.clear()
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

    def lookup_type(self, qname: str) -> BaseXsdType:
        return self.types.lookup(qname)

    def lookup_notation(self, qname: str) -> XsdNotation:
        return self.notations.lookup(qname)

    def lookup_attribute(self, qname: str) -> XsdAttribute:
        return self.attributes.lookup(qname)

    def lookup_attribute_group(self, qname: str) -> XsdAttributeGroup:
        return self.attribute_groups.lookup(qname)

    def lookup_group(self, qname: str) -> XsdGroup:
        return self.groups.lookup(qname)

    def lookup_element(self, qname: str) -> XsdElement:
        return self.elements.lookup(qname)

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
        if (validation_attempted := self.validation_attempted) == 'none':
            return False
        return validation_attempted == 'full' or self.validation != 'strict'

    @property
    def validation_attempted(self) -> str:
        if self._staged_globals < self.staged_globals:
            self._staged_globals = self.staged_globals

            for schema in self._schemas:
                if schema.maps is self:
                    schema.clear()  # clear XPath and component lazy properties

            if self._validation_attempted == 'full':
                self._validation_attempted = 'partial'

        return self._validation_attempted

    @property
    def validity(self) -> str:
        if self._staged_globals < self.staged_globals:
            self._staged_globals = self.staged_globals

            for schema in self._schemas:
                if schema.maps is self:
                    schema.clear()  # clear XPath and component lazy properties

            if self._validity == 'valid':
                self._validity = 'notKnown'

        if self._parent is None:
            return self._validity

        validity = self._parent.maps.validity
        if validity == self._validity:
            return validity
        elif validity == 'valid':
            return self._validity
        else:
            return 'notKnown'

    @property
    def use_meta(self):
        return self.validator.meta_schema is None or \
            self.validator.meta_schema in self._schemas

    @property
    def total_globals(self):
        """Total number of global components, fully and partially built."""
        return sum(len(m) for m in self.global_maps)

    @property
    def built_globals(self):
        """Total number of fully built global components."""
        return sum(1 for c in self.global_maps.iter_globals() if c.built)

    @property
    def incomplete_globals(self):
        """Total number of partially built global components."""
        return sum(1 for c in self.global_maps.iter_globals() if not c.built)

    @property
    def staged_globals(self):
        return sum(m.get_total_staged() for m in self.global_maps)

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

    @property
    def total_errors(self) -> int:
        return sum(s.total_errors for s in self._schemas)

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

    def iter_components(self, xsd_classes: Optional[ClassInfoType[XsdComponent]] = None) \
            -> Iterator[Union['XsdGlobals', XsdComponent]]:
        """Creates an iterator for the XSD components of built schemas."""
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        for xsd_global in self.global_maps.iter_globals():
            yield from xsd_global.iter_components(xsd_classes)

    def iter_globals(self) -> Iterator[SchemaGlobalType]:
        """Creates an iterator for the built XSD global components."""
        return self.global_maps.iter_globals()

    def iter_staged(self) -> Iterator[StagedItemType]:
        """Creates an iterator for the unbuilt XSD global components."""
        return self.global_maps.iter_staged()

    def iter_schemas(self) -> Iterator[SchemaType]:
        """Creates an iterator for the registered schemas."""
        yield from self._schemas

    def iter_ancestors(self) -> Iterator[SchemaType]:
        ancestors: list[SchemaType] = []
        parent = self._parent
        while parent is not None:
            ancestors.append(parent)
            parent = parent.maps._parent

        yield from reversed(ancestors)

    def get_schema(self, source: SchemaSourceType, base_url: Optional[str] = None) \
            -> Optional[SchemaType]:

        if isinstance(source, XMLResource):
            url = source.url
            source = source.source
        else:
            url = get_url(source)

        if url is not None:
            url = normalize_url(url, base_url)
            for schema in self._schemas:
                if url == schema.url:
                    return schema

        for schema in self._schemas:
            if source is schema.source.source:
                return schema

        return None

    def register(self, schema: SchemaType) -> None:
        """Registers an XMLSchema instance."""
        namespace = schema.target_namespace
        if schema not in self._schemas:
            if (other_schema := self.get_schema(schema.url or schema.source)) is not None:
                if other_schema.maps is self:
                    raise XMLSchemaValueError(
                        f"another schema loaded from {schema.source} is already registered"
                    )

            self._schemas.add(schema)

            try:
                ns_schemas = self.namespaces[namespace]
            except KeyError:
                self.namespaces[namespace] = [schema]
            else:
                ns_schemas.append(schema)
                if ns_schemas[0].maps is not self:
                    if not hasattr(schema, 'maps'):
                        schema.maps = self
                    self.collapse_to(ns_schemas[0].maps.validator)

            if self._validation_attempted == 'full':
                self._validation_attempted = 'partial'
            if self._validity == 'valid':
                self._validity = 'notKnown'

        # TODO: rebuild NamespaceView using a using a descriptor that checks maps binding
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
        substitution_groups = self.substitution_groups.copy()
        identities = self.identities.copy()

        if not self.validator.loader.load_namespace(namespace):
            return False

        try:
            self.build()
        except XMLSchemaNotBuiltError:
            self.clear()
            self.global_maps.update(global_maps)
            self.substitution_groups.update(substitution_groups)
            self.identities.update(identities)
            return False
        else:
            return True

    def collapse_to(self, ancestor: SchemaType) -> None:
        self.clear()
        do_copy = True
        for validator in self.iter_ancestors():
            if ancestor is validator:
                do_copy = True
                self._parent = validator.maps._parent
            if do_copy:
                maps = validator.maps
                for schema in maps._schemas:
                    if schema.maps is maps:
                        schema.copy().__dict__['maps'] = self

    def clear(self, remove_schemas: bool = False) -> None:
        """
        Clears the instance maps and schemas.

        :param remove_schemas: removes also the schema instances, keeping only the \
        validator that created the global maps instance and schemas and namespaces \
        inherited from ancestors.
        """
        self.global_maps.clear()
        self.substitution_groups.clear()
        self.identities.clear()

        for schema in self._schemas:
            if schema.maps is self:
                schema.clear()   # clear XPath and component lazy properties

        if remove_schemas:
            self._schemas.clear()
            self.namespaces.clear()

            for ancestor in self.iter_ancestors():
                self._schemas.update(ancestor.maps._schemas)
                self.namespaces.update(ancestor.maps.namespaces)

            self.register(self.validator)

        self._validation_attempted = 'none'
        self._validity = 'notKnown'

    def build(self) -> None:
        """
        Build the maps of XSD global definitions/declarations. The global maps are
        updated adding and building the globals of not built registered schemas.
        """
        if self.built:
            return

        with self._build_lock:
            if self.built:
                return

            self.check_schemas()
            self.clear()

            for ancestor in self.iter_ancestors():
                ancestor.maps.build()
                self.global_maps.update(ancestor.maps.global_maps)
                self.substitution_groups.update(ancestor.maps.substitution_groups)
                self.identities.update(ancestor.maps.identities)

            target_schemas = [s for s in self.schemas if s.maps is self]

            self.global_maps.load_globals(target_schemas)
            initial_staged = self.staged_globals

            self.types.build_builtins()
            self.notations.build()
            self.attributes.build()
            self.attribute_groups.build()

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

            self.types.build()
            self.elements.build()
            self.groups.build()

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

            # Save totals for a fast integrity check on globals maps
            self._staged_globals = self.staged_globals

            if not initial_staged:
                self._validation_attempted = 'full'
            elif 0 < (still_staged := self.staged_globals) < initial_staged:
                self._validation_attempted = 'partial'
            else:
                self._validation_attempted = 'none' if still_staged else 'full'

            if self.total_errors:
                self._validity = 'invalid'
            elif self._validation_attempted != 'full':
                self._validity = 'notKnown'
            else:
                self._validity = 'valid'

            self.check_validator()

    def check_schemas(self) -> None:
        """Checks the coherence of schema registrations."""
        if self.validator not in self._schemas:
            raise XMLSchemaValueError(_('global maps main validator is not registered'))

        if nm.XML_NAMESPACE not in self.namespaces:
            self.load_namespace(nm.XML_NAMESPACE)

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
        self.check_validator()
        if schemas is None:
            _schemas = [s for s in self._schemas if s.maps is self]
        else:
            _schemas = schemas

        # Checks substitution groups circularity
        for qname in self.substitution_groups:
            xsd_element = self.elements[qname]
            assert isinstance(xsd_element, XsdElement), _("global element not built!")
            if any(e is xsd_element for e in xsd_element.iter_substitutes()):
                msg = _("circularity found for substitution group with head element {}")
                xsd_element.parse_error(msg.format(xsd_element))

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
