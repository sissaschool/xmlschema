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
from decimal import Decimal
from elementpath import XPath2Parser, ElementPathSyntaxError, XPathContext
from elementpath.xpath_helpers import boolean_value
from elementpath.datatypes import AbstractDateTime, Duration

from ..exceptions import XMLSchemaAttributeError
from ..qnames import XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE_GROUP, \
    XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE, XSD_ALTERNATIVE, XSD_ELEMENT, XSD_ANY_TYPE, XSD_UNIQUE, \
    XSD_KEY, XSD_KEYREF, XSI_NIL, XSI_TYPE, XSD_ID
from ..helpers import get_qname, get_xml_bool_attribute, get_xsd_derivation_attribute, \
    get_xsd_form_attribute, ParticleCounter
from ..etree import etree_element
from ..converters import ElementData, raw_xml_encode, XMLSchemaConverter
from ..xpath import ElementPathMixin

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent, XsdType, ValidationMixin, ParticleMixin
from .identities import XsdUnique, XsdKey, XsdKeyref
from .wildcards import XsdAnyElement


XSD_MODEL_GROUP_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}
XSD_ATTRIBUTE_GROUP_ELEMENT = etree_element(XSD_ATTRIBUTE_GROUP)


class XsdElement(XsdComponent, ValidationMixin, ParticleMixin, ElementPathMixin):
    """
    Class for XSD 1.0 'element' declarations.
    
    <element
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
    _admitted_tags = {XSD_ELEMENT}
    qualified = False
    _ref = None
    _abstract = False
    _block = None
    _final = None
    _substitution_group = None

    def __init__(self, elem, schema, parent, name=None):
        super(XsdElement, self).__init__(elem, schema, parent, name)
        self.names = (self.qualified_name,) if self.qualified else (self.qualified_name, self.local_name)
        if not hasattr(self, 'type'):
            raise XMLSchemaAttributeError("undefined 'type' attribute for %r." % self)
        if not hasattr(self, 'qualified'):
            raise XMLSchemaAttributeError("undefined 'qualified' attribute for %r." % self)

    def __repr__(self):
        if self.ref is None:
            return '%s(name=%r, occurs=%r)' % (self.__class__.__name__, self.prefixed_name, self.occurs)
        else:
            return '%s(ref=%r, occurs=%r)' % (self.__class__.__name__, self.prefixed_name, self.occurs)

    def __setattr__(self, name, value):
        if name == "type":
            assert value is None or isinstance(value, XsdType), "Wrong value %r for attribute 'type'." % value
            if hasattr(value, 'attributes'):
                self.attributes = value.attributes
            else:
                self.attributes = self.schema.BUILDERS.attribute_group_class(
                    XSD_ATTRIBUTE_GROUP_ELEMENT, self.schema, self
                )
        super(XsdElement, self).__setattr__(name, value)

    def __iter__(self):
        if not self.type.has_simple_content():
            for e in self.type.content_type.iter_subelements():
                yield e

    def _parse(self):
        XsdComponent._parse(self)
        self._parse_attributes()
        index = self._parse_type()
        self._parse_identity_constraints(index)
        if self.parent is None:
            self._parse_substitution_group()

    def _parse_attributes(self):
        elem = self.elem
        attrib = elem.attrib
        self._parse_particle(elem)

        try:
            self.qualified = (self.form or self.schema.element_form_default) == 'qualified'
        except ValueError as err:
            self.parse_error(err)

        name = elem.get('name')
        if name is not None:
            if self.parent is None or self.qualified:
                self.name = get_qname(self.target_namespace, attrib['name'])
            else:
                self.name = attrib['name']
        elif self.parent is None:
            self.parse_error("missing 'name' in a global element declaration")
            self.name = elem.get('ref', 'nameless_%s' % str(id(self)))
        elif 'ref' not in attrib:
            self.parse_error("missing both 'name' and 'ref' attributes")
            self.name = elem.get('nameless_%s' % str(id(self)))
        else:
            try:
                element_name = self.schema.resolve_qname(attrib['ref'])
            except ValueError as err:
                self.parse_error(err)
                self.type = self.maps.types[XSD_ANY_TYPE]
                self.name = elem.get('nameless_%s' % str(id(self)))
            else:
                if not element_name:
                    self.parse_error("empty 'ref' attribute")
                    self.type = self.maps.types[XSD_ANY_TYPE]
                    self.name = elem.get('nameless_%s' % str(id(self)))
                else:
                    try:
                        xsd_element = self.maps.lookup_element(element_name)
                    except KeyError:
                        self.parse_error('unknown element %r' % element_name)
                        self.name = element_name
                        self.type = self.maps.types[XSD_ANY_TYPE]
                    else:
                        self._ref = xsd_element
                        self.name = xsd_element.name
                        self.type = xsd_element.type
                        self.qualified = xsd_element.qualified

            for attr_name in ('name', 'type', 'nillable', 'default', 'fixed', 'form',
                              'block', 'abstract', 'final', 'substitutionGroup'):
                if attr_name in attrib:
                    self.parse_error("attribute %r is not allowed when element reference is used." % attr_name)
            return

        if 'default' in attrib and 'fixed' in attrib:
            self.parse_error("'default' and 'fixed' attributes are mutually exclusive.")

        if 'abstract' in elem.attrib:
            try:
                self._abstract = get_xml_bool_attribute(elem, 'abstract')
            except ValueError as err:
                self.parse_error(err, elem)
            else:
                if self.parent is not None:
                    self.parse_error("local scope elements cannot have abstract attribute")

        if 'block' in elem.attrib:
            try:
                self._block = get_xsd_derivation_attribute(
                    elem, 'block', ('extension', 'restriction', 'substitution')
                )
            except ValueError as err:
                self.parse_error(err, elem)

        if self.parent is None:
            self._parse_properties('nillable')

            if 'final' in elem.attrib:
                try:
                    self._final = get_xsd_derivation_attribute(elem, 'final', ('extension', 'restriction'))
                except ValueError as err:
                    self.parse_error(err, elem)

            for attr_name in ('ref', 'form', 'minOccurs', 'maxOccurs'):
                if attr_name in attrib:
                    self.parse_error("attribute %r not allowed in a global element declaration" % attr_name)
        else:
            self._parse_properties('form', 'nillable')

            for attr_name in ('final', 'substitutionGroup'):
                if attr_name in attrib:
                    self.parse_error("attribute %r not allowed in a local element declaration" % attr_name)

    def _parse_type(self):
        attrib = self.elem.attrib
        if self.ref:
            if self._parse_component(self.elem, required=False, strict=False) is not None:
                self.parse_error("element reference declaration can't has children.")
        elif 'type' in attrib:
            try:
                self.type = self.maps.lookup_type(self.schema.resolve_qname(attrib['type']))
            except KeyError:
                self.parse_error('unknown type %r' % attrib['type'])
                self.type = self.maps.types[XSD_ANY_TYPE]
            except ValueError as err:
                self.parse_error(err)
                self.type = self.maps.types[XSD_ANY_TYPE]
            finally:
                child = self._parse_component(self.elem, required=False, strict=False)
                if child is not None and child.tag in (XSD_COMPLEX_TYPE, XSD_SIMPLE_TYPE):
                    msg = "the attribute 'type' and the <%s> local declaration are mutually exclusive"
                    self.parse_error(msg % child.tag.split('}')[-1])
        else:
            child = self._parse_component(self.elem, required=False, strict=False)
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
            elif self.schema.XSD_VERSION == '1.0' and (
                    self.type.name == XSD_ID or self.type.is_derived(self.schema.meta_schema.types['ID'])):
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")
        elif 'fixed' in attrib:
            if not self.type.is_valid(attrib['fixed']):
                msg = "'fixed' value {!r} is not compatible with the type {!r}"
                self.parse_error(msg.format(attrib['fixed'], self.type))
            elif self.schema.XSD_VERSION == '1.0' and (
                    self.type.name == XSD_ID or self.type.is_derived(self.schema.meta_schema.types['ID'])):
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")

        return 0

    def _parse_identity_constraints(self, index=0):
        self.constraints = {}
        for child in self._iterparse_components(self.elem, start=index):
            if child.tag == XSD_UNIQUE:
                constraint = XsdUnique(child, self.schema, self)
            elif child.tag == XSD_KEY:
                constraint = XsdKey(child, self.schema, self)
            elif child.tag == XSD_KEYREF:
                constraint = XsdKeyref(child, self.schema, self)
            else:
                continue  # Error already caught by validation against the meta-schema

            try:
                if child != self.maps.constraints[constraint.name]:
                    self.parse_error("duplicated identity constraint %r:" % constraint.name, child)
            except KeyError:
                self.maps.constraints[constraint.name] = constraint
            finally:
                self.constraints[constraint.name] = constraint

    def _parse_substitution_group(self):
        substitution_group = self.elem.get('substitutionGroup')
        if substitution_group is None:
            return

        try:
            substitution_group_qname = self.schema.resolve_qname(substitution_group)
        except ValueError as err:
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

        if self.type.name == XSD_ANY_TYPE and 'type' not in self.elem.attrib:
            self.type = self.maps.elements[substitution_group_qname].type

        try:
            self.maps.substitution_groups[substitution_group_qname].add(self)
        except KeyError:
            self.maps.substitution_groups[substitution_group_qname] = {self}
        finally:
            self._substitution_group = substitution_group_qname

    @property
    def built(self):
        return self.type.parent is None or self.type.built

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        else:
            return self.type.validation_attempted

    # XSD declaration attributes
    @property
    def ref(self):
        return self.elem.get('ref')

    # Global element's exclusive properties
    @property
    def abstract(self):
        return self._abstract if self._ref is None else self._ref.abstract

    @property
    def final(self):
        return self._final or self.schema.final_default if self._ref is None else self._ref.final

    @property
    def block(self):
        return self._block or self.schema.block_default if self._ref is None else self._ref.block

    @property
    def substitution_group(self):
        return self._substitution_group if self._ref is None else self._ref.substitution_group

    @property
    def default(self):
        return self.elem.get('default') if self._ref is None else self._ref.default

    @property
    def fixed(self):
        return self.elem.get('fixed') if self._ref is None else self._ref.fixed

    @property
    def form(self):
        return get_xsd_form_attribute(self.elem, 'form') if self._ref is None else self._ref.form

    @property
    def nillable(self):
        if self._ref is not None:
            return self._ref.nillable
        return get_xml_bool_attribute(self.elem, 'nillable', default=False)

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.target_namespace, name)]
        return self.type.attributes[name]

    def get_type(self, elem):
        return self.type

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
            for obj in self.constraints.values():
                yield obj
        else:
            if isinstance(self, xsd_classes):
                yield self
            for obj in self.constraints.values():
                if isinstance(obj, xsd_classes):
                    yield obj

        if self.ref is None and self.type.parent is not None:
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def iter_substitutes(self):
        for xsd_element in self.maps.substitution_groups.get(self.name, ()):
            yield xsd_element
            for e in xsd_element.iter_substitutes():
                yield e

    def iter_decode(self, elem, validation='lax', converter=None, **kwargs):
        """
        Creates an iterator for decoding an Element instance.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode, can be 'lax', 'strict' or 'skip.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        if not isinstance(converter, XMLSchemaConverter):
            converter = self.schema.get_converter(converter, **kwargs)
        level = kwargs.pop('level', 0)
        use_defaults = kwargs.get('use_defaults', False)
        value = content = attributes = None

        # Get the instance type: xsi:type or the schema's declaration
        if XSI_TYPE not in elem.attrib:
            xsd_type = self.get_type(elem)
        else:
            xsi_type = elem.attrib[XSI_TYPE]
            try:
                xsd_type = self.maps.lookup_type(converter.unmap_qname(xsi_type))
            except KeyError:
                yield self.validation_error(validation, "unknown type %r" % xsi_type, elem, **kwargs)
                xsd_type = self.get_type(elem)

        # Decode attributes
        attribute_group = getattr(xsd_type, 'attributes', self.attributes)
        for result in attribute_group.iter_decode(elem.attrib, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield self.validation_error(validation, result, elem, **kwargs)
            else:
                attributes = result

        # Checks the xsi:nil attribute of the instance
        if validation != 'skip' and XSI_NIL in elem.attrib:
            if not self.nillable:
                yield self.validation_error(validation, "element is not nillable.", elem, **kwargs)
            try:
                if get_xml_bool_attribute(elem, XSI_NIL):
                    if elem.text is not None:
                        reason = "xsi:nil='true' but the element is not empty."
                        yield self.validation_error(validation, reason, elem, **kwargs)
                    else:
                        element_data = ElementData(elem.tag, None, None, attributes)
                        yield converter.element_decode(element_data, self, level)
                        return
            except TypeError:
                reason = "xsi:nil attribute must has a boolean value."
                yield self.validation_error(validation, reason, elem, **kwargs)

        if xsd_type.is_simple():
            if len(elem) and validation != 'skip':
                reason = "a simpleType element can't has child elements."
                yield self.validation_error(validation, reason, elem, **kwargs)

            text = elem.text
            if self.fixed is not None:
                if text is None:
                    text = self.fixed
                elif text != self.fixed:
                    reason = "must has the fixed value %r." % self.fixed
                    yield self.validation_error(validation, reason, elem, **kwargs)
            elif not text and use_defaults and self.default is not None:
                text = self.default

            if text is None:
                for result in xsd_type.iter_decode('', validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
            else:
                for result in xsd_type.iter_decode(text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                    else:
                        value = result

        elif xsd_type.has_simple_content():
            if len(elem) and validation != 'skip':
                reason = "a simple content element can't has child elements."
                yield self.validation_error(validation, reason, elem, **kwargs)

            if elem.text is not None:
                text = elem.text or self.default if use_defaults else elem.text
                for result in xsd_type.content_type.iter_decode(text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield self.validation_error(validation, result, elem, **kwargs)
                    else:
                        value = result
        else:
            for result in xsd_type.content_type.iter_decode(elem, validation, converter, level=level + 1, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield self.validation_error(validation, result, elem, **kwargs)
                else:
                    content = result

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

        element_data = ElementData(elem.tag, value, content, attributes)
        yield converter.element_decode(element_data, self, level)
        if content is not None:
            del content

        if validation != 'skip':
            for constraint in self.constraints.values():
                for error in constraint(elem):
                    yield self.validation_error(validation, error, elem, **kwargs)

    def iter_encode(self, obj, validation='lax', converter=None, **kwargs):
        """
        Creates an iterator for encoding data to an Element.

        :param obj: the data that has to be encoded.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields an Element, eventually preceded by a sequence of \
        validation or encoding errors.
        """
        if not isinstance(converter, XMLSchemaConverter):
            converter = self.schema.get_converter(converter, **kwargs)
        level = kwargs.pop('level', 0)
        element_data = converter.element_encode(obj, self, level)

        errors = []
        tag = element_data.tag
        text = None
        children = element_data.content
        attributes = ()

        if element_data.attributes and XSI_TYPE in element_data.attributes:
            xsi_type = element_data.attributes[XSI_TYPE]
            try:
                xsd_type = self.maps.lookup_type(converter.unmap_qname(xsi_type))
            except KeyError:
                errors.append("unknown type %r" % xsi_type)
                xsd_type = self.get_type(element_data)
        else:
            xsd_type = self.get_type(element_data)

        attribute_group = getattr(xsd_type, 'attributes', self.attributes)
        for result in attribute_group.iter_encode(element_data.attributes, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                errors.append(result)
            else:
                attributes = result

        if validation != 'skip' and XSI_NIL in element_data.attributes:
            if not self.nillable:
                errors.append("element is not nillable.")
            xsi_nil = element_data.attributes[XSI_NIL]
            if xsi_nil.strip() not in ('0', '1', 'true', 'false'):
                errors.append("xsi:nil attribute must has a boolean value.")
            if element_data.text is not None:
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
            for result in xsd_type.content_type.iter_encode(
                    element_data, validation, converter, level=level+1, **kwargs):
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

    def is_restriction(self, other, check_occurs=True):
        if isinstance(other, XsdAnyElement):
            if self.min_occurs == self.max_occurs == 0:
                return True
            if check_occurs and not self.has_occurs_restriction(other):
                return False
            return other.is_matching(self.name, self.default_namespace)
        elif isinstance(other, XsdElement):
            if self.name != other.name:
                substitution_group = self.substitution_group

                if other.name == self.substitution_group and other.min_occurs != other.max_occurs \
                        and self.max_occurs != 0 and not other.abstract:
                    # Base is the head element, it's not abstract and has non deterministic occurs: this
                    # is less restrictive than W3C test group (elemZ026), marked as invalid despite it's
                    # based on an abstract declaration.
                    return False
                elif self.substitution_group is None:
                    return False
                elif not any(e.name == self.name for e in self.maps.substitution_groups[substitution_group]):
                    return False

            if check_occurs and not self.has_occurs_restriction(other):
                return False
            elif self.type is not other.type and self.type.elem is not other.type.elem and \
                    not self.type.is_derived(other.type, 'restriction') and not other.type.abstract:
                return False
            elif self.fixed != other.fixed and self.type.normalize(self.fixed) != other.type.normalize(other.fixed):
                return False
            elif other.nillable is False and self.nillable:
                return False
            elif any(value not in self.block for value in other.block.split()):
                return False
            elif not all(k in other.constraints for k in self.constraints):
                return False
            else:
                return True
        elif other.model == 'choice':
            if other.is_empty() and self.max_occurs != 0:
                return False

            check_group_items_occurs = self.schema.XSD_VERSION == '1.0'
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

    def overlap(self, other):
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


class Xsd11Element(XsdElement):
    """
    Class for XSD 1.1 'element' declarations.

    <element
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
    def _parse(self):
        XsdComponent._parse(self)
        self._parse_attributes()
        index = self._parse_type()
        index = self._parse_alternatives(index)
        self._parse_identity_constraints(index)
        if self.parent is None:
            self._parse_substitution_group()
        self._parse_target_namespace()

    def _parse_alternatives(self, index=0):
        if self._ref is not None:
            self.alternatives = self._ref.alternatives
        else:
            self.alternatives = []
            for child in self._iterparse_components(self.elem, start=index):
                if child.tag == XSD_ALTERNATIVE:
                    self.alternatives.append(XsdAlternative(child, self.schema, self))
                    index += 1
                else:
                    break
        return index

    @property
    def target_namespace(self):
        try:
            return self.elem.attrib['targetNamespace']
        except KeyError:
            return self.schema.target_namespace

    def get_type(self, elem):
        if not self.alternatives:
            return self.type

        if isinstance(elem, ElementData):
            if elem.attributes:
                attrib = {k: raw_xml_encode(v) for k, v in elem.attributes.items()}
                elem = etree_element(elem.tag, attrib=attrib)
            else:
                elem = etree_element(elem.tag)

        for alt in self.alternatives:
            if alt.type is not None and boolean_value(list(alt.token.select(context=XPathContext(root=elem)))):
                return alt.type
        return self.type

    def overlap(self, other):
        if isinstance(other, XsdElement):
            if self.name == other.name:
                return True
            elif other.substitution_group == self.name or other.name == self.substitution_group:
                return True
        return False


class XsdAlternative(XsdComponent):
    """
    <alternative
      id = ID
      test = an XPath expression
      type = QName
      xpathDefaultNamespace = (anyURI | (##defaultNamespace | ##targetNamespace | ##local))
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleType | complexType)?)
    </alternative>
    """
    _admitted_tags = {XSD_ALTERNATIVE}
    type = None

    def __repr__(self):
        return '%s(type=%r, test=%r)' % (self.__class__.__name__, self.elem.get('type'), self.elem.get('test'))

    def _parse(self):
        XsdComponent._parse(self)
        attrib = self.elem.attrib
        try:
            self.path = attrib['test']
        except KeyError as err:
            self.path = 'true()'
            self.parse_error(err)

        if 'xpathDefaultNamespace' in attrib:
            self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
        else:
            self.xpath_default_namespace = self.schema.xpath_default_namespace
        parser = XPath2Parser(self.namespaces, strict=False, default_namespace=self.xpath_default_namespace)

        try:
            self.token = parser.parse(self.path)
        except ElementPathSyntaxError as err:
            self.parse_error(err)
            self.token = parser.parse('true()')
            self.path = 'true()'

        try:
            type_qname = self.schema.resolve_qname(attrib['type'])
        except KeyError:
            self.parse_error("missing 'type' attribute")
        except ValueError as err:
            self.parse_error(err)
        else:
            try:
                self.type = self.maps.lookup_type(type_qname)
            except KeyError:
                self.parse_error("unknown type %r" % attrib['type'])
            else:
                if not self.type.is_derived(self.parent.type):
                    self.parse_error("type %r ir not derived from %r" % (attrib['type'], self.parent.type))

    @property
    def built(self):
        raise NotImplementedError
