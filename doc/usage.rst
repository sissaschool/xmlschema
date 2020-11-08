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


Validation
==========

A schema instance has methods to validate an XML document against the schema.

The first method is :meth:`XMLSchema.is_valid`, that returns ``True``
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
:meth:`XMLSchema.validate`, that raises an error when the XML doesn't conforms
to the schema:

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


Decoding to JSON
----------------

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

Schemas and XML instances processing are based on the class :class:`XMLResource`,
that handles the loading and the iteration of XSD/XML data.
Starting from v1.3.0 :class:`XMLResource` has been empowered with ElementTree-like
XPath API. From the same release a new class :class:`xmlschema.XmlDocument` is
available for representing XML resources with a related schema:

.. doctest::

    >>> import xmlschema
    >>> xml_document = xmlschema.XmlDocument('tests/test_cases/examples/vehicles/vehicles.xml')
    >>> xml_document.schema
    XMLSchema10(name='vehicles.xsd', namespace='http://example.com/vehicles')

This class can be used to derive specialized schema-related classes. An example of
specialization is the class :class:`Wsdl11Document`, usable for validating and
parsing WSDL 1.1 documents, that can be imported from *wsdl* module:

.. doctest::

    >>> from xmlschema.wsdl import Wsdl11Document
    >>> wsdl_document = Wsdl11Document('tests/test_cases/examples/stockquote/stockquoteservice.wsdl')
    >>> wsdl_document.schema
    XMLSchema10(name='wsdl.xsd', namespace='http://schemas.xmlsoap.org/wsdl/')

A parsed WSDL 1.1 document can aggregate a set of WSDL/XSD files for building
interrelated set of definitions in multiple namespaces. The XMLResource base
class and schema validation assure a fully checked WSDL document with
protections against XML attacks.
See :class:`xmlschema.wsdl.Wsdl11Document` API for details.
