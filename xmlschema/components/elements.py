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
This module contains classes for XML Schema elements, complex types and model groups.
"""
from collections import Sequence

from ..core import etree_element, ElementData
from ..exceptions import XMLSchemaValidationError, XMLSchemaParseError, XMLSchemaAttributeError
from ..qnames import (
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_ELEMENT_TAG,
    XSD_ATTRIBUTE_GROUP_TAG, XSD_COMPLEX_TYPE_TAG, get_qname, XSD_ANY_TYPE, XSD_SIMPLE_TYPE_TAG,
    local_name, reference_to_qname
)
from ..xpath import XPathMixin
from ..utils import check_type
from .xsdbase import (
    get_xsd_attribute, get_xsd_bool_attribute, get_xsd_component,
    get_xsd_derivation_attribute, XsdComponent, ParticleMixin
)

XSD_MODEL_GROUP_TAGS = {XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}


class XsdElement(Sequence, XsdComponent, ParticleMixin, XPathMixin):
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
    FACTORY_KWARG = 'element_factory'
    XSD_GLOBAL_TAG = XSD_ELEMENT_TAG

    def __init__(self, elem, schema=None, is_global=False, parent=None, name=None, xsd_type=None,
                 qualified=False, ref=False, **options):

        self.simple_type_class = options[XSD_SIMPLE_TYPE_TAG]
        self.complex_type_class = options[XSD_COMPLEX_TYPE_TAG]
        self.attribute_group_class = options[XSD_ATTRIBUTE_GROUP_TAG]

        if xsd_type is not None:
            self.type = xsd_type
        self.ref = ref
        self.qualified = qualified
        super(XsdElement, self).__init__(elem, schema, is_global, parent, name, **options)
        if not hasattr(self, 'type'):
            raise XMLSchemaAttributeError("undefined 'type' attribute for %r." % self)

    def __getitem__(self, i):
        try:
            return self.type.content_type.elements[i]
        except (AttributeError, IndexError):
            raise IndexError('child index out of range')
        except TypeError:
            content_type = self.type.content_type
            content_type.elements = [e for e in content_type.iter_elements()]
            try:
                content_type.elements[i]
            except IndexError:
                raise IndexError('child index out of range')

    def __len__(self):
        try:
            return len(self.type.content_type.elements)
        except AttributeError:
            return 0
        except TypeError:
            content_type = self.type.content_type
            content_type.elements = [e for e in content_type.iter_elements()]

    def __setattr__(self, name, value):
        super(XsdElement, self).__setattr__(name, value)
        if name == "type":
            check_type(value, self.simple_type_class, self.complex_type_class)
            try:
                self.attributes = self.type.attributes
            except AttributeError:
                self.attributes = self.attribute_group_class(
                    etree_element(XSD_ATTRIBUTE_GROUP_TAG), schema=self.schema
                )
        elif name == "elem":
            if self.default and self.fixed:
                self.schema.errors.append(XMLSchemaParseError(
                    "'default' and 'fixed' attributes are mutually exclusive", self
                ))
            getattr(self, 'abstract')
            getattr(self, 'block')
            getattr(self, 'final')
            getattr(self, 'form')
            getattr(self, 'nillable')

    def _parse(self):
        super(XsdElement, self)._parse()
        elem = self.elem
        schema = self.schema
        options = self.options
        simple_type_factory = options.get['simple_type_factory']
        complex_type_class = options.get[XSD_COMPLEX_TYPE_TAG]

        self.name = None
        self.type = None
        self.qualified = elem.attrib.get('form', schema.element_form_default) == 'qualified'

        # Parse element attributes
        try:
            element_name = reference_to_qname(elem.attrib['ref'], schema.namespaces)
        except KeyError:
            # No 'ref' attribute ==> 'name' attribute required.
            try:
                self.name = get_qname(schema.target_namespace, elem.attrib['name'])
            except KeyError:
                self._parse_error("invalid element declaration in XSD schema", elem)
                self.ref = None
            else:
                self.ref = False
        else:
            # Reference to a global element
            self.ref = True
            if self.is_global:
                self._parse_error("an element reference can't be global", elem)
            msg = "attribute %r is not allowed when element reference is used"
            if 'name' in elem.attrib:
                self._parse_error(msg % 'name', elem)
            elif 'type' in elem.attrib:
                self._parse_error(msg % 'type', elem)
            xsd_element = schema.maps.lookup_element(element_name, **options)
            self.type = xsd_element.type   # TODO: Check if copy other attributes

        if 'substitutionGroup' in elem.attrib and not self.is_global:
            self._parse_error("'substitutionGroup' attribute in a local element declaration", elem)

        if self.ref:
            if get_xsd_component(elem, required=False, strict=False) is not None:
                self._parse_error("element reference declaration can't has children", elem)
        elif 'type' in elem.attrib:
            type_qname = reference_to_qname(elem.attrib['type'], schema.namespaces)
            try:
                self.type = schema.maps.lookup_type(type_qname, **options)
            except KeyError:
                self._parse_error('unknown type %r' % elem.attrib['type'], elem)
                self.type = schema.maps.lookup_type(XSD_ANY_TYPE)
        else:
            child = get_xsd_component(elem, required=False, strict=False)
            if child is not None:
                if child.tag == XSD_COMPLEX_TYPE_TAG:
                    self.type = complex_type_class(child, schema, **options)
                elif child.tag == XSD_SIMPLE_TYPE_TAG:
                    self.type = simple_type_factory(child, schema, **options)
            else:
                self.type = schema.maps.lookup_type(XSD_ANY_TYPE)

    @property
    def abstract(self):
        return get_xsd_bool_attribute(self.elem, 'abstract', default=False)

    @property
    def block(self):
        return get_xsd_derivation_attribute(self.elem, 'block', ('extension', 'restriction', 'substitution'))

    @property
    def default(self):
        return self._attrib.get('default', '')

    @property
    def final(self):
        return get_xsd_derivation_attribute(self.elem, 'final', ('extension', 'restriction'))

    @property
    def fixed(self):
        return self._attrib.get('fixed', '')

    @property
    def form(self):
        return get_xsd_attribute(self.elem, 'form', ('qualified', 'unqualified'), default=None)

    @property
    def nillable(self):
        return get_xsd_bool_attribute(self.elem, 'nillable', default=False)

    @property
    def substitution_group(self):
        return self._attrib.get('substitutionGroup')

    def iter_components(self, xsd_classes=None):
        for obj in super(XsdElement, self).iter_components(xsd_classes):
            yield obj
        for obj in self.type.iter_components(xsd_classes):
            yield obj

    @property
    def built(self):
        return super(XsdElement, self).built and self.type.built

    def check(self):
        if self.checked:
            return
        super(XsdElement, self).check()

        self.type.check()
        if self.type.valid is False:
            self._valid = False
        elif self.valid is False and self.type.valid is None:
            self._valid = None

    def has_name(self, name):
        return self.name == name or (not self.qualified and local_name(self.name) == name)

    def iter_decode(self, elem, validate=True, **kwargs):
        """
        Generator method for decoding elements. A data structure is returned, eventually
        preceded by a sequence of validation or decode errors (decode errors only if the
        optional argument *validate* is `False`).
        """
        # skip_errors = kwargs.get('skip_errors', False)
        element_decode_hook = kwargs.get('element_decode_hook')
        if element_decode_hook is None:
            element_decode_hook = self.schema.get_converter().element_decode
            kwargs['element_decode_hook'] = element_decode_hook
        use_defaults = kwargs.get('use_defaults', False)

        if self.type.is_complex():
            if use_defaults and self.type.has_simple_content():
                kwargs['default'] = self.default
            for result in self.type.iter_decode(elem, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    if result.schema_elem is None:
                        if self.type.name is not None and self.target_namespace == self.type.target_namespace:
                            result.schema_elem = self.type.elem
                        else:
                            result.schema_elem = self.elem
                    if result.elem is None:
                        result.elem = elem
                    yield result
                else:
                    yield element_decode_hook(ElementData(elem.tag, *result), self)
                    del result
        else:
            if elem.attrib:
                yield XMLSchemaValidationError(self, elem, "a simpleType element can't has attributes.")
            if len(elem):
                yield XMLSchemaValidationError(self, elem, "a simpleType element can't has child elements.")

            if elem.text is None:
                yield None
            else:
                text = elem.text or self.default if use_defaults else elem.text
                for result in self.type.iter_decode(text, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        if result.schema_elem is None:
                            if self.type.name is not None and \
                                            self.target_namespace == self.type.target_namespace:
                                result.schema_elem = self.type.elem
                            else:
                                result.schema_elem = self.elem
                        if result.elem is None:
                            result.elem = elem
                        yield result
                    else:
                        yield element_decode_hook(ElementData(elem.tag, result, None, None), self)
                        del result

    def iter_encode(self, data, validate=True, **kwargs):
        element_encode_hook = kwargs.get('element_encode_hook')
        if element_encode_hook is None:
            element_encode_hook = self.schema.get_converter().element_encode
            kwargs['element_encode_hook'] = element_encode_hook
        _etree_element = kwargs.get('etree_element') or etree_element

        level = kwargs.pop('level', 0)
        indent = kwargs.get('indent', None)
        tail = (u'\n' + u' ' * indent * level) if indent is not None else None

        element_data, errors = element_encode_hook(data, self)
        for e in errors:
            yield e

        if self.type.is_complex():
            for result in self.type.iter_encode(element_data, validate, level=level + 1, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    if result.schema_elem is None:
                        result.obj, result.schema_elem = data, self.elem
                    yield result
                else:
                    elem = _etree_element(self.name, attrib=dict(result.attributes))
                    elem.text = result.text
                    elem.extend(result.content)
                    elem.tail = tail
                    yield elem
        else:
            # Encode a simpleType
            if element_data.attributes:
                yield XMLSchemaValidationError(self, data, "a simpleType element can't has attributes.")
            if element_data.content:
                yield XMLSchemaValidationError(self, data, "a simpleType element can't has child elements.")

            if element_data.text is None:
                elem = _etree_element(self.name, attrib={})
                elem.text = None
                elem.tail = tail
                yield elem
            else:
                for result in self.type.iter_encode(element_data.text, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        if result.elem is None:
                            result.obj, result.schema_elem = data, self.elem
                        yield result
                    else:
                        elem = _etree_element(self.name, attrib={})
                        elem.text = result
                        elem.tail = tail
                        yield elem
                        break

        del element_data

    def iter_decode_children(self, elem, index=0):
        model_occurs = 0
        while True:
            try:
                qname = get_qname(self.target_namespace, elem[index].tag)
            except IndexError:
                if model_occurs == 0 and self.min_occurs > 0:
                    yield XMLSchemaValidationError(self, elem, "tag %r expected." % self.name)
                else:
                    yield index
                return
            else:
                if qname != self.name:
                    if model_occurs == 0 and self.min_occurs > 0:
                        yield XMLSchemaValidationError(self, elem, "tag %r expected." % self.name)
                    else:
                        yield index
                    return
                else:
                    yield self, elem[index]

            index += 1
            model_occurs += 1
            if self.max_occurs is not None and model_occurs >= self.max_occurs:
                yield index
                return

    def get_attribute(self, name):
        if name[0] != '{':
            return self.type.attributes[get_qname(self.type.schema.target_namespace, name)]
        return self.type.attributes[name]

    def iter(self, tag=None):
        if tag is None or self.name == tag:
            yield self
        try:
            for xsd_element in self.type.content_type.iter_elements():
                for e in xsd_element.iter(tag):
                    yield e
        except (TypeError, AttributeError):
            return

    def iterchildren(self, tag=None):
        try:
            for xsd_element in self.type.content_type.iter_elements():
                if tag is None or xsd_element.has_name(tag):
                    yield xsd_element
        except (TypeError, AttributeError):
            return


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
    pass
