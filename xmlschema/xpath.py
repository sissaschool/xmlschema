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
from decimal import Decimal
from collections import MutableSequence
from abc import ABCMeta

from .exceptions import XMLSchemaXPathError, XMLSchemaSyntaxError
from .qnames import reference_to_qname


_RE_SPLIT_PATH = re.compile(r'/(?![^{}]*})')


def split_path(path):
    return _RE_SPLIT_PATH.split(path)


#
# XPath tokenizer
def get_xpath_tokenizer_pattern(symbols):
    tokenizer_pattern_template = r"""
        ('[^']*' | "[^"]*" | \d+(?:\.\d?)? | \.\d+) |   # Literals (strings or numbers)
        (%s | [%s]) |                                   # Symbols
        ((?:{[^}]+\})?[^/\[\]()@=\s]+) |                # References and other names   
        \s+                                             # Skip extra spaces
        """

    def tokens_escape(s):
        s = re.escape(s)
        if s[-2:] == r'\(':
            s = '%s\s*%s' % (s[:-2], s[-2:])
        elif s[-4:] == r'\:\:':
            s = '%s\s*%s' % (s[:-4], s[-4:])
        return s

    symbols.sort(key=lambda x: -len(x))
    fence = len([i for i in symbols if len(i) > 1])
    return tokenizer_pattern_template % (
        '|'.join(map(tokens_escape, symbols[:fence])),
        ''.join(map(re.escape, symbols[fence:]))
    )


XPATH_SYMBOLS = [
    'processing-instruction(', 'descendant-or-self::', 'following-sibling::',
    'preceding-sibling::', 'ancestor-or-self::', 'descendant::', 'attribute::',
    'following::', 'namespace::', 'preceding::', 'ancestor::', 'comment(', 'parent::',
    'child::', 'self::', 'text(', 'node(', 'and', 'mod', 'div', 'or',
    '..', '//', '!=', '<=', '>=', '(', ')', '[', ']', '.', '@', ',', '/', '|', '*',
    '-', '=', '+', '<', '>',

    # XPath Core function library
    'last(', 'position(',  # Node set functions
    'not(', 'true(', 'false('  # Boolean functions
    
    # added in XPath 2.0
    'union'
]

xpath_tokens_regex = re.compile(get_xpath_tokenizer_pattern(XPATH_SYMBOLS), re.VERBOSE)


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
        lbp = _dict['lbp'] = _dict.pop('lbp', 0)
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
        self.value = value if value is not None else self.name
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
        for t in self[:1]:
            for token in t.iter():
                yield token
        yield self
        for t in self[1:]:
            for token in t.iter():
                yield token

    def iter_selectors(self):
        for t in self[:1]:
            for sed in t.iter_selectors():
                yield sed
        if hasattr(self, 'sed'):
            yield self.sed
        if self.name != '[':
            for t in self[1:]:
                for sed in t.iter_selectors():
                    yield sed

    def expected(self, name):
        if self.name != name:
            raise XMLSchemaXPathError("Expected %r token, found %r." % (name, str(self.value)))

    def unexpected(self, name=None):
        if not name or self.name == name:
            raise XMLSchemaXPathError("Unexpected %r token." % str(self.value))

    #
    # XPath selectors
    @staticmethod
    def self_selector():
        def select(context, results):
            for elem in results:
                yield elem
        return select

    def descendant_selector(self):
        def select(context, results):
            for elem in results:
                for e in elem.iter(self.value):
                    if e is not elem:
                        yield e
        return select

    def children_selector(self):
        def select(context, results):
            for elem in results:
                for e in elem.iterchildren(self.value):
                    yield e
        return select

    def value_selector(self):
        def select(context, results):
            for _ in results:
                yield self.value
        return select

    # @attribute
    def attribute_selector(self):
        key = self.value

        def select(context, results):
            if key is not None:
                for elem in results:
                    if key in elem.attributes:
                        yield elem.attributes[key]
            else:
                for elem in results:
                    for attr in elem.attributes.values():
                        yield attr
        return select

    # @attribute='value'
    def attribute_value_selector(self):
        key = self.value
        value = self[0].value

        def select(context, results):
            if key is not None:
                for elem in results:
                    yield elem.get(key) == value
            else:
                for elem in results:
                    for attr in elem.attributes.values():
                        yield attr == value
        return select

    def find_selector(self):
        def select(context, results):
            for elem in results:
                if elem.find(self.value) is not None:
                    yield elem
        return select

    def subscript_selector(self):
        if self.value > 0:
            index = self.value - 1
        elif self.value == 0 or self.name not in ('last(', 'position('):
            index = None
        else:
            index = self.value

        def select(context, results):
            if index is not None:
                try:
                    yield [elem for elem in results][index]
                except IndexError:
                    return
        return select

    def predicate_selector(self):
        selectors = [f for f in self.iter_selectors()]

        def select(context, results):
            for elem in results:
                predicate_results = [elem]
                for selector in selectors:
                    predicate_results = selector(context, predicate_results)
                predicate_results = list(predicate_results)
                if predicate_results and any(predicate_results):
                    yield elem
        return select

    @staticmethod
    def parent_selector():
        def select(context, results):
            parent_map = context.parent_map
            results_parents = []
            for elem in results:
                try:
                    parent = parent_map[elem]
                except KeyError:
                    pass
                else:
                    if parent not in results_parents:
                        results_parents.append(parent)
                        yield parent
        return select

    # [tag='value']
    def tag_value_selector(self):
        def select(context, results):
            for elem in results:
                for e in elem.findall(self.name):
                    if "".join(e.itertext()) == self.value:
                        yield elem
                        break
        return select

    def disjunction_selector(self):
        def select(context, results):
            for elem in results:
                for token in self:
                    for selector in token.iter_selectors():
                        for e in selector(context, elem):
                            yield e
        return select

    def conjunction_selector(self):
        def select(context, results):
            for elem in results:
                result_set = {
                    e for selector in self[1].iter_selectors()
                    for e in selector(context, elem)
                }
                for token in self[2:]:
                    result_set &= {
                        e for selector in token.iter_selectors()
                        for e in selector(context, elem)
                    }
                for selector in self[0].iter_selectors():
                    for e in selector(context, elem):
                        if e in result_set:
                            yield e
        return select


