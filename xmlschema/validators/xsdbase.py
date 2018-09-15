# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
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

from ..compat import PY3, string_base_type
from ..etree import etree_tostring, is_etree_element
from ..exceptions import XMLSchemaValueError, XMLSchemaTypeError
from ..qnames import (
    local_name, get_qname, qname_to_prefixed, XSD_ANNOTATION_TAG, XSD_APPINFO_TAG,
    XSD_DOCUMENTATION_TAG, XML_LANG, XSD_ANY_TYPE
)
from .exceptions import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaDecodeError,
    XMLSchemaEncodeError, XMLSchemaChildrenValidationError
)
from .parseutils import get_xsd_component, iter_xsd_components, get_xsd_int_attribute

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
        Property that is ``True`` if schema validator has been fully parsed and built, ``False`` otherwise.
        """
        raise NotImplementedError

    @property
    def validation_attempted(self):
        """
        Property that returns the XSD validator's validation status. It can be 'full', 'partial' or 'none'.

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
        if self.errors or any([comp.errors for comp in self.iter_components()]):
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

    def parse_error(self, error, elem=None):
        """
        Helper method for registering parse errors. Does nothing if validation mode is 'skip'.
        Il validation mode is 'lax' collects the error, otherwise raise the error.

        :param error: can be a parse error or an error message.
        :param elem: the Element instance related to the error, for default uses the 'elem' \
        attribute of the validator, if it's present.
        """
        if self.validation == 'skip':
            return

        elem = elem if elem is not None else getattr(self, 'elem', None)
        if isinstance(error, XMLSchemaParseError):
            error.validator = self
            error.namespaces = getattr(self, 'namespaces', None)
            error.elem = elem
            error.source = getattr(self, 'source', None)
        elif isinstance(error, string_base_type):
            error = XMLSchemaParseError(self, str(error), elem)
        else:
            raise XMLSchemaValueError("'error' argument must be a parse error or a string, not %r." % error)

        if self.validation == 'lax':
            self.errors.append(error)
        else:
            raise error


