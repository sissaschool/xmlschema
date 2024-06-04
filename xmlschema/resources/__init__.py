#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from xmlschema.resources.typing import IOProtocol, FileWrapperProtocol, \
    XMLSourceType, ResourceNodeType
from xmlschema.resources._resource import XMLResource
from xmlschema.resources.utils import fetch_resource, fetch_namespaces, \
    fetch_schema_locations, fetch_schema