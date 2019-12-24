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
This module contains classes for XML Schema elements, complex types and model groups.
"""
from __future__ import unicode_literals
import warnings
from decimal import Decimal
from elementpath import XPath2Parser, ElementPathError, XPathContext
from elementpath.datatypes import AbstractDateTime, Duration

from ..exceptions import XMLSchemaAttributeError
from ..qnames import XSD_ANNOTATION, XSD_GROUP, XSD_SEQUENCE, XSD_ALL, \
    XSD_CHOICE, XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE, \
    XSD_ALTERNATIVE, XSD_ELEMENT, XSD_ANY_TYPE, XSD_UNIQUE, XSD_KEY, \
    XSD_KEYREF, XSI_NIL, XSI_TYPE, XSD_ERROR, get_qname
from ..etree import etree_element, etree_iter_location_hints
from ..helpers import get_xsd_derivation_attribute, get_xsd_form_attribute, \
    ParticleCounter, strictly_equal
from ..namespaces import get_namespace
from ..converters import ElementData, raw_xml_encode, XMLSchemaConverter
from ..xpath import XMLSchemaProxy, ElementPathMixin

from .exceptions import XMLSchemaValidationError, XMLSchemaTypeTableWarning
from .xsdbase import XsdComponent, XsdType, ValidationMixin, ParticleMixin
from .identities import XsdKeyref
from .wildcards import XsdAnyElement


XSD_MODEL_GROUP_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}
XSD_ATTRIBUTE_GROUP_ELEMENT = etree_element(XSD_ATTRIBUTE_GROUP)


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
    type = None
    qualified = False
    alternatives = ()
    inheritable = ()

    _ADMITTED_TAGS = {XSD_ELEMENT}
    _abstract = False
    _block = None
    _final = None
    _form = None
    _nillable = False
    _substitution_group = None

    def __init__(self, elem, schema, parent):
        super(XsdElement, self).__init__(elem, schema, parent)
        ElementPathMixin.__init__(self)
        if self.type is None:
            raise XMLSchemaAttributeError("undefined 'type' attribute for %r." % self)
        if self.qualified is None:
            raise XMLSchemaAttributeError("undefined 'qualified' attribute for %r." % self)

    def __repr__(self):
        if self.ref is None:
            return '%s(name=%r, occurs=%r)' % (self.__class__.__name__, self.prefixed_name, self.occurs)
        else:
            return '%s(ref=%r, occurs=%r)' % (self.__class__.__name__, self.prefixed_name, self.occurs)

    def __setattr__(self, name, value):
        if name == "type":
            assert value is None or isinstance(value, XsdType)
            try:
                self.attributes = value.attributes
            except AttributeError:
                self.attributes = self.schema.create_empty_attribute_group(self)
        super(XsdElement, self).__setattr__(name, value)

    def __iter__(self):
        if not self.type.has_simple_content():
            for e in self.type.content_type.iter_elements():
                yield e

    @property
    def xpath_proxy(self):
        return XMLSchemaProxy(self.schema, self)

    def _parse(self):
        XsdComponent._parse(self)
        self._parse_attributes()
        index = self._parse_type()
        self._parse_identity_constraints(index)
        if self.parent is None and 'substitutionGroup' in self.elem.attrib:
            self._parse_substitution_group(self.elem.attrib['substitutionGroup'])

    def _parse_attributes(self):
        self._parse_particle(self.elem)

        attrib = self.elem.attrib
        if self._parse_reference():
            try:
                xsd_element = self.maps.lookup_element(self.name)
            except KeyError:
                self.parse_error('unknown element %r' % self.name)
                self.type = self.maps.types[XSD_ANY_TYPE]
            else:
                self.ref = xsd_element
                self.type = xsd_element.type
                self.qualified = xsd_element.qualified

            for attr_name in ('type', 'nillable', 'default', 'fixed', 'form',
                              'block', 'abstract', 'final', 'substitutionGroup'):
                if attr_name in attrib:
                    self.parse_error("attribute %r is not allowed when element reference is used." % attr_name)
            return

        if 'form' in attrib:
            try:
                self._form = get_xsd_form_attribute(self.elem, 'form')
            except ValueError as err:
                self.parse_error(err)

        if (self.form or self.schema.element_form_default) == 'qualified':
            self.qualified = True

        try:
            if self.parent is None or self.qualified:
                self.name = get_qname(self.target_namespace, attrib['name'])
            else:
                self.name = attrib['name']
        except KeyError:
            pass

        if 'default' in attrib and 'fixed' in attrib:
            self.parse_error("'default' and 'fixed' attributes are mutually exclusive.")

        if 'abstract' in attrib:
            if self.parent is not None:
                self.parse_error("local scope elements cannot have abstract attribute")
            if self._parse_boolean_attribute('abstract'):
                self._abstract = True

        if 'block' in attrib:
            try:
                self._block = get_xsd_derivation_attribute(
                    self.elem, 'block', ('extension', 'restriction', 'substitution')
                )
            except ValueError as err:
                self.parse_error(err)

        if self._parse_boolean_attribute('nillable'):
            self._nillable = True

        if self.parent is None:
            if 'final' in attrib:
                try:
                    self._final = get_xsd_derivation_attribute(self.elem, 'final', ('extension', 'restriction'))
                except ValueError as err:
                    self.parse_error(err)

            for attr_name in ('ref', 'form', 'minOccurs', 'maxOccurs'):
                if attr_name in attrib:
                    self.parse_error("attribute %r not allowed in a global element declaration" % attr_name)
        else:
            for attr_name in ('final', 'substitutionGroup'):
                if attr_name in attrib:
                    self.parse_error("attribute %r not allowed in a local element declaration" % attr_name)

    def _parse_type(self):
        attrib = self.elem.attrib
        if self.ref is not None:
            if self._parse_child_component(self.elem, strict=False) is not None:
                self.parse_error("element reference declaration can't has children.")
        elif 'type' in attrib:
            try:
                type_qname = self.schema.resolve_qname(attrib['type'])
            except (KeyError, ValueError, RuntimeError) as err:
                self.parse_error(err)
                self.type = self.maps.types[XSD_ANY_TYPE]
            else:
                try:
                    self.type = self.maps.lookup_type(type_qname)
                except KeyError:
                    self.parse_error('unknown type %r' % attrib['type'])
                    self.type = self.maps.types[XSD_ANY_TYPE]
            finally:
                child = self._parse_child_component(self.elem, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    msg = "the attribute 'type' and the <%s> local declaration are mutually exclusive"
                    self.parse_error(msg % child.tag.split('}')[-1])
        else:
            child = self._parse_child_component(self.elem, strict=False)
            if child is not None:
                if child.tag == XSD_COMPLEX_TYPE:
                    self.type = self.schema.BUILDERS.complex_type_class(child, self.schema, self)
                elif child.tag == XSD_SIMPLE_TYPE:
                    self.type = self.schema.BUILDERS.simple_type_factory(child, self.schema, self)
                else:
                    self.type = self.maps.lookup_type(XSD_ANY_TYPE)
                    return 0

                # Check value constraints
                if 'default' in attrib and not self.type.is_valid(attrib['default']):
                    msg = "'default' value %r is not compatible with the type of the element"
                    self.parse_error(msg % attrib['default'])
                elif 'fixed' in attrib and not self.type.is_valid(attrib['fixed']):
                    msg = "'fixed' value %r is not compatible with the type of the element"
                    self.parse_error(msg % attrib['fixed'])

                return 1
            else:
                self.type = self.maps.lookup_type(XSD_ANY_TYPE)
                return 0

        # Check value constraints
        if 'default' in attrib:
            if not self.type.is_valid(attrib['default']):
                msg = "'default' value {!r} is not compatible with the type {!r}"
                self.parse_error(msg.format(attrib['default'], self.type))
            elif self.xsd_version == '1.0' and self.type.is_key():
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")
        elif 'fixed' in attrib:
            if not self.type.is_valid(attrib['fixed']):
                msg = "'fixed' value {!r} is not compatible with the type {!r}"
                self.parse_error(msg.format(attrib['fixed'], self.type))
            elif self.xsd_version == '1.0' and self.type.is_key():
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")

        return 0

    def _parse_identity_constraints(self, index=0):
        if self.ref is not None:
            self.identities = self.ref.identities
            return

        self.identities = {}
        for child in filter(lambda x: x.tag != XSD_ANNOTATION, self.elem[index:]):
            if child.tag == XSD_UNIQUE:
                constraint = self.schema.BUILDERS.unique_class(child, self.schema, self)
            elif child.tag == XSD_KEY:
                constraint = self.schema.BUILDERS.key_class(child, self.schema, self)
            elif child.tag == XSD_KEYREF:
                constraint = self.schema.BUILDERS.keyref_class(child, self.schema, self)
            else:
                continue  # Error already caught by validation against the meta-schema

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
                substitution_group_qname = get_qname(self.target_namespace, substitution_group_qname)

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
        if self.type == head_element.type or self.type.name == XSD_ANY_TYPE:
            pass
        elif not self.type.is_derived(head_element.type):
            msg = "%r type is not of the same or a derivation of the head element %r type."
            self.parse_error(msg % (self, head_element))
        elif final == '#all' or 'extension' in final and 'restriction' in final:
            msg = "head element %r can't be substituted by an element that has a derivation of its type"
            self.parse_error(msg % head_element)
        elif 'extension' in final and self.type.is_derived(head_element.type, 'extension'):
            msg = "head element %r can't be substituted by an element that has an extension of its type"
            self.parse_error(msg % head_element)
        elif 'restriction' in final and self.type.is_derived(head_element.type, 'restriction'):
            msg = "head element %r can't be substituted by an element that has a restriction of its type"
            self.parse_error(msg % head_element)

        try:
            self.maps.substitution_groups[substitution_group_qname].add(self)
        except KeyError:
            self.maps.substitution_groups[substitution_group_qname] = {self}
        finally:
            self._substitution_group = substitution_group_qname

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

    # Global element's exclusive properties
    @property
    def abstract(self):
        return self._abstract if self.ref is None else self.ref.abstract

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

    @property
    def nillable(self):
        return self._nillable if self.ref is None else self.ref.nillable

    @property
    def substitution_group(self):
        return self._substitution_group if self.ref is None else self.ref.substitution_group

    @property
    def default(self):
        return self.elem.get('default') if self.ref is None else self.ref.default

    @property
    def fixed(self):
        return self.elem.get('fixed') if self.ref is None else self.ref.fixed

    @property
    def form(self):
        return self._form if self.ref is None else self.ref.form

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.target_namespace, name)]
        return self.type.attributes[name]

    def get_type(self, elem, inherited=None):
        return self.type

    def get_attributes(self, xsd_type):
        try:
            return xsd_type.attributes
        except AttributeError:
            return self.attributes

    def get_path(self, ancestor=None, reverse=False):
        """
        Returns the XPath expression of the element. The path is relative to the schema instance
        in which the element is contained or is relative to a specific ancestor passed as argument.
        In the latter case returns `None` if the argument is not an ancestor.

        :param ancestor: optional XSD component of the same schema, that may be an ancestor of the element.
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
            for obj in self.identities.values():
                yield obj
        else:
            if isinstance(self, xsd_classes):
                yield self
            for obj in self.identities.values():
                if isinstance(obj, xsd_classes):
                    yield obj

        if self.ref is None and self.type.parent is not None:
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def iter_substitutes(self):
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

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Creates an iterator for decoding an Element instance.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        if self.abstract:
            msg = "cannot use an abstract element for validation"
            yield self.validation_error(validation, msg, elem, **kwargs)

        try:
            namespaces = kwargs['namespaces']
        except KeyError:
            namespaces = None

        try:
            level = kwargs['level']
        except KeyError:
            level = kwargs['level'] = 0

        try:
            converter = kwargs['converter']
        except KeyError:
            converter = kwargs['converter'] = self.schema.get_converter(**kwargs)
        else:
            if not isinstance(converter, XMLSchemaConverter) and converter is not None:
                converter = kwargs['converter'] = self.schema.get_converter(**kwargs)

        try:
            pass  # self.check_dynamic_context(elem, **kwargs)
        except XMLSchemaValidationError as err:
            yield self.validation_error(validation, err, elem, **kwargs)

        inherited = kwargs.get('inherited')
        value = content = attributes = None

        # Get the instance effective type
        xsd_type = self.get_type(elem, inherited)
        if XSI_TYPE in elem.attrib:
            type_name = elem.attrib[XSI_TYPE].strip()
            try:
                xsd_type = self.maps.get_instance_type(type_name, xsd_type, namespaces)
            except (KeyError, TypeError) as err:
                yield self.validation_error(validation, err, elem, **kwargs)

            if xsd_type.is_blocked(self):
                yield self.validation_error(validation, "usage of %r is blocked" % xsd_type, elem, **kwargs)

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
                yield self.validation_error(validation, "element is not nillable.", elem, **kwargs)
            elif xsi_nil not in {'0', '1', 'false', 'true'}:
                reason = "xsi:nil attribute must has a boolean value."
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
                if converter is not None:
                    element_data = ElementData(elem.tag, None, None, attributes)
                    yield converter.element_decode(element_data, self, level)
                return

        if xsd_type.is_empty() and elem.text:
            reason = "character data is not allowed because the type's content is empty"
            yield self.validation_error(validation, reason, elem, **kwargs)

        if not xsd_type.has_simple_content():
            for assertion in xsd_type.assertions:
                for error in assertion(elem, **kwargs):
                    yield self.validation_error(validation, error, **kwargs)

            for result in xsd_type.content_type.iter_decode(elem, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self.validation_error(validation, result, elem, **kwargs)
                else:
                    content = result

            if len(content) == 1 and content[0][0] == 1:
                value, content = content[0][1], None

        else:
            if len(elem) and validation != 'skip':
                reason = "a simple content element can't has child elements."
                yield self.validation_error(validation, reason, elem, **kwargs)

            text = elem.text
            if self.fixed is not None:
                if text is None:
                    text = self.fixed
                elif text == self.fixed or validation == 'skip':
                    pass
                elif not strictly_equal(xsd_type.text_decode(text), xsd_type.text_decode(self.fixed)):
                    reason = "must has the fixed value %r." % self.fixed
                    yield self.validation_error(validation, reason, elem, **kwargs)

            elif not text and kwargs.get('use_defaults') and self.default is not None:
                text = self.default

            if xsd_type.is_complex():
                for assertion in xsd_type.assertions:
                    for error in assertion(elem, value=text, **kwargs):
                        yield self.validation_error(validation, error, **kwargs)

                if text and xsd_type.content_type.is_list():
                    value = text.split()
                else:
                    value = text

                xsd_type = xsd_type.content_type

            if text is None:
                for result in xsd_type.iter_decode('', validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                        if 'filler' in kwargs:
                            value = kwargs['filler'](self)
            else:
                for result in xsd_type.iter_decode(text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                    elif result is None and 'filler' in kwargs:
                        value = kwargs['filler'](self)
                    else:
                        value = result

        if isinstance(value, Decimal):
            try:
                value = kwargs['decimal_type'](value)
            except (KeyError, TypeError):
                pass
        elif isinstance(value, (AbstractDateTime, Duration)):
            try:
                if kwargs['datetime_types'] is not True:
                    value = elem.text
            except KeyError:
                value = elem.text

        if converter is not None:
            element_data = ElementData(elem.tag, value, content, attributes)
            yield converter.element_decode(element_data, self, level)
        if content is not None:
            del content

        if validation != 'skip':
            if 'max_depth' in kwargs:
                # Don't check key references with lazy or shallow validation
                for constraint in filter(lambda x: not isinstance(x, XsdKeyref), self.identities.values()):
                    for error in constraint(elem, namespaces):
                        yield self.validation_error(validation, error, elem, **kwargs)
            else:
                for constraint in self.identities.values():
                    for error in constraint(elem, namespaces):
                        yield self.validation_error(validation, error, elem, **kwargs)

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

            if element_data.text is None:
                pass
            else:
                for result in xsd_type.iter_encode(element_data.text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        text = result

        elif xsd_type.has_simple_content():
            if element_data.text is not None:
                for result in xsd_type.content_type.iter_encode(element_data.text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        text = result
        else:
            for result in xsd_type.content_type.iter_encode(element_data, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    errors.append(result)
                elif result:
                    text, children = result

        elem = converter.etree_element(tag, text, children, attributes, level)

        if validation != 'skip' and errors:
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
            elif self.fixed != other.fixed and self.type.normalize(self.fixed) != other.type.normalize(other.fixed):
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
            counter = ParticleCounter()
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
          Content: (annotation?, ((simpleType | complexType)?, alternative*, (unique | key | keyref)*))
        </element>
    """
    _target_namespace = None

    def _parse(self):
        XsdComponent._parse(self)
        self._parse_attributes()
        index = self._parse_type()
        index = self._parse_alternatives(index)
        self._parse_identity_constraints(index)

        if self.parent is None and 'substitutionGroup' in self.elem.attrib:
            for substitution_group in self.elem.attrib['substitutionGroup'].split():
                self._parse_substitution_group(substitution_group)

        self._parse_target_namespace()

        if any(v.inheritable for v in self.attributes.values()):
            self.inheritable = {k: v for k, v in self.attributes.items() if v.inheritable}

    def _parse_alternatives(self, index=0):
        if self.ref is not None:
            self.alternatives = self.ref.alternatives
        else:
            alternatives = []
            has_test = True
            for child in filter(lambda x: x.tag != XSD_ANNOTATION, self.elem[index:]):
                if child.tag == XSD_ALTERNATIVE:
                    alternatives.append(XsdAlternative(child, self.schema, self))
                    if not has_test:
                        self.parse_error("test attribute missing on non-final alternative")
                    has_test = 'test' in child.attrib
                    index += 1
                else:
                    break
            if alternatives:
                self.alternatives = alternatives

        return index

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
            for obj in self.identities.values():
                yield obj
        else:
            if isinstance(self, xsd_classes):
                yield self
            for obj in self.identities.values():
                if isinstance(obj, xsd_classes):
                    yield obj

        for alt in self.alternatives:
            for obj in alt.iter_components(xsd_classes):
                yield obj

        if self.ref is None and self.type.parent is not None:
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def iter_substitutes(self):
        for xsd_element in self.maps.substitution_groups.get(self.name, ()):
            yield xsd_element
            for e in xsd_element.iter_substitutes():
                yield e

    def get_type(self, elem, inherited=None):
        if not self.alternatives:
            return self.type

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

        return self.type

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
        return '%s(type=%r, test=%r)' % (self.__class__.__name__, self.elem.get('type'), self.elem.get('test'))

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
                self.type = self.maps.lookup_type(XSD_ANY_TYPE)
            else:
                child = self._parse_child_component(self.elem, strict=False)
                if child is None or child.tag not in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    self.parse_error("missing 'type' attribute")
                    self.type = self.maps.lookup_type(XSD_ANY_TYPE)
                elif child.tag == XSD_COMPLEX_TYPE:
                    self.type = self.schema.BUILDERS.complex_type_class(child, self.schema, self)
                else:
                    self.type = self.schema.BUILDERS.simple_type_factory(child, self.schema, self)
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
                    msg = "the attribute 'type' and the <%s> local declaration are mutually exclusive"
                    self.parse_error(msg % child.tag.split('}')[-1])

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
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def test(self, elem):
        try:
            return self.token.boolean_value(list(self.token.select(context=XPathContext(elem))))
        except (TypeError, ValueError):
            return False
