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
from ..core import ElementData, etree_element
from ..exceptions import XMLSchemaValidationError, XMLSchemaAttributeError
from ..utils import check_type
from ..qnames import (
    get_qname, reference_to_qname, local_name, XSD_GROUP_TAG, XSD_ATTRIBUTE_GROUP_TAG,
    XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG, XSD_ANY_ATTRIBUTE_TAG,
    XSD_ATTRIBUTE_TAG, XSD_COMPLEX_CONTENT_TAG, XSD_RESTRICTION_TAG, XSD_COMPLEX_TYPE_TAG,
    XSD_EXTENSION_TAG, XSD_ANY_TYPE, XSD_SIMPLE_CONTENT_TAG, XSD_ANY_SIMPLE_TYPE
)
from .xsdbase import (
    get_xsd_attribute, get_xsd_bool_attribute, get_xsd_component,
    get_xsd_derivation_attribute, XsdComponent
)
from .attributes import XsdAttributeGroup

XSD_MODEL_GROUP_TAGS = {XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}


class XsdComplexType(XsdComponent):
    """
    Class for XSD 1.0 'complexType' definitions.
    
    <complexType
      abstract = boolean : false
      block = (#all | List of (extension | restriction))
      final = (#all | List of (extension | restriction))
      id = ID
      mixed = boolean : false
      name = NCName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleContent | complexContent | 
      ((group | all | choice | sequence)?, ((attribute | attributeGroup)*, anyAttribute?))))
    </complexType>
    """
    def __init__(self, elem, schema, is_global=False, parent=None, name=None,
                 content_type=None, attributes=None, derivation=None, mixed=None):
        self.derivation = derivation
        super(XsdComplexType, self).__init__(elem, schema, is_global, parent, name)

        if not hasattr(self, 'content_type'):
            if content_type is None:
                import pdb
                pdb.set_trace()
                self._parse()
                raise XMLSchemaAttributeError("undefined 'content_type' attribute for %r." % self)
            self.content_type = content_type
        if not hasattr(self, 'attributes'):
            if attributes is None:
                raise XMLSchemaAttributeError("undefined 'attributes' attribute for %r." % self)
            self.attributes = attributes
        if not hasattr(self, 'mixed'):
            if mixed is None:
                raise XMLSchemaAttributeError("undefined 'mixed' attribute for %r." % self)
            self.mixed = mixed

    def __setattr__(self, name, value):
        if name == 'content_type':
            check_type(value, self.schema.simple_type_class, self.schema.group_class)
        elif name == 'attributes':
            check_type(value, self.schema.attribute_group_class)
        super(XsdComplexType, self).__setattr__(name, value)

    def _parse(self):
        super(XsdComplexType, self)._parse()
        elem = self.elem
        schema = self.schema
        self.mixed = get_xsd_bool_attribute(self.elem, 'mixed', default=False)

        getattr(self, 'abstract')
        getattr(self, 'block')
        getattr(self, 'final')

        try:
            self.name = get_qname(schema.target_namespace, elem.attrib['name'])
        except KeyError:
            self.name = None
        else:
            if not self.is_global:
                self._parse_error("attribute 'name' not allowed for a local complexType", elem)

        self.derivation = None
        self.mixed = elem.attrib.get('mixed') in ('true', '1')

        content_elem = get_xsd_component(elem, required=False, strict=False)
        if content_elem is None or content_elem.tag in \
                {XSD_ATTRIBUTE_TAG, XSD_ATTRIBUTE_GROUP_TAG, XSD_ANY_ATTRIBUTE_TAG}:
            #
            # complexType with empty content
            self.content_type = schema.group_class(elem, schema, self.mixed)
            self.attributes = schema.attribute_group_class(elem, schema)

        elif content_elem.tag in {XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG}:
            #
            # complexType with child elements
            self.content_type = schema.group_class(content_elem, schema, mixed=self.mixed)
            self.attributes = schema.attribute_group_class(elem, schema)

        elif content_elem.tag == XSD_COMPLEX_CONTENT_TAG:
            #
            # complexType with complexContent restriction/extension
            if 'mixed' in content_elem.attrib:
                self.mixed = content_elem.attrib['mixed'] in ('true', '1')

            derivation_elem = get_xsd_component(content_elem, required=False)
            if getattr(derivation_elem, 'tag', None) not in (XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG):
                self._parse_error("restriction or extension tag expected", derivation_elem)
                return
            self.derivation = local_name(derivation_elem.tag)
            base_type = self._parse_base_type(derivation_elem)

            if not isinstance(base_type, XsdComplexType):
                self._parse_error("a complexType ancestor required: %r" % base_type, elem)
                return self.schema.maps.lookup_type(XSD_ANY_TYPE)

            if derivation_elem.tag == XSD_RESTRICTION_TAG:
                self._parse_complex_restriction(derivation_elem, base_type)
            else:
                if base_type.content_type.model == XSD_ALL_TAG:
                    self._parse_error("XSD 1.0 do not allows 'ALL' group extensions", derivation_elem)
                else:
                    self._parse_complex_extension(derivation_elem, base_type)

        elif content_elem.tag == XSD_SIMPLE_CONTENT_TAG:
            if 'mixed' in content_elem.attrib:
                self._parse_error("'mixed' attribute not allowed with simpleContent", content_elem)

            derivation_elem = get_xsd_component(content_elem, required=False)
            if getattr(derivation_elem, 'tag', None) not in (XSD_RESTRICTION_TAG, XSD_EXTENSION_TAG):
                self._parse_error("restriction or extension tag expected", derivation_elem)
                return
            self.derivation = local_name(derivation_elem.tag)
            base_type = self._parse_base_type(derivation_elem)

            if derivation_elem.tag == XSD_RESTRICTION_TAG:
                self._parse_simple_restriction(derivation_elem, base_type)
            else:
                self._parse_simple_extension(derivation_elem, base_type)

        else:
            self._parse_error("unexpected tag %r for complexType content:" % content_elem.tag, self)

    def _parse_base_type(self, elem):
        try:
            content_base = get_xsd_attribute(elem, 'base')
        except KeyError:
            self._parse_error("'base' attribute required", elem)
            return self.schema.maps.lookup_type(XSD_ANY_TYPE)

        base_qname = reference_to_qname(content_base, self.schema.namespaces)
        try:
            base_type = self.schema.maps.lookup_type(base_qname)
        except KeyError:
            self._parse_error("missing base type %r" % base_qname, elem)
            return self.schema.maps.lookup_type(XSD_ANY_TYPE)
        else:
            return base_type

    def _parse_complex_restriction(self, elem, base_type):
        # Parse complexContent restriction
        #
        group_elem = get_xsd_component(elem, required=False, strict=False)
        if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
            self.content_type = self.schema.group_class(group_elem, self.schema, self.mixed)

            # Checks restrictions
            if self.content_type.model != base_type.content_type.model:
                self._parse_error(
                    "content model differ from base type: %r" % base_type.content_type.model, elem
                )
                # TODO: other checks on restrictions ...

        else:
            # Empty content model
            self.content_type = self.schema.group_class(elem, self.schema, self.mixed)

        self.attributes = self.schema.attribute_group_class(
            elem=elem,
            schema=self.schema,
            derivation='restriction',
            initdict=base_type.attributes
        )

    def _parse_complex_extension(self, elem, base_type):
        # Parse complexContent extension
        #
        group_elem = get_xsd_component(elem, required=False, strict=False)
        if base_type.is_empty():
            # Empty model extension: don't create a nested group.
            if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                self.content_type = self.schema.group_class(group_elem, self.schema, self.mixed)
            else:
                # Empty content model
                self.content_type = self.schema.group_class(elem, self.schema, self.mixed)
        elif not base_type.is_simple():
            dummy_elem = etree_element(XSD_SEQUENCE_TAG)
            self.content_type = self.schema.group_class(dummy_elem, self.schema)
            if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                xsd_group = self.schema.group_class(group_elem, self.schema, self.mixed)
                self.content_type.append(base_type.content_type)
                self.content_type.append(xsd_group)
            else:
                self.content_type.append(base_type.content_type)

        elif group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
            # Complex extension of a simple content complexType
            self.content_type = self.schema.group_class(group_elem, self.schema, mixed=self.mixed)

        self.attributes = self.schema.attribute_group_class(
            elem=elem,
            schema=self.schema,
            derivation='extension',
            initdict=base_type.attributes
        )

    def _parse_simple_restriction(self, elem, base_type):
        if not isinstance(base_type, XsdComplexType):
            self._parse_error("a complexType ancestor required: %r" % base_type, elem)
            base_type = self.schema.maps.lookup_type(XSD_ANY_TYPE)

        if base_type.content_type.is_empty():
            self._parse_error(
                "with simple content cannot restrict an empty content type", base_type.elem)
        elif not base_type.content_type.element_only():
            self._parse_error(
                "with simple content cannot restrict an element only content type", base_type.elem)

            self.content_type = self.schema.restriction_class(elem, self.schema)

    def _parse_simple_extension(self, elem, base_type):
        if base_type.is_simple():
            self.content_type = base_type.content_type
        else:
            self._parse_error("base type %r has not simple content." % base_type, elem)
            base_type = self.schema.maps.lookup_type(XSD_ANY_SIMPLE_TYPE)

        child = get_xsd_component(elem, required=False, strict=False)
        if child is not None and child.tag not in \
                {XSD_ATTRIBUTE_GROUP_TAG, XSD_ATTRIBUTE_TAG, XSD_ANY_ATTRIBUTE_TAG}:
            self._parse_error("unexpected tag %r." % child.tag, child)

        self.attributes = self.schema.attribute_group_class(
            elem=elem,
            schema=self.schema,
            derivation='extension',
            initdict=base_type.attributes
        )

    @property
    def admitted_tags(self):
        return {XSD_COMPLEX_TYPE_TAG}

    @staticmethod
    def is_simple():
        return False

    @staticmethod
    def is_complex():
        return True

    def is_empty(self):
        return self.content_type.is_empty()

    def is_emptiable(self):
        return self.content_type.is_emptiable()

    def has_simple_content(self):
        try:
            return self.content_type.is_simple()
        except AttributeError:
            return False

    def has_mixed_content(self):
        try:
            return self.content_type.mixed
        except AttributeError:
            return False

    def is_element_only(self):
        try:
            return not self.content_type.mixed
        except AttributeError:
            return False

    @property
    def abstract(self):
        return get_xsd_bool_attribute(self.elem, 'abstract', default=False)

    @property
    def block(self):
        return get_xsd_derivation_attribute(self.elem, 'block', ('extension', 'restriction'))

    @property
    def final(self):
        return get_xsd_derivation_attribute(self.elem, 'final', ('extension', 'restriction'))

    def iter_components(self, xsd_classes=None):
        for obj in super(XsdComplexType, self).iter_components(xsd_classes):
            yield obj
        for obj in self.attributes.iter_components(xsd_classes):
            yield obj
        for obj in self.content_type.iter_components(xsd_classes):
            yield obj

    def validation_attempted(self):
        if self.checked:
            return 'full'
        elif self.attributes.checked or self.content_type.checked:
            return 'partial'
        else:
            return 'none'

    def check(self):
        if self.checked:
            return
        super(XsdComplexType, self).check()

        if self.name != XSD_ANY_TYPE:
            self.content_type.check()
            self.attributes.check()

            if self.content_type.valid is False or self.attributes.valid is False:
                self._valid = False
            elif self.valid is not False:
                if self.content_type.valid is None and self.attributes.valid is None:
                    self._valid = None

    @staticmethod
    def get_facet(*args, **kwargs):
        return None

    def admit_simple_restriction(self):
        if 'restriction' in self.final:
            return False
        else:
            return self.mixed and (self.has_simple_content() or self.is_emptiable())

    def has_restriction(self):
        return self.derivation is False

    def has_extension(self):
        return self.derivation is True

    def iter_decode(self, elem, validate=True, **kwargs):
        """
        Generator method for decoding complexType elements. A 3-tuple (simple content,
        complex content, attributes) containing the decoded parts is returned, eventually
        preceded by a sequence of validation/decode errors (decode errors only if the
        optional argument *validate* is `False`).
        """
        # Decode attributes
        for result in self.attributes.iter_decode(elem, validate, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                attributes = result
                break
        else:
            attributes = None

        if self.is_simple():
            # Decode a simple content element
            if len(elem):
                yield XMLSchemaValidationError(
                    self, elem, "a simple content element can't has child elements."
                )
            if elem.text is not None:
                text = elem.text or kwargs.pop('default', '')
                for result in self.content_type.iter_decode(text, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        yield result, None, attributes
            else:
                yield None, None, attributes
        else:
            # Decode a complex content element
            for result in self.content_type.iter_decode(elem, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    yield None, result, attributes

    def iter_encode(self, data, validate=True, **kwargs):
        # Encode attributes
        for result in self.attributes.iter_encode(data.attributes, validate, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                attributes = result
                break
        else:
            attributes = ()

        if self.is_simple():
            # Encode a simple or simple content element
            if data.text is None:
                yield ElementData(None, None, data.content, attributes)
            else:
                for result in self.content_type.iter_encode(data.text, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        yield ElementData(None, result, data.content, attributes)
        else:
            # Encode a complex content element
            for result in self.content_type.iter_encode(data.content, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    yield ElementData(None, result[0], result[1], attributes)


class Xsd11ComplexType(XsdComplexType):
    """
    Class for XSD 1.1 'complexType' definitions.

    <complexType
      abstract = boolean : false
      block = (#all | List of (extension | restriction))
      final = (#all | List of (extension | restriction))
      id = ID
      mixed = boolean
      name = NCName
      defaultAttributesApply = boolean : true
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (simpleContent | complexContent | (openContent?, 
      (group | all | choice | sequence)?, ((attribute | attributeGroup)*, anyAttribute?), assert*)))
    </complexType>
    """
    pass
