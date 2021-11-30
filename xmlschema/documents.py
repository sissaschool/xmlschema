#
# Copyright (c), 2016-2020, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import json
from io import IOBase, TextIOBase
from typing import Any, Dict, List, Optional, Type, Union, Tuple, \
    IO, BinaryIO, TextIO, Iterator

from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLResourceError
from .names import XSD_NAMESPACE, XSI_TYPE
from .etree import ElementTree, etree_tostring
from .aliases import ElementType, XMLSourceType, NamespacesType, LocationsType, \
    LazyType, SchemaSourceType, ConverterType, DecodeType, EncodeType, \
    JsonDecodeType
from .helpers import is_etree_document
from .resources import fetch_schema_locations, XMLResource
from .validators import XMLSchema10, XMLSchemaBase, XMLSchemaValidationError


def get_context(xml_document: Union[XMLSourceType, XMLResource],
                schema: Optional[Union[XMLSchemaBase, SchemaSourceType]] = None,
                cls: Optional[Type[XMLSchemaBase]] = None,
                locations: Optional[LocationsType] = None,
                base_url: Optional[str] = None,
                defuse: str = 'remote',
                timeout: int = 300,
                lazy: LazyType = False,
                dummy_schema: bool = False) -> Tuple[XMLResource, XMLSchemaBase]:
    """
    Get the XML document validation/decode context.

    :return: an XMLResource instance and a schema instance.
    """
    resource: XMLResource
    kwargs: Dict[Any, Any]

    if cls is None:
        cls = XMLSchema10
    elif not issubclass(cls, XMLSchemaBase):
        raise XMLSchemaTypeError(f"invalid schema class {cls}")

    if isinstance(xml_document, XMLResource):
        resource = xml_document
    else:
        resource = XMLResource(xml_document, base_url, defuse=defuse,
                               timeout=timeout, lazy=lazy)

    if isinstance(schema, XMLSchemaBase) and resource.namespace in schema.maps.namespaces:
        return resource, schema
    if isinstance(resource, XmlDocument) and isinstance(resource.schema, XMLSchemaBase):
        return resource, resource.schema

    try:
        schema_location, locations = fetch_schema_locations(resource, locations, base_url=base_url)
    except ValueError:
        if schema is None:
            if XSI_TYPE in resource.root.attrib and cls.meta_schema is not None:
                return resource, cls.meta_schema
            elif dummy_schema:
                return resource, get_dummy_schema(resource, cls)
            else:
                msg = "no schema can be retrieved for the provided XML data"
                raise XMLSchemaValueError(msg) from None

        elif isinstance(schema, XMLSchemaBase):
            return resource, schema
        else:
            return resource, cls(schema, locations=locations, base_url=base_url,
                                 defuse=defuse, timeout=timeout)
    else:
        kwargs = dict(locations=locations, defuse=defuse, timeout=timeout)
        if schema is None or isinstance(schema, XMLSchemaBase):
            return resource, cls(schema_location, **kwargs)
        else:
            return resource, cls(schema, **kwargs)


def get_dummy_schema(resource: XMLResource, cls: Type[XMLSchemaBase]) -> XMLSchemaBase:
    tag = resource.root.tag
    if tag.startswith('{'):
        namespace, name = tag[1:].split('}')
    else:
        namespace, name = '', tag

    if namespace:
        return cls(
            '<xs:schema xmlns:xs="{0}" targetNamespace="{1}">\n'
            '    <xs:element name="{2}"/>\n'
            '</xs:schema>'.format(XSD_NAMESPACE, namespace, name)
        )
    else:
        return cls(
            '<xs:schema xmlns:xs="{0}">\n'
            '    <xs:element name="{1}"/>\n'
            '</xs:schema>'.format(XSD_NAMESPACE, name)
        )


def get_lazy_json_encoder(errors: List[XMLSchemaValidationError]) -> Type[json.JSONEncoder]:

    class JSONLazyEncoder(json.JSONEncoder):
        def default(self, obj: Any) -> Any:
            if isinstance(obj, Iterator):
                while True:
                    result = next(obj, None)
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        return result
            return json.JSONEncoder.default(self, obj)

    return JSONLazyEncoder


