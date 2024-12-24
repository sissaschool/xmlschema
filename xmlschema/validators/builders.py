#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import importlib
from abc import abstractmethod
from collections import Counter
from collections.abc import Callable, ItemsView, Iterator, Mapping, ValuesView
from copy import copy as shallow_copy
from typing import Any, cast, Optional, overload, Union, Type, TypeVar
from xml.etree.ElementTree import Element

from elementpath import XPath2Parser

from xmlschema.aliases import BaseXsdType, ElementType, LoadedItemType, \
    SchemaType, StagedItemType
from xmlschema.exceptions import XMLSchemaAttributeError, XMLSchemaKeyError, \
    XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.translation import gettext as _
import xmlschema.names as nm
from xmlschema.utils.qnames import local_name, get_qname
from xmlschema.xpath.assertion_parser import XsdAssertionXPathParser

from .helpers import get_xsd_derivation_attribute
from .exceptions import XMLSchemaCircularityError
from .xsdbase import XsdComponent, XsdAnnotation
from .builtins import BUILTIN_TYPES
from .facets import XsdFacet, FACETS_BUILDERS
from .identities import XsdIdentity, IDENTITY_BUILDERS
from .simple_types import XsdSimpleType, XsdAtomicBuiltin, XsdAtomicRestriction, \
    Xsd11AtomicRestriction, SIMPLE_BUILDERS
from .notations import XsdNotation
from .attributes import XsdAttribute, Xsd11Attribute, XsdAttributeGroup
from .complex_types import XsdComplexType, Xsd11ComplexType
from .wildcards import XsdAnyElement, Xsd11AnyElement, XsdAnyAttribute, Xsd11AnyAttribute
from .groups import XsdGroup, Xsd11Group
from .elements import XsdElement, Xsd11Element


# Elements for building dummy groups
ATTRIBUTE_GROUP_ELEMENT = Element(nm.XSD_ATTRIBUTE_GROUP)
ANY_ATTRIBUTE_ELEMENT = Element(
    nm.XSD_ANY_ATTRIBUTE, attrib={'namespace': '##any', 'processContents': 'lax'}
)
SEQUENCE_ELEMENT = Element(nm.XSD_SEQUENCE)
ANY_ELEMENT = Element(
    nm.XSD_ANY,
    attrib={
        'namespace': '##any',
        'processContents': 'lax',
        'minOccurs': '0',
        'maxOccurs': 'unbounded'
    })


