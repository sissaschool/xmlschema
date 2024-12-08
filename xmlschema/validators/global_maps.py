#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import threading
import warnings
from collections import Counter
from collections.abc import Callable, Collection, Iterator, Iterable, Mapping
from itertools import dropwhile
from operator import itemgetter
from types import MappingProxyType
from typing import Any, cast, NamedTuple, Optional, Union, Type, TypeVar

from xmlschema.aliases import ClassInfoType, SchemaSourceType, \
    SchemaType, BaseXsdType, SchemaGlobalType, NsmapType, StagedItemType
from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, \
    XMLSchemaValueError, XMLSchemaWarning, XMLSchemaNamespaceError
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import local_name, get_extended_qname
from xmlschema.utils.urls import get_url, normalize_url
from xmlschema.loaders import NamespaceResourcesMap, SchemaLoader
from xmlschema.resources import XMLResource
import xmlschema.names as nm

from .exceptions import XMLSchemaNotBuiltError, XMLSchemaModelError, \
    XMLSchemaModelDepthError, XMLSchemaParseError
from .xsdbase import XsdValidator, XsdComponent
from .models import check_model
from . import XsdAttribute, XsdSimpleType, XsdComplexType, XsdElement, \
    XsdAttributeGroup, XsdGroup, XsdNotation, XsdIdentity, XsdAssert, \
    XsdUnion, XsdAtomicRestriction
from .builders import TypesMap, NotationsMap, AttributesMap, \
    AttributeGroupsMap, ElementsMap, GroupsMap

GLOBAL_TAGS = frozenset((
    nm.XSD_NOTATION, nm.XSD_SIMPLE_TYPE, nm.XSD_COMPLEX_TYPE,
    nm.XSD_ATTRIBUTE, nm.XSD_ATTRIBUTE_GROUP, nm.XSD_GROUP, nm.XSD_ELEMENT
))

_GLOBAL_GETTERS = MappingProxyType({
    nm.XSD_SIMPLE_TYPE: itemgetter(0),
    nm.XSD_COMPLEX_TYPE: itemgetter(0),
    nm.XSD_NOTATION: itemgetter(1),
    nm.XSD_ATTRIBUTE: itemgetter(2),
    nm.XSD_ATTRIBUTE_GROUP: itemgetter(3),
    nm.XSD_ELEMENT: itemgetter(4),
    nm.XSD_GROUP: itemgetter(5),
})


class GlobalMaps(NamedTuple):
    types: TypesMap
    notations: NotationsMap
    attributes: AttributesMap
    attribute_groups: AttributeGroupsMap
    elements: ElementsMap
    groups: GroupsMap

    def clear(self) -> None:
        for item in self:
            item.clear()

    def update(self, other: 'GlobalMaps') -> None:
        for m1, m2 in zip(self, other):
            m1.update(m2)  # type: ignore[attr-defined]

    def copy(self) -> 'GlobalMaps':
        return GlobalMaps(*[m.copy() for m in self])  # type: ignore[arg-type]

    def iter_globals(self) -> Iterator[SchemaGlobalType]:
        for item in self:
            yield from item.values()

    def iter_staged(self) -> Iterator[StagedItemType]:
        for item in self:
            yield from item.staged_values

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

                    _GLOBAL_GETTERS[tag](self).load(qname, elem, schema)

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

            if elem.tag == nm.XSD_REDEFINE:
                _GLOBAL_GETTERS[child.tag](self).load_redefine(qname, child, schema)
            else:
                _GLOBAL_GETTERS[child.tag](self).load_override(qname, child, schema)


T = TypeVar('T', bound=Union[XsdComponent, set[XsdElement]])


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


