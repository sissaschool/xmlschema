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
from decimal import Decimal
from typing import Optional
from elementpath import XPath2Parser, ElementPathError, XPathContext
from elementpath.datatypes import AbstractDateTime, Duration, AbstractBinary

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..names import XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE, XSD_ALTERNATIVE, \
    XSD_ELEMENT, XSD_ANY_TYPE, XSD_UNIQUE, XSD_KEY, XSD_KEYREF, XSI_NIL, \
    XSI_TYPE, XSD_ERROR, XSD_NOTATION_TYPE
from ..etree import etree_element
from ..helpers import get_qname, get_namespace, etree_iter_location_hints
from ..converters import ElementData, XMLSchemaConverter
from ..xpath import XMLSchemaProxy, ElementPathMixin

from .exceptions import XMLSchemaValidationError, XMLSchemaTypeTableWarning
from .helpers import get_xsd_derivation_attribute, raw_xml_encode, strictly_equal
from .xsdbase import XSD_TYPE_DERIVATIONS, XSD_ELEMENT_DERIVATIONS, \
    XsdComponent, XsdType, ValidationMixin
from .particles import ParticleMixin
from .models import OccursCounter
from .identities import XsdKeyref
from .wildcards import XsdAnyElement


class XsdElement(XsdComponent, ValidationMixin, ParticleMixin, ElementPathMixin):
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
    abstract = False
    nillable = False
    qualified = False
    form = None
    default = None
    fixed = None
    substitution_group = None

    alternatives = ()
    inheritable = ()

    _ADMITTED_TAGS = {XSD_ELEMENT}
    _block = None
    _final = None
    _head_type = None

    def __init__(self, elem, schema, parent):
        super(XsdElement, self).__init__(elem, schema, parent)
        ElementPathMixin.__init__(self)

    def __repr__(self):
        return '%s(%s=%r, occurs=%r)' % (
            self.__class__.__name__,
            'name' if self.ref is None else 'ref',
            self.prefixed_name,
            self.occurs
        )

    def __setattr__(self, name: str, value: Optional[XsdType]):
        if name == "type":
            try:
                self.attributes = value.attributes
            except AttributeError:
                self.attributes = self.schema.create_empty_attribute_group(self)
        super(XsdElement, self).__setattr__(name, value)

    def __iter__(self):
        if self.type.has_complex_content():
            yield from self.type.content.iter_elements()

    def _parse(self):
        XsdComponent._parse(self)
        self._parse_particle(self.elem)
        self._parse_attributes()

        if self.ref is None:
            self._parse_type()
            self._parse_constraints()

            if self.parent is None and 'substitutionGroup' in self.elem.attrib:
                self._parse_substitution_group(self.elem.attrib['substitutionGroup'])

    def _parse_attributes(self):
        attrib = self.elem.attrib
        if self._parse_reference():
            try:
                xsd_element: XsdElement = self.maps.lookup_element(self.name)
            except KeyError:
                self.type = self.any_type
                self.parse_error('unknown element %r' % self.name)
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

            for attr_name in {'type', 'nillable', 'default', 'fixed', 'form',
                              'block', 'abstract', 'final', 'substitutionGroup'}:
                if attr_name in attrib:
                    msg = "attribute {!r} is not allowed when element reference is used"
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
                self.parse_error("local scope elements cannot have abstract attribute")
            if attrib['abstract'].strip() in {'true', '1'}:
                self.abstract = True

        if 'block' in attrib:
            try:
                self._block = get_xsd_derivation_attribute(
                    self.elem, 'block', XSD_ELEMENT_DERIVATIONS
                )
            except ValueError as err:
                self.parse_error(err)

        if 'nillable' in attrib and attrib['nillable'].strip() in {'true', '1'}:
            self.nillable = True

        if self.parent is None:
            if 'final' in attrib:
                try:
                    self._final = get_xsd_derivation_attribute(
                        self.elem, 'final', XSD_TYPE_DERIVATIONS
                    )
                except ValueError as err:
                    self.parse_error(err)

            for attr_name in {'ref', 'form', 'minOccurs', 'maxOccurs'}:
                if attr_name in attrib:
                    msg = "attribute {!r} is not allowed in a global element declaration"
                    self.parse_error(msg.format(attr_name))
        else:
            for attr_name in {'final', 'substitutionGroup'}:
                if attr_name in attrib:
                    msg = "attribute {!r} not allowed in a local element declaration"
                    self.parse_error(msg.format(attr_name))

    def _parse_type(self):
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
                        self.parse_error('unknown type {!r}'.format(type_name))
                        self.type = self.any_type
            finally:
                child = self._parse_child_component(self.elem, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    self.parse_error("the attribute 'type' and a {} local declaration "
                                     "are mutually exclusive".format(child.tag.split('}')[-1]))
        else:
            child = self._parse_child_component(self.elem, strict=False)
            if child is None:
                self.type = self.any_type
            elif child.tag == XSD_COMPLEX_TYPE:
                self.type = self.schema.BUILDERS.complex_type_class(child, self.schema, self)
            elif child.tag == XSD_SIMPLE_TYPE:
                self.type = self.schema.BUILDERS.simple_type_factory(child, self.schema, self)
            else:
                self.type = self.any_type

    def _parse_constraints(self):
        # Value constraints
        if 'default' in self.elem.attrib:
            self.default = self.elem.attrib['default']
            if 'fixed' in self.elem.attrib:
                self.parse_error("'default' and 'fixed' attributes are mutually exclusive")

            if not self.type.is_valid(self.default):
                msg = "'default' value {!r} is not compatible with element's type"
                self.parse_error(msg.format(self.default))
                self.default = None
            elif self.xsd_version == '1.0' and self.type.is_key():
                self.parse_error("xs:ID or a type derived from xs:ID "
                                 "cannot have a default value")

        elif 'fixed' in self.elem.attrib:
            self.fixed = self.elem.attrib['fixed']
            if not self.type.is_valid(self.fixed):
                msg = "'fixed' value {!r} is not compatible with element's type"
                self.parse_error(msg.format(self.fixed))
                self.fixed = None
            elif self.xsd_version == '1.0' and self.type.is_key():
                self.parse_error("xs:ID or a type derived from xs:ID "
                                 "cannot have a fixed value")

        # Identity constraints
        self.identities = {}
        for child in self.elem:
            if child.tag == XSD_UNIQUE:
                constraint = self.schema.BUILDERS.unique_class(child, self.schema, self)
            elif child.tag == XSD_KEY:
                constraint = self.schema.BUILDERS.key_class(child, self.schema, self)
            elif child.tag == XSD_KEYREF:
                constraint = self.schema.BUILDERS.keyref_class(child, self.schema, self)
            else:
                # Invalid tags already caught by validation against the meta-schema
                continue

            if constraint.ref:
                if constraint.name in self.identities:
                    self.parse_error("duplicated identity constraint %r:" % constraint.name, child)
                self.identities[constraint.name] = constraint
                continue

            try:
                if child != self.maps.identities[constraint.name]:
                    self.parse_error("duplicated identity constraint %r:" % constraint.name, child)
            except KeyError:
                self.maps.identities[constraint.name] = constraint
            finally:
                self.identities[constraint.name] = constraint

    def _parse_substitution_group(self, substitution_group):
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
            self.parse_error("unknown substitutionGroup %r" % substitution_group)
            return
        else:
            if isinstance(head_element, tuple):
                self.parse_error("circularity found for substitutionGroup %r" % substitution_group)
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
            self.parse_error("%r type is not of the same or a derivation "
                             "of the head element %r type." % (self, head_element))
        elif final == '#all' or 'extension' in final and 'restriction' in final:
            self.parse_error("head element %r can't be substituted by an element "
                             "that has a derivation of its type" % head_element)
        elif 'extension' in final and self.type.is_derived(head_element.type, 'extension'):
            self.parse_error("head element %r can't be substituted by an element "
                             "that has an extension of its type" % head_element)
        elif 'restriction' in final and self.type.is_derived(head_element.type, 'restriction'):
            self.parse_error("head element %r can't be substituted by an element "
                             "that has a restriction of its type" % head_element)

        try:
            self.maps.substitution_groups[substitution_group_qname].add(self)
        except KeyError:
            self.maps.substitution_groups[substitution_group_qname] = {self}
        finally:
            self.substitution_group = substitution_group_qname

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)

    @property
    def built(self):
        return (self.type.parent is None or self.type.built) and \
            all(c.built for c in self.identities.values())

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif self.type.validation_attempted == 'partial':
            return 'partial'
        elif any(c.validation_attempted == 'partial' for c in self.identities.values()):
            return 'partial'
        else:
            return 'none'

    @property
    def scope(self):
        """The scope of the element declaration that can be 'global' or 'local'."""
        return 'global' if self.parent is None else 'local'

    @property
    def value_constraint(self):
        """The fixed or the default value if either is defined, `None` otherwise."""
        return self.fixed if self.fixed is not None else self.default

    @property
    def final(self):
        if self.ref is not None:
            return self.ref.final
        elif self._final is not None:
            return self._final
        return self.schema.final_default

    @property
    def block(self):
        if self.ref is not None:
            return self.ref.block
        elif self._block is not None:
            return self._block
        return self.schema.block_default

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.target_namespace, name)]
        return self.type.attributes[name]

    def get_type(self, elem, inherited=None):
        return self._head_type or self.type

    def get_attributes(self, xsd_type):
        try:
            return xsd_type.attributes
        except AttributeError:
            if xsd_type is self.type:
                return self.attributes
            else:
                return self.schema.create_empty_attribute_group(self)

    def get_path(self, ancestor=None, reverse=False):
        """
        Returns the XPath expression of the element. The path is relative to the schema instance
        in which the element is contained or is relative to a specific ancestor passed as argument.
        In the latter case returns `None` if the argument is not an ancestor.

        :param ancestor: optional XSD component of the same schema, that maybe \
        an ancestor of the element.
        :param reverse: if set to `True` returns the reverse path, from the element to ancestor.
        """
        path = []
        xsd_component = self
        while xsd_component is not None:
            if xsd_component is ancestor:
                return '/'.join(reversed(path)) or '.'
            elif hasattr(xsd_component, 'tag'):
                path.append('..' if reverse else xsd_component.name)
            xsd_component = xsd_component.parent
        else:
            if ancestor is None:
                return '/'.join(reversed(path)) or '.'

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None:
            yield self
            yield from self.identities.values()
        else:
            if isinstance(self, xsd_classes):
                yield self
            for obj in self.identities.values():
                if isinstance(obj, xsd_classes):
                    yield obj

        if self.ref is None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def iter_substitutes(self):
        if self.parent is None or self.ref is not None:
            for xsd_element in self.maps.substitution_groups.get(self.name, ()):
                if not xsd_element.abstract:
                    yield xsd_element
                for e in xsd_element.iter_substitutes():
                    if not e.abstract:
                        yield e

    def data_value(self, elem):
        """Returns the decoded data value of the provided element as XPath fn:data()."""
        text = elem.text
        if text is None:
            text = self.fixed if self.fixed is not None else self.default
            if text is None:
                return
        return self.type.text_decode(text)

    def check_dynamic_context(self, elem, **kwargs):
        try:
            locations = kwargs['locations']
        except KeyError:
            return

        for ns, url in etree_iter_location_hints(elem):
            if ns not in locations:
                locations[ns] = url
            elif locations[ns] is None:
                reason = "schemaLocation declaration after namespace start"
                raise XMLSchemaValidationError(self, elem, reason)

            if ns == self.target_namespace:
                schema = self.schema.include_schema(url, self.schema.base_url)
            else:
                schema = self.schema.import_namespace(ns, url, self.schema.base_url)

            if not schema.built:
                reason = "dynamic loaded schema change the assessment"
                raise XMLSchemaValidationError(self, elem, reason)

        if elem.attrib:
            for name in elem.attrib:
                if name[0] == '{':
                    ns = get_namespace(name)
                    if ns not in locations:
                        locations[ns] = None

        if elem.tag[0] == '{':
            ns = get_namespace(elem.tag)
            if ns not in locations:
                locations[ns] = None

    def start_identities(self, identities):
        """
        Start tracking of XSD element's identities.

        :param identities: a dictionary containing the identities counters.
        """
        for constraint in self.identities.values():
            try:
                identities[constraint].clear()
            except KeyError:
                identities[constraint] = constraint.get_counter()

    def stop_identities(self, identities):
        """
        Stop tracking of XSD element's identities.

        :param identities: a dictionary containing the identities counters.
        """
        for identity in self.identities.values():
            try:
                identities[identity].enabled = False
            except KeyError:
                identities[identity] = identity.get_counter(enabled=False)

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Creates an iterator for decoding an Element instance.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        if self.abstract:
            reason = "cannot use an abstract element for validation"
            yield self.validation_error(validation, reason, elem, **kwargs)

        try:
            namespaces = kwargs['namespaces']
        except KeyError:
            namespaces = None

        try:
            level = kwargs['level']
        except KeyError:
            level = kwargs['level'] = 0

        try:
            identities = kwargs['identities']
        except KeyError:
            identities = kwargs['identities'] = {}

        self.start_identities(identities)

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)
        else:
            if not isinstance(converter, XMLSchemaConverter) and converter is not None:
                converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        try:
            pass  # self.check_dynamic_context(elem, **kwargs) TODO: dynamic schema load
        except XMLSchemaValidationError as err:
            yield self.validation_error(validation, err, elem, **kwargs)

        inherited = kwargs.get('inherited')
        value = content = attributes = None
        nilled = False

        # Get the instance effective type
        xsd_type = self.get_type(elem, inherited)
        if XSI_TYPE in elem.attrib:
            type_name = elem.attrib[XSI_TYPE].strip()
            try:
                xsd_type = self.maps.get_instance_type(type_name, xsd_type, namespaces)
            except (KeyError, TypeError) as err:
                yield self.validation_error(validation, err, elem, **kwargs)

            if xsd_type.is_blocked(self):
                reason = "usage of %r is blocked" % xsd_type
                yield self.validation_error(validation, reason, elem, **kwargs)

        if xsd_type.abstract:
            yield self.validation_error(validation, "%r is abstract", elem, **kwargs)
        if xsd_type.is_complex() and self.xsd_version == '1.1':
            kwargs['id_list'] = []  # Track XSD 1.1 multiple xs:ID attributes/children

        content_decoder = xsd_type.content if xsd_type.is_complex() else xsd_type

        # Decode attributes
        attribute_group = self.get_attributes(xsd_type)
        for result in attribute_group.iter_decode(elem.attrib, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield self.validation_error(validation, result, elem, **kwargs)
            else:
                attributes = result

        if self.inheritable and any(name in self.inheritable for name in elem.attrib):
            if inherited:
                inherited = inherited.copy()
                inherited.update((k, v) for k, v in elem.attrib.items() if k in self.inheritable)
            else:
                inherited = {k: v for k, v in elem.attrib.items() if k in self.inheritable}
            kwargs['inherited'] = inherited

        # Checks the xsi:nil attribute of the instance
        if XSI_NIL in elem.attrib:
            xsi_nil = elem.attrib[XSI_NIL].strip()
            if not self.nillable:
                reason = "element is not nillable."
                yield self.validation_error(validation, reason, elem, **kwargs)
            elif xsi_nil not in {'0', '1', 'false', 'true'}:
                reason = "xsi:nil attribute must have a boolean value."
                yield self.validation_error(validation, reason, elem, **kwargs)
            elif xsi_nil in ('0', 'false'):
                pass
            elif self.fixed is not None:
                reason = "xsi:nil='true' but the element has a fixed value."
                yield self.validation_error(validation, reason, elem, **kwargs)
            elif elem.text is not None or len(elem):
                reason = "xsi:nil='true' but the element is not empty."
                yield self.validation_error(validation, reason, elem, **kwargs)
            else:
                nilled = True

        if xsd_type.is_empty() and elem.text:
            reason = "character data is not allowed because content is empty"
            yield self.validation_error(validation, reason, elem, **kwargs)

        if nilled:
            pass
        elif xsd_type.model_group is not None:
            for assertion in xsd_type.assertions:
                for error in assertion(elem, **kwargs):
                    yield self.validation_error(validation, error, **kwargs)

            for result in content_decoder.iter_decode(elem, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self.validation_error(validation, result, elem, **kwargs)
                else:
                    content = result

            if len(content) == 1 and content[0][0] == 1:
                value, content = content[0][1], None

            if self.fixed is not None and \
                    (len(elem) > 0 or value is not None and self.fixed != value):
                reason = "must have the fixed value %r" % self.fixed
                yield self.validation_error(validation, reason, elem, **kwargs)

        else:
            if len(elem):
                reason = "a simple content element can't have child elements."
                yield self.validation_error(validation, reason, elem, **kwargs)

            text = elem.text
            if self.fixed is not None:
                if text is None:
                    text = self.fixed
                elif text == self.fixed:
                    pass
                elif not strictly_equal(xsd_type.text_decode(text),
                                        xsd_type.text_decode(self.fixed)):
                    reason = "must have the fixed value %r" % self.fixed
                    yield self.validation_error(validation, reason, elem, **kwargs)

            elif not text and self.default is not None and kwargs.get('use_defaults'):
                text = self.default

            if xsd_type.is_complex():
                for assertion in xsd_type.assertions:
                    for error in assertion(elem, value=text, **kwargs):
                        yield self.validation_error(validation, error, **kwargs)

                if text and content_decoder.is_list():
                    value = text.split()
                else:
                    value = text

            elif xsd_type.is_notation():
                if xsd_type.name == XSD_NOTATION_TYPE:
                    msg = "cannot validate against xs:NOTATION directly, " \
                          "only against a subtype with an enumeration facet"
                    yield self.validation_error(validation, msg, text, **kwargs)
                elif not xsd_type.enumeration:
                    msg = "missing enumeration facet in xs:NOTATION subtype"
                    yield self.validation_error(validation, msg, text, **kwargs)

            if text is None:
                for result in content_decoder.iter_decode('', validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                        if 'filler' in kwargs:
                            value = kwargs['filler'](self)
            else:
                for result in content_decoder.iter_decode(text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                    elif result is None and 'filler' in kwargs:
                        value = kwargs['filler'](self)
                    else:
                        value = result

            if isinstance(value, (int, float, list)) or value is None:
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
                    value = elem.text
            elif isinstance(value, AbstractBinary):
                if not kwargs.get('binary_types'):
                    value = elem.text

        if converter is not None:
            element_data = ElementData(elem.tag, value, content, attributes)
            yield converter.element_decode(element_data, self, xsd_type, level)
        elif not level:
            yield ElementData(elem.tag, value, None, attributes)

        if content is not None:
            del content

        # Collects fields values for identities that refer to this element.
        for identity, counter in identities.items():
            if not counter.enabled:
                continue
            elif self in identity.elements:
                xsd_element = self
            elif self.ref in identity.elements:
                xsd_element = self.ref
            else:
                continue

            try:
                if xsd_type is self.type:
                    xsd_fields = identity.elements[xsd_element]
                    if xsd_fields is None:
                        xsd_fields = identity.get_fields(xsd_element)
                        identity.elements[xsd_element] = xsd_fields
                else:
                    xsd_element = self.copy()
                    xsd_element.type = xsd_type
                    xsd_fields = identity.get_fields(xsd_element)

                if all(x is None for x in xsd_fields):
                    continue
                fields = identity.get_fields(elem, namespaces, decoders=xsd_fields)
            except (XMLSchemaValueError, XMLSchemaTypeError) as err:
                yield self.validation_error(validation, err, elem, **kwargs)
            else:
                if any(x is not None for x in fields) or nilled:
                    try:
                        counter.increase(fields)
                    except ValueError as err:
                        yield self.validation_error(validation, err, elem, **kwargs)

        # Disable collect for out of scope identities and check key references
        if 'max_depth' not in kwargs:
            for identity in self.identities.values():
                counter = identities[identity]
                counter.enabled = False
                if isinstance(identity, XsdKeyref):
                    for err in counter.iter_errors(identities):
                        yield self.validation_error(validation, err, elem, **kwargs)
        elif level:
            self.stop_identities(identities)

    def iter_encode(self, obj, validation='lax', **kwargs):
        """
        Creates an iterator for encoding data to an Element.

        :param obj: the data that has to be encoded.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields an Element, eventually preceded by a sequence of \
        validation or encoding errors.
        """
        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)
        else:
            if not isinstance(converter, XMLSchemaConverter):
                converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        try:
            level = kwargs['level']
        except KeyError:
            level = 0

        element_data = converter.element_encode(obj, self, level)
        errors = []
        tag = element_data.tag
        text = None
        children = element_data.content
        attributes = ()

        xsd_type = self.get_type(element_data)
        if XSI_TYPE in element_data.attributes:
            type_name = element_data.attributes[XSI_TYPE].strip()
            try:
                xsd_type = self.maps.get_instance_type(type_name, xsd_type, converter)
            except (KeyError, TypeError) as err:
                errors.append(err)
            else:
                default_namespace = converter.get('')
                if default_namespace and xsd_type.attributes:
                    # Adjust attributes mapped into default namespace

                    ns_part = '{%s}' % default_namespace
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
            elif xsi_nil not in {'0', '1', 'true', 'false'}:
                errors.append("xsi:nil attribute must has a boolean value.")
            elif xsi_nil in ('0', 'false'):
                pass
            elif self.fixed is not None:
                errors.append("xsi:nil='true' but the element has a fixed value.")
            elif element_data.text is not None or element_data.content:
                errors.append("xsi:nil='true' but the element is not empty.")
            else:
                elem = converter.etree_element(element_data.tag, attrib=attributes, level=level)
                for e in errors:
                    yield self.validation_error(validation, e, elem, **kwargs)
                yield elem
                return

        if xsd_type.is_simple():
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
            elif self.default is not None and kwargs.get('use_defaults'):
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
            elif self.default is not None and kwargs.get('use_defaults'):
                text = self.default

        else:
            for result in xsd_type.content.iter_encode(element_data, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    errors.append(result)
                elif result:
                    text, children = result

        elem = converter.etree_element(tag, text, children, attributes, level)

        if errors:
            for e in errors:
                yield self.validation_error(validation, e, elem, **kwargs)
        yield elem
        del element_data

    def is_matching(self, name, default_namespace=None, group=None):
        if default_namespace and name[0] != '{':
            qname = '{%s}%s' % (default_namespace, name)
            if name == self.name or qname == self.name:
                return True
            return any(name == e.name or qname == e.name for e in self.iter_substitutes())
        elif name == self.name:
            return True
        else:
            return any(name == e.name for e in self.iter_substitutes())

    def match(self, name, default_namespace=None, **kwargs):
        if default_namespace and name[0] != '{':
            qname = '{%s}%s' % (default_namespace, name)
            if name == self.name or qname == self.name:
                return self

            for xsd_element in self.iter_substitutes():
                if name == xsd_element.name or qname == xsd_element.name:
                    return xsd_element

        elif name == self.name:
            return self
        else:
            for xsd_element in self.iter_substitutes():
                if name == xsd_element.name:
                    return xsd_element

    def is_restriction(self, other, check_occurs=True):
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
                    # An UPA violation case. Base is the head element, it's not
                    # abstract and has non deterministic occurs: this is less
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
            counter = OccursCounter()
            for e in other.iter_model():
                if not isinstance(e, (XsdElement, XsdAnyElement)):
                    return False
                elif not self.is_restriction(e, check_group_items_occurs):
                    continue
                counter += e
                counter *= other
                if self.has_occurs_restriction(counter):
                    return True
                counter.reset()
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

    def is_overlap(self, other):
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

    def is_consistent(self, other):
        """
        Element Declarations Consistent check between two element particles.

        Ref: https://www.w3.org/TR/xmlschema-1/#cos-element-consistent

        :returns: `True` if there is no inconsistency between the particles, `False` otherwise,
        """
        return self.name != other.name or self.type is other.type

    def is_single(self):
        try:
            if self.max_occurs != 1:
                return False
            elif self.parent.max_occurs == 1:
                return True
            else:
                return self.parent.model != 'choice' and len(self.parent) > 1
        except AttributeError:
            return True


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
    _target_namespace = None

    def _parse(self):
        XsdComponent._parse(self)
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
            self.inheritable = {k: v for k, v in self.attributes.items() if v.inheritable}

    def _parse_alternatives(self):
        alternatives = []
        has_test = True
        for child in self.elem:
            if child.tag == XSD_ALTERNATIVE:
                alternatives.append(XsdAlternative(child, self.schema, self))
                if not has_test:
                    self.parse_error("test attribute missing on non-final alternative")
                has_test = 'test' in child.attrib

        if alternatives:
            self.alternatives = alternatives

    @property
    def built(self):
        return (self.type.parent is None or self.type.built) and \
            all(c.built for c in self.identities.values()) and \
            all(a.built for a in self.alternatives)

    @property
    def target_namespace(self):
        if self._target_namespace is not None:
            return self._target_namespace
        elif self.ref is not None:
            return self.ref.target_namespace
        else:
            return self.schema.target_namespace

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None:
            yield self
            yield from self.identities.values()
        else:
            if isinstance(self, xsd_classes):
                yield self
            for obj in self.identities.values():
                if isinstance(obj, xsd_classes):
                    yield obj

        for alt in self.alternatives:
            yield from alt.iter_components(xsd_classes)

        if self.ref is None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def iter_substitutes(self):
        if self.parent is None or self.ref is not None:
            for xsd_element in self.maps.substitution_groups.get(self.name, ()):
                yield xsd_element
                yield from xsd_element.iter_substitutes()

    def get_type(self, elem, inherited=None):
        if not self.alternatives:
            return self._head_type or self.type

        if isinstance(elem, ElementData):
            if elem.attributes:
                attrib = {k: raw_xml_encode(v) for k, v in elem.attributes.items()}
                elem = etree_element(elem.tag, attrib=attrib)
            else:
                elem = etree_element(elem.tag)

        if inherited:
            dummy = etree_element('_dummy_element', attrib=inherited)
            dummy.attrib.update(elem.attrib)

            for alt in filter(lambda x: x.type is not None, self.alternatives):
                if alt.token is None or alt.test(elem) or alt.test(dummy):
                    return alt.type
        else:
            for alt in filter(lambda x: x.type is not None, self.alternatives):
                if alt.token is None or alt.test(elem):
                    return alt.type

        return self._head_type or self.type

    def is_overlap(self, other):
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

    def is_consistent(self, other, strict=True):
        if isinstance(other, XsdAnyElement):
            if other.process_contents == 'skip':
                return True
            xsd_element = other.match(self.name, self.default_namespace, resolve=True)
            return xsd_element is None or self.is_consistent(xsd_element, strict=False)

        e1, e2 = self, other
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
            msg = "Maybe a not equivalent type table between elements %r and %r." % (e1, e2)
            warnings.warn(msg, XMLSchemaTypeTableWarning, stacklevel=3)
        return True


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
    type = None
    path = None
    token = None
    _ADMITTED_TAGS = {XSD_ALTERNATIVE}

    def __init__(self, elem, schema, parent):
        super(XsdAlternative, self).__init__(elem, schema, parent)

    def __repr__(self):
        return '%s(type=%r, test=%r)' % (
            self.__class__.__name__, self.elem.get('type'), self.elem.get('test')
        )

    def __eq__(self, other):
        return self.path == other.path and self.type is other.type and \
            self.xpath_default_namespace == other.xpath_default_namespace

    def __ne__(self, other):
        return self.path != other.path or self.type is not other.type or \
            self.xpath_default_namespace != other.xpath_default_namespace

    def _parse(self):
        XsdComponent._parse(self)
        attrib = self.elem.attrib

        if 'xpathDefaultNamespace' in attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace
        parser = XPath2Parser(
            self.namespaces, strict=False, default_namespace=self.xpath_default_namespace
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
                    self.parse_error("missing 'type' attribute")
                    self.type = self.any_type
                elif child.tag == XSD_COMPLEX_TYPE:
                    self.type = self.schema.BUILDERS.complex_type_class(child, self.schema, self)
                else:
                    self.type = self.schema.BUILDERS.simple_type_factory(child, self.schema, self)

                if not self.type.is_derived(self.parent.type):
                    msg = "declared type is not derived from {!r}"
                    self.parse_error(msg.format(self.parent.type))
        else:
            try:
                self.type = self.maps.lookup_type(type_qname)
            except KeyError:
                self.parse_error("unknown type %r" % attrib['type'])
            else:
                if self.type.name != XSD_ERROR and not self.type.is_derived(self.parent.type):
                    msg = "type {!r} is not derived from {!r}"
                    self.parse_error(msg.format(attrib['type'], self.parent.type))

                child = self._parse_child_component(self.elem, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    self.parse_error("the attribute 'type' and the <%s> local declaration "
                                     "are mutually exclusive" % child.tag.split('}')[-1])

    @property
    def built(self):
        return self.type.parent is None or self.type.built

    @property
    def validation_attempted(self):
        return 'full' if self.built else self.type.validation_attempted

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.type is not None and self.type.parent is not None:
            yield from self.type.iter_components(xsd_classes)

    def test(self, elem):
        try:
            return self.token.boolean_value(list(self.token.select(context=XPathContext(elem))))
        except (TypeError, ValueError):
            return False