#
# Helper functions/decorators
def symbol(name, lbp=0):
    """
    Create or update a token class. If the symbol is already registered
    just update the left binding power if it has a greater value.

    :param name: An identifier name for this token class and for its objects.
    :param lbp: Left binding power, default to 0.
    :return: Custom token class.
    """
    return TokenMeta(name.strip(), (Token,), {'lbp': lbp})


def register_symbols(*names, **kwargs):
    """
    Create or update token classes for a sequence of symbols. Pass a keyword argument 
    'lbp' for setting a left binding power greater than 0. If a symbol is already 
    registered just update the left binding power if it has a greater value.

    :param names: A tuple of identifiers for token classes and for their objects.
    """
    lbp = kwargs.pop('lbp', 0)
    for name in names:
        TokenMeta(name.strip(), (Token,), {'lbp': lbp})


def register_nud(*names, **kwargs):
    """
    Decorator to register a function as the null denotation method for a token class.
    Pass a keyword argument 'lbp' for setting a left binding power greater than 0.

    :param names: A tuple of identifiers for token classes and for their objects.
    """

    def nud_decorator(func):
        lbp = kwargs.pop('lbp', 0)
        for name in names:
            TokenMeta(name.strip(), (Token,), {'lbp': lbp, 'nud': func})
        return func

    return nud_decorator


def register_led(*names, **kwargs):
    """
    Decorator to register a function as the left denotation method for a token class.
    Pass a keyword argument 'lbp' for setting a left binding power greater than 0.

    :param names: A tuple of identifiers for token classes and for their objects.
    """

    def led_decorator(func):
        lbp = kwargs.get('lbp', 0)
        for name in names:
            TokenMeta(name.strip(), (Token,), {'lbp': lbp, 'led': func})
        return func

    return led_decorator


#
# XPath parser
RELATIVE_PATH_TOKENS = {s for s in XPATH_SYMBOLS if s.endswith("::")} | {
    '(integer)', '(string)', '(decimal)', '(ref)', '*', '@', '..', '.', '(', '/'
}


def dummy_advance(name=None):
    return symbol('(end)')

advance = dummy_advance  # Replaced by active parser
current_token = None
next_token = None


