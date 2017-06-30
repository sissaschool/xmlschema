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
from ..exceptions import XMLSchemaParseError
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
    FACTORY_KWARG = 'notation_factory'
    XSD_GLOBAL_TAG = XSD_NOTATION_TAG

    def __init__(self, elem, schema, is_global=False, **options):
        super(XsdNotation, self).__init__(elem.get('name', ''), elem, schema, is_global=is_global, **options)

    def _parse(self):
        super(XsdNotation, self)._parse()
        if not self.is_global:
            self.schema.errors.append(XMLSchemaParseError(
                "a notation declaration must be global.", self
            ))
        try:
            self.name = get_qname(self.schema.target_namespace, self.elem.attrib['name'])
        except KeyError:
            self.schema.errors.append(
                XMLSchemaParseError("a notation must have a 'name'.", self)
            )

        for key in self.elem.attrib:
            if key not in {'id', 'name', 'public', 'system'}:
                self.schema.errors.append(XMLSchemaParseError(
                    "wrong attribute %r for notation definition." % key, self
                ))
            if 'public' not in self.elem.attrib and 'system' not in self.elem.attrib:
                self.schema.errors.append(XMLSchemaParseError(
                    "a notation may have 'public' or 'system' attribute.", self
                ))

    @property
    def public(self):
        return self._attrib.get('public')

    @property
    def system(self):
        return self._attrib.get('system')
