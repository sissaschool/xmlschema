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
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Pattern, \
    Set, Tuple, Union, Counter
from elementpath import XPath2Parser, ElementPathError, XPathToken, XPathContext, \
    ElementNode, translate_pattern, datatypes

from ..exceptions import XMLSchemaTypeError, XMLSchemaValueError
from ..names import XSD_QNAME, XSD_UNIQUE, XSD_KEY, XSD_KEYREF, XSD_SELECTOR, XSD_FIELD
from ..translation import gettext as _
from ..helpers import get_qname, get_extended_qname
from ..aliases import ElementType, SchemaType, NamespacesType, AtomicValueType
from .exceptions import XMLSchemaNotBuiltError
from .xsdbase import XsdComponent
from .attributes import XsdAttribute
from .wildcards import XsdAnyElement
from . import elements

if TYPE_CHECKING:
    from .elements import XsdElement

IdentityFieldItemType = Union[AtomicValueType, XsdAttribute, Tuple[Any, ...], None]
IdentityCounterType = Tuple[IdentityFieldItemType, ...]
IdentityMapType = Dict[Union['XsdKey', 'XsdKeyref', str, None],
                       Union['IdentityCounter', 'KeyrefCounter']]

XSD_IDENTITY_XPATH_SYMBOLS = frozenset((
    'processing-instruction', 'following-sibling', 'preceding-sibling',
    'ancestor-or-self', 'attribute', 'following', 'namespace', 'preceding',
    'ancestor', 'position', 'comment', 'parent', 'child', 'false', 'text', 'node',
    'true', 'last', 'not', 'and', 'mod', 'div', 'or', '..', '//', '!=', '<=', '>=',
    '(', ')', '[', ']', '.', '@', ',', '/', '|', '*', '-', '=', '+', '<', '>', ':',
    '(end)', '(unknown)', '(invalid)', '(name)', '(string)', '(float)', '(decimal)',
    '(integer)', '::', '{', '}',
))


# XSD identities use a restricted XPath 2.0 parser. The XMLSchemaProxy is
# not used for the specific selection of fields and elements and the XSD
# fields are collected at first validation run.

def iter_root_elements(token: XPathToken) -> Iterator[XPathToken]:
    if token.symbol in ('(name)', ':', '*', '.'):
        yield token
    elif token.symbol in ('//', '/'):
        yield from iter_root_elements(token[0])
        for tk in token[1].iter():
            if tk.symbol == '|':
                yield from iter_root_elements(tk[1])
                break
    elif token.symbol in '|':
        for tk in token:
            yield from iter_root_elements(tk)


class IdentityXPathParser(XPath2Parser):
    symbol_table = {
        k: v for k, v in XPath2Parser.symbol_table.items()  # type: ignore[misc]
        if k in XSD_IDENTITY_XPATH_SYMBOLS
    }
    SYMBOLS = XSD_IDENTITY_XPATH_SYMBOLS