class XsdComponent(XsdValidator):
    """
    Class for XSD components. See: https://www.w3.org/TR/xmlschema-ref/

    :param elem: ElementTree's node containing the definition.
    :param schema: the XMLSchema object that owns the definition.
    :param parent: the XSD parent, `None` means that is a global component that has the schema as parent.
    :param name: name of the component, maybe overwritten by the parse of the `elem` argument.

    :cvar admitted_tags: the set of admitted element tags for component type.
    :vartype admitted_tags: tuple or set
    :cvar qualified: for name matching, unqualified matching may be admitted only for elements and attributes..
    :vartype qualified: bool
    """
    _REGEX_SPACE = re.compile(r'\s')
    _REGEX_SPACES = re.compile(r'\s+')

    admitted_tags = ()
    qualified = True

    def __init__(self, elem, schema, parent, name=None):
        super(XsdComponent, self).__init__(schema.validation)
        if name == '':
            raise XMLSchemaValueError("'name' cannot be an empty string!")
        assert name is None or name[0] == '{' or not schema.target_namespace, \
            "name=%r argument: can be None or a qualified name of the target namespace." % name

        self.name = name
        self.parent = parent
        self.schema = schema
        self.elem = elem

    def __setattr__(self, name, value):
        if name == "elem":
            if not is_etree_element(value):
                raise XMLSchemaTypeError("%r attribute must be an Etree Element: %r" % (name, value))
            elif value.tag not in self.admitted_tags:
                raise XMLSchemaValueError(
                    "wrong XSD element %r for %r, must be one of %r." % (
                        local_name(value.tag), self,
                        [local_name(tag) for tag in self.admitted_tags]
                    )
                )
            elif hasattr(self, 'elem'):
                self._elem = self.elem  # redefinition cases
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
    def is_global(self):
        """Is `True` if the instance is a global component, `False` if it's local."""
        return self.parent is None

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
        return self.schema.target_namespace

    @property
    def default_namespace(self):
        """Property that references to schema's default namespaces."""
        return self.schema.namespaces.get('')

    @property
    def namespaces(self):
        """Property that references to schema's namespace mapping."""
        return self.schema.namespaces

    @property
    def xpath_default_namespace(self):
        try:
            return getattr(self, '_xpath_default_namespace')
        except AttributeError:
            getattr(self.schema, '_xpath_default_namespace', None)

    @property
    def maps(self):
        """Property that references to schema's global maps."""
        return self.schema.maps

    def __repr__(self):
        if self.name is None:
            return '<%s at %#x>' % (self.__class__.__name__, id(self))
        else:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)

    def _parse(self):
        del self.errors[:]
        try:
            if self.elem[0].tag == XSD_ANNOTATION_TAG:
                self.annotation = XsdAnnotation(self.elem[0], self.schema, self)
            else:
                self.annotation = None
        except (TypeError, IndexError):
            self.annotation = None

    def _parse_component(self, elem, required=True, strict=True):
        try:
            return get_xsd_component(elem, required, strict)
        except XMLSchemaValueError as err:
            self.parse_error(str(err), elem)

    def _iterparse_components(self, elem, start=0):
        try:
            for obj in iter_xsd_components(elem, start):
                yield obj
        except XMLSchemaValueError as err:
            self.parse_error(str(err), elem)

    def _parse_properties(self, *properties):
        for name in properties:
            try:
                getattr(self, name)
            except (ValueError, TypeError) as err:
                self.parse_error(str(err))

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

    def is_matching(self, name, default_namespace=None):
        """
        Returns `True` if the component name is matching the name provided as argument, `False` otherwise.

        :param name: a local or fully-qualified name.
        :param default_namespace: used if it's not None and not empty for completing the name \
        argument in case it's a local name.
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

    def match(self, name, default_namespace=None):
        """Returns the component if its name is matching the name provided as argument, `None` otherwise."""
        return self if self.is_matching(name, default_namespace) else None

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
    Class for XSD 'annotation' definitions.

    <annotation
      id = ID
      {any attributes with non-schema namespace . . .}>
      Content: (appinfo | documentation)*
    </annotation>

    <appinfo
      source = anyURI
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </appinfo>

    <documentation
      source = anyURI
      xml:lang = language
      {any attributes with non-schema namespace . . .}>
      Content: ({any})*
    </documentation>
    """
    admitted_tags = {XSD_ANNOTATION_TAG}

    @property
    def built(self):
        return True

    def _parse(self):
        del self.errors[:]
        self.appinfo = []
        self.documentation = []
        for child in self.elem:
            if child.tag == XSD_APPINFO_TAG:
                for key in child.attrib:
                    if key != 'source':
                        self.parse_error("wrong attribute %r for appinfo declaration." % key)
                self.appinfo.append(child)
            elif child.tag == XSD_DOCUMENTATION_TAG:
                for key in child.attrib:
                    if key not in ['source', XML_LANG]:
                        self.parse_error("wrong attribute %r for documentation declaration." % key)
                self.documentation.append(child)


