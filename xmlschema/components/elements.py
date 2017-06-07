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

from ..core import unicode_type
from ..exceptions import (
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaParseError, XMLSchemaValueError
)
from ..qnames import (
    get_qname, local_name, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG
)
from ..utils import get_namespace
from .. import xpath
from .xsdbase import (
    check_type, get_xsd_attribute, get_xsd_bool_attribute,
    XsdComponent, check_value, ParticleMixin
)
from .attributes import XsdAttributeGroup
from .datatypes import XsdSimpleType


class XsdElement(Sequence, XsdComponent, ParticleMixin):
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
    def __init__(self, name, xsd_type, elem, schema, ref=False, qualified=False):
        super(XsdElement, self).__init__(name, elem, schema)
        self.type = xsd_type
        self.ref = ref
        self.qualified = qualified
        try:
            self.attributes = self.type.attributes
        except AttributeError:
            self.attributes = XsdAttributeGroup(schema=schema)

        if ref and self.substitution_group is not None:
            raise XMLSchemaParseError(
                "a reference can't has 'substitutionGroup' attribute.", self
            )

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
        ParticleMixin.__setattr__(self, name, value)
        if name == "type":
            check_type(value, XsdSimpleType, XsdComplexType)
        elif name == "elem":
            if self.default and self.fixed:
                raise XMLSchemaParseError(
                    "'default' and 'fixed' attributes are mutually exclusive", self
                )
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
        return self._get_derivation_attribute('block', ('extension', 'restriction', 'substitution'))

    @property
    def default(self):
        return self._attrib.get('default', '')

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('extension', 'restriction'))

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

    def has_name(self, name):
        return self.name == name or (not self.qualified and local_name(self.name) == name)

    def iter_decode(self, elem, validate=True, **kwargs):
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
                    if result.elem is None:
                        result.elem, result.schema_elem = elem, self.elem
                    yield result
                else:
                    yield element_decode_hook(elem, self, *result)
                    del result
        else:
            if elem.attrib:
                yield XMLSchemaValidationError(
                    self, elem, "a simple type element can't has attributes."
                )
            if len(elem):
                yield XMLSchemaValidationError(
                    self, elem, "a simple type element can't has child elements."
                )

            if elem.text is None:
                yield None
            else:
                text = elem.text or self.default if use_defaults else elem.text
                for result in self.type.iter_decode(text, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        if result.elem is None:
                            result.elem, result.schema_elem = elem, self.elem
                        yield result
                    else:
                        yield element_decode_hook(elem, self, result)
                        del result

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.type.iter_encode(obj, validate, **kwargs):
            yield result
            if isinstance(result, XMLSchemaEncodeError):
                return

    def iter_model(self, elem, index=0):
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
                    yield (self, elem[index])

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

    def iterfind(self, path, namespaces=None):
        """
        Generate all matching XML Schema element declarations by path.

        :param path: a string having an XPath expression. 
        :param namespaces: an optional mapping from namespace prefix to full name.
        """
        if path[:1] == "/":
            raise SyntaxError("cannot use absolute path on element")
        return xpath.xsd_iterfind(self, path, namespaces)

    def find(self, path, namespaces=None):
        """
        Find first matching XML Schema element declaration by path.

        :param path: a string having an XPath expression.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: The first matching XML Schema element declaration or None if a 
        matching declaration is not found.
        """
        if path[:1] == "/":
            raise SyntaxError("cannot use absolute path on element")
        return next(xpath.xsd_iterfind(self, path, namespaces), None)

    def findall(self, path, namespaces=None):
        """
        Find all matching XML Schema element declarations by path.

        :param path: a string having an XPath expression.
        :param namespaces: an optional mapping from namespace prefix to full name.
        :return: A list of matching XML Schema element declarations or None if a 
        matching declaration is not found.
        """
        if path[:1] == "/":
            raise SyntaxError("cannot use absolute path on element")
        return list(xpath.xsd_iterfind(self, path, namespaces))


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
        super(XsdAnyElement, self).__init__(elem=elem, schema=schema)

    def __setattr__(self, name, value):
        super(XsdAnyElement, self).__setattr__(name, value)
        ParticleMixin.__setattr__(self, name, value)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict'
        )

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

    def iter_model(self, elem, index=0):
        namespace = get_namespace(elem.tag)
        if not self._is_namespace_allowed(namespace, self.namespace):
            return

        try:
            xsd_element = self.schema.maps.lookup_element(elem.tag)
        except LookupError:
            return
        else:
            for obj in xsd_element.iter_model(elem, index):
                yield obj


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
    def __init__(self, content_type, name=None, elem=None, schema=None, attributes=None,
                 derivation=None, mixed=None):
        super(XsdComplexType, self).__init__(name, elem, schema)
        self.content_type = content_type
        self.attributes = attributes or XsdAttributeGroup(schema=schema)
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
        return self._get_derivation_attribute('block', ('extension', 'restriction'))

    @property
    def final(self):
        return self._get_derivation_attribute('final', ('extension', 'restriction'))

    def is_simple(self):
        """Return true if the the type has simple content."""
        return isinstance(self.content_type, XsdSimpleType)

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
        # Decode attributes
        for result in self.attributes.iter_decode(elem, validate, **kwargs):
            if isinstance(result, XMLSchemaValidationError):
                if result.elem is None:
                    result.elem, result.schema_elem = elem, self.elem
                yield result
            else:
                attributes = result
                break
        else:
            # Should be never executed with the default implementation
            attributes = []

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
                        if result.elem is None:
                            result.elem, result.schema_elem = elem, self.elem
                        yield result
                    else:
                        yield (result, attributes)
            else:
                yield (None, attributes)
        else:
            # Decode a complex content element
            for result in self.content_type.iter_decode(elem, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    if result.elem is None:
                        result.elem, result.schema_elem = elem, self.elem
                    yield result
                else:
                    yield (result, attributes)

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.content_type.iter_encode(obj, validate, **kwargs):
            yield result


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
    def __init__(self, name=None, elem=None, schema=None, model=None, mixed=False, initlist=None):
        XsdComponent.__init__(self, name, elem, schema)
        self.model = model
        self.mixed = mixed
        self._group = []
        self.elements = None
        if initlist is not None:
            if isinstance(initlist, type(self._group)):
                self._group[:] = initlist
            elif isinstance(initlist, XsdGroup):
                self._group[:] = initlist._group[:]
            else:
                self._group = list(initlist)

    # Implements the abstract methods of MutableSequence
    def __getitem__(self, i):
        return self._group[i]

    def __setitem__(self, i, item):
        check_type(item, XsdGroup, XsdElement, XsdAnyElement)
        self._group[i] = item
        self.elements = None

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        check_type(item, XsdGroup, XsdElement, XsdAnyElement)
        self._group.insert(i, item)
        self.elements = None

    def __repr__(self):
        return XsdComponent.__repr__(self)

    def __setattr__(self, name, value):
        super(XsdGroup, self).__setattr__(name, value)
        ParticleMixin.__setattr__(self, name, value)
        if name == 'model':
            check_value(value, None, XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_CHOICE_TAG, XSD_ALL_TAG)
        elif name == 'mixed':
            check_value(value, True, False)
        elif name == '_group':
            check_type(value, list)
            for item in value:
                check_type(item, XsdGroup, XsdElement, XsdAnyElement)

    def clear(self):
        del self._group[:]

    def is_emptiable(self):
        return all([item.is_emptiable() for item in self])

    def iter_elements(self):
        for item in self:
            if isinstance(item, (XsdElement, XsdAnyElement)):
                yield item
            elif isinstance(item, XsdGroup):
                for e in item.iter_elements():
                    yield e

    def iter_decode(self, elem, validate=True, **kwargs):
        def not_whitespace(s):
            return s is not None and s.strip()

        skip_errors = kwargs.get('skip_errors', False)
        result_list = []
        cdata_index = 1
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
        for obj in self.iter_model(elem):
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
        yield result_list

    def iter_model(self, elem, index=0):
        if not len(self):
            return  # Skip empty groups!

        model_occurs = 0
        reason = "found tag %r when one of %r expected."
        while index < len(elem):
            model_index = index
            if self.model == XSD_SEQUENCE_TAG:
                for item in self:
                    for obj in item.iter_model(elem, model_index):
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
                        for obj in item.iter_model(elem, model_index):
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
                validated = False
                for item in self:
                    for obj in item.iter_model(elem, model_index):
                        if not isinstance(obj, XMLSchemaValidationError):
                            if isinstance(obj, tuple):
                                yield obj
                                continue
                            validated = True
                            model_index = obj
                        break
                    if validated:
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

    def iter_encode(self, obj, validate=True, **kwargs):
        return


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
