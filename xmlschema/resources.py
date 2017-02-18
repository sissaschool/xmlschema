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
import os.path

from .core import (
    PY3, etree_fromstring, etree_tostring, etree_parse_error, etree_iselement,
    urlsplit, urljoin, urlopen, uses_relative, unicode_type, URLError
)
from .exceptions import (
    XMLSchemaTypeError, XMLSchemaParseError, XMLSchemaValueError, XMLSchemaURLError
)


def load_text_file(filename):
    """
    Reads a text file (coded with ASCII, UTF-8 or ISO-8859-1) into a string.
    With Python 2 returns an ascii string with encoded Unicode characters.

    :param filename:
    :return: A string.
    """
    try:
        with open(filename, encoding='utf-8') as text_file:
            return str(text_file.read())
    except UnicodeDecodeError:
        with open(filename, 'rb') as text_file:
            return str(text_file.read().decode('iso-8859-1'))
    except TypeError:
        # Python 2.x fallback
        import codecs
        try:
            with codecs.open(filename, mode='r', encoding='utf-8') as text_file:
                return text_file.read().encode('utf-8')
        except UnicodeDecodeError:
            with codecs.open(filename, mode='rb', encoding='iso-8859-1') as text_file:
                return text_file.read().encode('utf-8')


def load_xml_resource(source, element_only=True):
    """
    Examines the source and returns the root Element of an ElementTree structure,
    the XML text and an uri, if available. Returns only the root Element if the
    optional argument "element_only" is False. This function is usable for XML
    data files of small or medium sizes, as XSD schemas.

    :param source: An Element or a string with XML data or the name of the file
    or an URI that refers to the XML resource or a file-like object.
    :param element_only: If True the function returns only the Element.
    :return: a tuple with three items (root Element, XML text and XML URI) or
    only the root Element if element_only is True.
    """
    if etree_iselement(source):
        return source if element_only else (source, etree_tostring(source), None)

    try:
        # obj is a file-like object containing XML data
        xml_data = source.read()
    except AttributeError:
        if not isinstance(source, (str, bytes, unicode_type)):
            raise XMLSchemaTypeError(
                "a file-like or a bytes-like object is required"
                ", not %r." % source.__class__.__name__
            )

        try:
            xml_data, xml_uri = load_resource(source)
            res_err = None
        except (OSError, IOError, ValueError, XMLSchemaURLError) as err:
            xml_data, xml_uri = source, None
            res_err = err
        except XMLSchemaTypeError as err:
            raise type(err)("an element, %s" % err)

    else:
        xml_uri = getattr(source, 'name', getattr(source, 'uri', None))
        source.close()
        res_err = None

    try:
        xml_root = etree_fromstring(xml_data)
    except (etree_parse_error, UnicodeEncodeError) as err:
        raise res_err or XMLSchemaParseError(
            "error parsing XML data from %r: %s" % (xml_uri or type(xml_data), err)
        )

    return xml_root if element_only else (xml_root, xml_data, xml_uri)


def load_resource(locations, base_uri=None):
    """
    Load resource from the first available URI, decoding into a UTF-8 string.
    If no URI is available raise an XMLSchemaOSError.

    :param locations: String-like object with a space separated list of URIs.
    :param base_uri: The reference base uri for completing local URIs.
    :return: Resource as unicode string ad the loaded URI.
    """
    if locations is None or not locations.strip():
        raise XMLSchemaValueError("No locations")

    errors = []
    for location in locations.strip().split():
        try:
            resource, uri = open_resource(location, base_uri)
        except XMLSchemaURLError as err:
            errors.append(err.reason)
            continue

        try:
            data = resource.read()
        except (OSError, IOError) as err:
            errors.append(err)
        else:
            resource.close()
            break
    else:
        raise XMLSchemaURLError(
            reason="cannot load resource from %r: %s" % (locations, errors)
        )

    if PY3:
        try:
            return data.decode('utf-8'), uri
        except UnicodeDecodeError:
            return data.decode('iso-8859-1'), uri
    else:
        try:
            return data.encode('utf-8'), uri
        except UnicodeDecodeError:
            import codecs
            with codecs.open(urlsplit(uri).path, mode='rb', encoding='iso-8859-1') as text_file:
                return text_file.read().encode('utf-8'), uri


def open_resource(locations, base_uri=None):
    if locations is None or not locations.strip():
        raise XMLSchemaValueError("No locations")

    errors = []
    for location in locations.strip().split():
        uri_parts = urlsplit(location)
        uri = uri_parts.geturl()
        if uri_parts.scheme:
            # The location is a well formed uri
            try:
                return urlopen(uri), uri
            except URLError as err:
                errors.append(err.reason)
                if base_uri is None or uri_parts.scheme not in uses_relative:
                    continue
                uri_parts = urlsplit(urljoin(base_uri, os.path.basename(uri_parts.path)))
        else:
            # The location is a file path
            absolute_uri = u'file://%s' % os.path.abspath(uri)
            try:
                return urlopen(absolute_uri), absolute_uri
            except URLError as err:
                errors.append(err.reason)
                if base_uri is None:
                    uri_parts = urlsplit(urljoin(__file__, uri))
                else:
                    uri_parts = urlsplit(urljoin(base_uri, uri))

        # Fallback tentative using a specific base_uri
        uri = uri_parts.geturl()
        if not uri_parts.scheme:
            uri = urljoin('file://', os.path.abspath(uri))
        try:
            return urlopen(uri), uri
        except URLError:
            pass
    else:
        raise XMLSchemaURLError(
            reason="cannot access resource from %r: %s" % (locations, errors)
        )
