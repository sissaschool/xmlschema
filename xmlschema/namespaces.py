# -*- coding: utf-8 -*-
#
# Copyright (c), 2016-2018, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains namespace related constants, functions and classes.
"""
import re
from collections import Mapping, MutableMapping
from .compat import urlsplit

_RE_MATCH_NAMESPACE = re.compile(r'{([^}]*)}')

# Namespaces for W3C core standards
XSD_NAMESPACE = 'http://www.w3.org/2001/XMLSchema'
"URI of the XML Schema Definition namespace (xs|xsd)"

XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
"URI of the XML Schema Instance namespace (xsi)"

XML_NAMESPACE = 'http://www.w3.org/XML/1998/namespace'
"URI of the XML namespace (xml)"

XHTML_NAMESPACE = 'http://www.w3.org/1999/xhtml'
XHTML_DATATYPES_NAMESPACE = "http://www.w3.org/1999/xhtml/datatypes/"
"URIs of the Extensible Hypertext Markup Language namespace (html)"

XLINK_NAMESPACE = 'http://www.w3.org/1999/xlink'
"URI of the XML Linking Language (XLink)"

XSLT_NAMESPACE = "http://www.w3.org/1999/XSL/Transform"
"URI of the XSL Transformations namespace (xslt)"

HFP_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty'
"URI of the XML Schema has Facet and Property namespace (hfp)"

VC_NAMESPACE = "http://www.w3.org/2007/XMLSchema-versioning"
"URI of the XML Schema Versioning namespace (vc)"


def get_namespace(name):
    try:
        return _RE_MATCH_NAMESPACE.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


class URIDict(MutableMapping):
    """
    Dictionary which uses normalized URIs as keys.
    """
    @staticmethod
    def normalize(uri):
        return urlsplit(uri).geturl()

    def __init__(self, *args, **kwargs):
        self._store = dict()
        self._store.update(*args, **kwargs)

    def __getitem__(self, uri):
        return self._store[self.normalize(uri)]

    def __setitem__(self, uri, value):
        self._store[self.normalize(uri)] = value

    def __delitem__(self, uri):
        del self._store[self.normalize(uri)]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return repr(self._store)

    def clear(self):
        self._store.clear()


class NamespaceResourcesMap(URIDict):

    def __setitem__(self, uri, value):
        uri = self.normalize(uri)
        if isinstance(value, list):
            self._store[uri] = value
        else:
            try:
                self._store[uri].append(value)
            except KeyError:
                self._store[uri] = [value]


class NamespaceMapper(MutableMapping):
    """
    A class to map/unmap XML namespace URIs to prefixes. An instance
    memorize the used prefixes.

    :param namespaces: The reference dictionary for namespace prefix to URI mapping.
    """
    def __init__(self, namespaces=None):
        self._xmlns = {}
        self.namespaces = namespaces if namespaces is not None else {}

    def __getitem__(self, key):
        return self._xmlns[key]

    def __setitem__(self, key, value):
        self._xmlns[key] = value

    def __delitem__(self, key):
        del self._xmlns[key]

    def __iter__(self):
        return iter(self._xmlns)

    def __len__(self):
        return len(self._xmlns)

    def clear(self):
        self._xmlns.clear()

    def map_qname(self, qname):
        try:
            if qname[0] != '{' or not self.namespaces:
                return qname
        except IndexError:
            return qname

        qname_uri = get_namespace(qname)
        for prefix, uri in self.namespaces.items():
            if uri != qname_uri:
                continue
            if prefix:
                self._xmlns[prefix] = uri
                return qname.replace(u'{%s}' % uri, u'%s:' % prefix)
            else:
                if uri:
                    self._xmlns[prefix] = uri
                return qname.replace(u'{%s}' % uri, '')
        else:
            return qname

    def unmap_qname(self, qname):
        try:
            if qname[0] == '{' or not self.namespaces:
                return qname
        except IndexError:
            return qname

        try:
            prefix, name = qname.split(':', 1)
        except ValueError:
            return qname
        else:
            try:
                uri = self.namespaces[prefix]
            except KeyError:
                return qname
            else:
                self._xmlns[prefix] = uri
                return u'{%s}%s' % (uri, name)

    def transfer(self, other):
        transferred = []
        for k, v in other.items():
            if k in self:
                if v != self[k]:
                    continue
            else:
                self[k] = v
            transferred.append(k)
        for k in transferred:
            del other[k]


class NamespaceView(Mapping):
    """
    A read-only map for filtered access to a dictionary that stores objects mapped from QNames.
    """
    def __init__(self, qname_dict, namespace_uri):
        self.target_dict = qname_dict
        self.namespace = namespace_uri
        if namespace_uri:
            self.key_fmt = '{' + namespace_uri + '}%s'
        else:
            self.key_fmt = '%s'

    def __getitem__(self, key):
        return self.target_dict[self.key_fmt % key]

    def __len__(self):
        return len(self.as_dict())

    def __iter__(self):
        return iter(self.as_dict())

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self.as_dict()))

    def __contains__(self, key):
        return self.key_fmt % key in self.target_dict

    def __eq__(self, other):
        return self.as_dict() == dict(other.items())

    def copy(self, **kwargs):
        return self.__class__(self, **kwargs)

    def as_dict(self, fqn_keys=False):
        if fqn_keys:
            return {
                k: v for k, v in self.target_dict.items()
                if self.namespace == get_namespace(k)
            }
        else:
            return {
                k if k[0] != '{' else k[k.rindex('}') + 1:]: v
                for k, v in self.target_dict.items()
                if self.namespace == get_namespace(k)
            }
