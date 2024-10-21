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
import re
from typing import TYPE_CHECKING, cast, Any, Dict, Generic, List, Iterator, Optional, \
    Set, Tuple, TypeVar, Union, MutableMapping
from xml.etree import ElementTree

from elementpath import select
from elementpath.etree import etree_tostring

from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..names import XSD_ANNOTATION, XSD_APPINFO, XSD_DOCUMENTATION, \
    XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE, XSD_ID, \
    XSD_QNAME, XSD_OVERRIDE, XSD_NOTATION_TYPE, XSD_DECIMAL, \
    XMLNS_NAMESPACE, XSD_BOOLEAN
from ..aliases import ElementType, NamespacesType, SchemaType, BaseXsdType, \
    ComponentClassType, ExtraValidatorType, DecodeType, IterDecodeType, \
    EncodeType, IterEncodeType
from ..translation import gettext as _
from ..helpers import get_qname, local_name, get_prefixed_qname, \
    is_etree_element, is_etree_document, format_xmlschema_stack
from ..resources import XMLResource
from ..converters import XMLSchemaConverter
from .exceptions import XMLSchemaParseError, XMLSchemaValidationError
from .helpers import get_xsd_annotation_child

if TYPE_CHECKING:
    from .simple_types import XsdSimpleType
    from .complex_types import XsdComplexType
    from .elements import XsdElement
    from .groups import XsdGroup
    from .global_maps import XsdGlobals

logger = logging.getLogger('xmlschema')

XSD_TYPE_DERIVATIONS = {'extension', 'restriction'}
XSD_ELEMENT_DERIVATIONS = {'extension', 'restriction', 'substitution'}

XSD_VALIDATION_MODES = {'strict', 'lax', 'skip'}
"""
XML Schema validation modes
Ref.: https://www.w3.org/TR/xmlschema11-1/#key-va
"""


