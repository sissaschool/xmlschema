#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import io
from pathlib import Path
from typing import cast, IO, Optional, Union
from urllib.parse import urlsplit
from urllib.request import urlopen

from xml.sax import SAXParseException
from xml.sax import expatreader  # type: ignore[attr-defined]
from xml.dom import pulldom

from ._parser import SafeExpatParser
from .typing import IOProtocol, XMLSourceType, ResourceType


def get_resource(xml_source: XMLSourceType, timeout: int = 300) -> Optional[ResourceType]:
    """
    Returns a seekable resource or `None` if the argument is already
    an Element or an ElementTree object.
    """
    if isinstance(xml_source, Path):
        return xml_source.open(mode='r')
    elif isinstance(xml_source, str):
        if '\n' in xml_source or xml_source.lstrip().startswith('<'):
            return io.StringIO(xml_source)
        elif urlsplit(xml_source).scheme:
            return cast(ResourceType, urlopen(xml_source, timeout=timeout))
        else:
            return open(xml_source)

    elif isinstance(xml_source, bytes):
        if b'\n' in xml_source or xml_source.lstrip().startswith(b'<'):
            return io.BytesIO(xml_source)
        elif urlsplit(xml_source).scheme:
            return cast(ResourceType, urlopen(xml_source.decode(), timeout=timeout))
        else:
            return open(xml_source.decode())

    elif isinstance(xml_source, (io.StringIO, io.BytesIO)):
        return xml_source
    elif hasattr(xml_source, 'read'):
        if not hasattr(xml_source, 'seekable') or not xml_source.seekable():
            return io.BufferedReader(cast(io.RawIOBase, xml_source))
        return cast(ResourceType, xml_source)
    else:
        return None


def defuse_xml(xml_source: XMLSourceType) -> Optional[ResourceType]:
    resource = get_resource(xml_source)
    if resource is not None:
        parser = SafeExpatParser()
        try:
            for event, node in pulldom.parse(resource, parser):
                if event == pulldom.START_ELEMENT:
                    break
        except SAXParseException:
            pass  # the purpose is to defuse not to check xml source syntax
        finally:
            resource.seek(0)

    return resource


__all__ = ['get_resource', 'defuse_xml']
