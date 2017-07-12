API Documentation
=================

Module level API
----------------

.. function:: validate(xml_document, schema=None, cls=None, use_defaults=True)

    Validates an XML document against a schema instance. This function builds an
    :class:`XMLSchema` object for validating the XML document. Raises an
    :exc:`XMLSchemaValidationError` if the XML document is not validated against
    the schema.

    *xml_document* can be a file-like object or a string containing the XML data
    or a file path or an URI of a resource or an ElementTree/Element instance.
    *schema* can be a file-like object or a file path or an URI of a resource or
    a string containing the schema. *cls* is the schema class to use for building
    the instance (default is :class:`XMLSchema`). *use_defaults* defines when to
    use elements and attribute defaults for filling missing required values.

.. function:: to_dict(xml_document, schema=None, cls=None, path=None, \
              process_namespaces=True, **kwargs)

    Decodes an XML document to a Python's nested dictionary. The decoding is based
    on an XML Schema class instance. For default the document is validated during
    the decode phase. Raises an :exc:`XMLSchemaValidationError` if the XML document
    is not validated against the schema.

    *xml_document* can be a file-like object or a string containing the XML data
    or a file path or an URI of a resource or an ElementTree/Element instance.
    *schema* can be a file-like object or a file path or an URI of a resource or
    a string containing the schema. *cls* is the schema class to use for building
    the instance (default is :class:`XMLSchema`). *path* is an optional XPath
    expression that matches the subelement of the document that have to be decoded.
    The XPath expression considers the schema as the root element with global elements
    as its children.
    *process_namespaces* indicates whether to get the namespaces from the XML
    document and use them in the decoding process. With *kwargs* you can provide
    the optional arguments of :meth:`XMLSchema.iter_decode` as keyword arguments
    to variate the decoding process.


Schema level API
----------------

