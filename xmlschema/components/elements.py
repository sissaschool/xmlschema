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
from collections import Sequence, MutableSequence

from ..core import unicode_type, etree_element, ElementData
from ..exceptions import (
    XMLSchemaValidationError, XMLSchemaParseError, XMLSchemaValueError,
    XMLSchemaEncodeError, XMLSchemaNotBuiltError
)
from ..qnames import (
    get_qname, local_name, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG,
    XSD_CHOICE_TAG, XSD_COMPLEX_TYPE_TAG, XSD_ANY_TYPE, XSD_ELEMENT_TAG
)
from ..utils import get_namespace, listify_update
from ..xpath import XPathMixin
from .xsdbase import (
    check_tag, get_xsd_attribute, get_xsd_bool_attribute,
    get_xsd_derivation_attribute, XsdComponent, ParticleMixin
)
from xmlschema.utils import check_type, check_value
from .attributes import XsdAttributeGroup
from .datatypes import XsdSimpleType


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

    def __init__(self, name, xsd_type, elem, schema, ref=False, qualified=False, is_global=False):
        super(XsdElement, self).__init__(name, elem, schema, is_global)
        self.type = xsd_type
        self.ref = ref
        self.qualified = qualified
        try:
            self.attributes = self.type.attributes
        except AttributeError:
            self.attributes = XsdAttributeGroup(schema=schema)

        if ref and self.substitution_group is not None:
            self.schema.errors.append(XMLSchemaParseError(
                "a reference can't has 'substitutionGroup' attribute.", self
            ))

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
            check_type(value, XsdSimpleType, XsdComplexType)
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
        skip_errors = kwargs.get('skip_errors', False)
        element_decode_hook = kwargs.get('element_decode_hook')
        if element_decode_hook is None:
            element_decode_hook = self.schema.get_converter().element_decode
            kwargs['element_decode_hook'] = element_decode_hook
        use_defaults = kwargs.get('use_defaults', False)

        if isinstance(self.type, XsdComplexType):
            if use_defaults and self.type.is_simple():
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

        if isinstance(self.type, XsdComplexType):
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


class XsdAnyElement(XsdComponent, ParticleMixin):
    """
    Class for XSD 1.0 'any' declarations.

    <any
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )  : ##any
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </any>
    """
    def __init__(self, elem=None, schema=None):
        self.name = None
        super(XsdAnyElement, self).__init__(elem=elem, schema=schema)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict'
        )

    def check(self):
        if self.checked:
            return
        super(XsdAnyElement, self).check()
        if self.process_contents != 'strict' and self.elem is not None:
            self._valid = True

    def iter_decode(self, elem, validate=True, **kwargs):
        if self.process_contents == 'skip':
            return

        namespace = get_namespace(elem.tag)
        if self._is_namespace_allowed(namespace, self.namespace):
            try:
                xsd_element = self.schema.maps.lookup_base_element(elem.tag)
            except LookupError:
                if self.process_contents == 'strict' and validate:
                    yield XMLSchemaValidationError(self, elem, "element %r not found." % elem.tag)
            else:
                for result in xsd_element.iter_decode(elem, validate, **kwargs):
                    yield result

        elif validate:
            yield XMLSchemaValidationError(self, elem, "element %r not allowed here." % elem.tag)

    def iter_decode_children(self, elem, index=0):
        model_occurs = 0
        process_contents = self.process_contents
        while True:
            try:
                namespace = get_namespace(elem[index].tag)
            except IndexError:
                if model_occurs == 0 and self.min_occurs > 0:
                    yield XMLSchemaValidationError(self, elem, "a tag from %r expected." % self.namespaces)
                yield index
                return
            else:
                if not self._is_namespace_allowed(namespace, self.namespace):
                    yield XMLSchemaValidationError(self, elem, "%r not allowed." % namespace)

                try:
                    xsd_element = self.schema.maps.lookup_element(elem[index].tag)
                except LookupError:
                    if process_contents == 'strict':
                        yield XMLSchemaValidationError(
                            self, elem, "cannot retrieve the schema for %r" % elem[index]
                        )
                else:
                    if process_contents != 'skip':
                        for obj in xsd_element.iter_decode_children(elem, index):
                            yield obj

            index += 1
            model_occurs += 1
            if self.max_occurs is not None and model_occurs >= self.max_occurs:
                yield index
                return



