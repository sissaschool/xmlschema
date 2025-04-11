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
This module contains base functions and classes XML Schema components.
"""
import logging
from collections.abc import Iterator, MutableMapping
from functools import cached_property
from typing import TYPE_CHECKING, cast, Any, Optional, Union

from elementpath import select
from elementpath.etree import etree_tostring

from xmlschema.exceptions import XMLSchemaValueError, XMLSchemaTypeError
from xmlschema.names import XSD_ANNOTATION, XSD_APPINFO, XSD_DOCUMENTATION, \
    XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE, XSD_BOOLEAN, XSD_ID, \
    XSD_QNAME, XSD_OVERRIDE, XSD_NOTATION_TYPE, XSD_DECIMAL, XMLNS_NAMESPACE
from xmlschema.aliases import ElementType, NsmapType, SchemaType, BaseXsdType, \
    ComponentClassType, DecodedValueType
from xmlschema.translation import gettext as _
from xmlschema.utils.qnames import get_qname, local_name, get_prefixed_qname
from xmlschema.utils.etree import is_etree_element
from xmlschema.utils.logger import format_xmlschema_stack, dump_data
from xmlschema.resources import XMLResource

from .validation import check_validation_mode, DecodeContext
from .exceptions import XMLSchemaParseError, XMLSchemaNotBuiltError
from .helpers import get_xsd_annotation_child

if TYPE_CHECKING:
    from .simple_types import XsdSimpleType
    from .complex_types import XsdComplexType
    from .elements import XsdElement
    from .groups import XsdGroup
    from .xsd_globals import XsdGlobals

logger = logging.getLogger('xmlschema')

XSD_TYPE_DERIVATIONS = {'extension', 'restriction'}
XSD_ELEMENT_DERIVATIONS = {'extension', 'restriction', 'substitution'}


class XsdValidator:
    """
    Common base class for XML Schema validator, that represents a PSVI (Post Schema Validation
    Infoset) information item. A concrete XSD validator have to report its validity collecting
    building errors and implementing the properties.

    :param validation: defines the XSD validation mode to use for build the validator, \
    its value can be 'strict', 'lax' or 'skip'. Strict mode is the default.
    :type validation: str

    :ivar validation: XSD validation mode.
    :vartype validation: str
    :ivar errors: XSD validator building errors.
    :vartype errors: list
    """
    def __init__(self, validation: str = 'strict') -> None:
        self.validation = validation
        self.errors: list[XMLSchemaParseError] = []

    @classmethod
    def _mro_slots(cls) -> Iterator[str]:
        for c in cls.__mro__:
            if hasattr(c, '__slots__'):
                yield from c.__slots__

    @property
    def built(self) -> bool:
        """
        Property that is ``True`` if XSD validator has been fully parsed and built,
        ``False`` otherwise. For schemas the property is checked on all global
        components. For XSD components check only the building of local subcomponents.
        """
        raise NotImplementedError()

    @property
    def validation_attempted(self) -> str:
        """
        Property that returns the *validation status* of the XSD validator.
        It can be 'full', 'partial' or 'none'.

        | https://www.w3.org/TR/xmlschema-1/#e-validation_attempted
        | https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validation_attempted
        """
        raise NotImplementedError()

    @property
    def validity(self) -> str:
        """
        Property that returns the XSD validator's validity.
        It can be ‘valid’, ‘invalid’ or ‘notKnown’.

        | https://www.w3.org/TR/xmlschema-1/#e-validity
        | https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validity
        """
        if self.validation == 'skip':
            return 'notKnown'
        elif self.errors or any(comp.errors for comp in self.iter_components()):
            return 'invalid'
        elif self.built:
            return 'valid'
        else:
            return 'notKnown'

    def check_validator(self, validation: Optional[str] = None) -> None:
        """Checks the status of a schema validator against a validation mode."""
        if validation is None:
            # Validator self-check
            validation = self.validation
            if self.validation_attempted == 'none' and self.validity == 'notKnown':
                return
        else:
            # Check called before validation
            check_validation_mode(validation)

        if self.validation_attempted == 'none' and validation != 'skip':
            msg = _("%r is not built") % self
            raise XMLSchemaNotBuiltError(self, msg)

        if validation == 'strict':
            if self.validation_attempted != 'full':
                msg = _("validation mode is 'strict' and %r is not built") % self
                raise XMLSchemaNotBuiltError(self, msg)
            if self.validity != 'valid':
                msg = _("validation mode is 'strict' and %r is not valid") % self
                raise XMLSchemaNotBuiltError(self, msg)

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[Union['XsdComponent', SchemaType, 'XsdGlobals']]:
        """
        Creates an iterator for traversing all XSD components of the validator.

        :param xsd_classes: returns only a specific class/classes of components, \
        otherwise returns all components.
        """
        raise NotImplementedError()

    @property
    def all_errors(self) -> list[XMLSchemaParseError]:
        """
        A list with all the building errors of the XSD validator and its components.
        """
        errors = []
        for comp in self.iter_components():
            if comp.errors:
                errors.extend(comp.errors)
        return errors

    @property
    def total_errors(self) -> int:
        return sum(len(comp.errors) for comp in self.iter_components())

    def __copy__(self) -> 'XsdValidator':
        validator: 'XsdValidator' = object.__new__(self.__class__)
        validator.validation = self.validation
        validator.errors = self.errors.copy()
        return validator

    def parse_error(self, error: Union[str, Exception],
                    elem: Optional[ElementType] = None,
                    validation: Optional[str] = None,
                    namespaces: Optional[NsmapType] = None) -> None:
        """
        Helper method for registering parse errors. Does nothing if validation mode is 'skip'.
        Il validation mode is 'lax' collects the error, otherwise raise the error.

        :param error: can be a parse error or an error message.
        :param elem: the Element instance related to the error, for default uses the 'elem' \
        attribute of the validator, if it's present.
        :param validation: overrides the default validation mode of the validator.
        :param namespaces: overrides the namespaces of the validator, or provides a mapping \
        if the validator hasn't a namespaces attribute.
        """
        if validation is not None:
            check_validation_mode(validation)
        else:
            validation = self.validation

        if validation == 'skip':
            return
        elif elem is None:
            elem = getattr(self, 'elem', None)
        elif not is_etree_element(elem):
            msg = "the argument 'elem' must be an Element instance, not {!r}."
            raise XMLSchemaTypeError(msg.format(elem))

        if namespaces is None:
            namespaces = getattr(self, 'namespaces', None)

        if isinstance(error, XMLSchemaParseError):
            if error.namespaces is None:
                error.namespaces = namespaces
            if error.elem is None:
                error.elem = elem
            if error.source is None:
                error.source = getattr(self, 'source', None)
        elif isinstance(error, Exception):
            message = str(error).strip()
            if message[0] in '\'"' and message[0] == message[-1]:
                message = message.strip('\'"')
            error = XMLSchemaParseError(self, message, elem, namespaces=namespaces)
        elif isinstance(error, str):
            error = XMLSchemaParseError(self, error, elem, namespaces=namespaces)
        else:
            msg = "'error' argument must be an exception or a string, not {!r}."
            raise XMLSchemaTypeError(msg.format(error))

        if validation == 'lax':
            if error.stack_trace is None and logger.level == logging.DEBUG:
                error.stack_trace = format_xmlschema_stack('xmlschema/validators')
                logger.debug("Collect %r with traceback:\n%s", error, error.stack_trace)

            self.errors.append(error)
        else:
            raise error

    def _parse_xpath_default_namespace(self, elem: ElementType) -> str:
        """
        Parse XSD 1.1 xpathDefaultNamespace attribute for schema, alternative, assert, assertion
        and selector declarations, checking if the value is conforming to the specification. In
        case the attribute is missing or for wrong attribute values defaults to ''.
        """
        try:
            value = elem.attrib['xpathDefaultNamespace']
        except KeyError:
            return ''

        value = value.strip()
        if value == '##local':
            return ''
        elif value == '##defaultNamespace':
            default_namespace = getattr(self, 'default_namespace', None)
            return default_namespace if isinstance(default_namespace, str) else ''
        elif value == '##targetNamespace':
            target_namespace = getattr(self, 'target_namespace', '')
            return target_namespace if isinstance(target_namespace, str) else ''
        elif len(value.split()) == 1:
            return value
        else:
            admitted_values = ('##defaultNamespace', '##targetNamespace', '##local')
            msg = _("wrong value {0!r} for 'xpathDefaultNamespace' "
                    "attribute, can be (anyURI | {1}).")
            self.parse_error(msg.format(value, ' | '.join(admitted_values)), elem)
            return ''


class XsdComponent(XsdValidator):
    """
    Class for XSD components. See: https://www.w3.org/TR/xmlschema-ref/

    :param elem: ElementTree's node containing the definition.
    :param schema: the XMLSchema object that owns the definition.
    :param parent: the XSD parent, `None` means that is a global component that \
    has the schema as parent.
    :param name: name of the component, maybe overwritten by the parse of the `elem` argument.

    :cvar qualified: for name matching, unqualified matching may be admitted only \
    for elements and attributes.
    :vartype qualified: bool
    """
    @classmethod
    def meta_tag(cls) -> str:
        """The reference tag for the component type."""
        try:
            return cls._ADMITTED_TAGS[0]
        except IndexError:
            raise NotImplementedError(f"not available for {cls!r}")

    _ADMITTED_TAGS: Union[tuple[str, ...], tuple[()]] = ()

    maps: 'XsdGlobals'
    elem: ElementType
    qualified = True
    ref: Optional['XsdComponent']
    redefine: Optional['XsdComponent']
    _built: bool = False  # marks whether the build() method has been called

    __slots__ = ('name', 'parent', 'schema', 'xsd_version', 'target_namespace', 'maps',
                 'builders', 'elem', 'validation', 'errors', 'ref', 'redefine')

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional['XsdComponent'] = None,
                 name: Optional[str] = None) -> None:

        super().__init__(schema.validation)
        self.ref = self.redefine = None
        self.name = name
        self.parent = parent
        self.schema = schema
        self.xsd_version = schema.XSD_VERSION
        self.target_namespace = schema.target_namespace
        self.maps = schema.maps
        self.builders = schema.builders
        self.parse(elem)

    def __repr__(self) -> str:
        if self.ref is not None:
            return '%s(ref=%r)' % (self.__class__.__name__, self.prefixed_name)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __copy__(self) -> 'XsdComponent':
        component: 'XsdComponent' = object.__new__(self.__class__)
        component.__dict__.update(self.__dict__)

        for cls in self.__class__.__mro__:
            for attr in getattr(cls, '__slots__', ()):
                object.__setattr__(component, attr, getattr(self, attr))

        component.errors = self.errors.copy()
        return component

    def is_global(self) -> bool:
        """Returns `True` if the instance is a global component, `False` if it's local."""
        return self.parent is None

    def is_override(self) -> bool:
        """Returns `True` if the instance is an override of a global component."""
        if self.parent is not None:
            return False
        return any(self.elem in x for x in self.schema.root if x.tag == XSD_OVERRIDE)

    @property
    def schema_elem(self) -> ElementType:
        """The reference element of the schema for the component instance."""
        return self.elem

    @property
    def source(self) -> XMLResource:
        """Property that references to schema source."""
        return self.schema.source

    @property
    def default_namespace(self) -> Optional[str]:
        """Property that references to schema's default namespaces."""
        return self.schema.namespaces.get('')

    @property
    def namespaces(self) -> NsmapType:
        """Property that references to schema's namespace mapping."""
        return self.schema.namespaces

    @property
    def any_type(self) -> 'XsdComplexType':
        """Property that references to the xs:anyType instance of the global maps."""
        return cast('XsdComplexType', self.maps.types[XSD_ANY_TYPE])

    @property
    def any_simple_type(self) -> 'XsdSimpleType':
        """Property that references to the xs:anySimpleType instance of the global maps."""
        return cast('XsdSimpleType', self.maps.types[XSD_ANY_SIMPLE_TYPE])

    @property
    def any_atomic_type(self) -> 'XsdSimpleType':
        """Property that references to the xs:anyAtomicType instance of the global maps."""
        return cast('XsdSimpleType', self.maps.types[XSD_ANY_ATOMIC_TYPE])

    @cached_property
    def annotation(self) -> Optional['XsdAnnotation']:
        """
        The primary annotation of the XSD component, if any. This is the annotation
        defined in the first child of the element where the component is defined.
        """
        child = get_xsd_annotation_child(self.elem)
        if child is not None:
            return XsdAnnotation(child, self.schema, self)
        else:
            return None

    @cached_property
    def annotations(self) -> Union[tuple[()], list['XsdAnnotation']]:
        """A list containing all the annotations of the XSD component."""
        annotations = []
        components = self.schema.components
        parent_map = self.schema.source.parent_map

        for elem in self.elem.iter():
            if elem is self.elem:
                if self.annotation is not None:
                    annotations.append(self.annotation)
            elif elem in components:
                break
            elif elem.tag == XSD_ANNOTATION:
                parent_elem = parent_map[elem]
                if parent_elem is not self.elem:
                    annotations.append(XsdAnnotation(elem, self.schema, self, parent_elem))

        return annotations

    def parse(self, elem: ElementType) -> None:
        """Set and parse the component Element."""
        if elem.tag not in self._ADMITTED_TAGS:
            msg = "wrong XSD element {!r} for {!r}, must be one of {!r}"
            raise XMLSchemaValueError(
                msg.format(elem.tag, self.__class__, self._ADMITTED_TAGS)
            )

        if hasattr(self, 'elem'):
            # Redefinition of a global component
            if self.parent is not None:
                raise XMLSchemaValueError(f'{self!r} is not a global component')
            self.__dict__.clear()

        self.elem = elem
        if self.errors:
            self.errors.clear()
        self._parse()

        if self.__class__.build is XsdComponent.build:
            self._built = True

    def _parse(self) -> None:
        return

    def _parse_reference(self) -> Optional[bool]:
        """
        Helper method for referable components. Returns `True` if a valid reference QName
        is found without any error, otherwise returns `None`. Sets an id-related name for
        the component ('nameless_<id of the instance>') if both the attributes 'ref' and
        'name' are missing.
        """
        ref = self.elem.get('ref')
        if ref is None:
            if 'name' in self.elem.attrib:
                return None
            elif self.parent is None:
                msg = _("missing attribute 'name' in a global %r")
                self.parse_error(msg % type(self))
            else:
                msg = _("missing both attributes 'name' and 'ref' in local %r")
                self.parse_error(msg % type(self))
        elif 'name' in self.elem.attrib:
            msg = _("attributes 'name' and 'ref' are mutually exclusive")
            self.parse_error(msg)
        elif self.parent is None:
            msg = _("attribute 'ref' not allowed in a global %r")
            self.parse_error(msg % type(self))
        else:
            try:
                self.name = self.schema.resolve_qname(ref)
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err)
            else:
                if self._parse_child_component(self.elem, strict=False) is not None:
                    msg = _("a reference component cannot have child definitions/declarations")
                    self.parse_error(msg)
                return True

        return None

    def _parse_child_component(self, elem: ElementType, strict: bool = True) \
            -> Optional[ElementType]:
        child = None
        for e in elem:
            if e.tag == XSD_ANNOTATION or callable(e.tag):
                continue
            elif not strict:
                return e
            elif child is not None:
                msg = _("too many XSD components, unexpected {0!r} found at position {1}")
                self.parse_error(msg.format(child, elem[:].index(e)), elem)
                break
            else:
                child = e
        return child

    def _parse_target_namespace(self) -> None:
        """
        XSD 1.1 targetNamespace attribute in elements and attributes declarations.
        """
        if 'targetNamespace' not in self.elem.attrib:
            return

        target_namespace = self.elem.attrib['targetNamespace'].strip()
        if target_namespace == XMLNS_NAMESPACE:
            # https://www.w3.org/TR/xmlschema11-1/#sec-nss-special
            msg = _(f"The namespace {XMLNS_NAMESPACE} cannot be used as 'targetNamespace'")
            raise XMLSchemaValueError(msg)

        if 'name' not in self.elem.attrib:
            msg = _("attribute 'name' must be present when "
                    "'targetNamespace' attribute is provided")
            self.parse_error(msg)
        if 'form' in self.elem.attrib:
            msg = _("attribute 'form' must be absent when "
                    "'targetNamespace' attribute is provided")
            self.parse_error(msg)
        if target_namespace != self.target_namespace:
            if self.parent is None:
                msg = _("a global %s must have the same namespace as its parent schema")
                self.parse_error(msg % self.__class__.__name__)

            xsd_type = self.get_parent_type()
            if xsd_type is None or xsd_type.parent is not None:
                pass
            elif xsd_type.derivation != 'restriction' or \
                    getattr(xsd_type.base_type, 'name', None) == XSD_ANY_TYPE:
                msg = _("a declaration contained in a global complexType "
                        "must have the same namespace as its parent schema")
                self.parse_error(msg)

        self.target_namespace = target_namespace
        if self.name is None:
            pass  # pragma: no cover
        elif not target_namespace:
            self.name = local_name(self.name)
        else:
            self.name = f'{{{target_namespace}}}{local_name(self.name)}'

    @cached_property
    def local_name(self) -> Optional[str]:
        """The local part of the name of the component, or `None` if the name is `None`."""
        return None if self.name is None else local_name(self.name)

    @cached_property
    def qualified_name(self) -> Optional[str]:
        """The name of the component in extended format, or `None` if the name is `None`."""
        return None if self.name is None else get_qname(self.target_namespace, self.name)

    @cached_property
    def prefixed_name(self) -> Optional[str]:
        """The name of the component in prefixed format, or `None` if the name is `None`."""
        return None if self.name is None else get_prefixed_qname(self.name, self.namespaces)

    @cached_property
    def display_name(self) -> Optional[str]:
        """
        The name of the component to display when you have to refer to it with a
        simple unambiguous format.
        """
        prefixed_name = self.prefixed_name
        if prefixed_name is None:
            return None
        return self.name if ':' not in prefixed_name else prefixed_name

    @property
    def id(self) -> Optional[str]:
        """The ``'id'`` attribute of the component tag, ``None`` if missing."""
        return self.elem.get('id')

    @property
    def validation_attempted(self) -> str:
        return 'full' if self.built else 'partial'

    def build(self) -> None:
        """
        Builds components that are not fully parsed at initialization, like model groups
        or internal local elements in model groups, otherwise does nothing.
        """

    @property
    def built(self) -> bool:
        return self._built

    def is_matching(self, name: Optional[str], default_namespace: Optional[str] = None,
                    **kwargs: Any) -> bool:
        """
        Returns `True` if the component name is matching the name provided as argument,
        `False` otherwise. For XSD elements the matching is extended to substitutes.

        :param name: a local or fully-qualified name.
        :param default_namespace: used by the XPath processor for completing \
        the name argument in case it's a local name.
        :param kwargs: additional options that can be used by certain components.
        """
        return bool(self.name == name or default_namespace and name and
                    name[0] != '{' and self.name == f'{{{default_namespace}}}{name}')

    def match(self, name: Optional[str], default_namespace: Optional[str] = None,
              **kwargs: Any) -> Optional['XsdComponent']:
        """
        Returns the component if its name is matching the name provided as argument,
        `None` otherwise.
        """
        return self if self.is_matching(name, default_namespace, **kwargs) else None

    def get_matching_item(self, mapping: MutableMapping[str, Any],
                          ns_prefix: str = 'xmlns',
                          match_local_name: bool = False) -> Optional[Any]:
        """
        If a key is matching component name, returns its value, otherwise returns `None`.
        """
        if self.name is None:
            return None
        elif not self.target_namespace:
            return mapping.get(self.name)
        elif self.qualified_name in mapping:
            return mapping[cast(str, self.qualified_name)]
        elif self.prefixed_name in mapping:
            return mapping[cast(str, self.prefixed_name)]

        # Try a match with other prefixes
        target_namespace = self.target_namespace
        suffix = f':{self.local_name}'

        for k in filter(lambda x: x.endswith(suffix), mapping):
            prefix = k.split(':')[0]
            if self.schema.namespaces.get(prefix) == target_namespace:
                return mapping[k]

            # Match namespace declaration within value
            ns_declaration = f'{ns_prefix}:{prefix}'
            try:
                if mapping[k][ns_declaration] == target_namespace:
                    return mapping[k]
            except (KeyError, TypeError):
                pass
        else:
            if match_local_name:
                return mapping.get(self.local_name)  # type: ignore[arg-type]
            return None

    def get_global(self) -> 'XsdComponent':
        """Returns the global XSD component that contains the component instance."""
        if self.parent is None:
            return self
        component = self.parent
        while component is not self:
            if component.parent is None:
                return component
            component = component.parent
        else:  # pragma: no cover
            msg = _("parent circularity from {}")
            raise XMLSchemaValueError(msg.format(self))

    def get_parent_type(self) -> Optional['XsdType']:
        """
        Returns the nearest XSD type that contains the component instance,
        or `None` if the component doesn't have an XSD type parent.
        """
        component = self.parent
        while component is not self and component is not None:
            if isinstance(component, XsdType):
                return component
            component = component.parent
        return None

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator['XsdComponent']:
        """
        Creates an iterator for XSD subcomponents.

        :param xsd_classes: provide a class or a tuple of classes to iterate \
        over only a specific classes of components.
        """
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self

    def iter_ancestors(self, xsd_classes: ComponentClassType = None)\
            -> Iterator['XsdComponent']:
        """
        Creates an iterator for XSD ancestor components, schema excluded.
        Stops when the component is global or if the ancestor is not an
        instance of the specified class/classes.

        :param xsd_classes: provide a class or a tuple of classes to iterate \
        over only a specific classes of components.
        """
        ancestor = self
        while True:
            if ancestor.parent is None:
                break
            ancestor = ancestor.parent
            if xsd_classes is not None and not isinstance(ancestor, xsd_classes):
                break
            yield ancestor

    def tostring(self, indent: str = '', max_lines: Optional[int] = None,
                 spaces_for_tab: int = 4) -> Union[str, bytes]:
        """Serializes the XML elements that declare or define the component to a string."""
        return etree_tostring(self.schema_elem, self.namespaces, indent, max_lines, spaces_for_tab)

    def dump_status(self, *args: Any) -> None:
        """Dump component status to logger for debugging purposes."""
        dump_data(self.schema.source, *args)


