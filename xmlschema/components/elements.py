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
from collections import MutableSequence

from ..core import unicode_type, etree_tostring
from ..exceptions import (
    XMLSchemaValidationError, XMLSchemaEncodeError, XMLSchemaParseError
)
from ..qnames import (
    split_reference, get_qname, qname_to_prefixed, local_name,
    XSD_GROUP_TAG, XSD_SEQUENCE_TAG, XSD_ALL_TAG, XSD_CHOICE_TAG
)
from ..xsdbase import (
    check_type, get_xsd_attribute, get_xsd_bool_attribute,
    xsd_lookup, XsdComponent, check_value, ParticleMixin
)
from .. import xpath

from .datatypes import XsdSimpleType
from .attributes import XsdAttributeGroup


class XsdElement(XsdComponent, ParticleMixin):
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

    def iter_decode(self, elem, validate=True, **kwargs):
        dict_class = kwargs.get('dict_class', dict)
        use_defaults = kwargs.get('use_defaults', False)
        text_key = kwargs.get('text_key', '#text')
        attribute_prefix = kwargs.get('attribute_prefix', '@')

        result_dict = dict_class()
        if elem.attrib:
            for result in self.attributes.iter_decode(elem, validate, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    if result.elem is None:
                        result.schema_elem = self.elem
                        result.elem = elem
                    yield result
                else:
                    result_dict.update([(u'%s%s' % (attribute_prefix, k), v) for k, v in result])
                    break

        result = None
        if len(elem):
            for result in self.type.iter_decode(elem, validate, result_dict=result_dict, **kwargs):
                if isinstance(result, XMLSchemaValidationError):
                    if result.elem is None:
                        result.schema_elem = self.elem
                        result.elem = elem
                    yield result
                else:
                    result = None
                    break
            else:
                if not kwargs.get('skip_errors'):
                    # The subelements are not decodable then transform them to a string.
                    result = '\n'.join([etree_tostring(child) for child in elem]) or None
                else:
                    result = None

        elif elem.text is not None:
            if use_defaults:
                text = elem.text or self.default
            else:
                text = elem.text

            if not self.type.is_simple():
                result = unicode_type(text)
            else:
                for result in self.type.iter_decode(text, validate, result_dict=result_dict, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        if result.elem is None:
                            result.schema_elem = self.elem
                            result.elem = elem
                        yield result
                    else:
                        break
                else:
                    if not kwargs.get('skip_errors'):
                        result = unicode_type(text)
                    else:
                        result = None

        if result_dict:
            if result or result is False:
                result_dict[text_key] = result
            yield result_dict
        elif result or result is False:
            yield result
        else:
            yield None

    def iter_encode(self, obj, validate=True, **kwargs):
        for result in self.type.iter_encode(obj, validate, **kwargs):
            yield result
            if isinstance(result, XMLSchemaEncodeError):
                return

    def iter_model(self, elem, index):
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
                if tag is None or xsd_element.name == tag or (
                    not xsd_element.qualified and local_name(xsd_element.name) == tag
                ):
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

        qname, namespace = split_reference(elem.tag, namespaces=self.namespaces)
        if self._is_namespace_allowed(namespace, self.namespace):
            try:
                xsd_element = xsd_lookup(qname, self.schema.maps.base_elements)
            except LookupError:
                if self.process_contents == 'strict' and validate:
                    yield XMLSchemaValidationError(self, elem, "element %r not found." % elem.tag)
            else:
                for result in xsd_element.iter_decode(elem, validate, **kwargs):
                    yield result

        elif validate:
            yield XMLSchemaValidationError(self, elem, "element %r not allowed here." % elem.tag)

    def iter_model(self, elem, index):
        qname, namespace = split_reference(elem.tag, namespaces=self.namespaces)
        if not self._is_namespace_allowed(namespace, self.namespace):
            return

        try:
            xsd_element = xsd_lookup(qname, self.schema.maps.elements)
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

    def iter_decode(self, obj, validate=True, **kwargs):
        for result in self.content_type.iter_decode(obj, validate, **kwargs):
            yield result

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
        self.parsed = initlist is not None
        self._group = []
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
        check_type(item, XsdGroup)
        if self.model is None:
            raise XMLSchemaParseError(u"cannot add items when the group model is None.", self)
        self._group[i] = item

    def __delitem__(self, i):
        del self._group[i]

    def __len__(self):
        return len(self._group)

    def insert(self, i, item):
        self._group.insert(i, item)

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

        # Validate character data between tags
        if validate and not self.mixed:
            if not_whitespace(elem.text) or any([not_whitespace(child.tail) for child in elem]):
                if len(self) == 1 and isinstance(self[0], XsdAnyElement):
                    pass  # [XsdAnyElement()] is equivalent to an empty complexType declaration
                else:
                    yield XMLSchemaValidationError(
                        self, elem, "character data between child elements not allowed!"
                    )

        # Decode elements
        dict_class = kwargs.get('dict_class', dict)
        force_list = kwargs.get('force_list', True)
        namespaces = kwargs.get('namespaces')
        result_dict = kwargs.pop('result_dict', dict_class())
        for obj in self.iter_model(elem):
            if isinstance(obj, XMLSchemaValidationError):
                if validate:
                    yield obj
            elif isinstance(obj, tuple):
                xsd_element, child = obj
                for result in xsd_element.iter_decode(child, validate, **kwargs):
                    if isinstance(result, XMLSchemaValidationError):
                        yield result
                        continue
                    elif child.tag[0] == '{' and namespaces:
                        key = qname_to_prefixed(child.tag, namespaces)
                    else:
                        key = child.tag

                    # Set or append the result
                    try:
                        result_dict[key].append(result)
                    except KeyError:
                        if force_list and xsd_element.max_occurs != 1:
                            result_dict[key] = [result]
                        else:
                            result_dict[key] = result
                    except AttributeError:
                        result_dict[key] = [result_dict[key], result]

        yield result_dict

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
                        group = [e for e in self.iter_elements()]
                        yield XMLSchemaValidationError(
                            self, elem, reason % (elem[model_index].tag, [e.name for e in group])
                        )
                    elif model_occurs:
                        yield index
                    return

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
