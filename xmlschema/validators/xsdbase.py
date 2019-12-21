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
This module contains base functions and classes XML Schema components.
"""
from __future__ import unicode_literals
import re

from ..compat import PY3, string_base_type, unicode_type
from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..qnames import XSD_ANNOTATION, XSD_APPINFO, XSD_DOCUMENTATION, XML_LANG, \
    XSD_ANY_TYPE, XSD_ANY_SIMPLE_TYPE, XSD_ANY_ATOMIC_TYPE, XSD_ID, XSD_OVERRIDE, \
    get_qname, local_name, qname_to_prefixed
from ..etree import etree_tostring
from ..helpers import is_etree_element
from .exceptions import XMLSchemaParseError, XMLSchemaValidationError, \
    XMLSchemaDecodeError, XMLSchemaEncodeError


XSD_VALIDATION_MODES = {'strict', 'lax', 'skip'}
"""
XML Schema validation modes
Ref.: https://www.w3.org/TR/xmlschema11-1/#key-va
"""


class XsdValidator(object):
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
    xsd_version = None

    def __init__(self, validation='strict'):
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)
        self.validation = validation
        self.errors = []

    def __str__(self):
        # noinspection PyCompatibility,PyUnresolvedReferences
        return unicode(self).encode("utf-8")

    def __unicode__(self):
        return self.__repr__()

    if PY3:
        __str__ = __unicode__

    @property
    def built(self):
        """
        Property that is ``True`` if XSD validator has been fully parsed and built,
        ``False`` otherwise. For schemas the property is checked on all global
        components. For XSD components check only the building of local subcomponents.
        """
        raise NotImplementedError

    @property
    def validation_attempted(self):
        """
        Property that returns the *validation status* of the XSD validator. It can be 'full', 'partial' or 'none'.

        | https://www.w3.org/TR/xmlschema-1/#e-validation_attempted
        | https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validation_attempted
        """
        raise NotImplementedError

    @property
    def validity(self):
        """
        Property that returns the XSD validator's validity. It can be ‘valid’, ‘invalid’ or ‘notKnown’.

        | https://www.w3.org/TR/xmlschema-1/#e-validity
        | https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validity
        """
        if self.errors or any(comp.errors for comp in self.iter_components()):
            return 'invalid'
        elif self.built:
            return 'valid'
        else:
            return 'notKnown'

    def iter_components(self, xsd_classes=None):
        """
        Creates an iterator for traversing all XSD components of the validator.

        :param xsd_classes: returns only a specific class/classes of components, \
        otherwise returns all components.
        """
        raise NotImplementedError

    @property
    def all_errors(self):
        """
        A list with all the building errors of the XSD validator and its components.
        """
        errors = []
        for comp in self.iter_components():
            if comp.errors:
                errors.extend(comp.errors)
        return errors

    def copy(self):
        validator = object.__new__(self.__class__)
        validator.__dict__.update(self.__dict__)
        validator.errors = self.errors[:]
        return validator

    __copy__ = copy

    def parse_error(self, error, elem=None, validation=None):
        """
        Helper method for registering parse errors. Does nothing if validation mode is 'skip'.
        Il validation mode is 'lax' collects the error, otherwise raise the error.

        :param error: can be a parse error or an error message.
        :param elem: the Element instance related to the error, for default uses the 'elem' \
        attribute of the validator, if it's present.
        :param validation: overrides the default validation mode of the validator.
        """
        if validation not in XSD_VALIDATION_MODES:
            validation = self.validation
        if validation == 'skip':
            return

        if is_etree_element(elem):
            pass
        elif elem is None:
            elem = getattr(self, 'elem', None)
        else:
            raise XMLSchemaValueError("'elem' argument must be an Element instance, not %r." % elem)

        if isinstance(error, XMLSchemaParseError):
            error.validator = self
            error.namespaces = getattr(self, 'namespaces', None)
            error.elem = elem
            error.source = getattr(self, 'source', None)
        elif isinstance(error, Exception):
            message = unicode_type(error).strip()
            if message[0] in '\'"' and message[0] == message[-1]:
                message = message.strip('\'"')
            error = XMLSchemaParseError(self, message, elem)
        elif isinstance(error, string_base_type):
            error = XMLSchemaParseError(self, error, elem)
        else:
            raise XMLSchemaValueError("'error' argument must be an exception or a string, not %r." % error)

        if validation == 'lax':
            self.errors.append(error)
        else:
            raise error

    def _parse_xpath_default_namespace(self, elem):
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
            return getattr(self, 'default_namespace')
        elif value == '##targetNamespace':
            return getattr(self, 'target_namespace')
        elif len(value.split()) == 1:
            return value
        else:
            admitted_values = ('##defaultNamespace', '##targetNamespace', '##local')
            msg = "wrong value %r for 'xpathDefaultNamespace' attribute, can be (anyURI | %s)."
            self.parse_error(msg % (value, ' | '.join(admitted_values)), elem)
            return ''


class XsdComponent(XsdValidator):
    """
    Class for XSD components. See: https://www.w3.org/TR/xmlschema-ref/

    :param elem: ElementTree's node containing the definition.
    :param schema: the XMLSchema object that owns the definition.
    :param parent: the XSD parent, `None` means that is a global component that has the schema as parent.
    :param name: name of the component, maybe overwritten by the parse of the `elem` argument.

    :cvar qualified: for name matching, unqualified matching may be admitted only for elements and attributes.
    :vartype qualified: bool
    """
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')
    _ADMITTED_TAGS = ()

    parent = None
    name = None
    ref = None
    qualified = True

    def __init__(self, elem, schema, parent=None, name=None):
        super(XsdComponent, self).__init__(schema.validation)
        if name is not None:
            assert name and (name[0] == '{' or not schema.target_namespace), \
                "name=%r argument: must be a qualified name of the target namespace." % name
            self.name = name
        if parent is not None:
            self.parent = parent
        self.schema = schema
        self.elem = elem

    def __setattr__(self, name, value):
        if name == "elem":
            if not is_etree_element(value):
                raise XMLSchemaTypeError("%r attribute must be an Etree Element: %r" % (name, value))
            elif value.tag not in self._ADMITTED_TAGS:
                raise XMLSchemaValueError(
                    "wrong XSD element %r for %r, must be one of %r." % (
                        local_name(value.tag), self,
                        [local_name(tag) for tag in self._ADMITTED_TAGS]
                    )
                )
            super(XsdComponent, self).__setattr__(name, value)
            self._parse()
            return
        elif name == "schema":
            if hasattr(self, 'schema') and self.schema.target_namespace != value.target_namespace:
                raise XMLSchemaValueError(
                    "cannot change 'schema' attribute of %r: the actual %r has a different "
                    "target namespace than %r." % (self, self.schema, value)
                )
        super(XsdComponent, self).__setattr__(name, value)

    @property
    def xsd_version(self):
        return self.schema.XSD_VERSION

    def is_global(self):
        """Returns `True` if the instance is a global component, `False` if it's local."""
        return self.parent is None

    def is_override(self):
        """Returns `True` if the instance is an override of a global component."""
        if self.parent is not None:
            return False
        return any(self.elem in x for x in self.schema.root if x.tag == XSD_OVERRIDE)

    @property
    def schema_elem(self):
        """The reference element of the schema for the component instance."""
        return self.elem

    @property
    def source(self):
        """Property that references to schema source."""
        return self.schema.source

    @property
    def target_namespace(self):
        """Property that references to schema's targetNamespace."""
        return self.schema.target_namespace if self.ref is None else self.ref.target_namespace

    @property
    def default_namespace(self):
        """Property that references to schema's default namespaces."""
        return self.schema.namespaces.get('')

    @property
    def namespaces(self):
        """Property that references to schema's namespace mapping."""
        return self.schema.namespaces

    @property
    def maps(self):
        """Property that references to schema's global maps."""
        return self.schema.maps

    @property
    def any_type(self):
        """Property that references to the xs:anyType instance of the global maps."""
        return self.schema.maps.types[XSD_ANY_TYPE]

    @property
    def any_simple_type(self):
        """Property that references to the xs:anySimpleType instance of the global maps."""
        return self.schema.maps.types[XSD_ANY_SIMPLE_TYPE]

    @property
    def any_atomic_type(self):
        """Property that references to the xs:anyAtomicType instance of the global maps."""
        return self.schema.maps.types[XSD_ANY_ATOMIC_TYPE]

    def __repr__(self):
        if self.name is None:
            return '<%s at %#x>' % (self.__class__.__name__, id(self))
        elif self.ref is not None:
            return '%s(ref=%r)' % (self.__class__.__name__, self.prefixed_name)
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def _parse(self):
        del self.errors[:]
        try:
            if self.elem[0].tag == XSD_ANNOTATION:
                self.annotation = XsdAnnotation(self.elem[0], self.schema, self)
            else:
                self.annotation = None
        except (TypeError, IndexError):
            self.annotation = None

    def _parse_reference(self):
        """
        Helper method for referable components. Returns `True` if a valid reference QName
        is found without any error, otherwise returns `None`. Sets an id-related name for
        the component ('nameless_<id of the instance>') if both the attributes 'ref' and
        'name' are missing.
        """
        ref = self.elem.get('ref')
        if ref is None:
            if 'name' in self.elem.attrib:
                return
            elif self.parent is None:
                self.parse_error("missing attribute 'name' in a global %r" % type(self))
            else:
                self.parse_error("missing both attributes 'name' and 'ref' in local %r" % type(self))
            self.name = 'nameless_%s' % str(id(self))
        elif self.parent is None:
            self.parse_error("attribute 'ref' not allowed in a global %r" % type(self))
        elif 'name' in self.elem.attrib:
            self.parse_error("attributes 'name' and 'ref' are mutually exclusive")
        else:
            try:
                self.name = self.schema.resolve_qname(ref)
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err)
            else:
                if self._parse_child_component(self.elem) is not None:
                    self.parse_error("a reference component cannot has child definitions/declarations")
                return True

    def _parse_boolean_attribute(self, name):
        try:
            value = self.elem.attrib[name].strip()
        except KeyError:
            return
        else:
            if value in ('true', '1'):
                return True
            elif value in ('false', '0'):
                return False
            else:
                self.parse_error("wrong value %r for boolean attribute %r" % (value, name))

    def _parse_child_component(self, elem, strict=True):
        child = None
        for index, child in enumerate(filter(lambda x: x.tag != XSD_ANNOTATION, elem)):
            if not strict:
                return child
            elif index:
                msg = "too many XSD components, unexpected {!r} found at position {}"
                self.parse_error(msg.format(child, index), elem)
        return child

    def _parse_target_namespace(self):
        """
        XSD 1.1 targetNamespace attribute in elements and attributes declarations.
        """
        if 'targetNamespace' not in self.elem.attrib:
            return

        self._target_namespace = self.elem.attrib['targetNamespace'].strip()
        if 'name' not in self.elem.attrib:
            self.parse_error("attribute 'name' must be present when 'targetNamespace' attribute is provided")
        if 'form' in self.elem.attrib:
            self.parse_error("attribute 'form' must be absent when 'targetNamespace' attribute is provided")
        if self._target_namespace != self.schema.target_namespace:
            if self.parent is None:
                self.parse_error("a global attribute must has the same namespace as its parent schema")

            xsd_type = self.get_parent_type()
            if xsd_type and xsd_type.parent is None and \
                    (xsd_type.derivation != 'restriction' or xsd_type.base_type.name == XSD_ANY_TYPE):
                self.parse_error("a declaration contained in a global complexType "
                                 "must has the same namespace as its parent schema")

        if not self._target_namespace and self.name[0] == '{':
            self.name = local_name(self.name)
        elif self.name[0] != '{':
            self.name = '{%s}%s' % (self._target_namespace, self.name)
        else:
            self.name = '{%s}%s' % (self._target_namespace, local_name(self.name))

    @property
    def local_name(self):
        return local_name(self.name)

    @property
    def qualified_name(self):
        return get_qname(self.target_namespace, self.name)

    @property
    def prefixed_name(self):
        return qname_to_prefixed(self.name, self.namespaces)

    @property
    def id(self):
        """The ``'id'`` attribute of the component tag, ``None`` if missing."""
        return self.elem.get('id')

    @property
    def validation_attempted(self):
        return 'full' if self.built else 'partial'

    @property
    def built(self):
        raise NotImplementedError

    def is_matching(self, name, default_namespace=None, **kwargs):
        """
        Returns `True` if the component name is matching the name provided as argument,
        `False` otherwise. For XSD elements the matching is extended to substitutes.

        :param name: a local or fully-qualified name.
        :param default_namespace: used if it's not None and not empty for completing the name \
        argument in case it's a local name.
        :param kwargs: additional options that can be used by certain components.
        """
        if not name:
            return self.name == name
        elif name[0] == '{':
            return self.qualified_name == name
        elif not default_namespace:
            return self.name == name or not self.qualified and self.local_name == name
        else:
            qname = '{%s}%s' % (default_namespace, name)
            return self.qualified_name == qname or not self.qualified and self.local_name == name

    def match(self, name, default_namespace=None, **kwargs):
        """Returns the component if its name is matching the name provided as argument, `None` otherwise."""
        return self if self.is_matching(name, default_namespace, **kwargs) else None

    def get_global(self):
        """Returns the global XSD component that contains the component instance."""
        if self.parent is None:
            return self
        component = self.parent
        while component is not self:
            if component.parent is None:
                return component
            component = component.parent

    def get_parent_type(self):
        """
        Returns the nearest XSD type that contains the component instance,
        or `None` if the component doesn't have an XSD type parent.
        """
        component = self.parent
        while component is not self and component is not None:
            if isinstance(component, XsdType):
                return component
            component = component.parent

    def iter_components(self, xsd_classes=None):
        """
        Creates an iterator for XSD subcomponents.

        :param xsd_classes: provide a class or a tuple of classes to iterates over only a \
        specific classes of components.
        """
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self

    def iter_ancestors(self, xsd_classes=None):
        """
        Creates an iterator for XSD ancestor components, schema excluded. Stops when the component
        is global or if the ancestor is not an instance of the specified class/classes.

        :param xsd_classes: provide a class or a tuple of classes to iterates over only a \
        specific classes of components.
        """
        ancestor = self
        while True:
            ancestor = ancestor.parent
            if ancestor is None:
                break
            elif xsd_classes is None or isinstance(ancestor, xsd_classes):
                yield ancestor
            else:
                break

    def tostring(self, indent='', max_lines=None, spaces_for_tab=4):
        """
        Returns the XML elements that declare or define the component as a string.
        """
        if self.elem is None:
            return str(None)  # Incomplete component
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

    @property
    def built(self):
        return True

    def _parse(self):
        del self.errors[:]
        self.appinfo = []
        self.documentation = []
        for child in self.elem:
            if child.tag == XSD_APPINFO:
                for key in child.attrib:
                    if key != 'source':
                        self.parse_error("wrong attribute %r for appinfo declaration." % key)
                self.appinfo.append(child)
            elif child.tag == XSD_DOCUMENTATION:
                for key in child.attrib:
                    if key not in ['source', XML_LANG]:
                        self.parse_error("wrong attribute %r for documentation declaration." % key)
                self.documentation.append(child)


