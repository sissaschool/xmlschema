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
This module contains classes for XML Schema wildcards.
"""
from typing import cast, Any, Callable, Dict, Iterable, Iterator, List, Optional, \
    Tuple, Union, Counter

from elementpath import SchemaElementNode, build_schema_node_tree

from ..exceptions import XMLSchemaValueError
from ..names import XSI_NAMESPACE, XSD_ANY, XSD_ANY_ATTRIBUTE, \
    XSD_OPEN_CONTENT, XSD_DEFAULT_OPEN_CONTENT, XSI_TYPE
from ..aliases import ElementType, SchemaType, SchemaElementType, SchemaAttributeType, \
    ModelGroupType, ModelParticleType, AtomicValueType, IterDecodeType, IterEncodeType, \
    DecodedValueType, EncodedValueType
from ..translation import gettext as _
from ..helpers import get_namespace, raw_xml_encode
from ..xpath import XsdSchemaProtocol, XsdElementProtocol, XMLSchemaProxy, ElementPathMixin
from .xsdbase import ValidationMixin, XsdComponent
from .particles import ParticleMixin
from . import elements


OccursCounterType = Counter[Union[ModelParticleType, Tuple[ModelParticleType]]]


class XsdWildcard(XsdComponent):
    names = ()
    namespace: Union[Tuple[str], List[str]] = ('##any',)
    not_namespace: Union[Tuple[()], List[str]] = ()
    not_qname: Union[Tuple[()], List[str]] = ()
    process_contents = 'strict'

    # For compatibility with protocol of XSD elements/attributes
    type = None
    default = None
    fixed = None

    def __repr__(self) -> str:
        if self.not_namespace:
            return '%s(not_namespace=%r, process_contents=%r)' % (
                self.__class__.__name__, self.not_namespace, self.process_contents
            )
        else:
            return '%s(namespace=%r, process_contents=%r)' % (
                self.__class__.__name__, self.namespace, self.process_contents
            )

    def _parse(self) -> None:
        # Parse namespace and processContents
        namespace = self.elem.attrib.get('namespace', '##any').strip()
        if namespace == '##any':
            pass
        elif not namespace:
            self.namespace = []  # an empty value means no namespace allowed!
        elif namespace == '##other':
            self.namespace = [namespace]
        elif namespace == '##local':
            self.namespace = ['']
        elif namespace == '##targetNamespace':
            self.namespace = [self.target_namespace]
        else:
            self.namespace = []
            for ns in namespace.split():
                if ns == '##local':
                    self.namespace.append('')
                elif ns == '##targetNamespace':
                    self.namespace.append(self.target_namespace)
                elif ns.startswith('##'):
                    msg = _("wrong value %r in 'namespace' attribute")
                    self.parse_error(msg % ns)
                else:
                    self.namespace.append(ns)

        process_contents = self.elem.attrib.get('processContents', 'strict')
        if process_contents == 'strict':
            pass
        elif process_contents not in ('lax', 'skip'):
            msg = _("wrong value %r for 'processContents' attribute")
            self.parse_error(msg % self.process_contents)
        else:
            self.process_contents = process_contents

    def _parse_not_constraints(self) -> None:
        if 'notNamespace' not in self.elem.attrib:
            pass
        elif 'namespace' in self.elem.attrib:
            msg = _("'namespace' and 'notNamespace' attributes are mutually exclusive")
            self.parse_error(msg)
        else:
            self.namespace = []
            self.not_namespace = []
            for ns in self.elem.attrib['notNamespace'].strip().split():
                if ns == '##local':
                    self.not_namespace.append('')
                elif ns == '##targetNamespace':
                    self.not_namespace.append(self.target_namespace)
                elif ns.startswith('##'):
                    msg = _("wrong value %r in 'notNamespace' attribute")
                    self.parse_error(msg % ns)
                else:
                    self.not_namespace.append(ns)

        # Parse notQName attribute
        if 'notQName' not in self.elem.attrib:
            return

        not_qname = self.elem.attrib['notQName'].strip().split()

        if isinstance(self, XsdAnyAttribute) and \
                not all(not s.startswith('##') or s == '##defined'
                        for s in not_qname) or \
                not all(not s.startswith('##') or s in {'##defined', '##definedSibling'}
                        for s in not_qname):
            self.parse_error(_("wrong value for 'notQName' attribute"))
            return

        try:
            names = [x if x.startswith('##') else self.schema.resolve_qname(x, False)
                     for x in not_qname]
        except KeyError as err:
            msg = _("unmapped QName in 'notQName' attribute: %s")
            self.parse_error(msg % str(err))
            return
        except ValueError as err:
            msg = _("wrong QName format in 'notQName' attribute: %s")
            self.parse_error(msg % str(err))
            return

        if self.not_namespace:
            if any(not x.startswith('##') for x in names) and \
                    all(get_namespace(x) in self.not_namespace
                        for x in names if not x.startswith('##')):
                msg = _("the namespace of each QName in notQName is allowed by notNamespace")
                self.parse_error(msg)
        elif any(not self.is_namespace_allowed(get_namespace(x))
                 for x in names if not x.startswith('##')):
            msg = _("names in notQName must be in namespaces that are allowed")
            self.parse_error(msg)

        self.not_qname = names

    @property
    def built(self) -> bool:
        return True

    @property
    def value_constraint(self) -> Optional[str]:
        return None

    def is_matching(self, name: Optional[str],
                    default_namespace: Optional[str] = None,
                    **kwargs: Any) -> bool:
        if name is None:
            return False
        elif not name or name[0] == '{':
            return self.is_namespace_allowed(get_namespace(name))
        elif not default_namespace:
            return self.is_namespace_allowed('')
        else:
            return self.is_namespace_allowed(default_namespace)

    def is_namespace_allowed(self, namespace: str) -> bool:
        if self.not_namespace:
            return namespace not in self.not_namespace
        elif '##any' in self.namespace or namespace == XSI_NAMESPACE:
            return True
        elif '##other' in self.namespace:
            if not namespace:
                return False
            return namespace != self.target_namespace
        else:
            return namespace in self.namespace

    def deny_namespaces(self, namespaces: List[str]) -> bool:
        if self.not_namespace:
            return all(x in self.not_namespace for x in namespaces)
        elif '##any' in self.namespace:
            return False
        elif '##other' in self.namespace:
            return all(x == self.target_namespace for x in namespaces)
        else:
            return all(x not in self.namespace for x in namespaces)

    def deny_qnames(self, names: Iterable[str]) -> bool:
        if self.not_namespace:
            return all(x in self.not_qname or get_namespace(x) in self.not_namespace
                       for x in names)
        elif '##any' in self.namespace:
            return all(x in self.not_qname for x in names)
        elif '##other' in self.namespace:
            return all(x in self.not_qname or get_namespace(x) == self.target_namespace
                       for x in names)
        else:
            return all(x in self.not_qname or get_namespace(x) not in self.namespace
                       for x in names)

    def is_restriction(self, other: Union[ModelParticleType, 'XsdAnyAttribute'],
                       check_occurs: bool = True) -> bool:
        if not isinstance(other, self.__class__):
            return False
        elif check_occurs and isinstance(self, ParticleMixin):
            if not isinstance(other, XsdAnyAttribute) and \
                    not self.has_occurs_restriction(other):
                return False
            elif self.max_occurs == 0:
                return True

        other: XsdWildcard  # type: ignore[no-redef]
        if other.process_contents == 'strict' and self.process_contents != 'strict':
            return False
        elif other.process_contents == 'lax' and self.process_contents == 'skip':
            return False

        if not self.not_qname and not other.not_qname:
            pass
        elif '##defined' in other.not_qname and '##defined' not in self.not_qname:
            return False
        elif '##definedSibling' in other.not_qname and '##definedSibling' not in self.not_qname:
            return False
        elif other.not_qname:
            if not self.deny_qnames(x for x in other.not_qname if not x.startswith('##')):
                return False
        elif any(not other.is_namespace_allowed(get_namespace(x))
                 for x in self.not_qname if not x.startswith('##')):
            return False

        if self.not_namespace:
            if other.not_namespace:
                return all(ns in self.not_namespace for ns in other.not_namespace)
            elif '##any' in other.namespace:
                return True
            elif '##other' in other.namespace:
                return '' in self.not_namespace and other.target_namespace in self.not_namespace
            else:
                return False
        elif other.not_namespace:
            if '##any' in self.namespace:
                return False
            elif '##other' in self.namespace:
                return set(other.not_namespace).issubset({'', other.target_namespace})
            else:
                return all(ns not in other.not_namespace for ns in self.namespace)

        if self.namespace == other.namespace:
            return True
        elif '##any' in other.namespace:
            return True
        elif '##any' in self.namespace or '##other' in self.namespace:
            return False
        elif '##other' in other.namespace:
            return other.target_namespace not in self.namespace and '' not in self.namespace
        else:
            return all(ns in other.namespace for ns in self.namespace)

    def union(self, other: Union['XsdAnyElement', 'XsdAnyAttribute']) -> None:
        """
        Update an XSD wildcard with the union of itself and another XSD wildcard.
        """
        if not self.not_qname:
            self.not_qname = other.not_qname[:]
        else:
            self.not_qname = [
                x for x in self.not_qname
                if x in other.not_qname or not other.is_namespace_allowed(get_namespace(x))
            ]

        if self.not_namespace:
            if other.not_namespace:
                self.not_namespace = [ns for ns in self.not_namespace if ns in other.not_namespace]
            elif '##any' in other.namespace:
                self.not_namespace = []
                self.namespace = ['##any']
                return
            elif '##other' in other.namespace:
                not_namespace = ('', other.target_namespace)
                self.not_namespace = [ns for ns in self.not_namespace if ns in not_namespace]
            else:
                self.not_namespace = [ns for ns in self.not_namespace if ns not in other.namespace]

            if not self.not_namespace:
                self.namespace = ['##any']
            return

        elif other.not_namespace:
            if '##any' in self.namespace:
                return
            elif '##other' in self.namespace:
                not_namespace = ('', self.target_namespace)
                self.not_namespace = [ns for ns in other.not_namespace if ns in not_namespace]
            else:
                self.not_namespace = [ns for ns in other.not_namespace if ns not in self.namespace]

            self.namespace = ['##any'] if not self.not_namespace else []
            return

        w1: XsdWildcard
        w2: XsdWildcard
        if '##any' in self.namespace or self.namespace == other.namespace:
            return
        elif '##any' in other.namespace:
            self.namespace = ['##any']
            return
        elif '##other' in other.namespace:
            w1, w2 = other, self
        elif '##other' in self.namespace:
            w1, w2 = self, other
        else:
            assert isinstance(self.namespace, list)
            self.namespace.extend(ns for ns in other.namespace if ns not in self.namespace)
            return

        if w1.target_namespace in w2.namespace and '' in w2.namespace:
            self.namespace = ['##any']
        elif '' not in w2.namespace and w1.target_namespace == w2.target_namespace:
            self.namespace = ['##other']
        elif self.xsd_version == '1.0':
            msg = _("not expressible wildcard namespace union: {0!r} V {1!r}:")
            raise XMLSchemaValueError(msg.format(other.namespace, self.namespace))
        else:
            self.namespace = []
            self.not_namespace = ['', w1.target_namespace] if w1.target_namespace else ['']

    def intersection(self, other: Union['XsdAnyElement', 'XsdAnyAttribute']) -> None:
        """
        Update an XSD wildcard with the intersection of itself and another XSD wildcard.
        """
        if self.not_qname:
            self.not_qname.extend(x for x in other.not_qname if x not in self.not_qname)
        else:
            self.not_qname = [x for x in other.not_qname]

        if self.not_namespace:
            if other.not_namespace:
                self.not_namespace.extend(ns for ns in other.not_namespace
                                          if ns not in self.not_namespace)
            elif '##any' in other.namespace:
                pass
            elif '##other' not in other.namespace:
                self.namespace = [ns for ns in other.namespace if ns not in self.not_namespace]
                self.not_namespace = []
            else:
                if other.target_namespace not in self.not_namespace:
                    self.not_namespace.append(other.target_namespace)
                if '' not in self.not_namespace:
                    self.not_namespace.append('')
            return

        elif other.not_namespace:
            if '##any' in self.namespace:
                self.not_namespace = [ns for ns in other.not_namespace]
                self.namespace = []
            elif '##other' not in self.namespace:
                self.namespace = [ns for ns in self.namespace if ns not in other.not_namespace]
            else:
                self.not_namespace = [ns for ns in other.not_namespace]
                if self.target_namespace not in self.not_namespace:
                    self.not_namespace.append(self.target_namespace)
                if '' not in self.not_namespace:
                    self.not_namespace.append('')
                self.namespace = []
            return

        if self.namespace == other.namespace:
            return
        elif '##any' in other.namespace:
            return
        elif '##any' in self.namespace:
            self.namespace = other.namespace[:]
        elif '##other' in self.namespace:
            self.namespace = [ns for ns in other.namespace if ns not in ('', self.target_namespace)]
        elif '##other' not in other.namespace:
            self.namespace = [ns for ns in self.namespace if ns in other.namespace]
        else:
            assert isinstance(self.namespace, list)
            if other.target_namespace in self.namespace:
                self.namespace.remove(other.target_namespace)
            if '' in self.namespace:
                self.namespace.remove('')


class XsdAnyElement(XsdWildcard, ParticleMixin,
                    ElementPathMixin[SchemaElementType],
                    ValidationMixin[ElementType, Any]):
    """
    Class for XSD 1.0 *any* wildcards.

    ..  <any
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded) : 1
          minOccurs = nonNegativeInteger : 1
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace|##local)) ) : ##any
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </any>
    """
    _ADMITTED_TAGS = {XSD_ANY}
    precedences: Dict[ModelGroupType, List[ModelParticleType]]
    copy: Callable[['XsdAnyElement'], 'XsdAnyElement']

    def __init__(self, elem: ElementType, schema: SchemaType, parent: XsdComponent) -> None:
        self.precedences = {}
        super(XsdAnyElement, self).__init__(elem, schema, parent)

    def __repr__(self) -> str:
        if self.namespace:
            return '%s(namespace=%r, process_contents=%r, occurs=%r)' % (
                self.__class__.__name__, self.namespace,
                self.process_contents, list(self.occurs)
            )
        else:
            return '%s(not_namespace=%r, process_contents=%r, occurs=%r)' % (
                self.__class__.__name__, self.not_namespace,
                self.process_contents, list(self.occurs)
            )

    @property
    def xpath_proxy(self) -> XMLSchemaProxy:
        return XMLSchemaProxy(
            schema=cast(XsdSchemaProtocol, self.schema),
            base_element=cast(XsdElementProtocol, self)
        )

    @property
    def xpath_node(self) -> SchemaElementNode:
        schema_node = self.schema.xpath_node
        node = schema_node.get_element_node(cast(XsdElementProtocol, self))
        if isinstance(node, SchemaElementNode):
            return node

        return build_schema_node_tree(
            root=cast(XsdElementProtocol, self),
            elements=schema_node.elements,
            global_elements=schema_node.children,
        )

    def _parse(self) -> None:
        super(XsdAnyElement, self)._parse()
        self._parse_particle(self.elem)

    def match(self, name: Optional[str], default_namespace: Optional[str] = None,
              resolve: bool = False, **kwargs: Any) -> Optional[SchemaElementType]:
        """
        Returns the element wildcard if name is matching the name provided
        as argument, `None` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used when it's not `None` and not empty for \
        completing local name arguments.
        :param resolve: when `True` it doesn't return the wildcard but try to \
        resolve and return the element matching the name.
        :param kwargs: additional options used by XSD 1.1 xs:any wildcards.
        """
        if not name or not self.is_matching(name, default_namespace, **kwargs):
            return None
        elif not resolve:
            return self

        try:
            if name[0] != '{' and default_namespace:
                return self.maps.lookup_element(f'{{{default_namespace}}}{name}')
            else:
                return self.maps.lookup_element(name)
        except LookupError:
            return None

    def __iter__(self) -> Iterator[Any]:
        return iter(())

    def iter(self, tag: Optional[str] = None) -> Iterator[Any]:
        return iter(())

    def iterchildren(self, tag: Optional[str] = None) -> Iterator[Any]:
        return iter(())

    @staticmethod
    def iter_substitutes() -> Iterator[Any]:
        return iter(())

    def iter_decode(self, obj: ElementType, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[Any]:

        if not self.is_matching(obj.tag):
            reason = _("element {!r} is not allowed here").format(obj)
            yield self.validation_error(validation, reason, obj, **kwargs)

        if self.process_contents == 'skip':
            if 'process_skipped' not in kwargs or not kwargs['process_skipped']:
                return

        namespace = get_namespace(obj.tag)
        if not self.maps.load_namespace(namespace):
            reason = f"unavailable namespace {namespace!r}"
        else:
            try:
                xsd_element = self.maps.lookup_element(obj.tag)
            except LookupError:
                reason = f"element {obj.tag!r} not found"
            else:
                yield from xsd_element.iter_decode(obj, validation, **kwargs)
                return

        if XSI_TYPE in obj.attrib:
            if self.process_contents == 'strict':
                xsd_element = self.maps.validator.create_element(
                    obj.tag, parent=self, form='unqualified'
                )
            else:
                xsd_element = self.maps.validator.create_element(
                    obj.tag, parent=self, nillable='true', form='unqualified'
                )

            yield from xsd_element.iter_decode(obj, validation, **kwargs)
            return

        if validation != 'skip' and self.process_contents == 'strict':
            yield self.validation_error(validation, reason, obj, **kwargs)
        yield from self.any_type.iter_decode(obj, validation, **kwargs)

    def iter_encode(self, obj: Tuple[str, ElementType], validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[Any]:
        name, value = obj
        namespace = get_namespace(name)

        if not self.is_namespace_allowed(namespace):
            reason = _("element {!r} is not allowed here").format(name)
            yield self.validation_error(validation, reason, value, **kwargs)

        if self.process_contents == 'skip':
            if 'process_skipped' not in kwargs or not kwargs['process_skipped']:
                return

        if not self.maps.load_namespace(namespace):
            reason = f"unavailable namespace {namespace!r}"
        else:
            try:
                xsd_element = self.maps.lookup_element(name)
            except LookupError:
                reason = f"element {name!r} not found"
            else:
                yield from xsd_element.iter_encode(value, validation, **kwargs)
                return

        # Check if there is a xsi:type attribute, but it has to extract
        # attributes using the converter instance.
        if self.process_contents == 'strict':
            xsd_element = self.maps.validator.create_element(
                name, parent=self, form='unqualified'
            )
        else:
            xsd_element = self.maps.validator.create_element(
                name, parent=self, nillable='true', form='unqualified'
            )

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        try:
            level = kwargs['level']
        except KeyError:
            level = 0

        try:
            element_data = converter.element_encode(value, xsd_element, level)
        except (ValueError, TypeError) as err:
            if validation != 'skip' and self.process_contents == 'strict':
                yield self.validation_error(validation, err, value, **kwargs)
        else:
            if XSI_TYPE in element_data.attributes:
                yield from xsd_element.iter_encode(value, validation, **kwargs)
                return

        if validation != 'skip' and self.process_contents == 'strict':
            yield self.validation_error(validation, reason, **kwargs)

        yield from self.any_type.iter_encode(obj, validation, **kwargs)

    def is_overlap(self, other: ModelParticleType) -> bool:
        if not isinstance(other, XsdAnyElement):
            if isinstance(other, elements.XsdElement):
                return other.is_overlap(self)
            return False

        if self.not_namespace:
            if other.not_namespace:
                return True
            elif '##any' in other.namespace:
                return True
            elif '##other' in other.namespace:
                return True
            else:
                return any(ns not in self.not_namespace for ns in other.namespace)
        elif other.not_namespace:
            if '##any' in self.namespace:
                return True
            elif '##other' in self.namespace:
                return True
            else:
                return any(ns not in other.not_namespace for ns in self.namespace)
        elif self.namespace == other.namespace:
            return True
        elif '##any' in self.namespace or '##any' in other.namespace:
            return True
        elif '##other' in self.namespace:
            return any(ns and ns != self.target_namespace for ns in other.namespace)
        elif '##other' in other.namespace:
            return any(ns and ns != other.target_namespace for ns in self.namespace)
        else:
            return any(ns in self.namespace for ns in other.namespace)

    def is_consistent(self, other: SchemaElementType, **kwargs: Any) -> bool:
        return True


class XsdAnyAttribute(XsdWildcard, ValidationMixin[Tuple[str, str], DecodedValueType]):
    """
    Class for XSD 1.0 *anyAttribute* wildcards.

    ..  <anyAttribute
          id = ID
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </anyAttribute>
    """
    copy: Callable[['XsdAnyAttribute'], 'XsdAnyAttribute']
    _ADMITTED_TAGS = {XSD_ANY_ATTRIBUTE}

    # Added for compatibility with protocol of XSD attributes
    use = None
    inheritable = False  # XSD 1.1 attributes

    def match(self, name: Optional[str], default_namespace: Optional[str] = None,
              resolve: bool = False, **kwargs: Any) -> Optional[SchemaAttributeType]:
        """
        Returns the attribute wildcard if name is matching the name provided
        as argument, `None` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used when it's not `None` and not empty for \
        completing local name arguments.
        :param resolve: when `True` it doesn't return the wildcard but try to \
        resolve and return the attribute matching the name.
        :param kwargs: additional options that can be used by certain components.
        """
        if not name or not self.is_matching(name, default_namespace, **kwargs):
            return None
        elif not resolve:
            return self

        try:
            if name[0] != '{' and default_namespace:
                return self.maps.lookup_attribute(f'{{{default_namespace}}}{name}')
            else:
                return self.maps.lookup_attribute(name)
        except LookupError:
            return None

    def iter_decode(self, obj: Tuple[str, str], validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[DecodedValueType]:
        name, value = obj

        if not self.is_matching(name):
            reason = _("attribute %r not allowed") % name
            yield self.validation_error(validation, reason, obj, **kwargs)

        if self.process_contents == 'skip':
            if 'process_skipped' not in kwargs or not kwargs['process_skipped']:
                return

        if self.maps.load_namespace(get_namespace(name)):
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if validation != 'skip' and self.process_contents == 'strict':
                    reason = _("attribute %r not found") % name
                    yield self.validation_error(validation, reason, obj, **kwargs)
            else:
                yield from xsd_attribute.iter_decode(value, validation, **kwargs)
                return

        elif validation != 'skip' and self.process_contents == 'strict':
            reason = _("unavailable namespace {!r}").format(get_namespace(name))
            yield self.validation_error(validation, reason, **kwargs)

        yield value

    def iter_encode(self, obj: Tuple[str, AtomicValueType], validation: str = 'lax',
                    **kwargs: Any) -> IterEncodeType[EncodedValueType]:
        name, value = obj
        namespace = get_namespace(name)

        if not self.is_namespace_allowed(namespace):
            reason = _("attribute %r not allowed") % name
            yield self.validation_error(validation, reason, obj, **kwargs)

        if self.process_contents == 'skip':
            if 'process_skipped' not in kwargs or not kwargs['process_skipped']:
                return

        if self.maps.load_namespace(namespace):
            try:
                xsd_attribute = self.maps.lookup_attribute(name)
            except LookupError:
                if validation != 'skip' and self.process_contents == 'strict':
                    reason = _("attribute %r not found") % name
                    yield self.validation_error(validation, reason, obj, **kwargs)
            else:
                yield from xsd_attribute.iter_encode(value, validation, **kwargs)
                return

        elif validation != 'skip' and self.process_contents == 'strict':
            reason = _("unavailable namespace {!r}").format(get_namespace(name))
            yield self.validation_error(validation, reason, **kwargs)

        yield raw_xml_encode(value)


class Xsd11AnyElement(XsdAnyElement):
    """
    Class for XSD 1.1 *any* declarations.

    ..  <any
          id = ID
          maxOccurs = (nonNegativeInteger | unbounded)  : 1
          minOccurs = nonNegativeInteger : 1
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          notNamespace = List of (anyURI | (##targetNamespace | ##local))
          notQName = List of (QName | (##defined | ##definedSibling))
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </any>
    """
    def _parse(self) -> None:
        super(Xsd11AnyElement, self)._parse()
        self._parse_not_constraints()

    def is_matching(self, name: Optional[str],
                    default_namespace: Optional[str] = None,
                    group: Optional[ModelGroupType] = None,
                    occurs: Optional[OccursCounterType] = None,
                    **kwargs: Any) -> bool:
        """
        Returns `True` if the component name is matching the name provided as argument,
        `False` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used by the XPath processor for completing \
        the name argument in case it's a local name.
        :param group: used only by XSD 1.1 any element wildcards to verify siblings in \
        case of ##definedSibling value in notQName attribute.
        :param occurs: a Counter instance for verify model occurrences counting.
        """
        if name is None:
            return False
        elif not name or name[0] == '{':
            if not self.is_namespace_allowed(get_namespace(name)):
                return False
        elif not default_namespace:
            if not self.is_namespace_allowed(''):
                return False
        else:
            name = f'{{{default_namespace}}}{name}'
            if not self.is_namespace_allowed(default_namespace):
                return False

        if group in self.precedences:
            if occurs is None:
                if any(e.is_matching(name) for e in self.precedences[group]):
                    return False
            elif any(e.is_matching(name) and not e.is_over(occurs[e])
                     for e in self.precedences[group]):
                return False

        if '##defined' in self.not_qname and name in self.maps.elements:
            return False
        if group and '##definedSibling' in self.not_qname:
            if any(e.is_matching(name) for e in group.iter_elements()
                   if not isinstance(e, XsdAnyElement)):
                return False

        return name not in self.not_qname

    def is_consistent(self, other: SchemaElementType, **kwargs: Any) -> bool:
        if isinstance(other, XsdAnyElement) or self.process_contents == 'skip':
            return True
        xsd_element = self.match(other.name, other.default_namespace, resolve=True)
        return xsd_element is None or other.is_consistent(xsd_element, strict=False)

    def add_precedence(self, other: ModelParticleType, group: ModelGroupType) -> None:
        try:
            self.precedences[group].append(other)
        except KeyError:
            self.precedences[group] = [other]


class Xsd11AnyAttribute(XsdAnyAttribute):
    """
    Class for XSD 1.1 *anyAttribute* declarations.

    ..  <anyAttribute
          id = ID
          namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
          notNamespace = List of (anyURI | (##targetNamespace | ##local))
          notQName = List of (QName | ##defined)
          processContents = (lax | skip | strict) : strict
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?)
        </anyAttribute>
    """
    def _parse(self) -> None:
        super(Xsd11AnyAttribute, self)._parse()
        self._parse_not_constraints()

    def is_matching(self, name: Optional[str],
                    default_namespace: Optional[str] = None,
                    **kwargs: Any) -> bool:
        if name is None:
            return False
        elif not name or name[0] == '{':
            namespace = get_namespace(name)
        elif not default_namespace:
            namespace = ''
        else:
            name = f'{{{default_namespace}}}{name}'
            namespace = default_namespace

        if '##defined' in self.not_qname and name in self.maps.attributes:
            xsd_attribute = self.maps.attributes[name]
            if isinstance(xsd_attribute, tuple):
                if xsd_attribute[1] is self.schema:
                    return False
            elif xsd_attribute.schema is self.schema:
                return False

        return name not in self.not_qname and self.is_namespace_allowed(namespace)


class XsdOpenContent(XsdComponent):
    """
    Class for XSD 1.1 *openContent* model definitions.

    ..  <openContent
          id = ID
          mode = (none | interleave | suffix) : interleave
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?), (any?)
        </openContent>
    """
    _ADMITTED_TAGS = {XSD_OPEN_CONTENT}
    mode = 'interleave'
    any_element = None  # type: Xsd11AnyElement

    def __init__(self, elem: ElementType, schema: SchemaType, parent: XsdComponent) -> None:
        super(XsdOpenContent, self).__init__(elem, schema, parent)

    def __repr__(self) -> str:
        return '%s(mode=%r)' % (self.__class__.__name__, self.mode)

    def _parse(self) -> None:
        super(XsdOpenContent, self)._parse()
        try:
            self.mode = self.elem.attrib['mode']
        except KeyError:
            pass
        else:
            if self.mode not in {'none', 'interleave', 'suffix'}:
                msg = _("wrong value %r for 'mode' attribute")
                self.parse_error(msg % self.mode)

        child = self._parse_child_component(self.elem)
        if self.mode == 'none':
            if child is not None and child.tag == XSD_ANY:
                msg = _("an openContent with mode='none' cannot "
                        "have an <xs:any> child declaration")
                self.parse_error(msg)
        elif child is None or child.tag != XSD_ANY:
            self.parse_error(_("an <xs:any> child declaration is required"))
        else:
            any_element = Xsd11AnyElement(child, self.schema, self)
            any_element.min_occurs = 0
            any_element.max_occurs = None
            self.any_element = any_element

    @property
    def built(self) -> bool:
        return True

    def is_restriction(self, other: 'XsdOpenContent') -> bool:
        if other is None or other.mode == 'none':
            return self.mode == 'none'
        elif self.mode == 'interleave' and other.mode == 'suffix':
            return False
        else:
            return self.any_element.is_restriction(other.any_element)


class XsdDefaultOpenContent(XsdOpenContent):
    """
    Class for XSD 1.1 *defaultOpenContent* model definitions.

    ..  <defaultOpenContent
          appliesToEmpty = boolean : false
          id = ID
          mode = (interleave | suffix) : interleave
          {any attributes with non-schema namespace . . .}>
          Content: (annotation?, any)
        </defaultOpenContent>
    """
    _ADMITTED_TAGS = {XSD_DEFAULT_OPEN_CONTENT}
    applies_to_empty = False

    def __init__(self, elem: ElementType, schema: SchemaType) -> None:
        super(XsdOpenContent, self).__init__(elem, schema)

    def _parse(self) -> None:
        super(XsdDefaultOpenContent, self)._parse()
        if self.parent is not None:
            msg = _("defaultOpenContent must be a child of the schema")
            self.parse_error(msg)
        if self.mode == 'none':
            msg = _("the attribute 'mode' of a defaultOpenContent cannot be 'none'")
            self.parse_error(msg)
        if self._parse_child_component(self.elem) is None:
            msg = _("a defaultOpenContent declaration cannot be empty")
            self.parse_error(msg)

        if 'appliesToEmpty' in self.elem.attrib:
            if self.elem.attrib['appliesToEmpty'].strip() in {'true', '1'}:
                self.applies_to_empty = True
