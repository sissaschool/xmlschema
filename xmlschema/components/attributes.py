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
from ..exceptions import XMLSchemaValidationError, XMLSchemaParseError
from ..qnames import get_qname
from ..utils import get_namespace
from .xsdbase import check_type, get_xsd_attribute, XsdComponent
from .datatypes import XsdSimpleType


def get_attributes(obj):
    if isinstance(obj, dict):
        return obj
    elif isinstance(obj, str):
        return {(attr.split('=', maxsplit=1) for attr in obj.split(''))}
    else:
        return obj.attrib


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
    def __init__(self, xsd_type, name, elem=None, schema=None, qualified=False):
        super(XsdAttribute, self).__init__(name, elem, schema)
        self.type = xsd_type
        self.qualified = qualified

    def __setattr__(self, name, value):
        super(XsdAttribute, self).__setattr__(name, value)
        if name == "type":
            check_type(value, XsdSimpleType)
        elif name == "elem":
            if self.default and self.fixed:
                raise XMLSchemaParseError(
                    "'default' and 'fixed' attributes are mutually exclusive", self
                )
            getattr(self, 'form')
            getattr(self, 'use')

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

    def is_optional(self):
        return self.use == 'optional'

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


class XsdAnyAttribute(XsdComponent):
    """
    Class for XSD 1.0 'anyAttribute' declarations.
    
    <anyAttribute
      id = ID
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </anyAttribute>
    """
    def __init__(self, elem=None, schema=None):
        super(XsdAnyAttribute, self).__init__(elem=elem, schema=schema)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict',
        )

    def iter_decode(self, obj, validate=True, **kwargs):
        if self.process_contents == 'skip':
            return

        for name, value in get_attributes(obj).items():
            namespace = get_namespace(name)
            if self._is_namespace_allowed(namespace, self.namespace):
                try:
                    xsd_attribute = self.schema.maps.lookup_attribute(name)
                except LookupError:
                    if self.process_contents == 'strict':
                        yield XMLSchemaValidationError(self, obj, "attribute %r not found." % name)
                else:
                    for result in xsd_attribute.iter_decode(value, validate, **kwargs):
                        yield result
            else:
                yield XMLSchemaValidationError(self, obj, "attribute %r not allowed." % name)


class Xsd11AnyAttribute(XsdAnyAttribute):
    """
    Class for XSD 1.1 'anyAttribute' declarations.

    <anyAttribute
      id = ID
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      notNamespace = List of (anyURI | (##targetNamespace | ##local))
      notQName = List of (QName | ##defined)
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </anyAttribute>
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
    def __init__(self, name=None, elem=None, schema=None, initdict=None):
        XsdComponent.__init__(self, name, elem, schema)
        self._attribute_group = dict()
        if initdict is not None:
            self._attribute_group.update(initdict.items())

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