def check_validation_mode(validation: str) -> None:
    if not isinstance(validation, str):
        raise XMLSchemaTypeError(_("validation mode must be a string"))
    if validation not in XSD_VALIDATION_MODES:
        raise XMLSchemaValueError(_("validation mode can be 'strict', "
                                    "'lax' or 'skip': %r") % validation)


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
    elem: Optional[ElementTree.Element] = None
    namespaces: Any = None
    errors: List[XMLSchemaParseError]

    def __init__(self, validation: str = 'strict') -> None:
        self.validation = validation
        self.errors = []

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

    def iter_components(self, xsd_classes: ComponentClassType = None) \
            -> Iterator[Union['XsdComponent', SchemaType, 'XsdGlobals']]:
        """
        Creates an iterator for traversing all XSD components of the validator.

        :param xsd_classes: returns only a specific class/classes of components, \
        otherwise returns all components.
        """
        raise NotImplementedError()

    @property
    def all_errors(self) -> List[XMLSchemaParseError]:
        """
        A list with all the building errors of the XSD validator and its components.
        """
        errors = []
        for comp in self.iter_components():
            if comp.errors:
                errors.extend(comp.errors)
        return errors

    def copy(self) -> 'XsdValidator':
        validator: 'XsdValidator' = object.__new__(self.__class__)
        validator.__dict__.update(self.__dict__)
        validator.errors = self.errors[:]  # shallow copy duplicates errors list
        return validator

    __copy__ = copy

    def parse_error(self, error: Union[str, Exception],
                    elem: Optional[ElementType] = None,
                    validation: Optional[str] = None) -> None:
        """
        Helper method for registering parse errors. Does nothing if validation mode is 'skip'.
        Il validation mode is 'lax' collects the error, otherwise raise the error.

        :param error: can be a parse error or an error message.
        :param elem: the Element instance related to the error, for default uses the 'elem' \
        attribute of the validator, if it's present.
        :param validation: overrides the default validation mode of the validator.
        """
        if validation is not None:
            check_validation_mode(validation)
        else:
            validation = self.validation

        if validation == 'skip':
            return
        elif elem is None:
            elem = self.elem
        elif not is_etree_element(elem):
            msg = "the argument 'elem' must be an Element instance, not {!r}."
            raise XMLSchemaTypeError(msg.format(elem))

        if isinstance(error, XMLSchemaParseError):
            if error.namespaces is None:
                error.namespaces = getattr(self, 'namespaces', None)
            if error.elem is None:
                error.elem = elem
            if error.source is None:
                error.source = getattr(self, 'source', None)
        elif isinstance(error, Exception):
            message = str(error).strip()
            if message[0] in '\'"' and message[0] == message[-1]:
                message = message.strip('\'"')
            error = XMLSchemaParseError(self, message, elem)
        elif isinstance(error, str):
            error = XMLSchemaParseError(self, error, elem)
        else:
            msg = "'error' argument must be an exception or a string, not {!r}."
            raise XMLSchemaTypeError(msg.format(error))

        if validation == 'lax':
            if error.stack_trace is None and logger.level == logging.DEBUG:
                error.stack_trace = format_xmlschema_stack()
                logger.debug("Collect %r with traceback:\n%s", error, error.stack_trace)

            self.errors.append(error)
        else:
            raise error

    def validation_error(self, validation: str,
                         error: Union[str, Exception],
                         obj: Any = None,
                         elem: Optional[ElementType] = None,
                         source: Optional[Any] = None,
                         namespaces: Optional[NamespacesType] = None,
                         **kwargs: Any) -> XMLSchemaValidationError:
        """
        Helper method for generating and updating validation errors. If validation
        mode is 'lax' or 'skip' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param error: an error instance or the detailed reason of failed validation.
        :param obj: the instance related to the error.
        :param elem: the element related to the error, can be `obj` for elements.
        :param source: the XML resource or data related to the validation process.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param kwargs: other keyword arguments of the validation process.
        """
        check_validation_mode(validation)
        if elem is None and is_etree_element(obj):
            elem = cast(ElementType, obj)

        if isinstance(error, XMLSchemaValidationError):
            if error.namespaces is None and namespaces is not None:
                error.namespaces = namespaces
            if error.source is None and source is not None:
                error.source = source
            if error.obj is None and obj is not None:
                error.obj = obj
            elif is_etree_element(error.obj) and elem is not None:
                if elem.tag == error.obj.tag and elem is not error.obj:
                    error.obj = elem

        elif isinstance(error, Exception):
            error = XMLSchemaValidationError(self, obj, str(error), source, namespaces)
        else:
            error = XMLSchemaValidationError(self, obj, error, source, namespaces)

        if error.elem is None and elem is not None:
            error.elem = elem

        if validation == 'strict' and error.elem is not None:
            raise error

        if error.stack_trace is None and logger.level == logging.DEBUG:
            error.stack_trace = format_xmlschema_stack()
            logger.debug("Collect %r with traceback:\n%s", error, error.stack_trace)

        if 'errors' in kwargs and error not in kwargs['errors']:
            kwargs['errors'].append(error)

        return error

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
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')
    _ADMITTED_TAGS: Union[Set[str], Tuple[str, ...], Tuple[()]] = ()

    elem: ElementType
    parent = None
    name = None
    ref: Optional['XsdComponent'] = None
    qualified = True
    redefine = None
    _annotation = None
    _annotations: List['XsdAnnotation']
    _target_namespace: Optional[str]

    def __init__(self, elem: ElementType,
                 schema: SchemaType,
                 parent: Optional['XsdComponent'] = None,
                 name: Optional[str] = None) -> None:

        super().__init__(schema.validation)
        if name:
            self.name = name
        if parent is not None:
            self.parent = parent
        self.schema = schema
        self.maps: XsdGlobals = schema.maps
        self.elem = elem

    def __setattr__(self, name: str, value: Any) -> None:
        if name == 'elem':
            if value.tag not in self._ADMITTED_TAGS:
                msg = "wrong XSD element {!r} for {!r}, must be one of {!r}"
                raise XMLSchemaValueError(
                    msg.format(value.tag, self.__class__, self._ADMITTED_TAGS)
                )
            super().__setattr__(name, value)
            if self.errors:
                self.errors.clear()
            self._parse()
        else:
            super().__setattr__(name, value)

    @property
    def xsd_version(self) -> str:
        return self.schema.XSD_VERSION

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
    def target_namespace(self) -> str:
        """Property that references to schema's targetNamespace."""
        return self.schema.target_namespace if self.ref is None else self.ref.target_namespace

    @property
    def default_namespace(self) -> Optional[str]:
        """Property that references to schema's default namespaces."""
        return self.schema.namespaces.get('')

    @property
    def namespaces(self) -> NamespacesType:
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

    @property
    def annotation(self) -> Optional['XsdAnnotation']:
        """
        The primary annotation of the XSD component, if any. This is the annotation
        defined in the first child of the element where the component is defined.
        """
        if '_annotation' not in self.__dict__:
            child = get_xsd_annotation_child(self.elem)
            if child is not None:
                self._annotation = XsdAnnotation(child, self.schema, self)
            else:
                self._annotation = None

        return self._annotation

    @property
    def annotations(self) -> List['XsdAnnotation']:
        """A list containing all the annotations of the XSD component."""
        if '_annotations' not in self.__dict__:
            self._annotations = []
            components = self.schema.components
            parent_map = self.schema.source.parent_map

            for elem in self.elem.iter():
                if elem is self.elem:
                    annotation = self.annotation
                    if annotation is not None:
                        self._annotations.append(annotation)
                elif elem in components:
                    break
                elif elem.tag == XSD_ANNOTATION:
                    parent_elem = parent_map[elem]
                    self._annotations.append(XsdAnnotation(elem, self.schema, self, parent_elem))

        return self._annotations

    def __repr__(self) -> str:
        if self.ref is not None:
            return '%s(ref=%r)' % (self.__class__.__name__, self.prefixed_name)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

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

        self._target_namespace = self.elem.attrib['targetNamespace'].strip()
        if self._target_namespace == XMLNS_NAMESPACE:
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
        if self._target_namespace != self.schema.target_namespace:
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

        if self.name is None:
            pass  # pragma: no cover
        elif not self._target_namespace:
            self.name = local_name(self.name)
        else:
            self.name = f'{{{self._target_namespace}}}{local_name(self.name)}'

    def _get_converter(self, obj: Any, kwargs: Dict[str, Any]) -> XMLSchemaConverter:
        if 'source' not in kwargs:
            if isinstance(obj, XMLResource):
                kwargs['source'] = obj
            elif is_etree_element(obj) or is_etree_document(obj):
                kwargs['source'] = XMLResource(obj)
            else:
                kwargs['source'] = obj

        converter = kwargs['converter'] = self.schema.get_converter(**kwargs)
        kwargs['namespaces'] = converter.namespaces
        return converter

    @property
    def local_name(self) -> Optional[str]:
        """The local part of the name of the component, or `None` if the name is `None`."""
        return None if self.name is None else local_name(self.name)

    @property
    def qualified_name(self) -> Optional[str]:
        """The name of the component in extended format, or `None` if the name is `None`."""
        return None if self.name is None else get_qname(self.target_namespace, self.name)

    @property
    def prefixed_name(self) -> Optional[str]:
        """The name of the component in prefixed format, or `None` if the name is `None`."""
        return None if self.name is None else get_prefixed_qname(self.name, self.namespaces)

    @property
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
        raise NotImplementedError()

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
            if self.namespaces.get(prefix) == target_namespace:
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
    _ADMITTED_TAGS = {XSD_ANNOTATION}

    annotation = None

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

    @property
    def built(self) -> bool:
        return True

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

    abstract = False
    base_type: Optional[BaseXsdType] = None
    derivation: Optional[str] = None
    _final: Optional[str] = None

    @property
    def final(self) -> str:
        return self.schema.final_default if self._final is None else self._final

    @property
    def built(self) -> bool:
        raise NotImplementedError()

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

    def is_derived(self, other: Union[BaseXsdType, Tuple[ElementType, SchemaType]],
                   derivation: Optional[str] = None) -> bool:
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
        return self.name == XSD_ID or self.is_derived(self.maps.types[XSD_ID])

    def is_qname(self) -> bool:
        return self.name == XSD_QNAME or self.is_derived(self.maps.types[XSD_QNAME])

    def is_notation(self) -> bool:
        return self.name == XSD_NOTATION_TYPE or self.is_derived(self.maps.types[XSD_NOTATION_TYPE])

    def is_decimal(self) -> bool:
        return self.name == XSD_DECIMAL or self.is_derived(self.maps.types[XSD_DECIMAL])

    def is_boolean(self) -> bool:
        return self.name == XSD_BOOLEAN or self.is_derived(self.maps.types[XSD_BOOLEAN])

    def text_decode(self, text: str) -> Any:
        raise NotImplementedError()