.. class:: XMLSchema(source, namespace=None, validation='strict', global_maps=None, \
           converter=None, build=True)

    The class for an XML Schema instance.
    *source* can be an URI that reference to a resource or a file path or a file-like
    object or a string containing the schema. *namespace* is an optional argument
    that contains the URI of the namespace. When specified it must be equal to the
    *targetNamespace* declared in the schema. *validation* defines the XSD validation
    mode to use for build the schema, can be 'strict', 'lax' or 'skip'.
    *global_maps* is an optional argument containing an :class:`XsdGlobals`
    instance, a mediator object for sharing declaration data between dependents
    schema instances. *converter* is an optional argument that can be an
    :class:`XMLSchemaConverter` subclass or instance, used for defining the default
    XML data converter for XML Schema instance. *build* is a boolean value that defines
    whether build the schema maps.

    .. attribute::root

        The XML schema Element root.

    .. attribute:: text

        The XML schema source text.

    .. attribute:: url

        The schema resource URL. It's `None` if the schema is built from a string.

    .. attribute:: target_namespace

        Is the *targetNamespace* of the schema, the namespace to which the schema's
        declarations belong. If it's empty none namespace is associated with the schema.
        In this case the schema declarations can be reused from other namespaces as
        *chameleon* definitions.

    .. py:attribute:: element_form

        *elementFormDefault* for the schema, default to ``'unqualified'``.

    .. py:attribute:: attribute_form

        *attributeFormDefault* for the schema, default to ``'unqualified'``.

    .. attribute:: schema_locations
    .. py:attribute:: no_namespace_schema_location

        Schema location hints. Usually specified in XML files, sometimes it's used
        in schemas when the namespace definitions are splitted into more files.

    .. attribute:: built

        Property that is ``True`` if schema declarations has been parsed and
        built, ``False`` if not.

    .. attribute:: namespaces

        A map from prefixes used by the schema to the correspondent namespace URI.
        This mapping can be different between each schema resource, so it's saved
        at schema's instance level.

    .. attribute:: converter

        The default `XMLSchemaConverter` instance used for XML data conversion.

    .. attribute:: maps

        An instance of :class:`XsdGlobal` that match the *global_maps* argument or
        a new :class:`XsdGlobal` object when this argument is not provided.

    .. attribute:: types
    .. attribute:: attributes
    .. attribute:: attribute_groups
    .. attribute:: groups
    .. attribute:: elements
    .. attribute:: base_elements

        Dictionary views of the global declarations defined by the schema instance.
        The global declarations are taken from the declarations of :attr:`maps`.
        In the schema's views the global declaration names are registered with the
        local part only.

    .. classmethod:: create_schema(*args, **kwargs)

        Creates a new schema instance of the same class of the caller.

    .. classmethod:: check_schema(schema)

        Validates the given schema against the XSD :attr:`META_SCHEMA`.

        :raises: :exc:`XMLSchemaValidationError` if the schema is invalid.

    .. method:: import_schema(namespace, location, base_url=None, force=False)

        Imports a schema for an external namespace, from a specific URL.
        *namespace* is the URI of the external namespace.
        *location* is the URL of the schema.
        *base_url* is an optional base URL for fetching the schema resource.
        If *force* is set to `True` imports the schema also if the namespace
        is already imported.

    .. method:: include_schema(location, base_url=None)

        Include a schema for the namespace, from a specific URL.
        *location* is the URL of the schema.
        *base_url* is an optional base URL for fetching the schema resource.

    .. method:: build()

        Builds the schema maps.

    .. method:: validate(xml_document, use_defaults=True)

        Validates an XML document against the schema instance. *xml_document* can be
        a path to a file or an URI of a resource or an opened file-like object or
        an Element Tree instance or a string containing XML data. *use_defaults*
        indicates whether to use default values for filling missing attributes or
        elements.

        :raises: :exc:`XMLSchemaValidationError` if the XML document is invalid.

    .. method:: is_valid(xml_document, use_defaults=True)

        Like :meth:`validate` except that do not raises an exception but returns
        ``True`` if the XML document is valid, ``False`` if is invalid.

    .. method:: iter_errors(xml_document, path=None, use_defaults=True)

        Creates an iterator for errors generated by the validation of an XML
        document against the schema instance. *path* is an optional XPath expression
        that defines the parts of the document that have to be validated. The XPath
        expression considers the schema as the root element with global elements as its children.
        *use_defaults* indicates whether to use default values for filling missing
        attributes or elements.

    .. method:: iter_decode(self, data, path=None, validation='lax', process_namespaces=True,\
                namespaces=None, use_defaults=True, decimal_type=None, converter=None,\
                dict_class=None, list_class=None)

        Creates an iterator for decoding an XML document using the schema instance.
        Yields objects that can be dictionaries or simple data values.
        *path* is an optional XPath expression that matches the parts of the document
        that have to be decoded. The XPath expression considers the schema as the root
        element with global elements as its children.
        *validation* defines the XSD validation mode to use for decode, can be 'strict',
        'lax' or 'skip'.
        *process_namespaces* indicates whether to process namespaces, using the map
        provided with the argument *namespaces* and the map extracted from the XML
        document.
        *namespaces* is an optional mapping from namespace prefix to URI.
        *use_defaults* indicates whether to use default values for filling missing
        attributes or elements.
        *decimal_type* conversion type for `Decimal` objects (generated by XSD `decimal`
        built-in and derived types), useful if you want to generate a JSON-compatible
        data structure.
        *converter* an `XMLSchemaConverter` subclass or instance to use for the decoding.
        *dict_class* the dictionary-like class that have to be used instead of
        the default dictionary class of the `XMLSchemaConverter` subclass/instance.
        *list_class* the list-like class that have to be used instead of the default
        list class of the `XMLSchemaConverter` class/instance.

    .. method:: decode(*args, **kwargs)
    .. method:: to_dict(*args, **kwargs)

        Decodes an XML document to a Python data structure using the schema instance.
        You can provide the arguments and keyword arguments of :meth:`iter_decode`.
        Raises an `XMLSchemaValidationError` at first decoding or validation error (when
        validation is requested, that is the default).

    .. method:: iter(name=None)

        Creates a schema iterator for elements declarations. The iteration starts
        from global XSD elements, going deep into the XSD declarations graph.
        If *name* argument is not ``None`` yields only the XSD elements matching
        the name.

    .. method:: iterchildren(name=None)

        Creates an iterator for global elements, sorted by name. If *name* is not
        ``None`` yields only the XSD global element matching the name.

    .. method:: find(path, namespaces=None)

        Finds the first XSD element or attribute declaration matching the path.
        Returns an XSD declaration or ``None`` if there is no match.
        *path* is an XPath expression that considers the schema as the root element
        with global elements as its children.
        *namespaces* is an optional mapping from namespace prefix to full name.

    .. method:: findall(path, namespaces=None)

        Finds all matching XSD element or attribute declarations matching the path.
        Returns a list containing all matching declarations in the schema order.
        An empty list is returned if there is no match.
        *path* is an XPath expression that considers the schema as the root element
        with global elements as its children.
        *namespaces* is an optional mapping from namespace prefix to full name.

    .. method:: iterfind(path, namespaces=None)

        Finds all matching XSD element or attribute declarations matching the path.
        Returns an iterable yielding all matching declarations in the schema order.
        *path* is an XPath expression that considers the schema as the root element
        with global elements as its children.
        *namespaces* is an optional mapping from namespace prefix to full name.


XSD globals maps API
--------------------

.. autoclass:: xmlschema.XsdGlobals
    :members: copy, register, iter_schemas, iter_globals, clear, build

XML Schema converters
---------------------

The base class `XMLSchemaConverter` is used for defining generic converters.
The subclasses implement some of the most used conventions for converting XML
to JSON data.

.. autoclass:: xmlschema.converters.XMLSchemaConverter
    :members: element_decode

.. class:: xmlschema.converters.ParkerConverter

    Converter class for Parker convention.

.. class:: xmlschema.converters.BadgerFishConverter

    Converter class for Badgerfish convention.

.. class:: xmlschema.converters.AbderaConverter

    Converter class for Abdera convention.

.. class:: xmlschema.converters.JsonMLConverter

    Converter class for JsonML convention.


Errors and exceptions
---------------------

.. autoexception:: xmlschema.XMLSchemaException

.. autoexception:: xmlschema.XMLSchemaNotBuiltError

.. autoexception:: xmlschema.XMLSchemaParseError

.. autoexception:: xmlschema.XMLSchemaRegexError

.. autoexception:: xmlschema.XMLSchemaXPathError

.. autoexception:: xmlschema.XMLSchemaValidationError

.. autoexception:: xmlschema.XMLSchemaDecodeError

.. autoexception:: xmlschema.XMLSchemaEncodeError

