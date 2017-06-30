# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
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
from collections import MutableMapping

from ..core import XSI_NAMESPACE_PATH
from ..exceptions import XMLSchemaValidationError, XMLSchemaParseError, XMLSchemaAttributeError
from ..qnames import (
    reference_to_qname, XSD_ATTRIBUTE_TAG, get_qname, XSD_ANY_SIMPLE_TYPE, XSD_SIMPLE_TYPE_TAG,
    XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG,
    XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_ANY_ATTRIBUTE_TAG
)
from ..utils import check_type, get_namespace
from .xsdbase import get_attributes, get_xsd_attribute, XsdComponent, get_xsd_component, iter_xsd_declarations
from .simple_types import XsdSimpleType
from .wildcards import XsdAnyAttribute


class XsdAttribute(XsdComponent):
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
    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None,
                 xsd_type=None, qualified=False, **options):
        if xsd_type is not None:
            self.type = xsd_type
        self.qualified = qualified
        super(XsdAttribute, self).__init__(elem, schema, is_global, parent, name, **options)
        if not hasattr(self, 'type'):
            raise XMLSchemaAttributeError("undefined 'type' for %r." % self)

    def __setattr__(self, name, value):
        super(XsdAttribute, self).__setattr__(name, value)
        if name == "type":
            check_type(value, XsdSimpleType)
        elif name == "elem":
            if self.default and self.fixed:
                self.schema.errors.append(XMLSchemaParseError(
                    "'default' and 'fixed' attributes are mutually exclusive", self
                ))
            getattr(self, 'form')
            getattr(self, 'use')

    def _parse(self):
        super(XsdAttribute, self)._parse()
        elem = self.elem
        schema = self.schema
        options = self.options
        simple_type_factory = options[XSD_SIMPLE_TYPE_TAG]
        self.qualified = elem.attrib.get('form', schema.attribute_form_default)

        try:
            name = elem.attrib['name']
        except KeyError:
            # No 'name' attribute, must be a reference
            try:
                attribute_name = reference_to_qname(elem.attrib['ref'], schema.namespaces)
            except KeyError:
                # Missing also the 'ref' attribute
                schema.errors.append(XMLSchemaParseError(
                    "missing both 'name' and 'ref' in attribute declaration", self
                ))
                return
            else:
                xsd_attribute = schema.maps.lookup_attribute(attribute_name, **options)
                self.name = attribute_name
                self.type = xsd_attribute.type
                self.qualified = xsd_attribute.qualified
                # self.schema = xsd_attribute.schema  TODO: Check this
                return
        else:
            attribute_name = get_qname(schema.target_namespace, name)

        xsd_type = None
        xsd_declaration = get_xsd_component(elem, required=False)
        try:
            type_qname = reference_to_qname(elem.attrib['type'], schema.namespaces)
            xsd_type = schema.maps.lookup_type(type_qname, **options)
            if xsd_type.name != type_qname:
                # must implement substitution groups before!?
                # raise XMLSchemaParseError("wrong name for %r: %r." % (xsd_type, type_qname), elem)
                pass
        except KeyError:
            if xsd_declaration is not None:
                # No 'type' attribute in declaration, parse for child local simpleType
                xsd_type = simple_type_factory(xsd_declaration, schema, xsd_type, **options)
            else:
                xsd_type = schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)  # Empty declaration means xsdAnySimpleType
        else:
            if xsd_declaration is not None and xsd_declaration.tag == XSD_SIMPLE_TYPE_TAG:
                raise XMLSchemaParseError("ambiguous type declaration for XSD attribute", elem)
            elif xsd_declaration:
                raise XMLSchemaParseError(
                    "not allowed element in XSD attribute declaration: {}".format(xsd_declaration[0]),
                    elem
                )
        self.name = attribute_name
        self.type = xsd_type

    @property
    def default(self):
        return self._attrib.get('default', '')

    @property
    def fixed(self):
        return self._attrib.get('fixed', '')

    @property
    def form(self):
        return get_xsd_attribute(
            self.elem, 'form', ('qualified', 'unqualified'), default=None
        )

    @property
    def use(self):
        return get_xsd_attribute(
            self.elem, 'use', ('optional', 'prohibited', 'required'), default='optional'
        )

    def check(self):
        if self.checked:
            return
        super(XsdAttribute, self).check()

        self.type.check()
        if self.type.valid is False:
            self._valid = False
        elif self.valid is not False and self.type.valid is None:
            self._valid = None

    def is_optional(self):
        return self.use == 'optional'

    def iter_components(self, xsd_classes=None):
        for obj in super(XsdAttribute, self).iter_components(xsd_classes):
            yield obj
        for obj in self.type.iter_components(xsd_classes):
            yield obj

    def iter_decode(self, text, validate=True, **kwargs):
        if not text and kwargs.get('use_defaults', True):
            text = self.default
        for result in self.type.iter_decode(text, validate, **kwargs):
            yield result
            if not isinstance(result, XMLSchemaValidationError):
                return

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.type.iter_encode(obj, validate):
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