class XsdType(XsdComponent):
    """Common base class for XSD types."""

    abstract = False
    block = None
    base_type = None
    derivation = None
    redefine = None
    _final = None

    @property
    def final(self):
        return self.schema.final_default if self._final is None else self._final

    @property
    def built(self):
        raise NotImplementedError

    @property
    def content_type_label(self):
        if self.is_empty():
            return 'empty'
        elif self.has_simple_content():
            return 'simple'
        elif self.is_element_only():
            return 'element-only'
        elif self.has_mixed_content():
            return 'mixed'
        else:
            return 'unknown'

    @property
    def root_type(self):
        """The root type of the type definition hierarchy. Is itself for a root type."""
        if self.base_type is None:
            return self  # Note that a XsdUnion type is always considered a root type

        try:
            if self.base_type.is_simple():
                return self.base_type.primitive_type
            else:
                return self.base_type.content_type.primitive_type
        except AttributeError:
            # The type has complex or XsdList content
            return self.base_type

    @staticmethod
    def is_simple():
        """Returns `True` if the instance is a simpleType, `False` otherwise."""
        raise NotImplementedError

    @staticmethod
    def is_complex():
        """Returns `True` if the instance is a complexType, `False` otherwise."""
        raise NotImplementedError

    @staticmethod
    def is_atomic():
        """Returns `True` if the instance is an atomic simpleType, `False` otherwise."""
        return False

    @staticmethod
    def is_datetime():
        """
        Returns `True` if the instance is a datetime/duration XSD builtin-type, `False` otherwise.
        """
        return False

    def is_empty(self):
        """Returns `True` if the instance has an empty value or content, `False` otherwise."""
        raise NotImplementedError

    def is_emptiable(self):
        """Returns `True` if the instance has an emptiable value or content, `False` otherwise."""
        raise NotImplementedError

    def has_simple_content(self):
        """
        Returns `True` if the instance is a simpleType or a complexType with simple
        content, `False` otherwise.
        """
        raise NotImplementedError

    def has_mixed_content(self):
        """
        Returns `True` if the instance is a complexType with mixed content, `False` otherwise.
        """
        raise NotImplementedError

    def is_element_only(self):
        """
        Returns `True` if the instance is a complexType with element-only content, `False` otherwise.
        """
        raise NotImplementedError

    def is_derived(self, other, derivation=None):
        raise NotImplementedError

    def is_blocked(self, xsd_element):
        """
        Returns `True` if the base type derivation is blocked, `False` otherwise.
        """
        xsd_type = xsd_element.type
        if self is xsd_type:
            return False

        block = ('%s %s' % (xsd_element.block, xsd_type.block)).strip()
        if not block:
            return False
        block = {x for x in block.split() if x in ('extension', 'restriction')}

        return any(self.is_derived(xsd_type, derivation) for derivation in block)

    def is_dynamic_consistent(self, other):
        return other.name == XSD_ANY_TYPE or self.is_derived(other) or \
            hasattr(other, 'member_types') and any(self.is_derived(mt) for mt in other.member_types)

    def is_key(self):
        return self.name == XSD_ID or self.is_derived(self.maps.types[XSD_ID])

    def text_decode(self, text):
        raise NotImplementedError


