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
from collections.abc import Iterator

from .exceptions import XMLSchemaTypeError, XMLSchemaValueError, XMLResourceError
from .names import XSD_NAMESPACE, XSI_TYPE
from .etree import ElementTree, etree_tostring
from .helpers import is_etree_document
from .resources import fetch_schema_locations, XMLResource
from .validators import XMLSchema10, XMLSchemaBase, XMLSchemaValidationError


def get_context(source, schema=None, cls=None, locations=None, base_url=None,
                defuse='remote', timeout=300, lazy=False, dummy_schema=False):
    """
    Get the XML document validation/decode context.

    :return: an XMLResource instance and a schema instance.
    """
    if cls is None:
        cls = XMLSchema10
    if not isinstance(source, XMLResource):
        source = XMLResource(source, base_url, defuse=defuse, timeout=timeout, lazy=lazy)
    if isinstance(schema, XMLSchemaBase) and source.namespace in schema.maps.namespaces:
        return source, schema
    if isinstance(source, XmlDocument) and source.schema is not None:
        return source, source.schema

    try:
        schema_location, locations = fetch_schema_locations(source, locations, base_url=base_url)
    except ValueError:
        if schema is None:
            if XSI_TYPE in source.root.attrib:
                schema = cls.meta_schema
            elif dummy_schema:
                return source, get_dummy_schema(source, cls)
            else:
                msg = "no schema can be retrieved for the provided XML data"
                raise XMLSchemaValueError(msg) from None

        elif not isinstance(schema, XMLSchemaBase):
            schema = cls(schema, validation='strict', locations=locations,
                         base_url=base_url, defuse=defuse, timeout=timeout)
    else:
        schema = cls(schema or schema_location, validation='strict', locations=locations,
                     defuse=defuse, timeout=timeout)

    return source, schema


def get_dummy_schema(xml_resource, schema_class):
    tag = xml_resource.root.tag
    if tag.startswith('{'):
        namespace, name = tag[1:].split('}')
    else:
        namespace, name = '', tag

    if namespace:
        return schema_class(
            '<xs:schema xmlns:xs="{0}" targetNamespace="{1}">\n'
            '    <xs:element name="{2}"/>\n'
            '</xs:schema>'.format(XSD_NAMESPACE, namespace, name)
        )
    else:
        return schema_class(
            '<xs:schema xmlns:xs="{0}">\n'
            '    <xs:element name="{1}"/>\n'
            '</xs:schema>'.format(XSD_NAMESPACE, name)
        )


def get_lazy_json_encoder(errors):

    class JSONLazyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Iterator):
                while True:
                    result = next(obj, None)
                    if isinstance(result, XMLSchemaValidationError):
                        errors.append(result)
                    else:
                        return result
            return json.JSONEncoder.default(self, obj)

    return JSONLazyEncoder


def validate(xml_document, schema=None, cls=None, path=None, schema_path=None,
             use_defaults=True, namespaces=None, locations=None, base_url=None,
             defuse='remote', timeout=300, lazy=False):
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
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    schema.validate(source, path, schema_path, use_defaults, namespaces)


def is_valid(xml_document, schema=None, cls=None, path=None, schema_path=None,
             use_defaults=True, namespaces=None, locations=None, base_url=None,
             defuse='remote', timeout=300, lazy=False):
    """
    Like :meth:`validate` except that do not raises an exception but returns ``True`` if
    the XML document is valid, ``False`` if it's invalid.
    """
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return schema.is_valid(source, path, schema_path, use_defaults, namespaces)


def iter_errors(xml_document, schema=None, cls=None, path=None, schema_path=None,
                use_defaults=True, namespaces=None, locations=None, base_url=None,
                defuse='remote', timeout=300, lazy=False):
    """
    Creates an iterator for the errors generated by the validation of an XML document.
    Takes the same arguments of the function :meth:`validate`.
    """
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return schema.iter_errors(source, path, schema_path, use_defaults, namespaces)


def to_dict(xml_document, schema=None, cls=None, path=None, process_namespaces=True,
            locations=None, base_url=None, defuse='remote', timeout=300, lazy=False, **kwargs):
    """
    Decodes an XML document to a Python's nested dictionary. The decoding is based
    on an XML Schema class instance. For default the document is validated during
    the decoding phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

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
    :return: an object containing the decoded data. If ``validation='lax'`` keyword argument \
    is provided the validation errors are collected and returned coupled in a tuple with the \
    decoded data.
    :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
    the XSD component, or also if it's invalid when ``validation='strict'`` is provided.
    """
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    return schema.decode(source, path=path, process_namespaces=process_namespaces, **kwargs)


