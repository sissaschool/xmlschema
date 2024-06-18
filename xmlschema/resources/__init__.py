#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from xmlschema.utils.descriptors import AttributeLink

from .sax import defuse_xml
from .xml_resource import XMLResource
from .fetchers import fetch_resource, fetch_namespaces, \
    fetch_schema_locations, fetch_schema


class ResourceLink(AttributeLink['XMLResource']):

    def __init__(self) -> None:
        super().__init__(attr_name='resource')


__all__ = ['defuse_xml', 'XMLResource', 'fetch_resource',
           'fetch_namespaces', 'fetch_schema_locations', 'fetch_schema']