class XsdBuilders:
    """
    A descriptor dataclass for providing versioned builders for XSD components.
    It's instantiated on a schema class, and it configures itself looking the
    XSD_VERSION of the class.
    """
    facets: dict[str, Type[XsdFacet]]
    identities: dict[str, Type[XsdIdentity]]
    simple_types: dict[str, Type[XsdSimpleType]]
    builtins: tuple[dict[str, Any], ...]

    __slots__ = ('facets', 'identities', 'simple_types', '__dict__')

    def __set_name__(self, cls: Type[SchemaType], name: str) -> None:
        self._name = name
        self._schema_class = cls

        try:
            self.facets = FACETS_BUILDERS[cls.XSD_VERSION]
            self.identities = IDENTITY_BUILDERS[cls.XSD_VERSION]
            self.simple_types = SIMPLE_BUILDERS[cls.XSD_VERSION]
            self.builtins = BUILTIN_TYPES[cls.XSD_VERSION]
        except KeyError as err:
            raise XMLSchemaValueError("wrong or unsupported XSD version {}".format(err))

        self.simple_type_class = XsdSimpleType
        self.notation_class = XsdNotation
        self.attribute_group_class = XsdAttributeGroup

        if cls.XSD_VERSION == '1.0':
            self.complex_type_class = XsdComplexType
            self.attribute_class = XsdAttribute
            self.group_class = XsdGroup
            self.element_class = XsdElement
            self.any_element_class = XsdAnyElement
            self.any_attribute_class = XsdAnyAttribute
            self.atomic_restriction_class = XsdAtomicRestriction
        else:
            self.complex_type_class = Xsd11ComplexType
            self.attribute_class = Xsd11Attribute
            self.group_class = Xsd11Group
            self.element_class = Xsd11Element
            self.any_element_class = Xsd11AnyElement
            self.any_attribute_class = Xsd11AnyAttribute
            self.atomic_restriction_class = Xsd11AtomicRestriction

    @overload
    def __get__(self, schema: None, cls: Type[SchemaType]) -> 'XsdBuilders': ...

    @overload
    def __get__(self, schema: SchemaType, cls: Type[SchemaType]) -> 'XsdBuilders': ...

    def __get__(self, schema: Optional[SchemaType], cls: Type[SchemaType]) \
            -> 'XsdBuilders':
        return self

    def __set__(self, instance: Any, value: Any) -> None:
        raise XMLSchemaAttributeError(_("Can't set attribute {}").format(self._name))

    def __delete__(self, instance: Any) -> None:
        raise XMLSchemaAttributeError(_("Can't delete attribute {}").format(self._name))

    @property
    def xsd_version(self) -> str:
        return self._schema_class.XSD_VERSION

    def create_any_content_group(self, parent: Union[XsdComplexType, XsdGroup],
                                 any_element: Optional[XsdAnyElement] = None) -> XsdGroup:
        """
        Creates a local child model group for a complex type or a group that accepts any content.

        :param parent: the parent complex type or group for the content group.
        :param any_element: an optional any element to use for the content group. \
        When provided it's copied, linked to the group and the minOccurs/maxOccurs \
        are set to 0 and 'unbounded'.
        """
        schema = parent.schema
        group: XsdGroup = self.group_class(SEQUENCE_ELEMENT, schema, parent)

        if isinstance(any_element, XsdAnyElement):
            particle = shallow_copy(any_element)
            particle.min_occurs = 0
            particle.max_occurs = None
            particle.parent = group
            group.append(particle)
        else:
            group.append(self.any_element_class(ANY_ELEMENT, schema, group))

        return group

    def create_empty_content_group(self, parent: Union[XsdComplexType, XsdGroup],
                                   model: str = 'sequence', **attrib: Any) -> XsdGroup:
        """
        Creates an empty local child content group for a complex type or a group.
        """
        if model == 'sequence':
            group_elem = Element(nm.XSD_SEQUENCE, **attrib)
        elif model == 'choice':
            group_elem = Element(nm.XSD_CHOICE, **attrib)
        elif model == 'all':
            group_elem = Element(nm.XSD_ALL, **attrib)
        else:
            msg = _("'model' argument must be (sequence | choice | all)")
            raise XMLSchemaValueError(msg)

        group_elem.text = '\n    '
        return self.group_class(group_elem, parent.schema, parent)

    def create_any_attribute_group(self, parent: Union[XsdComplexType, XsdElement]) \
            -> XsdAttributeGroup:
        """
        Creates a local child attribute group for a complex type or an element
        that accepts any attribute.
        """
        attribute_group = self.attribute_group_class(
            ATTRIBUTE_GROUP_ELEMENT, parent.schema, parent
        )
        attribute_group[None] = self.any_attribute_class(
            ANY_ATTRIBUTE_ELEMENT, parent.schema, attribute_group
        )
        return attribute_group

    def create_empty_attribute_group(self, parent: Union[XsdComplexType, XsdElement]) \
            -> XsdAttributeGroup:
        """
        Creates an empty local child attribute group for a complex type or an element.
        """
        return self.attribute_group_class(ATTRIBUTE_GROUP_ELEMENT, parent.schema, parent)

    def create_any_type(self, schema: SchemaType) -> XsdComplexType:
        """
        Creates a xs:anyType equivalent type related with the wildcards
        connected to global maps of the schema instance in order to do a
        correct namespace lookup during wildcards validation.
        """
        maps = schema.maps
        if schema.meta_schema is not None and schema.target_namespace != nm.XSD_NAMESPACE:
            schema = schema.meta_schema

        any_type = self.complex_type_class(
            elem=Element(nm.XSD_COMPLEX_TYPE, name=nm.XSD_ANY_TYPE),
            schema=schema, parent=None, mixed=True, block='', final=''
        )
        assert isinstance(any_type.content, XsdGroup)
        any_type.content.append(self.any_element_class(
            ANY_ELEMENT, schema, any_type.content
        ))
        any_type.attributes[None] = self.any_attribute_class(
            ANY_ATTRIBUTE_ELEMENT, schema, any_type.attributes
        )

        if maps is not schema.maps:
            any_type.maps = any_type.content.maps = any_type.content[0].maps = \
                any_type.attributes[None].maps = schema.maps

        return any_type

    def create_element(self, name: str,
                       schema: SchemaType,
                       parent: Optional[XsdComponent] = None,
                       text: Optional[str] = None, **attrib: Any) -> XsdElement:
        """
        Creates a xs:element instance related to schema component.
        Used as dummy element for validation/decoding/encoding
        operations of wildcards and complex types.
        """
        elem = Element(nm.XSD_ELEMENT, name=name, **attrib)
        if text is not None:
            elem.text = text
        return self.element_class(elem, schema, parent)


