#
# Copyright (c), 2016-2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
"""
This module contains the base definitions for xmlschema's converters.
"""
import re
from collections.abc import Callable, Container, Iterator, Mapping, MutableMapping
from typing import Any, NamedTuple, Optional, Union, TypeVar, TYPE_CHECKING

from xmlschema.aliases import NsmapType, ElementType, XmlnsType
from xmlschema.exceptions import XMLSchemaTypeError, XMLSchemaValueError
from xmlschema.utils.decoding import iter_decoded_data
from xmlschema.utils.qnames import get_namespace_map, update_namespaces, local_name
from xmlschema.resources import XMLResource

if TYPE_CHECKING:
    from xmlschema.validators import XsdComponent, XsdElement  # noqa: F401

XMLNS_PROCESSING_MODES = frozenset(('stacked', 'collapsed', 'root-only', 'none'))


class NamespaceMapperContext(NamedTuple):
    obj: Union[ElementType, Any]
    level: int
    xmlns: XmlnsType
    namespaces: NsmapType
    reverse: NsmapType


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
    The preferred mode is 'stacked', the mode that processes the namespace declarations \
    using a stack of contexts related with elements and levels. \
    This is the processing mode that always matches the XML namespace declarations \
    defined in the XML document. Provide 'collapsed' for loading all namespace \
    declarations of the XML source in a single map, renaming colliding prefixes. \
    Provide 'root-only' to use only the namespace declarations of the XML document root. \
    Provide 'none' to not use any namespace declaration of the XML document. \
    For default the xmlns processing mode is 'stacked' if the XML source is an \
    `XMLResource` instance, otherwise is 'none'.
    :param source: the origin of XML data. Con be an `XMLResource` instance, an XML \
    decoded data or `None`.
    """
    __slots__ = ('_namespaces', '_reverse', '_contexts', 'process_namespaces',
                 'strip_namespaces', '_use_namespaces', 'xmlns_processing',
                 '_xmlns_getter', 'source')

    _namespaces: NsmapType
    _contexts: list[NamespaceMapperContext]
    _xmlns_getter: Optional[Callable[[ElementType], XmlnsType]]

    def __init__(self, namespaces: Optional[NsmapType] = None,
                 process_namespaces: bool = True,
                 strip_namespaces: bool = False,
                 xmlns_processing: Optional[str] = None,
                 source: Optional[Any] = None) -> None:

        self.process_namespaces = process_namespaces
        self.strip_namespaces = strip_namespaces
        self._use_namespaces = bool(process_namespaces and not strip_namespaces)
        self.source = source

        if xmlns_processing is None:
            xmlns_processing = self.xmlns_processing_default
        elif not isinstance(xmlns_processing, str):
            raise XMLSchemaTypeError("invalid type for argument 'xmlns_processing'")

        if xmlns_processing not in XMLNS_PROCESSING_MODES:
            raise XMLSchemaValueError("invalid value for argument 'xmlns_processing'")
        self.xmlns_processing = xmlns_processing

        if xmlns_processing == 'none':
            self._xmlns_getter = None
        elif isinstance(source, XMLResource):
            self._xmlns_getter = source.get_xmlns
        else:
            self._xmlns_getter = self.get_xmlns_from_data

        self._namespaces = self.get_namespaces(namespaces)
        self._reverse = {
            v: k for k, v in reversed(self._namespaces.items())  # type: ignore[call-overload]
        }
        self._contexts = []

    def __getitem__(self, prefix: str) -> str:
        return self._namespaces[prefix]

    def __setitem__(self, prefix: str, uri: str) -> None:
        self._namespaces[prefix] = uri
        self._reverse[uri] = prefix

    def __delitem__(self, prefix: str) -> None:
        uri = self._namespaces.pop(prefix)
        del self._reverse[uri]

        for k in reversed(self._namespaces.keys()):   # type: ignore[call-overload]
            if self._namespaces[k] == uri:
                self._reverse[uri] = k
                break

    def __iter__(self) -> Iterator[str]:
        return iter(self._namespaces)

    def __len__(self) -> int:
        return len(self._namespaces)

    @property
    def namespaces(self) -> NsmapType:
        return self._namespaces

    @property
    def default_namespace(self) -> Optional[str]:
        return self._namespaces.get('')

    @property
    def xmlns_processing_default(self) -> str:
        return 'stacked' if isinstance(self.source, XMLResource) else 'none'

    def __copy__(self) -> 'NamespaceMapper':
        mapper: 'NamespaceMapper' = object.__new__(self.__class__)

        for cls in self.__class__.__mro__:
            if hasattr(cls, '__slots__'):
                for attr in cls.__slots__:
                    value = getattr(self, attr)
                    if isinstance(value, (dict, list)):
                        setattr(mapper, attr, value.copy())
                    else:
                        setattr(mapper, attr, value)

        return mapper

    def clear(self) -> None:
        self._namespaces.clear()
        self._reverse.clear()
        self._contexts.clear()

    def get_xmlns_from_data(self, obj: Any) -> XmlnsType:
        """Returns the XML declarations from decoded element data."""
        return None

    def get_namespaces(self, namespaces: Optional[NsmapType] = None,
                       root_only: bool = True) -> NsmapType:
        """
        Extracts namespaces with related prefixes from the XML source. It the XML
        source is an `XMLResource` instance delegates the extraction to it.
        With XML decoded data iterates the source try to extract xmlns information
        using the implementation of *get_xmlns_from_data()*. If xmlns processing
        mode is 'none', no namespace declaration is retrieved from the XML source.
        Arguments and return type are identical to the ones defined for the method
        *get_namespaces()* of `XMLResource` class.
        """
        if self._xmlns_getter is None:
            return get_namespace_map(namespaces)
        elif isinstance(self.source, XMLResource):
            return self.source.get_namespaces(namespaces, root_only)

        xmlns: XmlnsType
        namespaces = get_namespace_map(namespaces)
        for obj, level in iter_decoded_data(self.source):
            if root_only and level > 1:  # root xmlns declarations are usually at level 0 or 1
                break
            xmlns = self.get_xmlns_from_data(obj)
            if xmlns:
                update_namespaces(namespaces, xmlns, not level)

        return namespaces

    def set_context(self, obj: Any, level: int) -> XmlnsType:
        """
        set the right context for the XML data and its level, updating the namespace
        map if necessary. Returns the xmlns declarations of the provided XML data.
        """
        xmlns = None

        if self._contexts:
            # Remove contexts of sibling or descendant elements
            namespaces = reverse = None

            while self._contexts:  # pragma: no cover
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

        if xmlns or not self._xmlns_getter:
            return xmlns

        xmlns = self._xmlns_getter(obj)
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
                    xmlns: Optional[list[tuple[str, str]]] = None) -> str:
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
        namespaces: MutableMapping[str, str]

        if not self._use_namespaces:
            return local_name(qname) if self.strip_namespaces else qname

        if xmlns:
            namespaces = {k: v for k, v in self._namespaces.items()}
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


T = TypeVar('T', bound=object)


class NamespaceResourcesMap(MutableMapping[str, list[T]]):
    """
    Dictionary for storing information about namespace resources. Values are
    lists of objects. Setting an existing value appends the object to the value.
    Setting a value with a list sets/replaces the value.
    """
    __slots__ = ('_store',)

    def __init__(self, *args: Any, **kwargs: Any):
        self._store: dict[str, list[T]] = {}
        for item in args:
            self.update(item)
        self.update(kwargs)

    def __getitem__(self, uri: str) -> list[T]:
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

    def copy(self) -> 'NamespaceResourcesMap[T]':
        obj: NamespaceResourcesMap[T] = object.__new__(self.__class__)
        obj._store = {k: v.copy() for k, v in self.items()}
        return obj

    __copy__ = copy


CT = TypeVar('CT', bound=Union['XsdComponent', set['XsdElement']])


class NamespaceView(Mapping[str, CT]):
    """
    A mapping for filtered access to a dictionary that stores objects by FQDN.
    """
    __slots__ = '_target_dict', '_namespace', '_prefix', '_prefix_len'

    def __init__(self, target_dict: Mapping[str, CT], namespace: str):
        self._target_dict = target_dict
        self._namespace = namespace
        self._prefix = f'{{{namespace}}}' if namespace else ''
        self._prefix_len = len(self._prefix)

    def __getitem__(self, key: str) -> CT:
        try:
            return self._target_dict[self._prefix + key]
        except KeyError:
            raise KeyError(key) from None

    def __len__(self) -> int:
        if not self._namespace:
            return sum(1 for k in self._target_dict if k[:1] != '{')
        return sum(1 for k in self._target_dict if self._prefix == k[:self._prefix_len])

    def __iter__(self) -> Iterator[str]:
        if not self._namespace:
            for k in self._target_dict:
                if k[:1] != '{':
                    yield k
        else:
            for k in self._target_dict:
                if self._prefix == k[:self._prefix_len]:
                    yield k[self._prefix_len:]

    def __repr__(self) -> str:
        return '%s(%s)' % (self.__class__.__name__, str(self.as_dict()))

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and (self._prefix + key) in self._target_dict

    def __eq__(self, other: Any) -> Any:
        return self.as_dict() == other

    def as_dict(self) -> dict[str, CT]:
        if not self._namespace:
            return {k: v for k, v in self._target_dict.items() if k[:1] != '{'}
        else:
            return {
                k[self._prefix_len:]: v for k, v in self._target_dict.items()
                if self._prefix == k[:self._prefix_len]
            }
