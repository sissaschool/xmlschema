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
import copy
from typing import Any, Callable, Container, Dict, Iterator, List, \
    Optional, MutableMapping, Mapping, NamedTuple, Union, Tuple, TypeVar

from .exceptions import XMLSchemaValueError, XMLSchemaTypeError
from .helpers import local_name, get_namespace_map
from .aliases import NamespacesType, XmlnsType, ElementType
from .resources import XMLResource


class NamespaceMapperContext(NamedTuple):
    obj: Union[ElementType, Any]
    level: int
    xmlns: XmlnsType
    namespaces: NamespacesType
    reverse: NamespacesType


XMLNS_PROCESSING_MODES = frozenset(('stacked', 'collapsed', 'root-only', 'none'))


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
    For default the xmlns processing mode is 'stacked', the mode that processes the \
    namespace declarations using a stack of contexts related with elements and levels. \
    This is the processing mode that always matches the XML namespace declarations \
    defined in the XML document. Provide 'collapsed' for loading all namespace \
    declarations of the XML source before decoding. Provide 'root-only' to use \
    only the namespace declarations of the XML document root. Provide 'none' to \
    not use any namespace declaration of the XML document.
    :param source: the origin of XML data. Con be an `XMLResource` instance or `None`.
    """
    __slots__ = '_namespaces', '_reverse', '_contexts', \
        'process_namespaces', 'strip_namespaces', '_use_namespaces', \
        'xmlns_processing', 'source', '_xmlns_getter', '__dict__'

    _namespaces: NamespacesType
    _contexts: List[NamespaceMapperContext]
    _xmlns_getter: Optional[Callable[[ElementType], XmlnsType]]

    def __init__(self, namespaces: Optional[NamespacesType] = None,
                 process_namespaces: bool = True,
                 strip_namespaces: bool = False,
                 xmlns_processing: str = 'stacked',
                 source: Optional[XMLResource] = None) -> None:

        if not isinstance(xmlns_processing, str):
            raise XMLSchemaTypeError("invalid type for argument 'xmlns_processing'")
        elif xmlns_processing not in XMLNS_PROCESSING_MODES:
            raise XMLSchemaValueError("invalid value for argument 'xmlns_processing'")

        self.process_namespaces = process_namespaces
        self.strip_namespaces = strip_namespaces
        self._use_namespaces = bool(process_namespaces and not strip_namespaces)
        self.xmlns_processing = xmlns_processing
        self.source = source

        if isinstance(source, XMLResource) and xmlns_processing != 'none':
            self._xmlns_getter = source.get_xmlns
            self._namespaces = source.get_namespaces(namespaces)
        else:
            self._xmlns_getter = None
            self._namespaces = get_namespace_map(namespaces)

        self._reverse = {v: k for k, v in reversed(self._namespaces.items())}
        self._contexts = []

    def __getitem__(self, prefix: str) -> str:
        return self._namespaces[prefix]

    def __setitem__(self, prefix: str, uri: str) -> None:
        self._namespaces[prefix] = uri
        self._reverse[uri] = prefix

    def __delitem__(self, prefix: str) -> None:
        uri = self._namespaces.pop(prefix)
        del self._reverse[uri]

        for k in reversed(self._namespaces.keys()):
            if self._namespaces[k] == uri:
                self._reverse[uri] = k
                break

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

    def __copy__(self) -> 'NamespaceMapper':
        mapper: 'NamespaceMapper' = object.__new__(self.__class__)

        for cls in self.__class__.__mro__:
            if hasattr(cls, '__slots__'):
                for attr in cls.__slots__:
                    setattr(mapper, attr, copy.copy(getattr(self, attr)))

        return mapper

    def clear(self) -> None:
        self._namespaces.clear()
        self._reverse.clear()
        self._contexts.clear()

    def get_xmlns_from_data(self, obj: Any) -> XmlnsType:
        """Returns the XML declarations from decoded element data."""
        return None

    def set_context(self, obj: Any, level: int) -> XmlnsType:
        if self._contexts:
            # Remove contexts of sibling or descendant elements
            xmlns = namespaces = reverse = None

            while self._contexts:
                context = self._contexts[-1]
                if level > context.level:
                    break
                elif level == context.level and context.obj is obj:
                    # The context for (obj, level) already exists
                    xmlns = context.xmlns
                    break

                namespaces, reverse = self._contexts.pop()[-2:]

            if namespaces is not None and reverse is not None:
                self._namespaces.clear()
                self._namespaces.update(namespaces)
                self._reverse.clear()
                self._reverse.update(reverse)

            if xmlns:
                return xmlns

        if self._xmlns_getter:
            xmlns = self._xmlns_getter(obj)
        elif self.xmlns_processing == 'none':
            xmlns = None
        else:
            xmlns = self.get_xmlns_from_data(obj)

        if xmlns:
            if self.xmlns_processing == 'stacked':
                context = NamespaceMapperContext(
                    obj,
                    level,
                    xmlns,
                    {k: v for k, v in self._namespaces.items()},
                    {k: v for k, v in self._reverse.items()},
                )
                self._contexts.append(context)
                self._namespaces.update(xmlns)
                if level:
                    self._reverse.update((v, k) for k, v in xmlns)
                else:
                    self._reverse.update((v, k) for k, v in reversed(xmlns)
                                         if v not in self._reverse)
                return xmlns

            elif not level or self.xmlns_processing == 'collapsed':
                for prefix, uri in xmlns:
                    if not prefix:
                        if not uri:
                            continue
                        elif '' not in self._namespaces:
                            if not level:
                                self._namespaces[''] = uri
                                if uri not in self._reverse:
                                    self._reverse[uri] = ''
                                continue
                        elif self._namespaces[''] == uri:
                            continue
                        prefix = 'default'

                    while prefix in self._namespaces:
                        if self._namespaces[prefix] == uri:
                            break
                        match = re.search(r'(\d+)$', prefix)
                        if match:
                            index = int(match.group()) + 1
                            prefix = prefix[:match.span()[0]] + str(index)
                        else:
                            prefix += '0'
                    else:
                        self._namespaces[prefix] = uri
                        if uri not in self._reverse:
                            self._reverse[uri] = prefix
        return None

    def map_qname(self, qname: str) -> str:
        """
        Converts an extended QName to the prefixed format. Only registered
        namespaces are mapped.

        :param qname: a QName in extended format or a local name.
        :return: a QName in prefixed format or a local name.
        """
        if not self._use_namespaces:
            return local_name(qname) if self.strip_namespaces else qname

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
            prefix = self._reverse[namespace]
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
            return local_name(qname) if self.strip_namespaces else qname

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
