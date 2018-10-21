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
This module contains classes for XML Schema attributes and attribute groups.
"""
from __future__ import unicode_literals
from collections import MutableMapping
from decimal import Decimal

from ..exceptions import XMLSchemaAttributeError, XMLSchemaValueError
from ..qnames import XSD_ANY_SIMPLE_TYPE, XSD_SIMPLE_TYPE, XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, \
    XSD_RESTRICTION, XSD_EXTENSION, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE
from ..helpers import get_namespace, get_qname, local_name, prefixed_to_qname
from ..namespaces import XSI_NAMESPACE

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent, ValidationMixin
from .simple_types import XsdSimpleType
from .wildcards import XsdAnyAttribute


class XsdAttribute(XsdComponent, ValidationMixin):
    """
    Class for XSD 1.0 'attribute' declarations.

    <attribute
      default = string
      fixed = string
      form = (qualified | unqualified)
      id = ID
      name = NCName
      ref = QName
      type = QName
      use = (optional | prohibited | required) : optional
      {any attributes with non-schema namespace ...}>
      Content: (annotation?, simpleType?)
    </attribute>
    """
    admitted_tags = {XSD_ATTRIBUTE}

    def __init__(self, elem, schema, parent, name=None, xsd_type=None):
        if xsd_type is not None:
            self.type = xsd_type
        super(XsdAttribute, self).__init__(elem, schema, parent, name)
        self.names = (self.qualified_name,) if self.qualified else (self.qualified_name, self.local_name)
        if not hasattr(self, 'type'):
            raise XMLSchemaAttributeError("undefined 'type' for %r." % self)

    def __repr__(self):
        if self.ref is None:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)
        else:
            return '%s(ref=%r)' % (self.__class__.__name__, self.prefixed_name)

    def __setattr__(self, name, value):
        if name == "type":
            assert isinstance(value, XsdSimpleType), "An XSD attribute's type must be a simpleType."
        super(XsdAttribute, self).__setattr__(name, value)

    def _parse(self):
        super(XsdAttribute, self)._parse()
        elem = self.elem
        self.qualified = elem.attrib.get('form', self.schema.attribute_form_default) == 'qualified'

        if self.default is not None and self.fixed is not None:
            self.parse_error("'default' and 'fixed' attributes are mutually exclusive")
        self._parse_properties('form', 'use')

        try:
            if self.is_global or self.qualified:
                self.name = get_qname(self.target_namespace, elem.attrib['name'])
            else:
                self.name = elem.attrib['name']
        except KeyError:
            # No 'name' attribute, must be a reference
            try:
                attribute_name = prefixed_to_qname(elem.attrib['ref'], self.namespaces)
            except KeyError:
                # Missing also the 'ref' attribute
                self.parse_error("missing both 'name' and 'ref' in attribute declaration")
                return
            else:
                try:
                    xsd_attribute = self.maps.lookup_attribute(attribute_name)
                except LookupError:
                    self.parse_error("unknown attribute %r" % elem.attrib['ref'])
                    self.type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                else:
                    self.type = xsd_attribute.type
                    self.qualified = xsd_attribute.qualified

                self.name = attribute_name
                for attribute in ('form', 'type'):
                    if attribute in self.elem.attrib:
                        self.parse_error("attribute %r is not allowed when attribute reference is used." % attribute)
                return

        xsd_declaration = self._parse_component(elem, required=False)
        try:
            type_qname = prefixed_to_qname(elem.attrib['type'], self.namespaces)
        except KeyError:
            if xsd_declaration is not None:
                # No 'type' attribute in declaration, parse for child local simpleType
                xsd_type = self.schema.BUILDERS.simple_type_factory(xsd_declaration, self.schema, self)
            else:
                # Empty declaration means xsdAnySimpleType
                xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
        else:
            try:
                xsd_type = self.maps.lookup_type(type_qname)
            except LookupError:
                self.parse_error("unknown type %r." % elem.attrib['type'], elem)
                xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)

            if xsd_declaration is not None and xsd_declaration.tag == XSD_SIMPLE_TYPE:
                self.parse_error("ambiguous type declaration for XSD attribute")
            elif xsd_declaration:
                self.parse_error("not allowed element in XSD attribute declaration: %r" % xsd_declaration[0])
        self.type = xsd_type

    @property
    def built(self):
        return self.type.is_global or self.type.built

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

    @property
    def default(self):
        return self.elem.get('default')

    @property
    def fixed(self):
        return self.elem.get('fixed')

    @property
    def form(self):
        value = self.elem.get('form')
        if value not in (None, 'qualified', 'unqualified'):
            raise XMLSchemaValueError("wrong value %r for 'form' attribute." % value)
        return value

    @property
    def use(self):
        value = self.elem.get('use', 'optional')
        if value not in ('optional', 'prohibited', 'required'):
            raise XMLSchemaValueError("wrong value %r for 'use' attribute." % value)
        return value

    def is_optional(self):
        return self.use == 'optional'

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None and not self.type.is_global:
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, text, validation='lax', **kwargs):
        if not text and kwargs.get('use_defaults', True):
            text = self.default
        if self.fixed is not None and text != self.fixed and validation != 'skip':
            yield self.validation_error(validation, "value differs from fixed value", text, **kwargs)

        for result in self.type.iter_decode(text, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            elif isinstance(result, Decimal):
                try:
                    yield kwargs.get('decimal_type')(result)
                except TypeError:
                    yield result
                break
            else:
                yield result
                break

    def iter_encode(self, obj, validation='lax', **kwargs):
        for result in self.type.iter_encode(obj, validation):
            yield result
            if not isinstance(result, XMLSchemaValidationError):
                return


class Xsd11Attribute(XsdAttribute):
    """
    Class for XSD 1.1 'attribute' declarations.

    <attribute
      default = string
      fixed = string
      form = (qualified | unqualified)
      id = ID
      name = NCName
      ref = QName
      targetNamespace = anyURI
      type = QName
      use = (optional | prohibited | required) : optional
      inheritable = boolean
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, simpleType?)
    </attribute>
    """
    pass


class XsdAttributeGroup(MutableMapping, XsdComponent, ValidationMixin):
    """
    Class for XSD 'attributeGroup' definitions.
    
    <attributeGroup
      id = ID
      name = NCName
      ref = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, ((attribute | attributeGroup)*, anyAttribute?))
    </attributeGroup>
    """
    admitted_tags = {
        XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, XSD_RESTRICTION, XSD_EXTENSION,
        XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE
    }

    def __init__(self, elem, schema, parent, name=None, derivation=None, base_attributes=None):
        self.derivation = derivation
        self._attribute_group = dict()
        self.base_attributes = base_attributes
        XsdComponent.__init__(self, elem, schema, parent, name)

    def __repr__(self):
        if self.ref is not None:
            return '%s(ref=%r)' % (self.__class__.__name__, self.prefixed_name)
        elif self.name is not None:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)
        elif self:
            names = [a if a.name is None else a.prefixed_name for a in self.values()]
            return '%s(%r)' % (self.__class__.__name__, names)
        else:
            return '%s()' % self.__class__.__name__

    # Implements the abstract methods of MutableMapping
    def __getitem__(self, key):
        try:
            return self._attribute_group[key]
        except KeyError:
            if key is None or key[:1] != '{' or get_namespace(key) != self.target_namespace:
                raise
            else:
                # Unqualified form lookup if key is in targetNamespace
                try:
                    return self._attribute_group[local_name(key)]
                except KeyError:
                    pass
                raise

    def __setitem__(self, key, value):
        if key is None:
            assert isinstance(value, XsdAnyAttribute), 'An XsdAnyAttribute instance is required.'
            self._attribute_group[key] = value
        else:
            assert isinstance(value, XsdAttribute), 'An XsdAttribute instance is required.'
            if key[0] != '{':
                if value.local_name != key:
                    raise XMLSchemaValueError("%r name and key %r mismatch." % (value.name, key))
                if value.target_namespace != self.target_namespace:
                    # Qualify attributes of other namespaces
                    key = value.qualified_name
            elif value.qualified_name != key:
                raise XMLSchemaValueError("%r name and key %r mismatch." % (value.name, key))

            self._attribute_group[key] = value
            if value.use == 'required':
                self.required.add(key)

    def __delitem__(self, key):
        del self._attribute_group[key]
        self.required.discard(key)

    def __iter__(self):
        if None in self._attribute_group:
            # Put AnyAttribute ('None' key) at the end of iteration
            return iter(sorted(self._attribute_group, key=lambda x: (x is None, x)))
        else:
            return iter(self._attribute_group)

    def __len__(self):
        return len(self._attribute_group)

    # Other methods
    def __setattr__(self, name, value):
        super(XsdAttributeGroup, self).__setattr__(name, value)
        if name == '_attribute_group':
            assert isinstance(value, dict), 'A dictionary object is required.'
            for k, v in value.items():
                if k is None:
                    assert isinstance(value, XsdAnyAttribute), 'An XsdAnyAttribute instance is required.'
                else:
                    assert isinstance(value, XsdAttribute), 'An XsdAttribute instance is required.'
            self.required = {
                k for k, v in self.items() if k is not None and v.use == 'required'
            }

    def _parse(self):
        super(XsdAttributeGroup, self)._parse()
        elem = self.elem
        any_attribute = False
        self.clear()
        if self.base_attributes is not None:
            self._attribute_group.update(self.base_attributes.items())

        if elem.tag == XSD_ATTRIBUTE_GROUP:
            if self.parent is not None:
                return  # Skip dummy definitions
            try:
                self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
            except KeyError:
                self.parse_error("an attribute group declaration requires a 'name' attribute.")
                return

        for child in self._iterparse_components(elem):
            if any_attribute:
                if child.tag == XSD_ANY_ATTRIBUTE:
                    self.parse_error("more anyAttribute declarations in the same attribute group")
                else:
                    self.parse_error("another declaration after anyAttribute")

            elif child.tag == XSD_ANY_ATTRIBUTE:
                any_attribute = True
                self.update([(None, XsdAnyAttribute(child, self.schema, self))])

            elif child.tag == XSD_ATTRIBUTE:
                attribute = XsdAttribute(child, self.schema, self)
                self[attribute.name] = attribute

            elif child.tag == XSD_ATTRIBUTE_GROUP:
                try:
                    name = child.attrib['ref']
                except KeyError as err:
                    self.parse_error(str(err), elem)
                else:
                    qname = prefixed_to_qname(name, self.namespaces)
                    try:
                        attribute_group = self.maps.lookup_attribute_group(qname)
                    except LookupError:
                        self.parse_error("unknown attribute group %r" % name, elem)
                    else:
                        self.update(attribute_group.items())

            elif self.name is not None:
                self.parse_error("(attribute | attributeGroup) expected, found %r." % child)

    @property
    def built(self):
        return all([attr.built for attr in self.values()])

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif any([attr.validation_attempted == 'partial' for attr in self.values()]):
            return 'partial'
        else:
            return 'none'

    @property
    def ref(self):
        return self.elem.get('ref')

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None:
            for attr in self.values():
                if not attr.is_global:
                    for obj in attr.iter_components(xsd_classes):
                        yield obj

    def iter_decode(self, attrs, validation='lax', **kwargs):
        if not attrs and not self:
            return

        result_list = []
        required_attributes = self.required.copy()
        for name, value in attrs.items():
            try:
                xsd_attribute = self[name]
            except KeyError:
                if get_namespace(name) == XSI_NAMESPACE:
                    try:
                        xsd_attribute = self.maps.lookup_attribute(name)
                    except LookupError:
                        if validation != 'skip':
                            reason = "%r is not an attribute of the XSI namespace." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = (name, value)
                    except KeyError:
                        if validation != 'skip':
                            reason = "%r attribute not allowed for element." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue
            else:
                required_attributes.discard(name)

            for result in xsd_attribute.iter_decode(value, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((name, result))
                    break

        if required_attributes and validation != 'skip':
            reason = "missing required attributes: %r" % required_attributes
            yield self.validation_error(validation, reason, attrs, **kwargs)

        yield result_list

    def iter_encode(self, attrs, validation='lax', **kwargs):
        result_list = []
        required_attributes = self.required.copy()
        try:
            attrs = attrs.items()
        except AttributeError:
            pass

        for name, value in attrs:
            try:
                xsd_attribute = self[name]
            except KeyError:
                namespace = get_namespace(name) or self.target_namespace
                if namespace == XSI_NAMESPACE:
                    try:
                        xsd_attribute = self.maps.lookup_attribute(name)
                    except LookupError:
                        if validation != 'skip':
                            reason = "%r is not an attribute of the XSI namespace." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = (name, value)
                    except KeyError:
                        if validation != 'skip':
                            reason = "%r attribute not allowed for element." % name
                            yield self.validation_error(validation, reason, attrs, **kwargs)
                        continue
            else:
                required_attributes.discard(name)

            for result in xsd_attribute.iter_encode(value, validation, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((name, result))
                    break

        if required_attributes and validation != 'skip':
            reason = "missing required attributes %r" % required_attributes
            yield self.validation_error(validation, reason, attrs, **kwargs)
        yield result_list
