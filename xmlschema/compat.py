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


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    long_type = int
    unicode_type = str
    unicode_chr = chr
else:
    long_type = long
    unicode_type = unicode
    unicode_chr = unichr

