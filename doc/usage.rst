*****
Usage
*****

.. _lxml: http://lxml.de

.. testsetup::

    import xmlschema
    import os
    import warnings

    if os.getcwd().endswith('/doc'):
        os.chdir('..')
    warnings.simplefilter("ignore", xmlschema.XMLSchemaIncludeWarning)

.. testsetup:: collection

    import xmlschema
    import os
    import warnings

    if os.getcwd().endswith('/doc'):
        os.chdir('..')
    warnings.simplefilter("ignore", xmlschema.XMLSchemaIncludeWarning)
    schema = xmlschema.XMLSchema('tests/test_cases/examples/collection/collection.xsd')


Create a schema instance
========================

Import the library and then create an instance of a schema using the path of
the file containing the schema as argument:

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')

The argument can be also a file-like object or a string containing the schema definition:

.. doctest::

    >>> schema_file = open('tests/test_cases/examples/collection/collection.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file)

.. doctest::

    >>> schema = xmlschema.XMLSchema("""
    ... <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    ... <xs:element name="block" type="xs:string"/>
    ... </xs:schema>
    ... """)

Strings and file-like objects might not work when the schema includes other local subschemas,
because the package cannot knows anything about the schema's source location:

.. doctest::

    >>> schema_xsd = open('tests/test_cases/examples/vehicles/vehicles.xsd').read()
    >>> schema = xmlschema.XMLSchema(schema_xsd)
    Traceback (most recent call last):
    ...
    ...
    xmlschema.validators.exceptions.XMLSchemaParseError: unknown element '{http://example.com/vehicles}cars':

    Schema:

      <xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" ref="vh:cars" />

    Path: /xs:schema/xs:element/xs:complexType/xs:sequence/xs:element

In these cases you can provide an appropriate *base_url* optional argument to define the
reference directory path for other includes and imports:

.. doctest::

    >>> schema_file = open('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file, base_url='tests/test_cases/examples/vehicles/')


Non standard options for schema instance creation
-------------------------------------------------

Other options for schema instance creation are available using non-standard
methods. Most cases require to use the *build* option to delay the schema
build after the loading of all schema resources. For example:

.. doctest::

    >>> schema_file = open('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file, build=False)
    >>> _ = schema.include_schema('tests/test_cases/examples/vehicles/cars.xsd')
    >>> _ = schema.include_schema('tests/test_cases/examples/vehicles/bikes.xsd')
    >>> schema.build()

Another option, available since release v1.6.1, is to provide a list of schema sources,
particularly useful when sources have no locations associated:

.. doctest::

    >>> sources = [open('tests/test_cases/examples/vehicles/vehicles.xsd'),
    ...            open('tests/test_cases/examples/vehicles/cars.xsd'),
    ...            open('tests/test_cases/examples/vehicles/bikes.xsd'),
    ...            open('tests/test_cases/examples/vehicles/types.xsd')]
    >>> schema = xmlschema.XMLSchema(sources)

or similarly to the previous example one can use the method :meth:`xmlschema.XMLSchemaBase.add_schema`:

.. doctest::

    >>> schema_file = open('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema = xmlschema.XMLSchema(schema_file, build=False)
    >>> _ = schema.add_schema(open('tests/test_cases/examples/vehicles/cars.xsd'))
    >>> _ = schema.add_schema(open('tests/test_cases/examples/vehicles/bikes.xsd'))
    >>> _ = schema.add_schema(open('tests/test_cases/examples/vehicles/types.xsd'))
    >>> schema.build()


.. note::
    Anyway the advice is to build intermediate XSD schemas intead for loading
    all the schemas needed in a standard way, because XSD mechanisms of imports,
    includes, redefines and overrides are usually supported when you submit your
    schemas to other XSD validators.


Validation
==========

A schema instance has methods to validate an XML document against the schema.

The first method is :meth:`xmlschema.XMLSchemaBase.is_valid`, that returns ``True``
if the XML argument is validated by the schema loaded in the instance,
and returns ``False`` if the document is invalid.

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.is_valid('tests/test_cases/examples/vehicles/vehicles.xml')
    True
    >>> schema.is_valid('tests/test_cases/examples/vehicles/vehicles-1_error.xml')
    False
    >>> schema.is_valid("""<?xml version="1.0" encoding="UTF-8"?><fancy_tag/>""")
    False

An alternative mode for validating an XML document is implemented by the method
:meth:`xmlschema.XMLSchemaBase.validate`, that raises an error when the XML doesn't
conform to the schema:

.. doctest::

    >>> import xmlschema
    >>> schema = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> schema.validate('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> schema.validate('tests/test_cases/examples/vehicles/vehicles-1_error.xml')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/home/brunato/Development/projects/xmlschema/xmlschema/schema.py", line 220, in validate
        raise error
    xmlschema.exceptions.XMLSchemaValidationError: failed validating <Element ...

    Reason: character data between child elements not allowed!

    Schema:

      <xs:sequence xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <xs:element maxOccurs="unbounded" minOccurs="0" name="car" type="vh:vehicleType" />
      </xs:sequence>

    Instance:

      <ns0:cars xmlns:ns0="http://example.com/vehicles">
        NOT ALLOWED CHARACTER DATA
        <ns0:car make="Porsche" model="911" />
        <ns0:car make="Porsche" model="911" />
      </ns0:cars>


A validation method is also available at module level, useful when you need to
validate a document only once or if you extract information about the schema,
typically the schema location and the namespace, directly from the XML document:

.. doctest::

    >>> xmlschema.validate('tests/test_cases/examples/vehicles/vehicles.xml')

    >>> xml_file = 'tests/test_cases/examples/vehicles/vehicles.xml'
    >>> xsd_file = 'tests/test_cases/examples/vehicles/vehicles.xsd'
    >>> xmlschema.validate(xml_file, schema=xsd_file)


Data decoding and encoding
==========================

A schema instance can be also used for decoding an XML document to a nested dictionary:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/vehicles/vehicles.xml'))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}

The decoded values match the datatypes declared in the XSD schema:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/collection/collection.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/collection/collection.xml'))
    {'@xmlns:col': 'http://example.com/ns/collection',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/ns/collection collection.xsd',
     'object': [{'@available': True,
                 '@id': 'b0836217462',
                 'author': {'@id': 'PAR',
                            'born': '1841-02-25',
                            'dead': '1919-12-03',
                            'name': 'Pierre-Auguste Renoir',
                            'qualification': 'painter'},
                 'estimation': Decimal('10000.00'),
                 'position': 1,
                 'title': 'The Umbrellas',
                 'year': '1886'},
                {'@available': True,
                 '@id': 'b0836217463',
                 'author': {'@id': 'JM',
                            'born': '1893-04-20',
                            'dead': '1983-12-25',
                            'name': 'Joan Miró',
                            'qualification': 'painter, sculptor and ceramicist'},
                 'position': 2,
                 'title': None,
                 'year': '1925'}]}


Decoded data can be encoded back to XML:

.. doctest:: collection

    >>> obj = schema.decode('tests/test_cases/examples/collection/collection.xml')
    >>> collection = schema.encode(obj)
    >>> collection
    <Element '{http://example.com/ns/collection}collection' at ...>
    >>> print(xmlschema.etree_tostring(collection, {'col': 'http://example.com/ns/collection'}))
    <col:collection xmlns:col="http://example.com/ns/collection" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://example.com/ns/collection collection.xsd">
        <object id="b0836217462" available="true">
            <position>1</position>
            <title>The Umbrellas</title>
            <year>1886</year>
            <author id="PAR">
                <name>Pierre-Auguste Renoir</name>
                <born>1841-02-25</born>
                <dead>1919-12-03</dead>
                <qualification>painter</qualification>
            </author>
            <estimation>10000.00</estimation>
        </object>
        <object id="b0836217463" available="true">
            <position>2</position>
            <title />
            <year>1925</year>
            <author id="JM">
                <name>Joan Miró</name>
                <born>1893-04-20</born>
                <dead>1983-12-25</dead>
                <qualification>painter, sculptor and ceramicist</qualification>
            </author>
        </object>
    </col:collection>


All the decoding and encoding methods are based on two generator methods of the `XMLSchema` class,
namely *iter_decode()* and *iter_encode()*, that yield both data and validation errors.
See :ref:`schema-level-api` section for more information.


Decoding a part using XPath
---------------------------

If you need to decode only a part of the XML document you can pass also an XPath
expression using the *path* argument.

.. doctest::

    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> pprint(xs.to_dict('tests/test_cases/examples/vehicles/vehicles.xml', '/vh:vehicles/vh:bikes'))
    {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                 {'@make': 'Yamaha', '@model': 'XS650'}]}

.. note::

    An XPath expression for the schema *considers the schema as the root element
    with global elements as its children*.


Validating and decoding ElementTree's data
------------------------------------------

Validation and decode API works also with XML data loaded in ElementTree structures:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> from xml.etree import ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt, process_namespaces=False), depth=2)
    {'@{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://...',
     '{http://example.com/vehicles}bikes': {'{http://example.com/vehicles}bike': [...]},
     '{http://example.com/vehicles}cars': {'{http://example.com/vehicles}car': [...]}}

The standard ElementTree library lacks of namespace information in trees, so you
have to provide a map to convert URIs to prefixes:

    >>> namespaces = {'xsi': 'http://www.w3.org/2001/XMLSchema-instance', 'vh': 'http://example.com/vehicles'}
    >>> pprint(xs.to_dict(xt, namespaces=namespaces))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}

You can also convert XML data using the lxml_ library, that works better because
namespace information is associated within each node of the trees:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> import lxml.etree as ElementTree
    >>> xs = xmlschema.XMLSchema('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> xt = ElementTree.parse('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xs.is_valid(xt)
    True
    >>> pprint(xs.to_dict(xt))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}
    >>> pprint(xmlschema.to_dict(xt, 'tests/test_cases/examples/vehicles/vehicles.xsd'))
    {'@xmlns:vh': 'http://example.com/vehicles',
     '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
     '@xsi:schemaLocation': 'http://example.com/vehicles vehicles.xsd',
     'vh:bikes': {'vh:bike': [{'@make': 'Harley-Davidson', '@model': 'WL'},
                              {'@make': 'Yamaha', '@model': 'XS650'}]},
     'vh:cars': {'vh:car': [{'@make': 'Porsche', '@model': '911'},
                            {'@make': 'Porsche', '@model': '911'}]}}


Customize the decoded data structure
------------------------------------

Starting from the version 0.9.9 the package includes converter objects, in order to
control the decoding process and produce different data structures. These objects
intervene at element level to compose the decoded data (attributes and content) into
a data structure.

The default converter produces a data structure similar to the format produced by
previous versions of the package. You can customize the conversion process providing
a converter instance or subclass when you create a schema instance or when you want
to decode an XML document.
For instance you can use the *Badgerfish* converter for a schema instance:

.. doctest::

    >>> import xmlschema
    >>> from pprint import pprint
    >>> xml_schema = 'tests/test_cases/examples/vehicles/vehicles.xsd'
    >>> xml_document = 'tests/test_cases/examples/vehicles/vehicles.xml'
    >>> xs = xmlschema.XMLSchema(xml_schema, converter=xmlschema.BadgerFishConverter)
    >>> pprint(xs.to_dict(xml_document, dict_class=dict), indent=4)
    {   '@xmlns': {   'vh': 'http://example.com/vehicles',
                      'xsi': 'http://www.w3.org/2001/XMLSchema-instance'},
        'vh:vehicles': {   '@xsi:schemaLocation': 'http://example.com/vehicles '
                                                  'vehicles.xsd',
                           'vh:bikes': {   'vh:bike': [   {   '@make': 'Harley-Davidson',
                                                              '@model': 'WL'},
                                                          {   '@make': 'Yamaha',
                                                              '@model': 'XS650'}]},
                           'vh:cars': {   'vh:car': [   {   '@make': 'Porsche',
                                                            '@model': '911'},
                                                        {   '@make': 'Porsche',
                                                            '@model': '911'}]}}}

You can also change the data decoding process providing the keyword argument *converter*
to the method call:

.. doctest::

    >>> pprint(xs.to_dict(xml_document, converter=xmlschema.ParkerConverter, dict_class=dict), indent=4)
    {'vh:bikes': {'vh:bike': [None, None]}, 'vh:cars': {'vh:car': [None, None]}}


See the :ref:`converters` section for more information about converters.


Control the decoding of XSD atomic datatypes
--------------------------------------------

XSD datatypes are decoded to Python basic datatypes. Python strings are used
for all string-based XSD types and others, like *xs:hexBinary* or *xs:QName*.
Python integers are used for *xs:integer* and derived types, `bool` for *xs:boolean*
values and `decimal.Decimal` for *xs:decimal* values.

Currently there are three options for variate the decoding of XSD atomic datatypes:

decimal_type
    decoding type for *xs:decimal* (is `decimal.Decimal` for default)

datetime_types
    if set to `True` decodes datetime and duration types to their respective XSD
    atomic types instead of keeping the XML string value

binary_types
    if set to `True` decodes *xs:hexBinary* and *xs:base64Binary* types to their
    respective XSD atomic types instead of keeping the XML string value


Filling missing values
----------------------

Incompatible values are decoded with `None` when the *validation* mode is `'lax'`.
For these situations there are two options for changing the behavior of the decoder:

filler
    a callback function to fill undecodable data with a typed value. The
    callback function must accept one positional argument, that can be an
    XSD Element or an attribute declaration. If not provided undecodable
    data is replaced by `None`.

fill_missing
    if set to True the decoder fills also missing attributes. The filling value
    is None or a typed value if the *filler* callback is provided.


Control the decoding of elements
--------------------------------

These options concern the decoding of XSD elements:

value_hook
    a function that will be called with any decoded atomic value and the XSD type
    used for decoding. The return value will be used instead of the original value.

keep_empty
    if set to `True` empty elements that are valid are decoded with an empty string
    value instead of `None`.

element_hook
    an function that is called with decoded element data before calling the converter
    decode method. Takes an `ElementData` instance plus optionally the XSD element
    and the XSD type, and returns a new `ElementData` instance.


Control the decoding of wildcards
---------------------------------

These two options are specific for the content processed with an XSD wildcard:

keep_unknown
    if set to `True` unknown tags are kept and are decoded with *xs:anyType*.
    For default unknown tags not decoded by a wildcard are discarded.

process_skipped
    process XML data that match a wildcard with `processContents=’skip’`.


Control the decoding depth
--------------------------

max_depth
    maximum level of decoding, for default there is no limit. With lazy resources
    is automatically set to *source.lazy_depth* for managing lazy decoding.

depth_filler
    a callback function for replacing data over the *max_depth* level. The callback
    function must accept one positional argument, that can be an XSD Element. For
    default deeper data is replaced with `None` values when *max_depth* is provided.


Decoding to JSON
================

The data structured created by the decoder can be easily serialized to JSON. But if you data
include `Decimal` values (for *decimal* XSD built-in type) you cannot convert the data to JSON:

.. doctest::

    >>> import xmlschema
    >>> import json
    >>> xml_document = 'tests/test_cases/examples/collection/collection.xml'
    >>> print(json.dumps(xmlschema.to_dict(xml_document), indent=4))
    Traceback (most recent call last):
      File "/usr/lib64/python2.7/doctest.py", line 1315, in __run
        compileflags, 1) in test.globs
      File "<doctest default[3]>", line 1, in <module>
        print(json.dumps(xmlschema.to_dict(xml_document), indent=4))
      File "/usr/lib64/python2.7/json/__init__.py", line 251, in dumps
        sort_keys=sort_keys, **kw).encode(obj)
      File "/usr/lib64/python2.7/json/encoder.py", line 209, in encode
        chunks = list(chunks)
      File "/usr/lib64/python2.7/json/encoder.py", line 434, in _iterencode
        for chunk in _iterencode_dict(o, _current_indent_level):
      File "/usr/lib64/python2.7/json/encoder.py", line 408, in _iterencode_dict
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 332, in _iterencode_list
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 408, in _iterencode_dict
        for chunk in chunks:
      File "/usr/lib64/python2.7/json/encoder.py", line 442, in _iterencode
        o = _default(o)
      File "/usr/lib64/python2.7/json/encoder.py", line 184, in default
        raise TypeError(repr(o) + " is not JSON serializable")
    TypeError: Decimal('10000.00') is not JSON serializable