class XsdSelector(XsdComponent):
    """Class for defining an XPath selector for an XSD identity constraint."""
    _ADMITTED_TAGS = {XSD_SELECTOR}
    xpath_default_namespace = ''
    pattern: Union[str, Pattern[str]] = translate_pattern(
        r"(\.//)?(((child::)?((\i\c*:)?(\i\c*|\*)))|\.)(/(((child::)?"
        r"((\i\c*:)?(\i\c*|\*)))|\.))*(\|(\.//)?(((child::)?((\i\c*:)?"
        r"(\i\c*|\*)))|\.)(/(((child::)?((\i\c*:)?(\i\c*|\*)))|\.))*)*",
        back_references=False,
        lazy_quantifiers=False,
        anchors=False
    )
    token: Optional[XPathToken] = None
    parser: Optional[IdentityXPathParser] = None

    def __init__(self, elem: ElementType, schema: SchemaType,
                 parent: Optional['XsdIdentity']) -> None:
        super(XsdSelector, self).__init__(elem, schema, parent)

    def _parse(self) -> None:
        try:
            self.path = self.elem.attrib['xpath']
        except KeyError:
            self.parse_error(_("'xpath' attribute required"))
            self.path = '*'
        else:
            path = self.path.replace(' ', '')
            try:
                _match = self.pattern.match(path)  # type: ignore[union-attr]
            except AttributeError:
                # Compile regex pattern
                self.__class__.pattern = re.compile(self.pattern)
                _match = self.pattern.match(path)  # type: ignore[union-attr]

            if not _match:
                msg = _("invalid XPath expression for an {}")
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

    def __repr__(self) -> str:
        return '%s(path=%r)' % (self.__class__.__name__, self.path)

    @property
    def built(self) -> bool:
        return self.token is not None

    @property
    def target_namespace(self) -> str:
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
    name: str
    local_name: str
    prefixed_name: str
    parent: 'XsdElement'
    ref: Optional['XsdIdentity']

    selector: Optional[XsdSelector] = None
    fields: Union[Tuple[()], List[XsdFieldSelector]] = ()

    # XSD elements bound by selector (for speed-up and for lazy mode)
    elements: Union[Tuple[()], Dict['XsdElement', Optional[IdentityCounterType]]] = ()
    root_elements: Union[Tuple[()], Set['XsdElement']] = ()

    def __init__(self, elem: ElementType, schema: SchemaType,
                 parent: Optional['XsdElement']) -> None:
        super(XsdIdentity, self).__init__(elem, schema, parent)

    def _parse(self) -> None:
        try:
            self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self.parse_error(_("missing required attribute 'name'"))
            self.name = ''

        for child in self.elem:
            if child.tag == XSD_SELECTOR:
                self.selector = XsdSelector(child, self.schema, self)
                break
        else:
            self.parse_error(_("missing 'selector' declaration"))

        self.fields = []
        for child in self.elem:
            if child.tag == XSD_FIELD:
                self.fields.append(XsdFieldSelector(child, self.schema, self))

    def build(self) -> None:
        if self.ref is True:  # type: ignore[comparison-overlap]
            try:
                ref = self.maps.identities[self.name]
            except KeyError:
                msg = _("unknown identity constraint {!r}")
                self.parse_error(msg.format(self.name))
                return
            else:
                if not isinstance(ref, self.__class__):
                    msg = _("attribute 'ref' points to a different kind constraint")
                    self.parse_error(msg)
                self.selector = ref.selector
                self.fields = ref.fields
                self.ref = ref

        if self.selector is None:
            return  # Do not raise, already found by meta-schema validation.
        elif self.selector.token is None:
            raise XMLSchemaNotBuiltError(self, "identity selector is not built")

        context = XPathContext(self.schema.xpath_node, item=self.parent.xpath_node)
        self.elements = {}

        for e in self.selector.token.select_results(context):
            if not isinstance(e, (elements.XsdElement, XsdAnyElement)):
                msg = _("selector xpath expression can only select elements")
                self.parse_error(msg)
            elif e.name is not None:
                if e.ref is not None:
                    e = e.ref
                self.elements[e] = None  # XSD fields must be added during validation
                e.selected_by.add(self)

        if not self.elements:
            # Try to detect target XSD elements extracting QNames
            # of the leaf elements from the XPath expression and
            # use them to match global elements.

            qname: Any
            for qname in self.selector.token.iter_leaf_elements():
                xsd_element = self.maps.elements.get(
                    get_extended_qname(qname, self.namespaces)
                )
                if xsd_element is not None and \
                        not isinstance(xsd_element, tuple) and \
                        xsd_element not in self.elements:
                    if xsd_element.ref is not None:
                        xsd_element = xsd_element.ref

                    self.elements[xsd_element] = None
                    xsd_element.selected_by.add(self)

        self.root_elements = set()
        for token in iter_root_elements(self.selector.token):
            context = XPathContext(self.schema.xpath_node, item=self.parent.xpath_node)
            for e in token.select_results(context):
                if isinstance(e, elements.XsdElement):
                    self.root_elements.add(e)

    @property
    def built(self) -> bool:
        return not isinstance(self.elements, tuple)

    def get_fields(self, element_node: ElementNode,
                   namespaces: Optional[NamespacesType] = None,
                   decoders: Optional[Tuple[XsdAttribute, ...]] = None) -> IdentityCounterType:
        """
        Get fields for a schema or instance context element.

        :param element_node: an Element or an XsdElement
        :param namespaces: is an optional mapping from namespace prefix to URI.
        :param decoders: context schema fields decoders.
        :return: a tuple with field values. An empty field is replaced by `None`.
        """
        fields: List[IdentityFieldItemType] = []

        def append_fields() -> None:
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

        result: Any
        value: Union[AtomicValueType, None]

        for k, field in enumerate(self.fields):
            if field.token is None:
                msg = f"identity field {field} is not built"
                raise XMLSchemaNotBuiltError(self, msg)

            context = XPathContext(element_node)
            result = field.token.get_results(context)

            if not result:
                if decoders is not None and decoders[k] is not None:
                    value = decoders[k].value_constraint
                    if value is not None:
                        if decoders[k].type.root_type.name == XSD_QNAME:
                            value = get_extended_qname(value, namespaces)

                        append_fields()
                        continue

                if not isinstance(self, XsdKey) or 'ref' in element_node.elem.attrib and \
                        self.schema.meta_schema is None and self.schema.XSD_VERSION != '1.0':
                    fields.append(None)
                elif field.target_namespace not in self.maps.namespaces:
                    fields.append(None)
                else:
                    msg = _("missing key field {0!r} for {1!r}")
                    raise XMLSchemaValueError(msg.format(field.path, self))

            elif len(result) == 1:
                if decoders is None or decoders[k] is None:
                    fields.append(result[0])
                else:
                    if decoders[k].type.content_type_label not in ('simple', 'mixed'):
                        msg = _("%r field doesn't have a simple type!")
                        raise XMLSchemaTypeError(msg % field)

                    value = decoders[k].data_value(result[0])
                    if decoders[k].type.root_type.name == XSD_QNAME:
                        if isinstance(value, str):
                            value = get_extended_qname(value, namespaces)
                        elif isinstance(value, datatypes.QName):
                            value = value.expanded_name

                    append_fields()
            else:
                msg = _("%r field selects multiple values!")
                raise XMLSchemaValueError(msg % field)

        return tuple(fields)

    def get_counter(self, elem: ElementType) -> 'IdentityCounter':
        return IdentityCounter(self, elem)


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
    refer: Optional[Union[str, XsdKey]] = None
    refer_path = '.'

    def _parse(self) -> None:
        super(XsdKeyref, self)._parse()
        try:
            self.refer = self.schema.resolve_qname(self.elem.attrib['refer'])
        except (KeyError, ValueError, RuntimeError) as err:
            if 'refer' not in self.elem.attrib:
                self.parse_error(_("missing required attribute 'refer'"))
            else:
                self.parse_error(err)

    def build(self) -> None:
        super(XsdKeyref, self).build()

        if isinstance(self.refer, (XsdKey, XsdUnique)):
            return  # referenced key/unique identity constraint already set
        elif isinstance(self.ref, XsdKeyref):
            self.refer = self.ref.refer

        if self.refer is None:
            return  # attribute or key/unique identity constraint missing
        elif isinstance(self.refer, str):
            refer: Optional[XsdIdentity]
            for refer in self.parent.identities:
                if refer.name == self.refer:
                    break
            else:
                refer = None

            if refer is not None and refer.ref is None:
                self.refer = refer  # type: ignore[assignment]
            else:
                try:
                    self.refer = self.maps.identities[self.refer]  # type: ignore[assignment]
                except KeyError:
                    msg = _("key/unique identity constraint %r is missing")
                    self.parse_error(msg % self.refer)
                    return

        if not isinstance(self.refer, (XsdKey, XsdUnique)):
            msg = _("reference to a non key/unique identity constraint %r")
            self.parse_error(msg % self.refer)
        elif len(self.refer.fields) != len(self.fields):
            msg = _("field cardinality mismatch between {0!r} and {1!r}")
            self.parse_error(msg.format(self, self.refer))
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
                    path1 = self.parent.get_path(reverse=True)
                    path2 = self.refer.parent.get_path()
                    assert path1 is not None
                    assert path2 is not None
                    refer_path = f'{path1}/{path2}'

            self.refer_path = refer_path

    @property
    def built(self) -> bool:
        return not isinstance(self.elements, tuple) and isinstance(self.refer, XsdIdentity)

    def get_counter(self, elem: ElementType) -> 'KeyrefCounter':
        return KeyrefCounter(self, elem)