def validate(xml_document: Union[XMLSourceType, XMLResource],
             schema: Optional[XMLSchemaBase] = None,
             cls: Optional[Type[XMLSchemaBase]] = None,
             path: Optional[str] = None,
             schema_path: Optional[str] = None,
             use_defaults: bool = True,
             namespaces: Optional[NamespacesType] = None,
             locations: Optional[LocationsType] = None,
             base_url: Optional[str] = None,
             defuse: str = 'remote',
             timeout: int = 300,
             lazy: LazyType = False) -> None:
    """
    Validates an XML document against a schema instance. This function builds an
    :class:`XMLSchema` object for validating the XML document. Raises an
    :exc:`XMLSchemaValidationError` if the XML document is not validated against
    the schema.

    :param xml_document: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or an URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param schema: can be a schema instance or a file-like object or a file path or a URL \
    of a resource or a string containing the schema.
    :param cls: class to use for building the schema instance (for default \
    :class:`XMLSchema10` is used).
    :param path: is an optional XPath expression that matches the elements of the XML \
    data that have to be decoded. If not provided the XML root element is used.
    :param schema_path: an XPath expression to select the XSD element to use for decoding. \
    If not provided the *path* argument or the *source* root tag are used.
    :param use_defaults: defines when to use element and attribute defaults for filling \
    missing required values.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :param locations: additional schema location hints, used if a schema instance \
    has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    :param defuse: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param timeout: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param lazy: optional argument for construct the :class:`XMLResource` instance.
    """
    source, _schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    _schema.validate(source, path, schema_path, use_defaults, namespaces)


def is_valid(xml_document: Union[XMLSourceType, XMLResource],
             schema: Optional[XMLSchemaBase] = None,
             cls: Optional[Type[XMLSchemaBase]] = None,
             path: Optional[str] = None,
             schema_path: Optional[str] = None,
             use_defaults: bool = True,
             namespaces: Optional[NamespacesType] = None,
             locations: Optional[LocationsType] = None,
             base_url: Optional[str] = None,
             defuse: str = 'remote',
             timeout: int = 300,
             lazy: LazyType = False) -> bool:
    """
    Like :meth:`validate` except that do not raises an exception but returns ``True`` if
    the XML document is valid, ``False`` if it's invalid.
    """
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return schema.is_valid(source, path, schema_path, use_defaults, namespaces)


def iter_errors(xml_document: Union[XMLSourceType, XMLResource],
                schema: Optional[XMLSchemaBase] = None,
                cls: Optional[Type[XMLSchemaBase]] = None,
                path: Optional[str] = None,
                schema_path: Optional[str] = None,
                use_defaults: bool = True,
                namespaces: Optional[NamespacesType] = None,
                locations: Optional[LocationsType] = None,
                base_url: Optional[str] = None,
                defuse: str = 'remote',
                timeout: int = 300,
                lazy: LazyType = False) -> Iterator[XMLSchemaValidationError]:
    """
    Creates an iterator for the errors generated by the validation of an XML document.
    Takes the same arguments of the function :meth:`validate`.
    """
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return schema.iter_errors(source, path, schema_path, use_defaults, namespaces)


