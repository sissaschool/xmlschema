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
This module contains classes for XML Schema wildcards.
"""
from ..exceptions import XMLSchemaValidationError
from ..utils import get_namespace
from .xsdbase import get_attributes, get_xsd_attribute, XsdComponent, ParticleMixin


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
    def __init__(self, elem, schema=None, parent=None, **options):
        super(XsdAnyElement, self).__init__(elem, schema, is_global=False, parent=parent, **options)

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
    def __init__(self, elem, schema=None, parent=None, **options):
        super(XsdAnyAttribute, self).__init__(elem, schema, is_global=False, parent=parent, **options)

    @property
    def namespace(self):
        return self._get_namespace_attribute()

    @property
    def process_contents(self):
        return get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict',
        )

    def check(self):
        if self.checked:
            return
        super(XsdAnyAttribute, self).check()
        if self.process_contents != 'strict' and self.elem is not None:
            self._valid = True

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
