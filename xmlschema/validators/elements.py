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
This module contains classes for XML Schema elements, complex types and model groups.
"""
import warnings
from copy import copy as _copy
from decimal import Decimal
from types import GeneratorType
from typing import TYPE_CHECKING, cast, Any, Dict, Iterator, List, Optional, \
    Set, Tuple, Type, Union
from xml.etree.ElementTree import Element, ParseError

from elementpath import XPath2Parser, ElementPathError, XPathContext, XPathToken, \
    ElementNode, LazyElementNode, SchemaElementNode, build_schema_node_tree
from elementpath.datatypes import AbstractDateTime, Duration, AbstractBinary

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..names import XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE, XSD_ALTERNATIVE, \
    XSD_ELEMENT, XSD_ANY_TYPE, XSD_UNIQUE, XSD_KEY, XSD_KEYREF, XSI_NIL, \
    XSI_TYPE, XSD_ERROR, XSD_NOTATION_TYPE
from ..aliases import ElementType, SchemaType, BaseXsdType, SchemaElementType, \
    ModelParticleType, ComponentClassType, AtomicValueType, DecodeType, \
    IterDecodeType, IterEncodeType
from ..translation import gettext as _
from ..helpers import get_qname, etree_iter_location_hints, \
    etree_iter_namespaces, raw_xml_encode, strictly_equal
from ..namespaces import NamespaceMapper
from ..locations import normalize_url
from .. import dataobjects
from ..converters import ElementData, XMLSchemaConverter
from ..xpath import XMLSchemaProxy, ElementPathMixin, XPathElement
from ..resources import XMLResource

from .exceptions import XMLSchemaValidationError, XMLSchemaParseError, \
    XMLSchemaStopValidation, XMLSchemaTypeTableWarning
from .helpers import get_xsd_derivation_attribute
from .xsdbase import XSD_TYPE_DERIVATIONS, XSD_ELEMENT_DERIVATIONS, \
    XSD_VALIDATION_MODES, XsdComponent, ValidationMixin
from .particles import ParticleMixin, OccursCalculator
from .identities import XsdIdentity, XsdKey, XsdUnique, \
    XsdKeyref, KeyrefCounter, FieldValueSelector
from .simple_types import XsdSimpleType
from .attributes import XsdAttribute
from .wildcards import XsdAnyElement

if TYPE_CHECKING:
    from .attributes import XsdAttributeGroup
    from .groups import XsdGroup

DataBindingType = Type['dataobjects.DataElement']


class XsdElement(XsdComponent, ParticleMixin,
                 ElementPathMixin[SchemaElementType],
                 ValidationMixin[ElementType, Any]):
    """
    Class for XSD 1.0 *element* declarations.

    :ivar type: the XSD simpleType or complexType of the element.
    :ivar attributes: the group of the attributes associated with the element.

    ..  <element
          abstract = boolean : false
          block = (#all | List of (extension | restriction | substitution))
          default = string
          final = (#all | List of (extension | restriction))
          fixed = string
          form = (qualified | unqualified)
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          name = NCName
          nillable = boolean : false
          ref = QName
          substitutionGroup = QName
          type = QName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, ((simpleType | complexType)?, (unique | key | keyref)*))
        </element>
    """
    name: str
    local_name: str
    qualified_name: str
    prefixed_name: str

    parent: Optional['XsdGroup']
    ref: Optional['XsdElement']
    attributes: 'XsdAttributeGroup'

    type: BaseXsdType
    abstract = False
    nillable = False
    qualified = False
    form: Optional[str] = None
    default: Optional[str] = None
    fixed: Optional[str] = None
    substitution_group: Optional[str] = None

    identities: List[XsdIdentity]
    selected_by: Set[XsdIdentity]
    alternatives: Union[Tuple[()], List['XsdAlternative']] = ()
    inheritable: Union[Tuple[()], Dict[str, XsdAttribute]] = ()

    _ADMITTED_TAGS = {XSD_ELEMENT}
    _block: Optional[str] = None
    _final: Optional[str] = None
    _head_type = None
    _build = True

    binding: Optional[DataBindingType] = None

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent] = None,
                 build: bool = True) -> None:

        if not build:
            self._build = False
        self.selected_by = set()
        super().__init__(elem, schema, parent)

    def __repr__(self) -> str:
        return '%s(%s=%r, occurs=%r)' % (
            self.__class__.__name__,
            'name' if self.ref is None else 'ref',
            self.prefixed_name,
            list(self.occurs)
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "type":
            if isinstance(value, XsdSimpleType):
                self.attributes = self.schema.create_empty_attribute_group(self)
            else:
                self.attributes = value.attributes
        super().__setattr__(name, value)

    def __iter__(self) -> Iterator[SchemaElementType]:
        if self.type.has_complex_content():
            yield from self.type.content.iter_elements()  # type: ignore[union-attr]

    def _parse(self) -> None:
        if not self._build:
            return

        self._parse_particle(self.elem)
        self._parse_attributes()

        if self.ref is None:
            self._parse_type()
            self._parse_constraints()

            if self.parent is None and 'substitutionGroup' in self.elem.attrib:
                self._parse_substitution_group(self.elem.attrib['substitutionGroup'])

    def _parse_attributes(self) -> None:
        attrib = self.elem.attrib
        if self._parse_reference():
            try:
                xsd_element: XsdElement = self.maps.lookup_element(self.name)
            except KeyError:
                self.type = self.any_type
                self.parse_error(_('unknown element %r') % self.name)
            else:
                self.ref = xsd_element
                self.type = xsd_element.type
                self.abstract = xsd_element.abstract
                self.nillable = xsd_element.nillable
                self.qualified = xsd_element.qualified
                self.form = xsd_element.form
                self.default = xsd_element.default
                self.fixed = xsd_element.fixed
                self.substitution_group = xsd_element.substitution_group
                self.identities = xsd_element.identities
                self.alternatives = xsd_element.alternatives
                self.selected_by = xsd_element.selected_by

            for attr_name in ('type', 'nillable', 'default', 'fixed', 'form',
                              'block', 'abstract', 'final', 'substitutionGroup'):
                if attr_name in attrib:
                    msg = _("attribute {!r} is not allowed when element reference is used")
                    self.parse_error(msg.format(attr_name))
            return

        if 'form' in attrib:
            self.form = attrib['form']
            if self.form == 'qualified':
                self.qualified = True
        elif self.schema.element_form_default == 'qualified':
            self.qualified = True

        try:
            if self.parent is None or self.qualified:
                self.name = get_qname(self.target_namespace, attrib['name'])
            else:
                self.name = attrib['name']
        except KeyError:
            pass

        if 'abstract' in attrib:
            if self.parent is not None:
                msg = _("local scope elements cannot have abstract attribute")
                self.parse_error(msg)
            if attrib['abstract'].strip() in ('true', '1'):
                self.abstract = True

        if 'block' in attrib:
            try:
                self._block = get_xsd_derivation_attribute(
                    self.elem, 'block', XSD_ELEMENT_DERIVATIONS
                )
            except ValueError as err:
                self.parse_error(err)

        if 'nillable' in attrib and attrib['nillable'].strip() in ('true', '1'):
            self.nillable = True

        if self.parent is None:
            if 'final' in attrib:
                try:
                    self._final = get_xsd_derivation_attribute(
                        self.elem, 'final', XSD_TYPE_DERIVATIONS
                    )
                except ValueError as err:
                    self.parse_error(err)

            for attr_name in ('ref', 'form', 'minOccurs', 'maxOccurs'):
                if attr_name in attrib:
                    msg = _("attribute {!r} is not allowed in a global element declaration")
                    self.parse_error(msg.format(attr_name))
        else:
            for attr_name in ('final', 'substitutionGroup'):
                if attr_name in attrib:
                    msg = _("attribute {!r} not allowed in a local element declaration")
                    self.parse_error(msg.format(attr_name))

    def _parse_type(self) -> None:
        type_name = self.elem.get('type')
        if type_name is not None:
            try:
                extended_name = self.schema.resolve_qname(type_name)
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err)
                self.type = self.any_type
            else:
                if extended_name == XSD_ANY_TYPE:
                    self.type = self.any_type
                else:
                    try:
                        self.type = self.maps.lookup_type(extended_name)
                    except KeyError:
                        self.parse_error(_('unknown type {!r}').format(type_name))
                        self.type = self.any_type
            finally:
                child = self._parse_child_component(self.elem, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    msg = _("the attribute 'type' and a xs:{} local "
                            "declaration are mutually exclusive")
                    self.parse_error(msg.format(child.tag.split('}')[-1]))
        else:
            child = self._parse_child_component(self.elem, strict=False)
            if child is None:
                self.type = self.any_type
            elif child.tag == XSD_COMPLEX_TYPE:
                self.type = self.schema.xsd_complex_type_class(child, self.schema, self)
            elif child.tag == XSD_SIMPLE_TYPE:
                self.type = self.schema.simple_type_factory(child, self.schema, self)
            else:
                self.type = self.any_type

    def _parse_constraints(self) -> None:
        # Value constraints
        if 'default' in self.elem.attrib:
            self.default = self.elem.attrib['default']
            if 'fixed' in self.elem.attrib:
                msg = _("'default' and 'fixed' attributes are mutually exclusive")
                self.parse_error(msg)

            if not self.type.is_valid(self.default):
                msg = _("'default' value {!r} is not compatible with element's type")
                self.parse_error(msg.format(self.default))
                self.default = None
            elif self.xsd_version == '1.0' and self.type.is_key():
                msg = _("xs:ID or a type derived from xs:ID cannot have a default value")
                self.parse_error(msg)

        elif 'fixed' in self.elem.attrib:
            self.fixed = self.elem.attrib['fixed']
            if not self.type.is_valid(self.fixed):
                msg = _("'fixed' value {!r} is not compatible with element's type")
                self.parse_error(msg.format(self.fixed))
                self.fixed = None
            elif self.xsd_version == '1.0' and self.type.is_key():
                msg = _("xs:ID or a type derived from xs:ID cannot have a fixed value")
                self.parse_error(msg)

        # Identity constraints
        self.identities = []
        constraint: Union[XsdKey, XsdUnique, XsdKeyref]
        for child in self.elem:
            if child.tag == XSD_UNIQUE:
                constraint = self.schema.xsd_unique_class(child, self.schema, self)
            elif child.tag == XSD_KEY:
                constraint = self.schema.xsd_key_class(child, self.schema, self)
            elif child.tag == XSD_KEYREF:
                constraint = self.schema.xsd_keyref_class(child, self.schema, self)
            else:
                # Invalid tags already caught by validation against the meta-schema
                continue

            if constraint.ref:
                if any(constraint.name == x.name for x in self.identities):
                    msg = _("duplicated identity constraint %r:")
                    self.parse_error(msg % constraint.name, child)

                self.identities.append(constraint)
                continue

            try:
                if child != self.maps.identities[constraint.name].elem:
                    msg = _("duplicated identity constraint %r:")
                    self.parse_error(msg % constraint.name, child)
            except KeyError:
                self.maps.identities[constraint.name] = constraint
            finally:
                self.identities.append(constraint)

    def _parse_substitution_group(self, substitution_group: str) -> None:
        try:
            substitution_group_qname = self.schema.resolve_qname(substitution_group)
        except (KeyError, ValueError, RuntimeError) as err:
            self.parse_error(err)
            return
        else:
            if substitution_group_qname[0] != '{':
                substitution_group_qname = get_qname(
                    self.target_namespace, substitution_group_qname
                )

        try:
            head_element = self.maps.lookup_element(substitution_group_qname)
        except KeyError:
            msg = _("unknown substitutionGroup %r")
            self.parse_error(msg % substitution_group)
            return
        else:
            if isinstance(head_element, tuple):
                msg = _("circularity found for substitutionGroup %r")
                self.parse_error(msg % substitution_group)
                return
            elif 'substitution' in head_element.block:
                return

        final = head_element.final
        if self.type == head_element.type:
            pass
        elif self.type.name == XSD_ANY_TYPE:
            if head_element.type.name != XSD_ANY_TYPE:
                # Use head element's type for validate content
                # ref: https://www.w3.org/TR/xmlschema-1/#cElement_Declarations
                self._head_type = head_element.type
        elif not self.type.is_derived(head_element.type):
            msg = _("{0!r} type is not of the same or a derivation "
                    "of the head element {1!r} type")
            self.parse_error(msg.format(self, head_element))
        elif final == '#all' or 'extension' in final and 'restriction' in final:
            msg = _("head element %r can't be substituted by an "
                    "element that has a derivation of its type")
            self.parse_error(msg % head_element)
        elif 'extension' in final and self.type.is_derived(head_element.type, 'extension'):
            msg = _("head element %r can't be substituted by an "
                    "element that has an extension of its type")
            self.parse_error(msg % head_element)
        elif 'restriction' in final and self.type.is_derived(head_element.type, 'restriction'):
            msg = _("head element %r can't be substituted by an "
                    "element that has a restriction of its type")
            self.parse_error(msg % head_element)

        try:
            self.maps.substitution_groups[substitution_group_qname].add(self)
        except KeyError:
            self.maps.substitution_groups[substitution_group_qname] = {self}
        finally:
            self.substitution_group = substitution_group_qname

    @property
    def xpath_proxy(self) -> XMLSchemaProxy:
        return XMLSchemaProxy(self.schema, self)

    @property
    def xpath_node(self) -> SchemaElementNode:
        schema_node = self.schema.xpath_node
        node = schema_node.get_element_node(self)
        if isinstance(node, SchemaElementNode):
            return node

        return build_schema_node_tree(
            root=self,
            elements=schema_node.elements,
            global_elements=schema_node.children,
        )

    def build(self) -> None:
        if self._build:
            return None
        self._build = True
        self._parse()

    @property
    def built(self) -> bool:
        return hasattr(self, 'type') and \
            (self.type.parent is None or self.type.built) and \
            all(c.built for c in self.identities)

    @property
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif self.type.validation_attempted == 'partial':
            return 'partial'
        elif any(c.validation_attempted == 'partial' for c in self.identities):
            return 'partial'
        else:
            return 'none'

    @property
    def scope(self) -> str:
        """The scope of the element declaration that can be 'global' or 'local'."""
        return 'global' if self.parent is None else 'local'

    @property
    def value_constraint(self) -> Optional[str]:
        """The fixed or the default value if either is defined, `None` otherwise."""
        return self.fixed if self.fixed is not None else self.default

    @property
    def final(self) -> str:
        if self.ref is not None:
            return self.ref.final
        elif self._final is not None:
            return self._final
        return self.schema.final_default

    @property
    def block(self) -> str:
        if self.ref is not None:
            return self.ref.block
        elif self._block is not None:
            return self._block
        return self.schema.block_default

    def get_binding(self, *bases: Type[Any], replace_existing: bool = False, **attrs: Any) \
            -> DataBindingType:
        """
        Gets data object binding for XSD element, creating a new one if it doesn't exist.

        :param bases: base classes to use for creating the binding class.
        :param replace_existing: provide `True` to replace an existing binding class.
        :param attrs: attribute and method definitions for the binding class body.
        """
        if self.binding is None or replace_existing:
            if not bases:
                bases = (dataobjects.DataElement,)
            attrs['xsd_element'] = self
            class_name = '{}Binding'.format(self.local_name.title().replace('_', ''))
            self.binding = cast(DataBindingType,
                                dataobjects.DataBindingMeta(class_name, bases, attrs))
        return self.binding

    def get_type(self, elem: Union[ElementType, ElementData],
                 inherited: Optional[Dict[str, Any]] = None) -> BaseXsdType:
        return self._head_type or self.type

    def get_attributes(self, xsd_type: BaseXsdType) -> 'XsdAttributeGroup':
        if not isinstance(xsd_type, XsdSimpleType):
            return xsd_type.attributes
        elif xsd_type is self.type:
            return self.attributes
        else:
            return self.schema.create_empty_attribute_group(self)

    def get_path(self, ancestor: Optional[XsdComponent] = None,
                 reverse: bool = False) -> Optional[str]:
        """
        Returns the XPath expression of the element. The path is relative to the schema instance
        in which the element is contained or is relative to a specific ancestor passed as argument.
        In the latter case returns `None` if the argument is not an ancestor.

        :param ancestor: optional XSD component of the same schema, that maybe \
        an ancestor of the element.
        :param reverse: if set to `True` returns the reverse path, from the element to ancestor.
        """
        path: List[str] = []
        xsd_component: Optional[XsdComponent] = self
        while xsd_component is not None:
            if xsd_component is ancestor:
                return '/'.join(reversed(path)) or '.'
            elif isinstance(xsd_component, XsdElement):
                path.append('..' if reverse else xsd_component.name)
            xsd_component = xsd_component.parent
        else:
            if ancestor is None:
                return '/'.join(reversed(path)) or '.'
            return None

    def iter_components(self, xsd_classes: Optional[ComponentClassType] = None) \
            -> Iterator[XsdComponent]:

        if xsd_classes is None:
            yield self
            yield from self.identities
        else:
            if isinstance(self, xsd_classes):
                yield self
            if issubclass(XsdIdentity, xsd_classes):
                yield from self.identities

        if self.ref is None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def iter_substitutes(self) -> Iterator['XsdElement']:
        if self.parent is None or self.ref is not None:
            for xsd_element in self.maps.substitution_groups.get(self.name, ()):
                if not xsd_element.abstract:
                    yield xsd_element
                for e in xsd_element.iter_substitutes():
                    if not e.abstract:
                        yield e

    def data_value(self, elem: ElementType) -> Optional[AtomicValueType]:
        """Returns the decoded data value of the provided element as XPath fn:data()."""
        text = elem.text
        if text is None:
            text = self.fixed if self.fixed is not None else self.default
            if text is None:
                if self.type.is_valid(''):
                    self.type.text_decode('')
                return None
        return self.type.text_decode(text)

    def check_dynamic_context(self, elem: ElementType,
                              validation: str,
                              options: Dict[str, Any]) -> Iterator[XMLSchemaValidationError]:
        try:
            source: XMLResource = options['source']
        except KeyError:
            return

        for ns, url in etree_iter_location_hints(elem):
            base_url = source.base_url
            url = normalize_url(url, base_url)
            if any(url == schema.url for schema in self.maps.iter_schemas()):
                continue

            if ns in etree_iter_namespaces(source.root, elem):
                reason = _("schemaLocation declaration after namespace start")
                yield self.validation_error(validation, reason, elem, **options)

            try:
                if ns in self.maps.namespaces:
                    schema = self.maps.namespaces[ns][0]
                    schema.include_schema(url)
                    self.schema.clear()
                    self.schema.build()
                else:
                    self.schema.import_schema(ns, url, base_url, build=True)

            except (XMLSchemaValidationError, ParseError) as err:
                yield self.validation_error(validation, err, elem, **options)
            except XMLSchemaParseError as err:
                yield self.validation_error(validation, err.message, elem, **options)
            except OSError:
                continue

    def iter_decode(self, obj: ElementType, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[Any]:
        """
        Creates an iterator for decoding an Element instance.

        :param obj: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        error: Union[XMLSchemaValueError, XMLSchemaValidationError]
        result: Any

        if self.abstract:
            if self.name == obj.tag:
                reason = _("can't use an abstract element in an instance")
                yield self.validation_error(validation, reason, obj, **kwargs)
            elif self.name not in self.maps.substitution_groups:
                reason = _("can't use an abstract XSD element for validation "
                           "unless it's the head of a substitution group")
                yield self.validation_error(validation, reason, obj, **kwargs)
            else:
                for xsd_element in self.iter_substitutes():
                    if obj.tag == xsd_element.name:
                        yield from xsd_element.iter_decode(obj, validation, **kwargs)
                        return
                else:
                    reason = _("can't use an abstract XSD element for validation")
                    yield self.validation_error(validation, reason, obj, **kwargs)

        # Control validation on element and its descendants or stop validation
        if 'validation_hook' in kwargs:
            value = kwargs['validation_hook'](obj, self)
            if value:
                if isinstance(value, str) and value in XSD_VALIDATION_MODES:
                    validation = value
                else:
                    return

        kwargs['elem'] = obj
        try:
            level = kwargs['level']
        except KeyError:
            level = kwargs['level'] = 0

        try:
            identities = kwargs['identities']
        except KeyError:
            identities = kwargs['identities'] = {}

        for identity in self.identities:
            if identity in identities:
                identities[identity].reset(obj)
            else:
                identities[identity] = identity.get_counter(obj)

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = self._get_converter(obj, kwargs)
        else:
            if not isinstance(converter, NamespaceMapper):
                converter = self._get_converter(obj, kwargs)

        if not level:
            # Need to set base context with the right object (the resource can be lazy)
            converter.set_context(obj, level)
        elif kwargs.get('use_location_hints'):
            # Use location hints for dynamic schema load
            yield from self.check_dynamic_context(obj, validation, options=kwargs)

        inherited = kwargs.get('inherited')
        value = content = attributes = None
        nilled = False

        # Get the instance effective type
        xsd_type = self.get_type(obj, inherited)
        if XSI_TYPE in obj.attrib and self.schema.meta_schema is not None:
            # Meta-schema elements ignore xsi:type (issue #350)
            type_name = obj.attrib[XSI_TYPE].strip()
            namespaces = converter.namespaces
            try:
                xsd_type = self.maps.get_instance_type(type_name, xsd_type, namespaces)
            except (KeyError, TypeError) as err:
                yield self.validation_error(validation, err, obj, **kwargs)
            else:
                if self.identities:
                    xpath_element = XPathElement(self.name, xsd_type)
                    for identity in self.identities:
                        if not identity.built or identity.selector is None:
                            continue  # Skip unbuilt or incomplete identities
                        identity.elements.update(
                            identity.get_selected_elements(xpath_element)
                        )

            if xsd_type.is_blocked(self):
                reason = _("usage of %r is blocked") % xsd_type
                yield self.validation_error(validation, reason, obj, **kwargs)

        if xsd_type.abstract:
            reason = _("%r is abstract") % xsd_type
            yield self.validation_error(validation, reason, obj, **kwargs)
        if xsd_type.is_complex() and self.xsd_version == '1.1':
            kwargs['id_list'] = []  # Track XSD 1.1 multiple xs:ID attributes/children

        content_decoder = xsd_type if isinstance(xsd_type, XsdSimpleType) else xsd_type.content

        # Decode attributes
        attribute_group = self.get_attributes(xsd_type)
        for result in attribute_group.iter_decode(obj.attrib, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield self.validation_error(validation, result, obj, **kwargs)
            else:
                attributes = result

        if self.inheritable and any(name in self.inheritable for name in obj.attrib):
            if inherited:
                inherited = inherited.copy()
                inherited.update((k, v) for k, v in obj.attrib.items() if k in self.inheritable)
            else:
                inherited = {k: v for k, v in obj.attrib.items() if k in self.inheritable}
            kwargs['inherited'] = inherited

        # Checks the xsi:nil attribute of the instance
        if XSI_NIL in obj.attrib:
            xsi_nil = obj.attrib[XSI_NIL].strip()
            if not self.nillable:
                reason = _("element is not nillable")
                yield self.validation_error(validation, reason, obj, **kwargs)
            elif xsi_nil not in ('0', '1', 'false', 'true'):
                reason = _("xsi:nil attribute must have a boolean value")
                yield self.validation_error(validation, reason, obj, **kwargs)
            elif xsi_nil in ('0', 'false'):
                pass
            elif self.fixed is not None:
                reason = _("xsi:nil='true' but the element has a fixed value")
                yield self.validation_error(validation, reason, obj, **kwargs)
            elif obj.text is not None or len(obj):
                reason = _("xsi:nil='true' but the element is not empty")
                yield self.validation_error(validation, reason, obj, **kwargs)
            else:
                nilled = True

        if xsd_type.is_empty() and obj.text and xsd_type.normalize(obj.text):
            reason = _("character data is not allowed because content is empty")
            yield self.validation_error(validation, reason, obj, **kwargs)

        if nilled:
            pass
        elif not isinstance(content_decoder, XsdSimpleType):
            if not isinstance(xsd_type, XsdSimpleType):
                for assertion in xsd_type.assertions:
                    for error in assertion(obj, **kwargs):
                        yield self.validation_error(validation, error, **kwargs)

            for result in content_decoder.iter_decode(obj, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self.validation_error(validation, result, obj, **kwargs)
                else:
                    content = result

            if content and len(content) == 1 and content[0][0] == 1:
                value, content = content[0][1], None

            if self.fixed is not None and \
                    (len(obj) > 0 or value is not None and self.fixed != value):
                reason = _("must have the fixed value %r") % self.fixed
                yield self.validation_error(validation, reason, obj, **kwargs)

        else:
            if len(obj):
                reason = _("a simple content element can't have child elements")
                yield self.validation_error(validation, reason, obj, **kwargs)

            text = obj.text
            if self.fixed is not None:
                if not text:
                    text = self.fixed
                elif text == self.fixed:
                    pass
                elif not strictly_equal(xsd_type.text_decode(text),
                                        xsd_type.text_decode(self.fixed)):
                    reason = _("must have the fixed value %r") % self.fixed
                    yield self.validation_error(validation, reason, obj, **kwargs)

            elif not text and self.default is not None and kwargs.get('use_defaults', True):
                text = self.default

            if not isinstance(xsd_type, XsdSimpleType):
                for assertion in xsd_type.assertions:
                    for error in assertion(obj, value=text, **kwargs):
                        yield self.validation_error(validation, error, **kwargs)

                if text and content_decoder.is_list():
                    value = text.split()
                else:
                    value = text

            elif xsd_type.is_notation():
                if xsd_type.name == XSD_NOTATION_TYPE:
                    msg = _("cannot validate against xs:NOTATION directly, "
                            "only against a subtype with an enumeration facet")
                    yield self.validation_error(validation, msg, text, **kwargs)
                elif not xsd_type.enumeration:
                    msg = _("missing enumeration facet in xs:NOTATION subtype")
                    yield self.validation_error(validation, msg, text, **kwargs)

            for result in content_decoder.iter_decode(text or '', validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self.validation_error(validation, result, obj, **kwargs)
                elif result is None and 'filler' in kwargs:
                    value = kwargs['filler'](self)
                elif text or kwargs.get('keep_empty'):
                    value = result

            if 'value_hook' in kwargs:
                value = kwargs['value_hook'](value, xsd_type)
            elif isinstance(value, (int, float, list)) or value is None:
                pass
            elif isinstance(value, str):
                if value.startswith('{') and xsd_type.is_qname():
                    value = text
            elif isinstance(value, Decimal):
                try:
                    value = kwargs['decimal_type'](value)
                except (KeyError, TypeError):
                    pass
            elif isinstance(value, (AbstractDateTime, Duration)):
                if not kwargs.get('datetime_types'):
                    value = str(value) if text is None else text.strip()
            elif isinstance(value, AbstractBinary):
                if not kwargs.get('binary_types'):
                    value = str(value)

        xmlns = converter.set_context(obj, level)  # Purge existing sub-contexts

        if isinstance(converter, XMLSchemaConverter):
            element_data = ElementData(obj.tag, value, content, attributes, xmlns)
            if 'element_hook' in kwargs:
                element_data = kwargs['element_hook'](element_data, self, xsd_type)

            try:
                yield converter.element_decode(element_data, self, xsd_type, level)
            except (ValueError, TypeError) as err:
                yield self.validation_error(validation, err, obj, **kwargs)
        elif not level:
            yield ElementData(obj.tag, value, None, attributes, None)

        if content is not None:
            del content

        if self.selected_by:
            yield from self.collect_key_fields(obj, xsd_type, validation, nilled, **kwargs)

        # Apply non XSD optional validations
        if 'extra_validator' in kwargs:
            try:
                result = kwargs['extra_validator'](obj, self)
            except XMLSchemaValidationError as err:
                yield self.validation_error(validation, err, obj, **kwargs)
            else:
                if isinstance(result, GeneratorType):
                    for error in result:
                        yield self.validation_error(validation, error, obj, **kwargs)

        # Disable collect for out of scope identities and check key references
        if 'max_depth' not in kwargs:
            for identity in self.identities:
                counter = identities[identity]
                counter.enabled = False
                if isinstance(identity, XsdKeyref):
                    assert isinstance(counter, KeyrefCounter)
                    for error in counter.iter_errors(identities):
                        yield self.validation_error(validation, error, obj, **kwargs)
        elif level:
            for identity in self.identities:
                identities[identity].enabled = False

    def collect_key_fields(self, obj: ElementType, xsd_type: BaseXsdType,
                           validation: str = 'lax', nilled: bool = False,
                           **kwargs: Any) -> Iterator[XMLSchemaValidationError]:
        element_node: Union[ElementNode, LazyElementNode]

        try:
            identities = kwargs['identities']
            resource = cast(XMLResource, kwargs['source'])
        except KeyError:
            # skip identities collect if identity map or XML source are missing
            return

        try:
            namespaces = kwargs['namespaces']
        except KeyError:
            namespaces = None

        element_node = resource.get_xpath_node(obj, namespaces)

        xsd_element = self if self.ref is None else self.ref
        if xsd_element.type is not xsd_type:
            xsd_element = _copy(xsd_element)
            xsd_element.type = xsd_type

        # Collect field values for identities that refer to this XSD element.
        for identity in self.selected_by:
            try:
                counter = identities[identity]
            except KeyError:
                continue
            else:
                if not counter.enabled or not identity.elements:
                    continue

            if counter.elements is None:
                # Apply selector on Element ancestor for obtain the selected elements
                root_node = resource.get_xpath_node(counter.elem)
                context = XPathContext(root_node)
                assert identity.selector is not None
                counter.elements = set(identity.selector.token.select_results(context))

            if obj not in counter.elements:
                continue

            if xsd_element in identity.elements:
                selectors = identity.elements[xsd_element]
            else:
                selectors = [FieldValueSelector(f, xsd_element) for f in identity.fields]

            try:
                fields = tuple(s.get_value(element_node, namespaces) for s in selectors)
            except (XMLSchemaValueError, XMLSchemaTypeError) as err:
                yield self.validation_error(validation, err, obj, **kwargs)
            else:
                if any(x is not None for x in fields) or nilled:
                    try:
                        counter.increase(fields)
                    except ValueError as err:
                        yield self.validation_error(validation, err, obj, **kwargs)

    def to_objects(self, obj: ElementType, with_bindings: bool = False, **kwargs: Any) \
            -> DecodeType['dataobjects.DataElement']:
        """
        Decodes XML data to Python data objects.

        :param obj: the XML data source.
        :param with_bindings: if `True` is provided the decoding is done using \
        :class:`DataBindingConverter` that used XML data binding classes. For \
        default the objects are instances of :class:`DataElement` and uses the \
        :class:`DataElementConverter`.
        :param kwargs: other optional keyword arguments for the method \
        :func:`iter_decode`, except the argument *converter*.
        """
        if with_bindings:
            return self.decode(obj, converter=dataobjects.DataBindingConverter, **kwargs)
        return self.decode(obj, converter=dataobjects.DataElementConverter, **kwargs)

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[ElementType]:
        """
        Creates an iterator for encoding data to an Element.

        :param obj: the data that has to be encoded.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields an Element, eventually preceded by a sequence of \
        validation or encoding errors.
        """
        errors: List[Union[str, Exception]] = []
        result: Any

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = self._get_converter(obj, kwargs)
        else:
            if not isinstance(converter, XMLSchemaConverter):
                converter = self._get_converter(obj, kwargs)

        try:
            level = kwargs['level']
        except KeyError:
            level = kwargs['level'] = 0

        try:
            element_data = converter.element_encode(obj, self, level)
        except (ValueError, TypeError) as err:
            yield self.validation_error(validation, err, obj, **kwargs)
            return

        if self.abstract:
            if self.name == element_data.tag and converter.losslessly:
                reason = _("can't use an abstract element in an instance")
                yield self.validation_error(validation, reason, obj, **kwargs)
            elif self.name not in self.maps.substitution_groups:
                reason = _("can't use an abstract XSD element for validation "
                           "unless it's the head of a substitution group")
                yield self.validation_error(validation, reason, obj, **kwargs)
            else:
                for xsd_element in self.iter_substitutes():
                    if element_data.tag == xsd_element.name:
                        yield from xsd_element.iter_encode(obj, validation, **kwargs)
                        return
                else:
                    # In some cases the original tag could be missed, so try each
                    # substitute before generate an error.
                    for xsd_element in self.iter_substitutes():
                        for result in xsd_element.iter_encode(obj, validation, **kwargs):
                            if not isinstance(result, XMLSchemaValidationError):
                                yield result
                                return
                    else:
                        reason = _("can't use an abstract XSD element for validation")
                        yield self.validation_error(validation, reason, obj, **kwargs)

        if 'max_depth' in kwargs and kwargs['max_depth'] == 0 and not level:
            for e in errors:
                yield self.validation_error(validation, e, **kwargs)
            return

        text = None
        children = element_data.content
        attributes = ()

        xsd_type = self.get_type(element_data)
        if XSI_TYPE in element_data.attributes and self.schema.meta_schema is not None:
            type_name = element_data.attributes[XSI_TYPE].strip()
            try:
                xsd_type = self.maps.get_instance_type(type_name, xsd_type, converter)
            except (KeyError, TypeError) as err:
                errors.append(err)
            else:
                default_namespace = converter.get('')
                if default_namespace and not isinstance(xsd_type, XsdSimpleType):
                    # Adjust attributes mapped into default namespace

                    ns_part = f'{{{default_namespace}}}'
                    for k in list(element_data.attributes):
                        if not k.startswith(ns_part):
                            continue
                        elif k in xsd_type.attributes:
                            continue

                        local_name = k[len(ns_part):]
                        if local_name in xsd_type.attributes:
                            element_data.attributes[local_name] = element_data.attributes[k]
                            del element_data.attributes[k]

        attribute_group = self.get_attributes(xsd_type)
        for result in attribute_group.iter_encode(element_data.attributes, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                errors.append(result)
            else:
                attributes = result

        if XSI_NIL in element_data.attributes:
            xsi_nil = element_data.attributes[XSI_NIL].strip()
            if not self.nillable:
                errors.append("element is not nillable.")
            elif xsi_nil not in ('0', '1', 'true', 'false'):
                errors.append("xsi:nil attribute must has a boolean value.")
            elif xsi_nil in ('0', 'false'):
                pass
            elif self.fixed is not None:
                errors.append("xsi:nil='true' but the element has a fixed value.")
            elif element_data.text not in (None, '') or element_data.content:
                errors.append("xsi:nil='true' but the element is not empty.")
            else:
                elem = converter.etree_element(element_data.tag, attrib=attributes, level=level)
                for e in errors:
                    yield self.validation_error(validation, e, elem, **kwargs)
                yield elem
                return

        if isinstance(xsd_type, XsdSimpleType):
            if element_data.content:
                errors.append("a simpleType element can't has child elements.")

            if element_data.text is not None:
                for result in xsd_type.iter_encode(element_data.text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        text = result

            elif self.fixed is not None:
                text = self.fixed
            elif self.default is not None and kwargs.get('use_defaults', True):
                text = self.default

        elif xsd_type.has_simple_content():
            if element_data.text is not None:
                for result in xsd_type.content.iter_encode(element_data.text,
                                                           validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        text = result

            elif self.fixed is not None:
                text = self.fixed
            elif self.default is not None and kwargs.get('use_defaults', True):
                text = self.default

        else:
            for result in xsd_type.content.iter_encode(element_data, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    errors.append(result)
                elif result:
                    text, children = result

        elem = converter.etree_element(element_data.tag, text, children, attributes, level)

        if errors:
            for e in errors:
                yield self.validation_error(validation, e, elem, **kwargs)
        yield elem
        del element_data

    def is_matching(self, name: Optional[str], default_namespace: Optional[str] = None,
                    group: Optional['XsdGroup'] = None, **kwargs: Any) -> bool:
        if not name:
            return False
        elif default_namespace and name[0] != '{':
            name = f'{{{default_namespace}}}{name}'

            # Workaround for backward compatibility of XPath selectors on schemas.
            if not self.qualified and default_namespace == self.target_namespace:
                return (name == self.qualified_name or
                        any(name == e.qualified_name for e in self.iter_substitutes()))

        return name == self.name or any(name == e.name for e in self.iter_substitutes())

    def match(self, name: Optional[str], default_namespace: Optional[str] = None,
              **kwargs: Any) -> Optional['XsdElement']:
        if not name:
            return None
        elif default_namespace and name[0] != '{':
            name = f'{{{default_namespace}}}{name}'

        if name == self.name:
            return self
        else:
            for xsd_element in self.iter_substitutes():
                if name == xsd_element.name:
                    return xsd_element
        return None

    def match_child(self, name: str) -> Optional['XsdElement']:
        xsd_group = self.type.model_group
        if xsd_group is None:
            # fallback to xs:anyType encoder for matching extra content
            xsd_group = self.any_type.model_group
            assert xsd_group is not None

        for xsd_child in xsd_group.iter_elements():
            matched_element = xsd_child.match(name, resolve=True)
            if isinstance(matched_element, XsdElement):
                return matched_element
        else:
            if name in self.maps.elements and xsd_group.open_content_mode != 'none':
                return self.maps.lookup_element(name)
            return None

    def is_restriction(self, other: ModelParticleType, check_occurs: bool = True) -> bool:
        e: ModelParticleType

        if isinstance(other, XsdAnyElement):
            if self.min_occurs == self.max_occurs == 0:
                return True
            if check_occurs and not self.has_occurs_restriction(other):
                return False
            return other.is_matching(self.name, self.default_namespace)
        elif isinstance(other, XsdElement):
            if self.name != other.name:
                if other.name == self.substitution_group and \
                        other.min_occurs != other.max_occurs and \
                        self.max_occurs != 0 and not other.abstract \
                        and self.xsd_version == '1.0':
                    # A UPA violation case. Base is the head element, it's not
                    # abstract and has non-deterministic occurs: this is less
                    # restrictive than W3C test group (elemZ026), marked as
                    # invalid despite it's based on an abstract declaration.
                    # See also test case invalid_restrictions1.xsd.
                    return False

                for e in other.iter_substitutes():
                    if e.name == self.name:
                        break
                else:
                    return False

            if check_occurs and not self.has_occurs_restriction(other):
                return False
            elif self.max_occurs == 0 and check_occurs:
                return True  # type is not effective if the element can't have occurrences
            elif not self.is_consistent(other) and self.type.elem is not other.type.elem and \
                    not self.type.is_derived(other.type, 'restriction') and not other.type.abstract:
                return False
            elif other.fixed is not None and \
                    (self.fixed is None or self.type.normalize(
                        self.fixed) != other.type.normalize(other.fixed)):
                return False
            elif other.nillable is False and self.nillable:
                return False
            elif any(value not in self.block for value in other.block.split()):
                return False
            elif not all(k in other.identities for k in self.identities):
                return False
            else:
                return True
        elif other.model == 'choice':
            if other.is_empty() and self.max_occurs != 0:
                return False

            check_group_items_occurs = self.xsd_version == '1.0'
            total_occurs = OccursCalculator()
            for e in other.iter_model():
                if not isinstance(e, (XsdElement, XsdAnyElement)):
                    return False
                elif not self.is_restriction(e, check_group_items_occurs):
                    continue
                total_occurs += e
                total_occurs *= other
                if self.has_occurs_restriction(total_occurs):
                    return True
                total_occurs.reset()
            return False
        else:
            match_restriction = False
            for e in other.iter_model():
                if match_restriction:
                    if not e.is_emptiable():
                        return False
                elif self.is_restriction(e):
                    match_restriction = True
                elif not e.is_emptiable():
                    return False
            return True

    def is_overlap(self, other: SchemaElementType) -> bool:
        if isinstance(other, XsdElement):
            if self.name == other.name:
                return True
            elif other.substitution_group == self.name or other.name == self.substitution_group:
                return True
        elif isinstance(other, XsdAnyElement):
            if other.is_matching(self.name, self.default_namespace):
                return True
            for e in self.maps.substitution_groups.get(self.name, ()):
                if other.is_matching(e.name, self.default_namespace):
                    return True
        return False

    def is_consistent(self, other: SchemaElementType, strict: bool = True) -> bool:
        """
        Element Declarations Consistent check between two element particles.

        Ref: https://www.w3.org/TR/xmlschema-1/#cos-element-consistent

        :returns: `True` if there is no inconsistency between the particles, `False` otherwise,
        """
        return self.name != other.name or self.type is other.type

    def is_single(self) -> bool:
        if self.parent is None:
            return True
        elif self.max_occurs != 1:
            return False
        elif self.parent.max_occurs == 1:
            return True
        else:
            return self.parent.model != 'choice' and len(self.parent) > 1


class Xsd11Element(XsdElement):
    """
    Class for XSD 1.1 *element* declarations.

    ..  <element
          abstract = boolean : false
          block = (#all | List of (extension | restriction | substitution))
          default = string
          final = (#all | List of (extension | restriction))
          fixed = string
          form = (qualified | unqualified)
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          name = NCName
          nillable = boolean : false
          ref = QName
          substitutionGroup = List of QName
          targetNamespace = anyURI
          type = QName
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, ((simpleType | complexType)?, alternative*,
          (unique | key | keyref)*))
        </element>
    """
    _target_namespace: Optional[str] = None

    def _parse(self) -> None:
        if not self._build:
            return

        self._parse_particle(self.elem)
        self._parse_attributes()

        if self.ref is None:
            self._parse_type()
            self._parse_alternatives()
            self._parse_constraints()

            if self.parent is None and 'substitutionGroup' in self.elem.attrib:
                for substitution_group in self.elem.attrib['substitutionGroup'].split():
                    self._parse_substitution_group(substitution_group)

        self._parse_target_namespace()

        if any(v.inheritable for v in self.attributes.values()):
            self.inheritable = {}
            for k, v in self.attributes.items():
                if k is not None and isinstance(v, XsdAttribute):
                    if v.inheritable:
                        self.inheritable[k] = v

    def _parse_alternatives(self) -> None:
        alternatives = []
        has_test = True
        for child in self.elem:
            if child.tag == XSD_ALTERNATIVE:
                alternatives.append(XsdAlternative(child, self.schema, self))
                if not has_test:
                    msg = _("test attribute missing in non-final alternative")
                    self.parse_error(msg)
                has_test = 'test' in child.attrib

        if alternatives:
            self.alternatives = alternatives

    @property
    def built(self) -> bool:
        return (self.type.parent is None or self.type.built) and \
            all(c.built for c in self.identities) and \
            all(a.built for a in self.alternatives)

    @property
    def target_namespace(self) -> str:
        if self._target_namespace is not None:
            return self._target_namespace
        elif self.ref is not None:
            return self.ref.target_namespace
        else:
            return self.schema.target_namespace

    def iter_components(self, xsd_classes: ComponentClassType = None) -> Iterator[XsdComponent]:
        if xsd_classes is None:
            yield self
            yield from self.identities
        else:
            if isinstance(self, xsd_classes):
                yield self

            for obj in self.identities:
                if isinstance(obj, xsd_classes):
                    yield obj

        for alt in self.alternatives:
            yield from alt.iter_components(xsd_classes)

        if self.ref is None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def iter_substitutes(self) -> Iterator[XsdElement]:
        if self.parent is None or self.ref is not None:
            for xsd_element in self.maps.substitution_groups.get(self.name, ()):
                yield xsd_element
                yield from xsd_element.iter_substitutes()

    def get_type(self, elem: Union[ElementType, ElementData],
                 inherited: Optional[Dict[str, Any]] = None) -> BaseXsdType:
        if not self.alternatives:
            return self._head_type or self.type

        if isinstance(elem, ElementData):
            if elem.attributes:
                attrib: Dict[str, str] = {}
                for k, v in elem.attributes.items():
                    value = raw_xml_encode(v)
                    if value is not None:
                        attrib[k] = value

                elem = Element(elem.tag, attrib=attrib)
            else:
                elem = Element(elem.tag)

        if inherited:
            dummy = Element('_dummy_element', attrib=inherited)
            dummy.attrib.update(elem.attrib)

            for alt in self.alternatives:
                if alt.type is not None:
                    if alt.token is None or alt.test(elem) or alt.test(dummy):
                        return alt.type
        else:
            for alt in self.alternatives:
                if alt.type is not None:
                    if alt.token is None or alt.test(elem):
                        return alt.type

        return self._head_type or self.type

    def is_overlap(self, other: SchemaElementType) -> bool:
        if isinstance(other, XsdElement):
            if self.name == other.name:
                return True
            elif any(self.name == x.name for x in other.iter_substitutes()):
                return True

            for e in self.iter_substitutes():
                if other.name == e.name or any(x is e for x in other.iter_substitutes()):
                    return True

        elif isinstance(other, XsdAnyElement):
            if other.is_matching(self.name, self.default_namespace):
                return True
            for e in self.maps.substitution_groups.get(self.name, ()):
                if other.is_matching(e.name, self.default_namespace):
                    return True
        return False

    def is_consistent(self, other: SchemaElementType, strict: bool = True) -> bool:
        if isinstance(other, XsdAnyElement):
            if other.process_contents == 'skip':
                return True
            xsd_element = other.match(self.name, self.default_namespace, resolve=True)
            return xsd_element is None or self.is_consistent(xsd_element, strict=False)

        e1: XsdElement = self
        e2 = other
        if self.name != other.name:
            for e1 in self.iter_substitutes():
                if e1.name == other.name:
                    break
            else:
                for e2 in other.iter_substitutes():
                    if e2.name == self.name:
                        break
                else:
                    return True

        if len(e1.alternatives) != len(e2.alternatives):
            return False
        elif e1.type is not e2.type and strict:
            return False
        elif e1.type is not e2.type or \
                not all(any(a == x for x in e2.alternatives) for a in e1.alternatives) or \
                not all(any(a == x for x in e1.alternatives) for a in e2.alternatives):
            msg = _("Maybe a not equivalent type table between elements {0!r} and {1!r}")
            warnings.warn(msg.format(e1, e2), XMLSchemaTypeTableWarning, stacklevel=3)
        return True

    def check_dynamic_context(self, elem: ElementType,
                              validation: str,
                              options: Dict[str, Any]) -> Iterator[XMLSchemaValidationError]:
        try:
            source = options['source']
        except KeyError:
            return

        for ns, url in etree_iter_location_hints(elem):
            base_url = source.base_url
            url = normalize_url(url, base_url)
            if any(url == schema.url for schema in self.maps.iter_schemas()):
                continue

            try:
                if ns in self.maps.namespaces:
                    schema = self.maps.namespaces[ns][0]
                    schema.include_schema(url)
                    schema.clear()
                    schema.build()
                else:
                    schema = self.schema
                    schema.import_schema(ns, url, base_url, build=True)

                def stop_validation(e: ElementType, _xsd_element: XsdElement) -> bool:
                    if e is elem:
                        raise XMLSchemaStopValidation()
                    return False

                errors = list(schema.iter_errors(source, validation_hook=stop_validation))
                if len(options['errors']) != len(errors) or \
                        any(e1.elem is not e2.elem for e1, e2 in zip(options['errors'], errors)):
                    reason = _(f"adding schema at {url} change the "
                               f"assessment outcome of previous items")
                    yield self.validation_error(validation, reason, elem, **options)

            except (XMLSchemaValidationError, ParseError) as err:
                yield self.validation_error(validation, err, elem, **options)
            except XMLSchemaParseError as err:
                yield self.validation_error(validation, err.message, elem, **options)
            except OSError:
                continue


class XsdAlternative(XsdComponent):
    """
    XSD 1.1 type *alternative* definitions.

    ..  <alternative
          id = ID
          test = an XPath expression
          type = QName
          xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, (simpleType | complexType)?)
        </alternative>
    """
    parent: XsdElement
    type: BaseXsdType
    path: Optional[str] = None
    token: Optional[XPathToken] = None
    _ADMITTED_TAGS = {XSD_ALTERNATIVE}

    def __init__(self, elem: ElementType, schema: SchemaType, parent: XsdElement) -> None:
        super().__init__(elem, schema, parent)

    def __repr__(self) -> str:
        return '%s(type=%r, test=%r)' % (
            self.__class__.__name__, self.elem.get('type'), self.elem.get('test')
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, XsdAlternative) and \
            self.path == other.path and self.type is other.type and \
            self.xpath_default_namespace == other.xpath_default_namespace

    def __ne__(self, other: object) -> bool:
        return not isinstance(other, XsdAlternative) or \
            self.path != other.path or self.type is not other.type or \
            self.xpath_default_namespace != other.xpath_default_namespace

    def _parse(self) -> None:
        attrib = self.elem.attrib

        if 'xpathDefaultNamespace' in attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace
        parser = XPath2Parser(
            namespaces=self.namespaces,
            strict=False,
            default_namespace=self.xpath_default_namespace
        )

        try:
            self.path = attrib['test']
        except KeyError:
            pass  # an absent test is not an error, it should be the default type
        else:
            try:
                self.token = parser.parse(self.path)
            except ElementPathError as err:
                self.parse_error(err)
                self.token = parser.parse('false()')
                self.path = 'false()'

        try:
            type_qname = self.schema.resolve_qname(attrib['type'])
        except (KeyError, ValueError, RuntimeError) as err:
            if 'type' in attrib:
                self.parse_error(err)
                self.type = self.any_type
            else:
                child = self._parse_child_component(self.elem, strict=False)
                if child is None or child.tag not in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    self.parse_error(_("missing 'type' attribute"))
                    self.type = self.any_type
                elif child.tag == XSD_COMPLEX_TYPE:
                    self.type = self.schema.xsd_complex_type_class(child, self.schema, self)
                else:
                    self.type = self.schema.simple_type_factory(child, self.schema, self)

                if not self.type.is_derived(self.parent.type):
                    msg = _("declared type is not derived from {!r}")
                    self.parse_error(msg.format(self.parent.type))
        else:
            try:
                self.type = self.maps.lookup_type(type_qname)
            except KeyError:
                self.parse_error(_("unknown type {!r}").format(attrib['type']))
                self.type = self.any_type
            else:
                if self.type.name != XSD_ERROR and not self.type.is_derived(self.parent.type):
                    msg = _("type {0!r} is not derived from {1!r}")
                    self.parse_error(msg.format(attrib['type'], self.parent.type))

                child = self._parse_child_component(self.elem, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    msg = _("the attribute 'type' and the xs:%s local "
                            "declaration are mutually exclusive")
                    self.parse_error(msg % child.tag.split('}')[-1])

    @property
    def built(self) -> bool:
        if not hasattr(self, 'type'):
            return False
        return self.type.parent is None or self.type.built

    @property
    def validation_attempted(self) -> str:
        if self.built:
            return 'full'
        elif not hasattr(self, 'type'):
            return 'none'
        else:
            return self.type.validation_attempted

    def iter_components(self, xsd_classes: ComponentClassType = None) -> Iterator[XsdComponent]:
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.type is not None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def test(self, elem: ElementType) -> bool:
        if self.token is None:
            return False

        try:
            result = list(self.token.select(context=XPathContext(elem)))
            return self.token.boolean_value(result)
        except (TypeError, ValueError):
            return False