def iter_decode(xml_document: Union[XMLSourceType, XMLResource],
                schema: Optional[XMLSchemaBase] = None,
                cls: Optional[Type[XMLSchemaBase]] = None,
                path: Optional[str] = None,
                validation: str = 'strict',
                process_namespaces: bool = True,
                locations: Optional[LocationsType] = None,
                base_url: Optional[str] = None,
                defuse: str = 'remote',
                timeout: int = 300,
                lazy: LazyType = False,
                **kwargs: Any) -> Iterator[Union[Any, XMLSchemaValidationError]]:
    """
    Creates an iterator for decoding an XML source to a data structure. For default
    the document is validated during the decoding phase and if it's invalid then one
    or more :exc:`XMLSchemaValidationError` instances are yielded before the decoded data.

    :param xml_document: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or an URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param schema: can be a schema instance or a file-like object or a file path or a URL \
    of a resource or a string containing the schema.
    :param cls: class to use for building the schema instance (for default uses \
    :class:`XMLSchema10`).
    :param path: is an optional XPath expression that matches the elements of the XML \
    data that have to be decoded. If not provided the XML root element is used.
    :param validation: defines the XSD validation mode to use for decode, can be \
    'strict', 'lax' or 'skip'.
    :param process_namespaces: indicates whether to use namespace information in \
    the decoding process.
    :param locations: additional schema location hints, in case a schema instance \
    has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    :param defuse: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param timeout: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param lazy: optional argument for construct the :class:`XMLResource` instance.
    :param kwargs: other optional arguments of :meth:`XMLSchema.iter_decode` \
    as keyword arguments.
    :raises: :exc:`XMLSchemaValidationError` if the XML document is invalid and \
    ``validation='strict'`` is provided.
    """
    source, _schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    yield from _schema.iter_decode(source, path=path, validation=validation,
                                   process_namespaces=process_namespaces, **kwargs)


def to_dict(xml_document: Union[XMLSourceType, XMLResource],
            schema: Optional[XMLSchemaBase] = None,
            cls: Optional[Type[XMLSchemaBase]] = None,
            path: Optional[str] = None,
            validation: str = 'strict',
            process_namespaces: bool = True,
            locations: Optional[LocationsType] = None,
            base_url: Optional[str] = None,
            defuse: str = 'remote',
            timeout: int = 300,
            lazy: LazyType = False, **kwargs: Any) -> DecodeType[Any]:
    """
    Decodes an XML document to a Python's nested dictionary. Takes the same arguments
    of the function :meth:`iter_decode`, but *validation* mode defaults to 'strict'.

    :return: an object containing the decoded data. If ``validation='lax'`` is provided \
    validation errors are collected and returned in a tuple with the decoded data.
    :raises: :exc:`XMLSchemaValidationError` if the XML document is invalid and \
    ``validation='strict'`` is provided.
    """
    source, _schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return _schema.decode(source, path=path, validation=validation,
                          process_namespaces=process_namespaces, **kwargs)


def to_json(xml_document: Union[XMLSourceType, XMLResource],
            fp: Optional[IO[str]] = None,
            schema: Optional[XMLSchemaBase] = None,
            cls: Optional[Type[XMLSchemaBase]] = None,
            path: Optional[str] = None,
            converter: Optional[ConverterType] = None,
            process_namespaces: bool = True,
            locations: Optional[LocationsType] = None,
            base_url: Optional[str] = None,
            defuse: str = 'remote',
            timeout: int = 300,
            lazy: LazyType = False,
            json_options: Optional[Dict[str, Any]] = None,
            **kwargs: Any) -> JsonDecodeType:
    """
    Serialize an XML document to JSON. For default the XML data is validated during
    the decoding phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

    :param xml_document: can be an :class:`XMLResource` instance, a file-like object a path \
    to a file or an URI of a resource or an Element instance or an ElementTree instance or \
    a string containing the XML data. If the passed argument is not an :class:`XMLResource` \
    instance a new one is built using this and *defuse*, *timeout* and *lazy* arguments.
    :param fp: can be a :meth:`write()` supporting file-like object.
    :param schema: can be a schema instance or a file-like object or a file path or an URL \
    of a resource or a string containing the schema.
    :param cls: schema class to use for building the instance (for default uses \
    :class:`XMLSchema10`).
    :param path: is an optional XPath expression that matches the elements of the XML \
    data that have to be decoded. If not provided the XML root element is used.
    :param converter: an :class:`XMLSchemaConverter` subclass or instance to use \
    for the decoding.
    :param process_namespaces: indicates whether to use namespace information in \
    the decoding process.
    :param locations: additional schema location hints, in case the schema instance \
    has to be built.
    :param base_url: is an optional custom base URL for remapping relative locations, for \
    default uses the directory where the XSD or alternatively the XML document is located.
    :param defuse: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param timeout: optional argument to pass for construct schema and \
    :class:`XMLResource` instances.
    :param lazy: optional argument for construct the :class:`XMLResource` instance.
    :param json_options: a dictionary with options for the JSON serializer.
    :param kwargs: optional arguments of :meth:`XMLSchema.iter_decode` as keyword arguments \
    to variate the decoding process.
    :return: a string containing the JSON data if *fp* is `None`, otherwise doesn't \
    return anything. If ``validation='lax'`` keyword argument is provided the validation \
    errors are collected and returned, eventually coupled in a tuple with the JSON data.
    :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
    the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
    """
    source, _schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    if json_options is None:
        json_options = {}
    if 'decimal_type' not in kwargs:
        kwargs['decimal_type'] = float
    kwargs['converter'] = converter
    kwargs['process_namespaces'] = process_namespaces

    errors: List[XMLSchemaValidationError] = []

    if path is None and source.is_lazy() and 'cls' not in json_options:
        json_options['cls'] = get_lazy_json_encoder(errors)

    obj = _schema.decode(source, path=path, **kwargs)
    if isinstance(obj, tuple):
        errors.extend(obj[1])
        if fp is not None:
            json.dump(obj[0], fp, **json_options)
            return tuple(errors)
        else:
            result = json.dumps(obj[0], **json_options)
            return result, tuple(errors)
    elif fp is not None:
        json.dump(obj, fp, **json_options)
        return None if not errors else tuple(errors)
    else:
        result = json.dumps(obj, **json_options)
        return result if not errors else (result, tuple(errors))


