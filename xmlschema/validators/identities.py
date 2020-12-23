#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
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
import re
import math
from collections import Counter
from typing import Dict, Union
from elementpath import XPath2Parser, ElementPathError, XPathContext, translate_pattern

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..names import XSD_QNAME, XSD_UNIQUE, XSD_KEY, XSD_KEYREF, XSD_SELECTOR, XSD_FIELD
from ..helpers import get_qname, get_extended_qname
from ..xpath import iter_schema_nodes
from .xsdbase import XsdComponent
from .attributes import XsdAttribute


XSD_IDENTITY_XPATH_SYMBOLS = {
    'processing-instruction', 'following-sibling', 'preceding-sibling',
    'ancestor-or-self', 'attribute', 'following', 'namespace', 'preceding',
    'ancestor', 'position', 'comment', 'parent', 'child', 'false', 'text', 'node',
    'true', 'last', 'not', 'and', 'mod', 'div', 'or', '..', '//', '!=', '<=', '>=', '(', ')',
    '[', ']', '.', '@', ',', '/', '|', '*', '-', '=', '+', '<', '>', ':', '(end)', '(name)',
    '(string)', '(float)', '(decimal)', '(integer)', '::', '{', '}',
}


# XSD identities use a restricted parser and a context for iterate element
# references. The XMLSchemaProxy is not used for the specific selection of
# fields and elements and the XSD fields are got at first validation run.
class IdentityXPathContext(XPathContext):
    _iter_nodes = staticmethod(iter_schema_nodes)


class IdentityXPathParser(XPath2Parser):
    symbol_table = {
        k: v for k, v in XPath2Parser.symbol_table.items() if k in XSD_IDENTITY_XPATH_SYMBOLS
    }
    SYMBOLS = XSD_IDENTITY_XPATH_SYMBOLS


class XsdSelector(XsdComponent):
    """Class for defining an XPath selector for an XSD identity constraint."""
    _ADMITTED_TAGS = {XSD_SELECTOR}
    xpath_default_namespace = ''
    pattern = translate_pattern(
        r"(\.//)?(((child::)?((\i\c*:)?(\i\c*|\*)))|\.)(/(((child::)?"
        r"((\i\c*:)?(\i\c*|\*)))|\.))*(\|(\.//)?(((child::)?((\i\c*:)?"
        r"(\i\c*|\*)))|\.)(/(((child::)?((\i\c*:)?(\i\c*|\*)))|\.))*)*",
        back_references=False,
        lazy_quantifiers=False,
        anchors=False
    )
    token = None
    parser = None

    def __init__(self, elem, schema, parent):
        super(XsdSelector, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdSelector, self)._parse()
        try:
            self.path = self.elem.attrib['xpath']
        except KeyError:
            self.parse_error("'xpath' attribute required")
            self.path = '*'
        else:
            try:
                match = self.pattern.match(self.path.replace(' ', ''))
            except AttributeError:
                # Compile regex pattern
                self.__class__.pattern = re.compile(self.pattern)
                match = self.pattern.match(self.path.replace(' ', ''))

            if not match:
                msg = "invalid XPath expression for an {}"
                self.parse_error(msg.format(self.__class__.__name__))

        # XSD 1.1 xpathDefaultNamespace attribute
        if self.schema.XSD_VERSION > '1.0':
            if 'xpathDefaultNamespace' in self.elem.attrib:
                self.xpath_default_namespace = self._parse_xpath_default_namespace(self.elem)
            else:
                self.xpath_default_namespace = self.schema.xpath_default_namespace

        self.parser = IdentityXPathParser(
            namespaces=self.namespaces,
            strict=False,
            compatibility_mode=True,
            default_namespace=self.xpath_default_namespace,
        )

        try:
            self.token = self.parser.parse(self.path)
        except ElementPathError as err:
            self.token = self.parser.parse('*')
            self.parse_error(err)

    def __repr__(self):
        return '%s(path=%r)' % (self.__class__.__name__, self.path)

    @property
    def built(self):
        return self.token is not None

    @property
    def target_namespace(self):
        # TODO: implement a property in elementpath for getting XPath token's namespace
        if self.token is None:
            pass  # xpathDefaultNamespace="##targetNamespace"
        elif self.token.symbol == ':':
            return self.token[1].namespace or self.xpath_default_namespace
        elif self.token.symbol == '@' and self.token[0].symbol == ':':
            return self.token[0][1].namespace or self.xpath_default_namespace
        return self.schema.target_namespace