class XsdGlobals(XsdValidator, Collection[SchemaType]):
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
    namespaces: NamespaceResourcesMap[SchemaType]
    loader: SchemaLoader

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

        self.types = TypesMap(self.validator)
        self.notations = NotationsMap(self.validator)
        self.attributes = AttributesMap(self.validator)
        self.attribute_groups = AttributeGroupsMap(self.validator)
        self.elements = ElementsMap(self.validator)
        self.groups = GroupsMap(self.validator)
        self.global_maps = GlobalMaps(*(getattr(self, n) for n in GlobalMaps._fields))

        self.substitution_groups = {}
        self.identities = {}

        self.loader = (loader or SchemaLoader)(self)

        for ancestor in self.iter_ancestors():
            self._schemas.update(ancestor.maps.schemas)
            self.namespaces.update(ancestor.maps.namespaces)

        self.validator.maps = self

    @property
    def schemas(self) -> set[SchemaType]:
        return self._schemas

    @property
    def parent(self) -> Optional[SchemaType]:
        return self._parent

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
        for schema in self._schemas:
            if schema.maps is self and schema is not self.validator:
                schema.copy().maps = obj

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
    def use_meta(self) -> bool:
        return self.validator.meta_schema is None or \
            self.validator.meta_schema in self._schemas

    @property
    def total_globals(self) -> int:
        """Total number of global components, fully and partially built."""
        return sum(len(m) for m in self.global_maps)

    @property
    def built_globals(self) -> int:
        """Total number of fully built global components."""
        return sum(1 for c in self.global_maps.iter_globals() if c.built)

    @property
    def incomplete_globals(self) -> int:
        """Total number of partially built global components."""
        return sum(1 for c in self.global_maps.iter_globals() if not c.built)

    @property
    def staged_globals(self) -> int:
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
            parent = parent.maps.parent

        yield from reversed(ancestors)

    def get_schema(self, source: SchemaSourceType, base_url: Optional[str] = None) \
            -> Optional[SchemaType]:

        if isinstance(source, XMLResource):
            url = source.url
            _source = source.source
        else:
            url = get_url(source)
            _source = source

        if url is not None:
            url = normalize_url(url, base_url)
            for schema in self._schemas:
                if url == schema.url:
                    return schema

        for schema in self._schemas:
            if _source is schema.source.source:
                return schema

        return None

    def register(self, schema: SchemaType) -> None:
        """Registers an XMLSchema instance."""
        if schema in self._schemas:
            return

        if (other_schema := self.get_schema(schema.url or schema.source)) is not None:
            if other_schema.maps is self:
                raise XMLSchemaValueError(
                    f"another schema loaded from {schema.source} is already registered"
                )

        namespace = schema.target_namespace

        """
        schema.notations = NamespaceView(self.notations, namespace)
        schema.types = NamespaceView(self.types, namespace)
        schema.attributes = NamespaceView(self.attributes, namespace)
        schema.attribute_groups = NamespaceView(self.attribute_groups, namespace)
        schema.groups = NamespaceView(self.groups, namespace)
        schema.elements = NamespaceView(self.elements, namespace)
        schema.substitution_groups = NamespaceView(self.substitution_groups, namespace)
        schema.identities = NamespaceView(self.identities, namespace)

        schema.loader = self.loader
        """

        self._schemas.add(schema)

        if namespace not in self.namespaces:
            self.namespaces[namespace] = [schema]
        elif (ns_schemas := self.namespaces[namespace])[0].maps is self:
            ns_schemas.append(schema)
        else:
            ns_schemas.append(schema)
            schema.maps = self
            self.merge(ancestor=ns_schemas[0].maps.validator)

        if self._validation_attempted == 'full':
            self._validation_attempted = 'partial'
        if self._validity == 'valid':
            self._validity = 'notKnown'

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

    def merge(self, ancestor: SchemaType) -> None:
        """Merge the global maps until to a specific ancestor."""
        self.clear()
        for validator in dropwhile(lambda x: x is not ancestor, self.iter_ancestors()):
            maps = validator.maps
            for schema in maps._schemas:
                if schema.maps is maps:
                    namespace = schema.target_namespace
                    self._schemas.remove(schema)
                    k = self.namespaces[namespace].index(schema)

                    schema = schema.copy()
                    schema.__dict__['maps'] = self

                    self._schemas.add(schema)
                    self.namespaces[namespace][k] = schema

        self._parent = ancestor.maps._parent

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

            target_schemas = [s for s in self._schemas if s.maps is self]

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
                    schema.default_attributes = attributes

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
        if schemas is not None:
            _schemas = schemas
        else:
            _schemas = [s for s in self._schemas if s.maps is self]

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