ST = TypeVar('ST')
DT = TypeVar('DT')


class ValidationMixin(Generic[ST, DT]):
    """
    Mixin for implementing XML data validators/decoders on XSD components.
    A derived class must implement the methods `iter_decode` and `iter_encode`.
    """
    def validate(self, obj: ST,
                 use_defaults: bool = True,
                 namespaces: Optional[NamespacesType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None) -> None:
        """
        Validates XML data against the XSD schema/component instance.

        :param obj: the XML data. Can be a string for an attribute or a simple type \
        validators, or an ElementTree's Element otherwise.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param max_depth: maximum level of validation, for default there is no limit.
        :param extra_validator: an optional function for performing non-standard \
        validations on XML data. The provided function is called for each traversed \
        element, with the XML element as 1st argument and the corresponding XSD \
        element as 2nd argument. It can be also a generator function and has to \
        raise/yield :exc:`xmlschema.XMLSchemaValidationError` exceptions.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the XML data instance is invalid.
        """
        for error in self.iter_errors(obj, use_defaults, namespaces,
                                      max_depth, extra_validator):
            raise error

    def is_valid(self, obj: ST,
                 use_defaults: bool = True,
                 namespaces: Optional[NamespacesType] = None,
                 max_depth: Optional[int] = None,
                 extra_validator: Optional[ExtraValidatorType] = None) -> bool:
        """
        Like :meth:`validate` except that does not raise an exception but returns
        ``True`` if the XML data instance is valid, ``False`` if it is invalid.
        """
        error = next(self.iter_errors(obj, use_defaults, namespaces,
                                      max_depth, extra_validator), None)
        return error is None

    def iter_errors(self, obj: ST,
                    use_defaults: bool = True,
                    namespaces: Optional[NamespacesType] = None,
                    max_depth: Optional[int] = None,
                    extra_validator: Optional[ExtraValidatorType] = None) \
            -> Iterator[XMLSchemaValidationError]:
        """
        Creates an iterator for the errors generated by the validation of an XML data against
        the XSD schema/component instance. Accepts the same arguments of :meth:`validate`.
        """
        kwargs: Dict[str, Any] = {
            'use_defaults': use_defaults,
            'namespaces': namespaces,
        }
        if max_depth is not None:
            kwargs['max_depth'] = max_depth
        if extra_validator is not None:
            kwargs['extra_validator'] = extra_validator

        for result in self.iter_decode(obj, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                del result

    def decode(self, obj: ST, validation: str = 'strict', **kwargs: Any) -> DecodeType[DT]:
        """
        Decodes XML data.

        :param obj: the XML data. Can be a string for an attribute or for simple type \
        components or a dictionary for an attribute group or an ElementTree's \
        Element for other components.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_decode`.
        :return: a dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
        a simple data type object otherwise. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the decoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        check_validation_mode(validation)

        result: Union[DT, XMLSchemaValidationError]
        errors: List[XMLSchemaValidationError] = []
        for result in self.iter_decode(obj, validation, **kwargs):  # pragma: no cover
            if not isinstance(result, XMLSchemaValidationError):
                return (result, errors) if validation == 'lax' else result
            elif validation == 'strict':
                raise result
            else:
                errors.append(result)

        return (None, errors) if validation == 'lax' else None  # fallback: pragma: no cover

    def encode(self, obj: Any, validation: str = 'strict', **kwargs: Any) -> EncodeType[Any]:
        """
        Encodes data to XML.

        :param obj: the data to be encoded to XML.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_encode`.
        :return: An element tree's Element if the original data is a structured data or \
        a string if it's simple type datum. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the encoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`xmlschema.XMLSchemaValidationError` if the object is not encodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        check_validation_mode(validation)
        result, errors = None, []
        for result in self.iter_encode(obj, validation=validation, **kwargs):  # pragma: no cover
            if not isinstance(result, XMLSchemaValidationError):
                break
            elif validation == 'strict':
                raise result
            else:
                errors.append(result)

        return (result, errors) if validation == 'lax' else result

    def iter_decode(self, obj: ST, validation: str = 'lax', **kwargs: Any) \
            -> IterDecodeType[DT]:
        """
        Creates an iterator for decoding an XML source to a Python object.

        :param obj: the XML data.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoder API.
        :return: Yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        raise NotImplementedError()

    def iter_encode(self, obj: Any, validation: str = 'lax', **kwargs: Any) \
            -> IterEncodeType[Any]:
        """
        Creates an iterator for encoding data to an Element tree.

        :param obj: The data that has to be encoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoder API.
        :return: Yields an Element, eventually preceded by a sequence of validation \
        or encoding errors.
        """
        raise NotImplementedError()