def expression(rbp=0):
    """
    Recursive expression parser for expressions. Calls token.nud() and then 
    advance until the right binding power is less the left binding power of 
    the next token, invoking the led() method on the following token.

    :param rbp: right binding power for the expression.
    :return: left token.
    """
    global current_token, next_token
    advance()
    left = current_token.nud()
    while rbp < next_token.lbp:
        advance()
        left = current_token.led(left)
    return left


class XPathParser(object):
    """
    XPath expression iterator parser class.

    :param token_table: Dictionary with XPath grammar's tokens.
    :param path: XPath expression.
    :param namespaces: optional prefix to namespace map.
    """

    def __init__(self, token_table, path, namespaces=None):
        if not path:
            raise XMLSchemaXPathError("Empty XPath expression.")
        elif path[-1] == '/':
            raise XMLSchemaXPathError("Invalid path: %r" % path)
        if path[:1] == "/":
            path = "." + path

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
        global current_token, next_token
        if name:
            next_token.expected(name)

        while True:
            try:
                match = next(self._tokens)
            except StopIteration:
                current_token, next_token = next_token, self.token_table['(end)']()
                break
            else:
                current_token = next_token
                literal, operator, ref = match.groups()
                if operator is not None:
                    try:
                        next_token = self.token_table[operator.replace(' ', '')]()
                    except KeyError:
                        raise XMLSchemaXPathError("Unknown operator %r." % operator)
                    break
                elif literal is not None:
                    if literal[0] in '\'"':
                        next_token = self.token_table['(string)'](literal.strip("'\""))
                    elif '.' in literal:
                        next_token = self.token_table['(decimal)'](Decimal(literal))
                    else:
                        next_token = self.token_table['(integer)'](int(literal))
                    break
                elif ref is not None:
                    value = reference_to_qname(ref, self.namespaces)
                    next_token = self.token_table['(ref)'](value)
                    break
                elif match.group().strip():
                    raise XMLSchemaXPathError("Unexpected token: %r" % match)

        return current_token

    def parse(self):
        global advance
        advance = self.advance
        self.__iter__()
        advance()
        root_token = expression()
        if next_token.name != '(end)':
            next_token.unexpected()
        return root_token


@register_nud('(end)')
def end_nud(self):
    return self


@register_nud('(string)', '(decimal)', '(integer)')
def value_nud(self):
    self.sed = self.value_selector()
    return self


@register_nud('(ref)')
def ref_token_nud(self):
    self.sed = self.children_selector()
    return self


@register_nud('*')
def star_token_nud(self):
    if next_token.name not in ('/', '[', '(end)', ')'):
        next_token.unexpected()
    self.value = None
    self.sed = self.children_selector()
    return self


@register_led('*', lbp=45)
def star_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    self.value = left.value + self[1].value
    return self


@register_nud('@', 'attribute::')
def attribute_token_nud(self):
    self.insert(0, advance())
    if self[0].name not in ('*', '(ref)'):
        raise XMLSchemaXPathError("invalid attribute specification for XPath.")
    if next_token.name != '=':
        self.sed = self[0].attribute_selector()
    else:
        advance('=')
        self[0].insert(0, advance('(string)'))
        self.sed = self[0].attribute_value_selector()
    return self


@register_led('or', lbp=20)
def or_token_nud(self, left):
    self.insert(0, left)
    self.insert(1, expression(20))
    self.sed = self.disjunction_selector()
    return self


@register_led('and', lbp=25)
def and_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(25))
    self.sed = self.conjunction_selector()
    return self


@register_nud('=', '!=', '<', '>', '<=', '>=', lbp=30)
def compare_token_nud(self):
    self.insert(0, expression(30))
    return self


@register_led('=', '!=', '<', '>', '<=', '>=', lbp=30)
def compare_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(30))
    return self


@register_nud('+')
def plus_token_nud(self):
    self.insert(0, expression(75))
    if not isinstance(self[0].value, int):
        raise XMLSchemaXPathError("an integer value is required: %r." % self[0])
    self.value = self[0].value
    return self


@register_led('+', lbp=40)
def plus_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(40))
    self.value = left.value + self[1].value
    return self


@register_nud('-')
def minus_token_nud(self):
    self.insert(0, expression(75))
    if not isinstance(self[0].value, int):
        raise XMLSchemaXPathError("an integer value is required: %r." % self[0])
    self.value = - self[0].value
    return self


@register_led('-', lbp=40)
def minus_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(40))
    self.value = left.value - self[1].value
    return self


