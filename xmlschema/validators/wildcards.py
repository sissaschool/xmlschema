# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains classes for XML Schema wildcards.
"""
from ..namespaces import get_namespace
from ..qnames import XSD_ANY_TAG, XSD_ANY_ATTRIBUTE_TAG
from .parseutils import get_xsd_attribute, get_xsd_namespace_attribute
from .xsdbase import ValidatorMixin, XsdAnnotated, ParticleMixin


class XsdAnyElement(XsdAnnotated, ValidatorMixin, ParticleMixin):
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
    def __init__(self, elem, schema):
        super(XsdAnyElement, self).__init__(elem, schema, is_global=False)

    def _parse(self):
        super(XsdAnyElement, self)._parse()
        self._parse_particle()

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_ANY_TAG}

    @property
    def namespace(self):
        return get_xsd_namespace_attribute(self.elem)

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict'
        )

    def match(self, name):
        return self._is_namespace_allowed(get_namespace(name), self.namespace)

    def iter_decode(self, elem, validation='lax', **kwargs):
        if self.process_contents == 'skip':
            return

        if self.match(elem.tag):
            try:
                xsd_element = self.maps.lookup_base_element(elem.tag)
            except LookupError:
                if self.process_contents == 'strict' and validation != 'skip':
                    yield self._validation_error("element %r not found." % elem.tag, validation, elem)
            else:
                for result in xsd_element.iter_decode(elem, validation, **kwargs):
                    yield result

        elif validation != 'skip':
            yield self._validation_error("element %r not allowed here." % elem.tag, validation, elem)

    def iter_decode_children(self, elem, index=0, validation='lax'):
        model_occurs = 0
        process_contents = self.process_contents
        while True:
            try:
                namespace = get_namespace(elem[index].tag)
            except IndexError:
                if model_occurs == 0 and self.min_occurs > 0:
                    yield self._validation_error(
                        "a tag from %r expected." % self.namespaces, validation, elem
                    )
                yield index
                return
            else:
                if not self._is_namespace_allowed(namespace, self.namespace):
                    yield self._validation_error("%r not allowed." % namespace, validation, elem)

                try:
                    xsd_element = self.maps.lookup_element(elem[index].tag)
                except LookupError:
                    if process_contents == 'strict':
                        yield self._validation_error(
                            "cannot retrieve the schema for %r" % elem[index], validation, elem
                        )
                else:
                    if process_contents != 'skip':
                        for obj in xsd_element.iter_decode_children(elem, index, validation):
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


class XsdAnyAttribute(XsdAnnotated, ValidatorMixin):
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
    def __init__(self, elem, schema):
        super(XsdAnyAttribute, self).__init__(elem, schema, is_global=False)

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_ANY_ATTRIBUTE_TAG}

    @property
    def namespace(self):
        return get_xsd_namespace_attribute(self.elem)

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict',
        )

    def match(self, name):
        return self._is_namespace_allowed(get_namespace(name), self.namespace)

    def iter_decode(self, attrs, validation='lax', **kwargs):
        if self.process_contents == 'skip':
            return

        for name, value in attrs.items():
            if self.match(name):
                try:
                    xsd_attribute = self.maps.lookup_attribute(name)
                except LookupError:
                    if self.process_contents == 'strict':
                        yield self._validation_error("attribute %r not found." % name, validation, attrs)
                else:
                    for result in xsd_attribute.iter_decode(value, validation, **kwargs):
                        yield result
            else:
                yield self._validation_error("attribute %r not allowed." % name, validation, attrs)


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
