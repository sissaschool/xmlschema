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

NAMESPACE_PATTERN = re.compile(r'{([^}]*)}')

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
        return NAMESPACE_PATTERN.match(name).group(1)
    except (AttributeError, TypeError):
        return ''


class NamespaceResourcesMap(MutableMapping):
    """
    Dictionary for storing information about namespace resources. The values are
    lists of strings. Setting an existing value appends the string to the value.
    Setting a value with a list sets/replaces the value.
    """
    def __init__(self, *args, **kwargs):
        self._store = dict()
        self.update(*args, **kwargs)

    def __getitem__(self, uri):
        return self._store[uri]

    def __setitem__(self, uri, value):
        if isinstance(value, list):
            self._store[uri] = value
        else:
            try:
                self._store[uri].append(value)
            except KeyError:
                self._store[uri] = [value]

    def __delitem__(self, uri):
        del self._store[uri]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return repr(self._store)

    def clear(self):
        self._store.clear()


class NamespaceMapper(MutableMapping):
    """
    A class to map/unmap namespace prefixes to URIs.

    :param namespaces: Initial data with namespace prefixes and URIs.
    """
    def __init__(self, namespaces=None, register_namespace=None):
        self._namespaces = {}
        self.register_namespace = register_namespace
        if namespaces is not None:
            self.update(namespaces)

    def __getitem__(self, key):
        return self._namespaces[key]

    def __setitem__(self, key, value):
        self._namespaces[key] = value
        try:
            self.register_namespace(key, value)
        except (TypeError, ValueError):
            pass

    def __delitem__(self, key):
        del self._namespaces[key]

    def __iter__(self):
        return iter(self._namespaces)

    def __len__(self):
        return len(self._namespaces)

    @property
    def default_namespace(self):
        return self._namespaces.get('')

    def clear(self):
        self._namespaces.clear()

    def map_qname(self, qname):
        try:
            if qname[0] != '{' or not self._namespaces:
                return qname
        except IndexError:
            return qname

        qname_uri = get_namespace(qname)
        for prefix, uri in self.items():
            if uri != qname_uri:
                continue
            if prefix:
                self._namespaces[prefix] = uri
                return qname.replace(u'{%s}' % uri, u'%s:' % prefix)
            else:
                if uri:
                    self._namespaces[prefix] = uri
                return qname.replace(u'{%s}' % uri, '')
        else:
            return qname

    def unmap_qname(self, qname):
        try:
            if qname[0] == '{' or not self:
                return qname
        except IndexError:
            return qname

        try:
            prefix, name = qname.split(':', 1)
        except ValueError:
            return qname
        else:
            try:
                uri = self._namespaces[prefix]
            except KeyError:
                return qname
            else:
                return u'{%s}%s' % (uri, name) if uri else name

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
