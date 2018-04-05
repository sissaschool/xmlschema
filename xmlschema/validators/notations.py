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
from ..qnames import get_qname, XSD_NOTATION_TAG
from .xsdbase import XsdComponent


class XsdNotation(XsdComponent):
    """
    Class for XSD 'notation' definitions.

    <notation
      id = ID
      name = NCName
      public = token
      system = anyURI
      {any attributes with non-schema namespace}...>
      Content: (annotation?)
    </notation>
    """
    def __init__(self, elem, schema, is_global=True):
        super(XsdNotation, self).__init__(elem, schema, is_global=is_global)

    @property
    def built(self):
        return True

    @property
    def admitted_tags(self):
        return {XSD_NOTATION_TAG}

    def _parse(self):
        super(XsdNotation, self)._parse()
        if not self.is_global:
            self._parse_error("a notation declaration must be global.", self.elem)
        try:
            self.name = get_qname(self.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self._parse_error("a notation must have a 'name'.", self.elem)

        for key in self.elem.attrib:
            if key not in {'id', 'name', 'public', 'system'}:
                self._parse_error("wrong attribute %r for notation definition." % key, self.elem)
            if 'public' not in self.elem.attrib and 'system' not in self.elem.attrib:
                self._parse_error("a notation may have 'public' or 'system' attribute.", self.elem)

    @property
    def public(self):
        return self.elem.get('public')

    @property
    def system(self):
        return self.elem.get('system')
