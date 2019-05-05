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
This module contains classes for XML Schema attributes and attribute groups.
"""
from __future__ import unicode_literals
from decimal import Decimal
from elementpath.datatypes import AbstractDateTime, Duration

from ..compat import MutableMapping, ordered_dict_class
from ..exceptions import XMLSchemaAttributeError, XMLSchemaTypeError, XMLSchemaValueError
from ..qnames import XSD_ANY_SIMPLE_TYPE, XSD_SIMPLE_TYPE, XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, \
    XSD_RESTRICTION, XSD_EXTENSION, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE
from ..helpers import get_namespace, get_qname, get_xsd_form_attribute
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
    _admitted_tags = {XSD_ATTRIBUTE}
    qualified = False

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
            if not isinstance(value, XsdSimpleType):
                raise XMLSchemaTypeError("An XSD attribute's type must be a simpleType.")
        super(XsdAttribute, self).__setattr__(name, value)

    def _parse(self):
        super(XsdAttribute, self)._parse()
        elem = self.elem

        try:
            form = self.form
        except ValueError as err:
            self.parse_error(err)
        else:
            if form is None:
                self.qualified = self.schema.attribute_form_default == 'qualified'
            elif self.parent is None:
                self.parse_error("attribute 'form' not allowed in a global attribute.")
            else:
                self.qualified = form == 'qualified'

        self.use = elem.get('use')
        if self.use is None:
            self.use = 'optional'
        elif self.parent is None:
            self.parse_error("attribute 'use' not allowed in a global attribute.")
        elif self.use not in {'optional', 'prohibited', 'required'}:
            self.parse_error("wrong value %r for 'use' attribute." % self.use)
            self.use = 'optional'

        name = elem.get('name')
        if name is not None:
            if 'ref' in elem.attrib:
                self.parse_error("both 'name' and 'ref' in attribute declaration")
            elif name == 'xmlns':
                self.parse_error("an attribute name must be different from 'xmlns'")

            if self.parent is None or self.qualified:
                if self.target_namespace == XSI_NAMESPACE and \
                        name not in {'nil', 'type', 'schemaLocation', 'noNamespaceSchemaLocation'}:
                    self.parse_error("Cannot add attributes in %r namespace" % XSI_NAMESPACE)
                self.name = get_qname(self.target_namespace, name)
            else:
                self.name = name
        elif self.parent is None:
            self.parse_error("missing 'name' in global attribute declaration")
        else:
            try:
                attribute_qname = self.schema.resolve_qname(elem.attrib['ref'])
            except KeyError:
                self.parse_error("missing both 'name' and 'ref' in attribute declaration")
                self.xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                return
            except ValueError as err:
                self.parse_error(err)
                self.xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                return
            else:
                try:
                    xsd_attribute = self.maps.lookup_attribute(attribute_qname)
                except LookupError:
                    self.parse_error("unknown attribute %r" % elem.attrib['ref'])
                    self.type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
                else:
                    self.type = xsd_attribute.type
                    self.qualified = xsd_attribute.qualified
                    if xsd_attribute.fixed is not None and 'fixed' in elem.attrib and \
                            elem.get('fixed') != xsd_attribute.fixed:
                        self.parse_error("referenced attribute has a different fixed value %r" % xsd_attribute.fixed)

                self.name = attribute_qname
                for attribute in ('form', 'type'):
                    if attribute in self.elem.attrib:
                        self.parse_error("attribute %r is not allowed when attribute reference is used." % attribute)
                xsd_declaration = self._parse_component(elem, required=False)

                if xsd_declaration is not None and xsd_declaration.tag == XSD_SIMPLE_TYPE:
                    self.parse_error("not allowed type declaration for XSD attribute reference")
                return

        xsd_declaration = self._parse_component(elem, required=False)
        try:
            type_qname = self.schema.resolve_qname(elem.attrib['type'])
        except ValueError as err:
            self.parse_error(err, elem)
            xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)
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
            except LookupError as err:
                self.parse_error(err, elem)
                xsd_type = self.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)

            if xsd_declaration is not None and xsd_declaration.tag == XSD_SIMPLE_TYPE:
                self.parse_error("ambiguous type declaration for XSD attribute")
            elif xsd_declaration:
                self.parse_error("not allowed element in XSD attribute declaration: %r" % xsd_declaration[0])

        try:
            self.type = xsd_type
        except TypeError as err:
            self.parse_error(err)

        # Check value constraints
        if 'default' in elem.attrib:
            if 'fixed' in elem.attrib:
                self.parse_error("'default' and 'fixed' attributes are mutually exclusive")
            if self.use != 'optional':
                self.parse_error("the attribute 'use' must be 'optional' if the attribute 'default' is present")
            if not self.type.is_valid(elem.attrib['default']):
                msg = "'default' value {!r} is not compatible with the type {!r}"
                self.parse_error(msg.format(elem.attrib['default'], self.type))
            elif self.type.is_key():
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")
        elif 'fixed' in elem.attrib:
            if not self.type.is_valid(elem.attrib['fixed']):
                msg = "'fixed' value {!r} is not compatible with the type {!r}"
                self.parse_error(msg.format(elem.attrib['fixed'], self.type))
            elif self.type.is_key():
                self.parse_error("'xs:ID' or a type derived from 'xs:ID' cannot has a 'default'")

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

    @property
    def default(self):
        return self.elem.get('default')

    @property
    def fixed(self):
        return self.elem.get('fixed')

    @property
    def form(self):
        return get_xsd_form_attribute(self.elem, 'form')

    def is_optional(self):
        return self.use == 'optional'

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None and self.type.parent is not None:
            for obj in self.type.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, text, validation='lax', **kwargs):
        if not text and kwargs.get('use_defaults', True) and self.default is not None:
            text = self.default
        if self.fixed is not None and text != self.fixed and validation != 'skip':
            yield self.validation_error(validation, "value differs from fixed value", text, **kwargs)

        for result in self.type.iter_decode(text, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            elif isinstance(result, Decimal):
                try:
                    yield kwargs['decimal_type'](result)
                except (KeyError, TypeError):
                    yield result
                break
            elif isinstance(result, (AbstractDateTime, Duration)):
                try:
                    yield result if kwargs['datetime_types'] is True else text
                except KeyError:
                    yield text
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
    @property
    def inheritable(self):
        return self.elem.get('inheritable') in ('0', 'true')

    @property
    def target_namespace(self):
        return self.elem.get('targetNamespace', self.schema.target_namespace)

    def _parse(self):
        super(Xsd11Attribute, self)._parse()
        if not self.elem.get('inheritable') not in {'0', '1', 'false', 'true'}:
            self.parse_error("an XML boolean value is required for attribute 'inheritable'")
        self._parse_target_namespace()


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
    redefine = None
    _admitted_tags = {
        XSD_ATTRIBUTE_GROUP, XSD_COMPLEX_TYPE, XSD_RESTRICTION, XSD_EXTENSION,
        XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE
    }

    def __init__(self, elem, schema, parent, name=None, derivation=None, base_attributes=None):
        self.derivation = derivation
        self._attribute_group = ordered_dict_class()
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

    # Implementation of abstract methods
    def __getitem__(self, key):
        return self._attribute_group[key]

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

    def __delitem__(self, key):
        del self._attribute_group[key]

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

    def _parse(self):
        super(XsdAttributeGroup, self)._parse()
        elem = self.elem
        any_attribute = False
        attribute_group_refs = []

        if elem.tag == XSD_ATTRIBUTE_GROUP:
            if self.parent is not None:
                return  # Skip dummy definitions
            try:
                self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
            except KeyError:
                self.parse_error("an attribute group declaration requires a 'name' attribute.")
                return

        attributes = ordered_dict_class()
        for child in self._iterparse_components(elem):
            if any_attribute:
                if child.tag == XSD_ANY_ATTRIBUTE:
                    self.parse_error("more anyAttribute declarations in the same attribute group")
                else:
                    self.parse_error("another declaration after anyAttribute")

            elif child.tag == XSD_ANY_ATTRIBUTE:
                any_attribute = True
                attributes.update([(None, XsdAnyAttribute(child, self.schema, self))])

            elif child.tag == XSD_ATTRIBUTE:
                attribute = self.schema.BUILDERS.attribute_class(child, self.schema, self)
                if attribute.name in attributes:
                    self.parse_error("multiple declaration for attribute {!r}".format(attribute.name))
                else:
                    attributes[attribute.name] = attribute

            elif child.tag == XSD_ATTRIBUTE_GROUP:
                try:
                    ref = child.attrib['ref']
                    attribute_group_qname = self.schema.resolve_qname(ref)
                except ValueError as err:
                    self.parse_error(err, elem)
                except KeyError:
                    self.parse_error("the attribute 'ref' is required in a local attributeGroup", elem)
                else:
                    if attribute_group_qname in attribute_group_refs:
                        self.parse_error("duplicated attributeGroup %r" % ref)
                    elif self.redefine is not None:
                        if attribute_group_qname == self.name:
                            if attribute_group_refs:
                                self.parse_error("in a redefinition the reference to itself must be the first")
                            attribute_group_refs.append(attribute_group_qname)
                            attributes.update(self._attribute_group.items())
                            continue
                        elif not attribute_group_refs:
                            # May be an attributeGroup restriction with a ref to another group
                            if not any(e.tag == XSD_ATTRIBUTE_GROUP and ref == e.get('ref')
                                       for e in self.redefine.elem):
                                self.parse_error("attributeGroup ref=%r is not in the redefined group" % ref)
                    elif attribute_group_qname == self.name and self.schema.XSD_VERSION == '1.0':
                        self.parse_error("Circular attribute groups not allowed in XSD 1.0")
                    attribute_group_refs.append(attribute_group_qname)

                    try:
                        base_attributes = self.maps.lookup_attribute_group(attribute_group_qname)
                    except LookupError:
                        self.parse_error("unknown attribute group %r" % child.attrib['ref'], elem)
                    else:
                        if isinstance(base_attributes, tuple):
                            self.parse_error("Circular reference found between attribute groups "
                                             "{!r} and {!r}".format(self.name, attribute_group_qname))

                        for name, attr in base_attributes.items():
                            if name is not None and name in attributes:
                                self.parse_error("multiple declaration for attribute {!r}".format(name))
                            else:
                                attributes[name] = attr

            elif self.name is not None:
                self.parse_error("(attribute | attributeGroup) expected, found %r." % child)

        # Check and copy base attributes
        if self.base_attributes is not None:
            wildcard = self.base_attributes.get(None)
            for name, attr in attributes.items():
                if name not in self.base_attributes:
                    if self.derivation != 'restriction':
                        continue
                    elif wildcard is None or not wildcard.is_matching(name, self.default_namespace):
                        self.parse_error("Unexpected attribute %r in restriction" % name)
                    continue

                base_attr = self.base_attributes[name]

                if name is None:
                    if self.derivation == 'extension':
                        try:
                            attr.extend_namespace(base_attr)
                        except ValueError as err:
                            self.parse_error(err)
                    elif not attr.is_restriction(base_attr):
                        self.parse_error("Attribute wildcard is not a restriction of the base wildcard")
                    continue
                if self.derivation == 'restriction' and attr.type.name != XSD_ANY_SIMPLE_TYPE and \
                        not attr.type.is_derived(base_attr.type, 'restriction'):
                    self.parse_error("Attribute type is not a restriction of the base attribute type")
                if base_attr.use != 'optional' and attr.use == 'optional' or \
                        base_attr.use == 'required' and attr.use != 'required':
                    self.parse_error("Attribute %r: unmatched attribute use in restriction" % name)
                if base_attr.fixed is not None and \
                        attr.type.normalize(attr.fixed) != base_attr.type.normalize(base_attr.fixed):
                    self.parse_error("Attribute %r: derived attribute has a different fixed value" % name)

            self._attribute_group.update(self.base_attributes.items())
        elif self.redefine is not None and not attribute_group_refs:
            for name, attr in self._attribute_group.items():
                if name is None:
                    continue
                elif name not in attributes:
                    if attr.use == 'required':
                        self.parse_error("Missing required attribute %r in redefinition restriction" % name)
                    continue
                if attr.use != 'optional' and attributes[name].use != attr.use:
                    self.parse_error("Attribute %r: unmatched attribute use in redefinition" % name)
                if attr.fixed is not None and attributes[name].fixed is None:
                    self.parse_error("Attribute %r: redefinition remove fixed constraint" % name)

            pos = 0
            keys = list(self._attribute_group.keys())
            for name in attributes:
                try:
                    next_pos = keys.index(name)
                except ValueError:
                    self.parse_error("Redefinition restriction contains additional attribute %r" % name)
                else:
                    if next_pos < pos:
                        self.parse_error("Wrong attribute order in redefinition restriction")
                        break
                    pos = next_pos
            self.clear()

        self._attribute_group.update(attributes)

        if self.schema.XSD_VERSION == '1.0':
            has_key = False
            for attr in self._attribute_group.values():
                if attr.name is not None and attr.type.is_key():
                    if has_key:
                        self.parse_error("multiple key attributes in a group not allowed in XSD 1.0")
                    has_key = True

        elif self.parent is None and self.schema.default_attributes == self.name:
            self.schema.default_attributes = self

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

    def iter_required(self):
        for k, v in self._attribute_group.items():
            if k is not None and v.use == 'required':
                yield k

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.ref is None:
            for attr in self.values():
                if attr.parent is not None:
                    for obj in attr.iter_components(xsd_classes):
                        yield obj

    def iter_decode(self, attrs, validation='lax', **kwargs):
        if not attrs and not self:
            return

        result_list = []
        required_attributes = {a for a in self.iter_required()}
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
        required_attributes = {a for a in self.iter_required()}
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
