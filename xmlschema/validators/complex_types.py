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
from __future__ import unicode_literals

from ..exceptions import XMLSchemaValueError
from ..qnames import XSD_GROUP, XSD_ATTRIBUTE_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE, \
    XSD_ANY_ATTRIBUTE, XSD_ATTRIBUTE, XSD_COMPLEX_CONTENT, XSD_RESTRICTION, XSD_COMPLEX_TYPE, \
    XSD_EXTENSION, XSD_ANY_TYPE, XSD_SIMPLE_CONTENT, XSD_ANY_SIMPLE_TYPE, XSD_OPEN_CONTENT, XSD_ASSERT
from ..helpers import get_qname, local_name, get_xml_bool_attribute, get_xsd_derivation_attribute
from ..etree import etree_element

from .exceptions import XMLSchemaValidationError, XMLSchemaDecodeError
from .xsdbase import XsdType, ValidationMixin
from .assertions import XsdAssert
from .attributes import XsdAttributeGroup
from .simple_types import XsdSimpleType
from .groups import XsdGroup

XSD_MODEL_GROUP_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}

SEQUENCE_ELEMENT = etree_element(XSD_SEQUENCE)


class XsdComplexType(XsdType, ValidationMixin):
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
    _admitted_tags = {XSD_COMPLEX_TYPE, XSD_RESTRICTION}
    assertions = ()
    mixed = False
    _block = None
    _derivation = None

    @staticmethod
    def normalize(text):
        return text.decode('utf-8') if isinstance(text, bytes) else text

    def __init__(self, elem, schema, parent, name=None, **kwargs):
        if kwargs:
            if 'content_type' in kwargs:
                self.content_type = kwargs['content_type']
            if 'attributes' in kwargs:
                self.attributes = kwargs['attributes']
            if 'mixed' in kwargs:
                self.mixed = kwargs['mixed']
            if 'block' in kwargs:
                self._block = kwargs['block']
            if 'final' in kwargs:
                self._final = kwargs['final']
        super(XsdComplexType, self).__init__(elem, schema, parent, name)

    def __repr__(self):
        if self.name is not None:
            return '%s(name=%r)' % (self.__class__.__name__, self.prefixed_name)
        elif not hasattr(self, 'content_type'):
            return '%s(id=%r)' % (self.__class__.__name__, id(self))
        else:
            return '%s(content=%r, attributes=%r)' % (
                self.__class__.__name__, self.content_type_label,
                [a if a.name is None else a.prefixed_name for a in self.attributes.values()]
            )

    def __setattr__(self, name, value):
        if name == 'content_type':
            assert isinstance(value, (XsdSimpleType, XsdGroup)), \
                "The attribute 'content_type' must be a XsdSimpleType or an XsdGroup instance."
        elif name == 'attributes':
            assert isinstance(value, XsdAttributeGroup), \
                "The attribute 'attributes' must be an XsdAttributeGroup."
        super(XsdComplexType, self).__setattr__(name, value)

    def _parse(self):
        super(XsdComplexType, self)._parse()
        elem = self.elem
        if elem.tag == XSD_RESTRICTION:
            return  # a local restriction is already parsed by the caller

        if 'abstract' in elem.attrib:
            try:
                self.abstract = get_xml_bool_attribute(elem, 'abstract')
            except ValueError as err:
                self.parse_error(err, elem)

        if 'block' in elem.attrib:
            try:
                self._block = get_xsd_derivation_attribute(elem, 'block', ('extension', 'restriction'))
            except ValueError as err:
                self.parse_error(err, elem)

        if 'final' in elem.attrib:
            try:
                self._final = get_xsd_derivation_attribute(elem, 'final', ('extension', 'restriction'))
            except ValueError as err:
                self.parse_error(err, elem)

        if 'mixed' in elem.attrib:
            try:
                self.mixed = get_xml_bool_attribute(elem, 'mixed')
            except ValueError as err:
                self.parse_error(err, elem)

        try:
            self.name = get_qname(self.target_namespace, elem.attrib['name'])
        except KeyError:
            self.name = None
        else:
            if self.parent is not None:
                self.parse_error("attribute 'name' not allowed for a local complexType", elem)

        content_elem = self._parse_component(elem, required=False, strict=False)
        if content_elem is None or content_elem.tag in \
                {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE}:
            #
            # complexType with empty content
            self.content_type = self.schema.BUILDERS.group_class(SEQUENCE_ELEMENT, self.schema, self)
            self._parse_content_tail(elem)

        elif content_elem.tag in {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
            #
            # complexType with child elements
            self.content_type = self.schema.BUILDERS.group_class(content_elem, self.schema, self)
            self._parse_content_tail(elem)

        elif content_elem.tag == XSD_SIMPLE_CONTENT:
            if 'mixed' in content_elem.attrib:
                self.parse_error("'mixed' attribute not allowed with simpleContent", content_elem)

            derivation_elem = self._parse_derivation_elem(content_elem)
            if derivation_elem is None:
                return

            self.base_type = self._parse_base_type(derivation_elem)
            if derivation_elem.tag == XSD_RESTRICTION:
                self._parse_simple_content_restriction(derivation_elem, self.base_type)
            else:
                self._parse_simple_content_extension(derivation_elem, self.base_type)

            if content_elem is not elem[-1]:
                k = 2 if content_elem is not elem[0] else 1
                self.parse_error("unexpected tag %r after simpleContent declaration:" % elem[k].tag, elem)

        elif content_elem.tag == XSD_COMPLEX_CONTENT:
            #
            # complexType with complexContent restriction/extension
            if 'mixed' in content_elem.attrib:
                self.mixed = content_elem.attrib['mixed'] in ('true', '1')

            derivation_elem = self._parse_derivation_elem(content_elem)
            if derivation_elem is None:
                return

            base_type = self._parse_base_type(derivation_elem, complex_content=True)
            if derivation_elem.tag == XSD_RESTRICTION:
                self._parse_complex_content_restriction(derivation_elem, base_type)
            else:
                self._parse_complex_content_extension(derivation_elem, base_type)

            if content_elem is not elem[-1]:
                k = 2 if content_elem is not elem[0] else 1
                self.parse_error("unexpected tag %r after complexContent declaration:" % elem[k].tag, elem)
            if self.redefine or base_type is not self:
                self.base_type = base_type

        elif content_elem.tag == XSD_OPEN_CONTENT and self.schema.XSD_VERSION != '1.0':
            self.open_content = None

            if content_elem is elem[-1]:
                self.content_type = self.schema.BUILDERS.group_class(SEQUENCE_ELEMENT, self.schema, self)
            else:
                for child, index in enumerate(elem):
                    if content_elem is not child:
                        continue
                    elif elem[index + 1].tag in {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
                        self.content_type = self.schema.BUILDERS.group_class(elem[index + 1], self.schema, self)
                    else:
                        self.content_type = self.schema.BUILDERS.group_class(SEQUENCE_ELEMENT, self.schema, self)
                    break
            self._parse_content_tail(elem)

        else:
            if self.schema.validation == 'skip':
                # Also generated by meta-schema validation for 'lax' and 'strict' modes
                self.parse_error("unexpected tag %r for complexType content:" % content_elem.tag, elem)
            self.content_type = self.schema.create_any_content_group(self)
            self.attributes = self.schema.create_any_attribute_group(self)

        if self.redefine is None:
            if self.base_type is not None and self.base_type.name == self.name:
                self.parse_error("wrong definition with self-reference", elem)
        elif self.base_type is None or self.base_type.name != self.name:
            self.parse_error("wrong redefinition without self-reference", elem)

    def _parse_content_tail(self, elem, **kwargs):
        self.attributes = self.schema.BUILDERS.attribute_group_class(elem, self.schema, self, **kwargs)

    def _parse_derivation_elem(self, elem):
        derivation_elem = self._parse_component(elem, required=False)
        if getattr(derivation_elem, 'tag', None) not in (XSD_RESTRICTION, XSD_EXTENSION):
            self.parse_error("restriction or extension tag expected", derivation_elem)
            self.content_type = self.schema.create_any_content_group(self)
            self.attributes = self.schema.create_any_attribute_group(self)
            return

        derivation = local_name(derivation_elem.tag)
        if self._derivation is None:
            self._derivation = derivation == 'extension'
        elif self.redefine is None:
            raise XMLSchemaValueError("%r is expected to have a redefined/overridden component" % self)

        if self.base_type is not None and derivation in self.base_type.final:
            self.parse_error("%r derivation not allowed for %r." % (derivation, self))
        return derivation_elem

    def _parse_base_type(self, elem, complex_content=False):
        try:
            base_qname = self.schema.resolve_qname(elem.attrib['base'])
        except KeyError:
            self.parse_error("'base' attribute required", elem)
            return self.maps.types[XSD_ANY_TYPE]
        except ValueError as err:
            self.parse_error(err, elem)
            return self.maps.types[XSD_ANY_TYPE]

        try:
            base_type = self.maps.lookup_type(base_qname)
        except KeyError:
            self.parse_error("missing base type %r" % base_qname, elem)
            if complex_content:
                return self.maps.types[XSD_ANY_TYPE]
            else:
                return self.maps.types[XSD_ANY_SIMPLE_TYPE]
        else:
            if isinstance(base_type, tuple):
                self.parse_error("circularity definition found between %r and %r" % (self, base_qname), elem)
                return self.maps.types[XSD_ANY_TYPE]
            elif complex_content and base_type.is_simple():
                self.parse_error("a complexType ancestor required: %r" % base_type, elem)
                return self.maps.types[XSD_ANY_TYPE]
            return base_type

    def _parse_simple_content_restriction(self, elem, base_type):
        # simpleContent restriction: the base type must be a complexType with a simple
        # content or a complex content with a mixed and emptiable content.
        if base_type.is_simple():
            self.parse_error("a complexType ancestor required: %r" % base_type, elem)
            self.content_type = self.schema.create_any_content_group(self)
            self._parse_content_tail(elem)
        else:
            if base_type.has_simple_content():
                self.content_type = self.schema.BUILDERS.restriction_class(elem, self.schema, self)
                if not self.content_type.is_derived(base_type.content_type, 'restriction'):
                    self.parse_error("Content type is not a restriction of base content type", elem)

            elif base_type.mixed and base_type.is_emptiable():
                self.content_type = self.schema.BUILDERS.restriction_class(elem, self.schema, self)
            else:
                self.parse_error("with simple content cannot restrict an empty or "
                                 "an element-only content type ", base_type.elem)
                self.content_type = self.schema.create_any_content_group(self)

            self._parse_content_tail(elem, derivation='restriction', base_attributes=base_type.attributes)

    def _parse_simple_content_extension(self, elem, base_type):
        # simpleContent extension: the base type must be a simpleType or a complexType
        # with simple content.
        child = self._parse_component(elem, required=False, strict=False)
        if child is not None and child.tag not in \
                {XSD_ATTRIBUTE_GROUP, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE}:
            self.parse_error("unexpected tag %r." % child.tag, child)

        if base_type.is_simple():
            self.content_type = base_type
            self._parse_content_tail(elem)
        else:
            if base_type.has_simple_content():
                self.content_type = base_type.content_type
            else:
                self.parse_error("base type %r has not simple content." % base_type, elem)
                self.content_type = self.schema.create_any_content_group(self)

            self._parse_content_tail(elem, derivation='extension', base_attributes=base_type.attributes)

    def _parse_complex_content_restriction(self, elem, base_type):
        if 'restriction' in base_type.final:
            self.parse_error("the base type is not derivable by restriction")
        if base_type.is_simple() or base_type.has_simple_content():
            self.parse_error("base %r is simple or has a simple content." % base_type, elem)
            base_type = self.maps.types[XSD_ANY_TYPE]

        # complexContent restriction: the base type must be a complexType with a complex content.
        group_elem = self._parse_component(elem, required=False, strict=False)
        if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
            content_type = self.schema.BUILDERS.group_class(group_elem, self.schema, self)
        else:
            # Empty content model
            content_type = self.schema.BUILDERS.group_class(elem, self.schema, self)

        if base_type.is_element_only() and content_type.mixed:
            self.parse_error(
                "derived a mixed content from a base type that has element-only content.", elem
            )
        elif base_type.is_empty() and not content_type.is_empty():
            self.parse_error(
                "derived an empty content from base type that has not empty content.", elem
            )

        if base_type.name != XSD_ANY_TYPE and not base_type.is_empty() and False:
            if not content_type.has_occurs_restriction(base_type.content_type):
                self.parse_error("The derived group %r is not a restriction of the base group." % elem, elem)

        self.content_type = content_type
        self._parse_content_tail(elem, derivation='restriction', base_attributes=base_type.attributes)

    def _parse_complex_content_extension(self, elem, base_type):
        if 'extension' in base_type.final:
            self.parse_error("the base type is not derivable by extension")

        group_elem = self._parse_component(elem, required=False, strict=False)
        if base_type.is_empty():
            # Empty model extension: don't create a nested group.
            if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                self.content_type = self.schema.BUILDERS.group_class(group_elem, self.schema, self)
            else:
                # Empty content model
                self.content_type = self.schema.BUILDERS.group_class(elem, self.schema, self)
        else:
            # Set the content type using a dummy sequence element
            sequence_elem = etree_element(XSD_SEQUENCE)
            sequence_elem.text = '\n    '
            content_type = self.schema.BUILDERS.group_class(sequence_elem, self.schema, self)

            if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                # Illegal derivation from a simple content. Applies to both XSD 1.0 and XSD 1.1.
                # For the detailed rule refer to XSD 1.1 documentation:
                #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#sec-cos-ct-extends
                if base_type.is_simple() or base_type.has_simple_content():
                    self.parse_error("base %r is simple or has a simple content." % base_type, elem)
                    base_type = self.maps.types[XSD_ANY_TYPE]

                group = self.schema.BUILDERS.group_class(group_elem, self.schema, self)
                if group.model == 'all':
                    self.parse_error("Cannot extend a complex content with an all model")

                content_type.append(base_type.content_type)
                content_type.append(group)
                sequence_elem.append(base_type.content_type.elem)
                sequence_elem.append(group.elem)

                # complexContent extension: base type must be a complex type with complex content.
                # A dummy sequence group is added if the base type has not empty content model.
                if base_type.content_type.model == 'all' and base_type.content_type and group \
                        and self.schema.XSD_VERSION == '1.0':
                    self.parse_error("XSD 1.0 does not allow extension of a not empty 'ALL' model group.", elem)

                if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE:
                    self.parse_error("base has a different content type (mixed=%r) and the "
                                     "extension group is not empty." % base_type.mixed, elem)

            elif not base_type.is_simple() and not base_type.has_simple_content():
                content_type.append(base_type.content_type)
                sequence_elem.append(base_type.content_type.elem)
                if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE and self.mixed:
                    self.parse_error("extended type has a mixed content but the base is element-only", elem)

            self.content_type = content_type

        self._parse_content_tail(elem, derivation='extension', base_attributes=base_type.attributes)

    @property
    def built(self):
        try:
            return self.content_type.built and self.attributes.built and self.mixed in (False, True)
        except AttributeError:
            return False

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif self.attributes.validation_attempted == 'partial':
            return 'partial'
        elif self.content_type.validation_attempted == 'partial':
            return 'partial'
        else:
            return 'none'

    @property
    def block(self):
        return self.schema.block_default if self._block is None else self._block

    @staticmethod
    def is_simple():
        return False

    @staticmethod
    def is_complex():
        return True

    def is_empty(self):
        if self.name == XSD_ANY_TYPE:
            return False
        return self.content_type.is_empty()

    def is_emptiable(self):
        return self.content_type.is_emptiable()

    def has_simple_content(self):
        try:
            return self.content_type.is_simple()
        except AttributeError:
            if self.content_type or self.content_type.mixed or self.base_type is None:
                return False
            else:
                return self.base_type.is_simple() or self.base_type.has_simple_content()

    def has_mixed_content(self):
        try:
            return self.content_type.mixed
        except AttributeError:
            return False

    def is_element_only(self):
        if self.name == XSD_ANY_TYPE:
            return False
        try:
            return not self.content_type.mixed
        except AttributeError:
            return False

    def is_list(self):
        return self.has_simple_content() and self.content_type.is_list()

    def is_valid(self, source, use_defaults=True):
        if hasattr(source, 'tag'):
            return super(XsdComplexType, self).is_valid(source, use_defaults)
        elif isinstance(self.content_type, XsdSimpleType):
            return self.content_type.is_valid(source)
        else:
            return self.base_type is not None and self.base_type.is_valid(source) or self.mixed

    def is_derived(self, other, derivation=None):
        if self is other:
            return True
        elif derivation and self.derivation and derivation != self.derivation and other.is_complex():
            return False
        elif other.name == XSD_ANY_TYPE:
            return True
        elif self.base_type is other:
            return True
        elif hasattr(other, 'member_types'):
            return any(self.is_derived(m, derivation) for m in other.member_types)
        elif self.base_type is None:
            if not self.has_simple_content():
                return False
            return self.content_type.is_derived(other, derivation)
        elif self.has_simple_content():
            return self.content_type.is_derived(other, derivation) or self.base_type.is_derived(other, derivation)
        else:
            return self.base_type.is_derived(other, derivation)

    def iter_components(self, xsd_classes=None):
        if xsd_classes is None or isinstance(self, xsd_classes):
            yield self
        if self.attributes.parent is not None:
            for obj in self.attributes.iter_components(xsd_classes):
                yield obj
        if self.content_type.parent is not None:
            for obj in self.content_type.iter_components(xsd_classes):
                yield obj

        for obj in self.assertions:
            if xsd_classes is None or isinstance(obj, xsd_classes):
                yield obj

    @staticmethod
    def get_facet(*_args, **_kwargs):
        return None

    def admit_simple_restriction(self):
        if 'restriction' in self.final:
            return False
        else:
            return self.has_simple_content() or self.mixed and self.is_emptiable()

    @property
    def derivation(self):
        return 'extension' if self._derivation else 'restriction' if self._derivation is False else None

    def has_restriction(self):
        return self._derivation is False

    def has_extension(self):
        return self._derivation is True

    def decode(self, data, *args, **kwargs):
        if hasattr(data, 'attrib') or self.is_simple():
            return super(XsdComplexType, self).decode(data, *args, **kwargs)
        elif self.has_simple_content():
            return self.content_type.decode(data, *args, **kwargs)
        else:
            raise XMLSchemaDecodeError(self, data, "cannot decode %r data with %r" % (data, self))

    def iter_decode(self, elem, validation='lax', converter=None, **kwargs):
        """
        Decode an Element instance.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a 3-tuple (simple content, complex content, attributes) containing \
        the decoded parts, eventually preceded by a sequence of validation or decoding errors.
        """
        # XSD 1.1 assertions
        for assertion in self.assertions:
            for error in assertion(elem):
                yield self.validation_error(validation, error, **kwargs)

        for result in self.attributes.iter_decode(elem.attrib, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                attributes = result
                break
        else:
            attributes = None

        if self.has_simple_content():
            if len(elem) and validation != 'skip':
                reason = "a simple content element can't has child elements."
                yield self.validation_error(validation, reason, elem, **kwargs)

            if elem.text is not None:
                text = elem.text or kwargs.pop('default', '')
                for result in self.content_type.iter_decode(text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        yield result, None, attributes
            else:
                yield None, None, attributes
        else:
            for result in self.content_type.iter_decode(elem, validation, converter, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                else:
                    yield None, result, attributes

    def iter_encode(self, element_data, validation='lax', converter=None, **kwargs):
        """
        Encode an element data instance.

        :param element_data: an ElementData instance with unencoded data.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param converter: an :class:`XMLSchemaConverter` subclass or instance.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields a 3-tuple (text, content, attributes) containing the encoded parts, \
        eventually preceded by a sequence of validation or decoding errors.
        """
        for result in self.attributes.iter_encode(element_data.attributes, validation, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                yield result
            else:
                attributes = result
                break
        else:
            attributes = ()

        if self.has_simple_content():
            if element_data.text is None:
                yield None, element_data.content, attributes
            else:
                for result in self.content_type.iter_encode(element_data.text, validation, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                    else:
                        yield result, element_data.content, attributes
        else:
            for result in self.content_type.iter_encode(element_data, validation, converter, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    yield result
                elif result:
                    yield result[0], result[1], attributes
                else:
                    yield None, None, attributes


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
    def _parse(self):
        super(Xsd11ComplexType, self)._parse()

        # Add inheritable attributes
        if hasattr(self.base_type, 'attributes'):
            for name, attr in self.base_type.attributes.items():
                if name and attr.inheritable:
                    if name not in self.attributes:
                        self.attributes[name] = attr
                    elif not self.attributes[name].inheritable:
                        self.parse_error("attribute %r must be inheritable")

        # Add default attributes
        if isinstance(self.schema.default_attributes, XsdAttributeGroup) and self.default_attributes_apply:
            self.attributes.update(
                (k, v) for k, v in self.schema.default_attributes.items() if k not in self.attributes
            )

    def _parse_content_tail(self, elem, **kwargs):
        self.attributes = self.schema.BUILDERS.attribute_group_class(elem, self.schema, self, **kwargs)
        self.assertions = []
        for child in self._iterparse_components(elem):
            if child.tag == XSD_ASSERT:
                self.assertions.append(XsdAssert(child, self.schema, self, self))

    @property
    def default_attributes_apply(self):
        return get_xml_bool_attribute(self.elem, 'defaultAttributesApply', default=True)