class Xsd11AnyElement(XsdAnyElement):
    """
    Class for XSD 1.1 'any' declarations.

    <any
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      namespace = ((##any | ##other) | List of (anyURI | (##targetNamespace | ##local)) )
      notNamespace = List of (anyURI | (##targetNamespace | ##local))
      notQName = List of (QName | (##defined | ##definedSibling))
      processContents = (lax | skip | strict) : strict
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?)
    </any>
    """
    pass


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
    FACTORY_KWARG = 'complex_type_factory'
    XSD_GLOBAL_TAG = XSD_COMPLEX_TYPE_TAG

    def __init__(self, content_type, attributes, name=None, elem=None, schema=None,
                 derivation=None, mixed=None, is_global=False):
        super(XsdComplexType, self).__init__(name, elem, schema, is_global)
        self.content_type = content_type
        self.attributes = attributes
        if mixed is not None:
            self.mixed = mixed
        else:
            self.mixed = get_xsd_bool_attribute(self.elem, 'mixed', default=False)
        self.derivation = derivation

    def __setattr__(self, name, value):
        super(XsdComplexType, self).__setattr__(name, value)
        if name == "content_type":
            check_type(value, XsdSimpleType, XsdComplexType, XsdGroup)
        elif name == 'attributes':
            check_type(value, XsdAttributeGroup)
        elif name == 'elem':
            getattr(self, 'abstract')
            getattr(self, 'block')
            getattr(self, 'final')

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

    @property
    def built(self):
        if not self.attributes.built or not self.content_type.built:
            return False
        return super(XsdComplexType, self).built

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

    def is_simple(self):
        """Return true if the the type has simple content."""
        return isinstance(self.content_type, XsdSimpleType)

    @staticmethod
    def get_facet(*args, **kwargs):
        return None

    def admit_simple_restriction(self):
        if 'restriction' in self.final:
            return False
        else:
            return self.mixed and (
                not isinstance(self.content_type, XsdGroup) or self.content_type.is_emptiable()
            )

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