class XsdType(XsdComponent):

    base_type = None
    derivation = None

    @property
    def built(self):
        raise NotImplementedError

    @staticmethod
    def is_simple():
        raise NotImplementedError

    @staticmethod
    def is_complex():
        raise NotImplementedError

    @staticmethod
    def is_atomic():
        return None

    def is_empty(self):
        raise NotImplementedError

    def is_emptiable(self):
        raise NotImplementedError

    def has_simple_content(self):
        raise NotImplementedError

    def has_mixed_content(self):
        raise NotImplementedError

    def is_element_only(self):
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

    def is_derived(self, other, derivation=None):
        if other.name == XSD_ANY_TYPE or self.base_type == other:
            return True if derivation is None else derivation == self.derivation
        elif self.base_type is not None:
            return self.base_type.is_derived(other, derivation)
        else:
            return False

    def is_subtype(self, qname):
        if qname == XSD_ANY_TYPE or self.name == qname:
            return True
        elif self.base_type is not None:
            return self.base_type.is_subtype(qname)
        else:
            return False


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

    def is_valid(self, source, use_defaults=True):
        """
        Like :meth:`validate` except that do not raises an exception but returns ``True`` if
        the XML document is valid, ``False`` if it's invalid.

        :param source: the source of XML data. For a schema can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param use_defaults: indicates whether to use default values for filling missing data.
        """
        error = next(self.iter_errors(source, use_defaults=use_defaults), None)
        return error is None

    def iter_errors(self, source, path=None, use_defaults=True, namespaces=None):
        """
        Creates an iterator for the errors generated by the validation of an XML data
        against the XSD schema/component instance.

        :param source: the source of XML data. For a schema can be a path \
        to a file or an URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param path: is an optional XPath expression that defines the parts of the document \
        that have to be validated. The XPath expression considers the schema as the root element \
        with global elements as its children.
        :param use_defaults: Use schema's default values for filling missing data.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        """
        for result in self.iter_decode(source, path, use_defaults=use_defaults, namespaces=namespaces):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                del result

    def decode(self, source, *args, **kwargs):
        """
        Decodes XML data using the XSD schema/component.

        :param source: the source of XML data. For a schema can be a path to a file or an \
        URI of a resource or an opened file-like object or an Element Tree \
        instance or a string containing XML data. For other XSD components can be a string \
        for an attribute or a simple type validators, or an ElementTree's Element otherwise.
        :param args: arguments that maybe passed to :func:`XMLSchema.iter_decode`.
        :param kwargs: keyword arguments from the ones included in the optional \
        arguments of the :func:`XMLSchema.iter_decode`.
        :return: a dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
         a simple data type object otherwise. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the decoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        validation = kwargs.pop('validation', 'strict')
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)
        errors = []

        for result in self.iter_decode(source, validation=validation, *args, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                if validation == 'strict':
                    raise result
                elif validation == 'lax':
                    errors.append(result)
            elif validation == 'lax':
                return result, errors
            else:
                return result
    to_dict = decode

    def encode(self, obj, *args, **kwargs):
        """
        Encodes data to XML using the XSD schema/component.

        :param obj: the data to be encoded to XML.
        :param args: arguments that maybe passed to :func:`XMLSchema.iter_encode`.
        :param kwargs: keyword arguments from the ones included in the optional \
        arguments of the :func:`XMLSchema.iter_encode`.
        :return: An element tree's Element if the original data is a structured data or \
        a string if it's simple type datum. If *validation* argument is 'lax' a 2-items \
        tuple is returned, where the first item is the encoded object and the second item \
        is a list containing the errors.
        :raises: :exc:`XMLSchemaValidationError` if the object is not encodable by \
        the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
        """
        validation = kwargs.pop('validation', 'strict')
        if validation not in XSD_VALIDATION_MODES:
            raise XMLSchemaValueError("validation argument can be 'strict', 'lax' or 'skip': %r" % validation)
        errors = []

        for result in self.iter_encode(obj, validation=validation, *args, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                if validation == 'strict':
                    raise result
                elif validation == 'lax':
                    errors.append(result)
            elif validation == 'lax':
                return result, errors
            else:
                return result
    to_etree = encode

    def iter_decode(self, source, validation='lax', *args, **kwargs):
        """
        Creates an iterator for decoding an XML source to a Python object.

        :param source: the XML data source. The argument type depends by implementation.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param args: additional arguments for the decoder API.
        :param kwargs: keyword arguments for the decoder API.
        :return: Yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        raise NotImplementedError

    def iter_encode(self, obj, validation='lax', *args, **kwargs):
        """
        Creates an iterator for Encode data to an Element.

        :param obj: The data that has to be encoded.
        :param validation: The validation mode. Can be 'lax', 'strict' or 'skip'.
        :param args: additional arguments for the encoder API.
        :param kwargs: keyword arguments for the encoder API.
        :return: Yields an Element, eventually preceded by a sequence of validation \
        or encoding errors.
        """
        raise NotImplementedError

    def validation_error(self, validation, error, obj=None, source=None, namespaces=None, **kwargs):
        """
        Helper method for generating and updating validation errors. Incompatible with 'skip'
        validation mode. Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param error: an error instance or the detailed reason of failed validation.
        :param obj: the instance related to the error.
        :param source: the XML resource related to the validation process.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param kwargs: other keyword arguments of the validation process.
        """
        if not isinstance(error, XMLSchemaValidationError):
            error = XMLSchemaValidationError(self, obj, error, source, namespaces)
        else:
            if error.obj is None and obj is not None:
                error.obj = obj
            if error.namespaces is None and namespaces is not None:
                error.namespaces = namespaces
            if error.elem is None and is_etree_element(obj):
                error.elem = obj
            if error.source is None and source is not None:
                error.source = source

        if validation == 'lax':
            return error
        elif validation == 'strict':
            raise error
        elif validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")
        else:
            raise XMLSchemaValueError("unknown validation mode %r" % validation)

    def decode_error(self, validation, obj, decoder, reason=None, source=None, namespaces=None, **kwargs):
        """
        Helper method for generating decode errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param obj: the not validated XML data.
        :param decoder: the XML data decoder.
        :param reason: the detailed reason of failed validation.
        :param source: the XML resource that contains the error.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param kwargs: other keyword arguments of the validation process.
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

    def encode_error(self, validation, obj, encoder, reason=None, source=None, namespaces=None, **kwargs):
        """
        Helper method for generating encode errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raises the error.

        :param validation: an error-compatible validation mode: can be 'lax' or 'strict'.
        :param obj: the not validated XML data.
        :param encoder: the XML encoder.
        :param reason: the detailed reason of failed validation.
        :param source: the XML resource that contains the error.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param kwargs: other keyword arguments of the validation process.
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
    def parse_error(self, *args, **kwargs):
        # Implemented by XsdValidator
        raise NotImplementedError

    def _parse_particle(self, elem):
        try:
            self.min_occurs = get_xsd_int_attribute(elem, 'minOccurs', default=1, minimum=0)
        except (TypeError, ValueError):
            self.parse_error("minOccurs value must be a non negative integer")
            self.min_occurs = 1

        try:
            max_occurs = get_xsd_int_attribute(elem, 'maxOccurs', default=1, minimum=0)
        except (TypeError, ValueError):
            if elem.get('maxOccurs') == 'unbounded':
                max_occurs = None
            else:
                self.parse_error("maxOccurs value must be a non negative integer or 'unbounded'")
                max_occurs = 1

        if max_occurs is not None and self.min_occurs > max_occurs:
            self.parse_error("maxOccurs must be 'unbounded' or greater than minOccurs:")
        self.max_occurs = max_occurs
        self.occurs = [self.min_occurs, max_occurs]

    def is_emptiable(self):
        return self.min_occurs == 0

    is_optional = is_emptiable

    def is_single(self):
        return self.max_occurs == 1

    def is_restriction(self, other):
        if self.min_occurs < other.min_occurs:
            return False
        if other.max_occurs is not None:
            if self.max_occurs is None:
                return False
            elif self.max_occurs > other.max_occurs:
                return False
        return True

    def is_missing(self, occurs):
        return not self.is_emptiable() if occurs == 0 else self.min_occurs > occurs

    def is_over(self, occurs):
        return self.max_occurs is not None and self.max_occurs <= occurs

    def children_validation_error(self, validation, elem, index, particle, occurs=0, expected=None,
                                  source=None, namespaces=None, **kwargs):
        """
        Helper method for generating model validation errors. Incompatible with 'skip' validation mode.
        Il validation mode is 'lax' returns the error, otherwise raise the error.

        :param validation: the validation mode. Can be 'lax' or 'strict'.
        :param elem: the instance Element.
        :param index: the child index.
        :param particle: the XSD component (subgroup or element) associated to the child.
        :param occurs: the child tag occurs.
        :param expected: the expected element tags/object names.
        :param source: the XML resource related to the validation process.
        :param namespaces: is an optional mapping from namespace prefix to URI.
        """
        if validation == 'skip':
            raise XMLSchemaValueError("validation mode 'skip' incompatible with error generation.")

        error = XMLSchemaChildrenValidationError(self, elem, index, particle, occurs, expected, source, namespaces)
        if validation == 'strict':
            raise error
        else:
            return error