class SchemaConfig:
    """Store a schema instance configuration."""
    xpath_parser_class: Type[XPath2Parser]
    assertion_parser_class: Type[XsdAssertionXPathParser]

    def __init__(self, schema: SchemaType):
        self.schema_class = type(schema)
        self.builders = schema.builders

        # Save other validator init options, used for creating new schemas.
        self.schema_options: dict[str, Any] = {
            'validation': schema.validation,
            'converter': schema.converter,
            'allow': schema.source.allow,
            'defuse': schema.source.defuse,
            'timeout': schema.source.timeout,
            'uri_mapper': schema.source.uri_mapper,
            'opener': schema.source.opener,
            'use_xpath3': schema.use_xpath3,
        }

        if not schema.use_xpath3:
            self.xpath_parser_class = XPath2Parser
            self.assertion_parser_class = XsdAssertionXPathParser
        else:
            module = importlib.import_module('xmlschema.xpath.xpath3')
            self.xpath_parser_class = module.XPath3Parser
            self.assertion_parser_class = module.XsdAssertionXPath3Parser


CT = TypeVar('CT', bound=XsdComponent)

BuilderType = Callable[[ElementType, SchemaType], CT]
LocalBuilderType = Callable[[str], Callable[[ElementType, SchemaType, Optional[XsdComponent]], CT]]


