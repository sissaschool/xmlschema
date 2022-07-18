#
# Copyright (c), 2016-2021, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# Auto-generated code: don't edit this file
#
"""
Sample of XML data bindings for schema collection.xsd
"""
import xmlschema
from xmlschema.dataobjects import DataElement, DataBindingMeta

__NAMESPACE__ = "http://example.com/ns/collection"

schema = xmlschema.XMLSchema11("collection.xsd")


class CollectionBinding(DataElement, metaclass=DataBindingMeta):
    xsd_element = schema.elements['collection']


class PersonBinding(DataElement, metaclass=DataBindingMeta):
    xsd_element = schema.elements['person']