This problem is resolved providing an alternative JSON-compatible type for `Decimal` values,
using the keyword argument *decimal_type*:

.. doctest::

    >>> print(json.dumps(xmlschema.to_dict(xml_document, decimal_type=str), indent=4))  # doctest: +SKIP
    {
        "object": [
            {
                "@available": true,
                "author": {
                    "qualification": "painter",
                    "born": "1841-02-25",
                    "@id": "PAR",
                    "name": "Pierre-Auguste Renoir",
                    "dead": "1919-12-03"
                },
                "title": "The Umbrellas",
                "year": "1886",
                "position": 1,
                "estimation": "10000.00",
                "@id": "b0836217462"
            },
            {
                "@available": true,
                "author": {
                    "qualification": "painter, sculptor and ceramicist",
                    "born": "1893-04-20",
                    "@id": "JM",
                    "name": "Joan Mir\u00f3",
                    "dead": "1983-12-25"
                },
                "title": null,
                "year": "1925",
                "position": 2,
                "@id": "b0836217463"
            }
        ],
        "@xsi:schemaLocation": "http://example.com/ns/collection collection.xsd"
    }

From version 1.0 there are two module level API for simplify the JSON serialization
and deserialization task.
See the :meth:`xmlschema.to_json` and :meth:`xmlschema.from_json` in the
:ref:`document-level-api` section.