class StagedMap(Mapping[str, CT]):
    label = 'component'

    @abstractmethod
    def get_builder(self) -> Callable[[ElementType, SchemaType], CT]:
        """Returns the builder class or method used to build the global map."""

    def __init__(self, validator: SchemaType):
        self._store: dict[str, CT] = {}
        self._staging: dict[str, StagedItemType] = {}
        self._validator = validator
        self._builders = validator.builders
        self._factory_or_class = self.get_builder()

        # Schema counters for built and staged component
        self._store_counter: Counter[SchemaType] = Counter()
        self._staging_counter: Counter[SchemaType] = Counter()

    def __getitem__(self, qname: str) -> CT:
        try:
            return self._store[qname]
        except KeyError:
            if qname in self._staging:
                return self._build_global(qname)

            msg = _('global {} {!r} not found').format(self.label, qname)
            raise XMLSchemaKeyError(msg) from None

    def __iter__(self) -> Iterator[str]:
        yield from self._store

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return repr(self._store)

    def copy(self) -> 'StagedMap[CT]':
        obj = object.__new__(self.__class__)
        obj.__dict__.update(self.__dict__)
        obj._staging = self._staging.copy()
        obj._store = self._store.copy()
        obj._store_counter = self._store_counter.copy()
        obj._staging_counter = self._staging_counter.copy()
        return obj

    __copy__ = copy

    def clear(self) -> None:
        self._store.clear()
        self._staging.clear()
        self._store_counter.clear()
        self._staging_counter.clear()

    def update(self, other: 'StagedMap[CT]') -> None:
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

    def load(self, qname: str, elem: ElementType, schema: SchemaType) -> None:
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

            if len(obj) == 2 and isinstance(obj, tuple):
                _elem, _schema = obj  # type:ignore[misc]
                if _elem is elem and _schema is schema:
                    return  # ignored: it's the same component
                elif schema is _schema.override:
                    return  # ignored: the loaded component is overridden
                elif schema.override is _schema:
                    # replaced: the loaded component is an override
                    self._staging[qname] = (elem, schema)
                    return
                elif schema.meta_schema is None and _schema.meta_schema is not None:
                    return  # ignore merged meta-schema components
                elif _schema.meta_schema is None and schema.meta_schema is not None:
                    # Override merged meta-schema component
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

    def load_redefine(self, qname: str, elem: ElementType, schema: SchemaType) -> None:
        try:
            item = self._staging[qname]
        except KeyError:
            schema.parse_error(_("not a redefinition!"), elem)
        else:
            if isinstance(item, list):
                item.append((elem, schema))
            else:
                self._staging[qname] = [cast(LoadedItemType, item), (elem, schema)]

    def load_override(self, qname: str, elem: ElementType, schema: SchemaType) -> None:
        if qname not in self._staging:
            # Overrides that match nothing in the target schema are ignored. See the
            # period starting with "Source declarations not present in the target set"
            # of the paragraph https://www.w3.org/TR/xmlschema11-1/#override-schema.
            return

        self._staging[qname] = elem, schema

    def build(self) -> None:
        for name in [x for x in self._staging]:
            if name in self._staging:
                self._build_global(name)

    def _build_global(self, qname: str) -> CT:
        obj = self._staging[qname]
        if isinstance(obj, tuple):
            # Not built XSD global component without redefinitions
            try:
                elem, schema = obj  # type: ignore[misc]
            except ValueError:
                raise XMLSchemaCircularityError(qname, *obj[0])

            # Encapsulate into a tuple to catch circular builds
            self._staging[qname] = cast(LoadedItemType, (obj,))

            self._store[qname] = self._factory_or_class(elem, schema)
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
                raise XMLSchemaCircularityError(qname, *obj[0][0])

            self._staging[qname] = obj[0],  # To catch circular builds
            self._store[qname] = component = self._factory_or_class(elem, schema)
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


