#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains classes for managing maps related to namespaces.
"""
import re
from collections.abc import MutableMapping, Mapping

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .helpers import get_namespace, local_name


###
# Base classes for managing namespaces

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
            self._store[uri] = value[:]
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
    A class to map/unmap namespace prefixes to URIs. The mapped namespaces are
    automatically registered when set. Namespaces can be updated overwriting
    the existing registration or inserted using an alternative prefix.

    :param namespaces: initial data with namespace prefixes and URIs. \
    The provided dictionary is bound with the instance, otherwise a new \
    empty dictionary is used.
    :param strip_namespaces: if set to `True` uses name mapping methods that strip \
    namespace information.
    """
    def __init__(self, namespaces=None, strip_namespaces=False):
        if namespaces is None:
            self._namespaces = {}
        else:
            self._namespaces = namespaces
        self.strip_namespaces = strip_namespaces

    def __setattr__(self, name, value):
        if name == 'strip_namespaces':
            if value:
                self.map_qname = self.unmap_qname = self._local_name
            elif getattr(self, 'strip_namespaces', False):
                self.map_qname = self._map_qname
                self.unmap_qname = self._unmap_qname
        super(NamespaceMapper, self).__setattr__(name, value)

    def __getitem__(self, prefix):
        return self._namespaces[prefix]

    def __setitem__(self, prefix, uri):
        self._namespaces[prefix] = uri

    def __delitem__(self, prefix):
        del self._namespaces[prefix]

    def __iter__(self):
        return iter(self._namespaces)

    def __len__(self):
        return len(self._namespaces)

    @property
    def namespaces(self):
        return self._namespaces

    @property
    def default_namespace(self):
        return self._namespaces.get('')

    def clear(self):
        self._namespaces.clear()

    def insert_item(self, prefix, uri):
        """
        A method for setting an item that checks the prefix before inserting.
        In case of collision the prefix is changed adding a numerical suffix.
        """
        if not prefix:
            if '' not in self._namespaces:
                self._namespaces[prefix] = uri
                return
            elif self._namespaces[''] == uri:
                return
            prefix = 'default'

        while prefix in self._namespaces:
            if self._namespaces[prefix] == uri:
                return
            match = re.search(r'(\d+)$', prefix)
            if match:
                index = int(match.group()) + 1
                prefix = prefix[:match.span()[0]] + str(index)
            else:
                prefix += '0'
        self._namespaces[prefix] = uri

    def _map_qname(self, qname):
        """
        Converts an extended QName to the prefixed format. Only registered
        namespaces are mapped.

        :param qname: a QName in extended format or a local name.
        :return: a QName in prefixed format or a local name.
        """
        try:
            if qname[0] != '{' or not self._namespaces:
                return qname
            namespace, local_part = qname[1:].split('}')
        except IndexError:
            return qname
        except ValueError:
            raise XMLSchemaValueError("the argument 'qname' has a wrong format: %r" % qname)
        except TypeError:
            raise XMLSchemaTypeError("the argument 'qname' must be a string-like object")

        for prefix, uri in sorted(self._namespaces.items(), reverse=True):
            if uri == namespace:
                return '%s:%s' % (prefix, local_part) if prefix else local_part
        else:
            return qname

    map_qname = _map_qname

    def _unmap_qname(self, qname, name_table=None):
        """
        Converts a QName in prefixed format or a local name to the extended QName format.
        Local names are converted only if a default namespace is included in the instance.
        If a *name_table* is provided a local name is mapped to the default namespace
        only if not found in the name table.

        :param qname: a QName in prefixed format or a local name
        :param name_table: an optional lookup table for checking local names.
        :return: a QName in extended format or a local name.
        """
        try:
            if qname[0] == '{' or not self._namespaces:
                return qname
            prefix, name = qname.split(':')
        except IndexError:
            return qname
        except ValueError:
            if ':' in qname:
                raise XMLSchemaValueError("the argument 'qname' has a wrong format: %r" % qname)
            if not self._namespaces.get(''):
                return qname
            elif name_table is None or qname not in name_table:
                return '{%s}%s' % (self._namespaces.get(''), qname)
            else:
                return qname
        except (TypeError, AttributeError):
            raise XMLSchemaTypeError("the argument 'qname' must be a string-like object")
        else:
            try:
                uri = self._namespaces[prefix]
            except KeyError:
                return qname
            else:
                return '{%s}%s' % (uri, name) if uri else name

    unmap_qname = _unmap_qname

    @staticmethod
    def _local_name(qname, *_args, **_kwargs):
        return local_name(qname)

    def transfer(self, namespaces):
        """
        Transfers compatible prefix/namespace registrations from a dictionary.
        Registrations added to namespace mapper instance are deleted from argument.

        :param namespaces: a dictionary containing prefix/namespace registrations.
        """
        transferred = []
        for k, v in namespaces.items():
            if k in self._namespaces:
                if v != self._namespaces[k]:
                    continue
            else:
                self[k] = v
            transferred.append(k)

        for k in transferred:
            del namespaces[k]


class NamespaceView(Mapping):
    """
    A read-only map for filtered access to a dictionary that stores objects mapped from QNames.
    """
    def __init__(self, qname_dict, namespace_uri):
        self.target_dict = qname_dict
        self.namespace = namespace_uri
        if namespace_uri:
            self._key_fmt = '{' + namespace_uri + '}%s'
        else:
            self._key_fmt = '%s'

    def __getitem__(self, key):
        return self.target_dict[self._key_fmt % key]

    def __len__(self):
        return len(self.as_dict())

    def __iter__(self):
        return iter(self.as_dict())

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str(self.as_dict()))

    def __contains__(self, key):
        return self._key_fmt % key in self.target_dict

    def __eq__(self, other):
        return self.as_dict() == dict(other.items())

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