@register_led('div', lbp=45)
def div_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    return self


@register_led('mod', lbp=45)
def mod_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(45))
    return self


@register_led('union', '|', lbp=50)
def union_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(50))
    self.sed = self.disjunction_selector()
    return self


@register_nud('.', 'self::node()', lbp=60)
def self_token_nud(self):
    self.sed = self.self_selector()
    return self


@register_nud('..', 'parent::node()', lbp=60)
def parent_token_nud(self):
    self.sed = self.parent_selector()
    return self


@register_nud('/')
def child_nud(self):
    current_token.unexpected()


@register_led('/', lbp=80)
def child_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(100))
    if self[1].name not in RELATIVE_PATH_TOKENS:
        raise XMLSchemaXPathError("invalid child %r." % self[1])
    return self


@register_nud('child::', lbp=80)
def child_axis_nud(self):
    if next_token.name not in ('(ref)', '*'):
        raise XMLSchemaXPathError("invalid child axis %r." % next_token)
    else:
        self.insert(0, expression(80))
    return self


@register_led('//', lbp=80)
def descendant_token_led(self, left):
    self.insert(0, left)
    self.insert(1, expression(100))
    if self[1].name not in RELATIVE_PATH_TOKENS:
        raise XMLSchemaXPathError("invalid descendant %r." % self[1])
    if self[0].name in ('*', '(ref)'):
        delattr(self[0], 'sed')
        self.value = self[0].value
    else:
        self.value = None
    self.sed = self.descendant_selector()
    return self


@register_nud('(', lbp=90)
def group_token_nud(self):
    next_token.unexpected(')')
    self.insert(0, expression())
    advance(')')
    return self[0]


@register_nud(')')
@register_led(')')
def right_round_bracket_token(*args, **kwargs):
    current_token.unexpected()


@register_nud('[', lbp=90)
def predicate_token_nud(self):
    current_token.unexpected()


@register_led('[', lbp=90)
def predicate_token_led(self, left):
    next_token.unexpected(']')
    self.insert(0, left)
    self.insert(1, expression())
    if isinstance(self[1].value, int):
        self.sed = self[1].subscript_selector()
    else:
        self.sed = self[1].predicate_selector()
    advance(']')
    return self


@register_nud(']')
@register_led(']')
def predicate_close_token(*args, **kwargs):
    current_token.unexpected(']')


@register_nud('last(', )
def last_token_nud(self):
    advance(')')
    if next_token.name == '-':
        advance('-')
        self.insert(0, advance('(integer)'))
        self.value = -1 - self[0].value
    else:
        self.value = -1
    return self


@register_nud('position(')
def position_token_nud(self):
    advance(')')
    advance('=')
    self.insert(0, expression(90))
    if not isinstance(self[0].value, int):
        raise XMLSchemaXPathError("an integer expression is required: %r." % self[0].value)
    self.value = self[0].value
    return self


#
# XPath selector class and functions
class XPathSelector(MutableSequence):

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

    def iter_results(self):
        results = [self.context]
        for selector in self:
            results = selector(self.context, results)
        return results


_selector_cache = {}


def xsd_iterfind(context, path, namespaces=None):
    if path[:1] == "/":
        path = "." + path

    path_key = (id(context), path)
    try:
        return _selector_cache[path_key].iter_results()
    except KeyError:
        pass

    parser = XPathParser(TokenMeta.registry, path, namespaces)
    token_tree = parser.parse()
    selector = XPathSelector(context, path, token_tree.iter_selectors())
    if len(_selector_cache) > 100:
        _selector_cache.clear()
    _selector_cache[path] = selector
    return selector.iter_results()


def relative_path(path, levels, namespaces=None):
    """
    Return a relative XPath expression.
    
    :param path: An XPath expression.
    :param levels: Number of path levels to remove.
    :param namespaces: is an optional mapping from namespace 
    prefix to full qualified name.
    :return: a string with a relative XPath expression.
    """
    parser = XPathParser(TokenMeta.registry, path, namespaces)
    token_tree = parser.parse()
    path_parts = [t.value for t in token_tree.iter()]
    i = 0
    if path_parts[0] == '.':
        i += 1
    if path_parts[i] == '/':
        i += 1
    for value in path_parts[i:]:
        if levels <= 0:
            break
        if value == '/':
            levels -= 1
        i += 1
    return ''.join(path_parts[i:])
