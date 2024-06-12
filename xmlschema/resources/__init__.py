#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from ._typing import IOProtocol, FileWrapperProtocol, SourceType, \
    XMLSourceType, ResourceType, ResourceNodeType
from ._defuse import SafeExpatParser, defuse_xml
from ._resource import XMLResource
from ._helpers import ResourceAttribute, fetch_resource, fetch_namespaces, \
    fetch_schema_locations, fetch_schema

__all__ = ['IOProtocol', 'FileWrapperProtocol', 'SourceType', 'XMLSourceType',
           'ResourceType', 'ResourceNodeType', 'SafeExpatParser', 'defuse_xml',
           'XMLResource', 'ResourceAttribute', 'fetch_resource',
           'fetch_namespaces', 'fetch_schema_locations', 'fetch_schema']
