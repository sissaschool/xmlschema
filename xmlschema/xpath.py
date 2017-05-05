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
This module contains an XPath expressions parser.
"""
import re
from collections import MutableSequence
from abc import ABCMeta
from .exceptions import XMLSchemaXPathError, XMLSchemaSyntaxError
from .utils import reference_to_qname


#
# XPath tokenizer
def get_tokenizer_pattern(symbols):
    tokenizer_pattern_template = r"""
        ('[^']*' | "[^"]*" | \d+(?:\.\d?)? | \.\d+) |   # Literals (strings or numbers)
        (%s | [%s]) |                                   # Symbols
        ((?:{[^}]+\})?[^/\[\]()@=\s]+) |                # References and other names   
        \s+                                             # Skip extra spaces
        """

    symbols.sort(key=lambda x: -len(x))
    fence = len([i for i in symbols if len(i) > 1])
    return tokenizer_pattern_template % (
        '|'.join(map(re.escape, symbols[:fence])),
        ''.join(map(re.escape, symbols[fence:]))
    )

XPATH_SYMBOLS = [
    'processing-instruction(', 'descendant-or-self::', 'following-sibling::',
    'preceding-sibling::', 'ancestor-or-self::', 'descendant::', 'attribute::',
    'following::', 'namespace::', 'preceding::', 'ancestor::', 'comment(', 'parent::',
    'child::', 'self::', 'text(', 'node(', 'and', 'mod', 'div', 'or',
    '..', '//', '!=', '<=', '>=' '(', ')', '[', ']', '.', '@', ',', '/', '|', '*',
    '-', '=', '+', '<', '>'
]

xpath_tokens_regex = re.compile(get_tokenizer_pattern(XPATH_SYMBOLS), re.VERBOSE)


#
# XPath parser based on Vaughan Pratt's algorithm.
# ref: http://effbot.org/zone/simple-top-down-parsing.htm
class TokenMeta(ABCMeta):
    """
    Token metaclass for register token classes.
    """
    registry = {}

    def __new__(mcs, name, bases, _dict):
        _dict['name'] = name
        lbp = _dict['lbp'] = _dict.pop('bp', 0)
        nud = _dict.pop('nud', None)
        led = _dict.pop('led', None)

        try:
            token_class = mcs.registry[name]
        except KeyError:
            token_class = super(TokenMeta, mcs).__new__(mcs, "_%s_Token" % name, bases, _dict)
        else:
            if lbp > token_class.lbp:
                token_class.lbp = lbp

        if callable(nud):
            token_class.nud = nud
        if callable(led):
            token_class.led = led

        return token_class

    def __init__(cls, name, bases, _dict):
        cls.registry[_dict['name']] = cls
        super(TokenMeta, cls).__init__(name, bases, _dict)


class Token(MutableSequence):
    """
    Token class for defining a parser based on Pratt's method.

    :param value: the token value, its default is name.
    """
    __metaclass__ = TokenMeta

    name = None     # the token identifier, key in the symbol table.

    def __init__(self, value=None):
        self.value = value or self.name
        self._operands = []

    def __getitem__(self, i):
        return self._operands[i]

    def __setitem__(self, i, item):
        self._operands[i] = item

    def __delitem__(self, i):
        del self._operands[i]

    def __len__(self):
        return len(self._operands)

    def insert(self, i, item):
        self._operands.insert(i, item)

    def __repr__(self):
        return u"<%s '%s' at %#x>" % (self.__class__.__name__, self.value, id(self))

    def __cmp__(self, other):
        return self.name == other.name and self.value == other.value

    @property
    def arity(self):
        return len(self)

    def nud(self):
        """Null denotation method"""
        raise XMLSchemaSyntaxError("Undefined operator for %r." % self.name)

    def led(self, selector):
        """Left denotation method"""
        raise XMLSchemaSyntaxError("Undefined operator for %r." % self.name)

    def iter(self):
        yield self
        for t in self:
            for token in t.iter():
                yield token

    def iter_selectors(self):
        for token in self.iter():
            if hasattr(token, 'sed'):
                yield token.sed


class XPathParser(object):
    """
    XPath expression iterator parser class.

    :param token_table: Dictionary with XPath grammar's tokens.
    :param path: XPath expression.
    :param namespaces: optional prefix to namespace map.
    """

    def __init__(self, token_table, path, namespaces=None):
        if path[-1:] == "/" and len(path) > 1:
            raise XMLSchemaXPathError("Invalid path: %r" % path)
        if path[:1] == "/":
            path = "." + path

        self.token = None
        self.token_table = token_table
        self.path = path
        self.namespaces = namespaces if namespaces is not None else {}

    def __iter__(self):
        self._tokens = iter(xpath_tokens_regex.finditer(self.path))

    def __next__(self):
        token = self.advance()
        if token.name == '(end)':
            raise StopIteration()
        return token

    next = __next__

    def advance(self, name=None):
        try:
            match = next(self._tokens)
        except StopIteration:
            return self.token_table['(end)'](self)

        literal, operator, ref = match.groups()
        if operator is not None:
            try:
                token = self.token_table[operator]()
            except KeyError:
                raise XMLSchemaXPathError("Unknown operator %r." % operator)
        elif literal is not None:
            token = self.token_table['(literal)'](literal)
        elif ref is not None:
            value = reference_to_qname(ref, self.namespaces)
            token = self.token_table['(ref)'](value)
        else:
            raise XMLSchemaXPathError("Unexpected token: %r" % match)

        if name and token.name != name:
            raise XMLSchemaXPathError("Expected %r token." % name)
        return token

    def parse(self):
        global advance, expression
        advance = self.advance
        expression = self.expression
        self.__iter__()
        self.token = advance()
        return expression()

    def expression(self, rbp=0):
        """
        Recursive expression parser. Call token.nud() and then advance until the 
        right binding power is less the left binding power of the next token,
        invoking the led() method on the following token.

        :param rbp: right binding power for the expression.
        :return: left token.
        """
        previous_token, self.token = self.token, self.advance()
        left = previous_token.nud()
        while rbp < self.token.lbp:
            previous_token, self.token = self.token, self.advance()
            left = previous_token.led(left)
        return left


# XPath selector class and functions
class XPathSelector(MutableSequence):
    _parent_map = None

    def __init__(self, context, path, initlist=None):
        self.context = context
        self.path = path
        if initlist is not None:
            self._selector = [f for f in initlist]
        else:
            self._selector = []

    def __getitem__(self, i):
        return self._selector[i]

    def __setitem__(self, i, item):
        self._selector[i] = item

    def __delitem__(self, i):
        del self._selector[i]

    def __len__(self):
        return len(self._selector)

    def insert(self, i, item):
        self._selector.insert(i, item)

    @property
    def parent_map(self):
        if self._parent_map is None:
            self._parent_map = {
                e: p for p in self.context.iter()
                for e in p.iterchildren()
            }
        return self._parent_map

    def iter_results(self):
        results = [self.context]
        for selector in self:
            results = selector(self, results)
        return results


_selector_cache = {}


def xsd_iterfind(context, path, namespaces=None):
    if path[:1] == "/":
        path = "." + path

    path_key = (id(context), path)
    try:
        selector = _selector_cache[path_key]
    except KeyError:
        parser = XPathParser(TokenMeta.registry, path, namespaces)
        token_tree = parser.parse()
        selector = XPathSelector(context, path, token_tree.iter_selectors())
        if len(_selector_cache) > 100:
            _selector_cache.clear()
        _selector_cache[path] = selector

    return selector.iter_results()


#
# XPath selectors
def iter_selector(tag=None):
    def select(context, result):
        for elem in result:
            for e in elem.iter(tag):
                if e is not elem:
                    yield e
    return select


def children_selector(tag=None):
    def select(context, result):
        for elem in result:
            for e in elem.iterchildren(tag):
                yield e
    return select


# [@attribute]
def has_attribute_selector(key):
    def select(context, result):
        for elem in result:
            if elem.attributes.get(key) is not None:
                yield elem
    return select


# @attribute
def attribute_selector(key=None):
    def select(context, result):
        if key is not None:
            for elem in result:
                if key in elem.attributes:
                    yield elem.attributes[key]
        else:
            for elem in result:
                for attr in elem.attributes:
                    yield attr
    return select


def find_selector(tag):
    def select(context, result):
        for elem in result:
            if elem.find(tag) is not None:
                yield elem
    return select


def position_selector(index):
    def select(context, result):
        i = 0
        for elem in result:
            if i == index:
                yield elem
                return
            else:
                 i += 1
    return select


# [tag='value']
def tag_value_selector(tag, value):
    def select(context, result):
        for elem in result:
            for e in elem.findall(tag):
                if "".join(e.itertext()) == value:
                    yield elem
                    break
    return select


# [@attribute='value']
def attribute_value_selector(key, value):
    def select(context, result):
        for elem in result:
            if elem.get(key) == value:
                yield elem
    return select


#
# Helper functions and decorators
def symbol(name, bp=0):
    """
    Create or update a token class.
    
    :param name: An identifier name for this token class and for its objects.
    :param bp: Binding power, default to 0.
    :return: Custom token class.
    """
    return TokenMeta(name.strip(), (Token,), {'bp': bp})


def prefix(*names):
    """
    Decorator to register a function as the null denotation method for a token class.

    :param names: A tuple of identifiers for token classes and for their objects.
    """
    def nud_decorator(func):
        for name in names:
            TokenMeta(name.strip(), (Token,), {'nud': func})
        return func
    return nud_decorator


def infix(*names, **kwargs):
    """
    Decorator to register a function as the left denotation method for a token class.
    You can also pass a keyword argument 'bp' for setting a binding power greater than 0.
    
    :param names: A tuple of identifiers for token classes and for their objects.
    """
    def led_decorator(func):
        bp = kwargs.get('bp', 0)
        for name in names:
            TokenMeta(name.strip(), (Token,), {'bp': bp, 'led': func})
        return func

    return led_decorator



# Dummy calls replaced by XPathParser instance when parsing.
advance = lambda name=None: TokenMeta.registry['(end)']()
expression = lambda rbp=0: TokenMeta.registry['(end)']()


#
# Prefix operators
@prefix('(literal)', '(end)')
def literal_or_end_nud(self):
    return self


@prefix('(ref)')
def reference_nud(self):
    self.insert(0, expression(10))
    self.sed = children_selector(self.value)
    return self


@prefix('*')
def star_token_nud(self):
    self.insert(0, expression(45))
    self.sed = children_selector()
    return self


@infix('*', bp=45)
def star_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    return self


@prefix('.', 'self::node()')
def self_token_nud(self):
    def select(context, result):
        for elem in result:
            yield elem

    self.insert(0, expression(100))
    self.sed = select
    return self


@prefix('..', 'parent::node()')
def parent_token_nud(self):
    def select(context, result):
        parent_map = context.parent_map
        result_parents = []
        for elem in result:
            try:
                parent = parent_map[elem]
            except KeyError:
                pass
            else:
                if parent not in result_parents:
                    result_parents.append(parent)
                    yield parent

    self.insert(0, expression(70))
    self.sed = select
    return self


@prefix('@', 'attribute::')
def attribute_token_nud(self):
    self.insert(0, expression(70))
    if self[0].name == '*':
        self[0].sed = attribute_selector()
    elif self[0].name == '(ref)':
        self[0].sed = attribute_selector(self[0].value)
    else:
        raise SyntaxError("invalid attribute specification")
    return self


@infix('or', bp=20)
def or_token_nud(self, left):
    self.insert(0, left)
    self.insert(1, expression(20))
    return self


@infix('and', bp=25)
def and_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(25))
    return self


@infix('=', '!=', '<', '>', '<=', '>=', bp=30)
def compare_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(30))
    return self


@infix('+', bp=40)
def add_token_nud(self, left):
    self.insert(0, left)
    self.insert(1, expression(40))
    return self


@infix('-', bp=40)
def sub_token_nud(self, left):
    self.insert(0, left)
    self.insert(1, expression(40))
    return self


@infix('div', bp=45)
def div_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    return self


@infix('mod', bp=45)
def mod_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    return self


@infix('union', '|', bp=50)
def union_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(50))
    return self


@prefix('/', 'child::')
def child_nud(self):
    self.insert(0, expression(90))
    if self[0].name == 'child::':
        right = self[0][0]
    else:
        right = self[0]
    if right.name not in ('(ref)', '*', '@', 'attribute::', 'parent::', '..'):
        raise SyntaxError("invalid child")
    return self


@prefix('//', 'descendant-or-self::')
def descendant_token_nud(self):
    self.insert(0, expression(90))
    if self[0].name == '*':
        self[0].sed = iter_selector()
    elif self[0].name == '(ref)':
        self[0].sed = iter_selector()
    if self[0].name not in ('(ref)', '*', '@', 'attribute::', 'parent::', '..'):
        raise SyntaxError("invalid descendant")
    return self


symbol('(', 80)
symbol(')', 80)


@prefix('[')
def predicate_token_nud(self):
    self.insert(0, expression(95))
    if self[0].name == '(ref)':
        self.sed = find_selector(self[0].name)
    elif self[0].name in ('@', 'attribute::'):
        self[0][0].sed = has_attribute_selector(self[0][0].value)
    elif self[0].name == '(literal)':
        try:
            self.sed = position_selector(int(self[0].value))
        except:
            raise XMLSchemaXPathError("an integer value is required")
    advance(']')
    return self


@prefix(']')
def close_predicate_token_nud(self):
    self.insert(0, expression(95))
    return self