class XsdGroup(MutableSequence, XsdComponent, ParticleMixin):
    """
    A class for XSD 'group', 'choice', 'sequence' definitions and
    XSD 1.0 'all' definitions.

    <group
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      name = NCName
      ref = QName
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (all | choice | sequence)?)
    </group>

    <all
      id = ID
      maxOccurs = 1 : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, element*)
    </all>

    <choice
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </choice>

    <sequence
      id = ID
      maxOccurs = (nonNegativeInteger | unbounded)  : 1
      minOccurs = nonNegativeInteger : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | group | choice | sequence | any)*)
    </sequence>
    """
    FACTORY_KWARG = 'group_factory'
    XSD_GLOBAL_TAG = XSD_GROUP_TAG

    def __init__(self, name=None, elem=None, schema=None, model=None,
                 mixed=False, length=None, is_global=False, initlist=None):
        XsdComponent.__init__(self, name, elem, schema, is_global)
        self.model = model
        self.mixed = mixed
        self._group = []
        self.length = length
        self.elements = None
        if initlist is not None:
            if isinstance(initlist, type(self._group)):
                self._group[:] = initlist
            elif isinstance(initlist, XsdGroup):
                self._group[:] = initlist._group[:]
            else:
                self._group = list(initlist)
            self.length = max([len(self), length or 0])

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        if isinstance(item, tuple):
            print(item)
            # import pdb
            # pdb.set_trace()
            raise XMLSchemaNotBuiltError("element not built", obj=item)
        check_type(item, XsdGroup, XsdElement, XsdAnyElement)
        self._group[i] = item
        self.elements = None

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        check_type(item, tuple, XsdGroup, XsdElement, XsdAnyElement)
        self._group.insert(i, item)
        self.elements = None

    def __repr__(self):
        return XsdComponent.__repr__(self)

    def __setattr__(self, name, value):
        if name == 'elem' and value is not None:
            if self.name is None:
                check_tag(value, XSD_COMPLEX_TYPE_TAG, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG)
            else:
                check_tag(value, XSD_GROUP_TAG)
                # Check maxOccurs and minOccurs: not allowed
        elif name == 'model':
            check_value(value, None, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG)
            model = getattr(self, 'model', None)
            if model is not None and value != model:
                import pdb
                pdb.set_trace()
                raise XMLSchemaValueError("cannot change a valid group model: %r" % value)
        elif name == 'mixed':
            check_value(value, True, False)
        elif name == '_group':
            check_type(value, list)
            for item in value:
                check_type(item, XsdGroup, XsdElement, XsdAnyElement)
        super(XsdGroup, self).__setattr__(name, value)

    def iter_components(self, xsd_classes=None):
        for obj in super(XsdGroup, self).iter_components(xsd_classes):
            yield obj
        for item in self:
            if 'ref' in item.elem.attrib:
                if xsd_classes is None or isinstance(item, xsd_classes):
                    yield item
            else:
                try:
                    for obj in item.iter_components(xsd_classes):
                        yield obj
                except AttributeError:
                    pass

    @property
    def built(self):
        if self.model is None:
            if self.length == 0 and not self:
                return True
            else:
                return False
        elif self.length is None or len(self) < self.length:
            return False
        else:
            for item in self:
                if isinstance(item, (XsdElement, tuple)):
                    continue
                if not item.built:
                    return False
            return super(XsdGroup, self).built

    def check(self):
        if self.checked:
            return
        super(XsdGroup, self).check()

        for item in self:
            if not isinstance(item, (XsdElement, XsdGroup, XsdAnyElement)):
                self._valid = False
                return
            item.check()

        if any([e.valid is False for e in self]):
            self._valid = False
        elif self.valid is not False and any([e.valid is None for e in self]):
            self._valid = None

    def clear(self):
        del self._group[:]

    def is_empty(self):
        return self.model is None and self.length == 0

    def is_emptiable(self):
        return self.is_empty() or all([item.is_emptiable() for item in self])

    def iter_elements(self):
        for item in self:
            if isinstance(item, (XsdElement, XsdAnyElement)):
                yield item
            elif isinstance(item, XsdGroup):
                for e in item.iter_elements():
                    yield e

    def iter_decode(self, elem, validate=True, **kwargs):
        """
        Generator method for decoding complex content elements. A list of 3-tuples
        (key, decoded data, decoder) is returned, eventually preceded by a sequence
        of validation/decode errors (decode errors only if the optional argument
        *validate* is `False`).
        """
        def not_whitespace(s):
            return s is not None and s.strip()

        skip_errors = kwargs.get('skip_errors', False)
        result_list = []
        cdata_index = 1  # keys for CDATA sections are positive integers
        if validate and not self.mixed:
            # Validate character data between tags
            if not_whitespace(elem.text) or any([not_whitespace(child.tail) for child in elem]):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] is equivalent to an empty complexType declaration
                else:
                    if skip_errors:
                        cdata_index = 0
                    cdata_msg = "character data between child elements not allowed!"
                    yield XMLSchemaValidationError(self, elem, cdata_msg)

        if cdata_index and elem.text is not None:
            text = unicode_type(elem.text.strip())
            if text:
                result_list.append((cdata_index, text, None))
                cdata_index += 1

        # Decode child elements
        index = 0
        repeat = 0
        while index < len(elem):
            repeat += 1
            if repeat > 10:
                print ("ITER #%d" % repeat, index, len(elem), self)
                break
                # import pdb
                # pdb.set_trace()
            for obj in self.iter_decode_children(elem, index=index):
                if isinstance(obj, XMLSchemaValidationError):
                    if validate:
                        yield obj
                elif isinstance(obj, tuple):
                    xsd_element, child = obj
                    for result in xsd_element.iter_decode(child, validate, **kwargs):
                        if isinstance(result, XMLSchemaValidationError):
                            if validate:
                                yield result
                        else:
                            result_list.append((child.tag, result, xsd_element))
                    if cdata_index and elem.tail is not None:
                        tail = unicode_type(elem.tail.strip())
                        if tail:
                            result_list.append((cdata_index, tail, None))
                            cdata_index += 1
                elif obj < len(elem) - 1:
                    print("Invalid", obj, index)
                    yield XMLSchemaValidationError(
                        self, elem,
                        reason="Invalid content was found starting with element %r. "
                               "No child element is expected at this point." % elem[obj].tag
                    )
                    index = obj + 1
                    break
                else:
                    if index == obj:
                        stop = True
                    index = obj
                    break
            else:
                pass
                #print("Niente numero!!!")
        yield result_list

    def iter_encode(self, data, validate=True, **kwargs):
        skip_errors = kwargs.get('skip_errors', False)
        children = []
        children_map = {}
        level = kwargs.get('level', 0)
        indent = kwargs.get('indent', None)
        padding = (u'\n' + u' ' * indent * level) if indent is not None else None
        text = padding
        listify_update(children_map, [(e.name, e) for e in self.elements])
        if self.target_namespace:
            listify_update(children_map, [(local_name(e.name), e) for e in self.elements if not e.qualified])

        try:
            for name, value in data:
                if isinstance(name, int):
                    if children:
                        children[-1].tail = padding + value + padding
                    else:
                        text = padding + value + padding
                else:
                    try:
                        xsd_element = children_map[name]
                    except KeyError:
                        yield XMLSchemaValidationError(
                            self, obj=value, reason='%r does not match any declared element.' % name
                        )
                    else:
                        for result in xsd_element.iter_encode(value, validate, **kwargs):
                            if isinstance(result, XMLSchemaValidationError):
                                yield result
                            else:
                                children.append(result)
        except ValueError:
            yield XMLSchemaEncodeError(
                self,
                obj=data,
                encoder=self,
                reason='%r does not match content.' % data
            )

        if indent and level:
            if children:
                children[-1].tail = children[-1].tail[:-indent]
            else:
                text = text[:-indent]
        yield text, children

    def iter_decode_children(self, elem, index=0):
        if not len(self):
            return  # Skip empty groups!

        model_occurs = 0
        reason = "found tag %r when one of %r expected."
        while index < len(elem):
            model_index = index
            if self.model == XSD_SEQUENCE_TAG:
                for item in self:
                    for obj in item.iter_decode_children(elem, model_index):
                        if isinstance(obj, XMLSchemaValidationError):
                            if model_occurs == 0 and self.min_occurs > 0:
                                yield obj
                            elif model_occurs:
                                yield index
                            return
                        elif isinstance(obj, tuple):
                            yield obj
                        else:
                            model_index = obj

            elif self.model == XSD_ALL_TAG:
                group = [e for e in self]
                while group:
                    for item in group:
                        for obj in item.iter_decode_children(elem, model_index):
                            if isinstance(obj, tuple):
                                yield obj
                            elif isinstance(obj, int):
                                model_index = obj
                                break
                        else:
                            continue
                        break
                    else:
                        if model_occurs == 0 and self.min_occurs > 0:
                            yield XMLSchemaValidationError(
                                self, elem, reason % (elem[model_index].tag, [e.name for e in group])
                            )
                        elif model_occurs:
                            yield index
                        return
                    group.remove(item)

            elif self.model == XSD_CHOICE_TAG:
                matched_choice = False
                for item in self:
                    for obj in item.iter_decode_children(elem, model_index):
                        if not isinstance(obj, XMLSchemaValidationError):
                            if isinstance(obj, tuple):
                                yield obj
                                continue
                            if model_index < obj:
                                matched_choice = True
                                model_index = obj
                        break
                    if matched_choice:
                        break
                else:
                    if model_occurs == 0 and self.min_occurs > 0:
                        tags = [e.name for e in self.iter_elements()]
                        yield XMLSchemaValidationError(
                            self, elem, reason % (elem[model_index].tag, tags)
                        )
                    elif model_occurs:
                        yield index
                    return
            else:
                raise XMLSchemaValueError("the group %r has no model!" % self)

            model_occurs += 1
            index = model_index
            if self.max_occurs is not None and model_occurs >= self.max_occurs:
                yield index
                return
        else:
            yield index


class Xsd11Group(XsdGroup):
    """
    A class for XSD 'group', 'choice', 'sequence' definitions and 
    XSD 1.1 'all' definitions.

    <all
      id = ID
      maxOccurs = (0 | 1) : 1
      minOccurs = (0 | 1) : 1
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?, (element | any | group)*)
    </all>
    """
    pass