class ValidationMixin(object):
    """
    Mixin for implementing XML data validators/decoders. A derived class must implement the
    methods `iter_decode` and `iter_encode`.
    """
    def validate(self, source, use_defaults=True, namespaces=None):
        """
        Validates an XML data against the XSD schema/component instance.

        :param source: the source of XML data. For a schema can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :raises: :exc:`XMLSchemaValidationError` if XML *data* instance is not a valid.
        """
        for error in self.iter_errors(source, use_defaults=use_defaults, namespaces=namespaces):
            raise error

    def is_valid(self, source, use_defaults=True, namespaces=None):
        """
        Like :meth:`validate` except that do not raises an exception but returns ``True`` if
        the XML document is valid, ``False`` if it's invalid.

        :param source: the source of XML data. For a schema can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param use_defaults: indicates whether to use default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        """
        error = next(self.iter_errors(source, use_defaults=use_defaults, namespaces=namespaces), None)
        return error is None

    def iter_errors(self, source, use_defaults=True, namespaces=None):
        """
        Creates an iterator for the errors generated by the validation of an XML data
        against the XSD schema/component instance.

        :param source: the source of XML data. For a schema can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param use_defaults: Use schema's default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        """
        for result in self.iter_decode(source, use_defaults=use_defaults, namespaces=namespaces):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                del result

    def decode(self, source, validation='strict', **kwargs):
        """
        Decodes XML data.

        :param source: the XML data. Can be a string for an attribute or for a simple \
        type components or a dictionary for an attribute group or an ElementTree's \
        Element for other components.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_decode`.
        :return: a dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
         a simple data type object otherwise. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the decoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)

        errors = []
        for result in self.iter_decode(source, validation, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                return (result, errors) if validation == 'lax' else result
            elif validation == 'strict':
                raise result
            elif validation == 'lax':
                errors.append(result)

    def encode(self, obj, validation='strict', **kwargs):
        """
        Encodes data to XML.

        :param obj: the data to be encoded to XML.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: optional keyword arguments for the method :func:`iter_encode`.
        :return: An element tree's Element if the original data is a structured data or \
        a string if it's simple type datum. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the encoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`XMLSchemaValidationError` if the object is not encodable by the XSD \
        component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)

        errors = []
        for result in self.iter_encode(obj, validation=validation, **kwargs):
            if not isinstance(result, XMLSchemaValidationError):
                return (result, errors) if validation == 'lax' else result
            elif validation == 'strict':
                raise result
            elif validation == 'lax':
                errors.append(result)

    def iter_decode(self, source, validation='lax', **kwargs):
        """
        Creates an iterator for decoding an XML source to a Python object.

        :param source: the XML data source.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: keyword arguments for the decoder API.
        :return: Yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        raise NotImplementedError

    def iter_encode(self, obj, validation='lax', **kwargs):
        """
        Creates an iterator for Encode data to an Element.

        :param obj: The data that has to be encoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoder API.
        :return: Yields an Element, eventually preceded by a sequence of validation \
        or encoding errors.
        """
        raise NotImplementedError

    def validation_error(self, validation, error, obj=None, source=None, namespaces=None, **_kwargs):
        """
        Helper method for generating and updating validation errors. Incompatible with 'skip'
        validation mode. Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param error: an error instance or the detailed reason of failed validation.
        :param obj: the instance related to the error.
        :param source: the XML resource related to the validation process.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param _kwargs: keyword arguments of the validation process that are not used.
        """
        if not isinstance(error, XMLSchemaValidationError):
            error = XMLSchemaValidationError(self, obj, error, source, namespaces)
        else:
            if error.namespaces is None and namespaces is not None:
                error.namespaces = namespaces
            if error.source is None and source is not None:
                error.source = source
            if error.obj is None and obj is not None:
                error.obj = obj
            if error.elem is None and is_etree_element(obj):
                error.elem = obj

        if validation == 'lax':
            return error
        elif validation == 'strict':
            raise error
        elif validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")
        else:
            raise XMLSchemaValueError("unknown validation mode %r" % validation)

    def decode_error(self, validation, obj, decoder, reason=None, source=None, namespaces=None, **_kwargs):
        """
        Helper method for generating decode errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param obj: the not validated XML data.
        :param decoder: the XML data decoder.
        :param reason: the detailed reason of failed validation.
        :param source: the XML resource that contains the error.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param _kwargs: keyword arguments of the validation process that are not used.
        """
        error = XMLSchemaDecodeError(self, obj, decoder, reason, source, namespaces)
        if validation == 'lax':
            return error
        elif validation == 'strict':
            raise error
        elif validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")
        else:
            raise XMLSchemaValueError("unknown validation mode %r" % validation)

    def encode_error(self, validation, obj, encoder, reason=None, source=None, namespaces=None, **_kwargs):
        """
        Helper method for generating encode errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param obj: the not validated XML data.
        :param encoder: the XML encoder.
        :param reason: the detailed reason of failed validation.
        :param source: the XML resource that contains the error.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param _kwargs: keyword arguments of the validation process that are not used.
        """
        error = XMLSchemaEncodeError(self, obj, encoder, reason, source, namespaces)
        if validation == 'lax':
            return error
        elif validation == 'strict':
            raise error
        elif validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")
        else:
            raise XMLSchemaValueError("unknown validation mode %r" % validation)


class ParticleMixin(object):
    """
    Mixin for objects related to XSD Particle Schema Components:

      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#p
      https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/structures.html#t
    """
    min_occurs = 1
    max_occurs = 1

    @property
    def occurs(self):
        return [self.min_occurs, self.max_occurs]

    def is_emptiable(self):
        return self.min_occurs == 0

    def is_empty(self):
        return self.max_occurs == 0

    def is_single(self):
        return self.max_occurs == 1

    def is_ambiguous(self):
        return self.min_occurs != self.max_occurs

    def is_univocal(self):
        return self.min_occurs == self.max_occurs

    def is_missing(self, occurs):
        return not self.is_emptiable() if occurs == 0 else self.min_occurs > occurs

    def is_over(self, occurs):
        return self.max_occurs is not None and self.max_occurs <= occurs

    def has_occurs_restriction(self, other):
        if self.min_occurs == self.max_occurs == 0:
            return True
        elif self.min_occurs < other.min_occurs:
            return False
        elif other.max_occurs is None:
            return True
        elif self.max_occurs is None:
            return False
        else:
            return self.max_occurs <= other.max_occurs

    @property
    def effective_min_occurs(self):
        return self.min_occurs

    @property
    def effective_max_occurs(self):
        return self.max_occurs

    ###
    # Methods used by XSD components
    def parse_error(self, *args, **kwargs):
        """Helper method overridden by XsdValidator.parse_error() in XSD components."""
        raise XMLSchemaParseError(*args)

    def _parse_particle(self, elem):
        if 'minOccurs' in elem.attrib:
            try:
                min_occurs = int(elem.attrib['minOccurs'])
            except (TypeError, ValueError):
                self.parse_error("minOccurs value is not an integer value")
            else:
                if min_occurs < 0:
                    self.parse_error("minOccurs value must be a non negative integer")
                else:
                    self.min_occurs = min_occurs

        max_occurs = elem.get('maxOccurs')
        if max_occurs is None:
            if self.min_occurs > 1:
                self.parse_error("minOccurs must be lesser or equal than maxOccurs")
        elif max_occurs == 'unbounded':
            self.max_occurs = None
        else:
            try:
                max_occurs = int(max_occurs)
            except ValueError:
                self.parse_error("maxOccurs value must be a non negative integer or 'unbounded'")
            else:
                if self.min_occurs > max_occurs:
                    self.parse_error("maxOccurs must be 'unbounded' or greater than minOccurs")
                else:
                    self.max_occurs = max_occurs
