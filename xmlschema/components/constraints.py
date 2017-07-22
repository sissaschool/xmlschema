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
This module contains classes for other XML Schema constraints.
"""
from ..exceptions import (
    XMLSchemaParseError, XMLSchemaValidationError, XMLSchemaValueError, XMLSchemaTypeError
)
from ..qnames import (get_qname, reference_to_qname, XSD_UNIQUE_TAG, XSD_KEY_TAG,
                      XSD_KEYREF_TAG, XSD_SELECTOR_TAG, XSD_FIELD_TAG)
from ..xpath import XPathParser
from .component import XsdAnnotated, XsdComponent


def get_fields(elem, fields, is_key=False):
    """
    Return the value of fields selected by XPath expressions from a context element.
    None is the replacement value for empty XPath expression selections.

    :param elem: The Element that represent the context.
    :param fields: The sequence of XPathSelector instances.
    :param is_key: If True raise an error when a field return \
    an empty XPath expression.
    :return: A tuple.
    """
    values = []
    for field in fields:
        result = list(field.iter_select(elem))
        if not result:
            if is_key:
                raise XMLSchemaValueError("%r key field must have a value!" % field)
            else:
                values.append(None)
        elif len(result) == 1:
            values.append(result[0])
        else:
            raise XMLSchemaValueError("%r field must identify a single value!" % field)
    return tuple(values)


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

    def __init__(self, elem, schema):
        super(XsdConstraint, self).__init__(elem, schema)
        self.context = []

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

    def set_context(self, elem):
        if not isinstance(elem, XsdComponent):
            raise XMLSchemaTypeError("an XsdElement required: %r" % elem)
        if self.context:
            del self.context[:]
        try:
            self.context = self.get_context(elem)
        except XMLSchemaValueError as err:
            self.context = []
            self._parse_error(str(err), elem=elem)

        print("BASE: ", elem)
        print("CONTEXT: ", self.context)
        self.context_fields = []
        for e in self.context:
            print("ORIGIN: ", e, self.selector.path)
            try:
                fields = self.get_fields(e)
            except XMLSchemaValueError as err:
                self.context_fields.append(None)
                self._parse_error(str(err), elem=e)
            else:
                self.context_fields.append(tuple(fields))
        print("Context Fields: ", self.context_fields)

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

    def get_fields(self, elem, is_key=True):
        """
        Get fields generating the context from selector. I

        :param elem: Reference XSD element or Element.
        :return: A list containing tuples
        """
        values = []
        for field in self.fields:
            result = list(field.iter_select(elem))
            print("RES: ", result)
            if not result:
                if is_key:
                    raise XMLSchemaValueError("%r key field must have a value!" % field)
                else:
                    values.append(None)
            elif len(result) == 1:
                values.append(result[0])
            else:
                print("ELEM: ", elem, elem.elem.attrib)

                print("PATH: ", field.path)
                raise XMLSchemaValueError("%r field must identify a single value!" % field)
        return tuple(values)

        fields = [list(field.iter_select(elem)) for field in self.fields]
        try:
            if any([not field.type.is_simple() for field in elem_fields]):
                raise ValueError()
        except (AttributeError, ValueError):
            self._parse_error("element %r not allowed here:" % e)
        else:
            self.context_fields.append(elem_fields)

        result = list(field.iter_select(elem))
        if not result:
            if is_key:
                raise XMLSchemaValueError("%r key field must have a value!" % field)
            else:
                values.append(None)
        elif len(result) == 1:
            values.append(result[0])
        else:
            raise XMLSchemaValueError("%r field must identify a single value!" % field)

        print("Context Fields: ", self.context_fields)

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

    def validator2(self, context):
        try:
            values = [
                get_fields(elem, self.fields) for elem in self.selector.iter_select(context)
            ]
        except XMLSchemaValueError as err:
            yield XMLSchemaValidationError(self, context, reason=str(err))
        else:
            for v in values:
                if values.count(v) > 1:
                    yield XMLSchemaValidationError(self, context, reason="duplicated value %r." % v)
                    break

    def validator(self, context):
        xsd_element = self.schema.constraints[self.name]
        try:
            values = [
                self.get_fields(elem) for elem in self.selector.iter_select(context)
            ]
        except XMLSchemaValueError as err:
            yield XMLSchemaValidationError(self, context, reason=str(err))
        else:
            for v in values:
                if values.count(v) > 1:
                    yield XMLSchemaValidationError(self, context, reason="duplicated value %r." % v)
                    break


class XsdKey(XsdConstraint):

    @property
    def admitted_tags(self):
        return {XSD_KEY_TAG}

    def validator(self, context):
        try:
            values = [get_fields(elem, self.fields, True) for elem in self.selector.iter_select(context)]
        except XMLSchemaValueError as err:
            yield XMLSchemaValidationError(self, context, reason=str(err))
        else:
            for v in values:
                if values.count(v) > 1:
                    yield XMLSchemaValidationError(self, context, reason="duplicated key %r." % v)
                    break

    def validator2(self, context):
        try:
            values = [get_fields(elem, self.fields, True) for elem in self.selector.iter_select(context)]
        except XMLSchemaValueError as err:
            yield XMLSchemaValidationError(self, context, reason=str(err))
        else:
            for v in values:
                if values.count(v) > 1:
                    yield XMLSchemaValidationError(self, context, reason="duplicated key %r." % v)
                    break

class XsdKeyref(XsdConstraint):

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

    def validator(self, context):
        try:
            values = [get_fields(elem, self.fields, True) for elem in self.selector.iter_select(context)]
        except XMLSchemaValueError as err:
            yield XMLSchemaValidationError(self, context, reason=str(err))
        else:
            return
            xsd_element = self.maps.constraints[self.name]
            xsd_child = self.maps.constraints[self.refer]
            key_constraint = xsd_child.constraints[self.refer]
            if xsd_element is xsd_child:
                keys = [
                    get_fields(e, key_constraint.fields, True)
                    for e in key_constraint.selector.iter_select(context)
                ]
                print("VALUES: ", values)
                print ("KEYS: ", keys)
                for v in values:
                    if v not in keys:
                        yield XMLSchemaValidationError(self, context, reason="not a key %r." % v)

            elif xsd_child in xsd_element.findall('.//*'):
                print("DESCENDANT")

            parent_map = self.schema.parent_map
            xsd_key = xsd_element.constraints[self.refer]
            for v in values:
                pass

            # Checks key reference


