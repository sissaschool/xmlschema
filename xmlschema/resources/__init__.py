#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from xmlschema.resources._typing import IOProtocol, FileWrapperProtocol, \
    SourceType, XMLSourceType, ResourceType, ResourceNodeType
from xmlschema.resources._defuse import SafeExpatParser, defuse_xml
from xmlschema.resources._resource import XMLResource
from xmlschema.resources._utils import fetch_resource, fetch_namespaces, \
    fetch_schema_locations, fetch_schema