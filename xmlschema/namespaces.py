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
from typing import Any, Container, Dict, Iterator, List, Optional, MutableMapping, \
    Mapping, TypeVar

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .helpers import local_name
from .aliases import NamespacesType


###
# Base classes for managing namespaces

class NamespaceResourcesMap(MutableMapping[str, Any]):
    """
    Dictionary for storing information about namespace resources. The values are
    lists of objects. Setting an existing value appends the object to the value.
    Setting a value with a list sets/replaces the value.
    """
    __slots__ = ('_store',)

    def __init__(self, *args: Any, **kwargs: Any):
        self._store: Dict[str, List[Any]] = {}
        self.update(*args, **kwargs)

    def __getitem__(self, uri: str) -> Any:
        return self._store[uri]

    def __setitem__(self, uri: str, value: Any) -> None:
        if isinstance(value, list):
            self._store[uri] = value[:]
        else:
            try:
                self._store[uri].append(value)
            except KeyError:
                self._store[uri] = [value]

    def __delitem__(self, uri: str) -> None:
        del self._store[uri]

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return repr(self._store)

    def clear(self) -> None:
        self._store.clear()


class NamespaceMapper(MutableMapping[str, str]):
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
    __slots__ = '_namespaces', 'strip_namespaces', '__dict__'
    _namespaces: NamespacesType

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 strip_namespaces: bool = False):
        self._namespaces = {} if namespaces is None else namespaces
        self.strip_namespaces = strip_namespaces

    def __getitem__(self, prefix: str) -> str:
        return self._namespaces[prefix]

    def __setitem__(self, prefix: str, uri: str) -> None:
        self._namespaces[prefix] = uri

    def __delitem__(self, prefix: str) -> None:
        del self._namespaces[prefix]

    def __iter__(self) -> Iterator[str]:
        return iter(self._namespaces)

    def __len__(self) -> int:
        return len(self._namespaces)

    @property
    def namespaces(self) -> NamespacesType:
        return self._namespaces

    @property
    def default_namespace(self) -> Optional[str]:
        return self._namespaces.get('')

    def clear(self) -> None:
        self._namespaces.clear()

    def insert_item(self, prefix: str, uri: str) -> None:
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

    def map_qname(self, qname: str) -> str:
        """
        Converts an extended QName to the prefixed format. Only registered
        namespaces are mapped.

        :param qname: a QName in extended format or a local name.
        :return: a QName in prefixed format or a local name.
        """
        if self.strip_namespaces:
            return local_name(qname)

        try:
            if qname[0] != '{' or not self._namespaces:
                return qname
            namespace, local_part = qname[1:].split('}')
        except IndexError:
            return qname
        except ValueError:
            raise XMLSchemaValueError("the argument 'qname' has an invalid value %r" % qname)
        except TypeError:
            raise XMLSchemaTypeError("the argument 'qname' must be a string-like object")

        for prefix, uri in sorted(self._namespaces.items(), reverse=True):
            if uri == namespace:
                return f'{prefix}:{local_part}' if prefix else local_part
        else:
            return qname

    def unmap_qname(self, qname: str,
                    name_table: Optional[Container[Optional[str]]] = None) -> str:
        """
        Converts a QName in prefixed format or a local name to the extended QName format.
        Local names are converted only if a default namespace is included in the instance.
        If a *name_table* is provided a local name is mapped to the default namespace
        only if not found in the name table.

        :param qname: a QName in prefixed format or a local name
        :param name_table: an optional lookup table for checking local names.
        :return: a QName in extended format or a local name.
        """
        if self.strip_namespaces:
            return local_name(qname)

        try:
            if qname[0] == '{' or not self._namespaces:
                return qname
            prefix, name = qname.split(':')
        except IndexError:
            return qname
        except ValueError:
            if ':' in qname:
                raise XMLSchemaValueError("the argument 'qname' has an invalid value %r" % qname)

            default_namespace = self._namespaces.get('')
            if not default_namespace:
                return qname
            elif name_table is None or qname not in name_table:
                return f'{{{default_namespace}}}{qname}'
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
                return f'{{{uri}}}{name}' if uri else name

    def transfer(self, namespaces: NamespacesType) -> None:
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


T = TypeVar('T')


class NamespaceView(Mapping[str, T]):
    """
    A read-only map for filtered access to a dictionary that stores
    objects mapped from QNames in extended format.
    """
    __slots__ = 'target_dict', 'namespace', '_key_prefix'

    def __init__(self, qname_dict: Dict[str, T], namespace_uri: str):
        self.target_dict = qname_dict
        self.namespace = namespace_uri
        self._key_prefix = f'{{{namespace_uri}}}' if namespace_uri else ''

    def __getitem__(self, key: str) -> T:
        return self.target_dict[self._key_prefix + key]

    def __len__(self) -> int:
        if not self.namespace:
            return len([k for k in self.target_dict if not k or k[0] != '{'])
        return len([k for k in self.target_dict
                    if k and k[0] == '{' and self.namespace == k[1:k.rindex('}')]])

    def __iter__(self) -> Iterator[str]:
        if not self.namespace:
            for k in self.target_dict:
                if not k or k[0] != '{':
                    yield k
        else:
            for k in self.target_dict:
                if k and k[0] == '{' and self.namespace == k[1:k.rindex('}')]:
                    yield k[k.rindex('}') + 1:]

    def __repr__(self) -> str:
        return '%s(%s)' % (self.__class__.__name__, str(self.as_dict()))

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return self._key_prefix + key in self.target_dict
        return key in self.target_dict

    def __eq__(self, other: Any) -> Any:
        return self.as_dict() == other

    def as_dict(self, fqn_keys: bool = False) -> Dict[str, T]:
        if not self.namespace:
            return {
                k: v for k, v in self.target_dict.items() if not k or k[0] != '{'
            }
        elif fqn_keys:
            return {
                k: v for k, v in self.target_dict.items()
                if k and k[0] == '{' and self.namespace == k[1:k.rindex('}')]
            }
        else:
            return {
                k[k.rindex('}') + 1:]: v for k, v in self.target_dict.items()
                if k and k[0] == '{' and self.namespace == k[1:k.rindex('}')]
            }
