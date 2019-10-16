# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2019, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from __future__ import unicode_literals

from ..qnames import XSD_NOTATION, get_qname
from .xsdbase import XsdComponent


class XsdNotation(XsdComponent):
    """
    Class for XSD *notation* declarations.

    ..  <notation
          id = ID
          name = NCName
          public = token
          system = anyURI
          {any attributes with non-schema namespace}...>
          Content: (annotation?)
        </notation>
    """
    _ADMITTED_TAGS = {XSD_NOTATION}

    @property
    def built(self):
        return True

    def _parse(self):
        super(XsdNotation, self)._parse()
        if self.parent is not None:
            self.parse_error("a notation declaration must be global", self.elem)
        try:
            self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self.parse_error("a notation must have a 'name' attribute", self.elem)

        if 'public' not in self.elem.attrib and 'system' not in self.elem.attrib:
            self.parse_error("a notation must has a 'public' or a 'system' attribute", self.elem)

    @property
    def public(self):
        return self.elem.get('public')

    @property
    def system(self):
        return self.elem.get('system')