def from_json(source: Union[str, bytes, IO[str]],
              schema: XMLSchemaBase,
              path: Optional[str] = None,
              converter: Optional[ConverterType] = None,
              json_options: Optional[Dict[str, Any]] = None,
              **kwargs: Any) -> EncodeType[ElementType]:
    """
    Deserialize JSON data to an XML Element.

    :param source: can be a string or a :meth:`read()` supporting file-like object \
    containing the JSON document.
    :param schema: an :class:`XMLSchema10` or an :class:`XMLSchema11` instance.
    :param path: is an optional XPath expression for selecting the element of the schema \
    that matches the data that has to be encoded. For default the first global element of \
    the schema is used.
    :param converter: an :class:`XMLSchemaConverter` subclass or instance to use \
    for the encoding.
    :param json_options: a dictionary with options for the JSON deserializer.
    :param kwargs: other optional arguments of :meth:`XMLSchema.iter_encode` and \
    options for converter.
    :return: An element tree's Element instance. If ``validation='lax'`` keyword argument is \
    provided the validation errors are collected and returned coupled in a tuple with the \
    Element instance.
    :raises: :exc:`XMLSchemaValidationError` if the object is not encodable by the schema, \
    or also if it's invalid when ``validation='strict'`` is provided.
    """
    if not isinstance(schema, XMLSchemaBase):
        raise XMLSchemaTypeError("invalid type %r for argument 'schema'" % type(schema))
    elif json_options is None:
        json_options = {}

    if isinstance(source, (str, bytes)):
        obj = json.loads(source, **json_options)
    else:
        obj = json.load(source, **json_options)

    return schema.encode(obj, path=path, converter=converter, **kwargs)


