#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from xml.etree.ElementTree import ParseError

from xmlschema import XMLSchemaException


class XMLResourceError(XMLSchemaException):
    """
    A generic error on an XML resource that catches all the errors generated
    by an XML resource/loader instance.
    """


class XMLResourceOSError(XMLResourceError, OSError):
    """Raised when an error is found accessing an XML resource."""


class XMLResourceParseError(XMLResourceError, ParseError):
    """Raised when an error is found parsing an XML resource."""


class XMLResourceBlocked(XMLResourceError):
    """Raised when an XML resource access is blocked by security settings."""


class XMLResourceForbidden(XMLResourceError):
    """Raised when the parsing of an XML resource is forbidden for safety reasons."""
