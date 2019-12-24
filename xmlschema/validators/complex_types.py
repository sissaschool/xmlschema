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
from ..qnames import XSD_ANNOTATION, XSD_GROUP, XSD_ATTRIBUTE_GROUP, XSD_SEQUENCE, \
    XSD_ALL, XSD_CHOICE, XSD_ANY_ATTRIBUTE, XSD_ATTRIBUTE, XSD_COMPLEX_CONTENT, \
    XSD_RESTRICTION, XSD_COMPLEX_TYPE, XSD_EXTENSION, XSD_ANY_TYPE, XSD_OVERRIDE, \
    XSD_SIMPLE_CONTENT, XSD_ANY_SIMPLE_TYPE, XSD_OPEN_CONTENT, XSD_ASSERT, \
    get_qname, local_name
from ..helpers import get_xsd_derivation_attribute

from .exceptions import XMLSchemaDecodeError
from .xsdbase import XsdComponent, XsdType, ValidationMixin
from .assertions import XsdAssert
from .attributes import XsdAttributeGroup
from .simple_types import XsdSimpleType
from .groups import XsdGroup
from .wildcards import XsdOpenContent

XSD_MODEL_GROUP_TAGS = {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}


class XsdComplexType(XsdType, ValidationMixin):
    """
    Class for XSD 1.0 *complexType* definitions.

    :var attributes: the attribute group related with the type.
    :var content_type: the content type, that can be a model group or a simple type.
    :var mixed: if `True` the complex type has mixed content.

    ..  <complexType
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
    abstract = False
    mixed = False
    assertions = ()
    open_content = None
    content_type = None
    default_open_content = None
    _block = None

    _ADMITTED_TAGS = {XSD_COMPLEX_TYPE, XSD_RESTRICTION}
    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE, XSD_ATTRIBUTE_GROUP, XSD_ANY_ATTRIBUTE}

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
        elif not hasattr(self, 'content_type') or not hasattr(self, 'attributes'):
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

        if self._parse_boolean_attribute('abstract'):
            self.abstract = True

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

        if self._parse_boolean_attribute('mixed'):
            self.mixed = True

        try:
            self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self.name = None
            if self.parent is None:
                self.parse_error("missing attribute 'name' in a global complexType")
                self.name = 'nameless_%s' % str(id(self))
        else:
            if self.parent is not None:
                self.parse_error("attribute 'name' not allowed for a local complexType")
                self.name = None

        content_elem = self._parse_child_component(elem, strict=False)
        if content_elem is None or content_elem.tag in self._CONTENT_TAIL_TAGS:
            self.content_type = self.schema.create_empty_content_group(self)
            self._parse_content_tail(elem)

        elif content_elem.tag in {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
            self.content_type = self.schema.BUILDERS.group_class(content_elem, self.schema, self)
            default_open_content = self.default_open_content
            if default_open_content and \
                    (self.mixed or self.content_type or default_open_content.applies_to_empty):
                self.open_content = default_open_content
            self._parse_content_tail(elem)

        elif content_elem.tag == XSD_SIMPLE_CONTENT:
            if 'mixed' in content_elem.attrib:
                self.parse_error("'mixed' attribute not allowed with simpleContent", content_elem)

            derivation_elem = self._parse_derivation_elem(content_elem)
            if derivation_elem is None:
                return

            self.base_type = base_type = self._parse_base_type(derivation_elem)
            if derivation_elem.tag == XSD_RESTRICTION:
                self._parse_simple_content_restriction(derivation_elem, base_type)
            else:
                self._parse_simple_content_extension(derivation_elem, base_type)

            if content_elem is not elem[-1]:
                k = 2 if content_elem is not elem[0] else 1
                self.parse_error("unexpected tag %r after simpleContent declaration:" % elem[k].tag, elem)

        elif content_elem.tag == XSD_COMPLEX_CONTENT:
            #
            # complexType with complexContent restriction/extension
            if 'mixed' in content_elem.attrib:
                mixed = content_elem.attrib['mixed'] in ('true', '1')
                if mixed is not self.mixed:
                    self.mixed = mixed
                    if 'mixed' in elem.attrib and self.xsd_version == '1.1':
                        self.parse_error(
                            "value of 'mixed' attribute in complexType and complexContent must be same"
                        )

            derivation_elem = self._parse_derivation_elem(content_elem)
            if derivation_elem is None:
                return

            base_type = self._parse_base_type(derivation_elem, complex_content=True)
            if base_type is not self:
                self.base_type = base_type
            elif self.redefine:
                self.base_type = self.redefine
                self.open_content = None

            if derivation_elem.tag == XSD_RESTRICTION:
                self._parse_complex_content_restriction(derivation_elem, base_type)
            else:
                self._parse_complex_content_extension(derivation_elem, base_type)

            if content_elem is not elem[-1]:
                k = 2 if content_elem is not elem[0] else 1
                self.parse_error("unexpected tag %r after complexContent declaration:" % elem[k].tag, elem)

        elif content_elem.tag == XSD_OPEN_CONTENT and self.xsd_version > '1.0':
            self.open_content = XsdOpenContent(content_elem, self.schema, self)

            if content_elem is elem[-1]:
                self.content_type = self.schema.create_empty_content_group(self)
            else:
                for index, child in enumerate(elem):
                    if content_elem is not child:
                        continue
                    elif elem[index + 1].tag in {XSD_GROUP, XSD_SEQUENCE, XSD_ALL, XSD_CHOICE}:
                        self.content_type = self.schema.BUILDERS.group_class(elem[index + 1], self.schema, self)
                    else:
                        self.content_type = self.schema.self.schema.create_empty_content_group(self)
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
        derivation_elem = self._parse_child_component(elem)
        if getattr(derivation_elem, 'tag', None) not in (XSD_RESTRICTION, XSD_EXTENSION):
            self.parse_error("restriction or extension tag expected", derivation_elem)
            self.content_type = self.schema.create_any_content_group(self)
            self.attributes = self.schema.create_any_attribute_group(self)
            return

        derivation = local_name(derivation_elem.tag)
        if self.derivation is None:
            self.derivation = derivation
        elif self.redefine is None:
            raise XMLSchemaValueError("%r is expected to have a redefined/overridden component" % self)

        if self.base_type is not None and derivation in self.base_type.final:
            self.parse_error("%r derivation not allowed for %r." % (derivation, self))
        return derivation_elem

    def _parse_base_type(self, elem, complex_content=False):
        try:
            base_qname = self.schema.resolve_qname(elem.attrib['base'])
        except (KeyError, ValueError, RuntimeError) as err:
            if 'base' not in elem.attrib:
                self.parse_error("'base' attribute required", elem)
            else:
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

            if base_type.final and elem.tag.rsplit('}', 1)[-1] in base_type.final:
                msg = "derivation by %r blocked by attribute 'final' in base type"
                self.parse_error(msg % elem.tag.rsplit('}', 1)[-1])

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
        child = self._parse_child_component(elem, strict=False)
        if child is not None and child.tag not in self._CONTENT_TAIL_TAGS:
            self.parse_error('unexpected tag %r' % child.tag, child)

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
        for child in filter(lambda x: x.tag != XSD_ANNOTATION, elem):
            if child.tag == XSD_OPEN_CONTENT and self.xsd_version > '1.0':
                self.open_content = XsdOpenContent(child, self.schema, self)
                continue
            elif child.tag in XSD_MODEL_GROUP_TAGS:
                content_type = self.schema.BUILDERS.group_class(child, self.schema, self)
                if not base_type.content_type.admits_restriction(content_type.model):
                    msg = "restriction of an xs:{} with more than one particle with xs:{} is forbidden"
                    self.parse_error(msg.format(base_type.content_type.model, content_type.model))
                break
        else:
            content_type = self.schema.create_empty_content_group(self, base_type.content_type.model)

        content_type.restriction = base_type.content_type

        if base_type.is_element_only() and content_type.mixed:
            self.parse_error(
                "derived a mixed content from a base type that has element-only content.", elem
            )
        elif base_type.is_empty() and not content_type.is_empty():
            self.parse_error(
                "derived an empty content from base type that has not empty content.", elem
            )

        if not self.open_content:
            default_open_content = self.default_open_content
            if default_open_content and \
                    (self.mixed or content_type or default_open_content.applies_to_empty):
                self.open_content = default_open_content

        if self.open_content and content_type and \
                not self.open_content.is_restriction(base_type.open_content):
            msg = "{!r} is not a restriction of the base type {!r}"
            self.parse_error(msg.format(self.open_content, base_type.open_content))

        self.content_type = content_type
        self._parse_content_tail(elem, derivation='restriction', base_attributes=base_type.attributes)

    def _parse_complex_content_extension(self, elem, base_type):
        if 'extension' in base_type.final:
            self.parse_error("the base type is not derivable by extension")

        for group_elem in filter(lambda x: x.tag != XSD_ANNOTATION, elem):
            break
        else:
            group_elem = None

        if base_type.is_empty():
            if not base_type.mixed:
                # Empty element-only model extension: don't create a nested group.
                if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                    self.content_type = self.schema.BUILDERS.group_class(group_elem, self.schema, self)
                elif base_type.is_simple() or base_type.has_simple_content():
                    self.content_type = self.schema.create_empty_content_group(self)
                else:
                    self.content_type = self.schema.create_empty_content_group(
                        parent=self, model=base_type.content_type.model
                    )
            elif base_type.mixed:
                # Empty mixed model extension
                self.content_type = self.schema.create_empty_content_group(self)
                self.content_type.append(self.schema.create_empty_content_group(self.content_type))

                if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                    group = self.schema.BUILDERS.group_class(group_elem, self.schema, self.content_type)
                    if not self.mixed:
                        self.parse_error("base has a different content type (mixed=%r) and the "
                                         "extension group is not empty." % base_type.mixed, elem)
                else:
                    group = self.schema.create_empty_content_group(self)

                self.content_type.append(group)
                self.content_type.elem.append(base_type.content_type.elem)
                self.content_type.elem.append(group.elem)

        elif group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
            # Derivation from a simple content is forbidden if base type is not empty.
            if base_type.is_simple() or base_type.has_simple_content():
                self.parse_error("base %r is simple or has a simple content." % base_type, elem)
                base_type = self.any_type

            group = self.schema.BUILDERS.group_class(group_elem, self.schema, self)

            if group.model == 'all':
                self.parse_error("cannot extend a complex content with xs:all")
            if base_type.content_type.model == 'all' and group.model == 'sequence':
                self.parse_error("xs:sequence cannot extend xs:all")

            content_type = self.schema.create_empty_content_group(self)
            content_type.append(base_type.content_type)
            content_type.append(group)
            content_type.elem.append(base_type.content_type.elem)
            content_type.elem.append(group.elem)

            if base_type.content_type.model == 'all' and base_type.content_type and group:
                self.parse_error("XSD 1.0 does not allow extension of a not empty 'all' model group")
            if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE:
                self.parse_error("base has a different content type (mixed=%r) and the "
                                 "extension group is not empty." % base_type.mixed, elem)
            self.content_type = content_type

        elif not base_type.is_simple() and not base_type.has_simple_content():
            self.content_type = self.schema.create_empty_content_group(self)
            self.content_type.append(base_type.content_type)
            self.content_type.elem.append(base_type.content_type.elem)
            if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE and self.mixed:
                self.parse_error("extended type has a mixed content but the base is element-only", elem)
        else:
            self.content_type = self.schema.create_empty_content_group(self)

        self._parse_content_tail(elem, derivation='extension', base_attributes=base_type.attributes)

    @property
    def block(self):
        return self.schema.block_default if self._block is None else self._block

    @property
    def built(self):
        return self.content_type.parent is not None or self.content_type.built

    @property
    def validation_attempted(self):
        return 'full' if self.built else self.content_type.validation_attempted

    @staticmethod
    def is_simple():
        return False

    @staticmethod
    def is_complex():
        return True

    def is_empty(self):
        if self.name == XSD_ANY_TYPE:
            return False
        elif self.open_content and self.open_content.mode != 'none':
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

    def is_valid(self, source, use_defaults=True, namespaces=None):
        if hasattr(source, 'tag'):
            return super(XsdComplexType, self).is_valid(source, use_defaults, namespaces)
        elif isinstance(self.content_type, XsdSimpleType):
            return self.content_type.is_valid(source, use_defaults, namespaces)
        else:
            return self.mixed or self.base_type is not None and \
                self.base_type.is_valid(source, use_defaults, namespaces)

    def is_derived(self, other, derivation=None):
        if derivation and derivation == self.derivation:
            derivation = None  # derivation mode checked

        if self is other:
            return derivation is None
        elif other.name == XSD_ANY_TYPE:
            return True
        elif self.base_type is other:
            return derivation is None  # or self.base_type.derivation == derivation
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
        if getattr(self.base_type, 'parent', None) is not None:
            for obj in self.base_type.iter_components(xsd_classes):
                yield obj

        for obj in filter(lambda x: x.base_type is self, self.assertions):
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

    def has_restriction(self):
        return self.derivation == 'restriction'

    def has_extension(self):
        return self.derivation == 'extension'

    def text_decode(self, text):
        if self.has_simple_content():
            return self.content_type.decode(text, validation='skip')
        else:
            return text

    def decode(self, data, *args, **kwargs):
        if hasattr(data, 'attrib') or self.is_simple():
            return super(XsdComplexType, self).decode(data, *args, **kwargs)
        elif self.has_simple_content():
            return self.content_type.decode(data, *args, **kwargs)
        else:
            raise XMLSchemaDecodeError(self, data, "cannot decode %r data with %r" % (data, self))

    def iter_decode(self, elem, validation='lax', **kwargs):
        """
        Decode an Element instance. A dummy element is created for the type and it's
        used for decode data. Typically used for decoding with xs:anyType when an XSD
        element is not available.

        :param elem: the Element that has to be decoded.
        :param validation: the validation mode. Can be 'lax', 'strict' or 'skip.
        :param kwargs: keyword arguments for the decoding process.
        :return: yields a decoded object, eventually preceded by a sequence of \
        validation or decoding errors.
        """
        xsd_element = self.schema.create_element(name=elem.tag)
        xsd_element.type = self
        for result in xsd_element.iter_decode(elem, validation, **kwargs):
            yield result

    def iter_encode(self, obj, validation='lax', **kwargs):
        """
        Encode XML data. A dummy element is created for the type and it's used for
        encode data. Typically used for encoding with xs:anyType when an XSD element
        is not available.

        :param obj: decoded XML data.
        :param validation: the validation mode: can be 'lax', 'strict' or 'skip'.
        :param kwargs: keyword arguments for the encoding process.
        :return: yields an Element, eventually preceded by a sequence of \
        validation or encoding errors.
        """
        name, value = obj
        xsd_element = self.schema.create_element(name=name)
        xsd_element.type = self

        if isinstance(value, list):
            try:
                results = [x for item in value for x in xsd_element.iter_encode(
                    item, validation, **kwargs
                )]
            except XMLSchemaValueError:
                pass
            else:
                for result in results:
                    yield result
                return

        for result in xsd_element.iter_encode(value, validation, **kwargs):
            yield result


class Xsd11ComplexType(XsdComplexType):
    """
    Class for XSD 1.1 *complexType* definitions.

    ..  <complexType
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
    default_attributes_apply = True

    _CONTENT_TAIL_TAGS = {XSD_ATTRIBUTE_GROUP, XSD_ATTRIBUTE, XSD_ANY_ATTRIBUTE, XSD_ASSERT}

    @property
    def default_attributes(self):
        if self.redefine is not None:
            return self.schema.default_attributes

        for child in filter(lambda x: x.tag == XSD_OVERRIDE, self.schema.root):
            if self.elem in child:
                schema = self.schema.includes[child.attrib['schemaLocation']]
                if schema.override is self.schema:
                    return schema.default_attributes
        else:
            return self.schema.default_attributes

    @property
    def default_open_content(self):
        if self.parent is not None:
            return self.schema.default_open_content

        for child in filter(lambda x: x.tag == XSD_OVERRIDE, self.schema.root):
            if self.elem in child:
                schema = self.schema.includes[child.attrib['schemaLocation']]
                if schema.override is self.schema:
                    return schema.default_open_content
        else:
            return self.schema.default_open_content

    def _parse(self):
        super(Xsd11ComplexType, self)._parse()

        if self.base_type and self.base_type.base_type is self.any_simple_type and \
                self.base_type.derivation == 'extension' and not self.attributes:
            # Derivation from xs:anySimpleType with missing variety.
            # See: http://www.w3.org/TR/xmlschema11-1/#Simple_Type_Definition_details
            msg = "the simple content of {!r} is not a valid simple type in XSD 1.1"
            self.parse_error(msg.format(self.base_type))

        # Add open content to complex content type
        if isinstance(self.content_type, XsdGroup):
            if self.open_content is None:
                assert self.content_type.interleave is None and self.content_type.suffix is None
            elif self.open_content.mode == 'interleave':
                self.content_type.interleave = self.content_type.suffix = self.open_content.any_element
            elif self.open_content.mode == 'suffix':
                self.content_type.suffix = self.open_content.any_element

        # Add inheritable attributes
        if hasattr(self.base_type, 'attributes'):
            for name, attr in self.base_type.attributes.items():
                if attr.inheritable:
                    if name not in self.attributes:
                        self.attributes[name] = attr
                    elif not self.attributes[name].inheritable:
                        self.parse_error("attribute %r must be inheritable")

        if 'defaultAttributesApply' in self.elem.attrib:
            attr = self.elem.attrib['defaultAttributesApply'].strip()
            self.default_attributes_apply = False if attr in {'false', '0'} else True
        else:
            self.default_attributes_apply = True

        # Add default attributes
        if self.default_attributes_apply and isinstance(self.default_attributes, XsdComponent):
            if self.redefine is None and any(k in self.attributes for k in self.default_attributes):
                self.parse_error("at least a default attribute is already declared in the complex type")
            self.attributes.update((k, v) for k, v in self.default_attributes.items())

    def _parse_complex_content_extension(self, elem, base_type):
        # Complex content extension with simple base is forbidden XSD 1.1.
        # For the detailed rule refer to XSD 1.1 documentation:
        #   https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#sec-cos-ct-extends
        if base_type.is_simple() or base_type.has_simple_content():
            self.parse_error("base %r is simple or has a simple content." % base_type, elem)
            base_type = self.any_type

        if 'extension' in base_type.final:
            self.parse_error("the base type is not derivable by extension")

        # Parse openContent
        for group_elem in filter(lambda x: x.tag != XSD_ANNOTATION, elem):
            if group_elem.tag != XSD_OPEN_CONTENT:
                break
            self.open_content = XsdOpenContent(group_elem, self.schema, self)
            try:
                self.open_content.any_element.union(base_type.open_content.any_element)
            except AttributeError:
                pass
        else:
            group_elem = None

        if not base_type.content_type:
            if not base_type.mixed:
                # Empty element-only model extension: don't create a nested sequence group.
                if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                    self.content_type = self.schema.BUILDERS.group_class(group_elem, self.schema, self)
                else:
                    self.content_type = self.schema.create_empty_content_group(
                        parent=self, model=base_type.content_type.model
                    )
            elif base_type.mixed:
                # Empty mixed model extension
                self.content_type = self.schema.create_empty_content_group(self)
                self.content_type.append(self.schema.create_empty_content_group(self.content_type))

                if group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
                    group = self.schema.BUILDERS.group_class(group_elem, self.schema, self.content_type)
                    if not self.mixed:
                        self.parse_error("base has a different content type (mixed=%r) and the "
                                         "extension group is not empty." % base_type.mixed, elem)
                    if group.model == 'all':
                        self.parse_error("cannot extend an empty mixed content with an xs:all")
                else:
                    group = self.schema.create_empty_content_group(self)

                self.content_type.append(group)
                self.content_type.elem.append(base_type.content_type.elem)
                self.content_type.elem.append(group.elem)

        elif group_elem is not None and group_elem.tag in XSD_MODEL_GROUP_TAGS:
            group = self.schema.BUILDERS.group_class(group_elem, self.schema, self)

            if base_type.content_type.model != 'all':
                content_type = self.schema.create_empty_content_group(self)
                content_type.append(base_type.content_type)
                content_type.elem.append(base_type.content_type.elem)

                if group.model == 'all':
                    msg = "xs:all cannot extend a not empty xs:%s"
                    self.parse_error(msg % base_type.content_type.model)
                else:
                    content_type.append(group)
                    content_type.elem.append(group.elem)
            else:
                content_type = self.schema.create_empty_content_group(self, model='all')
                content_type.extend(base_type.content_type)
                content_type.elem.extend(base_type.content_type.elem)

                if not group:
                    pass
                elif group.model != 'all':
                    self.parse_error("cannot extend a not empty 'all' model group with a different model")
                elif base_type.content_type.min_occurs != group.min_occurs:
                    self.parse_error("when extend an xs:all group minOccurs must be the same")
                elif base_type.mixed and not base_type.content_type:
                    self.parse_error("cannot extend an xs:all group with mixed empty content")
                else:
                    content_type.extend(group)
                    content_type.elem.extend(group.elem)

            if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE:
                self.parse_error("base has a different content type (mixed=%r) and the "
                                 "extension group is not empty." % base_type.mixed, elem)

            self.content_type = content_type

        elif not base_type.is_simple() and not base_type.has_simple_content():
            self.content_type = self.schema.create_empty_content_group(self)
            self.content_type.append(base_type.content_type)
            self.content_type.elem.append(base_type.content_type.elem)
            if base_type.mixed != self.mixed and base_type.name != XSD_ANY_TYPE and self.mixed:
                self.parse_error("extended type has a mixed content but the base is element-only", elem)
        else:
            self.content_type = self.schema.create_empty_content_group(self)

        if not self.open_content:
            default_open_content = self.default_open_content
            if default_open_content and \
                    (self.mixed or self.content_type or default_open_content.applies_to_empty):
                self.open_content = default_open_content
            elif base_type.open_content:
                self.open_content = base_type.open_content

        if base_type.open_content and self.open_content is not base_type.open_content:
            if self.open_content.mode == 'none':
                self.open_content = base_type.open_content
            elif not base_type.open_content.is_restriction(self.open_content):
                msg = "{!r} is not an extension of the base type {!r}"
                self.parse_error(msg.format(self.open_content, base_type.open_content))

        self._parse_content_tail(elem, derivation='extension', base_attributes=base_type.attributes)

    def _parse_content_tail(self, elem, **kwargs):
        self.attributes = self.schema.BUILDERS.attribute_group_class(elem, self.schema, self, **kwargs)

        self.assertions = [XsdAssert(e, self.schema, self, self) for e in elem if e.tag == XSD_ASSERT]
        if getattr(self.base_type, 'assertions', None):
            self.assertions.extend(assertion for assertion in self.base_type.assertions)
