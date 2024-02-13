#
# Copyright (c), 2023, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from elementpath import XPath2Parser


class XsdAssertionXPathParser(XPath2Parser):
    """Parser for XSD 1.1 assertion facets."""


XsdAssertionXPathParser.unregister('last')
XsdAssertionXPathParser.unregister('position')


# noinspection PyUnusedLocal
@XsdAssertionXPathParser.method(  # type: ignore[no-untyped-def]
    XsdAssertionXPathParser.function('last', nargs=0))
def evaluate_last(self, context=None):
    raise self.missing_context("context item size is undefined")


# noinspection PyUnusedLocal
@XsdAssertionXPathParser.method(  # type: ignore[no-untyped-def]
    XsdAssertionXPathParser.function('position', nargs=0))
def evaluate_position(self, context=None):
    raise self.missing_context("context item position is undefined")