class XsdAnnotation(XsdComponent):
    """
    Class for XSD *annotation* definitions.

    :ivar appinfo: a list containing the xs:appinfo children.
    :ivar documentation: a list containing the xs:documentation children.

    ..  <annotation
          id = ID
          {any attributes with non-schema namespace . . .}>
          Content: (appinfo | documentation)*
        </annotation>

    ..  <appinfo
          source = anyURI
          {any attributes with non-schema namespace . . .}>
          Content: ({any})*
        </appinfo>

    ..  <documentation
          source = anyURI
          xml:lang = language
          {any attributes with non-schema namespace . . .}>
          Content: ({any})*
        </documentation>
    """
    _ADMITTED_TAGS = XSD_ANNOTATION,

    annotation = None
    annotations = ()

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional[XsdComponent] = None,
                 parent_elem: Optional[ElementType] = None) -> None:

        super().__init__(elem, schema, parent)
        if parent_elem is not None:
            self.parent_elem = parent_elem
        elif parent is not None:
            self.parent_elem = parent.elem
        else:
            self.parent_elem = schema.source.root

    def __repr__(self) -> str:
        return '%s(%r)' % (self.__class__.__name__, str(self)[:40])

    def __str__(self) -> str:
        return '\n'.join(select(self.elem, '*/fn:string()'))

    def _parse(self) -> None:
        self.appinfo = []
        self.documentation = []
        for child in self.elem:
            if child.tag == XSD_APPINFO:
                self.appinfo.append(child)
            elif child.tag == XSD_DOCUMENTATION:
                self.documentation.append(child)


