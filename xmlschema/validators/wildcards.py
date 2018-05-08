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
from ..namespaces import get_namespace, XSI_NAMESPACE
from ..qnames import XSD_ANY_TAG, XSD_ANY_ATTRIBUTE_TAG
from .exceptions import XMLSchemaChildrenValidationError
from .parseutils import get_xsd_attribute
from .xsdbase import ValidatorMixin, XsdComponent, ParticleMixin


class XsdWildcard(XsdComponent, ValidatorMixin):

    def __init__(self, elem, schema):
        super(XsdWildcard, self).__init__(elem, schema, is_global=False)

    def _parse(self):
        super(XsdWildcard, self)._parse()

        # Parse namespace and processContents
        namespace = get_xsd_attribute(self.elem, 'namespace', default='##any')
        items = namespace.strip().split()
        if len(items) == 1 and items[0] in ('##any', '##all', '##other', '##local', '##targetNamespace'):
            self.namespace = namespace.strip()
        elif not all([s not in ('##any', '##other') for s in items]):
            self._parse_error("wrong value %r for 'namespace' attribute." % namespace)
            self.namespace = '##any'
        else:
            self.namespace = namespace.strip()

        self.process_contents = get_xsd_attribute(
            self.elem, 'processContents', ('lax', 'skip', 'strict'), default='strict'
        )

    def __repr__(self):
        return u'%s(namespace=%r, process_contents=%r)' % (
            self.__class__.__name__, self.namespace, self.process_contents
        )

    @property
    def built(self):
        return True

    def match(self, name):
        return self.is_namespace_allowed(get_namespace(name))

    def is_namespace_allowed(self, namespace):
        if self.namespace == '##any' or namespace == XSI_NAMESPACE:
            return True
        elif self.namespace == '##other':
            return namespace and namespace != self.target_namespace
        else:
            any_namespaces = self.namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces


class XsdAnyElement(XsdWildcard, ParticleMixin):
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
    def _parse(self):
        super(XsdAnyElement, self)._parse()
        self._parse_particle()

    @property
    def admitted_tags(self):
        return {XSD_ANY_TAG}

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
        max_occurs = self.max_occurs
        while True:
            try:
                child = elem[index]
            except TypeError:
                # elem is a lxml.etree.Element and elem[index] is a <class 'lxml.etree._Comment'>:
                # in this case elem[index].tag is a <cyfunction Comment>, not subscriptable. So
                # decode nothing and take the next.
                pass
            except IndexError:
                if validation != 'skip' and model_occurs == 0 and self.min_occurs > 0:
                    error = XMLSchemaChildrenValidationError(
                        self, elem, index, expected="from %r namespace" % self.namespaces
                    )
                    yield self._validation_error(error, validation)
                yield index
                return
            else:
                namespace = get_namespace(child.tag)

                if not self.is_namespace_allowed(namespace):
                    if validation != 'skip' and model_occurs == 0 and self.min_occurs > 0:
                        error = XMLSchemaChildrenValidationError(self, elem, index)
                        yield self._validation_error(error, validation)
                    yield index
                    return

                try:
                    xsd_element = self.maps.lookup_element(child.tag)
                except LookupError:
                    if validation != 'skip' and process_contents == 'strict':
                        yield self._validation_error(
                            "cannot retrieve the schema for %r" % child, validation, elem
                        )
                    yield None, child
                else:
                    if process_contents != 'skip':
                        yield xsd_element, child
                    else:
                        yield None, child

            index += 1
            model_occurs += 1
            if max_occurs is not None and model_occurs >= max_occurs:
                yield index
                return

    def is_restriction(self, other):
        if not ParticleMixin.is_restriction(self, other):
            return False
        return True


class XsdAnyAttribute(XsdWildcard):
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
    @property
    def admitted_tags(self):
        return {XSD_ANY_ATTRIBUTE_TAG}

    def iter_decode(self, attrs, validation='lax', **kwargs):
        if self.process_contents == 'skip':
            return

        for name, value in attrs.items():
            if self.match(name):
                try:
                    xsd_attribute = self.maps.lookup_attribute(name)
                except LookupError:
                    if self.process_contents == 'strict' and validation != 'skip':
                        yield self._validation_error("attribute %r not found." % name, validation, attrs)
                else:
                    for result in xsd_attribute.iter_decode(value, validation, **kwargs):
                        yield result
            elif validation != 'skip':
                yield self._validation_error("attribute %r not allowed." % name, validation, attrs)


class Xsd11Wildcard(XsdWildcard):

    def __repr__(self):
        return u'%s(namespace=%r, process_contents=%r)' % (
            self.__class__.__name__, self.namespace, self.process_contents
        )

    def _parse(self):
        super(Xsd11Wildcard, self)._parse()

        # Parse notNamespace attribute
        try:
            not_namespace = self.elem.attrib['notNamespace'].strip()
        except KeyError:
            self.not_namespace = None
        else:
            if 'namespace' in self.elem.attrib:
                self.not_namespace = None
                self._parse_error("'namespace' and 'notNamespace' attributes are mutually exclusive.")
            elif not_namespace in ('##local', '##targetNamespace'):
                self.not_namespace = not_namespace
            else:
                self.not_namespace = not_namespace.split()

        # Parse notQName attribute
        try:
            not_qname = self.elem.attrib['notQName'].strip()
        except:
            self.not_qname = None
        else:
            if not_qname in ('##defined', '##definedSibling'):
                self.not_qname = not_qname
            else:
                self.not_qname = not_qname.split()

    def is_namespace_allowed(self, namespace):
        if self.namespace == '##any' or namespace == XSI_NAMESPACE:
            return True
        elif self.namespace == '##other':
            return namespace and namespace != self.target_namespace
        else:
            any_namespaces = self.namespace.split()
            if '##local' in any_namespaces and namespace == '':
                return True
            elif '##targetNamespace' in any_namespaces and namespace == self.target_namespace:
                return True
            else:
                return namespace in any_namespaces


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


class XsdOpenContent(XsdComponent):
    """
    Class for XSD 1.1 'openContent' model definitions.

    <openContent
      id = ID
      mode = (none | interleave | suffix) : interleave
      {any attributes with non-schema namespace . . .}>
      Content: (annotation?), (any?)
    </openContent>
    """
    def __init__(self, elem, schema):
        super(XsdOpenContent, self).__init__(elem, schema, is_global=False)
        self.mode = get_xsd_attribute(
            self.elem, 'mode', enumerate=('none', 'interleave', 'suffix'), default='interleave'
        )
