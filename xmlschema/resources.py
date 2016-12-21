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
import logging
import errno
import os.path

from .core import (
    etree_fromstring, etree_parse_error, urlsplit, urljoin, urlopen, uses_relative, URLError
)
from .exceptions import XMLSchemaOSError

logger = logging.getLogger(__name__)


def read_text_file(filename):
    """
    Read a text file and return a unicode string.
    :param filename:
    """
    try:
        with open(filename, encoding='utf-8') as text_file:
            return str(text_file.read())
    except UnicodeDecodeError:
        with open(filename, 'rb') as text_file:
            return str(text_file.read().decode('iso-8859-1'))
    except TypeError:
        # Python 2.x fallback
        try:
            with open(filename) as text_file:
                return unicode(text_file.read())
        except UnicodeDecodeError:
            import codecs
            with codecs.open(filename, 'r', 'iso-8859-1') as coded_file:
                return coded_file.read()


def load_uri_or_file(uri_or_path, base_uri=None):
    uri_parts = urlsplit(uri_or_path)
    uri_or_path = uri_parts.geturl()
    if uri_parts.scheme:
        # The argument is a well formed uri
        try:
            return urlopen(uri_or_path).read().decode('utf-8'), uri_or_path
        except (URLError, ValueError):
            if base_uri is None or uri_parts.scheme not in uses_relative:
                raise
            uri_parts = urlsplit(urljoin(base_uri, os.path.basename(uri_parts.path)))
    else:
        # The argument is a file path
        try:
            return read_text_file(uri_or_path), u'file://%s' % os.path.abspath(uri_or_path)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise
            if base_uri is None:
                uri_parts = urlsplit(urljoin(__file__, uri_or_path))
            else:
                uri_parts = urlsplit(urljoin(base_uri, uri_or_path))

    # Fallback tentative using a specific base_uri
    uri_or_path = uri_parts.geturl()
    if uri_parts.scheme:
        return urlopen(uri_or_path).read().decode('utf-8'), uri_or_path
    else:
        return read_text_file(uri_or_path), urljoin('file://', os.path.abspath(uri_or_path))


def load_resource(locations, base_uri):
    for location in locations.split():
        try:
            return load_uri_or_file(location, base_uri)
        except (OSError, IOError) as err:
            logger.info("Error accessing Location '%s': %s", location, err)
    else:
        raise XMLSchemaOSError(
            "no URI or file available to retrieve the resource: '%s'" % locations
        )


def load_xml(source):
    """
    This function is usable for loading XML data files of small or medium size.
    Returns a tuple with the XML source, the XML e-tree and the URI.

    :param source: A string with XML data or the name of the file containing
    the XML data or an URI that refers to the xml resource or a file-like object.
    :return: a tuple with three items: XML text, root Element and XML URI
    """
    try:
        # The source is a file-like object containing XML data
        xml_data = source.read()
        source.close()
        return xml_data, etree_fromstring(xml_data), getattr(source, 'name', None)
    except AttributeError:
        try:
            # Try il the source is a string containing XML data
            return source, etree_fromstring(source), None
        except TypeError:
            raise TypeError(
                "a file-like or a bytes-like object is required, not %r" % source.__class__.__name__
            )
        except etree_parse_error:
            xml_data, uri = load_uri_or_file(source)
            return xml_data, etree_fromstring(xml_data), uri