class XsdAttributeGroup(MutableMapping, XsdComponent):
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
    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None,
                 derivation=None, initdict=None, **options):
        self.derivation = derivation
        self._attribute_group = dict()
        if initdict is not None:
            self._attribute_group.update(initdict.items())
        XsdComponent.__init__(self, elem, schema, is_global, parent, name, **options)

    # Implements the abstract methods of MutableMapping
    def __getitem__(self, key):
        return self._attribute_group[key]

    def __setitem__(self, key, value):
        if key is None:
            check_type(value, XsdAnyAttribute)
        else:
            check_type(value, XsdAttribute)
        self._attribute_group[key] = value
        if key is not None and value.use == 'required':
            self.required.add(key)

    def __delitem__(self, key):
        del self._attribute_group[key]
        self.required.discard(key)

    def __iter__(self):
        return iter(self._attribute_group)

    def __len__(self):
        return len(self._attribute_group)

    # Other methods
    def __setattr__(self, name, value):
        super(XsdAttributeGroup, self).__setattr__(name, value)
        if name == '_attribute_group':
            check_type(value, dict)
            for k, v in value.items():
                if k is None:
                    check_type(v, XsdAnyAttribute)
                else:
                    check_type(v, XsdAttribute)
            self.required = {
                k for k, v in self.items() if k is not None and v.use == 'required'
            }

    def _parse(self):
        super(XsdAttributeGroup, self)._parse()
        elem = self.elem
        schema = self.schema
        options = self.options
        any_attribute = False
        self.clear()
        self.name = None

        if elem.tag not in {XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, XSD_RESTRICTION_TAG,
                            XSD_EXTENSION_TAG, XSD_ATTRIBUTE_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
            schema.errors.append(XMLSchemaParseError("unexpected tag", elem))
            return

        if elem.tag == XSD_ATTRIBUTE_GROUP_TAG:
            if not self.is_global:
                return  # Skip dummy definitions
            try:
                self.name = get_qname(schema.target_namespace, elem.attrib['name'])
            except KeyError:
                schema.errors.append(XMLSchemaParseError(
                    "an attribute group declaration requires a 'name' attribute.", elem
                ))
                return

        for child in iter_xsd_declarations(elem):
            if any_attribute:
                if child.tag == XSD_ANY_ATTRIBUTE_TAG:
                    schema.errors.append(XMLSchemaParseError(
                        "more anyAttribute declarations in the same attribute group", child))
                else:
                    schema.errors.append(XMLSchemaParseError(
                        "another declaration after anyAttribute", child))
            elif child.tag == XSD_ANY_ATTRIBUTE_TAG:
                any_attribute = True
                self.update({None: XsdAnyAttribute(elem=child, schema=schema)})
            elif child.tag == XSD_ATTRIBUTE_TAG:
                attribute = XsdAttribute(child, schema, **options)
                self[attribute.name] = attribute
            elif child.tag == XSD_ATTRIBUTE_GROUP_TAG:
                qname = reference_to_qname(get_xsd_attribute(child, 'ref'), schema.namespaces)
                ref_attribute_group = schema.maps.lookup_attribute_group(qname, **options)
                self.update(ref_attribute_group.items())
            elif self.name is not None:
                schema.errors.append(XMLSchemaParseError(
                    "(attribute | attributeGroup) expected, found", child
                ))

    @property
    def built(self):
        built = super(XsdAttributeGroup, self).built
        return built and all([attr.built for attr in self.values()])

    def check(self):
        if self.checked:
            return
        super(XsdAttributeGroup, self).check()

        for attr in self.values():
            attr.check()

        if any([attr.valid is False for attr in self.values()]):
            self._valid = False
        elif self.valid is not False and any([attr.valid is None for attr in self.values()]):
            self._valid = None

    def iter_components(self, xsd_classes=None):
        for obj in super(XsdAttributeGroup, self).iter_components(xsd_classes):
            yield obj
        for attr in self.values():
            for obj in attr.iter_components(xsd_classes):
                yield obj

    def iter_decode(self, obj, validate=True, **kwargs):
        result_list = []

        required_attributes = self.required.copy()
        attributes = get_attributes(obj)
        for name, value in attributes.items():
            qname = get_qname(self.target_namespace, name)
            try:
                xsd_attribute = self[qname]
            except KeyError:
                namespace = get_namespace(name) or self.target_namespace
                if namespace == XSI_NAMESPACE_PATH:
                    try:
                        xsd_attribute = self.schema.maps.lookup_attribute(qname)
                    except LookupError:
                        yield XMLSchemaValidationError(
                            self, attributes, "% is not an attribute of the XSI namespace." % name
                        )
                        continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = {qname: value}
                    except KeyError:
                        yield XMLSchemaValidationError(
                            self, attributes, "%r attribute not allowed for element." % name
                        )
                        continue
            else:
                required_attributes.discard(qname)

            for result in xsd_attribute.iter_decode(value, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((name, result))
                    break

        if required_attributes:
            yield XMLSchemaValidationError(
                self, attributes, "missing required attributes %r" % required_attributes,
            )
        yield result_list

    def iter_encode(self, attributes, validate=True, **kwargs):
        result_list = []
        required_attributes = self.required.copy()
        try:
            attributes = attributes.items()
        except AttributeError:
            pass

        for name, value in attributes:
            qname = reference_to_qname(name, self.namespaces)
            # qname = get_qname(self.target_namespace, name)
            try:
                xsd_attribute = self[qname]
            except KeyError:
                namespace = get_namespace(name) or self.target_namespace
                if namespace == XSI_NAMESPACE_PATH:
                    try:
                        xsd_attribute = self.schema.maps.lookup_attribute(qname)
                    except LookupError:
                        yield XMLSchemaValidationError(
                            self, attributes, "% is not an attribute of the XSI namespace." % name
                        )
                        continue
                else:
                    try:
                        xsd_attribute = self[None]  # None key ==> anyAttribute
                        value = {qname: value}
                    except KeyError:
                        yield XMLSchemaValidationError(
                            self, attributes, "%r attribute not allowed for element." % name
                        )
                        continue
            else:
                required_attributes.discard(qname)

            for result in xsd_attribute.iter_encode(value, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    result_list.append((name, result))
                    break

        if required_attributes:
            yield XMLSchemaValidationError(
                self, attributes, "missing required attributes %r" % required_attributes,
            )
        yield result_list