class XmlDocument(XMLResource):
    """
    An XML document bound with its schema. If no schema is get from the provided
    context and validation argument is 'skip' the XML document is associated with
    a generic schema, otherwise a ValueError is raised.

    :param source: a string containing XML data or a file path or an URL or a \
    file like object or an ElementTree or an Element.
    :param schema: can be a :class:`xmlschema.XMLSchema` instance or a file-like \
    object or a file path or an URL of a resource or a string containing the XSD schema.
    :param cls: class to use for building the schema instance (for default \
    :class:`XMLSchema10` is used).
    :param validation: the XSD validation mode to use for validating the XML document, \
    that can be 'strict' (default), 'lax' or 'skip'.
    :param namespaces: is an optional mapping from namespace prefix to URI.
    :param locations: resource location hints, that can be a dictionary or a \
    sequence of couples (namespace URI, resource URL).
    :param base_url: the base URL for base :class:`xmlschema.XMLResource` initialization.
    :param allow: the security mode for base :class:`xmlschema.XMLResource` initialization.
    :param defuse: the defuse mode for base :class:`xmlschema.XMLResource` initialization.
    :param timeout: the timeout for base :class:`xmlschema.XMLResource` initialization.
    :param lazy: the lazy mode for base :class:`xmlschema.XMLResource` initialization.
    """
    schema: Optional[XMLSchemaBase] = None
    _fallback_schema: Optional[XMLSchemaBase] = None
    validation: str = 'skip'
    namespaces: Optional[NamespacesType] = None
    errors: Union[Tuple[()], List[XMLSchemaValidationError]] = ()

    def __init__(self, source: XMLSourceType,
                 schema: Optional[Union[XMLSchemaBase, SchemaSourceType]] = None,
                 cls: Optional[Type[XMLSchemaBase]] = None,
                 validation: str = 'strict',
                 namespaces: Optional[NamespacesType] = None,
                 locations: Optional[LocationsType] = None,
                 base_url: Optional[str] = None,
                 allow: str = 'all',
                 defuse: str = 'remote',
                 timeout: int = 300,
                 lazy: LazyType = False) -> None:

        if cls is None:
            cls = XMLSchema10
        self.validation = validation
        self._namespaces = namespaces
        super(XmlDocument, self).__init__(source, base_url, allow, defuse, timeout, lazy)

        if isinstance(schema, XMLSchemaBase) and self.namespace in schema.maps.namespaces:
            self.schema = schema
        elif schema is not None and not isinstance(schema, XMLSchemaBase):
            self.schema = cls(
                source=schema,
                base_url=base_url,
                allow=allow,
                defuse=defuse,
                timeout=timeout,
            )
        else:
            try:
                schema_location, locations = fetch_schema_locations(self, locations, base_url)
            except ValueError:
                if XSI_TYPE in self._root.attrib:
                    self.schema = cls.meta_schema
                elif validation != 'skip':
                    msg = "no schema can be retrieved for the XML resource"
                    raise XMLSchemaValueError(msg) from None
                else:
                    self._fallback_schema = get_dummy_schema(self, cls)
            else:
                self.schema = cls(
                    source=schema_location,
                    validation='strict',
                    locations=locations,
                    defuse=defuse,
                    allow=allow,
                    timeout=timeout,
                )

        if self.schema is None:
            pass
        elif validation == 'strict':
            self.schema.validate(self, namespaces=self.namespaces)
        elif validation == 'lax':
            self.errors = [e for e in self.schema.iter_errors(self, namespaces=self.namespaces)]
        elif validation != 'skip':
            raise XMLSchemaValueError("{!r}: not a validation mode".format(validation))

    def parse(self, source: XMLSourceType, lazy: LazyType = False) -> None:
        super(XmlDocument, self).parse(source, lazy)
        self.namespaces = self.get_namespaces(self._namespaces)

        if self.schema is None:
            pass
        elif self.validation == 'strict':
            self.schema.validate(self, namespaces=self.namespaces)
        elif self.validation == 'lax':
            self.errors = [e for e in self.schema.iter_errors(self, namespaces=self.namespaces)]

    def getroot(self) -> ElementType:
        """Get the root element of the XML document."""
        return self._root

    def get_etree_document(self) -> Any:
        """
        The resource as ElementTree XML document. If the resource is lazy raises a resource error.
        """
        if is_etree_document(self._source):
            return self._source
        elif self._lazy:
            msg = "cannot create an ElementTree from a lazy resource"
            raise XMLResourceError(msg)
        elif hasattr(self._root, 'nsmap'):
            return self._root.getroottree()  # type: ignore[attr-defined]
        else:
            return ElementTree.ElementTree(self._root)

    def tostring(self, indent: str = '', max_lines: Optional[int] = None,
                 spaces_for_tab: int = 4, xml_declaration: bool = False,
                 encoding: str = 'unicode', method: str = 'xml') -> str:
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy XML document")

        _string = etree_tostring(
            elem=self._root,
            namespaces=self.namespaces,
            xml_declaration=xml_declaration,
            encoding=encoding,
            method=method
        )
        if isinstance(_string, bytes):
            return _string.decode('utf-8')
        return _string

    def decode(self, **kwargs: Any) -> DecodeType[Any]:
        """
        Decode the XML document to a nested Python dictionary.

        :param kwargs: options for the decode/to_dict method of the schema instance.
        """
        if 'validation' not in kwargs:
            kwargs['validation'] = self.validation
        if 'namespaces' not in kwargs:
            kwargs['namespaces'] = self.namespaces

        schema = self.schema or self._fallback_schema
        if schema is None:
            return None

        obj = schema.to_dict(self, **kwargs)
        return obj[0] if isinstance(obj, tuple) else obj

    def to_json(self, fp: Optional[IO[str]] = None,
                json_options: Optional[Dict[str, Any]] = None,
                **kwargs: Any) -> JsonDecodeType:
        """
        Converts loaded XML data to a JSON string or file.

        :param fp: can be a :meth:`write()` supporting file-like object.
        :param json_options: a dictionary with options for the JSON deserializer.
        :param kwargs: options for the decode/to_dict method of the schema instance.
        """
        if json_options is None:
            json_options = {}
        path = kwargs.pop('path', None)
        if 'validation' not in kwargs:
            kwargs['validation'] = self.validation
        if 'namespaces' not in kwargs:
            kwargs['namespaces'] = self.namespaces
        if 'decimal_type' not in kwargs:
            kwargs['decimal_type'] = float

        errors: List[XMLSchemaValidationError] = []

        if path is None and self._lazy and 'cls' not in json_options:
            json_options['cls'] = get_lazy_json_encoder(errors)
            kwargs['lazy_decode'] = True

        schema = self.schema or self._fallback_schema
        if schema is not None:
            obj = schema.decode(self, path=path, **kwargs)
        else:
            obj = None

        if isinstance(obj, tuple):
            if fp is not None:
                json.dump(obj[0], fp, **json_options)
                obj[1].extend(errors)
                return tuple(obj[1])
            else:
                result = json.dumps(obj[0], **json_options)
                obj[1].extend(errors)
                return result, tuple(obj[1])

        elif fp is not None:
            json.dump(obj, fp, **json_options)
            return None if not errors else tuple(errors)
        else:
            result = json.dumps(obj, **json_options)
            return result if not errors else (result, tuple(errors))

    def write(self, file: Union[str, TextIO, BinaryIO],
              encoding: str = 'us-ascii', xml_declaration: bool = False,
              default_namespace: Optional[str] = None, method: str = "xml") -> None:
        """Serialize an XML resource to a file. Cannot be used with lazy resources."""
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy XML document")

        kwargs: Dict[str, Any] = {
            'xml_declaration': xml_declaration,
            'encoding': encoding,
            'method': method,
        }
        if not default_namespace:
            kwargs['namespaces'] = self.namespaces
        else:
            namespaces: Optional[Dict[Optional[str], str]]
            if self.namespaces is None:
                namespaces = {}
            else:
                namespaces = {k: v for k, v in self.namespaces.items()}

            if hasattr(self._root, 'nsmap'):
                # noinspection PyTypeChecker
                namespaces[None] = default_namespace
            else:
                namespaces[''] = default_namespace
            kwargs['namespaces'] = namespaces

        _string = etree_tostring(self._root, **kwargs)

        if isinstance(file, str):
            if isinstance(_string, str):
                with open(file, 'w', encoding='utf-8') as fp:
                    fp.write(_string)
            else:
                with open(file, 'wb') as _fp:
                    _fp.write(_string)

        elif isinstance(file, TextIOBase):
            if isinstance(_string, bytes):
                file.write(_string.decode('utf-8'))
            else:
                file.write(_string)

        elif isinstance(file, IOBase):
            if isinstance(_string, str):
                file.write(_string.encode('utf-8'))
            else:
                file.write(_string)
        else:
            raise XMLSchemaTypeError(f"unexpected type {type(file)} for 'file' argument")
