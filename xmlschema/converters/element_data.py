#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from collections import namedtuple


ElementData = namedtuple('ElementData',
                         ['tag', 'text', 'content', 'attributes', 'xmlns'],
                         defaults=(None, None, None, None))
"""
Namedtuple for Element data interchange between decoders and converters.
The field *tag* is a string containing the Element's tag, *text* can be `None`
or a string representing the Element's text, *content* can be `None`, a list
containing the Element's children or a dictionary containing element name to
list of element contents for the Element's children (used for unordered input
data), *attributes* can be `None` or a dictionary containing the Element's
attributes, *xmlns* can be `None` or a list of couples containing namespace
declarations.
"""
