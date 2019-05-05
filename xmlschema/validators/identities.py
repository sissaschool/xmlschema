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
"""
This module contains classes for other XML Schema identity constraints.
"""
from __future__ import unicode_literals
import re
from collections import Counter
from elementpath import Selector, XPath1Parser, ElementPathSyntaxError, ElementPathKeyError

from ..exceptions import XMLSchemaValueError
from ..qnames import XSD_UNIQUE, XSD_KEY, XSD_KEYREF, XSD_SELECTOR, XSD_FIELD
from ..helpers import get_qname, qname_to_prefixed
from ..etree import etree_getpath
from ..regex import get_python_regex

from .exceptions import XMLSchemaValidationError
from .xsdbase import XsdComponent

XSD_IDENTITY_XPATH_SYMBOLS = {
    'processing-instruction', 'following-sibling', 'preceding-sibling',
    'ancestor-or-self', 'attribute', 'following', 'namespace', 'preceding',
    'ancestor', 'position', 'comment', 'parent', 'child', 'false', 'text', 'node',
    'true', 'last', 'not', 'and', 'mod', 'div', 'or', '..', '//', '!=', '<=', '>=', '(', ')',
    '[', ']', '.', '@', ',', '/', '|', '*', '-', '=', '+', '<', '>', ':', '(end)', '(name)',
    '(string)', '(float)', '(decimal)', '(integer)', '::'
}


class XsdIdentityXPathParser(XPath1Parser):
    symbol_table = {k: v for k, v in XPath1Parser.symbol_table.items() if k in XSD_IDENTITY_XPATH_SYMBOLS}
    SYMBOLS = XSD_IDENTITY_XPATH_SYMBOLS


XsdIdentityXPathParser.build_tokenizer()


class XsdSelector(XsdComponent):
    _admitted_tags = {XSD_SELECTOR}
    pattern = re.compile(get_python_regex(
        r"(\.//)?(((child::)?((\i\c*:)?(\i\c*|\*)))|\.)(/(((child::)?((\i\c*:)?(\i\c*|\*)))|\.))*(\|"
        r"(\.//)?(((child::)?((\i\c*:)?(\i\c*|\*)))|\.)(/(((child::)?((\i\c*:)?(\i\c*|\*)))|\.))*)*"
    ))

    def __init__(self, elem, schema, parent):
        super(XsdSelector, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdSelector, self)._parse()
        try:
            self.path = self.elem.attrib['xpath']
        except KeyError:
            self.parse_error("'xpath' attribute required:", self.elem)
            self.path = "*"
        else:
            if not self.pattern.match(self.path.replace(' ', '')):
                self.parse_error("Wrong XPath expression for an xs:selector")

        try:
            self.xpath_selector = Selector(self.path, self.namespaces, parser=XsdIdentityXPathParser)
        except (ElementPathSyntaxError, ElementPathKeyError) as err:
            self.parse_error(err)
            self.xpath_selector = Selector('*', self.namespaces, parser=XsdIdentityXPathParser)

        # XSD 1.1 xpathDefaultNamespace attribute
        if self.schema.XSD_VERSION > '1.0':
            if 'xpathDefaultNamespace' in self.elem.attrib:
                self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
            else:
                self.xpath_default_namespace = self.schema.xpath_default_namespace

    def __repr__(self):
        return '%s(path=%r)' % (self.__class__.__name__, self.path)

    @property
    def built(self):
        return True


class XsdFieldSelector(XsdSelector):
    _admitted_tags = {XSD_FIELD}
    pattern = re.compile(get_python_regex(
        r"(\.//)?((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)/)*((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)|"
        r"((attribute::|@)((\i\c*:)?(\i\c*|\*))))(\|(\.//)?((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)/)*"
        r"((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)|((attribute::|@)((\i\c*:)?(\i\c*|\*)))))*"
    ))


class XsdIdentity(XsdComponent):
    def __init__(self, elem, schema, parent):
        super(XsdIdentity, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdIdentity, self)._parse()
        elem = self.elem
        try:
            self.name = get_qname(self.target_namespace, elem.attrib['name'])
        except KeyError:
            self.parse_error("missing required attribute 'name'", elem)
            self.name = None

        child = self._parse_component(elem, required=False, strict=False)
        if child is None or child.tag != XSD_SELECTOR:
            self.parse_error("missing 'selector' declaration.", elem)
            self.selector = None
        else:
            self.selector = XsdSelector(child, self.schema, self)

        self.fields = []
        for child in self._iterparse_components(elem, start=int(self.selector is not None)):
            if child.tag == XSD_FIELD:
                self.fields.append(XsdFieldSelector(child, self.schema, self))
            else:
                self.parse_error("element %r not allowed here:" % child.tag, elem)

    def iter_elements(self):
        for xsd_element in self.selector.xpath_selector.iter_select(self.parent):
            yield xsd_element

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


class XsdUnique(XsdIdentity):
    _admitted_tags = {XSD_UNIQUE}


class XsdKey(XsdIdentity):
    _admitted_tags = {XSD_KEY}


class XsdKeyref(XsdIdentity):
    """
    Implementation of xs:keyref.

    :ivar refer: reference to a *xs:key* declaration that must be in the same element \
    or in a descendant element.
    """
    _admitted_tags = {XSD_KEYREF}
    refer = None
    refer_path = '.'

    def __repr__(self):
        return '%s(name=%r, refer=%r)' % (
            self.__class__.__name__, self.prefixed_name, getattr(self.refer, 'prefixed_name', None)
        )

    def _parse(self):
        super(XsdKeyref, self)._parse()
        try:
            self.refer = self.schema.resolve_qname(self.elem.attrib['refer'])
        except KeyError:
            self.parse_error("missing required attribute 'refer'")
        except ValueError as err:
            self.parse_error(err)

    def parse_refer(self):
        if self.refer is None:
            return  # attribute or key/unique identity constraint missing
        elif isinstance(self.refer, (XsdKey, XsdUnique)):
            return  # referenced key/unique identity constraint already set

        try:
            self.refer = self.parent.constraints[self.refer]
        except KeyError:
            try:
                self.refer = self.maps.constraints[self.refer]
            except KeyError:
                self.parse_error("key/unique identity constraint %r is missing" % self.refer)
                return

        if not isinstance(self.refer, (XsdKey, XsdUnique)):
            self.parse_error("reference to a non key/unique identity constraint %r" % self.refer)
        elif len(self.refer.fields) != len(self.fields):
            self.parse_error("field cardinality mismatch between %r and %r" % (self, self.refer))
        elif self.parent is not self.refer.parent:
            refer_path = self.refer.parent.get_path(ancestor=self.parent)
            if refer_path is None:
                # From a note in par. 3.11.5 Part 1 of XSD 1.0 spec: "keyref identity-constraints may be
                # defined on domains distinct from the embedded domain of the identity-constraint they
                # reference, or the domains may be the same but self-embedding at some depth. In either
                # case the node table for the referenced identity-constraint needs to propagate upwards,
                # with conflict resolution."
                refer_path = self.parent.get_path(ancestor=self.refer.parent, reverse=True)
                if refer_path is None:
                    refer_path = self.parent.get_path(reverse=True) + '/' + self.refer.parent.get_path()

            self.refer_path = refer_path

    def get_refer_values(self, elem):
        values = set()
        for e in elem.iterfind(self.refer_path):
            for v in self.refer.iter_values(e):
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
