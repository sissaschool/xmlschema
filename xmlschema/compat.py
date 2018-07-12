# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains imports and definitions for Python 2 and 3 compatibility.
"""
import sys
from collections import OrderedDict

try:
    # Python 3 imports
    from urllib.request import urlopen, urljoin, urlsplit, pathname2url
    from urllib.parse import uses_relative, urlparse, urlunsplit
    from urllib.error import URLError
    from io import StringIO
except ImportError:
    # Python 2 imports
    from urllib import pathname2url
    from urllib2 import urlopen, URLError
    from urlparse import urlsplit, urljoin, uses_relative, urlparse, urlunsplit
    from StringIO import StringIO  # the io.StringIO accepts only unicode type


PY3 = sys.version_info[0] == 3

if PY3:
    long_type = int
    string_base_type = str
    unicode_type = str
    unicode_chr = chr
else:
    long_type = long
    string_base_type = basestring
    unicode_type = unicode
    unicode_chr = unichr

ordered_dict_class = dict if sys.version_info >= (3, 6) else OrderedDict


def add_metaclass(metaclass):
    """
    Class decorator for creating a class with a metaclass.
    From `six` package source code: https://bitbucket.org/gutworth/six/overview.
    """
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper
