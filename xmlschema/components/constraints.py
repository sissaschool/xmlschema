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
from ..exceptions import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaValueError, XMLSchemaTypeError
)
from ..qnames import (get_qname, reference_to_qname, XSD_UNIQUE_TAG, XSD_KEY_TAG,
                      XSD_KEYREF_TAG, XSD_SELECTOR_TAG, XSD_FIELD_TAG)
from ..xpath import XPathParser
from .component import XsdAnnotated, XsdComponent


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
        self.context = []
        self.context_fields = []
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

    def set_context(self):
        if not isinstance(self.parent, XsdComponent):
            raise XMLSchemaTypeError("an XsdElement required: %r" % self.parent)
        del self.context[:]
        try:
            self.context = self.get_context(self.parent)
            # FIXME: Descendant paths (//) doesn't work on XSD structures, a context expansion is needed.
        except XMLSchemaValueError as err:
            self.context = []
            self._parse_error(str(err), self.parent)

        del self.context_fields[:]
        for e in self.context:
            try:
                fields = self.get_fields(e)
            except XMLSchemaValueError:
                self.context_fields.append(None)
            else:
                self.context_fields.append(tuple(fields))

        if self.context_fields and all([fields is None for fields in self.context_fields]):
            self._parse_error("empty context fields for %r:" % self, self.elem)

    def get_context(self, elem=None):
        if elem is None:
            return self.context

        if self.selector is None:
            return []
        context = []
        for e in self.selector.iter_select(elem):
            if type(e) is not type(elem):
                raise XMLSchemaValueError("wrong type for context element %r." % e)
            context.append(e)
        return context

    def get_fields(self, elem, is_key=True, decoders=None):
        """
        Get fields generating the context from selector.
        """
        values = []
        for k, field in enumerate(self.fields):
            result = list(field.iter_select(elem))
            if not result:
                if is_key:
                    raise XMLSchemaValueError("%r key field must have a value!" % field)
                else:
                    values.append(None)
            elif len(result) == 1:
                if decoders is None or decoders[k] is None:
                    values.append(result[0])
                else:
                    values.append(decoders[k].decode(result[0], validation="skip"))
            else:
                raise XMLSchemaValueError("%r field must identify a single value!" % field)
        return tuple(values)

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
        for e in self.get_context(elem):
            for i in range(len(self.context)):
                if self.context[i].match(e.tag):
                    try:
                        values.append(self.get_fields(e, is_key=False, decoders=self.context_fields[i]))
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
        for e in self.get_context(elem):
            for i in range(len(self.context)):
                if self.context[i].match(e.tag):
                    try:
                        values.append(self.get_fields(e, is_key=True, decoders=self.context_fields[i]))
                    except XMLSchemaValueError as err:
                        yield XMLSchemaValidationError(self, e, reason=str(err))

        for v in values:
            if values.count(v) > 1:
                yield XMLSchemaValidationError(self, elem, reason="duplicated key %r." % v)
                break


class XsdKeyref(XsdConstraint):

    def __init__(self, elem, schema, parent):
        super(XsdKeyref, self).__init__(elem, schema, parent)
        self.refer_elem = None
        self.refer_path = []

    @property
    def admitted_tags(self):
        return {XSD_KEYREF_TAG}

    def _parse(self):
        super(XsdKeyref, self)._parse()
        try:
            self.refer = reference_to_qname(self.elem.attrib['refer'], self.namespaces)
        except KeyError:
            self._parse_error("missing required attribute 'refer'", self.elem)
            self.refer = None

    def set_context(self):
        super(XsdKeyref, self).set_context()
        del self.refer_path[:]
        if self.refer in self.parent.constraints:
            self.refer_elem = self.parent
        else:
            for descendant in self.parent.iter():
                if self.refer in descendant.constraints():
                    self.refer_elem = refer_elem = descendant
                    self.refer_path.append(refer_elem)
                    parent_map = self.schema.parent_map
                    while True:
                        try:
                            refer_elem = parent_map[refer_elem]
                        except KeyError:
                            del self.refer_path[:]
                            break
                        else:
                            if refer_elem is self.parent:
                                break
                            else:
                                self.refer_path.append(refer_elem)
                    break
            if not self.refer_path:
                self._parse_error("attribute 'refer' doesn't refer to a descendant element.", self.parent)
            else:
                self.refer_path.reverse()

    def validator(self, elem):
        if self.refer is None:
            return

        # Find XML subelement
        refer_elem = elem
        for xsd_element in self.refer_path:
            for child in refer_elem:
                if xsd_element.match(child.tag):
                    refer_elem = child
                    break
            else:
                yield XMLSchemaValidationError(self, elem, reason="Missing key reference %r" % self.refer)
                return

        # Get the keyref values
        key_constraint = self.refer_elem.constraints[self.refer]
        keys = set()
        for e in key_constraint.get_context(refer_elem):
            for i in range(len(key_constraint.context)):
                if key_constraint.context[i].match(e.tag):
                    try:
                        keys.add(key_constraint.get_fields(e, is_key=True, decoders=key_constraint.context_fields[i]))
                    except XMLSchemaValueError:
                        pass

        # Check values with keys
        for e in self.get_context(elem):
            for i in range(len(self.context)):
                if self.context[i].match(e.tag):
                    try:
                        value = self.get_fields(e, is_key=False, decoders=self.context_fields[i])
                    except XMLSchemaValueError as err:
                        yield XMLSchemaValidationError(self, e, reason=str(err))
                    else:
                        if value not in keys:
                            yield XMLSchemaValidationError(self, elem, reason="not a key reference %r" % value)