class XsdType(XsdComponent):
    """Common base class for XSD types."""

    __slots__ = ()

    base_type: Optional[BaseXsdType] = None
    derivation: Optional[str] = None
    _final: Optional[str] = None

    @property
    def final(self) -> str:
        return self.schema.final_default if self._final is None else self._final

    @property
    def content_type_label(self) -> str:
        """The content type classification."""
        raise NotImplementedError()

    @property
    def sequence_type(self) -> str:
        """The XPath sequence type associated with the content."""
        raise NotImplementedError()

    @property
    def root_type(self) -> BaseXsdType:
        """
        The root type of the type definition hierarchy. For an atomic type
        is the primitive type. For a list is the primitive type of the item.
        For a union is the base union type. For a complex type is xs:anyType.
        """
        raise NotImplementedError()

    @property
    def simple_type(self) -> Optional['XsdSimpleType']:
        """
        Property that is the instance itself for a simpleType. For a
        complexType is the instance's *content* if this is a simpleType
        or `None` if the instance's *content* is a model group.
        """
        raise NotImplementedError()

    @property
    def model_group(self) -> Optional['XsdGroup']:
        """
        Property that is `None` for a simpleType. For a complexType is
        the instance's *content* if this is a model group or `None` if
        the instance's *content* is a simpleType.
        """
        return None

    @staticmethod
    def is_simple() -> bool:
        """Returns `True` if the instance is a simpleType, `False` otherwise."""
        raise NotImplementedError()

    @staticmethod
    def is_complex() -> bool:
        """Returns `True` if the instance is a complexType, `False` otherwise."""
        raise NotImplementedError()

    def is_atomic(self) -> bool:
        """Returns `True` if the instance is an atomic simpleType, `False` otherwise."""
        return False

    def is_primitive(self) -> bool:
        """Returns `True` if the type is an XSD primitive builtin type, `False` otherwise."""
        return False

    def is_list(self) -> bool:
        """Returns `True` if the instance is a list simpleType, `False` otherwise."""
        return False

    def is_union(self) -> bool:
        """Returns `True` if the instance is a union simpleType, `False` otherwise."""
        return False

    def is_datetime(self) -> bool:
        """
        Returns `True` if the instance is a datetime/duration XSD builtin-type, `False` otherwise.
        """
        return False

    def is_empty(self) -> bool:
        """Returns `True` if the instance has an empty content, `False` otherwise."""
        raise NotImplementedError()

    def is_emptiable(self) -> bool:
        """Returns `True` if the instance has an emptiable value or content, `False` otherwise."""
        raise NotImplementedError()

    def has_simple_content(self) -> bool:
        """
        Returns `True` if the instance has a simple content, `False` otherwise.
        """
        raise NotImplementedError()

    def has_complex_content(self) -> bool:
        """
        Returns `True` if the instance is a complexType with mixed or element-only
        content, `False` otherwise.
        """
        raise NotImplementedError()

    def has_mixed_content(self) -> bool:
        """
        Returns `True` if the instance is a complexType with mixed content, `False` otherwise.
        """
        raise NotImplementedError()

    def is_element_only(self) -> bool:
        """
        Returns `True` if the instance is a complexType with element-only content,
        `False` otherwise.
        """
        raise NotImplementedError()

    def is_derived(self, other: BaseXsdType, derivation: Optional[str] = None) -> bool:
        """
        Returns `True` if the instance is derived from *other*, `False` otherwise.
        The optional argument derivation can be a string containing the words
        'extension' or 'restriction' or both.
        """
        raise NotImplementedError()

    def is_extension(self) -> bool:
        return self.derivation == 'extension'

    def is_restriction(self) -> bool:
        return self.derivation == 'restriction'

    def is_blocked(self, xsd_element: 'XsdElement') -> bool:
        """
        Returns `True` if the base type derivation is blocked, `False` otherwise.
        """
        xsd_type = xsd_element.type
        if self is xsd_type:
            return False

        block = f'{xsd_element.block} {xsd_type.block}'.strip()
        if not block:
            return False

        _block = {x for x in block.split() if x in ('extension', 'restriction')}
        return any(self.is_derived(xsd_type, derivation) for derivation in _block)

    def is_dynamic_consistent(self, other: Any) -> bool:
        raise NotImplementedError()

    def is_key(self) -> bool:
        return self.is_derived(self.maps.types[XSD_ID])

    def is_qname(self) -> bool:
        return self.is_derived(self.maps.types[XSD_QNAME])

    def is_notation(self) -> bool:
        return self.is_derived(self.maps.types[XSD_NOTATION_TYPE])

    def is_decimal(self) -> bool:
        return self.is_derived(self.maps.types[XSD_DECIMAL])

    def is_boolean(self) -> bool:
        return self.is_derived(self.maps.types[XSD_BOOLEAN])

    def text_decode(self, text: str, validation: str = 'skip',
                    context: Optional[DecodeContext] = None) -> DecodedValueType:
        raise NotImplementedError()

    def text_is_valid(self, text: str, context: Optional[DecodeContext] = None) -> bool:
        raise NotImplementedError()