XML resources and documents
===========================

Schemas and XML instances processing are based on the class :class:`xmlschema.XMLResource`,
that handles the loading and the iteration of XSD/XML data.
Starting from v1.3.0 :class:`xmlschema.XMLResource` has been empowered with ElementTree-like
XPath API. From the same release a new class :class:`xmlschema.XmlDocument` is
available for representing XML resources with a related schema:

.. doctest::

    >>> import xmlschema
    >>> xml_document = xmlschema.XmlDocument('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xml_document.schema
    XMLSchema10(name='vehicles.xsd', namespace='http://example.com/vehicles')

This class can be used to derive specialized schema-related classes.
See :ref:`wsdl11-documents` section for an application example.


Meta-schemas and XSD sources
============================

Schema classes :class:`xmlschema.XMLSchema10` and :class:`xmlschema.XMLSchema11`
have built-in meta-schema instances, related to the XSD namespace, that can be used
directly to validate XSD sources without build a new schema:

.. doctest::

    >>> from xmlschema import XMLSchema
    >>> XMLSchema.meta_schema.validate('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> XMLSchema.meta_schema.validate('tests/test_cases/examples/vehicles/invalid.xsd')
    Traceback (most recent call last):
    ...
    ...
    xmlschema.validators.exceptions.XMLSchemaValidationError: failed validating ...

    Reason: use of attribute 'name' is prohibited

    Schema:

      <xs:restriction xmlns:xs="http://www.w3.org/2001/XMLSchema" base="xs:complexType">
       <xs:sequence>
        <xs:element ref="xs:annotation" minOccurs="0" />
        <xs:group ref="xs:complexTypeModel" />
       </xs:sequence>
       <xs:attribute name="name" use="prohibited" />
       <xs:attribute name="abstract" use="prohibited" />
       <xs:attribute name="final" use="prohibited" />
       <xs:attribute name="block" use="prohibited" />
       <xs:anyAttribute namespace="##other" processContents="lax" />
      </xs:restriction>

    Instance:

      <xs:complexType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="vehiclesType">
        <xs:sequence>
          <xs:element ref="vh:cars" />
          <xs:element ref="vh:bikes" />
        </xs:sequence>
      </xs:complexType>

    Path: /xs:schema/xs:element/xs:complexType


Furthermore also decode and encode methods can be applied on XSD files or sources:

.. doctest::

    >>> from xmlschema import XMLSchema
    >>> obj = XMLSchema.meta_schema.decode('tests/test_cases/examples/vehicles/vehicles.xsd')
    >>> from pprint import pprint
    >>> pprint(obj)
    {'@attributeFormDefault': 'unqualified',
     '@blockDefault': [],
     '@elementFormDefault': 'qualified',
     '@finalDefault': [],
     '@targetNamespace': 'http://example.com/vehicles',
     '@xmlns:xs': 'http://www.w3.org/2001/XMLSchema',
     'xs:attribute': {'@name': 'step', '@type': 'xs:positiveInteger'},
     'xs:element': {'@abstract': False,
                    '@name': 'vehicles',
                    '@nillable': False,
                    'xs:complexType': {'@mixed': False,
                                       'xs:sequence': {'@maxOccurs': 1,
                                                       '@minOccurs': 1,
                                                       'xs:element': [{'@maxOccurs': 1,
                                                                       '@minOccurs': 1,
                                                                       '@nillable': False,
                                                                       '@ref': 'vh:cars'},
                                                                      {'@maxOccurs': 1,
                                                                       '@minOccurs': 1,
                                                                       '@nillable': False,
                                                                       '@ref': 'vh:bikes'}]}}},
     'xs:include': [{'@schemaLocation': 'cars.xsd'},
                    {'@schemaLocation': 'bikes.xsd'}]}

.. note::
    Building a new schema for XSD namespace could be not trivial because other schemas are
    required for base namespaces (e.g. XML namespace 'http://www.w3.org/XML/1998/namespace').
    This is particularly true for XSD 1.1 because the XSD meta-schema lacks of built-in
    list types definitions, so a patch schema is required.