class Xsd11Unique(XsdUnique):
    def _parse(self) -> None:
        if self._parse_reference():
            self.ref = True  # type: ignore[assignment]
        else:
            super(Xsd11Unique, self)._parse()


class Xsd11Key(XsdKey):
    def _parse(self) -> None:
        if self._parse_reference():
            self.ref = True  # type: ignore[assignment]
        else:
            super(Xsd11Key, self)._parse()


class Xsd11Keyref(XsdKeyref):
    def _parse(self) -> None:
        if self._parse_reference():
            self.ref = True  # type: ignore[assignment]
        else:
            super(Xsd11Keyref, self)._parse()


class IdentityCounter:

    def __init__(self, identity: XsdIdentity, elem: ElementType) -> None:
        self.counter: Counter[IdentityCounterType] = Counter[IdentityCounterType]()
        self.identity = identity
        self.elem = elem
        self.enabled = True

    def __repr__(self) -> str:
        return "%s%r" % (self.__class__.__name__[:-7], self.counter)

    def reset(self, elem: ElementType) -> None:
        self.counter.clear()
        self.elem = elem
        self.enabled = True

    def increase(self, fields: IdentityCounterType) -> None:
        self.counter[fields] += 1
        if self.counter[fields] == 2:
            msg = _("duplicated value {0!r} for {1!r}")
            raise XMLSchemaValueError(msg.format(fields, self.identity))


class KeyrefCounter(IdentityCounter):
    identity: XsdKeyref

    def increase(self, fields: IdentityCounterType) -> None:
        self.counter[fields] += 1

    def iter_errors(self, identities: IdentityMapType) -> Iterator[XMLSchemaValueError]:
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