class XsdFieldSelector(XsdSelector):
    """Class for defining an XPath field selector for an XSD identity constraint."""
    _ADMITTED_TAGS = {XSD_FIELD}
    pattern = translate_pattern(
        r"(\.//)?((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)/)*((((child::)?"
        r"((\i\c*:)?(\i\c*|\*)))|\.)|((attribute::|@)((\i\c*:)?(\i\c*|\*))))"
        r"(\|(\.//)?((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)/)*"
        r"((((child::)?((\i\c*:)?(\i\c*|\*)))|\.)|"
        r"((attribute::|@)((\i\c*:)?(\i\c*|\*)))))*",
        back_references=False,
        lazy_quantifiers=False,
        anchors=False
    )


class XsdIdentity(XsdComponent):
    """
    Common class for XSD identity constraints.

    :ivar selector: the XPath selector of the identity constraint.
    :ivar fields: a list containing the XPath field selectors of the identity constraint.
    """
    selector = None
    elements = None  # XSD elements bound by selector (for speed-up and lazy mode)
    fields = ()

    def __init__(self, elem, schema, parent):
        super(XsdIdentity, self).__init__(elem, schema, parent)

    def _parse(self):
        super(XsdIdentity, self)._parse()
        try:
            self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self.parse_error("missing required attribute 'name'")
            self.name = None

        for child in self.elem:
            if child.tag == XSD_SELECTOR:
                self.selector = XsdSelector(child, self.schema, self)
                break
        else:
            self.parse_error("missing 'selector' declaration.")

        self.fields = []
        for child in self.elem:
            if child.tag == XSD_FIELD:
                self.fields.append(XsdFieldSelector(child, self.schema, self))

    def build(self):
        if self.ref is True:
            try:
                ref = self.maps.identities[self.name]
            except KeyError:
                self.parse_error("unknown identity constraint {!r}".format(self.name))
                return
            else:
                if not isinstance(ref, self.__class__):
                    self.parse_error("attribute 'ref' points to a different kind constraint")
                self.selector = ref.selector
                self.fields = ref.fields
                self.ref = ref

        context = IdentityXPathContext(self.schema, item=self.parent)

        try:
            self.elements = {
                e: None for e in self.selector.token.select_results(context) if e.name
            }
        except AttributeError:
            self.elements = {}
        else:
            if any(isinstance(e, XsdAttribute) for e in self.elements):
                self.parse_error("selector xpath cannot select attributes")
            elif not self.elements:
                # Try to detect target XSD elements extracting QNames
                # of the leaf elements from the XPath expression and
                # use them to match global elements.

                for qname in self.selector.token.iter_leaf_elements():
                    xsd_element = self.maps.elements.get(
                        get_extended_qname(qname, self.namespaces)
                    )
                    if xsd_element is not None and xsd_element not in self.elements:
                        self.elements[xsd_element] = None

    @property
    def built(self):
        return self.elements is not None

    def get_fields(self, elem, namespaces=None, decoders=None):
        """
        Get fields for a schema or instance context element.

        :param elem: an Element or an XsdElement
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param decoders: context schema fields decoders.
        :return: a tuple with field values. An empty field is replaced by `None`.
        """
        fields = []
        if isinstance(elem, XsdComponent):
            context_class = IdentityXPathContext
        else:
            context_class = XPathContext

        for k, field in enumerate(self.fields):
            result = field.token.get_results(context_class(elem))
            if not result:
                if decoders is not None and decoders[k] is not None:
                    value = decoders[k].value_constraint
                    if value is not None:
                        if decoders[k].type.root_type.name == XSD_QNAME:
                            value = get_extended_qname(value, namespaces)

                        if isinstance(value, list):
                            fields.append(tuple(value))
                        elif isinstance(value, bool):
                            fields.append((value, bool))
                        elif not isinstance(value, float):
                            fields.append(value)
                        elif math.isnan(value):
                            fields.append(('nan', float))
                        else:
                            fields.append((value, float))

                        continue

                if not isinstance(self, XsdKey) or 'ref' in elem.attrib and \
                        self.schema.meta_schema is None and self.schema.XSD_VERSION != '1.0':
                    fields.append(None)
                elif field.target_namespace not in self.maps.namespaces:
                    fields.append(None)
                else:
                    msg = "missing key field {!r} for {!r}"
                    raise XMLSchemaValueError(msg.format(field.path, self))

            elif len(result) == 1:
                if decoders is None or decoders[k] is None:
                    fields.append(result[0])
                else:
                    if decoders[k].type.content_type_label not in ('simple', 'mixed'):
                        raise XMLSchemaTypeError("%r field doesn't have a simple type!" % field)

                    value = decoders[k].data_value(result[0])
                    if decoders[k].type.root_type.name == XSD_QNAME:
                        value = get_extended_qname(value, namespaces)

                    if isinstance(value, list):
                        fields.append(tuple(value))
                    elif isinstance(value, bool):
                        fields.append((value, bool))
                    elif not isinstance(value, float):
                        fields.append(value)
                    elif math.isnan(value):
                        fields.append(('nan', float))
                    else:
                        fields.append((value, float))
            else:
                raise XMLSchemaValueError("%r field selects multiple values!" % field)

        return tuple(fields)

    def get_counter(self, enabled=True):
        return IdentityCounter(self, enabled)


