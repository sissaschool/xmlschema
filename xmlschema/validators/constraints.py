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
This module contains classes for other XML Schema constraints.
"""
from __future__ import unicode_literals
from collections import Counter
from elementpath import Selector, XPath1Parser, ElementPathSyntaxError

from ..exceptions import XMLSchemaValueError
from ..etree import etree_getpath
from ..qnames import (
    get_qname, prefixed_to_qname, qname_to_prefixed, XSD_UNIQUE_TAG,
    XSD_KEY_TAG, XSD_KEYREF_TAG, XSD_SELECTOR_TAG, XSD_FIELD_TAG
)

from .exceptions import XMLSchemaValidationError
from .parseutils import get_xpath_default_namespace
from .xsdbase import XsdComponent

XSD_CONSTRAINTS_XPATH_SYMBOLS = {
    'processing-instruction', 'descendant-or-self', 'following-sibling', 'preceding-sibling',
    'ancestor-or-self', 'descendant', 'attribute', 'following', 'namespace', 'preceding',
    'ancestor', 'position', 'comment', 'parent', 'child', 'self', 'false', 'text', 'node',
    'true', 'last', 'not', 'and', 'mod', 'div', 'or', '..', '//', '!=', '<=', '>=', '(', ')',
    '[', ']', '.', '@', ',', '/', '|', '*', '-', '=', '+', '<', '>', ':', '(end)', '(name)',
    '(string)', '(float)', '(decimal)', '(integer)'
}


class XsdConstraintXPathParser(XPath1Parser):
    symbol_table = {k: v for k, v in XPath1Parser.symbol_table.items() if k in XSD_CONSTRAINTS_XPATH_SYMBOLS}
    SYMBOLS = XSD_CONSTRAINTS_XPATH_SYMBOLS


XsdConstraintXPathParser.build_tokenizer()


class XsdSelector(XsdComponent):
    admitted_tags = {XSD_SELECTOR_TAG}

    def __init__(self, elem, schema, parent):
        super(XsdSelector, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdSelector, self)._parse()
        try:
            self.path = self.elem.attrib['xpath']
        except KeyError:
            self.parse_error("'xpath' attribute required:", self.elem)
            self.path = "*"

        try:
            self.xpath_selector = Selector(self.path, self.namespaces, parser=XsdConstraintXPathParser)
        except ElementPathSyntaxError as err:
            self.parse_error(err)
            self.xpath_selector = Selector('*', self.namespaces, parser=XsdConstraintXPathParser)

        # XSD 1.1 xpathDefaultNamespace attribute
        if self.schema.XSD_VERSION > '1.0':
            try:
                self._xpath_default_namespace = get_xpath_default_namespace(
                    self.elem, self.namespaces[''], self.target_namespace
                )
            except XMLSchemaValueError as error:
                self.parse_error(str(error))
                self._xpath_default_namespace = self.namespaces['']

    def __repr__(self):
        return '%s(path=%r)' % (self.__class__.__name__, self.path)

    @property
    def built(self):
        return True


class XsdFieldSelector(XsdSelector):
    admitted_tags = {XSD_FIELD_TAG}


class XsdConstraint(XsdComponent):
    def __init__(self, elem, schema, parent):
        super(XsdConstraint, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdConstraint, self)._parse()
        elem = self.elem
        try:
            self.name = get_qname(self.target_namespace, elem.attrib['name'])
        except KeyError:
            self.parse_error("missing required attribute 'name'", elem)
            self.name = None

        child = self._parse_component(elem, required=False, strict=False)
        if child is None or child.tag != XSD_SELECTOR_TAG:
            self.parse_error("missing 'selector' declaration.", elem)
            self.selector = None
        else:
            self.selector = XsdSelector(child, self.schema, self)

        self.fields = []
        for child in self._iterparse_components(elem, start=int(self.selector is not None)):
            if child.tag == XSD_FIELD_TAG:
                self.fields.append(XsdFieldSelector(child, self.schema, self))
            else:
                self.parse_error("element %r not allowed here:" % child.tag, elem)

    def get_fields(self, context, decoders=None):
        """
        Get fields for a schema or instance context element.

        :param context: Context Element or XsdElement
        :param decoders: Context schema fields decoders.
        :return: A tuple with field values. An empty field is replaced by `None`.
        """
        fields = []
        for k, field in enumerate(self.fields):
            result = field.xpath_selector.select(context)
            if not result:
                if isinstance(self, XsdKey):
                    raise XMLSchemaValueError("%r key field must have a value!" % field)
                else:
                    fields.append(None)
            elif len(result) == 1:
                if decoders is None or decoders[k] is None:
                    fields.append(result[0])
                else:
                    fields.append(decoders[k].decode(result[0], validation="skip"))
            else:
                raise XMLSchemaValueError("%r field selects multiple values!" % field)
        return tuple(fields)

    def iter_values(self, elem):
        """
        Iterate field values, excluding empty values (tuples with all `None` values).

        :param elem: Instance XML element.
        :return: N-Tuple with value fields.
        """
        current_path = ''
        xsd_fields = None
        for e in self.selector.xpath_selector.iter_select(elem):
            path = etree_getpath(e, elem)
            if current_path != path:
                # Change the XSD context only if the path is changed
                current_path = path
                xsd_element = self.parent.find(path)
                xsd_fields = self.get_fields(xsd_element)

            if all(fld is None for fld in xsd_fields):
                continue

            try:
                fields = self.get_fields(e, decoders=xsd_fields)
            except XMLSchemaValueError as err:
                yield XMLSchemaValidationError(self, e, reason=str(err))
            else:
                if any(fld is not None for fld in fields):
                    yield fields

    @property
    def built(self):
        return self.selector.built and all([f.built for f in self.fields])

    @property
    def validation_attempted(self):
        if self.built:
            return 'full'
        elif self.selector.built or any([f.built for f in self.fields]):
            return 'partial'
        else:
            return 'none'

    def __call__(self, *args, **kwargs):
        for error in self.validator(*args, **kwargs):
            yield error

    def validator(self, elem):
        values = Counter()
        for v in self.iter_values(elem):
            if isinstance(v, XMLSchemaValidationError):
                yield v
            else:
                values[v] += 1

        for value, count in values.items():
            if count > 1:
                yield XMLSchemaValidationError(self, elem, reason="duplicated value %r." % value)


class XsdUnique(XsdConstraint):
    admitted_tags = {XSD_UNIQUE_TAG}


class XsdKey(XsdConstraint):
    admitted_tags = {XSD_KEY_TAG}


class XsdKeyref(XsdConstraint):
    admitted_tags = {XSD_KEYREF_TAG}

    def __init__(self, elem, schema, parent):
        self.refer = None
        self.refer_walk = None  # Used in case of inner local scope
        super(XsdKeyref, self).__init__(elem, schema, parent)

    def __repr__(self):
        return '%s(name=%r, refer=%r)' % (
            self.__class__.__name__, self.prefixed_name, getattr(self.refer, 'prefixed_name', None)
        )

    def _parse(self):
        super(XsdKeyref, self)._parse()
        try:
            self.refer = prefixed_to_qname(self.elem.attrib['refer'], self.namespaces)
        except KeyError:
            self.parse_error("missing required attribute 'refer'", self.elem)

    def parse_refer(self):
        if self.refer is None:
            return  # attribute or key/unique constraint missing
        elif isinstance(self.refer, XsdConstraint):
            return  # referenced key/unique constraint already set

        try:
            refer = self.parent.constraints[self.refer]
            self.refer_walk = []
        except KeyError:
            try:
                refer = self.schema.constraints[self.refer]
            except KeyError:
                refer = None
            else:
                self.refer_walk = []
                xsd_element = refer.parent.parent
                if xsd_element is None:
                    xsd_element = self.schema
                while True:
                    if self.refer_walk.append(xsd_element):
                        if xsd_element is self.parent:
                            self.refer_walk.reverse()
                            break
                        elif xsd_element is self.schema:
                            self.refer_walk = None
                            self.parse_error("%r is not defined in a descendant element." % self.refer, self.refer)

        if not isinstance(refer, (XsdKey, XsdUnique)):
            self.parse_error("attribute 'refer' doesn't refer to a key/unique constraint.", self.refer)
            self.refer = None
        else:
            self.refer = refer

    def get_refer_values(self, elem):
        refer_elem = elem
        for xsd_element in self.refer_walk:
            for child in refer_elem:
                if xsd_element.is_matching(child.tag):
                    refer_elem = child
                    break
            else:
                raise XMLSchemaValueError("Missing key reference %r" % self.refer)

        values = set()
        for v in self.refer.iter_values(refer_elem):
            if not isinstance(v, XMLSchemaValidationError):
                values.add(v)
        return values

    def validator(self, elem):
        if self.refer is None:
            return

        refer_values = None
        for v in self.iter_values(elem):
            if isinstance(v, XMLSchemaValidationError):
                yield v
                continue

            if refer_values is None:
                try:
                    refer_values = self.get_refer_values(elem)
                except XMLSchemaValueError as err:
                    yield XMLSchemaValidationError(self, elem, str(err))
                    continue

            if v not in refer_values:
                reason = "Key %r with value %r not found for identity constraint of element %r." \
                         % (self.prefixed_name, v, qname_to_prefixed(elem.tag, self.namespaces))
                yield XMLSchemaValidationError(validator=self, obj=elem, reason=reason)
