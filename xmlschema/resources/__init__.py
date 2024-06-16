#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from . import typing
from ._descriptors import ResourceAttribute
from ._defuse import defuse_xml
from ._resource import XMLResource
from ._fetchers import fetch_resource, fetch_namespaces, \
    fetch_schema_locations, fetch_schema

__all__ = ['defuse_xml', 'XMLResource', 'ResourceAttribute', 'fetch_resource',
           'fetch_namespaces', 'fetch_schema_locations', 'fetch_schema']