def to_json(xml_document, fp=None, schema=None, cls=None, path=None, converter=None,
            process_namespaces=True, locations=None, base_url=None, defuse='remote',
            timeout=300, lazy=False, json_options=None, **kwargs):
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
    source, schema = get_context(
        xml_document, schema, cls, locations, base_url, defuse, timeout, lazy
    )
    if json_options is None:
        json_options = {}
    if 'decimal_type' not in kwargs:
        kwargs['decimal_type'] = float
    kwargs['converter'] = converter
    kwargs['process_namespaces'] = process_namespaces

    errors = []

    if path is None and source.is_lazy() and 'cls' not in json_options:
        json_options['cls'] = get_lazy_json_encoder(errors)

    obj = schema.decode(source, path=path, **kwargs)
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


def from_json(source, schema, path=None, converter=None, json_options=None, **kwargs):
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
    :param kwargs: Keyword arguments containing options for converter and encoding.
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

    if hasattr(source, 'read'):
        obj = json.load(source, **json_options)
    else:
        obj = json.loads(source, **json_options)

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
    schema = _fallback_schema = None
    validation = 'skip'
    namespaces = None
    errors = ()

    def __init__(self, source, schema=None, cls=None, validation='strict',
                 namespaces=None, locations=None, base_url=None, allow='all',
                 defuse='remote', timeout=300, lazy=False):

        self.validation = validation
        self._namespaces = namespaces
        super(XmlDocument, self).__init__(source, base_url, allow, defuse, timeout, lazy)

        if isinstance(schema, XMLSchemaBase) and self.namespace in schema.maps.namespaces:
            self.schema = schema
        elif schema is not None:
            self.schema = (cls or XMLSchema10)(
                source=schema,
                base_url=base_url,
                allow=allow,
                defuse=defuse,
                timeout=timeout,
            )
        else:
            if cls is None:
                cls = XMLSchema10

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

        if validation == 'strict':
            self.schema.validate(self, namespaces=self.namespaces)
        elif validation == 'lax':
            self.errors = [e for e in self.schema.iter_errors(self, namespaces=self.namespaces)]
        elif validation != 'skip':
            raise XMLSchemaValueError("{!r}: not a validation mode".format(validation))

    def parse(self, source, lazy=False):
        super(XmlDocument, self).parse(source, lazy)
        self.namespaces = self.get_namespaces(self._namespaces)

        if self.schema is None:
            pass
        elif self.validation == 'strict':
            self.schema.validate(self, namespaces=self.namespaces)
        elif self.validation == 'lax':
            self.errors = [e for e in self.schema.iter_errors(self, namespaces=self.namespaces)]

    def getroot(self):
        """Get the root element of the XML document."""
        return self._root

    def get_etree_document(self):
        """
        The resource as ElementTree XML document. If the resource is lazy raises a resource error.
        """
        if is_etree_document(self._source):
            return self._source
        elif self._lazy:
            msg = "cannot create an ElementTree from a lazy resource"
            raise XMLResourceError(msg)
        elif hasattr(self._root, 'nsmap'):
            return self._root.getroottree()
        else:
            return ElementTree.ElementTree(self._root)

    def tostring(self, indent='', max_lines=None, spaces_for_tab=4,
                 xml_declaration=False, encoding='unicode', method='xml'):
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy XML document")

        return etree_tostring(
            elem=self._root,
            namespaces=self.namespaces,
            xml_declaration=xml_declaration,
            encoding=encoding,
            method=method
        )

    def decode(self, **kwargs):
        """
        Decode the XML document to a nested Python dictionary.

        :param kwargs: options for the decode/to_dict method of the schema instance.
        """
        if 'validation' not in kwargs:
            kwargs['validation'] = self.validation
        if 'namespaces' not in kwargs:
            kwargs['namespaces'] = self.namespaces

        obj = (self.schema or self._fallback_schema).to_dict(self, **kwargs)
        return obj[0] if isinstance(obj, tuple) else obj

    def to_json(self, fp=None, json_options=None, **kwargs):
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

        errors = []

        if path is None and self._lazy and 'cls' not in json_options:
            json_options['cls'] = get_lazy_json_encoder(errors)
            kwargs['lazy_decode'] = True

        obj = (self.schema or self._fallback_schema).decode(self, path=path, **kwargs)
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

    def write(self, file, encoding='us-ascii', xml_declaration=None,
              default_namespace=None, method="xml"):
        """Serialize an XML resource to a file. Cannot be used with lazy resources."""
        if self._lazy:
            raise XMLResourceError("cannot serialize a lazy XML document")

        kwargs = {
            'xml_declaration': xml_declaration,
            'encoding': encoding,
            'method': method,
        }
        if not default_namespace:
            kwargs['namespaces'] = self.namespaces
        else:
            namespaces = self.namespaces.copy()
            if hasattr(self._root, 'nsmap'):
                namespaces[None] = default_namespace
            else:
                namespaces[''] = default_namespace
            kwargs['namespaces'] = namespaces

        if hasattr(file, 'write'):
            file.write(etree_tostring(self._root, **kwargs))
            file.close()
        elif encoding == 'unicode':
            with open(file, 'w', encoding='utf-8') as fp:
                fp.write(etree_tostring(self._root, **kwargs))
        else:
            with open(file, 'wb') as fp:
                fp.write(etree_tostring(self._root, **kwargs))
