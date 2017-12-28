# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2017, SISSA (International School for Advanced Studies).
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
from ..exceptions import XMLSchemaValueError
from ..etree import etree_getpath
from ..qnames import (get_qname, reference_to_qname, XSD_UNIQUE_TAG, XSD_KEY_TAG,
                      XSD_KEYREF_TAG, XSD_SELECTOR_TAG, XSD_FIELD_TAG)
from ..xpath import XPathParser

from .exceptions import XMLSchemaParseError, XMLSchemaValidationError
from .xsdbase import XsdAnnotated


class XsdPathSelector(XsdAnnotated):

    def __init__(self, elem, schema):
        super(XsdPathSelector, self).__init__(elem, schema)

    def _parse(self):
        super(XsdPathSelector, self)._parse()
        try:
            self.path = self.elem.attrib['xpath']
        except KeyError:
            self._parse_error("'xpath' attribute required:", self.elem)
            self.path = "*"

        parser = XPathParser(self.path, self.namespaces)
        try:
            self._selector = parser.parse()
        except XMLSchemaParseError as err:
            self._parse_error("invalid XPath expression: %s" % str(err), self.elem)
            self._selector = XPathParser("*").parse()

    def __repr__(self):
        return u"<%s %r at %#x>" % (self.__class__.__name__, self.path, id(self))

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_SELECTOR_TAG, XSD_FIELD_TAG}

    def iter_select(self, context):
        return self._selector.iter_select(context)


class XsdConstraint(XsdAnnotated):
    def __init__(self, elem, schema, parent):
        super(XsdConstraint, self).__init__(elem, schema)
        self.parent = parent

    def _parse(self):
        super(XsdConstraint, self)._parse()
        elem = self.elem
        try:
            self.name = get_qname(self.target_namespace, elem.attrib['name'])
        except KeyError:
            self._parse_error("missing required attribute 'name'", elem)
            self.name = None

        child = self._parse_component(elem, required=False, strict=False)
        if child is None or child.tag != XSD_SELECTOR_TAG:
            self._parse_error("missing 'selector' declaration.", elem)
            self.selector = None
        else:
            self.selector = XsdPathSelector(child, self.schema)

        self.fields = []
        for child in self._iterparse_components(elem, start=int(self.selector is not None)):
            if child.tag == XSD_FIELD_TAG:
                self.fields.append(XsdPathSelector(child, self.schema))
            else:
                self._parse_error("element %r not allowed here:" % child.tag, elem)

    def get_fields(self, elem, is_key=True, decoders=None):
        """
        Get fields generating the context from selector.
        """
        fields = []
        for k, field in enumerate(self.fields):
            result = list(field.iter_select(elem))
            if not result:
                if is_key:
                    raise XMLSchemaValueError("%r key field must have a value!" % field)
                else:
                    fields.append(None)
            elif len(result) == 1:
                if decoders is None or decoders[k] is None:
                    fields.append(result[0])
                else:
                    fields.append(decoders[k].decode(result[0], validation="skip"))
            else:
                raise XMLSchemaValueError("%r field must identify a single value!" % field)
        return tuple(fields)

    def iter_values(self, elem, is_key=False):
        """
        Iterate field values, excluding empty values (tuples with all `None` values).

        :param elem: Instance XML element.
        :param is_key: If `True` consider an error if a single field is `None`.
        :return: N-Tuple with value fields.
        """
        for e in self.selector.iter_select(elem):
            path = etree_getpath(e, elem)
            context = self.parent.find(path)
            context_fields = self.get_fields(context, is_key=is_key)
            if all(fld is None for fld in context_fields):
                continue

            try:
                fields = self.get_fields(e, is_key=is_key, decoders=context_fields)
            except XMLSchemaValueError as err:
                yield XMLSchemaValidationError(self, e, reason=str(err))
            else:
                if any(fld is not None for fld in fields):
                    yield fields

    @property
    def built(self):
        return self.selector.built and all([f.built for f in self.fields])

    @property
    def admitted_tags(self):
        raise NotImplementedError

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

    def validator(self, context):
        raise NotImplementedError


class XsdUnique(XsdConstraint):

    @property
    def admitted_tags(self):
        return {XSD_UNIQUE_TAG}

    def validator(self, elem):
        values = []
        for e in self.selector.iter_select(elem):
            if type(e) is not type(elem):
                raise XMLSchemaValueError("wrong type for context element %r." % e)
            path = etree_getpath(e, root=elem)
            context = self.parent.find(path)
            context_fields = self.get_fields(context, is_key=False)
            try:
                values.append(self.get_fields(e, is_key=False, decoders=context_fields))
            except XMLSchemaValueError as err:
                yield XMLSchemaValidationError(self, e, reason=str(err))

        for v in values:
            if values.count(v) > 1:
                yield XMLSchemaValidationError(self, elem, reason="duplicated key %r." % v)
                break


class XsdKey(XsdConstraint):

    @property
    def admitted_tags(self):
        return {XSD_KEY_TAG}

    def validator(self, elem):
        values = []
        for v in self.iter_values(elem, is_key=True):
            if isinstance(v, XMLSchemaValidationError):
                yield v
            else:
                values.append(v)

        for v in values:
            if values.count(v) > 1:
                yield XMLSchemaValidationError(self, elem, reason="duplicated key %r." % v)
                break


class XsdKeyref(XsdConstraint):

    def __init__(self, elem, schema, parent):
        self.refer = None
        self.refer_walk = None
        super(XsdKeyref, self).__init__(elem, schema, parent)

    @property
    def admitted_tags(self):
        return {XSD_KEYREF_TAG}

    def _parse(self):
        super(XsdKeyref, self)._parse()
        try:
            self.refer = reference_to_qname(self.elem.attrib['refer'], self.namespaces)
        except KeyError:
            self._parse_error("missing required attribute 'refer'", self.elem)

    def setup_refer(self):
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
                parent_map = self.schema.parent_map
                xsd_element = parent_map[refer.parent]
                while True:
                    if self.refer_walk.append(xsd_element):
                        if xsd_element is self.parent:
                            self.refer_walk.reverse()
                            break
                        elif xsd_element is self.schema:
                            self.refer_walk = None
                            self._parse_error("%r is not defined in a descendant element." % self.refer, self.refer)

        if not isinstance(refer, (XsdKey, XsdUnique)):
            self._parse_error("attribute 'refer' doesn't refer to a key/unique constraint.", self.refer)
            self.refer = None
        else:
            self.refer = refer

    def validator(self, elem):
        if self.refer is None:
            return

        # Get
        values = []
        for v in self.iter_values(elem, is_key=False):
            if isinstance(v, XMLSchemaValidationError):
                yield v
            else:
                values.append(v)

        if not values:
            return

        # Get key/unique values
        refer_elem = elem
        for xsd_element in self.refer_walk:
            for child in refer_elem:
                if xsd_element.match(child.tag):
                    refer_elem = child
                    break
            else:
                yield XMLSchemaValidationError(self, elem, reason="Missing key reference %r" % self.refer)
                return

        key_values = set()
        for v in self.refer.iter_values(refer_elem, is_key=isinstance(refer_elem, XsdKey)):
            if not isinstance(v, XMLSchemaValidationError):
                key_values.add(v)

        for v in values:
            if v not in key_values:
                yield XMLSchemaValidationError(
                    validator=self,
                    obj=elem,
                    reason="Key %r with value %r not found for identity constraint "
                           "of element %r." % (self.name, v, elem.tag)
                )