class TypesMap(StagedMap[BaseXsdType]):

    def __init__(self, validator: SchemaType):
        super().__init__(validator)
        self._complex_type_class = validator.builders.complex_type_class
        self._simple_types = validator.builders.simple_types
        self._facets_builders = validator.builders.facets

    def get_builder(self) -> Callable[[ElementType, SchemaType], BaseXsdType]:
        return self._build_global_type

    def _build_global_type(self, elem: ElementType, schema: SchemaType) -> BaseXsdType:
        if elem.tag == nm.XSD_COMPLEX_TYPE:
            return self._complex_type_class(elem, schema)
        else:
            return self.simple_type_factory(elem, schema)

    def build_builtins(self) -> None:
        if self._validator.meta_schema is not None and nm.XSD_ANY_TYPE in self._store:
            # builtin types already provided, rebuild only xs:anyType for wildcards
            self._store[nm.XSD_ANY_TYPE] = self._builders.create_any_type(self._validator)
            return

        #
        # Special builtin types.
        #
        # xs:anyType
        # Ref: https://www.w3.org/TR/xmlschema11-1/#builtin-ctd
        self._store[nm.XSD_ANY_TYPE] = self._builders.create_any_type(self._validator)

        # xs:anySimpleType
        # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
        any_simple_type = self._store[nm.XSD_ANY_SIMPLE_TYPE] = XsdSimpleType(
            elem=Element(nm.XSD_SIMPLE_TYPE, name=nm.XSD_ANY_SIMPLE_TYPE),
            schema=self._validator,
            parent=None,
            name=nm.XSD_ANY_SIMPLE_TYPE
        )

        # xs:anyAtomicType
        # Ref: https://www.w3.org/TR/xmlschema11-2/#builtin-stds
        self._store[nm.XSD_ANY_ATOMIC_TYPE] = \
            self._validator.builders.atomic_restriction_class(
                elem=Element(nm.XSD_SIMPLE_TYPE, name=nm.XSD_ANY_ATOMIC_TYPE),
                schema=self._validator,
                parent=None,
                name=nm.XSD_ANY_ATOMIC_TYPE,
                base_type=any_simple_type,
            )

        for item in self._builders.builtins:
            item = item.copy()
            name: str = item['name']
            try:
                value = self._staging.pop(name)
            except KeyError:
                # If builtin type element is missing create a dummy element. Necessary for the
                # meta-schema XMLSchema.xsd of XSD 1.1, that not includes builtins declarations.
                elem = Element(nm.XSD_SIMPLE_TYPE, name=name, id=name)
            else:
                if not isinstance(value, tuple) or len(value) != 2:
                    continue
                elem, schema = value

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
                        cls = self._facets_builders[e.tag]
                    except AttributeError:
                        built_facets[None] = e
                    else:
                        built_facets[e.tag] = cls(e, self._validator, xsd_type, base_type)
                xsd_type.facets = built_facets

            self._store[name] = xsd_type

    def simple_type_factory(self, elem: Element,
                            schema: SchemaType,
                            parent: Optional[XsdComponent] = None) -> XsdSimpleType:
        """
        Factory function for XSD simple types. Parses the xs:simpleType element and its
        child component, that can be a restriction, a list or a union. Annotations are
        linked to simple type instance, omitting the inner annotation if both are given.
        """
        annotation: Optional[XsdAnnotation] = None
        try:
            child = elem[0]
        except IndexError:
            return cast(XsdSimpleType, self._store[nm.XSD_ANY_SIMPLE_TYPE])
        else:
            if child.tag == nm.XSD_ANNOTATION:
                annotation = XsdAnnotation(child, schema, parent)
                try:
                    child = elem[1]
                except IndexError:
                    msg = _("(restriction | list | union) expected")
                    schema.parse_error(msg, elem)
                    return cast(XsdSimpleType, self._store[nm.XSD_ANY_SIMPLE_TYPE])

        xsd_type: XsdSimpleType
        try:
            xsd_type = self._simple_types[child.tag](child, schema, parent)
        except KeyError:
            msg = _("(restriction | list | union) expected")
            schema.parse_error(msg, elem)
            return cast(XsdSimpleType, self._store[nm.XSD_ANY_SIMPLE_TYPE])

        if annotation is not None:
            xsd_type._annotation = annotation

        try:
            xsd_type.name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            if parent is None:
                msg = _("missing attribute 'name' in a global simpleType")
                schema.parse_error(msg, elem)
                xsd_type.name = 'nameless_%s' % str(id(xsd_type))
        else:
            if parent is not None:
                msg = _("attribute 'name' not allowed for a local simpleType")
                schema.parse_error(msg, elem)
                xsd_type.name = None

        if 'final' in elem.attrib:
            try:
                xsd_type._final = get_xsd_derivation_attribute(elem, 'final')
            except ValueError as err:
                xsd_type.parse_error(err, elem)

        return xsd_type


class NotationsMap(StagedMap[XsdNotation]):
    def get_builder(self) -> Callable[[ElementType, SchemaType], XsdNotation]:
        return self._builders.notation_class


class AttributesMap(StagedMap[XsdAttribute]):
    def get_builder(self) -> Callable[[ElementType, SchemaType], XsdAttribute]:
        return self._builders.attribute_class


class AttributeGroupsMap(StagedMap[XsdAttributeGroup]):
    def get_builder(self) -> Callable[[ElementType, SchemaType], XsdAttributeGroup]:
        return self._builders.attribute_group_class


class ElementsMap(StagedMap[XsdElement]):
    def get_builder(self) -> Callable[[ElementType, SchemaType], XsdElement]:
        return self._builders.element_class


class GroupsMap(StagedMap[XsdGroup]):
    def get_builder(self) -> Callable[[ElementType, SchemaType], XsdGroup]:
        return self._builders.group_class