class XsdUnique(XsdIdentity):
    _ADMITTED_TAGS = {XSD_UNIQUE}


class XsdKey(XsdIdentity):
    _ADMITTED_TAGS = {XSD_KEY}


class XsdKeyref(XsdIdentity):
    """
    Implementation of xs:keyref.

    :ivar refer: reference to a *xs:key* declaration that must be in the same element \
    or in a descendant element.
    """
    _ADMITTED_TAGS = {XSD_KEYREF}
    refer = None
    refer_path = '.'

    def _parse(self):
        super(XsdKeyref, self)._parse()
        try:
            self.refer = self.schema.resolve_qname(self.elem.attrib['refer'])
        except (KeyError, ValueError, RuntimeError) as err:
            if 'refer' not in self.elem.attrib:
                self.parse_error("missing required attribute 'refer'")
            else:
                self.parse_error(err)

    def build(self):
        super(XsdKeyref, self).build()

        if isinstance(self.refer, (XsdKey, XsdUnique)):
            return  # referenced key/unique identity constraint already set
        elif isinstance(self.ref, XsdKeyref):
            self.refer = self.ref.refer

        if self.refer is None:
            return  # attribute or key/unique identity constraint missing
        elif isinstance(self.refer, str):
            refer = self.parent.identities.get(self.refer)
            if refer is not None and refer.ref is None:
                self.refer = refer
            else:
                try:
                    self.refer = self.maps.identities[self.refer]
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
                # From a note in par. 3.11.5 Part 1 of XSD 1.0 spec: "keyref
                # identity-constraints may be defined on domains distinct from
                # the embedded domain of the identity-constraint they reference,
                # or the domains may be the same but self-embedding at some depth.
                # In either case the node table for the referenced identity-constraint
                # needs to propagate upwards, with conflict resolution."
                refer_path = self.parent.get_path(ancestor=self.refer.parent, reverse=True)
                if refer_path is None:
                    refer_path = self.parent.get_path(reverse=True) + '/' + \
                        self.refer.parent.get_path()

            self.refer_path = refer_path

    @property
    def built(self):
        return self.elements is not None and isinstance(self.refer, XsdIdentity)

    def get_counter(self, enabled=True):
        return KeyrefCounter(self, enabled)


class Xsd11Unique(XsdUnique):

    def _parse(self):
        if self._parse_reference():
            super(XsdIdentity, self)._parse()
            self.ref = True
        else:
            super(Xsd11Unique, self)._parse()


class Xsd11Key(XsdKey):

    def _parse(self):
        if self._parse_reference():
            super(XsdIdentity, self)._parse()
            self.ref = True
        else:
            super(Xsd11Key, self)._parse()


class Xsd11Keyref(XsdKeyref):

    def _parse(self):
        if self._parse_reference():
            super(XsdIdentity, self)._parse()
            self.ref = True
        else:
            super(Xsd11Keyref, self)._parse()


class IdentityCounter:

    def __init__(self, identity: Union[XsdKey, XsdKeyref], enabled=True):
        self.counter = Counter()
        self.identity = identity
        self.enabled = enabled

    def __repr__(self):
        return "%s%r" % (self.__class__.__name__[:-7], self.counter)

    def clear(self):
        self.counter.clear()
        self.enabled = True

    def increase(self, fields: tuple):
        self.counter[fields] += 1
        if self.counter[fields] == 2:
            msg = "duplicated value {!r} for {!r}"
            raise XMLSchemaValueError(msg.format(fields, self.identity))


class KeyrefCounter(IdentityCounter):

    def increase(self, fields: tuple):
        self.counter[fields] += 1

    def iter_errors(self, identities: Dict[Union[XsdKey, XsdKeyref],
                                           Union['IdentityCounter', 'KeyrefCounter']]):
        refer_values = identities[self.identity.refer].counter

        for v in filter(lambda x: x not in refer_values, self.counter):
            if len(v) == 1 and v[0] in refer_values:
                continue
            elif self.counter[v] > 1:
                msg = "value {} not found for {!r} ({} times)"
                yield XMLSchemaValueError(msg.format(v, self.identity.refer, self.counter[v]))
            else:
                msg = "value {} not found for {!r}"
                yield XMLSchemaValueError(msg.format(v, self.identity.refer))
