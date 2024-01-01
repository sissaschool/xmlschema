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
import copy
from collections import namedtuple
from typing import cast, Any, Callable, Container, Dict, Iterator, List, \
    Optional, MutableMapping, Mapping, Tuple, TypeVar

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .helpers import local_name, get_namespace_map, is_etree_element
from .aliases import NamespacesType, ElementType
from .resources import XMLResource

NamespaceMapperContext = namedtuple(
    'NamespaceMapperContext', ['obj', 'level', 'xmlns', 'nsmap', 'reverse']
)

XMLNS_PROCESSING_MODES = frozenset(('stacked', 'collapsed', 'root-only', 'none'))


def dummy_xmlns_getter(_elem: ElementType) -> Optional[List[Tuple[str, str]]]:
    return None


class NamespaceMapper(MutableMapping[str, str]):
    """
    A class to map/unmap namespace prefixes to URIs. An internal reverse mapping
    from URI to prefix is also maintained for keep name mapping consistent within
    updates.

    :param namespaces: initial data with mapping of namespace prefixes to URIs.
    :param process_namespaces: whether to use namespace information in name mapping \
    methods. If set to `False` then the name mapping methods simply return the \
    provided name.
    :param strip_namespaces: if set to `True` then the name mapping methods return \
    the local part of the provided name.
    :param xmlns_processing: defines the processing mode of XML namespace declarations. \
    Provide 'stacked' to process namespace declarations using a stack of contexts \
    related with elements and levels. This the processing mode that always matches \
    the XML namespace declarations defined in the XML document. Provide 'collapsed' \
    for loading all namespace declarations of the XML source before decoding. \
    Provide 'root-only' to use only the namespace declarations of the XML \
    document root. Provide 'none' to not use any namespace declaration of \
    the XML document. For default the xmlns processing mode is set automatically \
    depending on the capabilities and the scope of namespace mapper class.
    :param source: the origin of XML data. Con be an `XMLResource` instance or \
    a generic decoded data.
    """
    __slots__ = '_namespaces', '_uri_to_prefix', '_contexts', \
        '_process_namespaces', '_strip_namespaces', '_use_namespaces', \
        '_xmlns_processing', '_use_xmlns', '_source', 'get_xmlns_from_elem'

    _namespaces: NamespacesType
    _contexts: List[NamespaceMapperContext]

    get_xmlns_from_elem: Callable[[ElementType], Optional[List[Tuple[str, str]]]]
    """Returns the XML declarations from decoded element data."""

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 process_namespaces: bool = True,
                 strip_namespaces: bool = False,
                 xmlns_processing: Optional[str] = None,
                 source: Any = None) -> None:

        namespaces = get_namespace_map(namespaces)

        self._process_namespaces = process_namespaces
        self._strip_namespaces = strip_namespaces
        self._use_namespaces = bool(process_namespaces and not strip_namespaces)

        if xmlns_processing is None:
            if self.__class__ is NamespaceMapper:
                xmlns_processing = 'stacked'
            else:
                xmlns_processing = 'stacked'
        elif not isinstance(xmlns_processing, str):
            raise XMLSchemaTypeError("invalid type for argument 'xmlns_processing'")
        elif xmlns_processing not in XMLNS_PROCESSING_MODES:
            raise XMLSchemaValueError("invalid value for argument 'xmlns_processing'")

        self._source = source
        if isinstance(source, XMLResource):
            self.get_xmlns_from_elem = source.get_xmlns
            if xmlns_processing == 'collapsed':
                namespaces = source.get_namespaces(namespaces, root_only=False)
            elif xmlns_processing != 'none':
                namespaces = source.get_namespaces(namespaces, root_only=True)
        else:
            self.get_xmlns_from_elem = dummy_xmlns_getter

        self._xmlns_processing = xmlns_processing
        self._use_xmlns = xmlns_processing == 'stacked'

        self._namespaces = namespaces
        self._contexts = []
        self._uri_to_prefix = {v: k for k, v in reversed(self._namespaces.items())}

    def __getitem__(self, prefix: str) -> str:
        return self._namespaces[prefix]

    def __setitem__(self, prefix: str, uri: str) -> None:
        self._namespaces[prefix] = uri
        self._uri_to_prefix[uri] = prefix

    def __delitem__(self, prefix: str) -> None:
        uri = self._namespaces.pop(prefix)
        del self._uri_to_prefix[uri]

        for k in reversed(self._namespaces.keys()):
            if self._namespaces[k] == uri:
                self._uri_to_prefix[uri] = k
                break

    def __iter__(self) -> Iterator[str]:
        return iter(self._namespaces)

    def __len__(self) -> int:
        return len(self._namespaces)

    @property
    def namespaces(self) -> NamespacesType:
        return self._namespaces

    @property
    def process_namespaces(self) -> bool:
        return self._process_namespaces

    @property
    def strip_namespaces(self) -> bool:
        return self._strip_namespaces

    @property
    def default_namespace(self) -> Optional[str]:
        return self._namespaces.get('')

    def __copy__(self) -> 'NamespaceMapper':
        mapper: 'NamespaceMapper' = object.__new__(self.__class__)

        for cls in self.__class__.__mro__:
            if hasattr(cls, '__slots__'):
                for attr in cls.__slots__:
                    setattr(mapper, attr, copy.copy(getattr(self, attr)))

        return mapper

    def clear(self) -> None:
        self._namespaces.clear()
        self._contexts.clear()
        self._uri_to_prefix.clear()

    def get_xmlns_from_data(self, obj: Any) -> Optional[List[Tuple[str, str]]]:
        """Returns the XML declarations from decoded element data."""
        return None

    def set_context(self, obj: Any, level: int) -> Optional[List[Tuple[str, str]]]:
        if not self._use_xmlns:
            return None
        elif self._contexts:
            # Clear previous states
            namespaces = uri_to_prefix = None
            while self._contexts:
                context = self._contexts[-1]
                if level > context.level:
                    break
                elif level == context.level and context.obj is obj:
                    return cast(List[Tuple[str, str]], context.xmlns)
                namespaces, uri_to_prefix = self._contexts.pop()[-2:]

            if namespaces is not None and uri_to_prefix is not None:
                self._namespaces.clear()
                self._namespaces.update(namespaces)
                self._uri_to_prefix.clear()
                self._uri_to_prefix.update(uri_to_prefix)

        if is_etree_element(obj):
            xmlns = self.get_xmlns_from_elem(obj)
        else:
            xmlns = self.get_xmlns_from_data(obj)

        if xmlns:
            context = NamespaceMapperContext(
                obj,
                level,
                xmlns,
                {k: v for k, v in self._namespaces.items()},
                {k: v for k, v in self._uri_to_prefix.items()},
            )
            self._contexts.append(context)
            self._namespaces.update(xmlns)
            self._uri_to_prefix.update((v, k) for k, v in xmlns)

        return xmlns

    def pop_namespaces(self, level: int) -> None:
        while self._contexts:
            if level > self._contexts[-1][1]:
                break
            namespaces, uri_to_prefix = self._contexts.pop()[-2:]
            self._namespaces.clear()
            self._namespaces.update(namespaces)
            self._uri_to_prefix.clear()
            self._uri_to_prefix.update(uri_to_prefix)

    def push_namespaces(self, level: int, xmlns: List[Tuple[str, str]]) -> None:
        while self._contexts:
            if level > self._contexts[-1][1]:
                break
            namespaces, uri_to_prefix = self._contexts.pop()[-2:]
            self._namespaces.clear()
            self._namespaces.update(namespaces)
            self._uri_to_prefix.clear()
            self._uri_to_prefix.update(uri_to_prefix)

        self._contexts.append(NamespaceMapperContext(
            None,
            level,
            xmlns[:],
            {k: v for k, v in self._namespaces.items()},
            {k: v for k, v in self._uri_to_prefix.items()},
        ))
        self._namespaces.update(xmlns)
        self._uri_to_prefix.update((v, k) for k, v in xmlns)

    def map_qname(self, qname: str) -> str:
        """
        Converts an extended QName to the prefixed format. Only registered
        namespaces are mapped.

        :param qname: a QName in extended format or a local name.
        :return: a QName in prefixed format or a local name.
        """
        if not self._use_namespaces:
            return local_name(qname) if self._strip_namespaces else qname

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

        try:
            prefix = self._uri_to_prefix[namespace]
        except KeyError:
            return qname
        else:
            return f'{prefix}:{local_part}' if prefix else local_part

    def unmap_qname(self, qname: str,
                    name_table: Optional[Container[Optional[str]]] = None,
                    xmlns: Optional[List[Tuple[str, str]]] = None) -> str:
        """
        Converts a QName in prefixed format or a local name to the extended QName format.
        Local names are converted only if a default namespace is included in the instance.
        If a *name_table* is provided a local name is mapped to the default namespace
        only if not found in the name table.

        :param qname: a QName in prefixed format or a local name
        :param name_table: an optional lookup table for checking local names.
        :param xmlns: an optional list of namespace declarations that integrate \
        or override the namespace map.
        :return: a QName in extended format or a local name.
        """
        if not self._use_namespaces:
            return local_name(qname) if self._strip_namespaces else qname

        if xmlns:
            namespaces: MutableMapping[str, str] = {**self._namespaces}
            namespaces.update(xmlns)
        else:
            namespaces = self._namespaces

        try:
            if qname[0] == '{' or not namespaces:
                return qname
            elif ':' in qname:
                prefix, name = qname.split(':')
            else:
                default_namespace = namespaces.get('')
                if not default_namespace:
                    return qname
                elif name_table is None or qname not in name_table:
                    return f'{{{default_namespace}}}{qname}'
                else:
                    return qname

        except IndexError:
            return qname
        except ValueError:
            raise XMLSchemaValueError("the argument 'qname' has an invalid value %r" % qname)
        except (TypeError, AttributeError):
            raise XMLSchemaTypeError("the argument 'qname' must be a string-like object")
        else:
            try:
                uri = namespaces[prefix]
            except KeyError:
                return qname
            else:
                return f'{{{uri}}}{name}' if uri else name


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
